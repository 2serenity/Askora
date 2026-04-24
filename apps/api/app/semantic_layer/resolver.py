from __future__ import annotations

from collections import defaultdict
import calendar
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.ai.percent_change import is_percent_change_request
from app.models.semantic import SemanticDictionaryEntry
from app.schemas.query import (
    ComparisonSpec,
    MultiDateSpec,
    QueryIntent,
    QueryPlan,
    ResolvedDimension,
    ResolvedFilter,
    ResolvedMetric,
    TimeRange,
)
from app.semantic_layer.loader import semantic_loader
from app.semantic_layer.time_context import SemanticTimeContext


class SemanticResolver:
    def __init__(self, db: Session):
        self.db = db
        self.catalog = semantic_loader.load_catalog()
        self.time_context = SemanticTimeContext(db)

    def resolve(self, intent: QueryIntent, user_role: str, *, anchor_date: date | None = None) -> QueryPlan:
        metrics = self._resolve_metrics(intent.metrics, user_role)
        dimensions = self._resolve_dimensions(intent.dimensions, user_role)
        filters = self._resolve_filters(intent.filters)
        time_range = intent.time_range_override or self._resolve_time_range(intent.time_expression, anchor_date=anchor_date)

        warnings = self._dedupe(list(intent.notes))
        clarification_questions = self._dedupe(list(intent.clarification_questions))
        needs_clarification = False

        if not metrics and not intent.ambiguity_reasons:
            fallback_metric = self.catalog.business_terms.get("заказы", {}).get("target_key", "total_orders")
            metric = self.catalog.metrics[fallback_metric]
            metrics = [
                ResolvedMetric(
                    key=metric.key,
                    label=metric.label,
                    description=metric.description,
                    expression=metric.sql,
                )
            ]
            warnings = self._dedupe(
                warnings + ["Метрика не была распознана явно, поэтому использована безопасная метрика по умолчанию: заказы."]
            )

        if not dimensions and intent.intent_type == "trend":
            day_key = "order_date" if "order_date" in self.catalog.dimensions else self._first_time_dimension_key()
            if day_key:
                day_dimension = self.catalog.dimensions[day_key]
                dimensions = [
                    ResolvedDimension(
                        key=day_dimension.key,
                        label=day_dimension.label,
                        expression=day_dimension.sql,
                        grain=day_dimension.grain,
                    )
                ]
                warnings = self._dedupe(
                    warnings + ["Явная группировка не указана, поэтому система построила динамику по дням заказа."]
                )

        # For multi-day windows users usually expect a day-by-day chart, not a single aggregate.
        if (
            not dimensions
            and not intent.comparison.enabled
            and not intent.multi_date
            and (time_range.end_date - time_range.start_date).days >= 1
            and "order_date" in self.catalog.dimensions
        ):
            day_dimension = self.catalog.dimensions["order_date"]
            dimensions = [
                ResolvedDimension(
                    key=day_dimension.key,
                    label=day_dimension.label,
                    expression=day_dimension.sql,
                    grain=day_dimension.grain,
                )
            ]
            warnings = self._dedupe(
                warnings + ["Период охватывает несколько дней, поэтому добавлена автоматическая разбивка по дням."]
            )

        if (
            dimensions
            and len(dimensions) == 1
            and dimensions[0].key != "order_date"
            and dimensions[0].key != "order_week"
            and dimensions[0].key != "order_month"
            and not intent.comparison.enabled
            and not intent.multi_date
            and (time_range.end_date - time_range.start_date).days >= 1
            and "order_date" in self.catalog.dimensions
        ):
            day_dimension = self.catalog.dimensions["order_date"]
            dimensions = [
                ResolvedDimension(
                    key=day_dimension.key,
                    label=day_dimension.label,
                    expression=day_dimension.sql,
                    grain=day_dimension.grain,
                ),
                *dimensions,
            ]
            warnings = self._dedupe(
                warnings
                + [
                    "Для многодневного периода добавлена разбивка по дням, чтобы график показывал динамику внутри выбранной категории.",
                ]
            )

        normalized_question = intent.question.lower().replace("ё", "е")
        explicit_month_grouping = any(
            token in normalized_question for token in ["по месяц", "помесяч", "помесячно", "месяцам", "за месяц"]
        )
        if (
            len(dimensions) == 1
            and dimensions[0].key == "order_month"
            and not explicit_month_grouping
            and (time_range.end_date - time_range.start_date).days <= 35
            and "order_date" in self.catalog.dimensions
        ):
            day_dimension = self.catalog.dimensions["order_date"]
            dimensions = [
                ResolvedDimension(
                    key=day_dimension.key,
                    label=day_dimension.label,
                    expression=day_dimension.sql,
                    grain=day_dimension.grain,
                )
            ]
            warnings = self._dedupe(
                warnings
                + [
                    "Разбивка по месяцам заменена на дневную, так как в запросе нет явного указания на помесячный график.",
                ]
            )

        if intent.comparison.enabled and intent.multi_date and intent.multi_date.dates:
            has_date_dimension = any(dimension.key == "order_date" for dimension in dimensions)
            if not has_date_dimension and "order_date" in self.catalog.dimensions:
                date_dimension = self.catalog.dimensions["order_date"]
                dimensions = [
                    *dimensions,
                    ResolvedDimension(
                        key=date_dimension.key,
                        label=date_dimension.label,
                        expression=date_dimension.sql,
                        grain=date_dimension.grain,
                    ),
                ]
                warnings = self._dedupe(
                    warnings + ["Для сравнения по явным датам добавлена обязательная группировка по order_date."]
                )

        dimensions, entity_notes = self._enforce_entity_grouping(intent.question, dimensions)
        if entity_notes:
            warnings = self._dedupe(warnings + entity_notes)

        metrics, metric_notes = self._enforce_metric_kind(intent.question, metrics, user_role)
        if metric_notes:
            warnings = self._dedupe(warnings + metric_notes)

        if intent.ambiguity_reasons:
            needs_clarification = True
            clarification_questions = self._dedupe(clarification_questions + intent.ambiguity_reasons)
            warnings = self._dedupe(warnings + intent.ambiguity_reasons)

        if self._is_percent_change_request(intent.question):
            metrics = self._adapt_metrics_for_percent_change(metrics)

        confidence = max(0.1, min(intent.confidence, 0.99))
        if needs_clarification:
            confidence = min(confidence, 0.59)

        return QueryPlan(
            question=intent.question,
            dataset=self.catalog.base_dataset,
            intent_type=intent.intent_type,
            metrics=metrics,
            dimensions=dimensions,
            filters=filters,
            time_range=time_range,
            multi_date=self._resolve_multi_date(intent.multi_date),
            comparison=intent.comparison or ComparisonSpec(),
            preferred_chart_type=intent.preferred_chart_type,
            sort=intent.sort,
            limit=min(intent.limit or 50, 200),
            confidence=confidence,
            warnings=warnings,
            needs_clarification=needs_clarification,
            clarification_questions=clarification_questions,
        )

    def _resolve_multi_date(self, multi_date: MultiDateSpec | None) -> MultiDateSpec | None:
        if not multi_date or not multi_date.dates:
            return None
        unique_dates: list[date] = []
        for item in sorted(multi_date.dates):
            if item not in unique_dates:
                unique_dates.append(item)
        if len(unique_dates) < 2:
            return None
        return MultiDateSpec(dates=unique_dates, mode=multi_date.mode)

    def _resolve_metrics(self, metric_keys: list[str], user_role: str) -> list[ResolvedMetric]:
        resolved: list[ResolvedMetric] = []
        for key in metric_keys:
            if key not in self.catalog.metrics:
                continue
            metric = self.catalog.metrics[key]
            if metric.allowed_roles and user_role not in metric.allowed_roles:
                continue
            resolved.append(
                ResolvedMetric(
                    key=metric.key,
                    label=metric.label,
                    description=metric.description,
                    expression=metric.sql,
                )
            )
        return resolved

    def _enforce_metric_kind(
        self,
        question: str,
        metrics: list[ResolvedMetric],
        user_role: str,
    ) -> tuple[list[ResolvedMetric], list[str]]:
        if len(metrics) > 1:
            return metrics, []

        requested_kind = self._detect_requested_metric_kind(question)
        if not requested_kind:
            return metrics, []

        matching = [metric for metric in metrics if self._metric_kind(metric.expression) == requested_kind]
        if matching:
            return matching, []

        fallback_key = self._default_metric_for_kind(question, requested_kind)
        if fallback_key:
            fallback_resolved = self._resolve_metrics([fallback_key], user_role)
            if fallback_resolved:
                return fallback_resolved, [f"Метрика скорректирована по типу запроса: {requested_kind}."]
        return metrics, []

    def _resolve_dimensions(self, dimension_keys: list[str], user_role: str) -> list[ResolvedDimension]:
        resolved: list[ResolvedDimension] = []
        for key in dimension_keys:
            if key not in self.catalog.dimensions:
                continue
            dimension = self.catalog.dimensions[key]
            if dimension.allowed_roles and user_role not in dimension.allowed_roles:
                continue
            resolved.append(
                ResolvedDimension(
                    key=dimension.key,
                    label=dimension.label,
                    expression=dimension.sql,
                    grain=dimension.grain,
                )
            )
        return resolved

    def _enforce_entity_grouping(
        self,
        question: str,
        dimensions: list[ResolvedDimension],
    ) -> tuple[list[ResolvedDimension], list[str]]:
        normalized = question.lower().replace("ё", "е")
        required_dimension_keys: list[str] = []
        if any(token in normalized for token in ["пользователь", "пользовател", "user"]):
            required_dimension_keys.append("user_id")
        if any(token in normalized for token in ["город", "городам", "городу", "city"]):
            required_dimension_keys.append("city_id")
        if "статус" in normalized:
            if "тендер" in normalized:
                required_dimension_keys.append("tender_status")
            else:
                required_dimension_keys.append("order_status")

        existing_keys = {dimension.key for dimension in dimensions}
        notes: list[str] = []
        for key in required_dimension_keys:
            if key in existing_keys or key not in self.catalog.dimensions:
                continue
            config = self.catalog.dimensions[key]
            dimensions.append(
                ResolvedDimension(
                    key=config.key,
                    label=config.label,
                    expression=config.sql,
                    grain=config.grain,
                )
            )
            notes.append(f"Добавлена обязательная группировка по {key} на основе сущности в вопросе.")
        return dimensions, notes

    def _resolve_filters(self, raw_filters: list[dict]) -> list[ResolvedFilter]:
        resolved: list[ResolvedFilter] = []
        for item in raw_filters:
            key = item.get("key")
            if not key or key not in self.catalog.filters:
                continue
            semantic_filter = self.catalog.filters[key]
            operator = item.get("operator", "eq")
            if operator not in semantic_filter.operators:
                continue
            resolved.append(
                ResolvedFilter(
                    key=key,
                    label=semantic_filter.label,
                    operator=operator,
                    value=item.get("value"),
                )
            )
        return resolved

    def _resolve_time_range(self, time_expression: str | None, *, anchor_date: date | None = None) -> TimeRange:
        today = anchor_date or self.time_context.get_anchor_date()
        mapping = self.catalog.time_mappings
        if time_expression and time_expression in mapping:
            config = mapping[time_expression]
            start, end = self._resolve_relative_window(config["kind"], today)
            return TimeRange(label=config["label"], start_date=start, end_date=end, grain=config.get("grain", "day"))
        return TimeRange(label="Последние 7 дней", start_date=today - timedelta(days=6), end_date=today, grain="day")

    def _resolve_relative_window(self, kind: str, today: date) -> tuple[date, date]:
        if kind == "yesterday":
            day = today - timedelta(days=1)
            return day, day
        if kind == "today":
            return today, today
        if kind == "current_week":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
            return start, end
        if kind == "previous_week":
            end = today - timedelta(days=today.weekday() + 1)
            start = end - timedelta(days=6)
            return start, end
        if kind == "current_month":
            start = today.replace(day=1)
            return start, today
        if kind == "previous_month":
            current_month_start = today.replace(day=1)
            end = current_month_start - timedelta(days=1)
            start = end.replace(day=1)
            return start, end
        if kind == "current_year":
            start = today.replace(month=1, day=1)
            return start, today
        if kind == "previous_year":
            year = today.year - 1
            return date(year, 1, 1), date(year, 12, 31)
        if kind == "rolling_quarter":
            # Last 3 months relative to today (approximation of NOW() - INTERVAL 3 MONTH).
            year = today.year
            month = today.month - 3
            while month <= 0:
                month += 12
                year -= 1
            day = min(today.day, calendar.monthrange(year, month)[1])
            return date(year, month, day), today
        return today - timedelta(days=6), today

    def _dedupe(self, items: list[str]) -> list[str]:
        result: list[str] = []
        for item in items:
            cleaned = item.strip()
            if cleaned and cleaned not in result:
                result.append(cleaned)
        return result

    def _first_time_dimension_key(self) -> str | None:
        for key, dimension in self.catalog.dimensions.items():
            if dimension.kind == "time":
                return key
        return None

    def _detect_requested_metric_kind(self, question: str) -> str | None:
        normalized = question.lower().replace("ё", "е")
        if "средн" in normalized or "в среднем" in normalized:
            return "avg"
        if any(token in normalized for token in ["сумм", "выручк", "доход", "оборот", "денег", "деньгам", "касс"]):
            return "sum"
        if "сколько" in normalized and "сколько процентов" not in normalized:
            return "count"
        return None

    def _default_metric_for_kind(self, question: str, kind: str) -> str | None:
        normalized = question.lower().replace("ё", "е")
        if kind == "count":
            return "total_orders" if "total_orders" in self.catalog.metrics else None
        if kind == "sum":
            return "total_revenue" if "total_revenue" in self.catalog.metrics else None
        if kind == "avg":
            if "скорост" in normalized and "avg_speed_mps" in self.catalog.metrics:
                return "avg_speed_mps"
            return "avg_order_price" if "avg_order_price" in self.catalog.metrics else None
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

    def collect_synonyms(self) -> dict[str, list[str]]:
        synonyms = defaultdict(list)
        for key, metric in self.catalog.metrics.items():
            synonyms[key].extend(metric.synonyms)
        for key, dimension in self.catalog.dimensions.items():
            synonyms[key].extend(dimension.synonyms)
        for entry in self.db.query(SemanticDictionaryEntry).filter(SemanticDictionaryEntry.is_active.is_(True)).all():
            synonyms[entry.target_key].extend(entry.synonyms_json)
            synonyms[entry.target_key].append(entry.term)
        return dict(synonyms)

    def _is_percent_change_request(self, question: str) -> bool:
        return is_percent_change_request(question)

    def _adapt_metrics_for_percent_change(self, metrics: list[ResolvedMetric]) -> list[ResolvedMetric]:
        if not metrics:
            return metrics
        adapted: list[ResolvedMetric] = []
        for metric in metrics:
            adapted.append(
                metric.model_copy(
                    update={
                        "label": f"{metric.label}, % к базе",
                        "description": f"Процентное изменение метрики «{metric.label}» относительно базового периода.",
                    }
                )
            )
        return adapted
