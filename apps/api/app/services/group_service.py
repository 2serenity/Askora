from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.collaboration import WorkspaceGroup, WorkspaceGroupMember, WorkspaceMemberRole, WorkspaceMessage
from app.models.user import User
from app.repositories.collaboration import CollaborationRepository
from app.repositories.reports import ReportRepository
from app.repositories.users import UserRepository
from app.schemas.group import GroupCreateRequest, GroupUpdateRequest
from app.services.audit_service import AuditService


class GroupService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CollaborationRepository(db)
        self.reports = ReportRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditService(db)

    def list_groups(self, user: User) -> list[WorkspaceGroup]:
        return self.repo.list_groups_for_user(user.id, is_admin=user.role.value == "admin")

    def get_group_for_user(self, group_id: UUID, user: User) -> WorkspaceGroup | None:
        group = self.repo.get_group(group_id)
        if not group:
            return None
        if user.role.value == "admin":
            return group
        membership = self.repo.get_membership(group_id, user.id)
        return group if membership else None

    def create_group(self, payload: GroupCreateRequest, user: User) -> WorkspaceGroup:
        group = WorkspaceGroup(
            name=payload.name,
            description=payload.description,
            is_private=payload.is_private,
            created_by_user_id=user.id,
        )
        saved = self.repo.create_group(group)
        self.repo.add_membership(
            WorkspaceGroupMember(
                group_id=saved.id,
                user_id=user.id,
                role=WorkspaceMemberRole.owner,
            )
        )
        self.audit.log(
            actor_user_id=user.id,
            event_type="group_created",
            status="success",
            extra_json={"group_id": str(saved.id), "group_name": saved.name},
        )
        return self.repo.get_group(saved.id) or saved

    def update_group(self, group: WorkspaceGroup, payload: GroupUpdateRequest, user: User) -> WorkspaceGroup:
        self._require_manage_access(group.id, user)
        group.name = payload.name
        group.description = payload.description
        group.is_private = payload.is_private
        saved = self.repo.save_group(group)
        self.audit.log(
            actor_user_id=user.id,
            event_type="group_updated",
            status="success",
            extra_json={"group_id": str(group.id)},
        )
        return saved

    def delete_group(self, group: WorkspaceGroup, user: User) -> None:
        self._require_manage_access(group.id, user)
        self.repo.delete_group(group)
        self.audit.log(
            actor_user_id=user.id,
            event_type="group_deleted",
            status="success",
            extra_json={"group_id": str(group.id)},
        )

    def add_or_update_member(self, group: WorkspaceGroup, target_user_id: UUID, role: str, actor: User) -> WorkspaceGroupMember:
        self._require_manage_access(group.id, actor)
        target_user = self.users.get_by_id(target_user_id)
        if not target_user or not target_user.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

        membership = self.repo.get_membership(group.id, target_user_id)
        if membership:
            membership.role = WorkspaceMemberRole(role)
            saved = self.repo.save_membership(membership)
            event_type = "group_member_updated"
        else:
            saved = self.repo.add_membership(
                WorkspaceGroupMember(group_id=group.id, user_id=target_user_id, role=WorkspaceMemberRole(role))
            )
            event_type = "group_member_added"

        self.audit.log(
            actor_user_id=actor.id,
            event_type=event_type,
            status="success",
            extra_json={"group_id": str(group.id), "target_user_id": str(target_user_id), "role": role},
        )
        return saved

    def remove_member(self, group: WorkspaceGroup, target_user_id: UUID, actor: User) -> None:
        self._require_manage_access(group.id, actor)
        membership = self.repo.get_membership(group.id, target_user_id)
        if not membership:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Участник группы не найден")
        if membership.role == WorkspaceMemberRole.owner and actor.role.value != "admin":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя удалить владельца группы")
        self.repo.delete_membership(membership)
        self.audit.log(
            actor_user_id=actor.id,
            event_type="group_member_removed",
            status="success",
            extra_json={"group_id": str(group.id), "target_user_id": str(target_user_id)},
        )

    def list_messages(self, group_id: UUID, user: User):
        group = self.get_group_for_user(group_id, user)
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Группа не найдена")
        return self.repo.list_messages(group_id)

    def post_message(self, group: WorkspaceGroup, body: str, actor: User) -> WorkspaceMessage:
        self._require_post_access(group.id, actor)
        message = WorkspaceMessage(group_id=group.id, author_user_id=actor.id, body=body.strip())
        saved = self.repo.create_message(message)
        self.audit.log(
            actor_user_id=actor.id,
            event_type="group_message_posted",
            status="success",
            extra_json={"group_id": str(group.id), "message_id": str(saved.id)},
        )
        return saved

    def list_shared_reports(self, group_id: UUID, user: User):
        group = self.get_group_for_user(group_id, user)
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Группа не найдена")
        return self.reports.list_group_shared_reports(group_id)

    def _require_manage_access(self, group_id: UUID, actor: User) -> None:
        if actor.role.value == "admin":
            return
        membership = self.repo.get_membership(group_id, actor.id)
        if not membership or membership.role not in {WorkspaceMemberRole.owner, WorkspaceMemberRole.manager}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для управления группой")

    def _require_post_access(self, group_id: UUID, actor: User) -> None:
        if actor.role.value == "admin":
            return
        membership = self.repo.get_membership(group_id, actor.id)
        if not membership or membership.role == WorkspaceMemberRole.viewer:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="У вас нет права писать в этой группе")
