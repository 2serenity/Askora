from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.query import ComparisonSpec, QueryIntent, QueryPlan


@dataclass
class QueryReviewResult:
    adjusted: bool
    intent: QueryIntent
    notes: list[str] = field(default_factory=list)


class QueryReviewService:
    """Lightweight alignment pass between raw intent and resolved plan."""

    _DIMENSION_HINTS = {
        "по дням недели": "order_dow",
        "по дням": "order_date",
        "по датам": "order_date",
        "по неделям": "order_week",
        "по месяцам": "order_month",
        "по часам": "order_hour",
        "по городам": "city_id",
        "по статусам заказа": "order_status",
        "по статусам тендера": "tender_status",
    }

    _METRIC_HINTS = {
        "выполненн": "completed_orders",
        "отмен": "cancelled_orders",
        "выручк": "total_revenue",
        "доход": "total_revenue",
        "средн": "avg_order_price",
        "тендер": "total_tenders",
    }

    _COMPARISON_HINTS = ("сравни", "сравнение", "по сравнению", "в сравнении", "относительно")
    _PERCENT_HINTS = ("процент", "процентов", "в процентах", "рост", "паден", "изменен", "поднял", "опуст")

    def __init__(self, db: Session):
        self.db = db

    def review(self, question: str, intent: QueryIntent, query_plan: QueryPlan) -> QueryReviewResult:
        notes: list[str] = []
        payload = intent.model_dump(mode="python")
        adjusted = False
        normalized_question = self._normalize_text(question)
        has_multi_date_breakdown = bool(intent.multi_date and len(intent.multi_date.dates) >= 2)
        wants_percent_change = self._wants_percent_change(normalized_question)
        wants_comparison = any(token in normalized_question for token in self._COMPARISON_HINTS)

        comparison = ComparisonSpec.model_validate(payload.get("comparison") or {})

        if has_multi_date_breakdown and comparison.enabled and not wants_percent_change:
            payload["comparison"] = ComparisonSpec().model_dump(mode="python")
            notes.append("Сравнение оставлено как разбивка по выбранным датам без сведения к двум периодам.")
            adjusted = True
            comparison = ComparisonSpec()

        if not comparison.enabled and wants_comparison and not has_multi_date_breakdown:
            payload["comparison"] = ComparisonSpec(
                enabled=True,
                mode="previous_period",
                baseline_label="Предыдущий период",
            ).model_dump(mode="python")
            notes.append("Вопрос интерпретирован как сравнение текущего и базового периода.")
            adjusted = True
            comparison = ComparisonSpec(enabled=True, mode="previous_period", baseline_label="Предыдущий период")

        if (
            comparison.enabled
            and not wants_comparison
            and not wants_percent_change
            and not has_multi_date_breakdown
            and not comparison.baseline_start_date
            and not comparison.baseline_end_date
        ):
            payload["comparison"] = ComparisonSpec().model_dump(mode="python")
            notes.append("Снято ложное сравнение периодов: в вопросе нет явного сигнала на сравнение.")
            adjusted = True
            comparison = ComparisonSpec()

        if has_multi_date_breakdown and "order_date" not in payload["dimensions"]:
            payload["dimensions"] = [*payload["dimensions"], "order_date"]
            notes.append("Для нескольких явных дат добавлена обязательная разбивка по дате заказа.")
            adjusted = True

        if "по дням недели" in normalized_question:
            if "order_dow" not in payload["dimensions"]:
                payload["dimensions"] = [*payload["dimensions"], "order_dow"]
                notes.append("Добавлена явная разбивка по дням недели.")
                adjusted = True
            if "order_date" in payload["dimensions"]:
                payload["dimensions"] = [item for item in payload["dimensions"] if item != "order_date"]
                notes.append("Лишняя разбивка по календарной дате убрана, чтобы сохранить запрос по дням недели.")
                adjusted = True

        for phrase, dimension_key in self._DIMENSION_HINTS.items():
            if phrase == "по дням" and "по дням недели" in normalized_question:
                continue
            if phrase in normalized_question and dimension_key not in payload["dimensions"]:
                payload["dimensions"] = [*payload["dimensions"], dimension_key]
                notes.append(f"Добавлена явная разбивка: {phrase}.")
                adjusted = True

        if not payload["metrics"] and not intent.ambiguity_reasons:
            for token, metric_key in self._METRIC_HINTS.items():
                if token in normalized_question:
                    payload["metrics"] = [metric_key]
                    notes.append("Метрика уточнена по ключевым словам из вопроса.")
                    adjusted = True
                    break

        if query_plan.needs_clarification and not payload["clarification_questions"]:
            payload["clarification_questions"] = list(intent.ambiguity_reasons or query_plan.clarification_questions)
            adjusted = True

        payload["confidence"] = self._recompute_confidence(payload)

        reviewed_intent = QueryIntent.model_validate(self._normalize_payload(payload))
        return QueryReviewResult(adjusted=adjusted, intent=reviewed_intent, notes=notes)

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload["metrics"] = self._dedupe(payload.get("metrics", []))
        payload["dimensions"] = self._dedupe(payload.get("dimensions", []))
        payload["clarification_questions"] = self._dedupe(payload.get("clarification_questions", []))
        payload["notes"] = self._dedupe(payload.get("notes", []))
        payload["ambiguity_reasons"] = self._dedupe(payload.get("ambiguity_reasons", []))
        return payload

    def _dedupe(self, items: list[Any]) -> list[Any]:
        result: list[Any] = []
        for item in items:
            if item not in result:
                result.append(item)
        return result

    def _recompute_confidence(self, payload: dict[str, Any]) -> float:
        score = 0.32
        score += min(len(payload.get("metrics", [])), 3) * 0.16
        score += min(len(payload.get("dimensions", [])), 2) * 0.12
        if payload.get("time_expression") or payload.get("time_range_override") or payload.get("multi_date"):
            score += 0.12
        if payload.get("comparison", {}).get("enabled"):
            score += 0.08
        if payload.get("preferred_chart_type"):
            score += 0.03
        if payload.get("filters"):
            score += 0.06
        if payload.get("ambiguity_reasons"):
            score -= 0.35
        return max(0.1, min(round(score, 2), 0.98))

    def _wants_percent_change(self, question: str) -> bool:
        return any(token in question for token in self._PERCENT_HINTS)

    def _normalize_text(self, value: str) -> str:
        return value.lower().replace("ё", "е")
