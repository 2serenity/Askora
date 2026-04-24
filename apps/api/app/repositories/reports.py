from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.collaboration import WorkspaceGroup, WorkspaceGroupMember
from app.models.report import QueryHistory, Report, ReportRun, ReportShare, Schedule, ScheduleChannel, UserQueryExample


class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_report(self, report: Report) -> Report:
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def find_existing_report(
        self,
        *,
        owner_id: UUID,
        name: str,
        question: str,
        sql_text: str,
    ) -> Report | None:
        normalized_name = name.strip().lower()
        return (
            self.db.query(Report)
            .filter(Report.owner_id == owner_id)
            .filter(func.lower(Report.name) == normalized_name)
            .filter(Report.question == question)
            .filter(Report.sql_text == sql_text)
            .one_or_none()
        )

    def update_report(self, report: Report) -> Report:
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_report(self, report_id: UUID, owner_id: UUID | None = None) -> Report | None:
        query = (
            self.db.query(Report)
            .options(joinedload(Report.runs), joinedload(Report.schedules), joinedload(Report.shares))
            .filter(Report.id == report_id)
        )
        if owner_id:
            query = query.filter(Report.owner_id == owner_id)
        return query.one_or_none()

    def list_reports(self, owner_id: UUID | None = None) -> list[Report]:
        query = (
            self.db.query(Report)
            .options(joinedload(Report.runs), joinedload(Report.schedules), joinedload(Report.shares))
            .order_by(Report.updated_at.desc())
        )
        if owner_id:
            query = query.filter(Report.owner_id == owner_id)
        return query.all()

    def list_shared_reports_for_user(self, user_id: UUID) -> list[Report]:
        return (
            self.db.query(Report)
            .join(ReportShare, ReportShare.report_id == Report.id)
            .join(WorkspaceGroupMember, WorkspaceGroupMember.group_id == ReportShare.group_id)
            .options(joinedload(Report.runs), joinedload(Report.schedules), joinedload(Report.shares))
            .filter(WorkspaceGroupMember.user_id == user_id)
            .order_by(Report.updated_at.desc())
            .distinct()
            .all()
        )

    def list_group_shared_reports(self, group_id: UUID) -> list[ReportShare]:
        return (
            self.db.query(ReportShare)
            .options(
                joinedload(ReportShare.report).joinedload(Report.runs),
                joinedload(ReportShare.report).joinedload(Report.owner),
                joinedload(ReportShare.group),
            )
            .filter(ReportShare.group_id == group_id)
            .order_by(ReportShare.created_at.desc())
            .all()
        )

    def create_share(self, share: ReportShare) -> ReportShare:
        self.db.add(share)
        self.db.commit()
        self.db.refresh(share)
        return share

    def save_share(self, share: ReportShare) -> ReportShare:
        self.db.add(share)
        self.db.commit()
        self.db.refresh(share)
        return share

    def find_share(self, report_id: UUID, group_id: UUID) -> ReportShare | None:
        return (
            self.db.query(ReportShare)
            .filter(ReportShare.report_id == report_id, ReportShare.group_id == group_id)
            .one_or_none()
        )

    def get_accessible_report(self, report_id: UUID, user_id: UUID, is_admin: bool = False) -> Report | None:
        query = (
            self.db.query(Report)
            .outerjoin(ReportShare, ReportShare.report_id == Report.id)
            .outerjoin(WorkspaceGroupMember, WorkspaceGroupMember.group_id == ReportShare.group_id)
            .options(joinedload(Report.runs), joinedload(Report.schedules), joinedload(Report.shares))
            .filter(Report.id == report_id)
        )
        if not is_admin:
            query = query.filter(or_(Report.owner_id == user_id, WorkspaceGroupMember.user_id == user_id))
        return query.distinct().first()

    def delete_report(self, report: Report) -> None:
        self.db.delete(report)
        self.db.commit()

    def create_run(self, run: ReportRun) -> ReportRun:
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def create_schedule(self, schedule: Schedule) -> Schedule:
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def find_existing_schedule(
        self,
        *,
        report_id: UUID,
        cron_expression: str,
        timezone: str,
        recipient: str,
        channel: ScheduleChannel,
        target_group_id: UUID | None = None,
    ) -> Schedule | None:
        return (
            self.db.query(Schedule)
            .filter(Schedule.report_id == report_id)
            .filter(Schedule.cron_expression == cron_expression)
            .filter(Schedule.timezone == timezone)
            .filter(Schedule.recipient == recipient)
            .filter(Schedule.channel == channel)
            .filter(Schedule.target_group_id == target_group_id)
            .one_or_none()
        )

    def list_schedules(self, owner_id: UUID | None = None) -> list[Schedule]:
        query = self.db.query(Schedule).join(Report).options(joinedload(Schedule.target_group)).order_by(Schedule.created_at.desc())
        if owner_id:
            query = query.filter(Report.owner_id == owner_id)
        return query.all()

    def get_schedule(self, schedule_id: UUID) -> Schedule | None:
        return self.db.query(Schedule).options(joinedload(Schedule.target_group)).filter(Schedule.id == schedule_id).one_or_none()

    def save_schedule(self, schedule: Schedule) -> Schedule:
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def delete_schedule(self, schedule: Schedule) -> None:
        self.db.delete(schedule)
        self.db.commit()

    def create_query_history(self, entry: QueryHistory) -> QueryHistory:
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_query_history(self, user_id: UUID) -> list[QueryHistory]:
        return (
            self.db.query(QueryHistory)
            .filter(QueryHistory.user_id == user_id)
            .order_by(QueryHistory.created_at.desc())
            .limit(50)
            .all()
        )

    def get_history_item(self, history_id: UUID, user_id: UUID) -> QueryHistory | None:
        return (
            self.db.query(QueryHistory)
            .filter(QueryHistory.id == history_id, QueryHistory.user_id == user_id)
            .one_or_none()
        )

    def delete_history_item(self, entry: QueryHistory) -> None:
        self.db.delete(entry)
        self.db.commit()

    def clear_history(self, user_id: UUID) -> int:
        deleted = self.db.query(QueryHistory).filter(QueryHistory.user_id == user_id).delete()
        self.db.commit()
        return deleted

    def list_query_examples(self, user_id: UUID) -> list[UserQueryExample]:
        return (
            self.db.query(UserQueryExample)
            .filter(UserQueryExample.user_id == user_id)
            .order_by(UserQueryExample.is_pinned.desc(), UserQueryExample.updated_at.desc())
            .all()
        )

    def find_query_example(self, user_id: UUID, text: str) -> UserQueryExample | None:
        return (
            self.db.query(UserQueryExample)
            .filter(UserQueryExample.user_id == user_id)
            .filter(func.lower(UserQueryExample.text) == text.strip().lower())
            .one_or_none()
        )

    def create_query_example(self, example: UserQueryExample) -> UserQueryExample:
        self.db.add(example)
        self.db.commit()
        self.db.refresh(example)
        return example

    def save_query_example(self, example: UserQueryExample) -> UserQueryExample:
        self.db.add(example)
        self.db.commit()
        self.db.refresh(example)
        return example

    def get_query_example(self, example_id: UUID, user_id: UUID) -> UserQueryExample | None:
        return (
            self.db.query(UserQueryExample)
            .filter(UserQueryExample.id == example_id, UserQueryExample.user_id == user_id)
            .one_or_none()
        )

    def delete_query_example(self, example: UserQueryExample) -> None:
        self.db.delete(example)
        self.db.commit()
