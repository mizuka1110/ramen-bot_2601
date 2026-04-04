import httpx
import math
from datetime import datetime, timedelta
from app.config import GOOGLE_PLACES_API_KEY, GOOGLE_NEARBY_URL

GOOGLE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
NON_STORE_KEYWORDS = (
    # 飲食店（ラーメン以外のジャンル）
    "寿司", "すし", "鮨",
    "とんかつ",
    "焼肉", "焼き肉",
    "天ぷら", "てんぷら",

    # 施設・観光スポット・その他
    "モニュメント", "記念碑", "像",
    "ミュージアム", "博物館",
    "ファクトリー", "工場",
)

FOOD_PLACE_TYPES = {
    "restaurant",
    "meal_takeaway",
    "meal_delivery",
}
EXCLUDE_TYPES = {
    "tourist_attraction",
    "museum",
    "amusement_park",
    "store",
    "shopping_mall",
}


class PlacesUpstreamError(Exception):
    def __init__(self, status: str, message: str | None = None):
        self.status = status
        self.message = message
        super().__init__(f"{status}: {message}")


# ==================================================
# ① 周辺検索（Nearby Search）
# ==================================================
async def search_nearby(lat: float, lng: float, q: str, radius: int) -> dict:
    if not GOOGLE_PLACES_API_KEY:
        raise PlacesUpstreamError("CONFIG_ERROR", "PLACES_API_KEY is missing")

    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "keyword": q,
        "key": GOOGLE_PLACES_API_KEY,
        "language": "ja",
        "region": "jp",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(GOOGLE_NEARBY_URL, params=params)
        r.raise_for_status()
        return r.json()


# ==================================================
# ② 写真取得（Photo API）
# ==================================================
async def fetch_photo(photo_reference: str, maxwidth: int = 600) -> httpx.Response:
    if not GOOGLE_PLACES_API_KEY:
        raise PlacesUpstreamError("CONFIG_ERROR", "PLACES_API_KEY is missing")

    url = "https://maps.googleapis.com/maps/api/place/photo"
    params = {
        "photo_reference": photo_reference,
        "maxwidth": maxwidth,
        "key": GOOGLE_PLACES_API_KEY,
    }

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r


# ==================================================
# ③ 店舗詳細（Place Details / 口コミ取得）
# ==================================================
async def get_place_reviews(place_id: str) -> dict:
    if not GOOGLE_PLACES_API_KEY:
        raise PlacesUpstreamError("CONFIG_ERROR", "PLACES_API_KEY is missing")

    params = {
        "place_id": place_id,
        "fields": "reviews,editorial_summary",
        "language": "ja",
        "key": GOOGLE_PLACES_API_KEY,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(GOOGLE_DETAILS_URL, params=params)
        r.raise_for_status()
        data = r.json()

    result = data.get("result", {}) or {}

    reviews = result.get("reviews", []) or []
    editorial_summary = (result.get("editorial_summary") or {}).get("overview")

    return {
        "reviews": [
            {
                "text": rev.get("text"),
                "rating": rev.get("rating"),
            }
            for rev in reviews
            if rev.get("text")
        ],
        "editorial_summary": editorial_summary,
    }


async def get_place_opening_hours(place_id: str) -> dict[str, object]:
    if not GOOGLE_PLACES_API_KEY:
        raise PlacesUpstreamError("CONFIG_ERROR", "PLACES_API_KEY is missing")

    params = {
        "place_id": place_id,
        "fields": "opening_hours",
        "language": "ja",
        "key": GOOGLE_PLACES_API_KEY,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(GOOGLE_DETAILS_URL, params=params)
        r.raise_for_status()
        data = r.json()

    result = data.get("result", {}) or {}
    opening_hours = result.get("opening_hours") or {}
    return {
        "periods": opening_hours.get("periods") or [],
    }


def is_open_at_jst(periods: list[dict], target_dt_jst: datetime) -> bool | None:
    if not periods:
        return None

    sunday_offset = (target_dt_jst.weekday() + 1) % 7
    week_start_sunday = (target_dt_jst - timedelta(days=sunday_offset)).date()

    for period in periods:
        open_info = period.get("open") or {}
        close_info = period.get("close") or {}
        open_day = open_info.get("day")
        open_time = open_info.get("time")

        if open_day is None or not isinstance(open_time, str) or len(open_time) != 4:
            continue

        try:
            open_hour = int(open_time[:2])
            open_minute = int(open_time[2:])
            open_day_int = int(open_day)
        except (TypeError, ValueError):
            continue

        open_date = week_start_sunday + timedelta(days=open_day_int)
        open_dt_base = datetime(
            open_date.year,
            open_date.month,
            open_date.day,
            open_hour,
            open_minute,
            tzinfo=target_dt_jst.tzinfo,
        )

        if close_info:
            close_day = close_info.get("day")
            close_time = close_info.get("time")
            if close_day is None or not isinstance(close_time, str) or len(close_time) != 4:
                continue
            try:
                close_hour = int(close_time[:2])
                close_minute = int(close_time[2:])
                close_day_int = int(close_day)
            except (TypeError, ValueError):
                continue
            close_date = week_start_sunday + timedelta(days=close_day_int)
            close_dt_base = datetime(
                close_date.year,
                close_date.month,
                close_date.day,
                close_hour,
                close_minute,
                tzinfo=target_dt_jst.tzinfo,
            )
        else:
            close_dt_base = open_dt_base + timedelta(days=1)

        for week_shift in (-7, 0, 7):
            open_dt = open_dt_base + timedelta(days=week_shift)
            close_dt = close_dt_base + timedelta(days=week_shift)
            if close_dt <= open_dt:
                close_dt += timedelta(days=7)

            if open_dt <= target_dt_jst < close_dt:
                return True

    return False


def _flat_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    km_per_deg_lat = 111.0
    km_per_deg_lng = 111.0 * math.cos(math.radians(lat1))
    dx = (lng2 - lng1) * km_per_deg_lng
    dy = (lat2 - lat1) * km_per_deg_lat
    return int(round(math.sqrt(dx * dx + dy * dy) * 1000))


def _is_ramen_shop_candidate(place: dict) -> bool:
    name = (place.get("name") or "").strip()
    if any(keyword in name for keyword in NON_STORE_KEYWORDS):
        return False

    types = set(place.get("types") or [])

    if types.intersection(EXCLUDE_TYPES):
        return False

    return bool(types.intersection(FOOD_PLACE_TYPES))


def nearby_result_to_items(result: dict, user_lat: float, user_lng: float, limit: int = 10) -> list[dict]:
    raw_items = result.get("results") or []

    items: list[dict] = []
    for r in raw_items:
        if not _is_ramen_shop_candidate(r):
            continue

        loc = (r.get("geometry") or {}).get("location") or {}
        lat = loc.get("lat")
        lng = loc.get("lng")
        if lat is None or lng is None:
            continue

        items.append(
            {
                "name": r.get("name"),
                "vicinity": r.get("vicinity"),
                "lat": lat,
                "lng": lng,
                "open_now": (r.get("opening_hours") or {}).get("open_now"),
                "rating": r.get("rating"),
                "rating_count": r.get("user_ratings_total"),
                "photo_reference": ((r.get("photos") or [{}])[0].get("photo_reference")),
                "place_id": r.get("place_id"),
                "distance_m": _flat_distance_m(user_lat, user_lng, lat, lng),
            }
        )

        if len(items) >= limit:
            break

    return items
