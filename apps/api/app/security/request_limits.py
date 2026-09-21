from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestSizeLimitMiddleware:
    """Reject HTTP request bodies larger than the configured byte limit."""

    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        if max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be greater than zero")
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = _content_length(scope)
        if content_length is not None and content_length > self.max_body_bytes:
            await _send_too_large(send)
            return

        body = bytearray()
        more_body = True

        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                await self.app(scope, _replay(body, message), send)
                return

            chunk = message.get("body", b"")
            body.extend(chunk)
            if len(body) > self.max_body_bytes:
                await _send_too_large(send)
                return

            more_body = message.get("more_body", False)

        replay = _replay(body)
        await self.app(scope, replay, send)


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() != b"content-length":
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


async def _send_too_large(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json")],
        },
    )
    await send(
        {
            "type": "http.response.body",
            "body": b'{"detail":"Request body is too large."}',
        },
    )


def _replay(body: bytearray, pending: Message | None = None) -> Receive:
    messages: list[Message] = [
        {
            "type": "http.request",
            "body": bytes(body),
            "more_body": False,
        },
    ]
    if pending is not None:
        messages.insert(0, pending)

    async def receive() -> Message:
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    return receive
