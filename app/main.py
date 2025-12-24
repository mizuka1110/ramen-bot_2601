from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse
import logging

from app.services.places import search_nearby, PlacesUpstreamError

app = FastAPI()

logger = logging.getLogger("uvicorn.error")

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
        items.append({
            "place_id": r.get("place_id"),
            "name": r.get("name"),
            "vicinity": r.get("vicinity"),
            "lat": loc.get("lat"),
            "lng": loc.get("lng"),
        })

    return {"items": items, "count": len(items)}

