from pydantic import BaseModel, Field, field_validator

from app.schemas.common import UserSummary


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)

    @field_validator("email")
    @classmethod
    def validate_login_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Введите корректный email для входа")
        return normalized


class RegisterRequest(LoginRequest):
    full_name: str = Field(min_length=3, max_length=255)


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    timezone: str = Field(min_length=2, max_length=64)
    locale: str = Field(min_length=2, max_length=16, default="ru-RU")


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=6)
    new_password: str = Field(min_length=8, max_length=128)


class AuthResponse(BaseModel):
    user: UserSummary
