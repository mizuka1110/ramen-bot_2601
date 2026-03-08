from app.db.db import get_conn
from psycopg.types.json import Json


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

    return row[0] or {}


def upsert_user_weights(line_user_id: str, weights: dict) -> None:
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
        (line_user_id, Json(weights)),
    )

    conn.commit()
    cur.close()
    conn.close()