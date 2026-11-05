"""Security headers on every API response.

- nosniff / frame denial / no referrer: standard hardening for any web API.
- Cache-Control: no-store by default, because API responses contain personal data (complaints,
  addresses, messages). Routes that set their own caching (the private photo endpoint) keep it.
- A strict Content-Security-Policy for /api responses: they are data, never pages to render.
  (The interactive /docs page loads scripts, so it is left alone; it is disabled in production.)
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_ALWAYS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
]
_API_CSP = (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = scope["path"].startswith("/api/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                extra = list(_ALWAYS)
                if is_api:
                    extra.append(_API_CSP)
                    extra.append((b"cache-control", b"no-store"))
                headers += [(name, value) for name, value in extra if name not in present]
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
