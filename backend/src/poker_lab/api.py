import os
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from sqlalchemy import text

from poker_lab import account_auth, analyzer, observations
from poker_lab.account_auth import DB
from poker_lab.account_data import data_router
from poker_lab.equity_api import create_equity_router
from poker_lab.profiles import OpponentProfile, default_profiles
from poker_lab.schemas import GameView, HeroAction, NewHandRequest
from poker_lab.strategy_api import create_strategy_router
from poker_lab.strategy_catalog import SolutionCatalog, configured_catalog, strict_json
from poker_lab.strategy_limits import PolicyBodyLimit
from poker_lab.study import StudyRequest, StudyResult, analyze, study_current
from poker_lab.trainer import CapacityReached, MissingSession, SessionStore, StaleHand

COOKIE = "poker_session"


@contextmanager
def errors() -> Iterator[None]:
    try:
        yield
    except MissingSession:
        raise HTTPException(404, "No active session; start a new hand") from None
    except StaleHand as exc:
        raise HTTPException(409, str(exc)) from None
    except CapacityReached:
        raise HTTPException(503, "Trainer is busy; please try again later") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


def create_app(
    store: SessionStore | None = None, *, strategy_catalog: SolutionCatalog | None = None
) -> FastAPI:
    sessions = store if store is not None else SessionStore()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        from poker_lab.account_db import pool

        if pool.cache_info().currsize:
            pool().dispose()
            pool.cache_clear()

    app = FastAPI(title="Poker Strategy Lab", version="0.5.0", lifespan=lifespan)

    @app.middleware("http")
    async def protect(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path.startswith("/api/") and request.method == "POST":
            origin = request.headers.get("origin")
            allowed = os.environ.get("TRAINER_ORIGIN", "http://localhost:3000")
            if request.url.path.startswith("/api/account/") and origin != allowed:
                return Response(status_code=403)
            if origin is not None and origin != allowed:
                return Response(status_code=403)
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return Response(status_code=415)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Vary"] = "Cookie"
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/games", response_model=observations.GameWithObservation)
    def create(body: NewHandRequest, request: Request, response: Response) -> GameView:
        with errors():
            token, state = sessions.create(request.cookies.get(COOKIE), body.opponents)
        response.set_cookie(
            COOKIE,
            token,
            httponly=True,
            samesite="strict",
            path="/api",
            secure=os.environ.get("COOKIE_SECURE", "false") == "true",
            max_age=int(sessions.ttl),
        )
        return observations.trainer_game(state)

    @app.get("/api/game", response_model=observations.GameWithObservation)
    def current(request: Request) -> GameView:
        with errors():
            return observations.trainer_game(sessions.get(request.cookies.get(COOKIE)))

    @app.post("/api/game/actions", response_model=observations.GameWithObservation)
    def action(body: HeroAction, request: Request) -> GameView:
        with errors():
            return observations.trainer_game(sessions.act(request.cookies.get(COOKIE), body))

    @app.get("/api/profiles", response_model=list[OpponentProfile])
    def profiles() -> list[OpponentProfile]:
        return default_profiles()

    @app.post("/api/study", response_model=StudyResult)
    def study(body: StudyRequest) -> StudyResult:
        return analyze(body)

    @app.get("/api/study/current", response_model=StudyResult)
    def current_study(request: Request) -> StudyResult:
        with errors():
            return study_current(sessions.get(request.cookies.get(COOKIE)))

    app.include_router(account_auth.router)

    @app.get("/ready")
    def ready(db: DB) -> dict[str, str]:
        if (
            db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            != "001_accounts"
        ):
            raise HTTPException(503, "Database migration required")
        return {"status": "ready"}

    app.include_router(create_equity_router())
    registry = strategy_catalog or configured_catalog(os.environ.get("STRATEGY_CATALOG"))
    app.include_router(create_strategy_router(registry))
    app.include_router(data_router(registry))

    @app.post("/api/analyzer/replay")
    async def replay_hand(request: Request, body: analyzer.Hand) -> list[analyzer.Snapshot]:
        with errors():
            strict_json((await request.body()).decode("utf-8"))
            return analyzer.replay(
                body,
                [
                    (e.document.solution_id, e.document.scenario)
                    for e in registry.visible("validated_gto")
                ],
            )

    @app.get("/api/analyzer/trainer")
    def review_trainer(request: Request) -> analyzer.Hand:
        with errors():
            return analyzer.from_trainer(sessions.get(request.cookies.get(COOKIE)))

    @app.post("/api/observations/report")
    async def observation_report(
        request: Request, body: observations.SummaryRequest
    ) -> list[observations.PlayerReport]:
        with errors():
            raw = await request.body()
            if len(raw) > 1024 * 1024:
                raise HTTPException(413, "Observation archive exceeds 1 MiB")
            strict_json(raw.decode("utf-8"))
            return observations.report(body)

    from starlette.middleware.trustedhost import TrustedHostMiddleware

    hosts = os.environ.get("ALLOWED_HOSTS")
    if hosts:
        app.add_middleware(
            TrustedHostMiddleware, allowed_hosts=[h.strip() for h in hosts.split(",")]
        )
    app.add_middleware(PolicyBodyLimit)
    return app


app = create_app()
