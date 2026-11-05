"""Import every ORM model here so SQLAlchemy's metadata (and Alembic autogenerate) can see them.

When you add a new `models.py` in a module, add one import line below.
"""

from app.core.database import Base
from app.modules.ai.models import AIAnalysis
from app.modules.auth.models import UserSession
from app.modules.authorities.models import Authority
from app.modules.communications.models import Communication
from app.modules.complaints.models import Complaint, ComplaintEvent
from app.modules.evidence.models import Evidence
from app.modules.monitoring.models import ScheduledAction
from app.modules.resolutions.models import ResolutionReview
from app.modules.users.models import User

__all__ = [
    "AIAnalysis",
    "Authority",
    "Base",
    "Communication",
    "Complaint",
    "ComplaintEvent",
    "Evidence",
    "ResolutionReview",
    "ScheduledAction",
    "User",
    "UserSession",
]
