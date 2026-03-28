import time
from typing import Any

# 2〜5分くらいが無難（課題なら短めでOK）
CACHE_TTL_SEC = 180
MAX_CACHE_ENTRIES = 200

_places_cache: dict[str, dict[str, Any]] = {}


def _cache_key(lat: float, lng: float, q: str, radius: int) -> str:
    # 0.001度 ≒ 約100m（緯度）。近接地点のキャッシュヒットを増やす用
    return f"{round(lat,3)}:{round(lng,3)}:{q}:{radius}"


def _prune_expired(now: float) -> None:
    expired_keys = [
        key
        for key, value in _places_cache.items()
        if now - value["ts"] > CACHE_TTL_SEC
    ]
    for key in expired_keys:
        _places_cache.pop(key, None)


def _prune_if_oversized() -> None:
    over = len(_places_cache) - MAX_CACHE_ENTRIES
    if over <= 0:
        return

    # もっとも古いものから削除
    oldest = sorted(
        _places_cache.items(),
        key=lambda kv: kv[1]["ts"],
    )[:over]
    for key, _ in oldest:
        _places_cache.pop(key, None)


def get_cached(lat: float, lng: float, q: str, radius: int) -> dict | None:
    now = time.time()
    _prune_expired(now)

    key = _cache_key(lat, lng, q, radius)
    hit = _places_cache.get(key)
    if not hit:
        return None

    if now - hit["ts"] > CACHE_TTL_SEC:
        _places_cache.pop(key, None)
        return None

    return hit["data"]


def set_cached(lat: float, lng: float, q: str, radius: int, data: dict) -> None:
    now = time.time()
    _prune_expired(now)

    key = _cache_key(lat, lng, q, radius)
    _places_cache[key] = {"ts": now, "data": data}
    _prune_if_oversized()
