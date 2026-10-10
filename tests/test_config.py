from pydantic import SecretStr

import musaid
from musaid.config import Settings


def test_version():
    assert musaid.__version__


def test_database_url_from_fields():
    s = Settings(
        _env_file=None,
        postgres_host="db",
        postgres_port=6543,
        postgres_db="kb",
        postgres_user="u",
        postgres_password=SecretStr("p"),
    )
    assert s.database_url == "postgresql://u:p@db:6543/kb"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "example")
    assert Settings(_env_file=None).postgres_host == "example"


def test_secrets_not_in_repr():
    s = Settings(_env_file=None, postgres_password=SecretStr("hunter2"))
    assert "hunter2" not in repr(s)
