from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GroupCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    is_private: bool = True


class GroupUpdateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    is_private: bool = True


class GroupMemberUpsertRequest(BaseModel):
    user_id: UUID
    role: str


class GroupMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class GroupMemberSummary(BaseModel):
    id: UUID
    user_id: UUID
    role: str
    full_name: str
    email: str
    joined_at: datetime


class GroupMessageSummary(BaseModel):
    id: UUID
    author_user_id: UUID
    author_name: str
    body: str
    payload_json: dict = Field(default_factory=dict)
    created_at: datetime


class GroupSharedReportSummary(BaseModel):
    id: UUID
    report_id: UUID
    report_name: str
    report_description: str | None
    report_question: str
    chart_type: str | None
    owner_name: str
    shared_by_name: str
    metric_labels: list[str] = Field(default_factory=list)
    period_label: str | None = None
    last_run_status: str | None = None
    last_run_at: datetime | None = None
    last_run_row_count: int | None = None
    preview_json: dict = Field(default_factory=dict)
    query_plan_json: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class GroupSummary(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_private: bool
    created_at: datetime
    updated_at: datetime
    member_count: int = 0
    current_user_role: str | None = None


class GroupDetail(GroupSummary):
    members: list[GroupMemberSummary]
    messages: list[GroupMessageSummary]
    shared_reports: list[GroupSharedReportSummary] = Field(default_factory=list)
