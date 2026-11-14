from fastapi.testclient import TestClient

from poker_lab.account_db import pool
from poker_lab.api import create_app


def test_guest_demo_has_no_private_routes_or_database_dependency(monkeypatch):
    for key, value in {
        "MIRACLE_ENV": "guest-demo",
        "TRAINER_ORIGIN": "https://demo.example.org",
        "COOKIE_SECURE": "true",
        "ALLOWED_HOSTS": "localhost",
    }.items():
        monkeypatch.setenv(key, value)
    for key in ("DATABASE_URL", "GOOGLE_CLIENT_ID"):
        monkeypatch.delenv(key, raising=False)
    pool.cache_clear()
    with TestClient(create_app(), base_url="https://localhost") as client:
        assert client.get("/ready").is_success
        paths = client.get("/openapi.json").json()["paths"]
        assert not any(p.startswith("/api/account/") for p in paths)
        assert (
            client.post(
                "/api/account/challenge", json={}, headers={"Origin": "https://demo.example.org"}
            ).status_code
            == 404
        )
        res = client.post("/api/games", json={}, headers={"Origin": "https://demo.example.org"})
        assert res.is_success and "Secure" in res.headers["set-cookie"]
        assert client.get("/api/game").is_success
        assert not pool.cache_info().currsize
