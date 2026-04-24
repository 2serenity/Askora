from __future__ import annotations

from collections import defaultdict
from datetime import date
import re
from typing import Any

from sqlalchemy.orm import Session

from app.ai.percent_change import is_percent_change_request
from app.ai.local_intent_model import local_intent_model
from app.models.semantic import SemanticDictionaryEntry
from app.schemas.query import ComparisonSpec, QueryIntent, TimeRange
from app.semantic_layer.loader import semantic_loader
from app.semantic_layer.resolver import SemanticResolver
from app.semantic_layer.time_context import SemanticTimeContext

MONTHS = {
    "января": 1,
    "январь": 1,
    "январе": 1,
    "февраля": 2,
    "февраль": 2,
    "феврале": 2,
    "марта": 3,
    "март": 3,
    "марте": 3,
    "апреля": 4,
    "апрель": 4,
    "апреле": 4,
    "мая": 5,
    "май": 5,
    "мае": 5,
    "июня": 6,
    "июнь": 6,
    "июне": 6,
    "июля": 7,
    "июль": 7,
    "июле": 7,
    "августа": 8,
    "август": 8,
    "августе": 8,
    "сентября": 9,
    "сентябрь": 9,
    "сентябре": 9,
    "октября": 10,
    "октябрь": 10,
    "октябре": 10,
    "ноября": 11,
    "ноябрь": 11,
    "ноябре": 11,
    "декабря": 12,
    "декабрь": 12,
    "декабре": 12,
}

DESTRUCTIVE_PATTERNS = [
    "удали",
    "удалить",
    "удаление",
    "снеси",
    "снести",
    "очисти",
    "очистить",
    "drop",
    "delete",
    "truncate",
    "alter",
    "insert",
    "update",
    "обнови",
    "обновить",
    "измени",
    "изменить",
]

AMBIGUOUS_OUT_OF_DOMAIN_PATTERNS = [
    "айфон",
    "айфонов",
    "iphone",
    "товар",
    "товаров",
]

UNSUPPORTED_ANALYTICS_PATTERNS = {
    "канал": "В текущем датасете нет измерения по каналам. Сформулируйте вопрос по заказам, тендерам, отменам, городам, статусам или времени.",
    "каналы": "В текущем датасете нет измерения по каналам. Сформулируйте вопрос по заказам, тендерам, отменам, городам, статусам или времени.",
    "каналам": "В текущем датасете нет измерения по каналам. Сформулируйте вопрос по заказам, тендерам, отменам, городам, статусам или времени.",
    "прибыль": "В текущем датасете нет себестоимости и прибыли. Доступны выручка, средняя цена заказа, заказы, отмены и тендеры.",
    "прибыли": "В текущем датасете нет себестоимости и прибыли. Доступны выручка, средняя цена заказа, заказы, отмены и тендеры.",
    "маржа": "В текущем датасете нет себестоимости и прибыли. Доступны выручка, средняя цена заказа, заказы, отмены и тендеры.",
}

EXPLICIT_DIMENSION_PHRASES = {
    "по дням": "order_date",
    "по датам": "order_date",
    "по каждому дню": "order_date",
    "в разбивке по дням": "order_date",
    "по неделям": "order_week",
    "понедельно": "order_week",
    "в разбивке по неделям": "order_week",
    "по месяцам": "order_month",
    "помесячно": "order_month",
    "в разбивке по месяцам": "order_month",
    "по часам": "order_hour",
    "по часам дня": "order_hour",
    "по дням недели": "order_dow",
    "по городу": "city_id",
    "в разрезе по городам": "city_id",
    "по каждому городу": "city_id",
    "по статусам заказа": "order_status",
    "по статусу заказа": "order_status",
    "по статусам": "order_status",
    "по статусам тендера": "tender_status",
    "по статусу тендера": "tender_status",
    "по причинам отмен": "cancel_source",
    "по источникам отмен": "cancel_source",
    "по причине отмены": "cancel_source",
    "по городам": "city_id",
    "по пользователям": "user_id",
    "по user": "user_id",
    "в разрезе пользователей": "user_id",
    "по каждому пользователю": "user_id",
}

VAGUE_TERM_PATTERNS = ["дорог", "быстр", "плох", "хорош", "дешев"]

MONTH_PATTERN = "|".join(sorted({re.escape(month) for month in MONTHS}, key=len, reverse=True))
TEXTUAL_DATE_PATTERN = rf"\d{{1,2}}\s+(?:{MONTH_PATTERN})(?:\s+\d{{4}})?"
NUMERIC_DATE_PATTERN = r"\d{1,2}\.\d{1,2}(?:\.\d{2,4})?"


class HybridIntentExtractor:
    def __init__(self, db: Session):
        self.db = db
        self.catalog = semantic_loader.load_catalog()
        self.resolver = SemanticResolver(db)
        self.time_context = SemanticTimeContext(db)

    def extract(self, question: str) -> QueryIntent:
        intent, _ = self.extract_with_trace(question)
        return intent

    def extract_with_trace(self, question: str) -> tuple[QueryIntent, dict[str, Any]]:
        question_normalized = self._normalize_text(question)
        rule_based = self._rule_based_parse(question_normalized)
        local_based, local_trace = self._local_parse(question)
        merged = self._merge(rule_based, local_based)
        merged["question"] = question
        trace = {
            "normalized_question": question_normalized,
            "rule_based": {
                "metrics": rule_based.get("metrics", []),
                "dimensions": rule_based.get("dimensions", []),
                "time_expression": rule_based.get("time_expression"),
                "time_range_override": rule_based.get("time_range_override"),
                "multi_date": rule_based.get("multi_date"),
                "comparison": rule_based.get("comparison"),
                "preferred_chart_type": rule_based.get("preferred_chart_type"),
                "ambiguity_reasons": rule_based.get("ambiguity_reasons", []),
                "notes": rule_based.get("notes", []),
            },
            "llm": {
                "enabled": False,
                "used_provider": None,
                "used_model": None,
                "attempts": [],
                "status": "local_only_mode",
            },
            "local_refinement": local_trace,
            "merged": {
                "metrics": merged.get("metrics", []),
                "dimensions": merged.get("dimensions", []),
                "time_expression": merged.get("time_expression"),
                "time_range_override": merged.get("time_range_override"),
                "multi_date": merged.get("multi_date"),
                "comparison": merged.get("comparison"),
                "preferred_chart_type": merged.get("preferred_chart_type"),
                "confidence": merged.get("confidence"),
            },
            "effective_source": self._effective_source(local_based),
        }
        return QueryIntent.model_validate(merged), trace

    def _rule_based_parse(self, question: str) -> dict[str, Any]:
        metric_hits = self._match_metric_keys(question)
        metric_hits, metric_notes = self._align_metrics_with_request_type(question, metric_hits)
        dimension_hits = self._match_dimension_keys(question)
        filters, filter_notes = self._extract_filters(question)
        explicit_comparison, explicit_time_range, explicit_comparison_notes = self._extract_explicit_comparison_period(question)
        time_expression, time_range_override, discrete_dates, time_notes = self._extract_time_range(question)
        if explicit_time_range:
            time_expression = None
            time_range_override = explicit_time_range
        comparison = explicit_comparison or self._detect_comparison(question)
        preferred_chart_type, chart_notes = self._extract_chart_preference(question)
        if len(discrete_dates) > 1:
            if "order_date" not in dimension_hits:
                dimension_hits.append("order_date")
            if comparison.enabled and not self._requests_percent_change(question):
                comparison = ComparisonSpec()
            if not preferred_chart_type:
                preferred_chart_type = "bar"

        intent_type = self._detect_intent_type(question, comparison.enabled, dimension_hits)
        ambiguity_reasons = self._detect_ambiguity(
            question,
            metric_hits=metric_hits,
            filters=filters,
            time_expression=time_expression,
            time_range_override=time_range_override,
            discrete_dates=discrete_dates,
            comparison=comparison,
        )

        notes: list[str] = [*time_notes, *metric_notes, *filter_notes, *chart_notes, *explicit_comparison_notes]
        if comparison.enabled:
            notes.append("Обнаружен сравнительный запрос между периодами.")
        if not metric_hits and not ambiguity_reasons:
            notes.append("Метрика не распознана явно, поэтому система может использовать безопасную метрику по умолчанию.")

        confidence = 0.35
        if metric_hits:
            confidence += 0.25
        if dimension_hits:
            confidence += 0.15
        if time_expression or time_range_override or discrete_dates:
            confidence += 0.15
        if comparison.enabled:
            confidence += 0.05
        if ambiguity_reasons:
            confidence -= 0.35

        clarification_questions: list[str] = []
        if ambiguity_reasons:
            clarification_questions.append(
                "Сформулируйте аналитический вопрос по заказам, тендерам, отменам, цене, длительности или дистанции."
            )

        return {
            "intent_type": intent_type,
            "metrics": metric_hits,
            "dimensions": dimension_hits,
            "filters": filters,
            "time_expression": time_expression,
            "time_range_override": time_range_override.model_dump(mode="json") if time_range_override else None,
            "multi_date": {"dates": [item.isoformat() for item in discrete_dates], "mode": "include"} if discrete_dates else None,
            "comparison": comparison.model_dump(),
            "preferred_chart_type": preferred_chart_type,
            "sort": None,
            "limit": 50,
            "confidence": max(0.1, min(confidence, 0.95)),
            "ambiguity_reasons": ambiguity_reasons,
            "clarification_questions": clarification_questions,
            "notes": notes,
        }

    def _align_metrics_with_request_type(self, question: str, metric_keys: list[str]) -> tuple[list[str], list[str]]:
        if len(metric_keys) > 1:
            return metric_keys, []

        requested_kind = self._detect_requested_metric_kind(question)
        if not requested_kind:
            return metric_keys, []

        matching = [key for key in metric_keys if self._metric_kind(key) == requested_kind]
        if matching:
            return matching, []

        if metric_keys:
            fallback = self._default_metric_for_kind(question, requested_kind)
            if fallback:
                return [fallback], [f"Метрика приведена к типу запроса: {requested_kind}."]
            return metric_keys, []

        fallback = self._default_metric_for_kind(question, requested_kind)
        if fallback:
            return [fallback], [f"Метрика выбрана по типу запроса: {requested_kind}."]
        return metric_keys, []

    def _detect_requested_metric_kind(self, question: str) -> str | None:
        if any(token in question for token in ["средн", "в среднем"]):
            return "avg"
        if any(token in question for token in ["сумм", "выручк", "доход", "оборот", "денег", "деньгам", "касс"]):
            return "sum"
        if "сколько" in question and "сколько процентов" not in question:
            return "count"
        return None

    def _default_metric_for_kind(self, question: str, kind: str) -> str | None:
        if kind == "count":
            return "total_orders" if "total_orders" in self.catalog.metrics else None
        if kind == "sum":
            return "total_revenue" if "total_revenue" in self.catalog.metrics else None
        if kind == "avg":
            if "скорост" in question and "avg_speed_mps" in self.catalog.metrics:
                return "avg_speed_mps"
            return "avg_order_price" if "avg_order_price" in self.catalog.metrics else None
        return None

    def _metric_kind(self, metric_key: str) -> str | None:
        metric = self.catalog.metrics.get(metric_key)
        if not metric:
            return None
        expression = metric.sql.upper()
        if "COUNT(" in expression:
            return "count"
        if "AVG(" in expression:
            return "avg"
        if "SUM(" in expression:
            return "sum"
        return None

    def _local_parse(self, question: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        return local_intent_model.extract_json_with_trace(question)

    def _merge(self, rule_based: dict[str, Any], local_based: dict[str, Any] | None) -> dict[str, Any]:
        if not local_based:
            return rule_based

        local_based = local_based or {}
        preserve_rule_disambiguation = self._should_preserve_rule_disambiguation(rule_based)
        merged_lists = defaultdict(list)
        for key in ["filters", "ambiguity_reasons", "clarification_questions", "notes"]:
            merged_lists[key] = list(rule_based.get(key, []))
            local_items = local_based.get(key, [])
            if preserve_rule_disambiguation and key in {"ambiguity_reasons", "clarification_questions"}:
                local_items = []
            for item in local_items:
                if item not in merged_lists[key]:
                    merged_lists[key].append(item)

        rule_comparison = ComparisonSpec.model_validate(rule_based.get("comparison") or {})
        local_comparison = ComparisonSpec.model_validate(local_based.get("comparison") or {})

        merged_metrics = self._prefer_list(rule_based.get("metrics"), local_based.get("metrics"))
        merged_dimensions = self._prefer_list(rule_based.get("dimensions"), local_based.get("dimensions"))

        return {
            "intent_type": rule_based.get("intent_type")
            if rule_based.get("intent_type") != "unknown"
            else (local_based.get("intent_type") or "unknown"),
            "metrics": merged_metrics,
            "dimensions": merged_dimensions,
            "filters": merged_lists["filters"],
            "time_expression": rule_based.get("time_expression") or local_based.get("time_expression"),
            "time_range_override": rule_based.get("time_range_override") or local_based.get("time_range_override"),
            "multi_date": rule_based.get("multi_date") or local_based.get("multi_date"),
            "comparison": (
                rule_comparison.model_dump()
                if rule_comparison.enabled
                else local_comparison.model_dump()
            ),
            "preferred_chart_type": rule_based.get("preferred_chart_type")
            or local_based.get("preferred_chart_type"),
            "sort": rule_based.get("sort") or local_based.get("sort"),
            "limit": local_based.get("limit") or rule_based.get("limit"),
            "confidence": max(
                rule_based.get("confidence", 0),
                min(local_based.get("confidence", 0), 0.95),
            ),
            "ambiguity_reasons": merged_lists["ambiguity_reasons"],
            "clarification_questions": merged_lists["clarification_questions"],
            "notes": merged_lists["notes"],
        }

    def _effective_source(self, local_based: dict[str, Any] | None) -> str:
        if local_based:
            return "hybrid_local"
        return "rules_only"

    def _prefer_list(self, *sources: list[str] | None) -> list[str]:
        for source in sources:
            if source:
                return source
        return []

    def _should_preserve_rule_disambiguation(self, rule_based: dict[str, Any]) -> bool:
        if rule_based.get("ambiguity_reasons"):
            return False
        multi_date = rule_based.get("multi_date") or {}
        explicit_dates = multi_date.get("dates") or []
        has_explicit_structure = bool(rule_based.get("time_range_override")) or len(explicit_dates) >= 2
        return has_explicit_structure and bool(rule_based.get("metrics"))

    def _match_metric_keys(self, question: str) -> list[str]:
        matches: list[str] = list(self._match_compound_metrics(question))
        occupied_spans: list[tuple[int, int]] = []

        metric_aliases = sorted(self._collect_metric_aliases(), key=lambda item: len(item[0]), reverse=True)
        for alias, key in metric_aliases:
            for match in re.finditer(re.escape(alias), question):
                span = match.span()
                if any(not (span[1] <= taken[0] or span[0] >= taken[1]) for taken in occupied_spans):
                    continue
                occupied_spans.append(span)
                matches.append(key)
                break

        if not matches:
            matches.extend(self._match_metric_typos(question, metric_aliases))

        unique_matches: list[str] = []
        for key in matches:
            if key not in unique_matches:
                unique_matches.append(key)
        return unique_matches

    def _match_metric_typos(self, question: str, aliases: list[tuple[str, str]]) -> list[str]:
        matches: list[str] = []
        seen_keys: set[str] = set()
        for token_match in re.finditer(r"\b[0-9a-zа-яё_-]{4,}\b", question):
            token = token_match.group(0)
            best_key: str | None = None
            best_distance: int | None = None
            best_alias_length = -1
            for alias, key in aliases:
                if " " in alias or len(alias) < 5 or alias == token:
                    continue
                if abs(len(alias) - len(token)) > 1:
                    continue
                if alias[0] != token[0] or alias[-1] != token[-1]:
                    continue
                if not self._is_safe_single_typo(token, alias):
                    continue
                distance = self._levenshtein_distance(token, alias)
                if distance > 1:
                    continue
                if (
                    best_distance is None
                    or distance < best_distance
                    or (distance == best_distance and len(alias) > best_alias_length)
                ):
                    best_key = key
                    best_distance = distance
                    best_alias_length = len(alias)
            if best_key and best_key not in seen_keys:
                matches.append(best_key)
                seen_keys.add(best_key)
        return matches

    def _is_safe_single_typo(self, token: str, alias: str) -> bool:
        if token == alias:
            return False
        if self._levenshtein_distance(token, alias) <= 1:
            return True
        if len(token) != len(alias):
            return False
        mismatches = [index for index, (left, right) in enumerate(zip(token, alias)) if left != right]
        if len(mismatches) != 2:
            return False
        first, second = mismatches
        return second == first + 1 and token[first] == alias[second] and token[second] == alias[first]

    def _levenshtein_distance(self, source: str, target: str) -> int:
        if source == target:
            return 0
        if not source:
            return len(target)
        if not target:
            return len(source)
        previous = list(range(len(target) + 1))
        for index, source_char in enumerate(source, start=1):
            current = [index]
            for target_index, target_char in enumerate(target, start=1):
                insertion = current[target_index - 1] + 1
                deletion = previous[target_index] + 1
                substitution = previous[target_index - 1] + (source_char != target_char)
                current.append(min(insertion, deletion, substitution))
            previous = current
        return previous[-1]

    def _match_compound_metrics(self, question: str) -> list[str]:
        matches: list[str] = []
        completion_rate_requested = bool(
            re.search(r"(процент|дол[яю]).*((выполненн|завершенн)\w*\s+заказ\w+)", question)
        )
        if completion_rate_requested:
            matches.append("order_completion_rate")
        if not completion_rate_requested and re.search(r"(выполненн|завершенн)\w*\s+заказ\w*", question):
            matches.append("completed_orders")
        if "отмен" in question and re.search(r"клиент\w+\s+и\s+водител\w+", question):
            matches.extend(["client_cancellations", "driver_cancellations"])
        if re.search(r"(выполненн\w+|поездк\w+)\s+и\s+отмен", question):
            matches.extend(["completed_orders", "cancelled_orders"])
        if re.search(r"отмен\w+\s+и\s+(выполненн\w+|поездк\w+)", question):
            matches.extend(["completed_orders", "cancelled_orders"])
        if re.search(r"выручк\w+.*\bи\b.*(выполненн\w+|поездк\w+)", question):
            matches.extend(["total_revenue", "completed_orders"])
        return matches

    def _collect_metric_aliases(self) -> list[tuple[str, str]]:
        aliases: list[tuple[str, str]] = []
        for key, metric in self.catalog.metrics.items():
            for alias in metric.synonyms:
                aliases.append((self._normalize_text(alias), key))
        for term, config in self.catalog.business_terms.items():
            if config.get("entity_type") != "metric":
                continue
            target_key = config.get("target_key")
            if target_key in self.catalog.metrics:
                aliases.append((self._normalize_text(term), target_key))
        for entry in self.db.query(SemanticDictionaryEntry).filter(SemanticDictionaryEntry.is_active.is_(True)).all():
            if entry.target_key not in self.catalog.metrics:
                continue
            aliases.append((self._normalize_text(entry.term), entry.target_key))
            for alias in entry.synonyms_json:
                aliases.append((self._normalize_text(alias), entry.target_key))
        return aliases

    def _match_dimension_keys(self, question: str) -> list[str]:
        matches: list[str] = []
        occupied_spans: list[tuple[int, int]] = []

        for phrase, key in sorted(EXPLICIT_DIMENSION_PHRASES.items(), key=lambda item: len(item[0]), reverse=True):
            for match in re.finditer(re.escape(phrase), question):
                span = match.span()
                if any(not (span[1] <= taken[0] or span[0] >= taken[1]) for taken in occupied_spans):
                    continue
                occupied_spans.append(span)
                if key not in matches:
                    matches.append(key)
                break

        for alias, key in sorted(self._collect_dimension_aliases(), key=lambda item: len(item[0]), reverse=True):
            for match in re.finditer(re.escape(alias), question):
                span = match.span()
                if any(not (span[1] <= taken[0] or span[0] >= taken[1]) for taken in occupied_spans):
                    continue
                occupied_spans.append(span)
                if key not in matches:
                    matches.append(key)
                break

        return matches

    def _collect_dimension_aliases(self) -> list[tuple[str, str]]:
        aliases: list[tuple[str, str]] = []
        for key, dimension in self.catalog.dimensions.items():
            for alias in dimension.synonyms:
                normalized_alias = self._normalize_text(alias)
                if dimension.kind == "time" and not self._is_explicit_grouping_alias(normalized_alias):
                    continue
                aliases.append((normalized_alias, key))
        for term, config in self.catalog.business_terms.items():
            if config.get("entity_type") != "dimension":
                continue
            target_key = config.get("target_key")
            if target_key in self.catalog.dimensions:
                aliases.append((self._normalize_text(term), target_key))
        for entry in self.db.query(SemanticDictionaryEntry).filter(SemanticDictionaryEntry.is_active.is_(True)).all():
            if entry.target_key not in self.catalog.dimensions:
                continue
            aliases.append((self._normalize_text(entry.term), entry.target_key))
            for alias in entry.synonyms_json:
                aliases.append((self._normalize_text(alias), entry.target_key))
        return aliases

    def _is_explicit_grouping_alias(self, alias: str) -> bool:
        grouping_markers = ("по ", "разбив", "помесяч", "понедел", "по дня", "сгрупп")
        return any(marker in alias for marker in grouping_markers)

    def _extract_filters(self, question: str) -> tuple[list[dict[str, Any]], list[str]]:
        filters: list[dict[str, Any]] = []
        notes: list[str] = []
        city_match = re.search(r"(?:город(?:\s+id)?|city)\s*(\d+)", question)
        if city_match:
            filters.append({"key": "city_id", "operator": "eq", "value": city_match.group(1)})
        user_match = re.search(r"(?:пользователь|user(?:_?id)?)\s*([a-zA-Z0-9_-]+)", question)
        if user_match:
            filters.append({"key": "user_id", "operator": "eq", "value": user_match.group(1)})
        if any(token in question for token in ["выходн", "по выходным", "на выходных"]):
            filters.append({"key": "order_dow", "operator": "in", "value": [0, 6]})
        elif any(token in question for token in ["будн", "по будням", "в будни"]):
            filters.append({"key": "order_dow", "operator": "in", "value": [1, 2, 3, 4, 5]})

        duration_gt_match = re.search(r"длител\w+\s+(?:больш[е]|выше)\s+(\d+)\s*мин", question)
        if duration_gt_match:
            filters.append({"key": "duration_seconds", "operator": "gt", "value": int(duration_gt_match.group(1)) * 60})

        duration_gte_match = re.search(r"длител\w+\s+(?:не\s+менее|минимум)\s+(\d+)\s*мин", question)
        if duration_gte_match:
            filters.append({"key": "duration_seconds", "operator": "gte", "value": int(duration_gte_match.group(1)) * 60})

        duration_lt_match = re.search(r"длител\w+\s+(?:меньше|ниже)\s+(\d+)\s*мин", question)
        if duration_lt_match:
            filters.append({"key": "duration_seconds", "operator": "lt", "value": int(duration_lt_match.group(1)) * 60})

        duration_lte_match = re.search(r"длител\w+\s+(?:не\s+более|максимум)\s+(\d+)\s*мин", question)
        if duration_lte_match:
            filters.append({"key": "duration_seconds", "operator": "lte", "value": int(duration_lte_match.group(1)) * 60})

        if any(re.search(rf"\b{pattern}\w*\b", question) for pattern in VAGUE_TERM_PATTERNS):
            notes.append("Нечёткие качественные термины в фильтрах проигнорированы; применена базовая интерпретация без таких условий.")

        return filters, notes

    def _extract_time_range(self, question: str) -> tuple[str | None, TimeRange | None, list[date], list[str]]:
        range_match = re.search(
            rf"(?:с|за период с)\s+({TEXTUAL_DATE_PATTERN}|{NUMERIC_DATE_PATTERN})\s+по\s+({TEXTUAL_DATE_PATTERN}|{NUMERIC_DATE_PATTERN})",
            question,
        )
        if range_match:
            start_text = range_match.group(1)
            end_text = range_match.group(2)
            start_date, end_date, note = self._parse_date_range(start_text, end_text)
            label = f"С {self._pretty_date_label(start_text, start_date)} по {self._pretty_date_label(end_text, end_date)}"
            return (
                None,
                TimeRange(label=label, start_date=start_date, end_date=end_date, grain="day"),
                [],
                [note] if note else [],
            )

        explicit_dates, explicit_date_notes = self._extract_explicit_dates(question)
        if explicit_dates:
            if len(explicit_dates) >= 2:
                return (
                    None,
                    TimeRange(
                        label=f"Выбранные даты: {', '.join(item.isoformat() for item in explicit_dates)}",
                        start_date=min(explicit_dates),
                        end_date=max(explicit_dates),
                        grain="day",
                    ),
                    explicit_dates,
                    explicit_date_notes,
                )
            only_date = explicit_dates[0]
            return (
                None,
                TimeRange(
                    label=only_date.isoformat(),
                    start_date=only_date,
                    end_date=only_date,
                    grain="day",
                ),
                [],
                explicit_date_notes,
            )

        month_match = re.search(rf"(?:за|в)\s+({MONTH_PATTERN})(?:\s+(\d{{4}}))?", question)
        if month_match:
            month_token = month_match.group(1)
            explicit_year = int(month_match.group(2)) if month_match.group(2) else None
            month = MONTHS.get(month_token)
            if month:
                start_date, end_date, is_partial = self.time_context.month_range(month, explicit_year)
                notes: list[str] = []
                if explicit_year is None:
                    notes.append(
                        f"Период интерпретирован как {start_date.isoformat()} - {end_date.isoformat()}, потому что год в запросе не указан."
                    )
                if is_partial:
                    notes.append(
                        f"Месяц ещё не завершён в данных, поэтому использован период по последнюю доступную дату: {end_date.isoformat()}."
                    )
                return (
                    None,
                    TimeRange(
                        label=self._build_month_label(month_token, start_date.year),
                        start_date=start_date,
                        end_date=end_date,
                        grain="day",
                    ),
                    [],
                    notes,
                )

        if "относительно прошлого месяца" in question or "к прошлому месяцу" in question or "относительно предыдущего месяца" in question:
            return "текущий месяц", None, [], []

        all_time_match = re.search(r"(?:за\s+)?(?:все|всё)\s+время|за\s+весь\s+период", question)
        if all_time_match:
            start_date, end_date = self.time_context.all_time_range()
            return (
                None,
                TimeRange(label="Всё время", start_date=start_date, end_date=end_date, grain="day"),
                [],
                [f"Использован весь доступный период данных: {start_date.isoformat()} - {end_date.isoformat()}."],
            )

        explicit_year_match = re.search(r"(?:за|в)\s+(\d{4})(?:\s+г(?:од|ода|оду|одом)?)?", question)
        if explicit_year_match:
            year = int(explicit_year_match.group(1))
            start_date, end_date, is_partial = self.time_context.calendar_year_range(year)
            notes: list[str] = []
            if is_partial:
                notes.append(
                    f"Год ещё не завершён в данных, поэтому использован период по последнюю доступную дату: {end_date.isoformat()}."
                )
            return (
                None,
                TimeRange(label=f"{year} год", start_date=start_date, end_date=end_date, grain="day"),
                [],
                notes,
            )

        rolling_year_match = re.search(r"(?:за|в)\s+(?:последний\s+год|год)\b", question)
        if rolling_year_match:
            start_date, end_date = self.time_context.rolling_year_range()
            return (
                None,
                TimeRange(label="Последние 12 календарных месяцев", start_date=start_date, end_date=end_date, grain="day"),
                [],
                [f"Период интерпретирован как последние 12 календарных месяцев: {start_date.isoformat()} - {end_date.isoformat()}."],
            )

        for phrase in sorted(self.catalog.time_mappings, key=len, reverse=True):
            if phrase in question:
                return phrase, None, [], []

        return None, None, [], []

    def _extract_explicit_comparison_period(
        self,
        question: str,
    ) -> tuple[ComparisonSpec | None, TimeRange | None, list[str]]:
        month_comparison = re.search(
            rf"(?:за|в)\s+({MONTH_PATTERN})(?:\s+(\d{{4}}))?\s+(?:относительно|по сравнению с|сравнительно с|к)\s+({MONTH_PATTERN})(?:\s+(\d{{4}}))?",
            question,
        )
        if not month_comparison:
            return None, None, []

        current_month_token = month_comparison.group(1)
        current_year = int(month_comparison.group(2)) if month_comparison.group(2) else None
        baseline_month_token = month_comparison.group(3)
        baseline_year = int(month_comparison.group(4)) if month_comparison.group(4) else None

        current_month = MONTHS.get(current_month_token)
        baseline_month = MONTHS.get(baseline_month_token)
        if not current_month or not baseline_month:
            return None, None, []

        current_start, current_end, current_partial = self.time_context.month_range(current_month, current_year)
        baseline_start, baseline_end, baseline_partial = self.time_context.month_range(baseline_month, baseline_year)

        notes: list[str] = []
        if current_year is None:
            notes.append(f"Для текущего месяца автоматически выбран год {current_start.year}.")
        if baseline_year is None:
            notes.append(f"Для базового месяца автоматически выбран год {baseline_start.year}.")
        if current_partial:
            notes.append(f"Текущий месяц в данных неполный, поэтому период ограничен датой {current_end.isoformat()}.")
        if baseline_partial:
            notes.append(f"Базовый месяц в данных неполный, поэтому период ограничен датой {baseline_end.isoformat()}.")

        return (
            ComparisonSpec(
                enabled=True,
                mode="previous_period",
                baseline_label=self._build_month_label(baseline_month_token, baseline_start.year),
                baseline_start_date=baseline_start,
                baseline_end_date=baseline_end,
            ),
            TimeRange(
                label=self._build_month_label(current_month_token, current_start.year),
                start_date=current_start,
                end_date=current_end,
                grain="day",
            ),
            notes,
        )

    def _extract_chart_preference(self, question: str) -> tuple[str | None, list[str]]:
        notes: list[str] = []
        if "не линейн" in question or "не лини" in question:
            notes.append("По формулировке запроса линейный график заменён на столбчатый.")
            return "bar", notes
        if "столб" in question or "гистограмм" in question or "bar" in question:
            return "bar", notes
        if "линейн" in question:
            return "line", notes
        if "кругов" in question or "pie" in question:
            return "pie", notes
        if "таблиц" in question or "без граф" in question:
            return "table", notes
        if "карточк" in question or "kpi" in question:
            return "kpi", notes
        return None, notes

    def _requests_percent_change(self, question: str) -> bool:
        return is_percent_change_request(question)

    def _detect_comparison(self, question: str) -> ComparisonSpec:
        if "этот год" in question and "прошлый год" in question:
            return ComparisonSpec(enabled=True, mode="year_over_year", baseline_label="Прошлый год")
        if any(token in question for token in ["сравни", "сравнение", "по сравнению", "в сравнении"]):
            return ComparisonSpec(enabled=True, mode="previous_period", baseline_label="Предыдущий период")
        if re.search(r"\b(текущ\w+|эт\w+)\b.*\bи\s+(прошл\w+|предыдущ\w+)\b", question):
            return ComparisonSpec(enabled=True, mode="previous_period", baseline_label="Предыдущий период")
        if is_percent_change_request(question):
            return ComparisonSpec(enabled=True, mode="previous_period", baseline_label="Предыдущий период")
        return ComparisonSpec()

    def _detect_intent_type(self, question: str, comparison_enabled: bool, dimension_hits: list[str]) -> str:
        if comparison_enabled:
            return "comparison"
        if any(token in question for token in ["динамика", "тренд", "по дням", "по неделям", "по месяцам", "по часам"]):
            return "trend"
        if dimension_hits:
            return "aggregation"
        return "aggregation"

    def _detect_ambiguity(
        self,
        question: str,
        *,
        metric_hits: list[str],
        filters: list[dict[str, Any]],
        time_expression: str | None,
        time_range_override: TimeRange | None,
        discrete_dates: list[date],
        comparison: ComparisonSpec,
    ) -> list[str]:
        reasons: list[str] = []

        if any(pattern in question for pattern in DESTRUCTIVE_PATTERNS):
            reason = "Запрос похож на команду изменения или удаления данных. Платформа работает только в режиме чтения и не выполняет такие действия."
            if reason not in reasons:
                reasons.append(reason)

        if any(pattern in question for pattern in AMBIGUOUS_OUT_OF_DOMAIN_PATTERNS):
            reason = "Текущий датасет описывает заказы такси, тендеры, отмены, цену, длительность и дистанцию. Такой запрос требует другой витрины данных."
            if reason not in reasons:
                reasons.append(reason)

        for pattern, reason in UNSUPPORTED_ANALYTICS_PATTERNS.items():
            if pattern in question and reason not in reasons:
                reasons.append(reason)

        multiple_dates_reason = self._detect_multiple_discrete_dates(question)
        if multiple_dates_reason and multiple_dates_reason not in reasons:
            reasons.append(multiple_dates_reason)

        normalized = self._normalize_text(question)
        has_time_context = bool(time_expression or time_range_override or discrete_dates)
        has_metric_context = bool(metric_hits)
        change_tokens = ("падени", "упал", "упали", "упало", "просел", "просела", "просели", "снижен", "снизил")
        asks_for_reason = "почему" in normalized
        describes_change = any(token in normalized for token in change_tokens) or is_percent_change_request(normalized)
        if describes_change and not has_metric_context and not has_time_context and not filters:
            reasons.append("Уточните, что именно упало или изменилось и за какой период нужно это анализировать.")
        elif asks_for_reason and describes_change and not has_time_context and not comparison.enabled:
            reasons.append("Чтобы объяснить падение, укажите период или базу сравнения. Например: «почему продажи упали в выходные за прошлый месяц» или «сравни выходные этой недели и прошлой».")

        return reasons

    def _detect_multiple_discrete_dates(self, question: str) -> str | None:
        if self._has_explicit_date_range(question):
            return None
        explicit_dates, _ = self._extract_explicit_dates(question)
        if len(explicit_dates) >= 2:
            return None

        unique_matches = self._extract_discrete_dates(question)
        if len(unique_matches) >= 2:
            return "В вопросе указано несколько отдельных дат. Уточните диапазон через «с ... по ...» или выберите одну дату."
        return None

    def _has_explicit_date_range(self, question: str) -> bool:
        return bool(
            re.search(
                rf"(?:с|за период с)\s+({TEXTUAL_DATE_PATTERN}|{NUMERIC_DATE_PATTERN})\s+по\s+({TEXTUAL_DATE_PATTERN}|{NUMERIC_DATE_PATTERN})",
                question,
            )
        )

    def _extract_discrete_dates(self, question: str) -> list[str]:
        matches = re.findall(rf"{TEXTUAL_DATE_PATTERN}|{NUMERIC_DATE_PATTERN}", question)
        unique_matches: list[str] = []
        for item in matches:
            value = item.strip()
            if value and value not in unique_matches:
                unique_matches.append(value)
        return unique_matches

    def _extract_two_date_pair(self, question: str) -> tuple[date, date, str | None] | None:
        pair_match = re.search(
            rf"({TEXTUAL_DATE_PATTERN}|{NUMERIC_DATE_PATTERN})\s+и\s+({TEXTUAL_DATE_PATTERN}|{NUMERIC_DATE_PATTERN})",
            question,
        )
        if not pair_match:
            return None

        first_date, first_note = self._parse_single_date(pair_match.group(1))
        second_date, second_note = self._parse_single_date(pair_match.group(2))
        if not first_date or not second_date:
            return None

        notes = [item for item in [first_note, second_note] if item]
        note = " ".join(notes) if notes else "Запрос с двумя датами интерпретирован как период от первой даты до второй."
        return first_date, second_date, note

    def _extract_explicit_dates(self, question: str) -> tuple[list[date], list[str]]:
        collected: list[date] = []
        notes: list[str] = []

        shared_month_match = re.search(
            rf"(\d{{1,2}})\s*(?:,|и)\s*(\d{{1,2}})\s+({MONTH_PATTERN})(?:\s+(\d{{4}}))?",
            question,
        )
        if shared_month_match:
            day_a = int(shared_month_match.group(1))
            day_b = int(shared_month_match.group(2))
            month_token = shared_month_match.group(3)
            explicit_year = int(shared_month_match.group(4)) if shared_month_match.group(4) else None
            month = MONTHS.get(month_token)
            if month:
                year = explicit_year or date.today().year
                for day in (day_a, day_b):
                    parsed = self._safe_date(year, month, day)
                    if parsed and parsed not in collected:
                        collected.append(parsed)
                if explicit_year is None:
                    notes.append(f"Для дат без года использован текущий год: {year}.")

        for token in self._extract_discrete_dates(question):
            parsed_date, note = self._parse_single_date(token)
            if not parsed_date:
                continue
            if parsed_date not in collected:
                collected.append(parsed_date)
            if note and note not in notes:
                notes.append(note)

        collected.sort()
        return collected, notes

    def _parse_date_range(self, start_text: str, end_text: str) -> tuple[date, date, str | None]:
        anchor = date.today()
        start_parts = self._parse_date_parts(start_text)
        end_parts = self._parse_date_parts(end_text)

        if not start_parts or not end_parts:
            return anchor, anchor, None

        start_day, start_month, start_year = start_parts
        end_day, end_month, end_year = end_parts

        if start_year is not None and end_year is not None:
            start_date = self._safe_date(start_year, start_month, start_day)
            end_date = self._safe_date(end_year, end_month, end_day)
        elif end_year is not None:
            end_date = self._safe_date(end_year, end_month, end_day)
            inferred_start_year = end_year if (start_month, start_day) <= (end_month, end_day) else end_year - 1
            start_date = self._safe_date(inferred_start_year, start_month, start_day)
        elif start_year is not None:
            start_date = self._safe_date(start_year, start_month, start_day)
            inferred_end_year = start_year if (end_month, end_day) >= (start_month, start_day) else start_year + 1
            end_date = self._safe_date(inferred_end_year, end_month, end_day)
        else:
            base_year = date.today().year
            end_date = self._safe_date(base_year, end_month, end_day)
            inferred_start_year = base_year if (start_month, start_day) <= (end_month, end_day) else base_year - 1
            start_date = self._safe_date(inferred_start_year, start_month, start_day)

        if not start_date or not end_date:
            return anchor, anchor, None

        if end_date < start_date:
            shifted_end = self._safe_date(start_date.year + 1, end_date.month, end_date.day)
            end_date = shifted_end or end_date

        note = None
        if start_year is None and end_year is None:
            note = f"Период интерпретирован как {start_date.isoformat()} - {end_date.isoformat()} с использованием текущего года."
        elif start_year is None or end_year is None:
            note = f"Период интерпретирован как {start_date.isoformat()} - {end_date.isoformat()} с учётом указанной части даты."

        return start_date, end_date, note

    def _parse_single_date(self, text: str) -> tuple[date | None, str | None]:
        parts = self._parse_date_parts(text)
        if not parts:
            return None, None

        day, month, explicit_year = parts
        if explicit_year is not None:
            parsed_date = self._safe_date(explicit_year, month, day)
            return parsed_date, None

        current_year = date.today().year
        parsed_date = self._safe_date(current_year, month, day)
        if not parsed_date:
            return None, None
        return parsed_date, f"Период интерпретирован как {parsed_date.isoformat()} с использованием текущего года."

    def _parse_date_parts(self, text: str) -> tuple[int, int, int | None] | None:
        stripped = text.strip()

        numeric_match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?", stripped)
        if numeric_match:
            day = int(numeric_match.group(1))
            month = int(numeric_match.group(2))
            year = self._normalize_year_token(numeric_match.group(3))
            return day, month, year

        match = re.fullmatch(rf"(\d{{1,2}})\s+({MONTH_PATTERN})(?:\s+(\d{{4}}))?", stripped)
        if not match:
            return None

        day = int(match.group(1))
        month_token = match.group(2)
        month = MONTHS.get(month_token)
        year = int(match.group(3)) if match.group(3) else None
        if not month:
            return None

        return day, month, year

    def _normalize_year_token(self, token: str | None) -> int | None:
        if not token:
            return None
        if len(token) == 2:
            return 2000 + int(token)
        return int(token)

    def _safe_date(self, year: int, month: int, day: int) -> date | None:
        try:
            return date(year, month, day)
        except ValueError:
            return None

    def _pretty_date_label(self, text: str, parsed_date: date | None = None) -> str:
        normalized = text[:1].upper() + text[1:]
        if re.search(r"\d{4}", text):
            return normalized
        if parsed_date is None:
            return normalized
        return f"{normalized} {parsed_date.year}"

    def _build_month_label(self, month_token: str, year: int) -> str:
        return f"{month_token[:1].upper() + month_token[1:]} {year}"

    def _normalize_text(self, value: str) -> str:
        normalized = value.lower().replace("ё", "е")
        normalized = re.sub(r"[,;:!\?\(\)\[\]\{\}\"'`]+", " ", normalized)
        normalized = re.sub(r"\b(пожалуйста|плиз|будьте добры|будь добра|будь добр|мне надо|мне нужно|мне бы|покажи мне|посмотри|глянь|скажи)\b", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()
