from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class SaveReportRequest(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    question: str
    query_plan_json: dict[str, Any]
    sql_text: str
    chart_type: str | None = None
    row_count: int = 0
    result_preview_json: dict[str, Any] = Field(default_factory=dict)
    execution_status: str = "executed"


class UpdateReportRequest(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class ScheduleRequest(BaseModel):
    cron_expression: str
    timezone: str = "Europe/Kaliningrad"
    recipient: str | None = None
    channel: str = "email"
    target_group_id: UUID | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_delivery_target(self):
        if self.channel == "group" and not self.target_group_id:
            raise ValueError("Для отправки в группу нужно выбрать рабочую группу")
        if self.channel != "group" and not self.recipient:
            raise ValueError("Нужно указать получателя")
        return self


class ShareReportToGroupRequest(BaseModel):
    group_id: UUID
    note: str | None = Field(default=None, max_length=2000)


class ReportSummary(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    question: str
    chart_type: str | None
    query_plan_json: dict[str, Any] = Field(default_factory=dict)
    last_run_status: str | None = None
    last_run_at: datetime | None = None
    last_run_row_count: int | None = None
    result_preview_json: dict[str, Any] = Field(default_factory=dict)
    runs_count: int = 0
    schedules_count: int = 0
    shares_count: int = 0
    created_at: datetime
    updated_at: datetime


class ScheduleSummary(BaseModel):
    id: UUID
    report_id: UUID
    cron_expression: str
    timezone: str
    recipient: str
    channel: str
    target_group_id: UUID | None
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None


class ReportShareSummary(BaseModel):
    id: UUID
    group_id: UUID
    group_name: str
    shared_by_user_id: UUID
    shared_by_name: str
    note: str | None
    created_at: datetime


class ReportRunSummary(BaseModel):
    id: UUID
    trigger_source: str
    status: str
    row_count: int
    executed_at: datetime
    result_preview_json: dict[str, Any]


class ReportDetail(ReportSummary):
    query_plan_json: dict[str, Any]
    sql_text: str
    schedules: list[ScheduleSummary]
    runs: list[ReportRunSummary]
    shares: list[ReportShareSummary] = Field(default_factory=list)
