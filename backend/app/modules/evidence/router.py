import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, UploadFile, status

from app.core.config import get_settings
from app.core.database import DbSession
from app.core.rate_limit import RateLimit
from app.integrations.storage.base import StorageService
from app.integrations.storage.factory import get_storage
from app.modules.auth.dependencies import CurrentUser
from app.modules.evidence import service
from app.modules.evidence.schemas import EvidenceRead

router = APIRouter(tags=["evidence"])

Storage = Annotated[StorageService, Depends(get_storage)]


@router.post(
    "/complaints/{complaint_id}/evidence",
    response_model=EvidenceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimit("upload", times=20, seconds=60))],
)
def upload_evidence(
    complaint_id: uuid.UUID, file: UploadFile, user: CurrentUser, db: DbSession, storage: Storage
):
    # Read one byte more than allowed, so an oversized file is detected without reading all of it.
    raw = file.file.read(get_settings().max_upload_bytes + 1)
    return service.upload_evidence(db, storage, user, complaint_id, raw)


@router.post(
    "/complaints/{complaint_id}/followup-evidence",
    response_model=EvidenceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimit("upload", times=20, seconds=60))],
)
def upload_followup_evidence(
    complaint_id: uuid.UUID, file: UploadFile, user: CurrentUser, db: DbSession, storage: Storage
):
    """An "after" photo for checking a repair (multipart field `file`)."""
    raw = file.file.read(get_settings().max_upload_bytes + 1)
    return service.upload_followup_evidence(db, storage, user, complaint_id, raw)


@router.get("/evidence/{evidence_id}/file")
def get_evidence_file(evidence_id: uuid.UUID, user: CurrentUser, db: DbSession, storage: Storage):
    evidence = service.get_owned_evidence(db, user, evidence_id)
    content = service.read_evidence_file(storage, evidence)
    return Response(
        content=content,
        media_type=evidence.file_type,
        headers={
            # Private: browsers may cache it, shared caches (proxies/CDNs) must not.
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


@router.delete("/evidence/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence(evidence_id: uuid.UUID, user: CurrentUser, db: DbSession, storage: Storage):
    service.delete_evidence(db, storage, user, evidence_id)
