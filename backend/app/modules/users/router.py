from fastapi import APIRouter

from app.core.database import DbSession
from app.modules.auth.dependencies import CurrentUser
from app.modules.users import service
from app.modules.users.schemas import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserRead)
def update_me(data: UserUpdate, user: CurrentUser, db: DbSession):
    return service.update_profile(db, user, data)
