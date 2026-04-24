from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.report import Schedule
from app.repositories.reports import ReportRepository
from app.services.schedule_service import ScheduleService


class SchedulerRunner:
    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)

    def start(self) -> None:
        if self.scheduler.running:
            return
        self._load_jobs()
        self.scheduler.start()

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def reload(self) -> None:
        self.scheduler.remove_all_jobs()
        self._load_jobs()

    def _load_jobs(self) -> None:
        db: Session = SessionLocal()
        try:
            schedules = ReportRepository(db).list_schedules()
            for schedule in schedules:
                if schedule.is_active:
                    self.scheduler.add_job(
                        self._run_schedule_job,
                        trigger=CronTrigger.from_crontab(schedule.cron_expression, timezone=schedule.timezone),
                        kwargs={"schedule_id": str(schedule.id)},
                        id=str(schedule.id),
                        replace_existing=True,
                    )
        finally:
            db.close()

    def _run_schedule_job(self, schedule_id: str) -> None:
        db: Session = SessionLocal()
        try:
            ScheduleService(db).fire_schedule(schedule_id)
        finally:
            db.close()


scheduler_runner = SchedulerRunner()

