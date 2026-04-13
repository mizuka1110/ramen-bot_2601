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


def _normalized_preference_weight(category: str, weights: dict[str, float]) -> float:
    weight = weights.get(category, 0.0) or 0.0
    if weight:
        return float(weight)

    if category == "二郎":
        return float(weights.get("二郎系", 0.0) or 0.0)
    if category == "二郎系":
        return float(weights.get("二郎", 0.0) or 0.0)

    return 0.0


CATEGORY_NAME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "つけ麺": ("つけ麺", "つけめん", "つけそば"),
    "まぜそば": ("まぜそば", "まぜ麺", "油そば"),
    "魚介": ("魚介",),
    "煮干し": ("煮干し", "にぼし"),
    "鶏白湯": ("鶏白湯",),
    "豚骨": ("豚骨",),
    "醤油": ("醤油", "しょうゆ"),
    "味噌": ("味噌", "みそ"),
    # 「しお」は短すぎて誤検知しやすいため、単独では一致させない。
    "塩": ("塩", "塩そば", "塩ラーメン", "しおそば", "しおラーメン", "しおらーめん"),
    "辛い": ("辛", "激辛"),
    "家系": ("家系",),
    "二郎系": ("二郎", "二郎系"),
}


def _canonical_preference_category(category: str) -> str:
    if category == "二郎":
        return "二郎系"
    return category


def _name_match_bonus(
    item: dict,
    weights: dict[str, float],
    signaled_categories: set[str],
) -> float:
    name = item.get("name")
    if not isinstance(name, str) or not signaled_categories:
        return 0.0

    bonus = 0.0
    for category in signaled_categories:
        canonical = _canonical_preference_category(category)
        keywords = CATEGORY_NAME_KEYWORDS.get(canonical)
        if not keywords:
            continue

        weight = _normalized_preference_weight(canonical, weights)
        if weight <= 0:
            continue

        if any(keyword in name for keyword in keywords):
            bonus += 0.2 if weight >= 1.0 else 0.08

    return min(bonus, 0.3)


def _preference_score(item: dict, weights: dict[str, float]) -> tuple[float, float]:
    mentions = item.get("category_mentions")
    if not isinstance(mentions, dict):
        categories = item.get("categories") or []
        signaled_categories = {c for c in categories if isinstance(c, str)}
        base_score = sum(_normalized_preference_weight(c, weights) for c in categories)
        addict_bonus = (
            1.05
            if any(_normalized_preference_weight(c, weights) >= 1.0 for c in categories)
            else 0.0
        )
        return base_score, addict_bonus + _name_match_bonus(item, weights, signaled_categories)

    base_score = 0.0
    addict_bonus = 0.0
    signaled_categories: set[str] = set()

    for category, raw_count in mentions.items():
        if not isinstance(category, str):
            continue
        if not isinstance(raw_count, int) or raw_count <= 0:
            continue
        signaled_categories.add(category)

        weight = _normalized_preference_weight(category, weights)
        if weight >= 1.0:
            addict_bonus += _addict_multiplier(raw_count)
            continue

        base_score += float(weight) * raw_count

    return base_score, addict_bonus + _name_match_bonus(item, weights, signaled_categories)


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
