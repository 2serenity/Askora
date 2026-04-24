from __future__ import annotations

import random

from app.db.session import SessionLocal
from app.repositories.users import UserRepository
from app.schemas.query import QueryRequest
from app.services.query_service import QueryService


BASE_QUESTIONS = [
    "Покажи выполненные заказы по дням за прошлую неделю",
    "Какой процент выполненных заказов в этом месяце",
    "Выручка и выполненные по дням за прошлую неделю",
    "Сравни долю успешных тендеров за текущую неделю и прошлую",
    "Средняя цена заказа по часам за вчера",
    "Сколько отмен было в прошлом месяце",
    "Ну чё у нас по деньгам за вчера?",
    "Сколько у нас сорвалось по дням на прошлой неделе?",
    "Довезли сколько по дням за эту неделю?",
    "На сколько процентов просела выручка в марте к февралю?",
    "Покажи среднюю скорость по дням за прошлую неделю",
    "Покажи выручку в выходные за прошлую неделю",
    "Покажи выручку в будни за прошлую неделю",
    "Покажи выручку по городам за прошлую неделю",
    "Покажи конверсию в выполненный заказ по дням за текущую неделю",
    "Покажи среднее время до принятия тендера по дням за прошлую неделю",
    "Покажи отмены по источникам за текущий месяц",
    "Сравни выручку за 16 апреля и 19 апреля",
    "Выручка за 16 марта и 19 марта по часам",
    "Подскажи обоот за 16 марта и 19 марта по часам",
    "Почему продажи упали в выходные? Покажи график",
    "Падение",
    "Обнови статусы заказов за вчера",
]

PREFIXES = ["", "пожалуйста ", "можешь ", "хочу понять ", "подскажи "]
SUFFIXES = ["", " пожалуйста", " плиз", ", если можно"]
REPLACEMENTS = [
    ("покажи", "выведи"),
    ("сравни", "сделай сравнение"),
    ("выручка", "оборот"),
    ("выполненные", "завершенные"),
    ("прошлую неделю", "предыдущую неделю"),
    ("в этом месяце", "за текущий месяц"),
]


def mutate(question: str) -> str:
    text = question.lower()
    for old, new in REPLACEMENTS:
        if old in text and random.random() < 0.5:
            text = text.replace(old, new, 1)
    if random.random() < 0.3 and len(text) > 8:
        index = random.randint(2, len(text) - 3)
        text = text[:index] + text[index + 1 :]
    return f"{random.choice(PREFIXES)}{text}{random.choice(SUFFIXES)}".strip()


def run() -> int:
    random.seed(42)
    db = SessionLocal()
    try:
        user = UserRepository(db).get_by_email("business@demo.local")
        if not user:
            raise RuntimeError("Не найден demo-пользователь business@demo.local")

        service = QueryService(db)
        total = 0
        failures: list[str] = []
        source_failures = 0

        for base in BASE_QUESTIONS:
            for _ in range(10):
                question = mutate(base)
                total += 1
                result = service.run(QueryRequest(question=question), user)
                extraction = (result.processing_trace or {}).get("extraction", {})
                source = extraction.get("effective_source")
                if source == "rules_only":
                    source_failures += 1
                if result.status not in {"executed", "needs_clarification"}:
                    failures.append(f"{question} -> {result.status}")

        print(f"Проверено стресс-кейсов: {total}")
        print(f"rules_only срабатываний: {source_failures}")
        print(f"Недопустимых статусов: {len(failures)}")
        if failures:
            for item in failures[:10]:
                print(f"- {item}")
            return 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(run())
