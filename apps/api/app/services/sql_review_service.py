from __future__ import annotations

from dataclasses import dataclass, field
import re

import sqlglot
from sqlglot import exp

from sqlalchemy.orm import Session

from app.schemas.query import QueryPlan


@dataclass
class SQLReviewResult:
    allowed: bool
    needs_clarification: bool = False
    blocked_reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class SQLReviewService:
    """Final semantic sanity-check before hard SQL guardrails."""

    def __init__(self, db: Session):
        self.db = db

    def review(self, *, question: str, query_plan: QueryPlan, sql_text: str, params: dict) -> SQLReviewResult:
        normalized_question = self._normalize_text(question)
        blocked_reasons: list[str] = []
        notes: list[str] = []

        try:
            parsed = sqlglot.parse_one(sql_text, read="postgres")
        except sqlglot.errors.ParseError:
            return SQLReviewResult(
                allowed=False,
                needs_clarification=True,
                blocked_reasons=["SQL не прошёл финальную проверку синтаксиса после построения."],
                notes=[],
            )

        projection_aliases = self._collect_projection_aliases(parsed)
        required_aliases = {metric.key for metric in query_plan.metrics} | {dimension.key for dimension in query_plan.dimensions}
        missing_aliases = sorted(alias for alias in required_aliases if alias not in projection_aliases)
        if missing_aliases:
            blocked_reasons.append(
                f"В финальном SQL отсутствуют ожидаемые поля из плана: {', '.join(missing_aliases)}."
            )

        if query_plan.dimensions and not parsed.find(exp.Group):
            blocked_reasons.append("Вопрос требует разбивку по измерениям, но GROUP BY не найден.")

        if self._question_mentions_entity(normalized_question, "user") and "user_id" not in {
            dimension.key for dimension in query_plan.dimensions
        }:
            blocked_reasons.append("В вопросе есть сущность пользователя, но нет обязательного GROUP BY user_id.")

        if self._question_mentions_entity(normalized_question, "city") and "city_id" not in {
            dimension.key for dimension in query_plan.dimensions
        }:
            blocked_reasons.append("В вопросе есть сущность города, но нет обязательного GROUP BY city_id.")

        if query_plan.comparison.enabled and "union all" not in sql_text.lower():
            blocked_reasons.append("Сравнительный запрос должен содержать объединение периодов через UNION ALL.")

        if query_plan.sort and "order by" not in sql_text.lower():
            blocked_reasons.append("В плане указан порядок сортировки, но ORDER BY не найден в SQL.")

        if query_plan.multi_date and query_plan.multi_date.dates:
            multi_date_params = [name for name in params if name.startswith("multi_date_")]
            if not multi_date_params:
                blocked_reasons.append("В плане есть несколько дат, но SQL не получил параметры multi_date_*.")

        # Ignore PostgreSQL casts like "::numeric" and capture only bind params like ":start_date".
        sql_placeholders = set(re.findall(r"(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)", sql_text))
        missing_params = sorted(name for name in sql_placeholders if name not in params)
        if missing_params:
            blocked_reasons.append(f"Для SQL не переданы обязательные параметры: {', '.join(missing_params)}.")

        extra_params = sorted(name for name in params if name not in sql_placeholders)
        if extra_params:
            notes.append(f"Переданы неиспользуемые параметры: {', '.join(extra_params)}.")

        missing_time_params = self._missing_time_params(query_plan, params)
        if missing_time_params:
            blocked_reasons.append(
                f"Не хватает параметров периода для выполнения запроса: {', '.join(missing_time_params)}."
            )

        metric_kind_reason = self._validate_metric_kind_alignment(normalized_question, query_plan)
        if metric_kind_reason:
            blocked_reasons.append(metric_kind_reason)

        duration_filter_reason = self._validate_duration_filter_alignment(normalized_question, sql_text)
        if duration_filter_reason:
            blocked_reasons.append(duration_filter_reason)

        explicit_date_reason = self._validate_explicit_date_priority(normalized_question, sql_text)
        if explicit_date_reason:
            blocked_reasons.append(explicit_date_reason)

        comparison_shape_reason = self._validate_comparison_shape(query_plan, sql_text)
        if comparison_shape_reason:
            blocked_reasons.append(comparison_shape_reason)

        limit_note = self._validate_limit_alignment(parsed, query_plan.limit)
        if limit_note:
            notes.append(limit_note)

        if query_plan.needs_clarification and not blocked_reasons:
            notes.append("План помечен как требующий уточнения, но SQL успешно прошёл формальную сверку.")

        return SQLReviewResult(
            allowed=not blocked_reasons,
            needs_clarification=bool(blocked_reasons),
            blocked_reasons=blocked_reasons,
            notes=notes,
        )

    def _collect_projection_aliases(self, parsed: exp.Expression) -> set[str]:
        aliases: set[str] = set()
        for select in parsed.find_all(exp.Select):
            for projection in select.expressions:
                if isinstance(projection, exp.Alias):
                    aliases.add(projection.alias_or_name)
                else:
                    # Non-aliased projections are still detectable by their SQL text.
                    aliases.add(projection.alias_or_name or projection.sql())
        return aliases

    def _missing_time_params(self, query_plan: QueryPlan, params: dict) -> list[str]:
        if query_plan.comparison.enabled:
            if query_plan.comparison.mode == "year_over_year":
                required = {"current_year", "previous_year"}
                return sorted(name for name in required if name not in params)
            if query_plan.multi_date and len(query_plan.multi_date.dates) >= 2:
                required = {"multi_date_0", "multi_date_1"}
            else:
                required = {"current_start", "current_end", "previous_start", "previous_end"}
        else:
            required = {"start_date", "end_date"}
        return sorted(name for name in required if name not in params)

    def _validate_limit_alignment(self, parsed: exp.Expression, expected_limit: int) -> str | None:
        limit_expr = parsed.find(exp.Limit)
        if not limit_expr:
            return None

        value_expr = limit_expr.expression
        if isinstance(value_expr, exp.Literal) and value_expr.is_int:
            sql_limit = int(value_expr.this)
            if sql_limit > expected_limit:
                return f"Лимит в SQL ({sql_limit}) выше лимита из плана ({expected_limit})."
            if sql_limit < expected_limit:
                return f"Лимит в SQL ({sql_limit}) ниже лимита из плана ({expected_limit})."

        return None

    def _validate_metric_kind_alignment(self, question: str, query_plan: QueryPlan) -> str | None:
        requested_kind = self._requested_metric_kind(question)
        if not requested_kind or not query_plan.metrics:
            return None

        metric_kinds = {self._metric_kind(metric.expression) for metric in query_plan.metrics}
        metric_kinds.discard(None)
        if requested_kind not in metric_kinds:
            return f"Тип метрики не соответствует формулировке запроса ({requested_kind})."
        return None

    def _validate_duration_filter_alignment(self, question: str, sql_text: str) -> str | None:
        if "длител" not in question:
            return None
        has_condition_phrase = any(
            token in question for token in ["больше", "выше", "не менее", "минимум", "меньше", "ниже", "не более", "максимум"]
        )
        if not has_condition_phrase:
            return None
        if "duration_in_seconds" not in sql_text:
            return "Вопрос содержит фильтр по длительности, но SQL не содержит соответствующего условия WHERE."
        return None

    def _requested_metric_kind(self, question: str) -> str | None:
        if "средн" in question or "в среднем" in question:
            return "avg"
        if "сумм" in question or "выручк" in question:
            return "sum"
        if "сколько" in question:
            return "count"
        return None

    def _metric_kind(self, expression: str) -> str | None:
        upper = expression.upper()
        if "COUNT(" in upper:
            return "count"
        if "AVG(" in upper:
            return "avg"
        if "SUM(" in upper:
            return "sum"
        return None

    def _question_mentions_entity(self, question: str, entity: str) -> bool:
        if entity == "user":
            return any(token in question for token in ["пользователь", "пользовател", "user"])
        if entity == "city":
            return any(token in question for token in ["город", "городам", "городу", "city"])
        return False

    def _normalize_text(self, value: str) -> str:
        return value.lower().replace("ё", "е")

    def _validate_explicit_date_priority(self, question: str, sql_text: str) -> str | None:
        has_explicit_date = bool(
            re.search(r"\d{1,2}\s+[а-я]+(?:\s+\d{4})?|\d{1,2}\.\d{1,2}(?:\.\d{2,4})?", question)
        )
        if not has_explicit_date:
            return None
        lowered_sql = sql_text.lower()
        if "current_date" in lowered_sql or "now()" in lowered_sql or " interval " in lowered_sql:
            return "При явных датах запрещено использовать default-периоды (NOW/CURRENT_DATE/INTERVAL)."
        return None

    def _validate_comparison_shape(self, query_plan: QueryPlan, sql_text: str) -> str | None:
        if not query_plan.comparison.enabled:
            return None
        if query_plan.dimensions:
            return None
        if "period_label" in sql_text.lower():
            return None
        return "Сравнительный запрос должен возвращать несколько групп (по периоду или категории), а не одно число."
