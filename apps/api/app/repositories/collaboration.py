from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.collaboration import WorkspaceGroup, WorkspaceGroupMember, WorkspaceMessage


class CollaborationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_groups_for_user(self, user_id: UUID, is_admin: bool = False) -> list[WorkspaceGroup]:
        query = self.db.query(WorkspaceGroup).options(joinedload(WorkspaceGroup.memberships)).order_by(WorkspaceGroup.updated_at.desc())
        if not is_admin:
            query = query.join(WorkspaceGroupMember).filter(WorkspaceGroupMember.user_id == user_id)
        return query.distinct().all()

    def get_group(self, group_id: UUID) -> WorkspaceGroup | None:
        return (
            self.db.query(WorkspaceGroup)
            .options(joinedload(WorkspaceGroup.memberships), joinedload(WorkspaceGroup.messages))
            .filter(WorkspaceGroup.id == group_id)
            .one_or_none()
        )

    def create_group(self, group: WorkspaceGroup) -> WorkspaceGroup:
        self.db.add(group)
        self.db.commit()
        self.db.refresh(group)
        return group

    def save_group(self, group: WorkspaceGroup) -> WorkspaceGroup:
        self.db.add(group)
        self.db.commit()
        self.db.refresh(group)
        return group

    def delete_group(self, group: WorkspaceGroup) -> None:
        self.db.delete(group)
        self.db.commit()

    def get_membership(self, group_id: UUID, user_id: UUID) -> WorkspaceGroupMember | None:
        return (
            self.db.query(WorkspaceGroupMember)
            .filter(WorkspaceGroupMember.group_id == group_id, WorkspaceGroupMember.user_id == user_id)
            .one_or_none()
        )

    def add_membership(self, membership: WorkspaceGroupMember) -> WorkspaceGroupMember:
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def save_membership(self, membership: WorkspaceGroupMember) -> WorkspaceGroupMember:
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def delete_membership(self, membership: WorkspaceGroupMember) -> None:
        self.db.delete(membership)
        self.db.commit()

    def create_message(self, message: WorkspaceMessage) -> WorkspaceMessage:
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_messages(self, group_id: UUID, limit: int = 150) -> list[WorkspaceMessage]:
        return (
            self.db.query(WorkspaceMessage)
            .filter(WorkspaceMessage.group_id == group_id)
            .order_by(WorkspaceMessage.created_at.asc())
            .limit(limit)
            .all()
        )

    def count_members(self, group_id: UUID) -> int:
        return (
            self.db.query(func.count(WorkspaceGroupMember.id))
            .filter(WorkspaceGroupMember.group_id == group_id)
            .scalar()
            or 0
        )
