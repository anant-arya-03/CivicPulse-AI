import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evidence_type: str
    file_type: str
    file_size_bytes: int
    width: int | None
    height: int | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        """Where the frontend loads the image from (requires the owner's session)."""
        return f"/api/v1/evidence/{self.id}/file"
