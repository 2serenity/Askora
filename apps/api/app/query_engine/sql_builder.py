from __future__ import annotations

import re
from datetime import timedelta

from app.schemas.query import QueryPlan
from app.semantic_layer.loader import semantic_loader
from app.semantic_layer.types import SemanticDataset


class SQLBuilder:
    def __init__(self) -> None:
        self.catalog = semantic_loader.load_catalog()
        self._join_by_alias = {join.alias: key for key, join in self.catalog.joins.items()}

    def build(self, plan: QueryPlan) -> tuple[str, dict]:
        dataset = self.catalog.datasets[plan.dataset]
        join_keys = self._collect_required_joins(plan, dataset)
        params = {
            "start_date": plan.time_range.start_date.isoformat(),
            "end_date": (plan.time_range.end_date + timedelta(days=1)).isoformat(),
            "row_limit": plan.limit,
        }

        select_parts = [f"{dimension.expression} AS {dimension.key}" for dimension in plan.dimensions]
        select_parts.extend(f"{metric.expression} AS {metric.key}" for metric in plan.metrics)
        group_parts = [dimension.expression for dimension in plan.dimensions]

        where_parts = [
            f"{dataset.default_time_field} >= :start_date",
            f"{dataset.default_time_field} < :end_date",
        ]
        where_parts.extend(self._build_multi_date_clause(plan, dataset, params))
        where_parts.extend(self._build_filter_clauses(plan, params))

        query = f"""
        SELECT
            {", ".join(select_parts)}
        {self._build_from_clause(dataset, join_keys)}
        WHERE {' AND '.join(where_parts)}
        {self._build_group_clause(group_parts)}
        {self._build_order_clause(plan)}
        LIMIT :row_limit
        """

        if plan.comparison.enabled and plan.comparison.mode == "previous_period":
            if self._needs_percent_change(plan.question):
                return self._build_period_percent_change(plan, dataset, join_keys)
            return self._build_period_comparison(plan, dataset, join_keys)
        if plan.comparison.enabled and plan.comparison.mode == "year_over_year":
            return self._build_year_over_year_comparison(plan, dataset, join_keys)

        return " ".join(query.split()), params

    def _needs_percent_change(self, question: str) -> bool:
        normalized = question.lower().replace("ё", "е")
        return any(token in normalized for token in ["изменени", "рост", "паден", "в процентах", "процент", "относительно прошлого", "к прошлому"])

    def _build_period_percent_change(self, plan: QueryPlan, dataset: SemanticDataset, join_keys: set[str]) -> tuple[str, dict]:
        if not plan.metrics:
            return self._build_period_comparison(plan, dataset, join_keys)

        metric = plan.metrics[0]
        metric_key = metric.key
        change_key = metric_key

        if plan.multi_date and len(plan.multi_date.dates) >= 2:
            return self._build_discrete_date_percent_change(plan, dataset, join_keys, metric_key, change_key)

        current_start, current_end, previous_start, previous_end = self._comparison_window(plan)

        dimension_select = [f"{dimension.expression} AS {dimension.key}" for dimension in plan.dimensions]
        group_parts = [dimension.expression for dimension in plan.dimensions]
        filter_clauses: list[str] = []
        filter_params: dict[str, object] = {}

        for item in plan.filters:
            filter_config = self.catalog.filters[item.key]
            clause, params = self._build_filter_clause(filter_config.field, item.operator, item.value, f"filter_{item.key}")
            filter_clauses.append(clause)
            filter_params.update(params)

        where_suffix = f" AND {' AND '.join(filter_clauses)}" if filter_clauses else ""
        current_sql = f"""
        SELECT
            {", ".join(dimension_select + ["'current'::text AS period_label", f"{metric.expression} AS {metric_key}"])}
        {self._build_from_clause(dataset, join_keys)}
        WHERE {dataset.default_time_field} >= :current_start AND {dataset.default_time_field} < :current_end{where_suffix}
        {self._build_group_clause(group_parts)}
        """
        previous_sql = f"""
        SELECT
            {", ".join(dimension_select + ["'previous'::text AS period_label", f"{metric.expression} AS {metric_key}"])}
        {self._build_from_clause(dataset, join_keys)}
        WHERE {dataset.default_time_field} >= :previous_start AND {dataset.default_time_field} < :previous_end{where_suffix}
        {self._build_group_clause(group_parts)}
        """

        outer_dims = [dimension.key for dimension in plan.dimensions]
        outer_group = f"GROUP BY {', '.join(outer_dims)}" if outer_dims else ""
        outer_order = f"ORDER BY {', '.join(outer_dims)}" if outer_dims else ""
        outer_select = [
            *outer_dims,
            f"ROUND(100.0 * ((SUM({metric_key}) FILTER (WHERE period_label = 'current')) - (SUM({metric_key}) FILTER (WHERE period_label = 'previous'))) / NULLIF((SUM({metric_key}) FILTER (WHERE period_label = 'previous')), 0), 2) AS {change_key}",
        ]
        query = f"""
        WITH unioned AS (
            {current_sql}
            UNION ALL
            {previous_sql}
        )
        SELECT {", ".join(outer_select)}
        FROM unioned
        {outer_group}
        {outer_order}
        LIMIT :row_limit
        """
        return (
            " ".join(query.split()),
            {
                "current_start": current_start,
                "current_end": current_end,
                "previous_start": previous_start,
                "previous_end": previous_end,
                "row_limit": plan.limit,
                **filter_params,
            },
        )

    def _build_discrete_date_percent_change(
        self,
        plan: QueryPlan,
        dataset: SemanticDataset,
        join_keys: set[str],
        metric_key: str,
        change_key: str,
    ) -> tuple[str, dict]:
        dates = sorted(plan.multi_date.dates)[:2] if plan.multi_date else []
        first_date = dates[0].isoformat()
        second_date = dates[1].isoformat()

        dimension_select = [f"{dimension.expression} AS {dimension.key}" for dimension in plan.dimensions]
        group_parts = [dimension.expression for dimension in plan.dimensions]
        filter_clauses: list[str] = []
        filter_params: dict[str, object] = {}
        metric_expression = plan.metrics[0].expression

        for item in plan.filters:
            filter_config = self.catalog.filters[item.key]
            clause, params = self._build_filter_clause(filter_config.field, item.operator, item.value, f"filter_{item.key}")
            filter_clauses.append(clause)
            filter_params.update(params)

        where_suffix = f" AND {' AND '.join(filter_clauses)}" if filter_clauses else ""
        first_sql = f"""
        SELECT
            {", ".join(dimension_select + ["'current'::text AS period_label", f"{metric_expression} AS {metric_key}"])}
        {self._build_from_clause(dataset, join_keys)}
        WHERE DATE({dataset.default_time_field}) = :multi_date_0{where_suffix}
        {self._build_group_clause(group_parts)}
        """
        second_sql = f"""
        SELECT
            {", ".join(dimension_select + ["'previous'::text AS period_label", f"{metric_expression} AS {metric_key}"])}
        {self._build_from_clause(dataset, join_keys)}
        WHERE DATE({dataset.default_time_field}) = :multi_date_1{where_suffix}
        {self._build_group_clause(group_parts)}
        """

        outer_dims = [dimension.key for dimension in plan.dimensions]
        outer_group = f"GROUP BY {', '.join(outer_dims)}" if outer_dims else ""
        outer_order = f"ORDER BY {', '.join(outer_dims)}" if outer_dims else ""
        outer_select = [
            *outer_dims,
            f"ROUND(100.0 * ((SUM({metric_key}) FILTER (WHERE period_label = 'current')) - (SUM({metric_key}) FILTER (WHERE period_label = 'previous'))) / NULLIF((SUM({metric_key}) FILTER (WHERE period_label = 'previous')), 0), 2) AS {change_key}",
        ]

        query = f"""
        WITH unioned AS (
            {first_sql}
            UNION ALL
            {second_sql}
        )
        SELECT {", ".join(outer_select)}
        FROM unioned
        {outer_group}
        {outer_order}
        LIMIT :row_limit
        """
        return (
            " ".join(query.split()),
            {
                "multi_date_0": first_date,
                "multi_date_1": second_date,
                "row_limit": plan.limit,
                **filter_params,
            },
        )

    def _build_year_over_year_comparison(self, plan: QueryPlan, dataset: SemanticDataset, join_keys: set[str]) -> tuple[str, dict]:
        # Compare current vs previous calendar year, without relying on default date windows.
        if not plan.metrics:
            # Defensive fallback: build a regular (non-comparison) query with existing time constraints.
            return self.build(plan.model_copy(update={"comparison": {"enabled": False, "mode": "none"}}))

        metric_select = [f"{metric.expression} AS {metric.key}" for metric in plan.metrics]
        dimension_select = [f"{dimension.expression} AS {dimension.key}" for dimension in plan.dimensions]
        group_parts = [dimension.expression for dimension in plan.dimensions]

        filter_clauses: list[str] = []
        filter_params: dict[str, object] = {}
        for item in plan.filters:
            filter_config = self.catalog.filters[item.key]
            clause, params = self._build_filter_clause(filter_config.field, item.operator, item.value, f"filter_{item.key}")
            filter_clauses.append(clause)
            filter_params.update(params)
        where_suffix = f" AND {' AND '.join(filter_clauses)}" if filter_clauses else ""

        current_sql = f"""
        SELECT
            {", ".join(dimension_select + ["EXTRACT(YEAR FROM " + dataset.default_time_field + ")::int AS order_year", "'Текущий год'::text AS period_label"] + metric_select)}
        {self._build_from_clause(dataset, join_keys)}
        WHERE EXTRACT(YEAR FROM {dataset.default_time_field}) = :current_year{where_suffix}
        {self._build_group_clause(group_parts + [f"EXTRACT(YEAR FROM {dataset.default_time_field})"])}
        """
        previous_sql = f"""
        SELECT
            {", ".join(dimension_select + ["EXTRACT(YEAR FROM " + dataset.default_time_field + ")::int AS order_year", "'Прошлый год'::text AS period_label"] + metric_select)}
        {self._build_from_clause(dataset, join_keys)}
        WHERE EXTRACT(YEAR FROM {dataset.default_time_field}) = :previous_year{where_suffix}
        {self._build_group_clause(group_parts + [f"EXTRACT(YEAR FROM {dataset.default_time_field})"])}
        """

        order_keys = [dimension.key for dimension in plan.dimensions] + ["order_year", "period_label"]
        order_clause = f"ORDER BY {', '.join(order_keys)}" if order_keys else ""
        outer_select = [dimension.key for dimension in plan.dimensions] + ["order_year", "period_label"] + [metric.key for metric in plan.metrics]
        query = f"""
        WITH unioned AS (
            {current_sql}
            UNION ALL
            {previous_sql}
        )
        SELECT {", ".join(outer_select)}
        FROM unioned
        {order_clause}
        LIMIT :row_limit
        """
        from datetime import date as _date  # local import to avoid top-level changes

        current_year = _date.today().year
        return (
            " ".join(query.split()),
            {
                "current_year": current_year,
                "previous_year": current_year - 1,
                "row_limit": plan.limit,
                **filter_params,
            },
        )

    def _build_period_comparison(self, plan: QueryPlan, dataset: SemanticDataset, join_keys: set[str]) -> tuple[str, dict]:
        if plan.multi_date and len(plan.multi_date.dates) >= 2:
            return self._build_discrete_date_comparison(plan, dataset, join_keys)

        current_start, current_end, previous_start, previous_end = self._comparison_window(plan)

        dimension_select = [f"{dimension.expression} AS {dimension.key}" for dimension in plan.dimensions]
        metric_select = [f"{metric.expression} AS {metric.key}" for metric in plan.metrics]
        group_parts = [dimension.expression for dimension in plan.dimensions]
        filter_clauses: list[str] = []
        filter_params: dict[str, object] = {}

        for item in plan.filters:
            filter_config = self.catalog.filters[item.key]
            clause, params = self._build_filter_clause(filter_config.field, item.operator, item.value, f"filter_{item.key}")
            filter_clauses.append(clause)
            filter_params.update(params)

        where_suffix = f" AND {' AND '.join(filter_clauses)}" if filter_clauses else ""
        current_sql = f"""
        SELECT
            {", ".join(dimension_select + ["'Текущий период'::text AS period_label"] + metric_select)}
        {self._build_from_clause(dataset, join_keys)}
        WHERE {dataset.default_time_field} >= :current_start AND {dataset.default_time_field} < :current_end{where_suffix}
        {self._build_group_clause(group_parts)}
        """
        previous_sql = f"""
        SELECT
            {", ".join(dimension_select + ["'Предыдущий период'::text AS period_label"] + metric_select)}
        {self._build_from_clause(dataset, join_keys)}
        WHERE {dataset.default_time_field} >= :previous_start AND {dataset.default_time_field} < :previous_end{where_suffix}
        {self._build_group_clause(group_parts)}
        """

        order_keys = [dimension.key for dimension in plan.dimensions] + ["period_label"]
        order_clause = f"ORDER BY {', '.join(order_keys)}" if order_keys else ""
        outer_select = [dimension.key for dimension in plan.dimensions] + ["period_label"] + [metric.key for metric in plan.metrics]
        query = f"""
        WITH unioned AS (
            {current_sql}
            UNION ALL
            {previous_sql}
        )
        SELECT {", ".join(outer_select)}
        FROM unioned
        {order_clause}
        LIMIT :row_limit
        """
        return (
            " ".join(query.split()),
            {
                "current_start": current_start,
                "current_end": current_end,
                "previous_start": previous_start,
                "previous_end": previous_end,
                "row_limit": plan.limit,
                **filter_params,
            },
        )

    def _build_discrete_date_comparison(self, plan: QueryPlan, dataset: SemanticDataset, join_keys: set[str]) -> tuple[str, dict]:
        dates = sorted(plan.multi_date.dates)[:2] if plan.multi_date else []
        first_date = dates[0].isoformat()
        second_date = dates[1].isoformat()

        dimension_select = [f"{dimension.expression} AS {dimension.key}" for dimension in plan.dimensions]
        metric_select = [f"{metric.expression} AS {metric.key}" for metric in plan.metrics]
        group_parts = [dimension.expression for dimension in plan.dimensions]
        filter_clauses: list[str] = []
        filter_params: dict[str, object] = {}

        for item in plan.filters:
            filter_config = self.catalog.filters[item.key]
            clause, params = self._build_filter_clause(filter_config.field, item.operator, item.value, f"filter_{item.key}")
            filter_clauses.append(clause)
            filter_params.update(params)

        where_suffix = f" AND {' AND '.join(filter_clauses)}" if filter_clauses else ""
        first_sql = f"""
        SELECT
            {", ".join(dimension_select + [f"'{first_date}'::text AS period_label"] + metric_select)}
        {self._build_from_clause(dataset, join_keys)}
        WHERE DATE({dataset.default_time_field}) = :multi_date_0{where_suffix}
        {self._build_group_clause(group_parts)}
        """
        second_sql = f"""
        SELECT
            {", ".join(dimension_select + [f"'{second_date}'::text AS period_label"] + metric_select)}
        {self._build_from_clause(dataset, join_keys)}
        WHERE DATE({dataset.default_time_field}) = :multi_date_1{where_suffix}
        {self._build_group_clause(group_parts)}
        """

        order_keys = [dimension.key for dimension in plan.dimensions] + ["period_label"]
        order_clause = f"ORDER BY {', '.join(order_keys)}" if order_keys else ""
        outer_select = [dimension.key for dimension in plan.dimensions] + ["period_label"] + [metric.key for metric in plan.metrics]
        query = f"""
        WITH unioned AS (
            {first_sql}
            UNION ALL
            {second_sql}
        )
        SELECT {", ".join(outer_select)}
        FROM unioned
        {order_clause}
        LIMIT :row_limit
        """

        return (
            " ".join(query.split()),
            {
                "multi_date_0": first_date,
                "multi_date_1": second_date,
                "row_limit": plan.limit,
                **filter_params,
            },
        )

    def _comparison_window(self, plan: QueryPlan) -> tuple[str, str, str, str]:
        current_start = plan.time_range.start_date
        current_end = plan.time_range.end_date + timedelta(days=1)

        if plan.comparison.baseline_start_date and plan.comparison.baseline_end_date:
            baseline_start = plan.comparison.baseline_start_date
            baseline_end = plan.comparison.baseline_end_date + timedelta(days=1)
        else:
            delta_days = (plan.time_range.end_date - plan.time_range.start_date).days + 1
            baseline_end = plan.time_range.start_date
            baseline_start = plan.time_range.start_date - timedelta(days=delta_days)

        return (
            current_start.isoformat(),
            current_end.isoformat(),
            baseline_start.isoformat(),
            baseline_end.isoformat(),
        )

    def _collect_required_joins(self, plan: QueryPlan, dataset: SemanticDataset) -> set[str]:
        _ = (plan, dataset)
        # Hard rule: do not generate JOIN queries for NL2SQL execution.
        return set()

    def _build_filter_clauses(self, plan: QueryPlan, params: dict[str, object]) -> list[str]:
        clauses: list[str] = []
        for item in plan.filters:
            filter_config = self.catalog.filters[item.key]
            clause, filter_params = self._build_filter_clause(filter_config.field, item.operator, item.value, f"filter_{item.key}")
            clauses.append(clause)
            params.update(filter_params)
        return clauses

    def _build_multi_date_clause(
        self,
        plan: QueryPlan,
        dataset: SemanticDataset,
        params: dict[str, object],
    ) -> list[str]:
        if not plan.multi_date or not plan.multi_date.dates:
            return []
        placeholders: list[str] = []
        for index, item in enumerate(plan.multi_date.dates):
            key = f"multi_date_{index}"
            params[key] = item.isoformat()
            placeholders.append(f":{key}")
        return [f"DATE({dataset.default_time_field}) IN ({', '.join(placeholders)})"]

    def _build_filter_clause(
        self,
        field: str,
        operator: str,
        value: object,
        param_prefix: str,
    ) -> tuple[str, dict[str, object]]:
        if operator == "eq":
            return f"{field} = :{param_prefix}", {param_prefix: value}

        if operator == "in":
            values = value if isinstance(value, list) else [value]
            placeholders: list[str] = []
            params: dict[str, object] = {}
            for index, item in enumerate(values):
                key = f"{param_prefix}_{index}"
                placeholders.append(f":{key}")
                params[key] = item
            return f"{field} IN ({', '.join(placeholders)})", params

        if operator in {"gt", "gte", "lt", "lte"}:
            operator_map = {
                "gt": ">",
                "gte": ">=",
                "lt": "<",
                "lte": "<=",
            }
            return f"{field} {operator_map[operator]} :{param_prefix}", {param_prefix: value}

        raise ValueError(f"Unsupported filter operator: {operator}")

    def _build_from_clause(self, dataset: SemanticDataset, join_keys: set[str]) -> str:
        joins = " ".join(
            f"LEFT JOIN {self.catalog.joins[key].table} {self.catalog.joins[key].alias} ON {self.catalog.joins[key].on}"
            for key in sorted(join_keys)
        )
        return f"FROM {dataset.table} {dataset.alias} {joins}".strip()

    def _build_group_clause(self, group_parts: list[str]) -> str:
        if not group_parts:
            return ""
        return f"GROUP BY {', '.join(group_parts)}"

    def _build_order_clause(self, plan: QueryPlan) -> str:
        if plan.sort:
            return f"ORDER BY {plan.sort}"
        if plan.dimensions:
            return f"ORDER BY {plan.dimensions[0].key}"
        if plan.metrics:
            return f"ORDER BY {plan.metrics[0].key} DESC"
        return ""


sql_builder = SQLBuilder()
