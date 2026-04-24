from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.data_source import DataSource
from app.models.semantic import ApprovedQueryTemplate, SemanticDictionaryEntry
from app.models.user import User, UserRole
from app.repositories.data_sources import DataSourceRepository
from app.repositories.semantic import SemanticRepository
from app.repositories.users import UserRepository
from app.schemas.admin import CreateUserRequest, DataSourceRequest, SemanticEntryRequest, TemplateRequest


class AdminService:
    def __init__(self, db: Session):
        self.db = db
        self.semantic = SemanticRepository(db)
        self.users = UserRepository(db)
        self.data_sources = DataSourceRepository(db)

    def list_users(self) -> list[User]:
        return self.users.list_all()

    def create_user(self, payload: CreateUserRequest) -> User:
        if self.users.get_by_email(payload.email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пользователь с таким email уже существует")

        user = User(
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
            role=UserRole(payload.role),
            is_active=payload.is_active,
        )
        return self.users.save(user)

    def update_user_role(self, user: User, role: str) -> User:
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
        user.role = UserRole(role)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user_status(self, user: User, is_active: bool) -> User:
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
        user.is_active = is_active
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def list_semantic_entries(self):
        return self.semantic.list_entries()

    def create_semantic_entry(self, payload: SemanticEntryRequest) -> SemanticDictionaryEntry:
        entry = SemanticDictionaryEntry(**payload.model_dump())
        return self.semantic.create_entry(entry)

    def list_templates(self):
        return self.semantic.list_templates()

    def create_template(self, payload: TemplateRequest) -> ApprovedQueryTemplate:
        template = ApprovedQueryTemplate(**payload.model_dump(), owner_role=UserRole(payload.owner_role))
        return self.semantic.create_template(template)

    def list_data_sources(self):
        return self.data_sources.list_all()

    def create_data_source(self, payload: DataSourceRequest) -> DataSource:
        if self.data_sources.get_by_key(payload.key):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Источник данных с таким ключом уже существует")
        if payload.is_default:
            self.data_sources.clear_default_flag()
        source = DataSource(**payload.model_dump())
        return self.data_sources.save(source)

    def update_data_source(self, source: DataSource, payload: DataSourceRequest) -> DataSource:
        if source is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Источник данных не найден")
        if payload.is_default:
            self.data_sources.clear_default_flag()
        for field, value in payload.model_dump().items():
            setattr(source, field, value)
        return self.data_sources.save(source)
