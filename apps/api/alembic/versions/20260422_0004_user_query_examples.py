from __future__ import annotations

"""add user managed query examples

Revision ID: 20260422_0004
Revises: 20260422_0003
Create Date: 2026-04-22 23:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260422_0004"
down_revision = "20260422_0003"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "user_query_examples"):
        op.create_table(
            "user_query_examples",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "text", name="uq_user_query_examples_user_text"),
        )
        op.create_index("ix_user_query_examples_user_id", "user_query_examples", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, "user_query_examples"):
        if _has_index(inspector, "user_query_examples", "ix_user_query_examples_user_id"):
            op.drop_index("ix_user_query_examples_user_id", table_name="user_query_examples")
        op.drop_table("user_query_examples")
