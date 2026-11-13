"""Private records. Every query includes the authenticated owner."""

import json
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy import Connection, text

from poker_lab import analyzer, observations, training
from poker_lab.account_auth import owner
from poker_lab.account_db import database
from poker_lab.strategy_catalog import SolutionCatalog
from poker_lab.strategy_models import StrictModel

User = Annotated[UUID, Depends(owner)]
DB = Annotated[Connection, Depends(database, scope="function")]
Page = Annotated[int, Query(ge=0, le=1000000)]


class HandBody(StrictModel):
    title: str = Field(min_length=1, max_length=100)
    hand: analyzer.Hand


class ObservationSave(StrictModel):
    revision: int = Field(ge=0, strict=True)
    archive: observations.Archive


class Confirmation(StrictModel):
    confirm: Literal[True]


def missing() -> HTTPException:
    return HTTPException(404, "Record unavailable")


def data_router(registry: SolutionCatalog) -> APIRouter:
    router = APIRouter(prefix="/api/account")

    @router.get("/hands")
    def hands(user: User, db: DB, offset: Page = 0) -> list[dict[str, Any]]:
        return [
            dict(r)
            for r in db.execute(
                text(
                    "SELECT id,title,updated_at FROM saved_hands WHERE owner=:u ORDER BY updated_at DESC,id LIMIT 50 OFFSET :offset"
                ),
                {"u": user, "offset": offset},
            ).mappings()
        ]

    @router.get("/hands/{key}")
    def hand(key: UUID, user: User, db: DB) -> dict[str, Any]:
        row = (
            db.execute(
                text(
                    "SELECT id,title,hand,source,source_id,version,created_at,updated_at FROM saved_hands WHERE owner=:u AND id=:id"
                ),
                {"u": user, "id": key},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise missing()
        return dict(row)

    def hand_params(body: HandBody, user: UUID, key: UUID) -> dict[str, Any]:
        try:
            final = analyzer.replay(body.hand, [])[-1]
            if any(
                seat.cards and position != body.hand.hero and not final.players[position].cards
                for position, seat in body.hand.seats.items()
            ):
                raise ValueError("Unrevealed opponent cards cannot be archived")
        except ValueError:
            raise HTTPException(422, "Invalid hand history") from None
        return {
            "u": user,
            "id": key,
            "title": body.title,
            "body": body.hand.model_dump_json(),
            "version": body.hand.version,
            "source": "trainer review" if body.hand.trainer_hand_id else "manual",
            "source_id": body.hand.trainer_hand_id,
        }

    @router.post("/hands")
    def create(body: HandBody, user: User, db: DB) -> dict[str, UUID]:
        key = uuid4()
        db.execute(
            text("""INSERT INTO saved_hands(owner,id,title,hand,source,source_id,version)
            VALUES(:u,:id,:title,CAST(:body AS jsonb),:source,:source_id,:version)"""),
            hand_params(body, user, key),
        )
        return {"id": key}

    @router.post("/hands/{key}/update")
    def update(key: UUID, body: HandBody, user: User, db: DB) -> dict[str, bool]:
        if not db.execute(
            text("""UPDATE saved_hands SET title=:title,hand=CAST(:body AS jsonb),source=:source,
            source_id=:source_id,version=:version,updated_at=now() WHERE owner=:u AND id=:id"""),
            hand_params(body, user, key),
        ).rowcount:
            raise missing()
        return {"ok": True}

    @router.post("/hands/{key}/delete")
    def delete_hand(key: UUID, user: User, db: DB) -> dict[str, bool]:
        if not db.execute(
            text("DELETE FROM saved_hands WHERE owner=:u AND id=:id"), {"u": user, "id": key}
        ).rowcount:
            raise missing()
        return {"ok": True}

    @router.get("/observations")
    def archive(user: User, db: DB) -> dict[str, Any]:
        row = (
            db.execute(
                text("SELECT revision,archive FROM opponent_archives WHERE owner=:u"), {"u": user}
            )
            .mappings()
            .one_or_none()
        )
        return (
            dict(row)
            if row
            else {"revision": 0, "archive": {"version": "1.0", "entries": [], "overrides": {}}}
        )

    @router.post("/observations")
    def save_archive(body: ObservationSave, user: User, db: DB) -> dict[str, int]:
        try:
            observations.report(observations.SummaryRequest(archive=body.archive))
        except ValueError:
            raise HTTPException(422, "Invalid observation evidence") from None
        params = {"u": user, "rev": body.revision, "body": body.archive.model_dump_json()}
        sql = (
            "INSERT INTO opponent_archives(owner,revision,archive) VALUES(:u,1,CAST(:body AS jsonb)) ON CONFLICT DO NOTHING"
            if not body.revision
            else "UPDATE opponent_archives SET revision=revision+1,archive=CAST(:body AS jsonb),updated_at=now() WHERE owner=:u AND revision=:rev"
        )
        if not db.execute(text(sql), params).rowcount:
            raise HTTPException(409, "Archive changed. Reload before replacing.")
        return {"revision": body.revision + 1}

    @router.post("/training")
    def import_training(body: training.Archive, user: User, db: DB) -> dict[str, int]:
        # Serialize imports per account; conflicting replay IDs roll back the whole batch.
        db.execute(text("SELECT id FROM members WHERE id=:u FOR UPDATE"), {"u": user})
        added = 0
        try:
            training.summarize(body)
            for attempt in body.attempts:
                params = {
                    "u": user,
                    "id": attempt.id,
                    "session": attempt.session,
                    "body": attempt.model_dump_json(),
                }
                old = db.execute(
                    text("SELECT attempt FROM practice_attempts WHERE owner=:u AND id=:id"), params
                ).scalar_one_or_none()
                if old is not None:
                    if old != json.loads(attempt.model_dump_json()):
                        raise HTTPException(409, "Attempt ID already has different content")
                    continue
                training.verify_attempt(registry, attempt)
                db.execute(
                    text(
                        "INSERT INTO practice_sessions VALUES(:u,:session) ON CONFLICT DO NOTHING"
                    ),
                    params,
                )
                db.execute(
                    text(
                        "INSERT INTO practice_attempts VALUES(:u,:id,:session,CAST(:body AS jsonb))"
                    ),
                    params,
                )
                added += 1
        except ValueError:
            raise HTTPException(422, "Attempt verification failed") from None
        return {"added": added, "duplicates": len(body.attempts) - added}

    @router.get("/sessions")
    def sessions(user: User, db: DB, offset: Page = 0) -> list[UUID]:
        return list(
            db.execute(
                text(
                    "SELECT id FROM practice_sessions WHERE owner=:u ORDER BY id LIMIT 50 OFFSET :offset"
                ),
                {"u": user, "offset": offset},
            ).scalars()
        )

    @router.get("/sessions/{key}")
    def attempts(key: UUID, user: User, db: DB, offset: Page = 0) -> dict[str, Any]:
        if not db.execute(
            text("SELECT id FROM practice_sessions WHERE owner=:u AND id=:id"),
            {"u": user, "id": key},
        ).scalar():
            raise missing()
        rows: list[Any] = list(
            db.execute(
                text(
                    "SELECT attempt FROM practice_attempts WHERE owner=:u AND session=:id ORDER BY attempt->>'time',id LIMIT 64 OFFSET :offset"
                ),
                {"u": user, "id": key, "offset": offset},
            ).scalars()
        )
        return {"version": "1", "attempts": list(rows)}

    @router.post("/sessions/{key}/delete")
    def delete_session(key: UUID, user: User, db: DB) -> dict[str, bool]:
        if not db.execute(
            text("DELETE FROM practice_sessions WHERE owner=:u AND id=:id"), {"u": user, "id": key}
        ).rowcount:
            raise missing()
        return {"ok": True}

    @router.post("/attempts/{key}/delete")
    def delete_attempt(key: UUID, user: User, db: DB) -> dict[str, bool]:
        if not db.execute(
            text("DELETE FROM practice_attempts WHERE owner=:u AND id=:id"), {"u": user, "id": key}
        ).rowcount:
            raise missing()
        return {"ok": True}

    @router.post("/training/clear")
    def clear(body: Confirmation, user: User, db: DB) -> dict[str, bool]:
        db.execute(text("DELETE FROM practice_sessions WHERE owner=:u"), {"u": user})
        return {"ok": True}

    @router.post("/delete")
    def delete_account(body: Confirmation, user: User, db: DB) -> dict[str, bool]:
        db.execute(text("DELETE FROM members WHERE id=:u"), {"u": user})
        return {"ok": True}

    return router
