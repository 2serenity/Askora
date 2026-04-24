from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.privacy import redact_payload
from app.models.collaboration import WorkspaceMessage
from app.models.report import QueryStatus, Report, ReportRun, ReportShare, Schedule, ScheduleChannel
from app.models.user import User
from app.repositories.collaboration import CollaborationRepository
from app.repositories.reports import ReportRepository
from app.schemas.report import SaveReportRequest, ScheduleRequest, UpdateReportRequest
from app.services.audit_service import AuditService


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReportRepository(db)
        self.groups = CollaborationRepository(db)
        self.audit = AuditService(db)

    def save_report(self, user: User, payload: SaveReportRequest) -> Report:
        existing = self.repo.find_existing_report(
            owner_id=user.id,
            name=payload.name,
            question=payload.question,
            sql_text=payload.sql_text,
        )
        if existing:
            existing.description = payload.description
            existing.query_plan_json = payload.query_plan_json
            existing.chart_type = payload.chart_type
            saved_existing = self.repo.update_report(existing)
            self._ensure_preview_run(saved_existing, payload, user.id)
            self.audit.log(
                actor_user_id=user.id,
                event_type="report_saved",
                status="deduplicated",
                question=payload.question,
                sql_text=payload.sql_text,
                interpretation_json=payload.query_plan_json,
            )
            return saved_existing

        report = Report(
            owner_id=user.id,
            name=payload.name,
            description=payload.description,
            question=payload.question,
            query_plan_json=payload.query_plan_json,
            sql_text=payload.sql_text,
            chart_type=payload.chart_type,
        )
        saved = self.repo.create_report(report)
        self._ensure_preview_run(saved, payload, user.id)
        self.audit.log(
            actor_user_id=user.id,
            event_type="report_saved",
            status="success",
            question=payload.question,
            sql_text=payload.sql_text,
            interpretation_json=payload.query_plan_json,
        )
        return saved

    def update_report(self, report: Report, payload: UpdateReportRequest) -> Report:
        report.name = payload.name
        report.description = payload.description
        return self.repo.update_report(report)

    def can_manage_report(self, report: Report, user: User) -> bool:
        return user.role.value == "admin" or report.owner_id == user.id

    def delete_report(self, report: Report, actor_user_id) -> None:
        self.repo.delete_report(report)
        self.audit.log(
            actor_user_id=actor_user_id,
            event_type="report_deleted",
            status="success",
            question=report.question,
            sql_text=report.sql_text,
        )

    def create_run(
        self,
        report: Report,
        *,
        triggered_by_user_id: UUID | None,
        trigger_source: str,
        status: QueryStatus,
        row_count: int,
        result_preview_json: dict,
    ) -> ReportRun:
        run = ReportRun(
            report_id=report.id,
            triggered_by_user_id=triggered_by_user_id,
            trigger_source=trigger_source,
            status=status,
            row_count=row_count,
            result_preview_json=redact_payload(jsonable_encoder(result_preview_json)),
        )
        return self.repo.create_run(run)

    def list_reports(self, user: User) -> list[Report]:
        return self.repo.list_reports(owner_id=user.id)

    def list_shared_reports(self, user: User) -> list[Report]:
        items = self.repo.list_shared_reports_for_user(user.id)
        return [item for item in items if item.owner_id != user.id]

    def get_report_for_user(self, report_id: UUID, user: User) -> Report | None:
        return self.repo.get_accessible_report(report_id, user.id, is_admin=user.role.value == "admin")

    def create_schedule(self, report: Report, payload: ScheduleRequest, actor: User) -> Schedule:
        channel = ScheduleChannel(payload.channel)
        recipient = self._resolve_schedule_recipient(payload)
        target_group_id = payload.target_group_id if channel == ScheduleChannel.group else None

        if target_group_id:
            self._require_group_post_access(target_group_id, actor)
            self.share_report_to_group(report, target_group_id, actor, note=None, publish_message=False)

        existing = self.repo.find_existing_schedule(
            report_id=report.id,
            cron_expression=payload.cron_expression,
            timezone=payload.timezone,
            recipient=recipient,
            channel=channel,
            target_group_id=target_group_id,
        )
        if existing:
            existing.is_active = payload.is_active
            existing.target_group_id = target_group_id
            existing.config_json = self._build_schedule_config(report, channel, recipient, target_group_id)
            existing.next_run_at = self._compute_next_run(payload.cron_expression, payload.timezone)
            saved_existing = self.repo.save_schedule(existing)
            self.audit.log(
                actor_user_id=actor.id,
                event_type="schedule_created",
                status="deduplicated",
                question=report.question,
                sql_text=report.sql_text,
                extra_json={"schedule_id": str(saved_existing.id), "cron_expression": saved_existing.cron_expression},
            )
            return saved_existing

        schedule = Schedule(
            report_id=report.id,
            cron_expression=payload.cron_expression,
            timezone=payload.timezone,
            recipient=recipient,
            channel=channel,
            target_group_id=target_group_id,
            is_active=payload.is_active,
            config_json=self._build_schedule_config(report, channel, recipient, target_group_id),
            next_run_at=self._compute_next_run(payload.cron_expression, payload.timezone),
        )
        saved = self.repo.create_schedule(schedule)
        self.audit.log(
            actor_user_id=actor.id,
            event_type="schedule_created",
            status="success",
            question=report.question,
            sql_text=report.sql_text,
            extra_json={"schedule_id": str(saved.id), "cron_expression": saved.cron_expression},
        )
        return saved

    def list_schedules(self, user: User):
        return self.repo.list_schedules(user.id)

    def delete_schedule(self, schedule: Schedule, actor_user_id) -> None:
        self.repo.delete_schedule(schedule)
        self.audit.log(
            actor_user_id=actor_user_id,
            event_type="schedule_deleted",
            status="success",
            extra_json={"schedule_id": str(schedule.id)},
        )

    def share_report_to_group(
        self,
        report: Report,
        group_id: UUID,
        actor: User,
        *,
        note: str | None,
        publish_message: bool = True,
    ) -> ReportShare:
        if actor.role.value != "admin" and report.owner_id != actor.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Делиться можно только своими отчётами")

        self._require_group_post_access(group_id, actor)
        share = self.repo.find_share(report.id, group_id)
        if share:
            share.note = note
            saved = self.repo.save_share(share)
            audit_status = "deduplicated"
        else:
            saved = self.repo.create_share(
                ReportShare(
                    report_id=report.id,
                    group_id=group_id,
                    shared_by_user_id=actor.id,
                    note=note,
                )
            )
            audit_status = "success"

        if publish_message:
            body = note.strip() if note else f"Поделился отчётом «{report.name}»."
            self.groups.create_message(
                WorkspaceMessage(
                    group_id=group_id,
                    author_user_id=actor.id,
                    body=body,
                    payload_json={
                        "kind": "report_share",
                        "report_id": str(report.id),
                        **self._build_report_preview_payload(report),
                    },
                )
            )

        self.audit.log(
            actor_user_id=actor.id,
            event_type="report_shared_to_group",
            status=audit_status,
            question=report.question,
            sql_text=report.sql_text,
            extra_json={"group_id": str(group_id), "report_id": str(report.id)},
        )
        return saved

    def _build_schedule_config(
        self,
        report: Report,
        channel: ScheduleChannel,
        recipient: str,
        target_group_id: UUID | None,
    ) -> dict:
        payload = {"email_subject": f"Отчёт: {report.name}", "delivery_target": recipient}
        payload["freshness_mode"] = "runtime_anchor"
        if channel == ScheduleChannel.group and target_group_id:
            payload["target_group_id"] = str(target_group_id)
        return payload

    def _build_report_preview_payload(self, report: Report) -> dict:
        query_plan = report.query_plan_json if isinstance(report.query_plan_json, dict) else {}
        metrics = query_plan.get("metrics", [])
        metric_labels = [item.get("label", item.get("key", "")) for item in metrics if isinstance(item, dict)]
        time_range = query_plan.get("time_range", {})
        period_label = time_range.get("label") if isinstance(time_range, dict) else None
        latest_run = self._get_latest_run(report)
        return {
            "report_name": report.name,
            "question": report.question,
            "chart_type": report.chart_type,
            "metric_labels": [label for label in metric_labels if label],
            "period_label": period_label,
            "query_plan_json": query_plan,
            "preview": latest_run.result_preview_json if latest_run and isinstance(latest_run.result_preview_json, dict) else {},
            "last_run_status": latest_run.status.value if latest_run else None,
            "last_run_row_count": latest_run.row_count if latest_run else None,
        }

    def _compute_next_run(self, cron_expression: str, timezone: str):
        now = datetime.now(ZoneInfo(timezone))
        trigger = CronTrigger.from_crontab(cron_expression, timezone=timezone)
        return trigger.get_next_fire_time(None, now)

    def _resolve_schedule_recipient(self, payload: ScheduleRequest) -> str:
        if payload.channel == ScheduleChannel.group.value:
            group = self.groups.get_group(payload.target_group_id) if payload.target_group_id else None
            if not group:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рабочая группа не найдена")
            return group.name
        if not payload.recipient:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нужно указать получателя")
        return str(payload.recipient)

    def _ensure_preview_run(self, report: Report, payload: SaveReportRequest, actor_user_id: UUID) -> None:
        if not payload.result_preview_json:
            return

        hydrated_report = self.repo.get_report(report.id) or report
        if hydrated_report.runs:
            return

        status = QueryStatus.executed if payload.execution_status == QueryStatus.executed.value else QueryStatus.failed
        self.create_run(
            hydrated_report,
            triggered_by_user_id=actor_user_id,
            trigger_source="report_save",
            status=status,
            row_count=payload.row_count,
            result_preview_json=payload.result_preview_json,
        )

    def _get_latest_run(self, report: Report) -> ReportRun | None:
        if not report.runs:
            return None
        return max(report.runs, key=lambda item: item.executed_at)

    def _require_group_post_access(self, group_id: UUID, actor: User) -> None:
        if actor.role.value == "admin":
            return
        membership = self.groups.get_membership(group_id, actor.id)
        if not membership or membership.role.value == "viewer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет прав публиковать отчёты в выбранную группу",
            )
