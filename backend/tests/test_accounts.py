import os
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_analyzer import sample

from poker_lab import account_auth as auth
from poker_lab.account_db import pool
from poker_lab.api import create_app

BASE = "/api/account/"
ORIGIN = {"origin": "http://localhost:3000"}


@pytest.fixture
def signer(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-audience")
    monkeypatch.setattr(
        auth,
        "keys",
        lambda: SimpleNamespace(
            get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())
        ),
    )

    def sign(nonce, **extra):
        now = int(time.time())
        claims = {
            "iss": auth.ISSUER,
            "sub": str(uuid4()),
            "aud": "test-audience",
            "iat": now,
            "exp": now + 300,
            "nonce": nonce,
            "name": "Player",
        }
        return jwt.encode(
            claims | extra, key, algorithm="RS256", headers={"kid": "test-signing-key"}
        )

    return sign


@pytest.mark.parametrize(
    "bad", [{"iss": "other"}, {"aud": "other"}, {"exp": 0}, {"nonce": "mismatch"}, {"azp": "wrong"}]
)
def test_identity_claims(signer, bad):
    from fastapi import HTTPException

    token = signer("expected", **bad) if "nonce" not in bad else signer("mismatch")
    with pytest.raises(HTTPException) as err:
        auth.claims(token, "expected")
    assert err.value.status_code == 401


@pytest.fixture
def app(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database")
    monkeypatch.setenv("DATABASE_URL", url)
    pool.cache_clear()
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    yield create_app()
    pool().dispose()
    pool.cache_clear()


def test_private_records_across_sessions(app, signer):
    a, b = TestClient(app, headers=ORIGIN), TestClient(app, headers=ORIGIN)
    assert a.get("/ready").status_code == 200
    assert (
        a.post(
            BASE + "challenge",
            content='{"a":1,"a":2}',
            headers={"content-type": "application/json"},
        ).status_code
        == 422
    )
    assert (
        a.post(
            BASE + "training", content=b"x" * 65537, headers={"content-type": "application/json"}
        ).status_code
        == 413
    )
    assert a.get(BASE + "hands").status_code == 401
    assert (
        a.post(
            BASE + "challenge", json={}, headers={"origin": "https://unrelated.invalid"}
        ).status_code
        == 403
    )
    for c in (a, b):
        nonce = c.post(BASE + "challenge", json={}).json()["nonce"]
        credential = {"credential": signer(nonce)}
        login = c.post(BASE + "login", json=credential)
        assert login.status_code == 200 and "HttpOnly" in login.headers["set-cookie"]
        assert c.post(BASE + "login", json=credential).status_code == 401
    h = {"title": "Reviewed river", "hand": sample()}
    partial = sample()
    partial.update(actions=[], board=[])
    assert a.post(BASE + "hands", json=h | {"hand": partial}).status_code == 422
    key = a.post(BASE + "hands", json=h).json()["id"]
    path = BASE + "hands/" + key
    assert a.get(path).json()["hand"]["hero"] == "BTN"
    restarted = TestClient(
        create_app(), headers=ORIGIN, cookies={auth.COOKIE: a.cookies.get(auth.COOKIE)}
    )
    assert restarted.get(path).json()["title"] == h["title"]
    assert b.get(path).status_code == 404
    assert b.post(path + "/update", json=h).status_code == 404
    assert b.post(path + "/delete", json={}).status_code == 404
    assert a.post(path + "/update", json=h | {"title": "New title"}).is_success
    assert a.post(BASE + "hands", json=h | {"owner": str(uuid4())}).status_code == 422
    assert (
        a.post(BASE + "hands", json=h | {"hand": sample() | {"payouts": {"BB": 1}}}).status_code
        == 422
    )
    assert b.get(BASE + "hands").json() == []
    assert a.get(BASE + "hands").json()[0]["title"] == "New title"
    raw = {"version": "1.0", "entries": [], "overrides": {}}
    public = sample()
    for seat in public["seats"].values():
        seat["cards"] = None
    evidence = {
        "source": "manual",
        "hand_id": "review-1",
        "mapping": {"BB": "player-a"},
        "hand": public,
    }
    raw.update(entries=[evidence], overrides={"player-a": "tag"})
    payload = {"revision": 0, "archive": raw}
    assert a.post(BASE + "observations", json=payload).json() == {"revision": 1}
    assert a.post(BASE + "observations", json=payload).status_code == 409
    assert a.post(BASE + "observations", json=payload | {"revision": 1}).json() == {"revision": 2}
    loaded = restarted.get(BASE + "observations").json()["archive"]
    assert (
        loaded["entries"][0]["mapping"] == {"BB": "player-a"}
        and loaded["overrides"] == raw["overrides"]
    )
    assert (
        a.post(
            BASE + "observations",
            json={"revision": 2, "archive": raw | {"entries": [evidence, evidence]}},
        ).status_code
        == 422
    )
    assert b.get(BASE + "observations").json()["revision"] == 0
    p = a.get("/api/strategy/training/exercises").json()[0]
    req = {k: p[k] for k in ("solution_id", "scenario_id", "version", "combo")}
    req["action"] = p["actions"][0]
    feedback = a.post("/api/strategy/training/grade", json=req).json()
    session = str(uuid4())
    attempt = {
        "session": session,
        "id": str(uuid4()),
        "time": "2026-01-02T00:00:00Z",
        "submission": req,
        "feedback": feedback,
        "origin": "practice",
        "retry": False,
        "street": p["street"],
        "position": p["position"],
    }
    archive = {"version": "1", "attempts": [attempt]}
    assert a.post(BASE + "training", json=archive).json()["added"] == 1
    assert a.post(BASE + "training", json=archive).json()["duplicates"] == 1
    assert (
        a.post(
            BASE + "training", json=archive | {"attempts": [attempt | {"retry": True}]}
        ).status_code
        == 409
    )
    assert (
        a.post(
            BASE + "training",
            json=archive
            | {
                "attempts": [
                    attempt | {"id": str(uuid4()), "feedback": feedback | {"loss": 100000}}
                ]
            },
        ).status_code
        == 422
    )
    assert a.get(BASE + "sessions").json() == [session]
    assert (
        a.get(BASE + "sessions/" + session).json()["attempts"][0]["submission"]["version"]
        == p["version"]
    )
    assert b.get(BASE + "sessions/" + session).status_code == 404
    for route in ("sessions/" + session, "attempts/" + attempt["id"]):
        assert b.post(BASE + route + "/delete", json={}).status_code == 404
    assert a.post(BASE + "attempts/" + attempt["id"] + "/delete", json={}).is_success
    assert a.post(BASE + "sessions/" + session + "/delete", json={}).is_success
    assert a.post(BASE + "training/clear", json={"confirm": True}).is_success
    assert a.post(path + "/delete", json={}).is_success
    assert a.post(BASE + "delete", json={"confirm": True}).is_success
    assert a.get(BASE + "me").status_code == 401
    token = b.cookies.get(auth.COOKIE)
    assert b.get(BASE + "me").json() == {"name": "Player"}
    restored = TestClient(create_app(), headers=ORIGIN, cookies={auth.COOKIE: token})
    assert restored.get(BASE + "me").is_success
    assert b.post(BASE + "logout", json={}).is_success
    assert restored.get(BASE + "me").status_code == 401
    nonce = b.post(BASE + "challenge", json={}).json()["nonce"]
    b.post(BASE + "login", json={"credential": signer(nonce)})
    with pool().begin() as db:
        db.execute(
            text("UPDATE logins SET expires=now() WHERE digest=:key"),
            {"key": auth.digest(b.cookies.get(auth.COOKIE))},
        )
    assert b.get(BASE + "me").status_code == 401


def test_browser_bound_challenge_and_rotation(app, signer):
    a = TestClient(app, headers=ORIGIN)
    b = TestClient(app, headers=ORIGIN)
    nonce = a.post(BASE + "challenge", json={}).json()["nonce"]
    assert b.post(BASE + "login", json={"credential": signer(nonce)}).status_code == 401
    with pool().begin() as db:
        db.execute(
            text("UPDATE challenges SET expires=now() WHERE digest=:digest"),
            {"digest": auth.digest(a.cookies.get(auth.CHALLENGE))},
        )
    assert a.post(BASE + "login", json={"credential": signer(nonce)}).status_code == 401
    for _ in range(2):
        nonce = a.post(BASE + "challenge", json={}).json()["nonce"]
        assert a.post(
            BASE + "login", json={"credential": signer(nonce, sub="rotation-test")}
        ).is_success
        current = a.cookies.get(auth.COOKIE)
        if _ == 0:
            b.cookies.set(auth.COOKIE, current)
    assert current != b.cookies.get(auth.COOKIE)
    assert b.get(BASE + "me").status_code == 401
    assert a.post(BASE + "delete", json={"confirm": True}).is_success
    assert a.get(BASE + "me").status_code == 401


def test_private_validation_and_wrong_signature(app, signer, monkeypatch):
    a = TestClient(app, headers=ORIGIN)
    marker = "fixture-private-value"
    res = a.post(BASE + "login", json={"credential": [marker]})
    assert res.status_code == 422 and marker not in res.text
    assert "no-store" in res.headers["cache-control"]
    nonce = a.post(BASE + "challenge", json={}).json()["nonce"]
    token = signer(nonce)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(
        auth,
        "keys",
        lambda: SimpleNamespace(
            get_signing_key_from_jwt=lambda _: SimpleNamespace(key=other.public_key())
        ),
    )
    assert a.post(BASE + "login", json={"credential": token}).status_code == 401
    assert a.post(BASE + "login", json={"credential": token}).json()["detail"] == "Sign-in expired"


def test_header_and_provider_failure(signer, monkeypatch):
    from fastapi import HTTPException

    token = signer("nonce")
    with pytest.raises(HTTPException) as failure:
        auth.claims(jwt.encode({"sub": "fixture"}, "a" * 32, algorithm="HS256"), "nonce")
    assert failure.value.status_code == 401

    def offline():
        raise jwt.PyJWKClientConnectionError("fixture outage")

    monkeypatch.setattr(auth, "keys", offline)
    with pytest.raises(HTTPException) as failure:
        auth.claims(token, "nonce")
    assert failure.value.status_code == 503


def test_public_body_limit_and_host_policy(monkeypatch):
    monkeypatch.setenv("ALLOWED_HOSTS", "testserver")
    c = TestClient(create_app())
    assert (
        c.get(
            "/health", headers={"host": "other.invalid", "x-forwarded-host": "testserver"}
        ).status_code
        == 400
    )
    assert (
        c.post(
            "/api/analyzer/replay",
            content=b" " * 1048577,
            headers={"content-type": "application/json"},
        ).status_code
        == 413
    )
    assert (
        c.post(BASE + "challenge", json={}, headers={"x-forwarded-host": "localhost"}).status_code
        == 403
    )
    assert c.post(BASE + "challenge", content="{}", headers=ORIGIN).status_code == 415


def test_unconfigured_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    pool.cache_clear()
    c = TestClient(create_app())
    assert c.get("/health").is_success
    assert c.get("/ready").status_code == 503
    assert c.get("/api/strategy/scenarios").is_success
