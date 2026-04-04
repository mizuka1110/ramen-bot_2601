import asyncio
import logging
from datetime import datetime

from app.db.user_pref_repo import get_user_weights
from app.services.ai_summary import extract_ramen_categories, summarize_reviews_30
from app.services.places import (
    get_place_opening_hours,
    get_place_reviews,
    is_open_at_jst,
    nearby_result_to_items,
    search_nearby,
)
from app.services.places_cache import get_cached, set_cached
from app.services.ranking import sort_items

logger = logging.getLogger("uvicorn.error")

_ENRICH_CONCURRENCY = 4
_PER_ITEM_TIMEOUT_SEC = 8.0
_ENRICH_TOTAL_TIMEOUT_SEC = 12.0
_SEARCH_RADII_M = (1000, 2000, 3000)
_MIN_RESULTS_FOR_STOP = 3


async def search_ramen_items(
    lat: float,
    lng: float,
    line_user_id: str | None = None,
    offset: int = 0,
    page_size: int = 10,
    target_datetime_jst: datetime | None = None,
) -> tuple[list[dict[str, object]], bool, bool, int | None]:
    q = "ラーメン"
    had_error = False
    items_by_place_id: dict[str, dict[str, object]] = {}
    used_radius: int | None = None

    for radius in _SEARCH_RADII_M:
        used_radius = radius
        cached = get_cached(lat, lng, q, radius)

        try:
            if cached:
                result = cached
            else:
                result = await search_nearby(lat=lat, lng=lng, q=q, radius=radius)
                set_cached(lat, lng, q, radius, result)
        except Exception:
            had_error = True
            if cached:
                result = cached
            else:
                continue

        radius_items = nearby_result_to_items(
            result,
            user_lat=lat,
            user_lng=lng,
            limit=20,
        )

        for item in radius_items:
            place_id_value = item.get("place_id")
            if isinstance(place_id_value, str) and place_id_value:
                dedupe_key = place_id_value
            else:
                dedupe_key = f"{item.get('name')}:{item.get('lat')}:{item.get('lng')}"
            items_by_place_id[dedupe_key] = item

        if len(items_by_place_id) >= _MIN_RESULTS_FOR_STOP:
            break

    items = list(items_by_place_id.values())

    if not items:
        return [], had_error, False, used_radius

    if target_datetime_jst is not None:
        items = await filter_items_open_at_datetime(items, target_datetime_jst)
    else:
        open_now_items = [item for item in items if item.get("open_now") is True]
        if open_now_items:
            items = open_now_items

    if not items:
        return [], had_error, False, used_radius

    # NOTE:
    # Preference ranking depends on extracted ramen categories.
    # Enrich all candidates before sorting so "中毒" etc. are reflected.
    await enrich_items(items)

    weights = get_user_weights(line_user_id) if line_user_id else {}
    ranked_items = sort_items(items, weights=weights)
    page_items = ranked_items[offset:offset + page_size]
    has_more = offset + page_size < len(ranked_items)

    return page_items, had_error, has_more, used_radius


async def filter_items_open_at_datetime(
    items: list[dict[str, object]],
    target_datetime_jst: datetime,
) -> list[dict[str, object]]:
    semaphore = asyncio.Semaphore(_ENRICH_CONCURRENCY)

    async def _check_open(item: dict[str, object]) -> bool:
        place_id_value = item.get("place_id")
        if not isinstance(place_id_value, str) or not place_id_value:
            return False
        async with semaphore:
            try:
                details = await asyncio.wait_for(
                    get_place_opening_hours(place_id_value),
                    timeout=_PER_ITEM_TIMEOUT_SEC,
                )
            except Exception as e:
                logger.warning(
                    "get_place_opening_hours skipped place_id=%s: %s",
                    place_id_value,
                    e,
                )
                return False

        periods = details.get("periods")
        if not isinstance(periods, list):
            return False

        is_open = is_open_at_jst(periods, target_datetime_jst)
        return bool(is_open)

    results = await asyncio.gather(*[_check_open(item) for item in items], return_exceptions=True)
    filtered: list[dict[str, object]] = []
    for item, result in zip(items, results):
        if isinstance(result, Exception):
            continue
        if result:
            filtered.append(item)
    return filtered


async def _enrich_item(
    item: dict[str, object],
    semaphore: asyncio.Semaphore,
) -> None:
    place_id_value = item.get("place_id")
    if not isinstance(place_id_value, str) or not place_id_value:
        return

    async with semaphore:
        try:
            detail = await asyncio.wait_for(
                get_place_reviews(place_id_value),
                timeout=_PER_ITEM_TIMEOUT_SEC,
            )
        except Exception as e:
            logger.warning(
                "get_place_reviews skipped place_id=%s: %s",
                place_id_value,
                e,
            )
            return

    reviews = detail.get("reviews") or []
    editorial_summary = detail.get("editorial_summary")

    category_task = extract_ramen_categories(editorial_summary, reviews)
    summary_task = summarize_reviews_30(reviews)

    categories_result, summary_result = await asyncio.gather(
        category_task,
        summary_task,
        return_exceptions=True,
    )

    if not isinstance(categories_result, Exception) and categories_result:
        item["categories"] = categories_result
    elif isinstance(categories_result, Exception):
        logger.warning(
            "extract_ramen_categories skipped place_id=%s: %s",
            place_id_value,
            categories_result,
        )

    if not isinstance(summary_result, Exception) and summary_result:
        item["review_summary"] = summary_result
    elif isinstance(summary_result, Exception):
        logger.warning(
            "summarize_reviews_30 skipped place_id=%s: %s",
            place_id_value,
            summary_result,
        )


async def enrich_items(items: list[dict[str, object]]) -> None:
    semaphore = asyncio.Semaphore(_ENRICH_CONCURRENCY)
    tasks = [_enrich_item(item, semaphore) for item in items]

    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=False),
            timeout=_ENRICH_TOTAL_TIMEOUT_SEC,
        )
    except TimeoutError:
        logger.warning("enrich_items timeout: returned without full enrichment")
