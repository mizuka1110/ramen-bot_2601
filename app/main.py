from fastapi import FastAPI, HTTPException, Query
import logging
import math

from app.services.places import search_nearby, PlacesUpstreamError

app = FastAPI()
logger = logging.getLogger("uvicorn.error")


# 距離計算関数（簡易ピタゴラス距離）
def flat_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    km_per_deg_lat = 111.32
    km_per_deg_lng = 111.32 * math.cos(math.radians(lat1))  # 緯度補正だけ入れる簡易版

    dx = (lng2 - lng1) * km_per_deg_lng
    dy = (lat2 - lat1) * km_per_deg_lat

    return math.sqrt(dx * dx + dy * dy)


# Google Places apiで検索をかけて結果をjsonで取ってくる
@app.get("/shops/search")
async def shops_search(
    lat: float = Query(...),
    lng: float = Query(...),
    q: str = Query(..., min_length=1),
    radius: int = Query(1000, ge=1, le=50000),
):
    try:
        data = await search_nearby(lat, lng, q, radius)
    except PlacesUpstreamError as e:
        logger.error("places config/upstream error: %s", e)
        raise HTTPException(status_code=500, detail="Upstream error")
    except Exception as e:
        logger.exception("places request failed: %s", e)
        raise HTTPException(status_code=500, detail="Upstream error")

    status = data.get("status")

    if status == "ZERO_RESULTS":
        return {"items": [], "count": 0}

    if status in ("REQUEST_DENIED", "INVALID_REQUEST"):
        logger.error("google places denied: %s / %s", status, data.get("error_message"))
        raise HTTPException(status_code=500, detail="Upstream error")

    if status != "OK":
        logger.error("google places unexpected status: %s payload=%s", status, data)
        raise HTTPException(status_code=500, detail="Upstream error")

    results = (data.get("results") or [])[:10]

    items = []
    for r in results:
        loc = (r.get("geometry") or {}).get("location") or {}
        shop_lat = loc.get("lat")
        shop_lng = loc.get("lng")

        # 位置が取れないデータはスキップ
        if shop_lat is None or shop_lng is None:
            continue

        km = flat_distance_km(lat, lng, shop_lat, shop_lng)

        items.append({
            "place_id": r.get("place_id"),
            "name": r.get("name"),
            "vicinity": r.get("vicinity"),
            "lat": shop_lat,
            "lng": shop_lng,
            "distance_km": km,
        })

    return {"items": items, "count": len(items)}
