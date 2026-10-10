"""Postgres connection helpers."""

import psycopg

from musaid.config import Settings, get_settings


def connect(settings: Settings | None = None) -> psycopg.Connection:
    settings = settings or get_settings()
    return psycopg.connect(settings.database_url, connect_timeout=5)


def pgvector_version(conn: psycopg.Connection) -> str | None:
    """Return the installed pgvector extension version, or None if missing."""
    row = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
    return row[0] if row else None
