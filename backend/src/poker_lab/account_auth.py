"""Google Identity Services ID-token sign-in, with one-time browser-bound nonces."""

import hashlib
import os
import secrets
from functools import lru_cache
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field
from sqlalchemy import Connection, text

from poker_lab.account_db import database
from poker_lab.strategy_models import StrictModel

ISSUER = "https://accounts.google.com"
COOKIE = "miracle_login"
CHALLENGE = "miracle_challenge"


def origin() -> str:
    return os.environ.get("TRAINER_ORIGIN", "http://localhost:3000")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def cookie(response: Response, name: str, value: str, age: int) -> None:
    response.set_cookie(
        name,
        value,
        path="/api/account",
        httponly=True,
        max_age=age,
        secure=origin().startswith("https://"),
        samesite="strict",
    )


def client_id() -> str:
    value = os.environ.get("GOOGLE_CLIENT_ID")
    if not value or not (origin().startswith("https://") or origin() == "http://localhost:3000"):
        raise HTTPException(503, "Sign-in is not configured")
    return value


@lru_cache(maxsize=1)
def keys() -> jwt.PyJWKClient:
    return jwt.PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", timeout=4)


def claims(token: str, nonce: str) -> tuple[str, str, str | None]:
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(kid, str) or not 1 <= len(kid) <= 128:
            raise ValueError
        key = keys().get_signing_key_from_jwt(token).key
        c = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=client_id(),
            issuer=ISSUER,
            options={"require": ["iss", "sub", "iat", "exp", "aud", "nonce"], "strict_aud": True},
        )
        if c["nonce"] != nonce or not c["sub"] or c.get("azp", client_id()) != client_id():
            raise ValueError
        return (
            c["sub"],
            str(c.get("name") or "Player")[:120],
            (c.get("email") if c.get("email_verified") is True else None),
        )
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(503, "Identity provider unavailable") from None
    except (jwt.PyJWTError, ValueError, TypeError, OverflowError):
        raise HTTPException(401, "Identity could not be verified") from None


DB = Annotated[Connection, Depends(database, scope="function")]


def owner(request: Request, db: DB) -> UUID:
    token = request.cookies.get(COOKIE)
    if token:
        value = db.execute(
            text("SELECT owner FROM logins WHERE digest=:key AND expires>now() FOR SHARE"),
            {"key": digest(token)},
        ).scalar_one_or_none()
        if isinstance(value, UUID):
            return value
    raise HTTPException(401, "Sign in required")


class Credential(StrictModel):
    credential: str = Field(min_length=1, max_length=16384)


router = APIRouter(prefix="/api/account")


@router.post("/challenge")
def challenge(response: Response, db: DB) -> dict[str, str]:
    audience = client_id()
    db.execute(text("SELECT pg_advisory_xact_lock(134953)"))
    db.execute(text("DELETE FROM challenges WHERE expires<=now()"))
    if db.execute(text("SELECT count(*) FROM challenges")).scalar_one() >= 256:
        raise HTTPException(429, "Sign-in capacity reached")
    token, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.execute(
        text(
            "INSERT INTO challenges(digest,nonce,expires) VALUES (:key,:nonce,now()+interval '5 minutes')"
        ),
        {"key": digest(token), "nonce": nonce},
    )
    cookie(response, CHALLENGE, token, 300)
    return {"client_id": audience, "nonce": nonce}


@router.post("/login")
def login(body: Credential, request: Request, response: Response, db: DB) -> dict[str, str]:
    nonce = db.execute(
        text("DELETE FROM challenges WHERE digest=:key AND expires>now() RETURNING nonce"),
        {"key": digest(request.cookies.get(CHALLENGE, ""))},
    ).scalar_one_or_none()
    if not nonce:
        raise HTTPException(401, "Sign-in expired")
    try:
        subject, name, email = claims(body.credential, nonce)
    except HTTPException as exc:
        response.status_code = exc.status_code
        cookie(response, CHALLENGE, "", 0)
        return {"detail": str(exc.detail)}
    user = db.execute(
        text("""INSERT INTO members(id,issuer,subject,display_name,verified_email)
        VALUES (:id,:issuer,:sub,:name,:email) ON CONFLICT(issuer,subject) DO UPDATE SET
        display_name=excluded.display_name,verified_email=excluded.verified_email,updated_at=now() RETURNING id"""),
        {"id": uuid4(), "issuer": ISSUER, "sub": subject, "name": name, "email": email},
    ).scalar_one()
    token = secrets.token_urlsafe(32)
    db.execute(
        text("DELETE FROM logins WHERE expires<=now() OR digest=:old"),
        {"old": digest(request.cookies.get(COOKIE, ""))},
    )
    db.execute(
        text("INSERT INTO logins VALUES (:key,:owner,now()+interval '8 hours')"),
        {"key": digest(token), "owner": user},
    )
    cookie(response, CHALLENGE, "", 0)
    cookie(response, COOKIE, token, 28800)
    return {"name": name}


@router.get("/me")
def me(user: Annotated[UUID, Depends(owner)], db: DB) -> dict[str, str]:
    return {
        "name": db.execute(
            text("SELECT display_name FROM members WHERE id=:id"), {"id": user}
        ).scalar_one()
    }


@router.post("/logout")
def logout(
    request: Request, response: Response, user: Annotated[UUID, Depends(owner)], db: DB
) -> dict[str, bool]:
    db.execute(
        text("DELETE FROM logins WHERE owner=:id AND digest=:key"),
        {"id": user, "key": digest(request.cookies.get(COOKIE, ""))},
    )
    cookie(response, COOKIE, "", 0)
    return {"ok": True}
