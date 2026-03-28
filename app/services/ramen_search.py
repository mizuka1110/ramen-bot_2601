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

    await attach_categories(items)
    weights = get_user_weights(line_user_id) if line_user_id else {}
    items = sort_items(items, weights=weights)
    items = items[:10]
    await attach_review_summaries(items)
    return items, had_error


async def _attach_category(item: dict[str, object]) -> None:
    try:
        place_id_value = item.get("place_id")
        if not isinstance(place_id_value, str) or not place_id_value:
            return

        detail = await get_place_reviews(place_id_value)
        reviews = detail.get("reviews") or []
        editorial_summary = detail.get("editorial_summary")

        categories = await extract_ramen_categories(editorial_summary, reviews)

        if categories:
            item["categories"] = categories

    except Exception as e:
        logger.exception(
            "attach_categories failed place_id=%s: %s",
            item.get("place_id"),
            e,
        )


async def attach_categories(items: list[dict[str, object]]) -> None:
    await asyncio.gather(*[_attach_category(item) for item in items])


async def _attach_review_summary(item: dict[str, object]) -> None:
    try:
        place_id_value = item.get("place_id")
        if not isinstance(place_id_value, str) or not place_id_value:
            return

        detail = await get_place_reviews(place_id_value)
        reviews = detail.get("reviews") or []

        summary = await summarize_reviews_30(reviews)

        if summary:
            item["review_summary"] = summary

    except Exception as e:
        logger.exception(
            "attach_review_summaries failed place_id=%s: %s",
            item.get("place_id"),
            e,
        )


async def attach_review_summaries(items: list[dict[str, object]]) -> None:
    await asyncio.gather(*[_attach_review_summary(item) for item in items])