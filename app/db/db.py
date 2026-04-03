import os
from urllib.parse import urlsplit, urlunsplit

import psycopg

DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "ramen_bot")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "pass")
DB_CONNECT_TIMEOUT_SEC = int(os.getenv("DB_CONNECT_TIMEOUT_SEC", "5"))
DB_STATEMENT_TIMEOUT_MS = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "8000"))


def _resolve_supabase_pooler_port(host: str | None, port: int | None) -> int | None:
    if host and host.endswith(".pooler.supabase.com") and (port is None or port == 5432):
        return 6543
    return port


def _normalize_db_url_port(db_url: str) -> str:
    parsed = urlsplit(db_url)
    normalized_port = _resolve_supabase_pooler_port(parsed.hostname, parsed.port)
    if normalized_port == parsed.port:
        return db_url

    userinfo = ""
    if parsed.username:
        userinfo = parsed.username
        if parsed.password:
            userinfo += f":{parsed.password}"
        userinfo += "@"

    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    netloc = f"{userinfo}{host}:{normalized_port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def get_db_connection_source() -> str:
    if SUPABASE_DB_URL:
        return "SUPABASE_DB_URL"
    if DATABASE_URL:
        return "DATABASE_URL"

    resolved_port = _resolve_supabase_pooler_port(DB_HOST, DB_PORT)
    return f"DB_HOST({DB_HOST}:{resolved_port}/{DB_NAME})"


def get_conn() -> psycopg.Connection:
    common_kwargs = {
        "connect_timeout": DB_CONNECT_TIMEOUT_SEC,
        "options": f"-c statement_timeout={DB_STATEMENT_TIMEOUT_MS}",
    }

    if SUPABASE_DB_URL:
        return psycopg.connect(_normalize_db_url_port(SUPABASE_DB_URL), **common_kwargs)

    if DATABASE_URL:
        return psycopg.connect(_normalize_db_url_port(DATABASE_URL), **common_kwargs)

    return psycopg.connect(
        host=DB_HOST,
        port=_resolve_supabase_pooler_port(DB_HOST, DB_PORT),
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        **common_kwargs,
    )
