import httpx
from app.config import GOOGLE_PLACES_API_KEY, GOOGLE_NEARBY_URL
from fastapi.responses import Response

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
        "radius": radius,            # 検索半径（m）
        "keyword": q,                # 検索ワード（ラーメン等）
        "key": GOOGLE_PLACES_API_KEY,
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
        "maxwidth": maxwidth,                # 画像サイズ
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

