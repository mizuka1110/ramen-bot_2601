import logging

from app.services.ai_summary import summarize_reviews_30
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
            limit=10,
        )
        items = sort_items(items)

        if items:
            break

    if not items:
        return [], had_error

    await attach_review_summaries(items[:3])
    return items, had_error


async def attach_review_summaries(items: list[dict[str, object]]) -> None:
    for item in items:
        try:
            place_id_value = item.get("place_id")
            if not isinstance(place_id_value, str) or not place_id_value:
                continue

            reviews = await get_place_reviews(place_id_value)
            summary = await summarize_reviews_30(reviews)

            if summary:
                item["review_summary"] = summary

        except Exception as e:
            logger.exception(
                "AI summary failed place_id=%s: %s",
                item.get("place_id"),
                e,
            )