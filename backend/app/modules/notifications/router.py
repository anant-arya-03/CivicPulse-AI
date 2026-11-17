import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.database import DbSession
from app.modules.auth.dependencies import CurrentUser
from app.modules.notifications import service
from app.modules.notifications.schemas import NotificationFeed

router = APIRouter(prefix="/notifications", tags=["notifications"])


class MarkSeen(BaseModel):
    through_id: uuid.UUID


@router.get("", response_model=NotificationFeed)
def notifications(user: CurrentUser, db: DbSession):
    return service.list_notifications(db, user)


@router.post("/mark-seen", status_code=204)
def mark_seen(data: MarkSeen, user: CurrentUser, db: DbSession):
    service.mark_seen(db, user, data.through_id)
