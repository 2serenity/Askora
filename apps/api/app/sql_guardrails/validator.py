from __future__ import annotations

import sqlglot
from sqlglot import exp

from app.core.config import settings
from app.schemas.query import ValidationResult
from app.semantic_layer.loader import semantic_loader
from app.sql_guardrails.estimator import complexity_estimator


class SQLGuardrailsValidator:
    def __init__(self) -> None:
        self.catalog = semantic_loader.load_catalog()

    def validate(self, sql: str, row_limit: int, dataset_key: str, *, dialect: str = "postgres") -> ValidationResult:
        warnings: list[str] = []
        blocked_reasons: list[str] = []
        dataset = self.catalog.datasets[dataset_key]
        allowed_tables = {dataset.table, "unioned"}
        allowed_aliases = {dataset.alias, "unioned"}

        for join_key in dataset.joins:
            join = self.catalog.joins[join_key]
            allowed_tables.add(join.table)
            allowed_aliases.add(join.alias)

        try:
            parsed = sqlglot.parse_one(sql, read=dialect)
        except sqlglot.errors.ParseError as exc:
            return ValidationResult(
                allowed=False,
                normalized_sql=sql,
                complexity_score=0,
                row_limit_applied=min(row_limit, settings.max_result_rows),
                warnings=[],
                blocked_reasons=[f"SQL не прошёл синтаксическую валидацию: {exc}"],
            )

        if not parsed.find(exp.Select):
            blocked_reasons.append("Разрешены только SELECT-запросы.")
        if parsed.find(exp.Join):
            blocked_reasons.append("JOIN запрещён политикой безопасности.")

        for node in parsed.walk():
            if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.TruncateTable)):
                blocked_reasons.append("Обнаружена опасная DDL/DML-конструкция.")
            if isinstance(node, exp.Table):
                table_name = f"{node.db}.{node.name}" if node.db else node.name
                if table_name not in allowed_tables:
                    blocked_reasons.append(f"Таблица {table_name} не входит в whitelist.")
            if isinstance(node, exp.Column) and node.table and node.table not in allowed_aliases:
                blocked_reasons.append(f"Алиас {node.table} не разрешён.")

        if parsed.find(exp.Star):
            blocked_reasons.append("Запрещён SELECT *.")

        normalized = parsed.sql(dialect=dialect)
        normalized_lower = normalized.lower()
        complexity = complexity_estimator.estimate(normalized)

        if complexity > settings.max_sql_complexity:
            blocked_reasons.append("Запрос слишком сложный для безопасного выполнения в текущем контуре.")
        if "information_schema" in normalized_lower or " pg_" in f" {normalized_lower}":
            blocked_reasons.append("Системные таблицы недоступны.")
        if not parsed.find(exp.Where):
            blocked_reasons.append("Запрос должен быть ограничен по периоду или фильтру.")
        if not parsed.find(exp.Limit):
            blocked_reasons.append("Запрос должен содержать LIMIT.")
        if dataset.default_time_field.lower() not in normalized_lower:
            warnings.append("Запрос не использует стандартное ограничение по времени и может быть дорогим.")

        return ValidationResult(
            allowed=not blocked_reasons,
            normalized_sql=normalized,
            complexity_score=complexity,
            row_limit_applied=min(row_limit, settings.max_result_rows),
            warnings=warnings,
            blocked_reasons=list(dict.fromkeys(blocked_reasons)),
        )


sql_validator = SQLGuardrailsValidator()
