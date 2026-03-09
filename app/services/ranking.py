def _review_penalty(count: int) -> float:
    if count >= 100:
        return 0
    if count >= 75:
        return -0.1
    if count >= 50:
        return -0.2
    if count >= 25:
        return -0.3
    return -0.5


def _preference_score(item: dict, weights: dict[str, float]) -> float:
    categories = item.get("categories") or []
    return sum(weights.get(c, 0) for c in categories)


def _total_score(item: dict, weights: dict[str, float]) -> float:
    rating = item.get("rating") or 0
    rating_count = item.get("rating_count") or 0
    return rating + _preference_score(item, weights) + _review_penalty(rating_count)


def sort_items(items: list[dict], weights: dict[str, float]) -> list[dict]:
    return sorted(
        items,
        key=lambda x: (
            not (x.get("open_now") is True),
            -_total_score(x, weights),
        )
    )