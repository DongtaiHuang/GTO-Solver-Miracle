"""Fail fast on unsafe production environment settings without logging their values."""

import os
import re
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def validate_environment() -> None:
    mode = os.getenv("MIRACLE_ENV", "development")
    if mode == "development":
        return
    if mode != "production":
        raise ValueError("MIRACLE_ENV must be development or production")
    if os.getenv("COOKIE_SECURE") != "true":
        raise ValueError("Production requires COOKIE_SECURE=true")
    origin = urlsplit(os.getenv("TRAINER_ORIGIN", ""))
    if (
        origin.scheme != "https"
        or not origin.hostname
        or origin.username is not None
        or origin.password is not None
        or origin.path
        or origin.query
        or origin.fragment
        or not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]+)?", origin.netloc)
    ):
        raise ValueError("Production requires an exact HTTPS TRAINER_ORIGIN")
    hosts = os.getenv("ALLOWED_HOSTS", "").split(",")
    if not all(re.fullmatch(r"[A-Za-z0-9.-]+", host.strip()) for host in hosts):
        raise ValueError("Production requires explicit ALLOWED_HOSTS")
    try:
        url = make_url(os.getenv("DATABASE_URL", ""))
        valid = (
            url.drivername == "postgresql+psycopg"
            and url.host
            and url.database
            and url.username
            and url.password
        )
    except (ArgumentError, ValueError):
        valid = False
    if not valid:
        raise ValueError("Production requires a configured PostgreSQL DATABASE_URL")
    if os.getenv("PGSSLROOTCERT") and url.query.get("sslmode") != "verify-full":
        raise ValueError("Managed PostgreSQL requires sslmode=verify-full with PGSSLROOTCERT")
