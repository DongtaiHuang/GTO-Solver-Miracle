"""Short-lived unit-of-work connections; guest endpoints never open a database."""

import os
from collections.abc import Iterator
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError


@lru_cache(maxsize=1)
def pool() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url or not url.startswith("postgresql+psycopg://"):
        raise HTTPException(503, "Account database unavailable")
    return create_engine(
        url,
        pool_size=4,
        max_overflow=2,
        pool_timeout=3,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 4,
            "options": "-c statement_timeout=8000 -c lock_timeout=3000",
        },
    )


def database() -> Iterator[Connection]:
    try:
        with pool().begin() as connection:
            yield connection
    except SQLAlchemyError:
        import logging

        logging.getLogger(__name__).error('{"event":"account_database_unavailable"}')
        raise HTTPException(503, "Account database unavailable") from None
