"""Run against a disposable PG16 cluster via libpq PGHOST/PGPORT/PGUSER/PGPASSWORD."""

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import psycopg
from sqlalchemy.engine import URL

BACKEND = Path(__file__).resolve().parents[1] / "backend"
TABLES = (
    "members",
    "saved_hands",
    "opponent_archives",
    "practice_sessions",
    "practice_attempts",
)
EXPECTED = {*TABLES, "logins", "challenges", "alembic_version"}


def snapshot(name):
    with psycopg.connect(dbname=name) as db:
        return {
            table: db.execute("SELECT * FROM " + table + " ORDER BY 1,2").fetchall()
            for table in TABLES
        }


def app_check(name, expected):
    env = os.environ.copy()
    env["DATABASE_URL"] = URL.create(
        "postgresql+psycopg",
        username=env["PGUSER"],
        password=env["PGPASSWORD"],
        host=env["PGHOST"],
        port=int(env["PGPORT"]),
        database=name,
    ).render_as_string(hide_password=False)
    # Each call boots and shuts down a separate application process without a listening port.
    subprocess.run(
        [
            sys.executable,
            "-c",
            """import sys
from fastapi.testclient import TestClient
from poker_lab.api import create_app
with TestClient(create_app()) as c:
    assert c.get('/health').status_code == 200
    assert c.get('/ready').status_code == int(sys.argv[1])
    assert c.get('/api/profiles').status_code == 200
    if int(sys.argv[1]) == 200:
        for token, count in [('rehearsal-owner',1),('rehearsal-other',0)]:
            c.cookies.set('miracle_login',token)
            hands=c.get('/api/account/hands')
            assert hands.status_code == 200 and len(hands.json()) == count
            assert len(c.get('/api/account/sessions').json()) == count
            assert c.get('/api/account/observations').json()['revision'] == count
            if count:
                assert c.get('/api/account/hands/'+hands.json()[0]['id']).json()['title']=='Practice hand'
                sid=c.get('/api/account/sessions').json()[0]
                assert len(c.get('/api/account/sessions/'+sid).json()['attempts'])==1
""",
            str(expected),
        ],
        env=env,
        cwd=BACKEND,
        check=True,
    )
    return env


def rehearse():
    import hashlib

    from poker_lab.strategy_catalog import configured_catalog
    from poker_lab.training import Exercise, Submission, exercises, grade

    if not __debug__:
        raise SystemExit("Recovery verification requires Python assertions")
    if os.environ.get("MIRACLE_DISPOSABLE_PG") != "yes":
        raise SystemExit(
            "Set MIRACLE_DISPOSABLE_PG=yes for an isolated disposable PG16 cluster"
        )
    source, target = ["rehearsal_" + uuid4().hex for _ in range(2)]
    created = []
    try:
        for name in (source, target):
            subprocess.run(["createdb", "--template=template0", name], check=True)
            created.append(name)
        env = app_check(source, 503)
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND,
            env=env,
            check=True,
        )
        catalog = configured_catalog(None)
        p = exercises(catalog)[0]
        request = Submission(
            **p.model_dump(include=set(Exercise.model_fields)), action=p.actions[0]
        )
        member, other, session, attempt = [uuid4() for _ in range(4)]
        hand = {
            "version": "1.0",
            "hero": "BTN",
            "small_blind": 50,
            "big_blind": 100,
            "board": [],
            "actions": [],
            "seats": {
                k: {"name": k, "stack": 10000, "cards": None}
                for k in ["BTN", "SB", "BB", "UTG", "HJ", "CO"]
            },
        }
        record = {
            "id": str(attempt),
            "session": str(session),
            "time": "2026-01-01T00:00:00Z",
            "submission": request.model_dump(mode="json"),
            "feedback": grade(catalog, request).model_dump(),
            "position": p.position,
            "street": p.street,
            "retry": False,
            "origin": "practice",
        }
        with psycopg.connect(dbname=source) as db:
            assert db.info.server_version // 10000 == 16
            assert {
                r[0]
                for r in db.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public'"
                )
            } == EXPECTED
            db.execute("UPDATE alembic_version SET version_num='older'")
            db.commit()
            app_check(source, 503)
            db.execute("UPDATE alembic_version SET version_num='001_accounts'")
            for who, token in [(member, "rehearsal-owner"), (other, "rehearsal-other")]:
                db.execute(
                    "INSERT INTO members(id,issuer,subject,display_name) VALUES(%s,'fixture',%s,'Reviewer')",
                    (who, str(who)),
                )
                db.execute(
                    "INSERT INTO logins VALUES(%s,%s,now()+interval '1 hour')",
                    (hashlib.sha256(token.encode()).hexdigest(), who),
                )
            db.execute(
                "INSERT INTO challenges VALUES('fixture','fixture',now()+interval '1 minute')"
            )
            db.execute(
                "INSERT INTO saved_hands(owner,id,title,hand,source,version) VALUES(%s,%s,'Practice hand',%s,'manual','1.0')",
                (member, uuid4(), json.dumps(hand)),
            )
            db.execute(
                "INSERT INTO opponent_archives(owner,archive,revision) VALUES(%s,%s,1)",
                (
                    member,
                    json.dumps({"version": "1.0", "entries": [], "overrides": {}}),
                ),
            )
            db.execute("INSERT INTO practice_sessions VALUES(%s,%s)", (member, session))
            db.execute(
                "INSERT INTO practice_attempts VALUES(%s,%s,%s,%s)",
                (member, attempt, session, json.dumps(record)),
            )
        app_check(source, 200)
        app_check(source, 200)
        expected = snapshot(source)
        with TemporaryDirectory() as temp:
            archive = str(Path(temp) / "disposable.dump")
            subprocess.run(["pg_dump", "-Fc", "-f", archive, source], check=True)
            subprocess.run(
                [
                    "pg_restore",
                    "--single-transaction",
                    "--exit-on-error",
                    "--no-owner",
                    "-d",
                    target,
                    archive,
                ],
                check=True,
            )
        with psycopg.connect(dbname=target) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (
                "001_accounts",
            )
            assert db.execute("SELECT count(*) FROM logins").fetchone() == (2,)
            assert db.execute("SELECT count(*) FROM challenges").fetchone() == (1,)
            db.execute("TRUNCATE logins,challenges")
            for table in ("logins", "challenges"):
                assert db.execute("SELECT count(*) FROM " + table).fetchone() == (0,)
            constraints = db.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='public'::regnamespace"
            ).fetchall()
            for fragment in (
                "UNIQUE (issuer, subject)",
                "FOREIGN KEY (owner, session) REFERENCES practice_sessions(owner, id)",
                "PRIMARY KEY (owner, id)",
            ):
                assert any(fragment in row[0] for row in constraints)
        assert snapshot(target) == expected
        print(
            "PG16 fresh migration, two backend starts, owner isolation, restore equality and session invalidation passed"
        )
    finally:
        for name in reversed(created):
            subprocess.run(["dropdb", name], check=True)


if __name__ == "__main__":
    rehearse()
