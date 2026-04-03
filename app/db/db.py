import os
from urllib.parse import urlsplit, urlunsplit

import psycopg

DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_PORT = 5432
DEFAULT_DB_NAME = "ramen_bot"
DEFAULT_DB_USER = "postgres"
DEFAULT_DB_PASSWORD = "pass"
DEFAULT_DB_CONNECT_TIMEOUT_SEC = 5
DEFAULT_DB_STATEMENT_TIMEOUT_MS = 8000


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _db_settings() -> dict[str, str | int]:
    return {
        "database_url": os.getenv("DATABASE_URL", ""),
        "supabase_db_url": os.getenv("SUPABASE_DB_URL", ""),
        "db_host": os.getenv("DB_HOST", DEFAULT_DB_HOST),
        "db_port": _get_int_env("DB_PORT", DEFAULT_DB_PORT),
        "db_name": os.getenv("DB_NAME", DEFAULT_DB_NAME),
        "db_user": os.getenv("DB_USER", DEFAULT_DB_USER),
        "db_password": os.getenv("DB_PASSWORD", DEFAULT_DB_PASSWORD),
        "db_connect_timeout_sec": _get_int_env(
            "DB_CONNECT_TIMEOUT_SEC",
            DEFAULT_DB_CONNECT_TIMEOUT_SEC,
        ),
        "db_statement_timeout_ms": _get_int_env(
            "DB_STATEMENT_TIMEOUT_MS",
            DEFAULT_DB_STATEMENT_TIMEOUT_MS,
        ),
    }


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
    settings = _db_settings()
    supabase_db_url = str(settings["supabase_db_url"])
    database_url = str(settings["database_url"])
    db_host = str(settings["db_host"])
    db_port = int(settings["db_port"])
    db_name = str(settings["db_name"])

    if supabase_db_url:
        return "SUPABASE_DB_URL"
    if database_url:
        return "DATABASE_URL"

    resolved_port = _resolve_supabase_pooler_port(db_host, db_port)
    return f"DB_HOST({db_host}:{resolved_port}/{db_name})"


def get_conn() -> psycopg.Connection:
    settings = _db_settings()
    supabase_db_url = str(settings["supabase_db_url"])
    database_url = str(settings["database_url"])
    db_host = str(settings["db_host"])
    db_port = int(settings["db_port"])
    db_name = str(settings["db_name"])
    db_user = str(settings["db_user"])
    db_password = str(settings["db_password"])
    db_connect_timeout_sec = int(settings["db_connect_timeout_sec"])
    db_statement_timeout_ms = int(settings["db_statement_timeout_ms"])

    common_kwargs = {
        "connect_timeout": db_connect_timeout_sec,
        "options": f"-c statement_timeout={db_statement_timeout_ms}",
    }

    if supabase_db_url:
        return psycopg.connect(_normalize_db_url_port(supabase_db_url), **common_kwargs)

    if database_url:
        return psycopg.connect(_normalize_db_url_port(database_url), **common_kwargs)

    return psycopg.connect(
        host=db_host,
        port=_resolve_supabase_pooler_port(db_host, db_port),
        dbname=db_name,
        user=db_user,
        password=db_password,
        **common_kwargs,
    )