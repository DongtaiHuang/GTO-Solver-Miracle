import pytest

from poker_lab.infrastructure import validate_environment


@pytest.mark.parametrize(
    ("key", "bad"),
    [
        ("MIRACLE_ENV", "prod"),
        ("TRAINER_ORIGIN", "http://example.org"),
        ("TRAINER_ORIGIN", "https://example.org/path"),
        ("ALLOWED_HOSTS", "*"),
        ("COOKIE_SECURE", "false"),
        ("DATABASE_URL", ""),
    ],
)
def test_production_configuration(monkeypatch, key, bad):
    settings = {
        "MIRACLE_ENV": "production",
        "TRAINER_ORIGIN": "https://example.org",
        "ALLOWED_HOSTS": "backend,localhost",
        "COOKIE_SECURE": "true",
        "DATABASE_URL": "postgresql+psycopg://test:fixture@db/test",
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    validate_environment()
    monkeypatch.setenv(key, bad)
    with pytest.raises(ValueError, match=key):
        validate_environment()
