from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.report import ScheduleRequest, ScheduleSummary
from app.scheduler.runner import scheduler_runner
from app.services.report_service import ReportService

router = APIRouter()


@router.get("", response_model=list[ScheduleSummary])
def list_schedules(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = ReportService(db).list_schedules(user)
    return [ScheduleSummary.model_validate(item, from_attributes=True) for item in items]


@router.post("/report/{report_id}", response_model=ScheduleSummary)
def create_schedule(
    report_id: UUID,
    payload: ScheduleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = ReportService(db)
    report = service.get_report_for_user(report_id, user)
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    if not service.can_manage_report(report, user):
        raise HTTPException(status_code=403, detail="Нет прав создавать расписание для этого отчёта")
    schedule = service.create_schedule(report, payload, user)
    scheduler_runner.reload()
    return ScheduleSummary.model_validate(schedule, from_attributes=True)


@router.delete("/{schedule_id}", response_model=MessageResponse)
def delete_schedule(
    schedule_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = ReportService(db)
    schedule = service.repo.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Расписание не найдено")
    report = service.get_report_for_user(schedule.report_id, user)
    if not report:
        raise HTTPException(status_code=404, detail="Расписание не найдено")
    if not service.can_manage_report(report, user):
        raise HTTPException(status_code=403, detail="Нет прав удалять это расписание")
    service.delete_schedule(schedule, user.id)
    scheduler_runner.reload()
    return MessageResponse(message="Расписание удалено")
