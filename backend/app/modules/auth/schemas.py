from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.users.schemas import UserRead, clean_name

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, value: object) -> object:
        return clean_name(value) if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        # Keep this rule identical to the frontend Zod schema (features/authentication/schemas.ts).
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one letter and one number.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class AuthResponse(BaseModel):
    user: UserRead
