from fastapi import APIRouter, Depends, Request, Response, status

from app.core.config import get_settings
from app.core.database import DbSession
from app.core.rate_limit import RateLimit
from app.modules.auth import service
from app.modules.auth.cookies import clear_auth_cookies, set_auth_cookies
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.schemas import AuthResponse, LoginRequest, RegisterRequest
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimit("register", times=10, seconds=60))],
)
def register(data: RegisterRequest, request: Request, response: Response, db: DbSession):
    user = service.register_user(db, data)
    token = service.start_session(db, user, request.headers.get("user-agent"))
    set_auth_cookies(response, token)
    return AuthResponse(user=UserRead.model_validate(user))


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(RateLimit("login", times=10, seconds=60))],
)
def login(data: LoginRequest, request: Request, response: Response, db: DbSession):
    user = service.authenticate(db, data.email, data.password)
    token = service.start_session(db, user, request.headers.get("user-agent"))
    set_auth_cookies(response, token)
    return AuthResponse(user=UserRead.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbSession) -> None:
    token = request.cookies.get(get_settings().session_cookie_name)
    if token:
        service.end_session(db, token)
    clear_auth_cookies(response)


@router.get("/me", response_model=AuthResponse)
def me(user: CurrentUser, request: Request, response: Response):
    # Re-issue the cookies so the CSRF cookie is always present for a logged-in user.
    token = request.cookies[get_settings().session_cookie_name]
    set_auth_cookies(response, token)
    return AuthResponse(user=UserRead.model_validate(user))
