from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import DbSession
from app.core.rate_limit import RateLimit
from app.integrations.storage.base import StorageService
from app.integrations.storage.factory import get_storage
from app.modules.authorities.models import Authority
from app.modules.department_portal import service
from app.modules.department_portal.schemas import (
    DepartmentInbox,
    DepartmentReport,
    DepartmentUpdateRequest,
)
from app.modules.evidence.service import read_evidence_file

router = APIRouter(prefix="/department", tags=["department portal"])
AccessCode = Annotated[HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))]


def get_department(db: DbSession, credentials: AccessCode) -> Authority:
    return service.authenticate(db, credentials.credentials if credentials else None)


Department = Annotated[Authority, Depends(get_department)]
Storage = Annotated[StorageService, Depends(get_storage)]


@router.get("/reports", dependencies=[Depends(RateLimit("department-inbox", times=60, seconds=60))])
def inbox(db: DbSession, department: Department) -> DepartmentInbox:
    return DepartmentInbox(department=department.name, reports=service.list_reports(db, department))


@router.get(
    "/reports/{complaint_id}/attachments/{evidence_id}",
    dependencies=[Depends(RateLimit("department-attachments", times=60, seconds=60))],
)
def attachment(
    complaint_id: UUID, evidence_id: UUID, db: DbSession, department: Department, storage: Storage
) -> Response:
    evidence = service.get_attachment(db, department, complaint_id, evidence_id)
    return Response(read_evidence_file(storage, evidence), media_type=evidence.file_type)


@router.post(
    "/reports/{complaint_id}/status",
    dependencies=[Depends(RateLimit("department-update", times=20, seconds=60))],
)
def update_status(
    complaint_id: UUID, data: DepartmentUpdateRequest, db: DbSession, department: Department
) -> DepartmentReport:
    return service.update_report(db, department, complaint_id, data.update)
