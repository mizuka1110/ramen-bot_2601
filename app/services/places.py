import httpx
import math
from app.config import GOOGLE_PLACES_API_KEY, GOOGLE_NEARBY_URL


# =========================
# Google Places 系のエラー用
# =========================
class PlacesUpstreamError(Exception):
    def __init__(self, status: str, message: str | None = None):
        self.status = status
        self.message = message
        super().__init__(f"{status}: {message}")


# ==================================================
# ① 周辺検索（Nearby Search）
# ==================================================
# 役割：
# 「この場所の近くに、条件に合う店を一覧で返してもらう」
#
# ★ここでは「写真を取りに行かない」
# ★写真ID（photo_reference）を含んだJSONを返すだけ
async def search_nearby(lat: float, lng: float, q: str, radius: int) -> dict:
    if not GOOGLE_PLACES_API_KEY:
        raise PlacesUpstreamError("CONFIG_ERROR", "PLACES_API_KEY is missing")

    params = {
        "location": f"{lat},{lng}",  # 緯度,経度
        "radius": radius,  # 検索半径（m）
        "keyword": q,  # 検索ワード（ラーメン等）
        "key": GOOGLE_PLACES_API_KEY,
        "language": "ja",
        "region": "jp",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(GOOGLE_NEARBY_URL, params=params)
        r.raise_for_status()
        return r.json()
    # ↑ ここで返るJSONの中に
    #   photos[0].photo_reference が「すでに入っている」


# ==================================================
# ② 写真取得（Photo API）
# ==================================================
# 役割：
# 「photo_reference を渡されたら、その写真そのものを取りに行く」
#
# ★JSONではなく「画像」が返る
# ★search_nearby とは完全に別API
async def fetch_photo(photo_reference: str, maxwidth: int = 600) -> httpx.Response:
    if not GOOGLE_PLACES_API_KEY:
        raise PlacesUpstreamError("CONFIG_ERROR", "PLACES_API_KEY is missing")

    url = "https://maps.googleapis.com/maps/api/place/photo"

    params = {
        "photo_reference": photo_reference,  # ← search_nearby で取れたID
        "maxwidth": maxwidth,  # 画像サイズ
        "key": GOOGLE_PLACES_API_KEY,
    }

    async with httpx.AsyncClient(
        timeout=10.0,
        follow_redirects=True,  # ← Photo API はリダイレクトする
    ) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r
    # ↑ r.content が「画像のバイナリ」


def _flat_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """ざっくり直線距離（m）。表示用途ならこれで十分。"""
    km_per_deg_lat = 111.0
    km_per_deg_lng = 111.0 * math.cos(math.radians(lat1))
    dx = (lng2 - lng1) * km_per_deg_lng
    dy = (lat2 - lat1) * km_per_deg_lat
    return int(round(math.sqrt(dx * dx + dy * dy) * 1000))


def nearby_result_to_items(result: dict, user_lat: float, user_lng: float, limit: int = 10) -> list[dict]:
    """Google Nearby Search の生JSON → Flex用 items（distance_m入り）に変換"""
    raw_items = (result.get("results") or [])[:limit]

    items: list[dict] = []
    for r in raw_items:
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
                "distance_m": _flat_distance_m(user_lat, user_lng, lat, lng),  # ← messages.py がこれを見る
            }
        )

    return items
