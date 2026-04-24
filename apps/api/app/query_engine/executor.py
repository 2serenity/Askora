from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.data_sources.adapters import adapter_registry
from app.data_sources.registry import data_source_registry


class QueryExecutor:
    def explain(
        self,
        db: Session,
        sql: str,
        params: dict,
        *,
        dataset_key: str,
    ) -> dict | None:
        source = data_source_registry.get_source(db, dataset_key=dataset_key)
        adapter = adapter_registry.get(source.dialect)

        # Portable fallback: only PostgreSQL adapter supports JSON explain here.
        if adapter.dialect not in {"postgres", "postgresql"}:
            return None

        explain_sql = f"EXPLAIN (FORMAT JSON) {sql}"
        if data_source_registry.is_primary_source(source):
            adapter.apply_session_settings(db)
            row = db.execute(text(explain_sql), params).first()
        else:
            engine = data_source_registry.get_engine(source)
            with engine.begin() as connection:
                adapter.apply_connection_settings(connection)
                row = connection.execute(text(explain_sql), params).first()

        if not row:
            return None
        plan_payload = row[0]
        if isinstance(plan_payload, list) and plan_payload:
            root = plan_payload[0]
            if isinstance(root, dict):
                return root
        if isinstance(plan_payload, dict):
            return plan_payload
        return None

    def execute(
        self,
        db: Session,
        sql: str,
        params: dict,
        *,
        dataset_key: str,
    ) -> tuple[list[str], list[dict], int]:
        source = data_source_registry.get_source(db, dataset_key=dataset_key)
        adapter = adapter_registry.get(source.dialect)

        if data_source_registry.is_primary_source(source):
            adapter.apply_session_settings(db)
            result = db.execute(text(sql), params)
        else:
            engine = data_source_registry.get_engine(source)
            with engine.begin() as connection:
                adapter.apply_connection_settings(connection)
                result = connection.execute(text(sql), params)

        rows = [dict(row._mapping) for row in result]
        columns = list(rows[0].keys()) if rows else []
        return columns, rows, len(rows)


query_executor = QueryExecutor()
