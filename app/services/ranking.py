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


def _addict_multiplier(raw_count: int) -> float:
    if raw_count <= 1:
        return 1.05
    if raw_count <= 3:
        return 1.15
    return 1.3


def _preference_score(item: dict, weights: dict[str, float]) -> tuple[float, float]:
    mentions = item.get("category_mentions")
    if not isinstance(mentions, dict):
        categories = item.get("categories") or []
        base_score = sum(weights.get(c, 0) for c in categories)
        addict_bonus = (
            1.05 if any((weights.get(c) or 0) >= 1.0 for c in categories) else 0.0
        )
        return base_score, addict_bonus

    base_score = 0.0
    addict_bonus = 0.0

    for category, raw_count in mentions.items():
        if not isinstance(category, str):
            continue
        if not isinstance(raw_count, int) or raw_count <= 0:
            continue

        weight = weights.get(category, 0.0) or 0.0
        if weight >= 1.0:
            addict_bonus += _addict_multiplier(raw_count)
            continue

        base_score += float(weight) * raw_count

    return base_score, addict_bonus


def _total_score(item: dict, weights: dict[str, float]) -> float:
    rating = item.get("rating") or 0
    rating_count = item.get("rating_count") or 0
    preference_score, addict_bonus = _preference_score(item, weights)
    return rating + preference_score + addict_bonus + _review_penalty(rating_count)


def _is_effectively_open(item: dict) -> bool:
    open_at_search_time = item.get("open_at_search_time")
    if isinstance(open_at_search_time, bool):
        return open_at_search_time
    return item.get("open_now") is True


def _open_now_priority(item: dict) -> int:
    open_now = item.get("open_now")
    if open_now is True:
        return 0
    if open_now is None:
        return 1
    return 2


def sort_items(
    items: list[dict],
    weights: dict[str, float],
    prioritize_open_now_status: bool = False,
) -> list[dict]:
    if prioritize_open_now_status:
        return sorted(
            items,
            key=lambda x: (
                _open_now_priority(x),
                -_total_score(x, weights),
            ),
        )

    return sorted(
        items,
        key=lambda x: (
            not _is_effectively_open(x),
            -_total_score(x, weights),
        )
    )