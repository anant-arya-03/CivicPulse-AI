import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.common.pagination import Page
from app.core.database import DbSession
from app.modules.auth.dependencies import CurrentUser
from app.modules.complaints import service
from app.modules.complaints.schemas import (
    ComplaintCreate,
    ComplaintEventRead,
    ComplaintListItem,
    ComplaintListParams,
    ComplaintRead,
    ComplaintUpdate,
    DashboardSummary,
)

router = APIRouter(prefix="/complaints", tags=["complaints"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.post("", response_model=ComplaintRead, status_code=status.HTTP_201_CREATED)
def create_complaint(user: CurrentUser, db: DbSession, data: ComplaintCreate | None = None):
    complaint = service.create_complaint(db, user, data or ComplaintCreate())
    return service.to_read(complaint)


@router.get("", response_model=Page[ComplaintListItem])
def list_complaints(
    user: CurrentUser, db: DbSession, params: Annotated[ComplaintListParams, Query()]
):
    complaints, total = service.list_complaints(db, user, params)
    return Page[ComplaintListItem](
        items=[service.to_list_item(c) for c in complaints],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


@router.get("/{complaint_id}", response_model=ComplaintRead)
def get_complaint(complaint_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return service.to_read(service.get_owned_complaint(db, user, complaint_id))


@router.patch("/{complaint_id}", response_model=ComplaintRead)
def update_complaint(
    complaint_id: uuid.UUID, data: ComplaintUpdate, user: CurrentUser, db: DbSession
):
    complaint = service.get_owned_complaint(db, user, complaint_id)
    return service.to_read(service.update_complaint(db, user, complaint, data))


@router.post("/{complaint_id}/cancel", response_model=ComplaintRead)
def cancel_complaint(complaint_id: uuid.UUID, user: CurrentUser, db: DbSession):
    complaint = service.get_owned_complaint(db, user, complaint_id)
    return service.to_read(service.cancel_complaint(db, user, complaint))


@router.post("/{complaint_id}/close", response_model=ComplaintRead)
def close_complaint(complaint_id: uuid.UUID, user: CurrentUser, db: DbSession):
    complaint = service.get_owned_complaint(db, user, complaint_id)
    return service.to_read(service.close_complaint(db, user, complaint))


@router.get("/{complaint_id}/timeline", response_model=list[ComplaintEventRead])
def get_timeline(complaint_id: uuid.UUID, user: CurrentUser, db: DbSession):
    complaint = service.get_owned_complaint(db, user, complaint_id)
    return service.get_timeline(db, complaint)


@dashboard_router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(user: CurrentUser, db: DbSession):
    return service.dashboard_summary(db, user)
