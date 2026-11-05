"""Domain errors and the handlers that turn them into one consistent JSON shape:

    {"error": {"code": "NOT_FOUND", "message": "...", "details": {...}}}

Services raise these exceptions; routers never build error responses by hand.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "BAD_REQUEST"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UnauthenticatedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHENTICATED"


class CSRFError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "CSRF_FAILED"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


class BusinessRuleError(AppError):
    """Input that is well-formed but breaks a rule, e.g. confirming a location with no city."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "VALIDATION_ERROR"


class InvalidTransitionError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "INVALID_STATUS_TRANSITION"


class FileRejectedError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "FILE_REJECTED"


class FileTooLargeError(FileRejectedError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "RATE_LIMITED"


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "SERVICE_UNAVAILABLE"


class SubmissionFailedError(AppError):
    """The email provider couldn't send the complaint. Nothing was delivered; retrying is safe."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "SUBMISSION_FAILED"


class RealSubmissionBlockedError(AppError):
    """A real (non-simulated) send was refused by the safety rules."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "REAL_SUBMISSION_BLOCKED"


class AIUnavailableError(AppError):
    """The AI couldn't produce a usable answer. The UI offers the manual path instead."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "AI_UNAVAILABLE"


def _error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


async def _handle_app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(
        status_code=exc.status_code, content=_error_body(exc.code, exc.message, exc.details)
    )


async def _handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields = [
        {
            "field": ".".join(str(part) for part in err["loc"] if part != "body"),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=_error_body("VALIDATION_ERROR", "Some fields are invalid.", {"fields": fields}),
    )


async def _handle_http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    return JSONResponse(status_code=exc.status_code, content=_error_body(code, str(exc.detail)))


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # Log the full error for developers, but never leak internals to the client.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body("INTERNAL_ERROR", "Something went wrong. Please try again."),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
