from datetime import datetime, timezone

from psycopg.types.json import Jsonb

from app.db.db import get_conn


def get_user_weights(line_user_id: str) -> dict[str, float]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT weights
                FROM user_preferences
                WHERE line_user_id = %s
                """,
                (line_user_id,),
            )
            row = cur.fetchone()

    if not row:
        return {}

    weights = row[0]
    if isinstance(weights, dict):
        return {str(k): float(v) for k, v in weights.items()}

    return {}


def upsert_user_weights(line_user_id: str, weights: dict[str, float]) -> None:
    now = datetime.now(timezone.utc)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_preferences (line_user_id, weights, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (line_user_id)
                DO UPDATE SET
                    weights = EXCLUDED.weights,
                    updated_at = EXCLUDED.updated_at
                """,
                (line_user_id, Jsonb(weights), now),
            )
        conn.commit()