from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).one_or_none()

    def get_by_id(self, user_id: str | UUID) -> User | None:
        return self.db.query(User).filter(User.id == user_id).one_or_none()

    def list_all(self) -> list[User]:
        return self.db.query(User).order_by(User.created_at.desc()).all()

    def list_active(self) -> list[User]:
        return self.db.query(User).filter(User.is_active.is_(True)).order_by(User.full_name.asc()).all()

    def save(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
