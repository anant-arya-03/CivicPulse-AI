import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: uuid.UUID
    complaint_id: uuid.UUID
    description: str
    created_at: datetime
    unread: bool


class NotificationFeed(BaseModel):
    unread_count: int
    items: list[NotificationRead]
