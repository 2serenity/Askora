from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session
import yaml
from fastapi import HTTPException, status

from app.core.config import settings
from app.data_sources.registry import RuntimeDataSource, data_source_registry
from app.semantic_layer.loader import semantic_loader


@dataclass
class ColumnProfile:
    name: str
    inferred_type: str
    non_null_ratio: float
    unique_ratio: float


class CsvAutoConfigService:
    def analyze_and_build(
        self,
        *,
        csv_bytes: bytes,
        source_key: str | None,
        table_name: str | None,
        delimiter: str = "auto",
        apply: bool = False,
        auto_mode: bool = True,
        db: Session,
    ) -> dict[str, Any]:
        normalized_delimiter = delimiter.strip().lower()
        if normalized_delimiter in {"tab", "\\t"}:
            delimiter = "\t"
        elif normalized_delimiter in {"comma"}:
            delimiter = ","
        elif normalized_delimiter in {"semicolon"}:
            delimiter = ";"
        elif normalized_delimiter in {"pipe"}:
            delimiter = "|"

        if delimiter != "auto" and len(delimiter) != 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Delimiter должен быть одним символом")

        content = self._decode_csv(csv_bytes)
        resolved_delimiter = self._resolve_delimiter(content, delimiter)
        reader = csv.DictReader(StringIO(content), delimiter=resolved_delimiter)
        if not reader.fieldnames:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV не содержит заголовок колонок")

        columns = [self._sanitize_identifier(item) for item in reader.fieldnames if item and item.strip()]
        if not columns:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось получить колонки CSV")

        sample_rows: list[dict[str, str]] = []
        for index, row in enumerate(reader):
            if index >= 5000:
                break
            sample_rows.append({self._sanitize_identifier(key): (value or "") for key, value in row.items() if key})

        profiles = self._profile_columns(columns, sample_rows)
        resolved_source_key, resolved_table_name, resolution_meta = self._resolve_target(
            requested_source_key=source_key,
            requested_table_name=table_name,
            auto_mode=auto_mode,
            db=db,
        )
        catalog = self._build_catalog(source_key=resolved_source_key, table_name=resolved_table_name, profiles=profiles)
        preview = self._build_preview(profiles, catalog)

        if apply:
            with open(settings.semantic_catalog_path, "w", encoding="utf-8") as file:
                yaml.safe_dump(catalog, file, sort_keys=False, allow_unicode=True)
            semantic_loader.invalidate()

        return {
            "applied": apply,
            "catalog_preview": preview,
            "catalog": catalog if not apply else None,
            "auto_resolution": resolution_meta,
            "used_delimiter": resolved_delimiter,
        }

    def _decode_csv(self, payload: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "cp1251"):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось декодировать CSV. Поддерживаются UTF-8/UTF-8-BOM/CP1251.",
        )

    def _profile_columns(self, columns: list[str], rows: list[dict[str, str]]) -> list[ColumnProfile]:
        total_rows = max(1, len(rows))
        profiles: list[ColumnProfile] = []
        for column in columns:
            values = [row.get(column, "").strip() for row in rows]
            non_empty = [value for value in values if value]
            unique_values = len(set(non_empty))
            inferred_type = self._infer_type(column, non_empty)
            profiles.append(
                ColumnProfile(
                    name=column,
                    inferred_type=inferred_type,
                    non_null_ratio=round(len(non_empty) / total_rows, 4),
                    unique_ratio=round((unique_values / max(1, len(non_empty))) if non_empty else 0.0, 4),
                )
            )
        return profiles

    def _infer_type(self, column_name: str, values: list[str]) -> str:
        normalized = column_name.lower()
        if any(token in normalized for token in ("date", "time", "timestamp")):
            return "datetime"
        if not values:
            return "text"

        checked = values[:300]
        datetime_hits = 0
        int_hits = 0
        float_hits = 0
        for raw in checked:
            if self._looks_like_datetime(raw):
                datetime_hits += 1
                continue
            if re.fullmatch(r"-?\d+", raw):
                int_hits += 1
                continue
            if re.fullmatch(r"-?\d+(?:[.,]\d+)?", raw):
                float_hits += 1
                continue

        threshold = max(1, int(len(checked) * 0.7))
        if datetime_hits >= threshold:
            return "datetime"
        if int_hits >= threshold:
            return "int"
        if float_hits >= threshold:
            return "float"
        return "text"

    def _looks_like_datetime(self, raw: str) -> bool:
        cleaned = raw.strip()
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y", "%d.%m.%Y %H:%M:%S"):
            try:
                datetime.strptime(cleaned, fmt)
                return True
            except ValueError:
                continue
        return False

    def _build_catalog(self, *, source_key: str, table_name: str, profiles: list[ColumnProfile]) -> dict[str, Any]:
        alias = "ot"
        dataset_key = "auto_dataset"
        time_column = self._pick_time_column(profiles)
        default_time_field = f"{alias}.{time_column}" if time_column else f"{alias}.{profiles[0].name}"

        metrics: dict[str, Any] = {
            "rows_count": {
                "key": "rows_count",
                "label": "Количество строк",
                "description": "Общее количество строк в датасете",
                "sql": f"COUNT({alias}.*)",
                "synonyms": ["количество", "сколько", "число строк", "count", "rows"],
                "allowed_roles": ["admin", "analyst", "business_user"],
            }
        }
        dimensions: dict[str, Any] = {}
        filters: dict[str, Any] = {}
        business_terms: dict[str, Any] = {
            "количество": {"entity_type": "metric", "target_key": "rows_count"},
            "сколько строк": {"entity_type": "metric", "target_key": "rows_count"},
        }

        for profile in profiles:
            human = self._humanize(profile.name)
            col_expr = f"{alias}.{profile.name}"
            dim_key = f"dim_{profile.name}"
            synonyms = [profile.name, human]

            if profile.inferred_type in {"int", "float"}:
                metric_sum_key = f"sum_{profile.name}"
                metric_avg_key = f"avg_{profile.name}"
                metrics[metric_sum_key] = {
                    "key": metric_sum_key,
                    "label": f"Сумма {human}",
                    "description": f"Сумма поля {profile.name}",
                    "sql": f"COALESCE(ROUND(SUM({col_expr})::numeric, 2), 0)",
                    "synonyms": [f"сумма {human}", f"sum {profile.name}", profile.name],
                    "allowed_roles": ["admin", "analyst", "business_user"],
                }
                metrics[metric_avg_key] = {
                    "key": metric_avg_key,
                    "label": f"Среднее {human}",
                    "description": f"Среднее значение поля {profile.name}",
                    "sql": f"ROUND(AVG({col_expr})::numeric, 2)",
                    "synonyms": [f"среднее {human}", f"avg {profile.name}", profile.name],
                    "allowed_roles": ["admin", "analyst", "business_user"],
                }
                business_terms[f"сумма {human}"] = {"entity_type": "metric", "target_key": metric_sum_key}
                business_terms[f"среднее {human}"] = {"entity_type": "metric", "target_key": metric_avg_key}

                filters[profile.name] = {
                    "key": profile.name,
                    "label": human,
                    "field": col_expr,
                    "operators": ["gt", "gte", "lt", "lte", "eq"],
                    "synonyms": synonyms,
                }

            if profile.inferred_type == "datetime":
                if not dimensions.get("order_date"):
                    dimensions["order_date"] = {
                        "key": "order_date",
                        "label": f"{human} (день)",
                        "sql": f"DATE({col_expr})",
                        "synonyms": ["по дням", f"по {human}", profile.name],
                        "kind": "time",
                        "grain": "day",
                        "allowed_roles": ["admin", "analyst", "business_user"],
                    }
                    dimensions["order_week"] = {
                        "key": "order_week",
                        "label": f"{human} (неделя)",
                        "sql": f"DATE_TRUNC('week', {col_expr})::date",
                        "synonyms": ["по неделям", "понедельно", f"week {profile.name}"],
                        "kind": "time",
                        "grain": "week",
                        "allowed_roles": ["admin", "analyst", "business_user"],
                    }
                    dimensions["order_month"] = {
                        "key": "order_month",
                        "label": f"{human} (месяц)",
                        "sql": f"DATE_TRUNC('month', {col_expr})::date",
                        "synonyms": ["по месяцам", "помесячно", f"month {profile.name}"],
                        "kind": "time",
                        "grain": "month",
                        "allowed_roles": ["admin", "analyst", "business_user"],
                    }
                filters[profile.name] = {
                    "key": profile.name,
                    "label": human,
                    "field": col_expr,
                    "operators": ["eq", "in", "gte", "lte"],
                    "synonyms": synonyms,
                }
                continue

            if profile.inferred_type == "text" or profile.unique_ratio <= 0.98:
                dimensions[dim_key] = {
                    "key": dim_key,
                    "label": human,
                    "sql": f"COALESCE({col_expr}::text, 'unknown')",
                    "synonyms": [f"по {human}", profile.name, human],
                    "kind": "category",
                    "allowed_roles": ["admin", "analyst", "business_user"],
                }
                filters[profile.name] = {
                    "key": profile.name,
                    "label": human,
                    "field": f"{col_expr}::text",
                    "operators": ["eq", "in"],
                    "synonyms": synonyms,
                }

        return {
            "version": 3,
            "base_dataset": dataset_key,
            "datasets": {
                dataset_key: {
                    "table": table_name,
                    "alias": alias,
                    "default_time_field": default_time_field,
                    "source_key": source_key,
                    "joins": [],
                }
            },
            "metrics": metrics,
            "dimensions": dimensions,
            "filters": filters,
            "joins": {},
            "business_terms": business_terms,
            "time_mappings": self._default_time_mappings(),
        }

    def _pick_time_column(self, profiles: list[ColumnProfile]) -> str | None:
        for profile in profiles:
            if profile.inferred_type == "datetime":
                return profile.name
        return None

    def _build_preview(self, profiles: list[ColumnProfile], catalog: dict[str, Any]) -> dict[str, Any]:
        columns = [
            {
                "name": item.name,
                "inferred_type": item.inferred_type,
                "non_null_ratio": item.non_null_ratio,
                "unique_ratio": item.unique_ratio,
            }
            for item in profiles
        ]
        return {
            "columns": columns,
            "metrics_count": len(catalog["metrics"]),
            "dimensions_count": len(catalog["dimensions"]),
            "filters_count": len(catalog["filters"]),
            "base_dataset": catalog["base_dataset"],
        }

    def _resolve_target(
        self,
        *,
        requested_source_key: str | None,
        requested_table_name: str | None,
        auto_mode: bool,
        db: Session,
    ) -> tuple[str, str, dict[str, Any]]:
        cleaned_source = (requested_source_key or "").strip()
        cleaned_table = (requested_table_name or "").strip()

        catalog = semantic_loader.load_catalog()
        active_dataset = catalog.datasets.get(catalog.base_dataset)
        fallback_source = active_dataset.source_key if active_dataset else "default"
        fallback_table = active_dataset.table if active_dataset else "analytics.order_tender_facts"
        runtime_sources = [source for source in data_source_registry.list_sources(db) if source.is_active]
        source_map = {source.key: source for source in runtime_sources}
        default_source = next((source for source in runtime_sources if source.is_default), None)

        source = cleaned_source
        table = cleaned_table
        strategy = "manual"
        notes: list[str] = []

        if auto_mode:
            strategy = "safe_auto"
            if not source:
                source = fallback_source if fallback_source in source_map else (default_source.key if default_source else "default")
                notes.append("source_key автоматически взят из активного semantic catalog или default-источника.")
            if not table:
                table = fallback_table
                notes.append("table_name автоматически взят из активного semantic catalog.")

        if not source or not table:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось определить source_key/table_name. Укажите их вручную или включите auto_mode.",
            )

        candidates = [
            {
                "source_key": fallback_source,
                "table_name": fallback_table,
                "confidence": 0.95 if active_dataset else 0.55,
                "reason": "Текущий активный dataset semantic catalog",
            },
            {
                "source_key": default_source.key if default_source else "default",
                "table_name": "analytics.order_tender_facts",
                "confidence": 0.6,
                "reason": "Безопасный резервный шаблон",
            },
        ]

        selected_source = source_map.get(source)
        validated, validation_message = self._validate_target_table(selected_source, table, db)
        if not validated:
            notes.append(validation_message)

        return source, table, {
            "strategy": strategy,
            "resolved_source_key": source,
            "resolved_table_name": table,
            "notes": notes,
            "validated": validated,
            "validation_message": validation_message,
            "candidates": candidates,
        }

    def _validate_target_table(self, source: RuntimeDataSource | None, table_name: str, db: Session) -> tuple[bool, str | None]:
        if not source:
            return False, "Источник данных не найден в активном реестре."
        if source.dialect not in {"postgres", "postgresql"}:
            return True, "Проверка существования таблицы доступна только для Postgres, пропущено."

        check_sql = "SELECT to_regclass(:table_name)"
        try:
            if data_source_registry.is_primary_source(source):
                value = db.execute(text(check_sql), {"table_name": table_name}).scalar()
            else:
                engine = data_source_registry.get_engine(source)
                with engine.begin() as connection:
                    value = connection.execute(text(check_sql), {"table_name": table_name}).scalar()
            if value:
                return True, "Таблица найдена в выбранном источнике."
            return False, f"Таблица {table_name} не найдена в выбранном источнике."
        except Exception as exc:
            return False, f"Не удалось проверить таблицу автоматически: {exc}"

    def _resolve_delimiter(self, content: str, delimiter: str) -> str:
        if delimiter != "auto":
            return delimiter
        sample = "\n".join(content.splitlines()[:8])
        try:
            sniffed = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            return sniffed.delimiter
        except csv.Error:
            return ","

    def _sanitize_identifier(self, raw: str) -> str:
        value = re.sub(r"[^a-zA-Z0-9_]+", "_", raw.strip())
        value = re.sub(r"_+", "_", value).strip("_").lower()
        return value or "field"

    def _humanize(self, value: str) -> str:
        return value.replace("_", " ").strip()

    def _default_time_mappings(self) -> dict[str, dict[str, str]]:
        return {
            "вчера": {"label": "Вчера", "kind": "yesterday", "grain": "day"},
            "за вчера": {"label": "Вчера", "kind": "yesterday", "grain": "day"},
            "сегодня": {"label": "Сегодня", "kind": "today", "grain": "day"},
            "за сегодня": {"label": "Сегодня", "kind": "today", "grain": "day"},
            "за прошлую неделю": {"label": "Прошлая неделя", "kind": "previous_week", "grain": "day"},
            "за текущую неделю": {"label": "Текущая неделя", "kind": "current_week", "grain": "day"},
            "за прошлый месяц": {"label": "Прошлый месяц", "kind": "previous_month", "grain": "day"},
            "за текущий месяц": {"label": "Текущий месяц", "kind": "current_month", "grain": "day"},
            "за прошлый год": {"label": "Прошлый год", "kind": "previous_year", "grain": "month"},
            "за текущий год": {"label": "Текущий год", "kind": "current_year", "grain": "month"},
        }


csv_autoconfig_service = CsvAutoConfigService()
