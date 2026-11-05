import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.database import DbSession
from app.core.errors import NotFoundError
from app.core.rate_limit import RateLimit
from app.integrations.ai_providers.base import AIProvider
from app.integrations.ai_providers.factory import get_ai_provider
from app.integrations.email_providers.base import EmailProvider
from app.integrations.email_providers.factory import get_email_provider
from app.modules.auth.dependencies import CurrentUser
from app.modules.communications.schemas import CommunicationRead
from app.modules.monitoring import service
from app.modules.monitoring.schemas import (
    AdvanceResult,
    MonitoringRead,
    ReplyKindRequest,
    ScheduledActionRead,
    SimulateReplyRequest,
    SimulationInfo,
)
from app.modules.monitoring.simulation import REPLY_SCENARIO_LABELS

router = APIRouter(tags=["monitoring"])

AI = Annotated[AIProvider, Depends(get_ai_provider)]
Email = Annotated[EmailProvider, Depends(get_email_provider)]


@router.get("/complaints/{complaint_id}/monitoring", response_model=MonitoringRead)
def monitoring(complaint_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return service.get_monitoring(db, user, complaint_id)


@router.put("/communications/{communication_id}/reply-kind", response_model=CommunicationRead)
def set_reply_kind(
    communication_id: uuid.UUID, data: ReplyKindRequest, user: CurrentUser, db: DbSession
):
    return service.classify_reply_manually(db, user, communication_id, data.kind)


# ── Development / demo only ─────────────────────────────────────────────────


def require_simulation() -> None:
    """The simulation endpoints don't exist unless ENABLE_SIMULATION=true (never in production)."""
    if not get_settings().enable_simulation:
        raise NotFoundError("Not found.")


simulation_dependencies = [
    Depends(require_simulation),
    Depends(RateLimit("simulation", times=30, seconds=60)),
]


@router.get("/simulation", response_model=SimulationInfo)
def simulation_info(_: CurrentUser):
    enabled = get_settings().enable_simulation
    return SimulationInfo(
        enabled=enabled,
        reply_scenarios=[{"id": k, "label": v} for k, v in REPLY_SCENARIO_LABELS.items()]
        if enabled
        else [],
    )


@router.post(
    "/complaints/{complaint_id}/simulation/reply",
    response_model=CommunicationRead,
    status_code=201,
    dependencies=simulation_dependencies,
)
def simulate_reply(
    complaint_id: uuid.UUID, data: SimulateReplyRequest, user: CurrentUser, db: DbSession, ai: AI
):
    return service.simulate_reply(
        db, ai, user, complaint_id, scenario=data.scenario, body=data.body
    )


@router.post(
    "/complaints/{complaint_id}/simulation/advance",
    response_model=AdvanceResult,
    dependencies=simulation_dependencies,
)
def advance(complaint_id: uuid.UUID, user: CurrentUser, db: DbSession, ai: AI, email: Email):
    ran = service.advance_to_next_check(
        db, ai=ai, email=email, user=user, complaint_id=complaint_id
    )
    return AdvanceResult(ran=[ScheduledActionRead.model_validate(a) for a in ran])
