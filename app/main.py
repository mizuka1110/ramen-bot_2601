import logging
import math
import httpx
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.services.places import search_nearby, PlacesUpstreamError
from app.config import GOOGLE_PLACES_API_KEY
from app.line.webhook import router as line_router

from fastapi.responses import FileResponse

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

        maps_url = (
            f"https://www.google.com/maps/search/?api=1&query_place_id={place_id}"
        )

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
async def shops_photo(
    ref: str = Query(...), maxwidth: int = Query(600, ge=64, le=1600)
):
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
from fastapi import Request

##LIFF

@app.get("/preferences")
async def preferences_page():
    return FileResponse("app/static/preferences.html")

##デバッグ用

# @app.post("/debug/push")
# async def debug_push(lat: float, lng: float):
#     try:
#         user_id = os.getenv("LINE_USER_ID")
#         if not user_id:
#             raise ValueError("LINE_USER_ID is empty")

#         result = await shops_search(lat=lat, lng=lng, q="ラーメン", radius=1000)
#         items = result.get("items") if isinstance(result, dict) else []

#         if not items:
#             await line_push(
#                 user_id,
#                 [{"type": "text", "text": "近くにラーメン屋が見つからなかったよ…🍜"}],
#             )
#             return {"ok": True, "count": 0}

#         logger.info("PUBLIC_BASE_URL=%s", os.getenv("PUBLIC_BASE_URL"))

#         flex = build_flex_carousel(items)
#         await line_push(user_id, [flex])

#         return {"ok": True, "count": len(items)}
       

    # except Exception as e:
    #     logger.exception("debug_push failed")
    #     raise HTTPException(status_code=500, detail=str(e))


