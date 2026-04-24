from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, PasswordChangeRequest, ProfileUpdateRequest, RegisterRequest
from app.schemas.common import MessageResponse, UserSummary
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService

router = APIRouter()


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    user, token = AuthService(db).authenticate(payload.email, payload.password)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.access_token_ttl_seconds,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return AuthResponse(user=UserSummary.model_validate(user, from_attributes=True))


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    user, token = AuthService(db).register(payload.email, payload.password, payload.full_name)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.access_token_ttl_seconds,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return AuthResponse(user=UserSummary.model_validate(user, from_attributes=True))


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response) -> MessageResponse:
    response.delete_cookie("access_token")
    return MessageResponse(message="Вы вышли из системы")


@router.get("/me", response_model=AuthResponse)
def me(user: User = Depends(get_current_user)) -> AuthResponse:
    return AuthResponse(user=UserSummary.model_validate(user, from_attributes=True))


@router.put("/me", response_model=AuthResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AuthResponse:
    updated = AuthService(db).update_profile(
        user,
        full_name=payload.full_name,
        timezone=payload.timezone,
        locale=payload.locale,
    )
    AuditService(db).log(
        actor_user_id=user.id,
        event_type="profile_updated",
        status="success",
        extra_json={"timezone": payload.timezone, "locale": payload.locale},
    )
    return AuthResponse(user=UserSummary.model_validate(updated, from_attributes=True))


@router.put("/me/password", response_model=MessageResponse)
def change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessageResponse:
    AuthService(db).change_password(user, current_password=payload.current_password, new_password=payload.new_password)
    AuditService(db).log(actor_user_id=user.id, event_type="password_changed", status="success")
    return MessageResponse(message="Пароль обновлён")
