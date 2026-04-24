from __future__ import annotations

"""schema alignment for users, schedules and shares

Revision ID: 20260422_0003
Revises: 20260422_0002
Create Date: 2026-04-22 22:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260422_0003"
down_revision = "20260422_0002"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _has_fk(inspector: sa.Inspector, table_name: str, fk_name: str) -> bool:
    return any((fk.get("name") or "") == fk_name for fk in inspector.get_foreign_keys(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "users"):
        if not _has_column(inspector, "users", "timezone"):
            op.add_column("users", sa.Column("timezone", sa.String(length=64), nullable=True))
            op.execute("UPDATE users SET timezone = 'Europe/Kaliningrad' WHERE timezone IS NULL")
            op.alter_column("users", "timezone", existing_type=sa.String(length=64), nullable=False)

        if not _has_column(inspector, "users", "locale"):
            op.add_column("users", sa.Column("locale", sa.String(length=16), nullable=True))
            op.execute("UPDATE users SET locale = 'ru-RU' WHERE locale IS NULL")
            op.alter_column("users", "locale", existing_type=sa.String(length=16), nullable=False)

        if not _has_column(inspector, "users", "preferences_json"):
            op.add_column(
                "users",
                sa.Column(
                    "preferences_json",
                    postgresql.JSONB(astext_type=sa.Text()),
                    nullable=False,
                    server_default=sa.text("'{}'::jsonb"),
                ),
            )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'schedule_channel'
                  AND e.enumlabel = 'group'
            ) THEN
                ALTER TYPE schedule_channel ADD VALUE 'group';
            END IF;
        END
        $$;
        """
    )

    inspector = sa.inspect(bind)
    if _has_table(inspector, "schedules"):
        if not _has_column(inspector, "schedules", "target_group_id"):
            op.add_column("schedules", sa.Column("target_group_id", postgresql.UUID(as_uuid=True), nullable=True))

        inspector = sa.inspect(bind)
        if not _has_index(inspector, "schedules", "ix_schedules_target_group_id"):
            op.create_index("ix_schedules_target_group_id", "schedules", ["target_group_id"], unique=False)

        inspector = sa.inspect(bind)
        if _has_table(inspector, "workspace_groups") and not _has_fk(inspector, "schedules", "fk_schedules_target_group_id"):
            op.create_foreign_key(
                "fk_schedules_target_group_id",
                "schedules",
                "workspace_groups",
                ["target_group_id"],
                ["id"],
            )

    inspector = sa.inspect(bind)
    if not _has_table(inspector, "report_shares"):
        op.create_table(
            "report_shares",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reports.id"), nullable=False),
            sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspace_groups.id"), nullable=False),
            sa.Column("shared_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("report_id", "group_id", name="uq_report_share_report_group"),
        )
        op.create_index("ix_report_shares_report_id", "report_shares", ["report_id"], unique=False)
        op.create_index("ix_report_shares_group_id", "report_shares", ["group_id"], unique=False)
        op.create_index("ix_report_shares_shared_by_user_id", "report_shares", ["shared_by_user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "report_shares"):
        if _has_index(inspector, "report_shares", "ix_report_shares_shared_by_user_id"):
            op.drop_index("ix_report_shares_shared_by_user_id", table_name="report_shares")
        if _has_index(inspector, "report_shares", "ix_report_shares_group_id"):
            op.drop_index("ix_report_shares_group_id", table_name="report_shares")
        if _has_index(inspector, "report_shares", "ix_report_shares_report_id"):
            op.drop_index("ix_report_shares_report_id", table_name="report_shares")
        op.drop_table("report_shares")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "schedules"):
        if _has_fk(inspector, "schedules", "fk_schedules_target_group_id"):
            op.drop_constraint("fk_schedules_target_group_id", "schedules", type_="foreignkey")
        if _has_index(inspector, "schedules", "ix_schedules_target_group_id"):
            op.drop_index("ix_schedules_target_group_id", table_name="schedules")
        if _has_column(inspector, "schedules", "target_group_id"):
            op.drop_column("schedules", "target_group_id")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "users"):
        if _has_column(inspector, "users", "preferences_json"):
            op.drop_column("users", "preferences_json")
        if _has_column(inspector, "users", "locale"):
            op.drop_column("users", "locale")
        if _has_column(inspector, "users", "timezone"):
            op.drop_column("users", "timezone")
