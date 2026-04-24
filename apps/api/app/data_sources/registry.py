from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.data_sources import DataSourceRepository
from app.semantic_layer.loader import semantic_loader


@dataclass(frozen=True)
class RuntimeDataSource:
    key: str
    name: str
    dialect: str
    connection_url: str
    schema_name: str | None = None
    is_active: bool = True
    is_default: bool = False
    allowed_roles: list[str] = field(default_factory=list)
    capabilities: dict = field(default_factory=dict)


class DataSourceRegistry:
    def __init__(self) -> None:
        self._engines: dict[str, Engine] = {}

    def list_sources(self, db: Session) -> list[RuntimeDataSource]:
        repo = DataSourceRepository(db)
        items = repo.list_all()
        if items:
            return [
                RuntimeDataSource(
                    key=item.key,
                    name=item.name,
                    dialect=item.dialect,
                    connection_url=item.connection_url,
                    schema_name=item.schema_name,
                    is_active=item.is_active,
                    is_default=item.is_default,
                    allowed_roles=item.allowed_roles_json or [],
                    capabilities=item.capabilities_json or {},
                )
                for item in items
            ]
        return [self.default_source()]

    def default_source(self) -> RuntimeDataSource:
        return RuntimeDataSource(
            key=settings.default_data_source_key,
            name="Основной PostgreSQL",
            dialect="postgres",
            connection_url=settings.database_url,
            is_active=True,
            is_default=True,
            allowed_roles=["admin", "analyst", "business_user"],
            capabilities={"scheduler": True, "guardrails": True},
        )

    def get_source(self, db: Session, *, key: str | None = None, dataset_key: str | None = None) -> RuntimeDataSource:
        requested_key = key
        if requested_key is None and dataset_key:
            catalog = semantic_loader.load_catalog()
            dataset = catalog.datasets[dataset_key]
            requested_key = dataset.source_key

        if requested_key is None:
            requested_key = settings.default_data_source_key

        for source in self.list_sources(db):
            if source.key == requested_key:
                return source

        return self.default_source()

    def get_engine(self, source: RuntimeDataSource) -> Engine:
        if source.connection_url not in self._engines:
            self._engines[source.connection_url] = create_engine(source.connection_url, future=True, pool_pre_ping=True)
        return self._engines[source.connection_url]

    def is_primary_source(self, source: RuntimeDataSource) -> bool:
        return source.connection_url == settings.database_url or source.key == settings.default_data_source_key

    def invalidate(self) -> None:
        for engine in self._engines.values():
            engine.dispose()
        self._engines = {}


data_source_registry = DataSourceRegistry()
