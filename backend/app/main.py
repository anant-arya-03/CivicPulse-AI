"""FastAPI application entry point.

Run with:  uvicorn app.main:app --reload   (from the backend/ folder)
"""

import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  (registers all ORM models)
from app.api_router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.upload_limit import UploadSizeLimitMiddleware
from app.modules.auth.dependencies import verify_csrf


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    application = FastAPI(
        title="CivicPulse AI API",
        version="0.1.0",
        description="See it. Report it. Track it. Resolve it.",
        # CSRF check runs before every route; it only acts on state-changing requests.
        dependencies=[Depends(verify_csrf)],
        # Hide interactive docs in production.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )

    # The browser normally reaches us through the Next.js proxy (same origin), so CORS
    # only matters for direct calls, e.g. a future mobile web client.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )
    # Refuse oversized uploads before FastAPI starts reading them.
    application.add_middleware(UploadSizeLimitMiddleware)
    # Added last, so it wraps everything: even a refused upload gets the headers.
    application.add_middleware(SecurityHeadersMiddleware)

    register_error_handlers(application)
    application.include_router(api_router)
    return application


app = create_app()
