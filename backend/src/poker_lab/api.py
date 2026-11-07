import os
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Request, Response

from poker_lab.schemas import EmptyRequest, GameView, HeroAction
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


def create_app(store: SessionStore | None = None) -> FastAPI:
    sessions = store if store is not None else SessionStore()
    app = FastAPI(title="Poker Strategy Lab", version="0.2.0")

    @app.middleware("http")
    async def protect(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path.startswith("/api/") and request.method == "POST":
            origin = request.headers.get("origin")
            allowed = os.environ.get("TRAINER_ORIGIN", "http://localhost:3000")
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

    @app.post("/api/games", response_model=GameView)
    def create(body: EmptyRequest, request: Request, response: Response) -> GameView:
        with errors():
            token, state = sessions.create(request.cookies.get(COOKIE))
        response.set_cookie(
            COOKIE,
            token,
            httponly=True,
            samesite="strict",
            path="/api",
            secure=os.environ.get("COOKIE_SECURE", "false") == "true",
            max_age=int(sessions.ttl),
        )
        return state

    @app.get("/api/game", response_model=GameView)
    def current(request: Request) -> GameView:
        with errors():
            return sessions.get(request.cookies.get(COOKIE))

    @app.post("/api/game/actions", response_model=GameView)
    def action(body: HeroAction, request: Request) -> GameView:
        with errors():
            return sessions.act(request.cookies.get(COOKIE), body)

    return app


app = create_app()
