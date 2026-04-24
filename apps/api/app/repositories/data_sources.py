from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.data_source import DataSource


class DataSourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> list[DataSource]:
        return self.db.query(DataSource).order_by(DataSource.is_default.desc(), DataSource.created_at.asc()).all()

    def list_active(self) -> list[DataSource]:
        return self.db.query(DataSource).filter(DataSource.is_active.is_(True)).order_by(DataSource.is_default.desc(), DataSource.created_at.asc()).all()

    def get_by_id(self, source_id: str | UUID) -> DataSource | None:
        return self.db.query(DataSource).filter(DataSource.id == source_id).one_or_none()

    def get_by_key(self, key: str) -> DataSource | None:
        return self.db.query(DataSource).filter(DataSource.key == key).one_or_none()

    def clear_default_flag(self) -> None:
        self.db.query(DataSource).filter(DataSource.is_default.is_(True)).update({"is_default": False})
        self.db.flush()

    def save(self, source: DataSource) -> DataSource:
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source
