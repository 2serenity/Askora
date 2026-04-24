import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    analyst = "analyst"
    business_user = "business_user"


class OrderStatus(str, enum.Enum):
    created = "created"
    assigned = "assigned"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class TenderStatus(str, enum.Enum):
    opened = "opened"
    matched = "matched"
    expired = "expired"
    cancelled = "cancelled"


class CancellationActor(str, enum.Enum):
    customer = "customer"
    driver = "driver"
    system = "system"
    unknown = "unknown"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Kaliningrad")
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="ru-RU")
    preferences_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    reports: Mapped[list["Report"]] = relationship(back_populates="owner")


class City(Base):
    __tablename__ = "cities"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_id: Mapped[int] = mapped_column(ForeignKey("analytics.cities.id"), nullable=False, index=True)
    segment: Mapped[str] = mapped_column(String(50), nullable=False, default="mass")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Driver(Base):
    __tablename__ = "drivers"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_id: Mapped[int] = mapped_column(ForeignKey("analytics.cities.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    vehicle_class: Mapped[str] = mapped_column(String(50), nullable=False, default="econom")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("analytics.cities.id"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analytics.customers.id"), nullable=False, index=True)
    driver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("analytics.drivers.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    order_status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, name="order_status"), nullable=False, index=True)
    tender_status: Mapped[TenderStatus] = mapped_column(
        Enum(TenderStatus, name="tender_status"),
        nullable=False,
        index=True,
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pickup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[CancellationActor] = mapped_column(
        Enum(CancellationActor, name="cancellation_actor"),
        default=CancellationActor.unknown,
        nullable=False,
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(100))
    price_local: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    distance_km: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    duration_min: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class OrderEvent(Base):
    __tablename__ = "order_events"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analytics.orders.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    event_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
