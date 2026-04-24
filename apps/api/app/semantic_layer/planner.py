from app.schemas.query import QueryPlan, VisualizationSpec


class VisualizationPlanner:
    def choose(self, plan: QueryPlan) -> VisualizationSpec:
        metric_keys = [metric.key for metric in plan.metrics]
        time_dimensions = {"order_date", "order_week", "order_month"}
        preferred = plan.preferred_chart_type
        normalized_question = plan.question.lower().replace("ё", "е")
        is_percent_change = any(token in normalized_question for token in ["процент", "рост", "паден", "изменен"])

        if preferred == "table":
            return VisualizationSpec(
                chart_type="table",
                x_key=plan.dimensions[0].key if plan.dimensions else None,
                y_keys=metric_keys,
                title="Табличный режим",
                description="Результат показан таблицей без обязательного графика.",
            )

        if is_percent_change and not plan.dimensions:
            chosen = preferred if preferred in {"kpi", "bar"} else "kpi"
            return VisualizationSpec(
                chart_type=chosen,
                x_key="period_label" if chosen == "bar" else None,
                y_keys=metric_keys,
                title="Изменение относительно базового периода",
                description="Показываем процентное изменение метрики относительно выбранной базы.",
            )

        if plan.comparison.enabled and not plan.dimensions:
            return VisualizationSpec(
                chart_type=preferred or "bar",
                x_key="period_label",
                y_keys=metric_keys,
                title="Сравнение периодов",
                description="Показываем значения метрик по текущему и базовому периоду.",
            )

        if any(dimension.key in time_dimensions for dimension in plan.dimensions):
            return VisualizationSpec(
                chart_type=preferred or "line",
                x_key=plan.dimensions[0].key,
                y_keys=metric_keys,
                title="Динамика по времени",
                description="Показываем, как меняются метрики по временной оси.",
            )

        if plan.dimensions:
            return VisualizationSpec(
                chart_type=preferred or "bar",
                x_key=plan.dimensions[0].key,
                y_keys=metric_keys,
                title="Сравнение по категориям",
                description="Такой график удобен для сравнения городов, статусов, часов и других категорий.",
            )

        return VisualizationSpec(
            chart_type=preferred or "kpi",
            x_key=None,
            y_keys=metric_keys,
            title="Сводные показатели",
            description="Показываем итоговые значения без лишней визуальной нагрузки.",
        )
