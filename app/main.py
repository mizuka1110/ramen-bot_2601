import logging
import math
import httpx
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.services.places import search_nearby, PlacesUpstreamError
from app.config import GOOGLE_PLACES_API_KEY
from app.services.line_client import line_push
from app.line.webhook import router as line_router
from app.line.messages import build_flex_carousel

app = FastAPI()
logger = logging.getLogger("uvicorn.error")

# 静的ファイルを /static パスで配信するための設定。
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(line_router)


# NOTE:
# 距離は「厳密な道のり」ではなく、表示用として十分な簡易距離でOK
def flat_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    km_per_deg_lat = 111.32
    km_per_deg_lng = 111.32 * math.cos(math.radians(lat1))
    dx = (lng2 - lng1) * km_per_deg_lng
    dy = (lat2 - lat1) * km_per_deg_lat
    return math.sqrt(dx * dx + dy * dy)


@app.get("/shops/search")
async def shops_search(
    lat: float = Query(...),
    lng: float = Query(...),
    q: str = Query(..., min_length=1),
    radius: int = Query(1000, ge=1, le=50000),
):
    """
    Nearby Search の結果を、Flex向けに整形して返す（写真は photo_reference だけ返す）
    """
    try:
        data = await search_nearby(lat, lng, q, radius)
    except PlacesUpstreamError as e:
        logger.error("places config/upstream error: %s", e)
        raise HTTPException(status_code=500, detail="Upstream error")
    except Exception:
        logger.exception("places request failed")
        raise HTTPException(status_code=500, detail="Upstream error")

    status = data.get("status")

    if status == "ZERO_RESULTS":
        return {"items": [], "count": 0}

    if status in ("REQUEST_DENIED", "INVALID_REQUEST"):
        raise HTTPException(status_code=500, detail="Upstream error")

    if status != "OK":
        raise HTTPException(status_code=500, detail="Upstream error")

    results = (data.get("results") or [])[:10]

    items: list[dict] = []
    for r in results:
        loc = (r.get("geometry") or {}).get("location") or {}
        shop_lat = loc.get("lat")
        shop_lng = loc.get("lng")

        if shop_lat is None or shop_lng is None:
            continue

        km = flat_distance_km(lat, lng, shop_lat, shop_lng)
        distance_m = int(round(km * 1000))

        photos = r.get("photos") or []
        photo_ref = (photos[0] or {}).get("photo_reference") if photos else None

        opening_hours = r.get("opening_hours") or {}
        open_now = opening_hours.get("open_now")

        place_id = r.get("place_id")
        if not place_id:
            continue

        maps_url = f"https://www.google.com/maps/search/?api=1&query_place_id={place_id}"

        items.append(
            {
                "place_id": place_id,
                "name": r.get("name"),
                "vicinity": r.get("vicinity"),
                "lat": shop_lat,
                "lng": shop_lng,
                "distance_m": distance_m,
                "rating": r.get("rating"),
                "rating_count": r.get("user_ratings_total"),
                "open_now": open_now,
                "photo_reference": photo_ref,  # ← ここが写真のID
                "maps_url": maps_url,
            }
        )

    return {"items": items, "count": len(items)}


@app.get("/shops/photo")
async def shops_photo(ref: str = Query(...), maxwidth: int = Query(600, ge=64, le=1600)):
    """
    Google Photo API を代理で叩いて、画像バイナリを返す
    (Flexの hero.url から参照する)
    """
    if not GOOGLE_PLACES_API_KEY:
        raise HTTPException(status_code=500, detail="GOOGLE_PLACES_API_KEY is empty")

    url = "https://maps.googleapis.com/maps/api/place/photo"
    params = {
        "photo_reference": ref,
        "maxwidth": maxwidth,
        "key": GOOGLE_PLACES_API_KEY,
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200 or not r.content:
        raise HTTPException(status_code=404, detail="Photo not found")

    headers = {"Cache-Control": "public, max-age=86400"}
    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "image/jpeg"),
        headers=headers,
    )


############### ここからカルーセル ###############

# def _open_label(open_now: bool | None) -> tuple[str, str]:
#     if open_now is True:
#         return ("営業中", "#16A34A")
#     if open_now is False:
#         return ("営業時間外", "#6B7280")
#     return ("営業時間不明", "#6B7280")


# def _photo_url(photo_reference: str | None, maxwidth: int = 600) -> str:
#     """
#     LINEが取りにいけるURLを返す必要がある。
#     PUBLIC_BASE_URL が未設定の場合は、とりあえずプレースホルダー。
#     """
#     base = (os.getenv("PUBLIC_BASE_URL") or "").rstrip("/")

#     if photo_reference and base:
#         return f"{base}/shops/photo?ref={photo_reference}&maxwidth={maxwidth}"

#     if base:
#         return f"{base}/static/no-image.jpg"

#     # base が無い = LINEが見に行けるURLが作れないのでプレースホルダー
#     return "https://via.placeholder.com/600x338?text=No+Image"


# def shop_to_bubble(item: dict) -> dict:
#     label_text, label_bg = _open_label(item.get("open_now"))

#     vicinity = item.get("vicinity") or ""
#     distance_m = item.get("distance_m")
#     meta = f"{vicinity}｜{distance_m}m" if distance_m is not None else vicinity

#     rating = item.get("rating")
#     rating_count = item.get("rating_count")
#     rating_text = None
#     if rating is not None:
#         rating_text = f"★{rating}"
#         if rating_count is not None:
#             rating_text += f"（{rating_count}）"
#     lat = item.get("lat")
#     lng = item.get("lng")

#     map_url = (
#     f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
#     if lat and lng
#     else item.get("maps_url")
# )

#     body_contents = [
#         {
#             "type": "box",
#             "layout": "horizontal",
#             "contents": [
#                 {
#                     "type": "text",
#                     "text": label_text,
#                     "size": "xxs",
#                     "weight": "bold",
#                     "color": "#FFFFFF",
#                 }
#             ],
#             "backgroundColor": label_bg,
#             "cornerRadius": "999px",
#             "paddingAll": "4px",
#             "paddingStart": "10px",
#             "paddingEnd": "10px",
#             "flex": 0,
#             "maxWidth": "55px", 
#         },
#         {
#             "type": "text",
#             "text": item.get("name") or "-",
#             "weight": "bold",
#             "size": "md",
#             "wrap": True,
#         },
#         {
#             "type": "text",
#             "text": meta,
#             "size": "sm",
#             "color": "#6B7280",
#             "wrap": True,
#         },
#     ]

#     if rating_text:
#         body_contents.append({
#             "type": "text",
#             "text": rating_text,
#             "size": "sm",
#             "color": "#111827",
#             "wrap": True,
#         })
    
#     return {
#         "type": "bubble",
#         "hero": {
#             "type": "image",
#             "url": _photo_url(item.get("photo_reference")),
#             "size": "full",
#             "aspectRatio": "16:9",  # ← 縦長すぎ対策
#             "aspectMode": "cover",
#         },
#         "body": {
#             "type": "box",
#             "layout": "vertical",
#             "spacing": "sm",
#             "contents": body_contents,
#         },
#         "footer": {
#             "type": "box",
#             "layout": "vertical",
#             "spacing": "sm",
#             "contents": [{
#                 "type": "button",
#                 "style": "secondary",
#                 "action": {
#                     "type": "uri",
#                     "label": "地図アプリを開く ",
#                     "uri": map_url,
#                 },
#             }],
#         },
#     }


# def build_flex_carousel(items: list[dict]) -> dict:
#     bubbles = [shop_to_bubble(x) for x in (items or [])[:10]]
#     return {
#         "type": "flex",
#         "altText": "近くのお店",
#         "contents": {
#             "type": "carousel",
#             "contents": bubbles,
#         },
#     }


# 以下はテスト段階でLINEからの指示を疑似的に作ったもの
# LINE側と繋がったら、コメントアウトする。
# @app.post("/line/webhook")
# async def line_webhook(payload: dict):
#     logger.info("LINE webhook payload: %s", payload)
#     return {"ok": True}


@app.post("/debug/push")
async def debug_push(lat: float, lng: float):
    try:
        user_id = os.getenv("LINE_USER_ID")
        if not user_id:
            raise ValueError("LINE_USER_ID is empty")

        result = await shops_search(lat=lat, lng=lng, q="ラーメン", radius=1000)
        items = result.get("items") if isinstance(result, dict) else None
        if not items:
            raise ValueError(f"shops_search returned no items: {result}")

        # ここで hero.url の例をログに出す（写真が出ない時の最短デバッグ）
        logger.info("PUBLIC_BASE_URL=%s", os.getenv("PUBLIC_BASE_URL"))
        logger.info("hero_url_example=%s", _photo_url(items[0].get("photo_reference")))

        flex = build_flex_carousel(items)
        await line_push(user_id, [flex])

        return {"ok": True}

    except Exception as e:
        logger.exception("debug_push failed")
        raise HTTPException(status_code=500, detail=str(e))
    #－－－－－－－－－－－－テストここまでーーーーーーーーーーーーーー
