import asyncio
import logging

from app.db.user_pref_repo import get_user_weights
from app.services.ai_summary import extract_ramen_categories, summarize_reviews_30
from app.services.places import (
    get_place_reviews,
    nearby_result_to_items,
    search_nearby,
)
from app.services.places_cache import get_cached, set_cached
from app.services.ranking import sort_items

logger = logging.getLogger("uvicorn.error")

_ENRICH_CONCURRENCY = 4
_PER_ITEM_TIMEOUT_SEC = 8.0
_ENRICH_TOTAL_TIMEOUT_SEC = 12.0


async def search_ramen_items(
    lat: float,
    lng: float,
    line_user_id: str | None = None,
) -> tuple[list[dict[str, object]], bool]:
    q = "ラーメン"
    had_error = False
    items: list[dict[str, object]] = []

    for radius in (1000, 2000, 3000):
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

        items = nearby_result_to_items(
            result,
            user_lat=lat,
            user_lng=lng,
            limit=15,
        )

        if items:
            break

    if not items:
        return [], had_error

    weights = get_user_weights(line_user_id) if line_user_id else {}
    items = sort_items(items, weights=weights)
    items = items[:10]

    await enrich_items(items)
    return items, had_error


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
