from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.modules.complaints.constants import ComplaintStatus

ReportUpdate = Literal["start_work", "repair_complete"]


class DepartmentReport(BaseModel):
    id: UUID
    reference: str
    status: ComplaintStatus
    subject: str
    body: str
    received_at: datetime | None
    attachment_ids: list[UUID]


class DepartmentInbox(BaseModel):
    department: str
    reports: list[DepartmentReport]


class DepartmentUpdateRequest(BaseModel):
    update: ReportUpdate
