import asyncio
import logging
import re
from datetime import datetime

from app.db.user_pref_repo import get_user_weights
from app.services.ai_summary import extract_ramen_category_mentions, summarize_reviews_30
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
_SEARCH_RADII_M = (1000, 2000, 3000)
_MIN_RESULTS_FOR_STOP = 3

RAMEN_KEYWORDS = (
    "ラーメン",
    "らーめん",
    "中華そば",
    "つけ麺",
    "油そば",
    "まぜそば",
)
NON_RAMEN_KEYWORDS = (
    "喫茶",
    "カフェ",
    "coffee",
    "居酒屋",
    "弁当",
    "定食",
)
NON_RAMEN_TYPES = {
    "cafe",
    "bar",
    "bakery",
}


async def search_ramen_items(
    lat: float,
    lng: float,
    line_user_id: str | None = None,
    offset: int = 0,
    page_size: int = 10,
    search_datetime: str | None = None,
    prioritize_open_now_status: bool = False,
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
            limit=30,
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

    # NOTE:
    # Preference ranking depends on extracted ramen category mentions.
    # Enrich all candidates before sorting so preference weights are reflected.
    await enrich_items(items, search_datetime=search_datetime)

    items = [item for item in items if not item.get("_exclude_as_non_ramen")]

    for item in items:
        item.pop("_exclude_as_non_ramen", None)

    if not items:
        return [], had_error, False, used_radius

    weights = get_user_weights(line_user_id) if line_user_id else {}
    ranked_items = sort_items(
        items,
        weights=weights,
        prioritize_open_now_status=prioritize_open_now_status,
    )
    page_items = ranked_items[offset:offset + page_size]
    has_more = offset + page_size < len(ranked_items)

    return page_items, had_error, has_more, used_radius


async def _enrich_item(
    item: dict[str, object],
    semaphore: asyncio.Semaphore,
    search_datetime: str | None = None,
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
    opening_hours = detail.get("opening_hours") or {}

    item["_exclude_as_non_ramen"] = _should_exclude_non_ramen_shop(
        item=item,
        reviews=reviews,
        editorial_summary=editorial_summary,
    )

    category_task = extract_ramen_category_mentions(editorial_summary, reviews)
    summary_task = summarize_reviews_30(reviews)

    categories_result, summary_result = await asyncio.gather(
        category_task,
        summary_task,
        return_exceptions=True,
    )

    if not isinstance(categories_result, Exception) and categories_result:
        item["category_mentions"] = categories_result
    elif isinstance(categories_result, Exception):
        logger.warning(
            "extract_ramen_category_mentions skipped place_id=%s: %s",
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

    hours_text = _hours_for_date(opening_hours, search_datetime)
    if hours_text:
        item["business_hours_text"] = hours_text

    open_at_target = _is_open_at_datetime(opening_hours, search_datetime)
    if open_at_target is not None:
        item["open_at_search_time"] = open_at_target


def _hours_for_date(opening_hours: dict[str, object], search_datetime: str | None) -> str | None:
    if not search_datetime:
        return None

    weekday_text = opening_hours.get("weekday_text")
    if not isinstance(weekday_text, list) or len(weekday_text) != 7:
        return None

    try:
        target_dt = datetime.fromisoformat(search_datetime)
    except ValueError:
        return None

    entry = weekday_text[target_dt.weekday()]
    if not isinstance(entry, str):
        return None

    if "：" in entry:
        hours = entry.split("：", 1)[1].strip()
    elif ":" in entry:
        hours = entry.split(":", 1)[1].strip()
    else:
        hours = entry.strip()

    if not hours:
        return None

    normalized = _normalize_business_hours_text(hours)
    normalized = re.sub(r"\s*[、,，]\s*", " / ", normalized)
    normalized = re.sub(r"\s*/\s*", " / ", normalized)
    return normalized.strip()


def _normalize_business_hours_text(hours: str) -> str:
    normalized = hours.replace("～", "〜").replace("~", "〜")
    normalized = normalized.translate(str.maketrans("０１２３４５６７８９：", "0123456789:"))

    def replace_japanese_time(match: re.Match[str]) -> str:
        am_pm = match.group(1)
        hour = int(match.group(2))
        minute = int(match.group(3) or "0")

        if am_pm == "午前":
            hour = 0 if hour == 12 else hour
        elif am_pm == "午後":
            hour = 12 if hour == 12 else hour + 12

        if hour >= 24 or minute >= 60:
            return match.group(0)

        return f"{hour:02d}:{minute:02d}"

    normalized = re.sub(
        r"(午前|午後)?\s*(\d{1,2})\s*(?:[:時]\s*(\d{1,2}))?\s*分?",
        replace_japanese_time,
        normalized,
    )
    normalized = re.sub(r"\b([01]\d|2[0-3])([0-5]\d)\b", r"\1:\2", normalized)
    return normalized


def _is_open_at_datetime(opening_hours: dict[str, object], search_datetime: str | None) -> bool | None:
    if not search_datetime:
        return None

    periods = opening_hours.get("periods")
    if not isinstance(periods, list) or not periods:
        return None

    try:
        target_dt = datetime.fromisoformat(search_datetime)
    except ValueError:
        return None

    # Python weekday: Mon=0..Sun=6
    # Google opening_hours.periods day: Sun=0..Sat=6
    target_day = (target_dt.weekday() + 1) % 7
    target_minutes = target_dt.hour * 60 + target_dt.minute

    for period in periods:
        if not isinstance(period, dict):
            continue

        open_info = period.get("open")
        if not isinstance(open_info, dict):
            continue

        open_day = open_info.get("day")
        open_time = open_info.get("time")
        if not isinstance(open_day, int) or not isinstance(open_time, str) or len(open_time) != 4:
            continue

        try:
            open_minutes = int(open_time[:2]) * 60 + int(open_time[2:])
        except ValueError:
            continue

        close_info = period.get("close")
        if isinstance(close_info, dict):
            close_day = close_info.get("day")
            close_time = close_info.get("time")
            if not isinstance(close_day, int) or not isinstance(close_time, str) or len(close_time) != 4:
                continue
            try:
                close_minutes = int(close_time[:2]) * 60 + int(close_time[2:])
            except ValueError:
                continue
        else:
            # closeが無い場合は24時間営業扱い
            close_day = (open_day + 1) % 7
            close_minutes = open_minutes

        # 同日内の営業
        if open_day == close_day and open_minutes < close_minutes:
            if target_day == open_day and open_minutes <= target_minutes < close_minutes:
                return True
            continue

        # 日跨ぎ営業（または24時間営業）
        if target_day == open_day and target_minutes >= open_minutes:
            return True
        if target_day == close_day and target_minutes < close_minutes:
            return True

        span_day = (open_day + 1) % 7
        while span_day != close_day:
            if target_day == span_day:
                return True
            span_day = (span_day + 1) % 7

    return False


def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _has_ramen_signal(text: str) -> bool:
    return _contains_any_keyword(text, RAMEN_KEYWORDS)


def _has_non_ramen_signal(text: str) -> bool:
    return _contains_any_keyword(text, NON_RAMEN_KEYWORDS)


def _should_exclude_non_ramen_shop(
    item: dict[str, object],
    reviews: list[dict[str, object]],
    editorial_summary: str | None,
) -> bool:
    name = (item.get("name") or "") if isinstance(item.get("name"), str) else ""
    types = {
        t.lower()
        for t in (item.get("types") or [])
        if isinstance(t, str)
    }
    summary = editorial_summary or ""

    review_texts = [
        text
        for review in reviews
        for text in [review.get("text")]
        if isinstance(text, str) and text.strip()
    ]
    menu_texts = [
        t
        for t in [item.get("menu_text"), item.get("menu_summary")]
        if isinstance(t, str) and t.strip()
    ]
    photo_texts = [
        t
        for t in [item.get("photo_caption"), item.get("photo_description")]
        if isinstance(t, str) and t.strip()
    ]
    has_ramen_in_name = _has_ramen_signal(name)
    has_non_ramen_in_name = _has_non_ramen_signal(name)
    has_ramen_type = any("ramen" in t or "noodle" in t for t in types)
    has_non_ramen_type = bool(types.intersection(NON_RAMEN_TYPES))

    # 店名/業態が明確に非ラーメンのときは、口コミノイズに引っ張られないよう先に除外
    if has_non_ramen_in_name and not has_ramen_in_name:
        return True
    if has_non_ramen_type and not has_ramen_type and not has_ramen_in_name:
        return True

    ramen_signals = [
        has_ramen_in_name,
        has_ramen_type,
        _has_ramen_signal(summary),
        any(_has_ramen_signal(text) for text in review_texts),
        any(_has_ramen_signal(text) for text in menu_texts),
        any(_has_ramen_signal(text) for text in photo_texts),
    ]
    if any(ramen_signals):
        return False

    review_non_ramen_hits = sum(
        1 for text in review_texts if _has_non_ramen_signal(text)
    )
    review_ramen_hits = sum(
        1 for text in review_texts if _has_ramen_signal(text)
    )

    if review_non_ramen_hits >= 3 and review_ramen_hits == 0:
        return True

    non_ramen_signals = [
        has_non_ramen_in_name,
        has_non_ramen_type,
        _has_non_ramen_signal(summary),
    ]

    if not any(non_ramen_signals):
        return False

    if not review_texts and not summary:
        return False

    return True


async def enrich_items(items: list[dict[str, object]], search_datetime: str | None = None) -> None:
    semaphore = asyncio.Semaphore(_ENRICH_CONCURRENCY)
    tasks = [_enrich_item(item, semaphore, search_datetime=search_datetime) for item in items]

    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=False),
            timeout=_ENRICH_TOTAL_TIMEOUT_SEC,
        )
    except TimeoutError:
        logger.warning("enrich_items timeout: returned without full enrichment")
