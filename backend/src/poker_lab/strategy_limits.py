"""Bound policy JSON before framework parsing, including chunked requests."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class PolicyBodyLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] not in (
            "/api/strategy/multistreet",
            "/api/strategy/multistreet-policy",
        ):
            await self.app(scope, receive, send)
            return
        buffer = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            part = message.get("body", b"")
            if len(part) + len(buffer) > 65536:
                await JSONResponse(
                    {"detail": "Multistreet requests are limited to 64 KiB"}, status_code=413
                )(scope, receive, send)
                return
            buffer.extend(part)
            if not message.get("more_body", False):
                break
        pending = True

        async def bounded_receive() -> Message:
            nonlocal pending
            if pending:
                pending = False
                return {"type": "http.request", "body": bytes(buffer), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
