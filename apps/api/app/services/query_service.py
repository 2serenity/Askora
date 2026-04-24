from __future__ import annotations

from datetime import date

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.ai.percent_change import is_percent_change_request
from app.ai.extractor import HybridIntentExtractor
from app.core.config import settings
from app.core.privacy import redact_payload
from app.data_sources.registry import data_source_registry
from app.models.report import QueryHistory, QueryStatus, UserQueryExample
from app.models.user import User
from app.query_engine.executor import query_executor
from app.query_engine.sql_builder import sql_builder
from app.repositories.reports import ReportRepository
from app.schemas.query import QueryExampleCreateRequest, QueryRequest, QueryResult, ValidationResult
from app.semantic_layer.planner import VisualizationPlanner
from app.semantic_layer.resolver import SemanticResolver
from app.services.audit_service import AuditService
from app.services.metrics_service import metrics_service
from app.services.query_review_service import QueryReviewService
from app.services.sql_review_service import SQLReviewService
from app.sql_guardrails.validator import sql_validator


class QueryService:
    def __init__(self, db: Session):
        self.db = db
        self.extractor = HybridIntentExtractor(db)
        self.reviewer = QueryReviewService(db)
        self.sql_reviewer = SQLReviewService(db)
        self.resolver = SemanticResolver(db)
        self.visualization = VisualizationPlanner()
        self.audit = AuditService(db)
        self.repo = ReportRepository(db)

    def run(self, payload: QueryRequest, user: User) -> QueryResult:
        execution_anchor = date.today() if payload.execution_context == "schedule" else None
        intent, extraction_trace = self.extractor.extract_with_trace(payload.question)
        query_plan = self.resolver.resolve(intent, user.role.value, anchor_date=execution_anchor)
        processing_trace: dict[str, object] = {
            "extraction": extraction_trace,
            "resolved_plan": self._summarize_plan(query_plan),
        }

        review = self.reviewer.review(payload.question, intent, query_plan)
        processing_trace["intent_review"] = {
            "adjusted": review.adjusted,
            "notes": review.notes,
        }
        if review.adjusted:
            query_plan = self.resolver.resolve(review.intent, user.role.value, anchor_date=execution_anchor)
            processing_trace["resolved_plan_after_review"] = self._summarize_plan(query_plan)
            self.audit.log(
                actor_user_id=user.id,
                event_type="query_reconciled",
                status="success",
                question=payload.question,
                interpretation_json=self._to_json(query_plan.model_dump(mode="json")),
                extra_json={"review_notes": review.notes, "trace": processing_trace},
            )

        visualization = self.visualization.choose(query_plan)
        processing_trace["visualization"] = visualization.model_dump(mode="json")
        source = data_source_registry.get_source(self.db, dataset_key=query_plan.dataset)

        if query_plan.needs_clarification:
            validation = ValidationResult(
                allowed=False,
                normalized_sql="",
                complexity_score=0,
                row_limit_applied=0,
                warnings=[],
                blocked_reasons=["Запрос требует уточнения."],
            )
            self._persist_history(
                user=user,
                payload=payload,
                query_plan=query_plan,
                sql_text="",
                validation_json=validation.model_dump(mode="json"),
                result_preview_json={},
                status=QueryStatus.needs_clarification,
                row_count=0,
                chart_type=visualization.chart_type,
            )
            self.audit.log(
                actor_user_id=user.id,
                event_type="query_interpreted",
                status="needs_clarification",
                question=payload.question,
                interpretation_json=self._to_json(query_plan.model_dump(mode="json")),
                extra_json={"trace": processing_trace},
            )
            self._track_query_outcome("needs_clarification", validation.blocked_reasons)
            return QueryResult(
                question=payload.question,
                query_plan=query_plan,
                generated_sql="",
                validation=validation,
                visualization=visualization,
                columns=[],
                rows=[],
                row_count=0,
                status="needs_clarification",
                user_message="Запрос требует уточнения. Система не стала выполнять его автоматически.",
                suggestions=query_plan.clarification_questions or query_plan.warnings,
                processing_trace=processing_trace,
            )

        if source.allowed_roles and user.role.value not in source.allowed_roles:
            validation = ValidationResult(
                allowed=False,
                normalized_sql="",
                complexity_score=0,
                row_limit_applied=query_plan.limit,
                warnings=[],
                blocked_reasons=[f"У роли {user.role.value} нет доступа к источнику данных {source.name}."],
            )
            self._persist_history(
                user=user,
                payload=payload,
                query_plan=query_plan,
                sql_text="",
                validation_json=validation.model_dump(mode="json"),
                result_preview_json={},
                status=QueryStatus.blocked,
                row_count=0,
                chart_type=visualization.chart_type,
            )
            self.audit.log(
                actor_user_id=user.id,
                event_type="query_blocked",
                status="blocked",
                question=payload.question,
                blocked_reason=validation.blocked_reasons[0],
                interpretation_json=self._to_json(query_plan.model_dump(mode="json")),
                validation_json=self._to_json(validation.model_dump(mode="json")),
                extra_json={"trace": processing_trace},
            )
            self._track_query_outcome("blocked", validation.blocked_reasons)
            return QueryResult(
                question=payload.question,
                query_plan=query_plan,
                generated_sql="",
                validation=validation,
                visualization=visualization,
                columns=[],
                rows=[],
                row_count=0,
                status="blocked",
                user_message="Запрос заблокирован политикой доступа к источнику данных.",
                suggestions=validation.blocked_reasons,
                processing_trace=processing_trace,
            )

        sql_text, params = sql_builder.build(query_plan)
        processing_trace["sql_builder"] = {
            "sql_preview": sql_text,
            "params": self._to_json(params),
        }

        sql_review = self.sql_reviewer.review(
            question=payload.question,
            query_plan=query_plan,
            sql_text=sql_text,
            params=params,
        )
        processing_trace["sql_review"] = {
            "allowed": sql_review.allowed,
            "needs_clarification": sql_review.needs_clarification,
            "blocked_reasons": sql_review.blocked_reasons,
            "notes": sql_review.notes,
        }

        if sql_review.notes:
            query_plan.warnings = self._dedupe(query_plan.warnings + sql_review.notes)
            query_plan.confidence = max(0.1, round(query_plan.confidence - min(0.03 * len(sql_review.notes), 0.12), 2))

        if not sql_review.allowed:
            query_plan.confidence = min(query_plan.confidence, 0.55)
            query_plan.needs_clarification = sql_review.needs_clarification or query_plan.needs_clarification
            query_plan.clarification_questions = self._dedupe(query_plan.clarification_questions + sql_review.blocked_reasons)
            query_plan.warnings = self._dedupe(query_plan.warnings + sql_review.blocked_reasons)
            validation = ValidationResult(
                allowed=False,
                normalized_sql=sql_text,
                complexity_score=0,
                row_limit_applied=query_plan.limit,
                warnings=[],
                blocked_reasons=sql_review.blocked_reasons,
            )
            result_status = QueryStatus.needs_clarification if sql_review.needs_clarification else QueryStatus.blocked
            self._persist_history(
                user=user,
                payload=payload,
                query_plan=query_plan,
                sql_text=sql_text,
                validation_json=validation.model_dump(mode="json"),
                result_preview_json={},
                status=result_status,
                row_count=0,
                chart_type=visualization.chart_type,
            )
            self.audit.log(
                actor_user_id=user.id,
                event_type="query_alignment_blocked",
                status=result_status.value,
                question=payload.question,
                sql_text=sql_text,
                blocked_reason="; ".join(sql_review.blocked_reasons),
                interpretation_json=self._to_json(query_plan.model_dump(mode="json")),
                validation_json=self._to_json(validation.model_dump(mode="json")),
                extra_json={"review_notes": sql_review.notes, "trace": processing_trace},
            )
            self._track_query_outcome(
                "needs_clarification" if sql_review.needs_clarification else "blocked",
                sql_review.blocked_reasons,
            )
            return QueryResult(
                question=payload.question,
                query_plan=query_plan,
                generated_sql=sql_text,
                validation=validation,
                visualization=visualization,
                columns=[],
                rows=[],
                row_count=0,
                status="needs_clarification" if sql_review.needs_clarification else "blocked",
                user_message=(
                    "Система остановила выполнение после финальной сверки смысла запроса и SQL."
                    if sql_review.needs_clarification
                    else "Запрос заблокирован на этапе финальной сверки."
                ),
                suggestions=sql_review.blocked_reasons,
                processing_trace=processing_trace,
            )

        validation = sql_validator.validate(sql_text, query_plan.limit, query_plan.dataset, dialect=source.dialect)
        processing_trace["guardrails"] = validation.model_dump(mode="json")

        if validation.warnings:
            query_plan.confidence = max(0.1, round(query_plan.confidence - min(0.02 * len(validation.warnings), 0.08), 2))

        if not validation.allowed:
            query_plan.confidence = min(query_plan.confidence, 0.45)
            self._persist_history(
                user=user,
                payload=payload,
                query_plan=query_plan,
                sql_text=validation.normalized_sql,
                validation_json=validation.model_dump(mode="json"),
                result_preview_json={},
                status=QueryStatus.blocked,
                row_count=0,
                chart_type=visualization.chart_type,
            )
            self.audit.log(
                actor_user_id=user.id,
                event_type="query_blocked",
                status="blocked",
                question=payload.question,
                sql_text=validation.normalized_sql,
                blocked_reason="; ".join(validation.blocked_reasons),
                interpretation_json=self._to_json(query_plan.model_dump(mode="json")),
                validation_json=self._to_json(validation.model_dump(mode="json")),
                extra_json={"trace": processing_trace},
            )
            self._track_query_outcome("blocked", validation.blocked_reasons)
            return QueryResult(
                question=payload.question,
                query_plan=query_plan,
                generated_sql=validation.normalized_sql,
                validation=validation,
                visualization=visualization,
                columns=[],
                rows=[],
                row_count=0,
                status="blocked",
                user_message="Запрос заблокирован guardrails и не был выполнен.",
                suggestions=validation.blocked_reasons,
                processing_trace=processing_trace,
            )

        explain_plan = self._safe_explain_plan(validation.normalized_sql, params, query_plan.dataset)
        if explain_plan:
            estimated_cost, estimated_rows = self._extract_plan_estimates(explain_plan)
            validation.explain_plan_json = explain_plan
            validation.estimated_cost = estimated_cost
            validation.estimated_rows = estimated_rows
            processing_trace["explain_plan"] = {
                "estimated_cost": estimated_cost,
                "estimated_rows": estimated_rows,
            }
            if (
                settings.max_query_cost > 0
                and estimated_cost is not None
                and estimated_cost > settings.max_query_cost
            ):
                validation.allowed = False
                validation.blocked_reasons = self._dedupe(
                    validation.blocked_reasons
                    + [
                        (
                            "Запрос отклонён до выполнения: прогнозируемая стоимость "
                            f"{estimated_cost:.2f} превышает лимит {settings.max_query_cost:.2f}."
                        )
                    ]
                )
                query_plan.confidence = min(query_plan.confidence, 0.5)
                self._persist_history(
                    user=user,
                    payload=payload,
                    query_plan=query_plan,
                    sql_text=validation.normalized_sql,
                    validation_json=validation.model_dump(mode="json"),
                    result_preview_json={},
                    status=QueryStatus.blocked,
                    row_count=0,
                    chart_type=visualization.chart_type,
                )
                self.audit.log(
                    actor_user_id=user.id,
                    event_type="query_blocked",
                    status="blocked",
                    question=payload.question,
                    sql_text=validation.normalized_sql,
                    blocked_reason="; ".join(validation.blocked_reasons),
                    interpretation_json=self._to_json(query_plan.model_dump(mode="json")),
                    validation_json=self._to_json(validation.model_dump(mode="json")),
                    extra_json={"trace": processing_trace},
                )
                self._track_query_outcome("blocked", validation.blocked_reasons)
                return QueryResult(
                    question=payload.question,
                    query_plan=query_plan,
                    generated_sql=validation.normalized_sql,
                    validation=validation,
                    visualization=visualization,
                    columns=[],
                    rows=[],
                    row_count=0,
                    status="blocked",
                    user_message="Запрос заблокирован по прогнозной стоимости до запуска в БД.",
                    suggestions=validation.blocked_reasons,
                    processing_trace=processing_trace,
                )

        columns: list[str] = []
        rows: list[dict] = []
        row_count = 0
        status = QueryStatus.executed
        user_message = "Запрос успешно выполнен."

        try:
            if payload.dry_run:
                user_message = "SQL успешно прошел проверку и не был выполнен, потому что выбран режим dry-run."
            else:
                columns, rows, row_count = query_executor.execute(
                    self.db,
                    validation.normalized_sql,
                    params,
                    dataset_key=query_plan.dataset,
                )
        except Exception as exc:
            status = QueryStatus.failed
            user_message = f"Не удалось выполнить запрос: {exc}"

        processing_trace["execution"] = {
            "status": status.value,
            "row_count": row_count,
            "dry_run": payload.dry_run,
            "columns": columns,
        }

        comparison_summary = self._build_comparison_summary(rows, query_plan)
        preview = redact_payload(self._to_json({"rows": rows[:10], "columns": columns}))
        self._persist_history(
            user=user,
            payload=payload,
            query_plan=query_plan,
            sql_text=validation.normalized_sql,
            validation_json=validation.model_dump(mode="json"),
            result_preview_json=preview,
            status=status,
            row_count=row_count,
            chart_type=visualization.chart_type,
        )
        self.audit.log(
            actor_user_id=user.id,
            event_type="query_executed" if status == QueryStatus.executed else "query_failed",
            status=status.value,
            question=payload.question,
            sql_text=validation.normalized_sql,
            row_count=row_count,
            interpretation_json=self._to_json(query_plan.model_dump(mode="json")),
            validation_json=self._to_json(validation.model_dump(mode="json")),
            extra_json={"preview": preview, "trace": processing_trace},
        )
        self._track_query_outcome("executed" if status == QueryStatus.executed else "failed", validation.blocked_reasons)
        return QueryResult(
            question=payload.question,
            query_plan=query_plan,
            generated_sql=validation.normalized_sql,
            validation=validation,
            visualization=visualization,
            columns=columns,
            rows=rows,
            row_count=row_count,
            status="executed" if status == QueryStatus.executed else "failed",
            user_message=user_message,
            suggestions=query_plan.warnings + validation.warnings,
            comparison_summary=comparison_summary,
            processing_trace=processing_trace,
        )

    def list_history(self, user: User):
        return self.repo.list_query_history(user.id)

    def delete_history_item(self, history_id, user: User) -> bool:
        item = self.repo.get_history_item(history_id, user.id)
        if not item:
            return False
        self.repo.delete_history_item(item)
        self.audit.log(
            actor_user_id=user.id,
            event_type="history_deleted",
            status="success",
            question=item.question,
            sql_text=item.sql_text,
        )
        return True

    def clear_history(self, user: User) -> int:
        deleted = self.repo.clear_history(user.id)
        self.audit.log(
            actor_user_id=user.id,
            event_type="history_cleared",
            status="success",
            row_count=deleted,
        )
        return deleted

    def list_examples(self, user: User) -> list[UserQueryExample]:
        return self.repo.list_query_examples(user.id)

    def create_example(self, payload: QueryExampleCreateRequest, user: User) -> UserQueryExample:
        existing = self.repo.find_query_example(user.id, payload.text)
        if existing:
            existing.is_pinned = payload.is_pinned
            return self.repo.save_query_example(existing)
        return self.repo.create_query_example(
            UserQueryExample(
                user_id=user.id,
                text=payload.text.strip(),
                is_pinned=payload.is_pinned,
            )
        )

    def delete_example(self, example_id, user: User) -> bool:
        item = self.repo.get_query_example(example_id, user.id)
        if not item:
            return False
        self.repo.delete_query_example(item)
        return True

    def _persist_history(
        self,
        *,
        user: User,
        payload: QueryRequest,
        query_plan,
        sql_text: str,
        validation_json: dict,
        result_preview_json: dict,
        status: QueryStatus,
        row_count: int,
        chart_type: str | None,
    ) -> QueryHistory:
        history = QueryHistory(
            user_id=user.id,
            question=payload.question,
            query_plan_json=self._to_json(query_plan.model_dump(mode="json")),
            sql_text=sql_text,
            validation_json=redact_payload(self._to_json(validation_json)),
            result_preview_json=redact_payload(self._to_json(result_preview_json)),
            chart_type=chart_type,
            confidence=query_plan.confidence,
            status=status,
            row_count=row_count,
        )
        return self.repo.create_query_history(history)

    def _build_comparison_summary(self, rows: list[dict], query_plan) -> dict | None:
        if (
            not query_plan.comparison.enabled
            or not rows
            or not query_plan.metrics
            or "period_label" not in rows[0]
            or is_percent_change_request(query_plan.question)
        ):
            return None

        metric_key = query_plan.metrics[0].key
        grouped: dict[str, dict[str, float]] = {}
        for row in rows:
            label_key = next((dimension.key for dimension in query_plan.dimensions if dimension.key in row), None)
            label_value = row.get(label_key, "Итого") if label_key else "Итого"
            grouped.setdefault(str(label_value), {})
            grouped[str(label_value)][str(row.get("period_label", "Период"))] = float(row.get(metric_key, 0) or 0)

        summary = []
        for label, periods in grouped.items():
            current = periods.get("Текущий период", 0)
            previous = periods.get("Предыдущий период", 0)
            delta = current - previous
            delta_pct = round((delta / previous * 100), 2) if previous else None
            summary.append(
                {
                    "label": label,
                    "current": current,
                    "previous": previous,
                    "delta": round(delta, 2),
                    "delta_pct": delta_pct,
                }
            )
        return {"items": summary, "metric": query_plan.metrics[0].label}

    def _to_json(self, payload):
        return jsonable_encoder(payload)

    def _safe_explain_plan(self, sql_text: str, params: dict, dataset_key: str) -> dict | None:
        try:
            return query_executor.explain(self.db, sql_text, params, dataset_key=dataset_key)
        except Exception:
            return None

    def _extract_plan_estimates(self, explain_plan: dict) -> tuple[float | None, float | None]:
        plan_node = explain_plan.get("Plan") if isinstance(explain_plan, dict) else None
        if not isinstance(plan_node, dict):
            return None, None
        total_cost = plan_node.get("Total Cost")
        plan_rows = plan_node.get("Plan Rows")
        try:
            cast_cost = float(total_cost) if total_cost is not None else None
        except (TypeError, ValueError):
            cast_cost = None
        try:
            cast_rows = float(plan_rows) if plan_rows is not None else None
        except (TypeError, ValueError):
            cast_rows = None
        return cast_cost, cast_rows

    def _dedupe(self, items: list[str]) -> list[str]:
        result: list[str] = []
        for item in items:
            cleaned = item.strip()
            if cleaned and cleaned not in result:
                result.append(cleaned)
        return result

    def _summarize_plan(self, query_plan) -> dict[str, object]:
        return {
            "dataset": query_plan.dataset,
            "intent_type": query_plan.intent_type,
            "metrics": [metric.key for metric in query_plan.metrics],
            "dimensions": [dimension.key for dimension in query_plan.dimensions],
            "filters": [item.key for item in query_plan.filters],
            "time_range": query_plan.time_range.model_dump(mode="json"),
            "multi_date": query_plan.multi_date.model_dump(mode="json") if query_plan.multi_date else None,
            "comparison": query_plan.comparison.model_dump(mode="json"),
            "preferred_chart_type": query_plan.preferred_chart_type,
            "confidence": query_plan.confidence,
            "needs_clarification": query_plan.needs_clarification,
        }

    def _track_query_outcome(self, status: str, blocked_reasons: list[str]) -> None:
        metrics_service.observe_query_run(status)
        if status in {"blocked", "needs_clarification"}:
            reasons = blocked_reasons or ["unknown"]
            for reason in reasons:
                metrics_service.observe_query_blocked_reason(reason)
