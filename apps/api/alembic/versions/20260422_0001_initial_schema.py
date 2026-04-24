"""initial schema

Revision ID: 20260422_0001
Revises:
Create Date: 2026-04-22 12:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260422_0001"
down_revision = None
branch_labels = None
depends_on = None


user_role = postgresql.ENUM("admin", "analyst", "business_user", name="user_role", create_type=False)
order_status = postgresql.ENUM("created", "assigned", "in_progress", "completed", "cancelled", name="order_status", create_type=False)
tender_status = postgresql.ENUM("opened", "matched", "expired", "cancelled", name="tender_status", create_type=False)
cancellation_actor = postgresql.ENUM("customer", "driver", "system", "unknown", name="cancellation_actor", create_type=False)
query_status = postgresql.ENUM("draft", "needs_clarification", "blocked", "executed", "failed", name="query_status", create_type=False)
report_run_status = postgresql.ENUM("draft", "needs_clarification", "blocked", "executed", "failed", name="report_run_status", create_type=False)
schedule_channel = postgresql.ENUM("email", "inbox", name="schedule_channel", create_type=False)
template_owner_role = postgresql.ENUM("admin", "analyst", "business_user", name="template_owner_role", create_type=False)


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics")

    user_role.create(op.get_bind(), checkfirst=True)
    order_status.create(op.get_bind(), checkfirst=True)
    tender_status.create(op.get_bind(), checkfirst=True)
    cancellation_actor.create(op.get_bind(), checkfirst=True)
    query_status.create(op.get_bind(), checkfirst=True)
    report_run_status.create(op.get_bind(), checkfirst=True)
    schedule_channel.create(op.get_bind(), checkfirst=True)
    template_owner_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index("ix_users_role", "users", ["role"], unique=False)

    op.create_table(
        "cities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("code"),
        schema="analytics",
    )
    op.create_index("ix_analytics_cities_name", "cities", ["name"], unique=False, schema="analytics")

    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("city_id", sa.Integer(), sa.ForeignKey("analytics.cities.id"), nullable=False),
        sa.Column("segment", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="analytics",
    )
    op.create_index("ix_analytics_customers_city_id", "customers", ["city_id"], unique=False, schema="analytics")

    op.create_table(
        "drivers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("city_id", sa.Integer(), sa.ForeignKey("analytics.cities.id"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("vehicle_class", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="analytics",
    )
    op.create_index("ix_analytics_drivers_city_id", "drivers", ["city_id"], unique=False, schema="analytics")

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("city_id", sa.Integer(), sa.ForeignKey("analytics.cities.id"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analytics.customers.id"), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analytics.drivers.id"), nullable=True),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("order_status", order_status, nullable=False),
        sa.Column("tender_status", tender_status, nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pickup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", cancellation_actor, nullable=False, server_default="unknown"),
        sa.Column("cancellation_reason", sa.String(length=100), nullable=True),
        sa.Column("price_local", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("distance_km", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("duration_min", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("external_id"),
        schema="analytics",
    )
    for column in ["external_id", "city_id", "customer_id", "driver_id", "channel", "order_status", "tender_status", "requested_at"]:
        op.create_index(f"ix_analytics_orders_{column}", "orders", [column], unique=False, schema="analytics")

    op.create_table(
        "order_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analytics.orders.id"), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        schema="analytics",
    )
    op.create_index("ix_analytics_order_events_order_id", "order_events", ["order_id"], unique=False, schema="analytics")
    op.create_index("ix_analytics_order_events_event_type", "order_events", ["event_type"], unique=False, schema="analytics")
    op.create_index("ix_analytics_order_events_event_time", "order_events", ["event_time"], unique=False, schema="analytics")

    op.create_table(
        "order_tender_facts",
        sa.Column("row_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("city_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("tender_id", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("driver_id", sa.String(length=64), nullable=True),
        sa.Column("offset_hours", sa.Integer(), nullable=True),
        sa.Column("status_order", sa.String(length=32), nullable=True),
        sa.Column("status_tender", sa.String(length=32), nullable=True),
        sa.Column("order_timestamp", sa.DateTime(timezone=False), nullable=False),
        sa.Column("tender_timestamp", sa.DateTime(timezone=False), nullable=True),
        sa.Column("driveraccept_timestamp", sa.DateTime(timezone=False), nullable=True),
        sa.Column("driverarrived_timestamp", sa.DateTime(timezone=False), nullable=True),
        sa.Column("driverstarttheride_timestamp", sa.DateTime(timezone=False), nullable=True),
        sa.Column("driverdone_timestamp", sa.DateTime(timezone=False), nullable=True),
        sa.Column("clientcancel_timestamp", sa.DateTime(timezone=False), nullable=True),
        sa.Column("drivercancel_timestamp", sa.DateTime(timezone=False), nullable=True),
        sa.Column("order_modified_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("cancel_before_accept_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("distance_in_meters", sa.Integer(), nullable=True),
        sa.Column("duration_in_seconds", sa.Integer(), nullable=True),
        sa.Column("price_order_local", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_tender_local", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_start_local", sa.Numeric(12, 2), nullable=True),
        schema="analytics",
    )
    for column in ["city_id", "order_id", "tender_id", "user_id", "driver_id", "status_order", "status_tender", "order_timestamp", "order_modified_local"]:
        op.create_index(f"ix_analytics_order_tender_facts_{column}", "order_tender_facts", [column], unique=False, schema="analytics")

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("query_plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sql_text", sa.Text(), nullable=False),
        sa.Column("chart_type", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reports_owner_id", "reports", ["owner_id"], unique=False)

    op.create_table(
        "query_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("query_plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sql_text", sa.Text(), nullable=False),
        sa.Column("validation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_preview_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("chart_type", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", query_status, nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_query_history_user_id", "query_history", ["user_id"], unique=False)

    op.create_table(
        "report_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("triggered_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("trigger_source", sa.String(length=50), nullable=False),
        sa.Column("status", report_run_status, nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_preview_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_report_runs_report_id", "report_runs", ["report_id"], unique=False)

    op.create_table(
        "schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("cron_expression", sa.String(length=120), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("channel", schedule_channel, nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_schedules_report_id", "schedules", ["report_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("sql_text", sa.Text(), nullable=True),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interpretation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("validation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("extra_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ["actor_user_id", "event_type", "status"]:
        op.create_index(f"ix_audit_logs_{column}", "audit_logs", [column], unique=False)

    op.create_table(
        "semantic_dictionary_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("term", sa.String(length=255), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("target_key", sa.String(length=120), nullable=False),
        sa.Column("synonyms_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_semantic_dictionary_entries_term", "semantic_dictionary_entries", ["term"], unique=False)

    op.create_table(
        "approved_query_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("guidance", sa.Text(), nullable=False),
        sa.Column("example_question", sa.Text(), nullable=False),
        sa.Column("output_shape_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("owner_role", template_owner_role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("approved_query_templates")
    op.drop_index("ix_semantic_dictionary_entries_term", table_name="semantic_dictionary_entries")
    op.drop_table("semantic_dictionary_entries")
    op.drop_index("ix_audit_logs_status", table_name="audit_logs")
    op.drop_index("ix_audit_logs_event_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_schedules_report_id", table_name="schedules")
    op.drop_table("schedules")
    op.drop_index("ix_report_runs_report_id", table_name="report_runs")
    op.drop_table("report_runs")
    op.drop_index("ix_query_history_user_id", table_name="query_history")
    op.drop_table("query_history")
    op.drop_index("ix_reports_owner_id", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_analytics_order_events_event_time", table_name="order_events", schema="analytics")
    op.drop_index("ix_analytics_order_events_event_type", table_name="order_events", schema="analytics")
    op.drop_index("ix_analytics_order_events_order_id", table_name="order_events", schema="analytics")
    op.drop_table("order_events", schema="analytics")
    for column in ["order_modified_local", "order_timestamp", "status_tender", "status_order", "driver_id", "user_id", "tender_id", "order_id", "city_id"]:
        op.drop_index(f"ix_analytics_order_tender_facts_{column}", table_name="order_tender_facts", schema="analytics")
    op.drop_table("order_tender_facts", schema="analytics")
    for column in ["requested_at", "tender_status", "order_status", "channel", "driver_id", "customer_id", "city_id", "external_id"]:
        op.drop_index(f"ix_analytics_orders_{column}", table_name="orders", schema="analytics")
    op.drop_table("orders", schema="analytics")
    op.drop_index("ix_analytics_drivers_city_id", table_name="drivers", schema="analytics")
    op.drop_table("drivers", schema="analytics")
    op.drop_index("ix_analytics_customers_city_id", table_name="customers", schema="analytics")
    op.drop_table("customers", schema="analytics")
    op.drop_index("ix_analytics_cities_name", table_name="cities", schema="analytics")
    op.drop_table("cities", schema="analytics")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    template_owner_role.drop(op.get_bind(), checkfirst=True)
    schedule_channel.drop(op.get_bind(), checkfirst=True)
    report_run_status.drop(op.get_bind(), checkfirst=True)
    query_status.drop(op.get_bind(), checkfirst=True)
    cancellation_actor.drop(op.get_bind(), checkfirst=True)
    tender_status.drop(op.get_bind(), checkfirst=True)
    order_status.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
    op.execute("DROP SCHEMA IF EXISTS analytics CASCADE")
