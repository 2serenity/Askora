from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrderTenderFact(Base):
    __tablename__ = "order_tender_facts"
    __table_args__ = {"schema": "analytics"}

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tender_id: Mapped[str | None] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    driver_id: Mapped[str | None] = mapped_column(String(64), index=True)
    offset_hours: Mapped[int | None] = mapped_column(Integer)
    status_order: Mapped[str | None] = mapped_column(String(32), index=True)
    status_tender: Mapped[str | None] = mapped_column(String(32), index=True)
    order_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)
    tender_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    driveraccept_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    driverarrived_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    driverstarttheride_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    driverdone_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    clientcancel_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    drivercancel_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    order_modified_local: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), index=True)
    cancel_before_accept_local: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    distance_in_meters: Mapped[int | None] = mapped_column(Integer)
    duration_in_seconds: Mapped[int | None] = mapped_column(Integer)
    price_order_local: Mapped[float | None] = mapped_column(Numeric(12, 2))
    price_tender_local: Mapped[float | None] = mapped_column(Numeric(12, 2))
    price_start_local: Mapped[float | None] = mapped_column(Numeric(12, 2))

