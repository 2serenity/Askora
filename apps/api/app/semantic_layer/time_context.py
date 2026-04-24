from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.semantic_layer.loader import semantic_loader


@dataclass(frozen=True)
class DatasetDateBounds:
    min_date: date
    max_date: date


class SemanticTimeContext:
    def __init__(self, db: Session):
        self.db = db
        self.catalog = semantic_loader.load_catalog()
        self._bounds: DatasetDateBounds | None = None

    def get_bounds(self) -> DatasetDateBounds:
        if self._bounds is not None:
            return self._bounds

        dataset = self.catalog.datasets[self.catalog.base_dataset]
        sql = text(
            f"""
            SELECT
                MIN({dataset.default_time_field})::date AS min_date,
                MAX({dataset.default_time_field})::date AS max_date
            FROM {dataset.table} AS {dataset.alias}
            """
        )
        row = self.db.execute(sql).mappings().one()
        today = date.today()

        min_date = self._coerce_date(row.get("min_date")) or today
        max_date = self._coerce_date(row.get("max_date")) or today
        self._bounds = DatasetDateBounds(min_date=min_date, max_date=max_date)
        return self._bounds

    def get_anchor_date(self) -> date:
        return self.get_bounds().max_date

    def latest_occurrence(self, month: int, day: int) -> date:
        anchor = self.get_anchor_date()
        year = anchor.year

        while year >= self.get_bounds().min_date.year - 1:
            try:
                candidate = date(year, month, day)
            except ValueError:
                year -= 1
                continue

            if candidate <= anchor:
                return candidate
            year -= 1

        return anchor

    def month_range(self, month: int, explicit_year: int | None = None) -> tuple[date, date, bool]:
        anchor = self.get_anchor_date()
        year = explicit_year if explicit_year is not None else self._infer_month_year(month, anchor)

        start_date = date(year, month, 1)
        end_date = date(year, month, calendar.monthrange(year, month)[1])
        is_partial = False

        if explicit_year is None and year == anchor.year and month == anchor.month and anchor < end_date:
            end_date = anchor
            is_partial = True

        return start_date, end_date, is_partial

    def calendar_year_range(self, year: int) -> tuple[date, date, bool]:
        anchor = self.get_anchor_date()
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        is_partial = False

        if year == anchor.year and anchor < end_date:
            end_date = anchor
            is_partial = True

        return start_date, end_date, is_partial

    def rolling_year_range(self) -> tuple[date, date]:
        anchor = self.get_anchor_date()
        year = anchor.year
        month = anchor.month - 11
        while month <= 0:
            month += 12
            year -= 1
        return date(year, month, 1), anchor

    def all_time_range(self) -> tuple[date, date]:
        bounds = self.get_bounds()
        return bounds.min_date, bounds.max_date

    def _infer_month_year(self, month: int, anchor: date) -> int:
        return anchor.year if month <= anchor.month else anchor.year - 1

    def _coerce_date(self, value) -> date | None:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        return None
