from fastapi import APIRouter, Depends

from app.core.database import DbSession
from app.core.rate_limit import RateLimit
from app.modules.auth.dependencies import CurrentUser
from app.modules.users import service
from app.modules.users.schemas import PasswordChange, SettingsUpdate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserRead)
def update_me(data: UserUpdate, user: CurrentUser, db: DbSession):
    return service.update_profile(db, user, data)


@router.put("/me/settings", response_model=UserRead)
def settings(data: SettingsUpdate, user: CurrentUser, db: DbSession):
    return service.update_settings(db, user, data)


@router.post(
    "/me/password",
    status_code=204,
    dependencies=[Depends(RateLimit("password", times=5, seconds=60))],
)
def password(data: PasswordChange, user: CurrentUser, db: DbSession):
    service.change_password(db, user, data)
