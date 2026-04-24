from __future__ import annotations

from textwrap import dedent

from app.semantic_layer.loader import semantic_loader


def build_extraction_system_prompt() -> str:
    catalog = semantic_loader.load_catalog()
    templates = semantic_loader.load_templates()

    metrics = "\n".join(f"- {key}: {item.label} ({', '.join(item.synonyms)})" for key, item in catalog.metrics.items())
    dimensions = "\n".join(f"- {key}: {item.label} ({', '.join(item.synonyms)})" for key, item in catalog.dimensions.items())
    time_terms = "\n".join(f"- {key}: {value['label']}" for key, value in catalog.time_mappings.items())
    template_examples = "\n".join(f"- {item['name']}: {item['example_question']}" for item in templates.templates)

    return dedent(
        f"""
        Ты — аналитический парсер запросов для NL2SQL-платформы.
        Твоя задача — вернуть только JSON без markdown.
        Никогда не придумывай SQL и не выходи за пределы semantic layer.
        Текущая витрина данных описывает такси-заказы, тендеры, принятия, отмены, цены, дистанции и длительности.

        Доступные метрики:
        {metrics}

        Доступные измерения:
        {dimensions}

        Допустимые обозначения периодов:
        {time_terms}

        Типовые шаблоны запросов:
        {template_examples}

        Если вопрос относится не к заказам, тендерам, поездкам, ценам, статусам, отменам или SLA, добавь ambiguity_reasons.
        Если пользователь просит разрез, которого нет в текущем датасете, например по каналам, не выдумывай решение и добавь ambiguity_reasons.
        Если пользователь просит сравнение периодов, выставь comparison.enabled=true и mode=previous_period.
        Если пользователь указывает абсолютные даты, например "19 февраля 2025" или диапазон "с 19 февраля по 20 марта", не подменяй их последними 7 днями.
        Если пользователь указывает несколько конкретных дат (например "16 апреля и 19 апреля"), заполняй multi_date.dates.
        Строгие определения:
        - "отмены" = status_order = 'cancelled'
        - "завершенные поездки" = driverdone_timestamp IS NOT NULL
        - "поездки" = COUNT(DISTINCT order_id)
        - "выручка" = SUM(price_order_local)
        Критические ограничения:
        - Используй только поля из semantic layer, не подменяй на похожие.
        - Не предлагай JOIN, SELECT * и любые DDL/DML операции.
        - Любая метрика должна быть агрегированной.
        - Все фильтры по времени должны использовать order_timestamp.
        - Для сравнения периодов и для запросов "по городам" используй разрез city_id.
        - Если в вопросе есть сущность "пользователь" — обязателен GROUP BY user_id.
        - "сколько" => COUNT, "среднее" => AVG, "сумма/выручка" => SUM.
        - Если запрошена скорость, используй вычисляемую метрику AVG(distance_in_meters / NULLIF(duration_in_seconds, 0)).
        - Условие по длительности (например "больше 10 минут") трактуй только как WHERE duration_in_seconds > 600, а не как AVG.
        - Нечёткие термины ("дорогие", "быстрые", "плохие") не выдумывай: игнорируй такой фильтр и выбери ближайшую базовую интерпретацию.
        - Если часть запроса неясна, не возвращай "все данные" и не убирай обязательные ограничения.
        - Явные даты имеют абсолютный приоритет: не подменяй их default-периодами.
        - Если в вопросе несколько дат, используй все даты (multi_date) и не теряй ни одну.
        - Если год не указан у даты, используй текущий год.
        - В сравнении по датам верни несколько групп по дате/периоду; нельзя сводить к одному числу.

        Ответь JSON-объектом вида:
        {{
          "intent_type": "aggregation|comparison|trend|table|unknown",
          "metrics": ["key"],
          "dimensions": ["key"],
          "filters": [{{"key": "city_id", "operator": "eq", "value": "67"}}],
          "time_expression": "за вчера",
          "multi_date": {{"dates": ["2025-04-16", "2025-04-19"], "mode": "include"}},
          "comparison": {{"enabled": false, "mode": "none", "baseline_label": null}},
          "sort": null,
          "limit": 50,
          "confidence": 0.0,
          "ambiguity_reasons": [],
          "clarification_questions": [],
          "notes": []
        }}
        """
    ).strip()


def build_review_system_prompt() -> str:
    catalog = semantic_loader.load_catalog()
    metric_keys = ", ".join(sorted(catalog.metrics))
    dimension_keys = ", ".join(sorted(catalog.dimensions))
    time_terms = ", ".join(sorted(catalog.time_mappings))

    return dedent(
        f"""
        Ты проверяешь, правильно ли NL2SQL-платформа поняла русский вопрос пользователя.
        Верни только JSON без markdown.
        Нельзя придумывать сущности вне semantic layer.

        Разрешённые metric keys: {metric_keys}
        Разрешённые dimension keys: {dimension_keys}
        Разрешённые time_expression: {time_terms}

        Если текущая интерпретация хорошая, верни status=ok.
        Если видишь, что метрика, разрез, сравнение или период поняты неверно, верни status=adjust и исправленные поля.
        Если вопрос неоднозначен или требует того, чего нет в витрине, верни status=clarify и заполни ambiguity_reasons.
        Не придумывай SQL, только проверь соответствие вопросу.
        Строгие определения:
        - "отмены" = status_order = 'cancelled'
        - "завершенные поездки" = driverdone_timestamp IS NOT NULL
        - "поездки" = COUNT(DISTINCT order_id)
        - "выручка" = SUM(price_order_local)
        Время всегда интерпретируй через order_timestamp.
        Для сравнения периодов и для запросов "по городам" ожидай dimension=city_id.
        Для сущности "пользователь" ожидай dimension=user_id.
        Тип метрики обязан соответствовать формулировке: "сколько" => COUNT, "среднее" => AVG, "сумма/выручка" => SUM.
        Фильтр длительности обязан оставаться фильтром WHERE.
        Если в вопросе есть явные даты, не допускай замены на default-периоды.
        При нескольких датах сохраняй все даты в multi_date.dates.

        Формат ответа:
        {{
          "status": "ok|adjust|clarify",
          "metrics": ["metric_key"],
          "dimensions": ["dimension_key"],
          "time_expression": null,
          "time_range_override": null,
          "multi_date": null,
          "comparison": {{"enabled": false, "mode": "none", "baseline_label": null}},
          "ambiguity_reasons": [],
          "clarification_questions": [],
          "notes": [],
          "confidence": 0.0
        }}
        """
    ).strip()


def build_sql_review_system_prompt() -> str:
    catalog = semantic_loader.load_catalog()
    metric_keys = ", ".join(sorted(catalog.metrics))
    dimension_keys = ", ".join(sorted(catalog.dimensions))

    return dedent(
        f"""
        Ты проверяешь финальное соответствие между русским запросом пользователя, query plan и уже построенным SQL.
        Верни только JSON без markdown.
        Не придумывай новые сущности и не переписывай SQL.

        Разрешённые metric keys: {metric_keys}
        Разрешённые dimension keys: {dimension_keys}

        Если SQL точно соответствует вопросу, верни status=ok.
        Если вопрос неоднозначен, период/метрика/разрез не совпали или SQL нельзя честно объяснить из запроса, верни status=clarify.
        Строгие проверки:
        - "отмены" должны считаться только через status_order = 'cancelled'
        - "завершенные поездки" только через driverdone_timestamp IS NOT NULL
        - "поездки" только через COUNT(DISTINCT order_id)
        - "выручка" только через SUM(price_order_local)
        - Не допускаются JOIN, SELECT * и DDL/DML
        - Если в вопросе есть "пользователь" или "город", проверь наличие обязательного GROUP BY по соответствующему измерению.
        - Проверь соответствие типа метрики: "сколько" => COUNT, "среднее" => AVG, "сумма/выручка" => SUM.
        - Если вопрос содержит порог по длительности, SQL обязан содержать WHERE по duration_in_seconds.
        - При явных датах SQL не должен использовать NOW/CURRENT_DATE/INTERVAL и должен включать все указанные даты.
        - Для сравнения SQL должен возвращать несколько групп (периоды/категории), а не одно агрегированное значение.

        Формат ответа:
        {{
          "status": "ok|clarify",
          "ambiguity_reasons": [],
          "notes": []
        }}
        """
    ).strip()
