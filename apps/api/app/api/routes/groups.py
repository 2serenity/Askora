from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.common import MessageResponse, UserSummary
from app.schemas.group import (
    GroupCreateRequest,
    GroupDetail,
    GroupMemberSummary,
    GroupMemberUpsertRequest,
    GroupMessageRequest,
    GroupMessageSummary,
    GroupSharedReportSummary,
    GroupSummary,
    GroupUpdateRequest,
)
from app.services.group_service import GroupService

router = APIRouter()


def _group_to_summary(group, user: User) -> GroupSummary:
    current_membership = next((item for item in group.memberships if item.user_id == user.id), None)
    return GroupSummary(
        id=group.id,
        name=group.name,
        description=group.description,
        is_private=group.is_private,
        created_at=group.created_at,
        updated_at=group.updated_at,
        member_count=len(group.memberships),
        current_user_role=current_membership.role.value if current_membership else ("admin" if user.role.value == "admin" else None),
    )


def _member_to_summary(member, users_by_id: dict[str, User]) -> GroupMemberSummary:
    user = users_by_id[str(member.user_id)]
    return GroupMemberSummary(
        id=member.id,
        user_id=member.user_id,
        role=member.role.value,
        full_name=user.full_name,
        email=user.email,
        joined_at=member.joined_at,
    )


def _message_to_summary(message, users_by_id: dict[str, User]) -> GroupMessageSummary:
    author = users_by_id[str(message.author_user_id)]
    return GroupMessageSummary(
        id=message.id,
        author_user_id=message.author_user_id,
        author_name=author.full_name,
        body=message.body,
        payload_json=message.payload_json,
        created_at=message.created_at,
    )


def _share_to_summary(share, users_by_id: dict[str, User]) -> GroupSharedReportSummary | None:
    author = users_by_id.get(str(share.shared_by_user_id))
    if not author or not share.report:
        return None
    last_run = max(share.report.runs, key=lambda item: item.executed_at) if share.report.runs else None
    metrics = share.report.query_plan_json.get("metrics", []) if isinstance(share.report.query_plan_json, dict) else []
    metric_labels = [item.get("label", item.get("key", "")) for item in metrics if isinstance(item, dict)]
    time_range = share.report.query_plan_json.get("time_range", {}) if isinstance(share.report.query_plan_json, dict) else {}
    period_label = time_range.get("label") if isinstance(time_range, dict) else None
    return GroupSharedReportSummary(
        id=share.id,
        report_id=share.report_id,
        report_name=share.report.name,
        report_description=share.report.description,
        report_question=share.report.question,
        chart_type=share.report.chart_type,
        owner_name=share.report.owner.full_name if share.report.owner else "Неизвестный владелец",
        shared_by_name=author.full_name,
        metric_labels=[label for label in metric_labels if label],
        period_label=period_label,
        last_run_status=last_run.status.value if last_run else None,
        last_run_at=last_run.executed_at if last_run else None,
        last_run_row_count=last_run.row_count if last_run else None,
        preview_json=last_run.result_preview_json if last_run and isinstance(last_run.result_preview_json, dict) else {},
        query_plan_json=share.report.query_plan_json if isinstance(share.report.query_plan_json, dict) else {},
        created_at=share.created_at,
        updated_at=share.report.updated_at,
    )


@router.get("", response_model=list[GroupSummary])
def list_groups(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    groups = GroupService(db).list_groups(user)
    return [_group_to_summary(group, user) for group in groups]


@router.post("", response_model=GroupDetail)
def create_group(payload: GroupCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = GroupService(db)
    group = service.create_group(payload, user)
    users_by_id = {str(user.id): user}
    return GroupDetail(
        **_group_to_summary(group, user).model_dump(),
        members=[
            GroupMemberSummary(
                id=membership.id,
                user_id=membership.user_id,
                role=membership.role.value,
                full_name=user.full_name,
                email=user.email,
                joined_at=membership.joined_at,
            )
            for membership in group.memberships
        ],
        messages=[],
        shared_reports=[],
    )


@router.get("/users/available", response_model=list[UserSummary])
def list_available_users(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    items = GroupService(db).users.list_active()
    return [UserSummary.model_validate(item, from_attributes=True) for item in items]


@router.get("/{group_id}", response_model=GroupDetail)
def get_group(group_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = GroupService(db)
    group = service.get_group_for_user(group_id, user)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    shared_reports = service.list_shared_reports(group_id, user)

    user_ids = {str(membership.user_id) for membership in group.memberships}
    user_ids.update({str(message.author_user_id) for message in group.messages})
    user_ids.update({str(item.shared_by_user_id) for item in shared_reports})
    users_by_id = {}
    for user_id in user_ids:
        author = service.users.get_by_id(user_id)
        if author:
            users_by_id[str(author.id)] = author

    share_summaries = []
    for share in shared_reports:
        summary = _share_to_summary(share, users_by_id)
        if summary:
            share_summaries.append(summary)

    return GroupDetail(
        **_group_to_summary(group, user).model_dump(),
        members=[_member_to_summary(member, users_by_id) for member in group.memberships if str(member.user_id) in users_by_id],
        messages=[_message_to_summary(message, users_by_id) for message in service.repo.list_messages(group.id) if str(message.author_user_id) in users_by_id],
        shared_reports=share_summaries,
    )


@router.put("/{group_id}", response_model=GroupSummary)
def update_group(
    group_id: UUID,
    payload: GroupUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = GroupService(db)
    group = service.get_group_for_user(group_id, user)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    updated = service.update_group(group, payload, user)
    updated = service.get_group_for_user(updated.id, user) or updated
    return _group_to_summary(updated, user)


@router.delete("/{group_id}", response_model=MessageResponse)
def delete_group(group_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = GroupService(db)
    group = service.get_group_for_user(group_id, user)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    service.delete_group(group, user)
    return MessageResponse(message="Группа удалена")


@router.post("/{group_id}/members", response_model=MessageResponse)
def add_member(
    group_id: UUID,
    payload: GroupMemberUpsertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = GroupService(db)
    group = service.get_group_for_user(group_id, user)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    service.add_or_update_member(group, payload.user_id, payload.role, user)
    return MessageResponse(message="Участник группы сохранён")


@router.delete("/{group_id}/members/{member_user_id}", response_model=MessageResponse)
def remove_member(
    group_id: UUID,
    member_user_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = GroupService(db)
    group = service.get_group_for_user(group_id, user)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    service.remove_member(group, member_user_id, user)
    return MessageResponse(message="Участник удалён из группы")


@router.get("/{group_id}/messages", response_model=list[GroupMessageSummary])
def list_messages(group_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = GroupService(db)
    group = service.get_group_for_user(group_id, user)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    messages = service.repo.list_messages(group_id)
    user_ids = {str(message.author_user_id) for message in messages}
    users_by_id = {}
    for user_id in user_ids:
        author = service.users.get_by_id(user_id)
        if author:
            users_by_id[str(author.id)] = author
    return [_message_to_summary(message, users_by_id) for message in messages if str(message.author_user_id) in users_by_id]


@router.post("/{group_id}/messages", response_model=GroupMessageSummary)
def post_message(
    group_id: UUID,
    payload: GroupMessageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = GroupService(db)
    group = service.get_group_for_user(group_id, user)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    message = service.post_message(group, payload.body, user)
    return GroupMessageSummary(
        id=message.id,
        author_user_id=message.author_user_id,
        author_name=user.full_name,
        body=message.body,
        payload_json=message.payload_json,
        created_at=message.created_at,
    )
