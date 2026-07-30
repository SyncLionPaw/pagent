from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg

from . import settings

SCHEMA_PATH = Path(__file__).resolve().parent / "db" / "schema.sql"
SEED_PATH = Path(__file__).resolve().parent / "db" / "seed.sql"


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    with psycopg.connect(settings.DATABASE_URL) as conn:
        yield conn


def ping() -> dict:
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                cur.fetchone()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def apply_sql_file(conn: psycopg.Connection, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def bootstrap() -> dict:
    """Apply schema + seed when tables are missing. Safe to call repeatedly."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select exists (
                    select 1
                    from information_schema.tables
                    where table_schema = 'public' and table_name = 'users'
                )
                """
            )
            has_users = bool(cur.fetchone()[0])
        if not has_users:
            apply_sql_file(conn, SCHEMA_PATH)
            apply_sql_file(conn, SEED_PATH)
            return {"ok": True, "bootstrapped": True}
        return {"ok": True, "bootstrapped": False}
