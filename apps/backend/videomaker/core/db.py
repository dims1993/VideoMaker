"""Postgres (Neon) connection + migrations."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row

from videomaker import config


def database_url() -> str:
    url = os.environ.get("NEON_DATABASE_URL", "").strip() or os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("Falta NEON_DATABASE_URL (o DATABASE_URL) en tu .env.")
    return url


def connect():
    # Neon: preferimos sslmode=require si no viene en la URL
    url = database_url()
    if "sslmode=" not in url:
        sep = "&" if "?" in url else "?"
        url = url + f"{sep}sslmode=require"
    return psycopg.connect(url, row_factory=dict_row)


def execute(sql: str, params: dict[str, Any] | None = None) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})


def fetch_all(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            rows = cur.fetchall()
            return list(rows) if rows else []


def fetch_one(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            row = cur.fetchone()
            return dict(row) if row else None


def run_migrations() -> None:
    mig_dir = config.BACKEND_ROOT / "migrations"
    if not mig_dir.is_dir():
        return
    files = sorted(mig_dir.glob("*.sql"))
    if not files:
        return
    with connect() as conn:
        with conn.cursor() as cur:
            # tabla de control simple
            cur.execute(
                """
                create table if not exists schema_migrations (
                  filename text primary key,
                  applied_at timestamptz not null default now()
                );
                """
            )
            cur.execute("select filename from schema_migrations")
            applied = {r["filename"] for r in (cur.fetchall() or [])}
            for f in files:
                if f.name in applied:
                    continue
                sql = f.read_text(encoding="utf-8")
                cur.execute(sql)
                cur.execute("insert into schema_migrations(filename) values (%s)", (f.name,))
        conn.commit()

    # Lightweight schema evolution for dev: apply additive alters if needed.
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    alter table videos
                      add column if not exists thumbnail_url text;
                    """
                )
            conn.commit()
    except Exception:
        pass

