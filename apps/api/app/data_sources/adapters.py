from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.config import settings


@dataclass(frozen=True)
class SQLAdapter:
    dialect: str
    sqlglot_dialect: str

    def apply_session_settings(self, db: Session) -> None:
        return None

    def apply_connection_settings(self, connection: Connection) -> None:
        return None


class PostgresAdapter(SQLAdapter):
    def __init__(self) -> None:
        super().__init__(dialect="postgres", sqlglot_dialect="postgres")

    def apply_session_settings(self, db: Session) -> None:
        db.execute(text(f"SET LOCAL statement_timeout = {settings.query_timeout_ms}"))

    def apply_connection_settings(self, connection: Connection) -> None:
        connection.execute(text(f"SET statement_timeout = {settings.query_timeout_ms}"))


class MySQLAdapter(SQLAdapter):
    def __init__(self) -> None:
        super().__init__(dialect="mysql", sqlglot_dialect="mysql")


class SQLiteAdapter(SQLAdapter):
    def __init__(self) -> None:
        super().__init__(dialect="sqlite", sqlglot_dialect="sqlite")


class ClickHouseAdapter(SQLAdapter):
    def __init__(self) -> None:
        super().__init__(dialect="clickhouse", sqlglot_dialect="clickhouse")


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters = {
            "postgres": PostgresAdapter(),
            "postgresql": PostgresAdapter(),
            "mysql": MySQLAdapter(),
            "sqlite": SQLiteAdapter(),
            "clickhouse": ClickHouseAdapter(),
        }

    def get(self, dialect: str) -> SQLAdapter:
        return self._adapters.get(dialect, self._adapters["postgres"])


adapter_registry = AdapterRegistry()
