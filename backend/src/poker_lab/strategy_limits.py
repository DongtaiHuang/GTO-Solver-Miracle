"""Bound policy JSON before framework parsing, including chunked requests."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class PolicyBodyLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        account = (
            scope["type"] == "http"
            and scope["path"].startswith("/api/account/")
            and scope["method"] == "POST"
        )
        if (
            scope["type"] != "http"
            or not account
            and scope["path"]
            not in (
                "/api/strategy/training/grade",
                "/api/strategy/training/report",
                "/api/strategy/multistreet",
                "/api/strategy/multistreet-policy",
            )
        ):
            await self.app(scope, receive, send)
            return
        limit = 1048576 if account and scope["path"] != "/api/account/training" else 65536
        buffer = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            part = message.get("body", b"")
            if len(part) + len(buffer) > limit:
                await JSONResponse({"detail": "Request exceeds size limit"}, status_code=413)(
                    scope, receive, send
                )
                return
            buffer.extend(part)
            if not message.get("more_body", False):
                break
        if account:
            from poker_lab.strategy_catalog import strict_json

            try:
                strict_json(buffer.decode("utf-8"))
            except (ValueError, RecursionError):
                await JSONResponse({"detail": "Invalid account JSON"}, status_code=422)(
                    scope, receive, send
                )
                return
        pending = True

        async def bounded_receive() -> Message:
            nonlocal pending
            if pending:
                pending = False
                return {"type": "http.request", "body": bytes(buffer), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
