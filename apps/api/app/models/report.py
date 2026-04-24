import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QueryStatus(str, enum.Enum):
    draft = "draft"
    needs_clarification = "needs_clarification"
    blocked = "blocked"
    executed = "executed"
    failed = "failed"


class ScheduleChannel(str, enum.Enum):
    email = "email"
    inbox = "inbox"
    group = "group"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    query_plan_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    chart_type: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped["User"] = relationship(back_populates="reports")
    runs: Mapped[list["ReportRun"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    shares: Mapped[list["ReportShare"]] = relationship(back_populates="report", cascade="all, delete-orphan")


class QueryHistory(Base):
    __tablename__ = "query_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    query_plan_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    validation_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result_preview_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    chart_type: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(nullable=False, default=0)
    status: Mapped[QueryStatus] = mapped_column(Enum(QueryStatus, name="query_status"), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportRun(Base):
    __tablename__ = "report_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id"), nullable=False, index=True)
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    trigger_source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    status: Mapped[QueryStatus] = mapped_column(Enum(QueryStatus, name="report_run_status"), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_preview_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    report: Mapped[Report] = relationship(back_populates="runs")


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id"), nullable=False, index=True)
    cron_expression: Mapped[str] = mapped_column(String(120), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    channel: Mapped[ScheduleChannel] = mapped_column(
        Enum(ScheduleChannel, name="schedule_channel"),
        nullable=False,
        default=ScheduleChannel.email,
    )
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    target_group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspace_groups.id"), nullable=True, index=True)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    report: Mapped[Report] = relationship(back_populates="schedules")
    target_group: Mapped["WorkspaceGroup | None"] = relationship("WorkspaceGroup")


class ReportShare(Base):
    __tablename__ = "report_shares"
    __table_args__ = (UniqueConstraint("report_id", "group_id", name="uq_report_share_report_group"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id"), nullable=False, index=True)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace_groups.id"), nullable=False, index=True)
    shared_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    report: Mapped[Report] = relationship(back_populates="shares")
    group: Mapped["WorkspaceGroup"] = relationship("WorkspaceGroup", back_populates="report_shares")


class UserQueryExample(Base):
    __tablename__ = "user_query_examples"
    __table_args__ = (UniqueConstraint("user_id", "text", name="uq_user_query_examples_user_text"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
