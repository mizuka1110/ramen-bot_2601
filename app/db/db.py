import os

import psycopg

DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "ramen_bot")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "pass")


def get_db_connection_source() -> str:
    if SUPABASE_DB_URL:
        return "SUPABASE_DB_URL"
    if DATABASE_URL:
        return "DATABASE_URL"
    return f"DB_HOST({DB_HOST}:{DB_PORT}/{DB_NAME})"


def get_conn() -> psycopg.Connection:
    if SUPABASE_DB_URL:
        return psycopg.connect(SUPABASE_DB_URL)

    if DATABASE_URL:
        return psycopg.connect(DATABASE_URL)

    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
