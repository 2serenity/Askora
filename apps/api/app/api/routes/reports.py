from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.report import QueryStatus
from app.models.user import User
from app.repositories.collaboration import CollaborationRepository
from app.repositories.users import UserRepository
from app.schemas.common import MessageResponse
from app.schemas.query import QueryRequest, QueryResult
from app.schemas.report import (
    ReportDetail,
    ReportRunSummary,
    ReportShareSummary,
    ReportSummary,
    SaveReportRequest,
    ScheduleSummary,
    ShareReportToGroupRequest,
    UpdateReportRequest,
)
from app.services.query_service import QueryService
from app.services.report_service import ReportService

router = APIRouter()


def _report_to_summary(report) -> ReportSummary:
    latest_run = max(report.runs, key=lambda item: item.executed_at) if report.runs else None
    return ReportSummary(
        id=report.id,
        owner_id=report.owner_id,
        name=report.name,
        description=report.description,
        question=report.question,
        chart_type=report.chart_type,
        query_plan_json=report.query_plan_json if isinstance(report.query_plan_json, dict) else {},
        last_run_status=latest_run.status.value if latest_run else None,
        last_run_at=latest_run.executed_at if latest_run else None,
        last_run_row_count=latest_run.row_count if latest_run else None,
        result_preview_json=latest_run.result_preview_json if latest_run and isinstance(latest_run.result_preview_json, dict) else {},
        runs_count=len(report.runs),
        schedules_count=len(report.schedules),
        shares_count=len(report.shares),
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def _build_share_summaries(db: Session, report) -> list[ReportShareSummary]:
    users = UserRepository(db)
    groups = CollaborationRepository(db)
    summaries: list[ReportShareSummary] = []
    for item in report.shares:
        author = users.get_by_id(item.shared_by_user_id)
        group = groups.get_group(item.group_id)
        if not author or not group:
            continue
        summaries.append(
            ReportShareSummary(
                id=item.id,
                group_id=item.group_id,
                group_name=group.name,
                shared_by_user_id=item.shared_by_user_id,
                shared_by_name=author.full_name,
                note=item.note,
                created_at=item.created_at,
            )
        )
    return summaries


@router.get("", response_model=list[ReportSummary])
def list_reports(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = ReportService(db).list_reports(user)
    return [_report_to_summary(item) for item in items]


@router.get("/shared", response_model=list[ReportSummary])
def list_shared_reports(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = ReportService(db).list_shared_reports(user)
    return [_report_to_summary(item) for item in items]


@router.post("", response_model=ReportSummary, status_code=status.HTTP_201_CREATED)
def save_report(payload: SaveReportRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = ReportService(db)
    report = service.save_report(user, payload)
    report = service.get_report_for_user(report.id, user) or report
    return _report_to_summary(report)


@router.get("/{report_id}", response_model=ReportDetail)
def get_report(report_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = ReportService(db)
    report = service.get_report_for_user(report_id, user)
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    summary = _report_to_summary(report)
    return ReportDetail(
        **summary.model_dump(),
        sql_text=report.sql_text,
        schedules=[ScheduleSummary.model_validate(item, from_attributes=True) for item in report.schedules],
        runs=[ReportRunSummary.model_validate(item, from_attributes=True) for item in report.runs],
        shares=_build_share_summaries(db, report),
    )


@router.put("/{report_id}", response_model=ReportSummary)
def update_report(
    report_id: UUID,
    payload: UpdateReportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = ReportService(db)
    report = service.get_report_for_user(report_id, user)
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    if not service.can_manage_report(report, user):
        raise HTTPException(status_code=403, detail="Нет прав изменять этот отчёт")
    updated = service.update_report(report, payload)
    updated = service.get_report_for_user(updated.id, user) or updated
    return _report_to_summary(updated)


@router.delete("/{report_id}", response_model=MessageResponse)
def delete_report(report_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = ReportService(db)
    report = service.get_report_for_user(report_id, user)
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    if not service.can_manage_report(report, user):
        raise HTTPException(status_code=403, detail="Нет прав удалять этот отчёт")
    service.delete_report(report, user.id)
    return MessageResponse(message="Отчёт удалён")


@router.post("/{report_id}/rerun", response_model=QueryResult)
def rerun_report(report_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    report_service = ReportService(db)
    report = report_service.get_report_for_user(report_id, user)
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")

    result = QueryService(db).run(QueryRequest(question=report.question), user)
    report_service.create_run(
        report,
        triggered_by_user_id=user.id,
        trigger_source="manual_rerun",
        status=QueryStatus.executed if result.status == "executed" else QueryStatus.failed,
        row_count=result.row_count,
        result_preview_json={"rows": result.rows[:10], "columns": result.columns},
    )
    return result


@router.post("/{report_id}/share/group", response_model=MessageResponse)
def share_report_to_group(
    report_id: UUID,
    payload: ShareReportToGroupRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = ReportService(db)
    report = service.get_report_for_user(report_id, user)
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    if not service.can_manage_report(report, user):
        raise HTTPException(status_code=403, detail="Нет прав публиковать этот отчёт")
    service.share_report_to_group(report, payload.group_id, user, note=payload.note, publish_message=True)
    return MessageResponse(message="Отчёт опубликован в рабочей группе")
