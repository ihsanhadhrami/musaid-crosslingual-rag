"""Integration checks against the docker compose stack. Run: pytest -m integration"""

import urllib.request

import pytest

from musaid.config import get_settings
from musaid.db import connect, pgvector_version

pytestmark = pytest.mark.integration


def test_postgres_has_pgvector():
    with connect() as conn:
        assert pgvector_version(conn) is not None


def test_vector_roundtrip():
    with connect() as conn:
        row = conn.execute("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector").fetchone()
        assert row[0] == pytest.approx(1.0)


@pytest.mark.skipif(
    not get_settings().langfuse_public_key, reason="Langfuse not configured (no .env)"
)
def test_langfuse_healthy():
    url = f"{get_settings().langfuse_host}/api/public/health"
    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
