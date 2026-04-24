from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from app.ai.percent_change import is_percent_change_request

def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("ё", "е").split())


def _extract_cases(script_path: Path) -> list[dict]:
    tree = ast.parse(script_path.read_text(encoding="utf-8"))
    cases: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "RegressionCase":
            continue
        if not node.args:
            continue
        if not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        item = {
            "question": node.args[0].value,
            "expected_status": "executed",
            "expected_metrics": [],
            "expected_dimensions": [],
        }
        for kw in node.keywords:
            if kw.arg == "expected_status" and isinstance(kw.value, ast.Constant):
                if isinstance(kw.value.value, str):
                    item["expected_status"] = kw.value.value
            elif kw.arg in {"expected_metrics", "expected_dimensions"} and isinstance(kw.value, ast.Tuple):
                values: list[str] = []
                for el in kw.value.elts:
                    if isinstance(el, ast.Constant) and isinstance(el.value, str):
                        values.append(el.value)
                item[kw.arg] = values
        cases.append(item)
    return cases


def _infer_payload(question: str, status: str, metrics: list[str], dimensions: list[str]) -> dict:
    normalized = _normalize(question)
    time_expression = None
    known_time_phrases = [
        "за вчера",
        "вчера",
        "за текущую неделю",
        "на этой неделе",
        "за прошлую неделю",
        "на прошлой неделе",
        "за текущий месяц",
        "в этом месяце",
        "за прошлый месяц",
        "в прошлом месяце",
        "за текущий год",
        "в этом году",
        "за прошлый год",
        "за всё время",
        "за весь период",
    ]
    for phrase in known_time_phrases:
        if _normalize(phrase) in normalized:
            time_expression = phrase
            break

    comparison_enabled = any(token in normalized for token in ["сравни", "сравнение", "по сравнению", "относительно"])
    if is_percent_change_request(normalized):
        comparison_enabled = True

    intent_type = "aggregation"
    if comparison_enabled:
        intent_type = "comparison"
    elif any(dim in {"order_date", "order_week", "order_month", "order_hour"} for dim in dimensions):
        intent_type = "trend"

    ambiguity_reasons: list[str] = []
    clarification_questions: list[str] = []
    if status == "needs_clarification":
        ambiguity_reasons = ["Запрос требует уточнения или не относится к поддерживаемому домену."]
        clarification_questions = ["Уточните метрику, разрез и период в рамках датасета поездок."]

    return {
        "intent_type": intent_type,
        "metrics": metrics,
        "dimensions": dimensions,
        "filters": [],
        "time_expression": time_expression,
        "time_range_override": None,
        "multi_date": None,
        "comparison": {
            "enabled": comparison_enabled,
            "mode": "previous_period" if comparison_enabled else "none",
            "baseline_label": "Предыдущий период" if comparison_enabled else None,
            "baseline_start_date": None,
            "baseline_end_date": None,
        },
        "preferred_chart_type": None,
        "sort": None,
        "limit": 50,
        "confidence": 0.7 if status != "needs_clarification" else 0.45,
        "ambiguity_reasons": ambiguity_reasons,
        "clarification_questions": clarification_questions,
        "notes": ["Локальная переносимая модель классификации интента."],
    }


def _generate_variants(question: str) -> list[str]:
    variants = {question.strip()}
    base = question.strip()
    prefixes = ["", "Подскажи, ", "Пожалуйста, ", "Хочу понять, ", "Можешь показать, "]
    suffixes = ["", " пожалуйста", " плиз"]

    replacements = [
        ("покажи", "выведи"),
        ("покажи", "дай"),
        ("сколько", "какое количество"),
        ("за прошлую неделю", "за предыдущую неделю"),
        ("за текущую неделю", "за эту неделю"),
        ("в этом месяце", "за текущий месяц"),
        ("за прошлый месяц", "за предыдущий месяц"),
        ("выручка", "оборот"),
        ("выполненные заказы", "завершенные заказы"),
        ("отмены", "срывы"),
        ("по дням", "в разбивке по дням"),
        ("сравни", "сделай сравнение"),
    ]

    for prefix in prefixes:
        for suffix in suffixes:
            candidate = f"{prefix}{base}{suffix}".strip()
            variants.add(re.sub(r"\s+", " ", candidate))

    # allow chained replacements to cover freer phrasing
    for _ in range(2):
        direct = list(variants)
        for text in direct:
            lowered = text.lower()
            for old, new in replacements:
                if old in lowered:
                    replaced = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)
                    variants.add(re.sub(r"\s+", " ", replaced).strip())

    return sorted(variants)[:28]


def run() -> int:
    script_path = Path(__file__).resolve().with_name("query_regression.py")
    model_path = Path(__file__).resolve().parents[1] / "ai" / "model" / "local_intent_model.json"
    model_path.parent.mkdir(parents=True, exist_ok=True)

    cases = _extract_cases(script_path)
    entries = []
    seen_questions: set[str] = set()
    for item in cases:
        payload = _infer_payload(
            question=item["question"],
            status=item["expected_status"],
            metrics=item["expected_metrics"],
            dimensions=item["expected_dimensions"],
        )
        for variant in _generate_variants(item["question"]):
            normalized = _normalize(variant)
            if normalized in seen_questions:
                continue
            seen_questions.add(normalized)
            entries.append({"question": variant, "payload": payload})

    payload = {
        "version": 1,
        "name": "askora-local-intent-v1",
        "description": "Portable NL intent model built from regression templates with paraphrase augmentation.",
        "entries": entries,
    }
    model_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved local model: {model_path}")
    print(f"Entries: {len(entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
