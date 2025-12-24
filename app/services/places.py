import httpx
from app.config import GOOGLE_PLACES_API_KEY, GOOGLE_NEARBY_URL

class PlacesUpstreamError(Exception):
    def __init__(self, status: str, message: str | None = None):
        self.status = status
        self.message = message
        super().__init__(f"{status}: {message}")

async def search_nearby(lat: float, lng: float, q: str, radius: int) -> dict:
    if not GOOGLE_PLACES_API_KEY:
        raise PlacesUpstreamError("CONFIG_ERROR", "GOOGLE_PLACES_API_KEY is missing")

    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "keyword": q,
        "key": GOOGLE_PLACES_API_KEY,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(GOOGLE_NEARBY_URL, params=params)
        r.raise_for_status()
        return r.json()
