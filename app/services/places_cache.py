import time
from typing import Any

# 2〜5分くらいが無難（課題なら短めでOK）
CACHE_TTL_SEC = 180

_places_cache: dict[str, dict[str, Any]] = {}


def _cache_key(lat: float, lng: float, q: str, radius: int) -> str:
    # 0.001度 ≒ 約100m（緯度）。近接地点のキャッシュヒットを増やす用
    return f"{round(lat,3)}:{round(lng,3)}:{q}:{radius}"


def get_cached(lat: float, lng: float, q: str, radius: int) -> dict | None:
    key = _cache_key(lat, lng, q, radius)
    hit = _places_cache.get(key)
    if not hit:
        return None

    if time.time() - hit["ts"] > CACHE_TTL_SEC:
        _places_cache.pop(key, None)
        return None

    return hit["data"]


def set_cached(lat: float, lng: float, q: str, radius: int, data: dict) -> None:
    key = _cache_key(lat, lng, q, radius)
    _places_cache[key] = {"ts": time.time(), "data": data}
