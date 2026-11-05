"""Reject oversized uploads before they are parsed or stored.

FastAPI parses a multipart upload (buffering it to a temp file) before the route function runs,
so the route's own size check would come too late for, say, a 2 GB request. This middleware
looks at the Content-Length header first and refuses anything clearly too big.

The route still checks the real size, because a client could omit or fake the header.
"""

import json

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings

# Room for the multipart boundaries and headers around the file itself.
_MULTIPART_OVERHEAD = 64 * 1024
# We read (and throw away) up to this much of a rejected upload, so the connection stays clean
# and proxies get a proper 413 response. Anything bigger is cut off instead.
_MAX_DISCARD_BYTES = 64 * 1024 * 1024


class UploadSizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in {"POST", "PUT", "PATCH"}:
            headers = dict(scope["headers"])
            content_length = headers.get(b"content-length")
            settings = get_settings()
            limit = settings.max_upload_bytes + _MULTIPART_OVERHEAD
            if content_length and content_length.isdigit() and int(content_length) > limit:
                fully_read = await _discard_body(receive)
                await _send_too_large(send, settings.max_upload_mb, close=not fully_read)
                return
        await self.app(scope, receive, send)


async def _discard_body(receive: Receive) -> bool:
    """Read the request body without keeping it. Returns True if it was read to the end."""
    discarded = 0
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return False
        discarded += len(message.get("body", b""))
        if not message.get("more_body", False):
            return True
        if discarded > _MAX_DISCARD_BYTES:
            return False


async def _send_too_large(send: Send, max_mb: int, *, close: bool) -> None:
    message = f"The upload is larger than {max_mb} MB. Please choose a smaller photo."
    error = {"error": {"code": "FILE_REJECTED", "message": message, "details": {}}}
    body = json.dumps(error).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
    ]
    if close:
        # Part of the upload is still unread on this connection, so it can't be reused.
        headers.append((b"connection", b"close"))
    await send({"type": "http.response.start", "status": 413, "headers": headers})
    await send({"type": "http.response.body", "body": body})
