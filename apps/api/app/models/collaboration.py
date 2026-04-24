import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WorkspaceMemberRole(str, enum.Enum):
    owner = "owner"
    manager = "manager"
    member = "member"
    viewer = "viewer"


class WorkspaceGroup(Base):
    __tablename__ = "workspace_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    memberships: Mapped[list["WorkspaceGroupMember"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["WorkspaceMessage"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )
    report_shares: Mapped[list["ReportShare"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )


class WorkspaceGroupMember(Base):
    __tablename__ = "workspace_group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_workspace_group_member"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace_groups.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[WorkspaceMemberRole] = mapped_column(
        Enum(WorkspaceMemberRole, name="workspace_member_role"),
        nullable=False,
        default=WorkspaceMemberRole.member,
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group: Mapped["WorkspaceGroup"] = relationship(back_populates="memberships")


class WorkspaceMessage(Base):
    __tablename__ = "workspace_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace_groups.id"), nullable=False, index=True)
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group: Mapped["WorkspaceGroup"] = relationship(back_populates="messages")
