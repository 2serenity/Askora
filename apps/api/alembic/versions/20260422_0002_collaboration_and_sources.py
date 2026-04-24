"""collaboration and sources

Revision ID: 20260422_0002
Revises: 20260422_0001
Create Date: 2026-04-22 20:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260422_0002"
down_revision = "20260422_0001"
branch_labels = None
depends_on = None


workspace_member_role = postgresql.ENUM(
    "owner",
    "manager",
    "member",
    "viewer",
    name="workspace_member_role",
    create_type=False,
)


def upgrade() -> None:
    workspace_member_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("dialect", sa.String(length=40), nullable=False),
        sa.Column("connection_url", sa.Text(), nullable=False),
        sa.Column("schema_name", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allowed_roles_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("capabilities_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("key", name="uq_data_sources_key"),
    )
    op.create_index("ix_data_sources_key", "data_sources", ["key"], unique=False)

    op.create_table(
        "workspace_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workspace_groups_created_by_user_id", "workspace_groups", ["created_by_user_id"], unique=False)

    op.create_table(
        "workspace_group_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspace_groups.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", workspace_member_role, nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "user_id", name="uq_workspace_group_member"),
    )
    op.create_index("ix_workspace_group_members_group_id", "workspace_group_members", ["group_id"], unique=False)
    op.create_index("ix_workspace_group_members_user_id", "workspace_group_members", ["user_id"], unique=False)

    op.create_table(
        "workspace_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspace_groups.id"), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workspace_messages_group_id", "workspace_messages", ["group_id"], unique=False)
    op.create_index("ix_workspace_messages_author_user_id", "workspace_messages", ["author_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_workspace_messages_author_user_id", table_name="workspace_messages")
    op.drop_index("ix_workspace_messages_group_id", table_name="workspace_messages")
    op.drop_table("workspace_messages")

    op.drop_index("ix_workspace_group_members_user_id", table_name="workspace_group_members")
    op.drop_index("ix_workspace_group_members_group_id", table_name="workspace_group_members")
    op.drop_table("workspace_group_members")

    op.drop_index("ix_workspace_groups_created_by_user_id", table_name="workspace_groups")
    op.drop_table("workspace_groups")

    op.drop_index("ix_data_sources_key", table_name="data_sources")
    op.drop_table("data_sources")

    workspace_member_role.drop(op.get_bind(), checkfirst=True)
