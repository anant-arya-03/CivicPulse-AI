import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.database import DbSession
from app.modules.auth.dependencies import CurrentUser
from app.modules.authorities import service
from app.modules.authorities.schemas import (
    AuthorityMatchesResponse,
    AuthorityMatchRead,
    AuthorityRead,
    SelectAuthorityRequest,
)
from app.modules.complaints import service as complaint_service
from app.modules.complaints.constants import Category
from app.modules.complaints.schemas import ComplaintRead

router = APIRouter(tags=["authorities"])


@router.get("/authorities", response_model=list[AuthorityRead])
def list_authorities(
    _: CurrentUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    category: Category | None = None,
    city: Annotated[str | None, Query(max_length=120)] = None,
):
    return service.list_authorities(db, q=q, category=category, city=city)


@router.get("/authorities/{authority_id}", response_model=AuthorityRead)
def get_authority(authority_id: uuid.UUID, _: CurrentUser, db: DbSession):
    return service.get_authority(db, authority_id)


@router.get("/complaints/{complaint_id}/authority-matches", response_model=AuthorityMatchesResponse)
def authority_matches(complaint_id: uuid.UUID, user: CurrentUser, db: DbSession):
    complaint, result = service.matches_for_complaint(db, user, complaint_id)
    return AuthorityMatchesResponse(
        confidence=result.confidence,
        matches=[
            AuthorityMatchRead(
                authority=AuthorityRead.model_validate(m.authority),
                score=m.score,
                reasons=m.reasons,
            )
            for m in result.matches
        ],
        selected_authority_id=complaint.authority_id,
    )


@router.put("/complaints/{complaint_id}/authority", response_model=ComplaintRead)
def select_authority(
    complaint_id: uuid.UUID, data: SelectAuthorityRequest, user: CurrentUser, db: DbSession
):
    complaint = service.select_authority(db, user, complaint_id, data.authority_id)
    return complaint_service.to_read(complaint)
