from app.db.user_pref_repo import get_user_weights, upsert_user_weights

PREFERENCE_CATEGORIES = {
    "あっさり": "あっさり",
    "こってり": "こってり",
    "魚介": "魚介系",
    "煮干し": "煮干し",
    "鶏白湯": "鶏白湯",
    "豚骨": "豚骨",
    "醤油": "醤油",
    "味噌": "味噌",
    "塩": "塩",
    "辛い": "辛い",
    "家系": "家系",
    "二郎系": "二郎系",
}

PREFERENCE_VALUE_MAP = {
    "like": 0.25,
    "love": 0.5,
    "dislike": -0.25,
}

PREFERENCE_LABEL_MAP = {
    "like": "好き",
    "love": "めちゃ好き",
    "dislike": "苦手",
}


def get_preference_weights(line_user_id: str) -> dict[str, float]:
    return get_user_weights(line_user_id)


def set_preference(
    line_user_id: str,
    category: str,
    choice: str,
) -> dict[str, float]:
    if category not in PREFERENCE_CATEGORIES:
        raise ValueError(f"unknown category: {category}")

    if choice not in PREFERENCE_VALUE_MAP:
        raise ValueError(f"unknown choice: {choice}")

    weights = get_user_weights(line_user_id)
    weights[category] = PREFERENCE_VALUE_MAP[choice]
    upsert_user_weights(line_user_id, weights)
    return weights


def get_preference_choice_label(choice: str) -> str:
    return PREFERENCE_LABEL_MAP.get(choice, "")
