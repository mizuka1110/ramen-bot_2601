from app.db.db import get_conn
from psycopg.types.json import Json

PREFERENCE_KEY_ALIASES = {
    "醤油": "しょうゆ",
    "塩": "しお",
}


def normalize_weights_keys(weights: dict) -> dict:
    if not isinstance(weights, dict):
        return {}

    normalized: dict = {}

    # まず正規キーを優先して反映
    for key, value in weights.items():
        canonical_key = PREFERENCE_KEY_ALIASES.get(key, key)
        if key == canonical_key:
            normalized[canonical_key] = value

    # 次にエイリアスキーを補完（正規キーが無い場合のみ）
    for key, value in weights.items():
        canonical_key = PREFERENCE_KEY_ALIASES.get(key, key)
        if canonical_key not in normalized:
            normalized[canonical_key] = value

    return normalized


def get_user_weights(line_user_id: str) -> dict:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT weights
        FROM user_preferences
        WHERE line_user_id = %s
        """,
        (line_user_id,),
    )
    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        return {}

    return normalize_weights_keys(row[0] or {})


def upsert_user_weights(line_user_id: str, weights: dict) -> None:
    normalized_weights = normalize_weights_keys(weights)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO user_preferences (line_user_id, weights)
        VALUES (%s, %s)
        ON CONFLICT (line_user_id)
        DO UPDATE SET
            weights = EXCLUDED.weights,
            updated_at = NOW()
        """,
        (line_user_id, Json(normalized_weights)),
    )

    conn.commit()
    cur.close()
    conn.close()
