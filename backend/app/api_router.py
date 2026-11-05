"""Every module's router is registered here, under the /api/v1 prefix."""

from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import DbSession
from app.modules.ai.router import router as ai_router
from app.modules.auth.router import router as auth_router
from app.modules.authorities.router import router as authorities_router
from app.modules.communications.router import router as communications_router
from app.modules.complaints.router import dashboard_router
from app.modules.complaints.router import router as complaints_router
from app.modules.evidence.router import router as evidence_router
from app.modules.locations.router import router as locations_router
from app.modules.monitoring.router import router as monitoring_router
from app.modules.resolutions.router import router as resolutions_router
from app.modules.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/health", tags=["health"])
def health(db: DbSession) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "error"
    return {"status": "ok" if database == "ok" else "degraded", "database": database}


api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(complaints_router)
api_router.include_router(evidence_router)
api_router.include_router(dashboard_router)
api_router.include_router(locations_router)
api_router.include_router(ai_router)
api_router.include_router(authorities_router)
api_router.include_router(communications_router)
api_router.include_router(monitoring_router)
api_router.include_router(resolutions_router)
