from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.repositories.users import UserRepository


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def authenticate(self, email: str, password: str) -> tuple[User, str]:
        user = self.users.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
            )
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь деактивирован")

        token = create_access_token(user.id, user.role.value)
        return user, token

    def register(self, email: str, password: str, full_name: str) -> tuple[User, str]:
        if not settings.allow_self_registration:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Самостоятельная регистрация отключена. Обратитесь к администратору.",
            )

        if self.users.get_by_email(email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пользователь с таким email уже существует")

        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role=UserRole.business_user,
            is_active=True,
        )
        saved = self.users.save(user)
        token = create_access_token(saved.id, saved.role.value)
        return saved, token

    def update_profile(self, user: User, *, full_name: str, timezone: str, locale: str) -> User:
        user.full_name = full_name.strip()
        user.timezone = timezone.strip()
        user.locale = locale.strip()
        return self.users.save(user)

    def change_password(self, user: User, *, current_password: str, new_password: str) -> User:
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Текущий пароль указан неверно")
        user.password_hash = hash_password(new_password)
        return self.users.save(user)
