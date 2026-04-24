from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.privacy import redact_payload
from app.models.collaboration import WorkspaceMessage
from app.models.report import QueryStatus, ReportRun
from app.repositories.collaboration import CollaborationRepository
from app.repositories.reports import ReportRepository
from app.repositories.users import UserRepository
from app.schemas.query import QueryRequest
from app.services.audit_service import AuditService
from app.services.query_service import QueryService


class ScheduleService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReportRepository(db)
        self.groups = CollaborationRepository(db)
        self.audit = AuditService(db)

    def fire_schedule(self, schedule_id):
        schedule = self.repo.get_schedule(schedule_id)
        if not schedule or not schedule.is_active:
            return None

        report = self.repo.get_report(schedule.report_id)
        if not report:
            return None

        owner = UserRepository(self.db).get_by_id(report.owner_id)
        if not owner:
            return None

        try:
            result = QueryService(self.db).run(
                QueryRequest(
                    question=report.question,
                    execution_context="schedule",
                ),
                owner,
            )
            preview = redact_payload(jsonable_encoder({"rows": result.rows[:10], "columns": result.columns}))
            status = QueryStatus.executed if result.status == "executed" else QueryStatus.failed
            self.repo.create_run(
                ReportRun(
                    report_id=report.id,
                    triggered_by_user_id=None,
                    trigger_source="schedule",
                    status=status,
                    row_count=result.row_count,
                    result_preview_json=preview,
                )
            )
            now = datetime.now(ZoneInfo(schedule.timezone))
            trigger = CronTrigger.from_crontab(schedule.cron_expression, timezone=schedule.timezone)
            schedule.last_run_at = now
            schedule.next_run_at = trigger.get_next_fire_time(None, now)
            self.repo.save_schedule(schedule)
            delivery_target = f"stub-email:{schedule.recipient}"
            if schedule.channel.value == "group" and schedule.target_group_id:
                delivery_target = f"group:{schedule.target_group_id}"
                self.groups.create_message(
                    WorkspaceMessage(
                        group_id=schedule.target_group_id,
                        author_user_id=report.owner_id,
                        body=f"По расписанию отправлен отчёт «{report.name}».",
                        payload_json={
                            "kind": "scheduled_report",
                            "report_id": str(report.id),
                            **self._build_report_preview_payload(report),
                            "schedule_id": str(schedule.id),
                            "preview": preview,
                            "last_run_status": status.value,
                        },
                    )
                )
            self.audit.log(
                actor_user_id=report.owner_id,
                event_type="schedule_fired",
                status="success" if result.status == "executed" else result.status,
                question=report.question,
                sql_text=result.generated_sql,
                row_count=result.row_count,
                extra_json={
                    "schedule_id": str(schedule.id),
                    "delivery": delivery_target,
                    "preview": preview,
                    "resolved_period": result.query_plan.time_range.model_dump(mode="json"),
                },
            )
        except Exception as exc:
            self.audit.log(
                actor_user_id=report.owner_id,
                event_type="schedule_fired",
                status="failed",
                question=report.question,
                sql_text=report.sql_text,
                blocked_reason=str(exc),
                extra_json={"schedule_id": str(schedule.id)},
            )
        return preview

    def _build_report_preview_payload(self, report) -> dict:
        query_plan = report.query_plan_json if isinstance(report.query_plan_json, dict) else {}
        metrics = query_plan.get("metrics", [])
        metric_labels = [item.get("label", item.get("key", "")) for item in metrics if isinstance(item, dict)]
        time_range = query_plan.get("time_range", {})
        period_label = time_range.get("label") if isinstance(time_range, dict) else None
        return {
            "report_name": report.name,
            "question": report.question,
            "chart_type": report.chart_type,
            "metric_labels": [label for label in metric_labels if label],
            "period_label": period_label,
            "query_plan_json": query_plan,
        }
