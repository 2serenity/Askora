from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
import json
from time import perf_counter
from typing import Callable

from app.db.session import SessionLocal
from app.repositories.users import UserRepository
from app.schemas.query import QueryRequest
from app.semantic_layer.time_context import SemanticTimeContext
from app.services.query_service import QueryService


@dataclass(frozen=True)
class RegressionCase:
    question: str
    expected_status: str = "executed"
    expected_metrics: tuple[str, ...] = ()
    expected_dimensions: tuple[str, ...] = ()
    time_assertion: Callable[[date, date, SemanticTimeContext], bool] | None = None


def _is_month(month: int, year: int | None = None):
    def checker(start: date, end: date, time_context: SemanticTimeContext) -> bool:
        if start.month != month or end.month != month:
            return False
        if year is not None:
            return start.year == year and end.year == year
        return True

    return checker


def _range_equals(start_expected: date, end_expected: date):
    return lambda start, end, _ctx: start == start_expected and end == end_expected


def _current_week(start: date, end: date, time_context: SemanticTimeContext) -> bool:
    anchor = time_context.get_anchor_date()
    expected_start = anchor - timedelta(days=anchor.weekday())
    return start == expected_start and end == anchor


def _previous_week(start: date, end: date, time_context: SemanticTimeContext) -> bool:
    anchor = time_context.get_anchor_date()
    expected_end = anchor - timedelta(days=anchor.weekday() + 1)
    expected_start = expected_end - timedelta(days=6)
    return start == expected_start and end == expected_end


def _current_month(start: date, end: date, time_context: SemanticTimeContext) -> bool:
    anchor = time_context.get_anchor_date()
    return start == anchor.replace(day=1) and end == anchor


def _previous_month(start: date, end: date, time_context: SemanticTimeContext) -> bool:
    anchor = time_context.get_anchor_date().replace(day=1)
    expected_end = anchor - timedelta(days=1)
    expected_start = expected_end.replace(day=1)
    return start == expected_start and end == expected_end


def _current_year(start: date, end: date, time_context: SemanticTimeContext) -> bool:
    anchor = time_context.get_anchor_date()
    return start == date(anchor.year, 1, 1) and end == anchor


def _previous_year(start: date, end: date, time_context: SemanticTimeContext) -> bool:
    anchor = time_context.get_anchor_date()
    return start == date(anchor.year - 1, 1, 1) and end == date(anchor.year - 1, 12, 31)


def build_cases() -> list[RegressionCase]:
    return [
        RegressionCase("Покажи, пожалуйста, сколько у нас было заказов за вчера", expected_metrics=("total_orders",)),
        RegressionCase("Мне нужно понять, сколько выполненных заказов было за вчера", expected_metrics=("completed_orders",)),
        RegressionCase("Что у нас по деньгам за вчера", expected_metrics=("total_revenue",)),
        RegressionCase("Сколько отменилось за вчера", expected_metrics=("cancelled_orders",)),
        RegressionCase("Скажи средний чек за вчера", expected_metrics=("avg_order_price",)),
        RegressionCase("Сколько заказов на этой неделе", expected_metrics=("total_orders",), time_assertion=_current_week),
        RegressionCase("Покажи выполненные заказы по дням на этой неделе", expected_metrics=("completed_orders",), expected_dimensions=("order_date",), time_assertion=_current_week),
        RegressionCase("Выручку по дням за текущую неделю покажи", expected_metrics=("total_revenue",), expected_dimensions=("order_date",), time_assertion=_current_week),
        RegressionCase("Отмены по дням за текущую неделю", expected_metrics=("cancelled_orders",), expected_dimensions=("order_date",), time_assertion=_current_week),
        RegressionCase("Клиенты отменили по дням за текущую неделю", expected_metrics=("client_cancellations",), expected_dimensions=("order_date",), time_assertion=_current_week),
        RegressionCase("Водители отменили по дням за текущую неделю", expected_metrics=("driver_cancellations",), expected_dimensions=("order_date",), time_assertion=_current_week),
        RegressionCase("Доля успешных тендеров за текущую неделю", expected_metrics=("tender_acceptance_rate",), time_assertion=_current_week),
        RegressionCase("Сравни долю успешных тендеров за текущую неделю и прошлую", expected_status="executed", expected_metrics=("tender_acceptance_rate",), time_assertion=_current_week),
        RegressionCase("Сколько принятых тендеров было на прошлой неделе", expected_metrics=("successful_tenders",), time_assertion=_previous_week),
        RegressionCase("Сколько было отклоненных тендеров на прошлой неделе", expected_metrics=("declined_tenders",), time_assertion=_previous_week),
        RegressionCase("Как быстро берут тендер на этой неделе", expected_metrics=("avg_accept_time_min",), time_assertion=_current_week),
        RegressionCase("Сколько в среднем ехали в этом месяце", expected_metrics=("avg_duration_min",), time_assertion=_current_month),
        RegressionCase("Средняя дистанция в этом месяце", expected_metrics=("avg_distance_km",), time_assertion=_current_month),
        RegressionCase("Количество заказов с 19 февраля по 20 марта", expected_metrics=("total_orders",), time_assertion=_range_equals(date(2026, 2, 19), date(2026, 3, 20))),
        RegressionCase("Покажи по деньгам с 19.02 по 20.03 по дням", expected_metrics=("total_revenue",), expected_dimensions=("order_date",), time_assertion=_range_equals(date(2026, 2, 19), date(2026, 3, 20))),
        RegressionCase("Сколько выполнено за февраль", expected_metrics=("completed_orders",), time_assertion=_is_month(2, 2026)),
        RegressionCase("Выручка за март 2026", expected_metrics=("total_revenue",), time_assertion=_is_month(3, 2026)),
        RegressionCase("Выручка за 2026 год по месяцам", expected_metrics=("total_revenue",), expected_dimensions=("order_month",), time_assertion=_current_year),
        RegressionCase("Выручка за прошлый год по месяцам", expected_metrics=("total_revenue",), expected_dimensions=("order_month",), time_assertion=_previous_year),
        RegressionCase("Выручка с начала года по месяцам", expected_metrics=("total_revenue",), expected_dimensions=("order_month",), time_assertion=_current_year),
        RegressionCase("Покажи заказы за всё время по месяцам", expected_metrics=("total_orders",), expected_dimensions=("order_month",)),
        RegressionCase("Выполненные и отмены по дням за прошлую неделю", expected_metrics=("completed_orders", "cancelled_orders"), expected_dimensions=("order_date",), time_assertion=_previous_week),
        RegressionCase("Выручка и выполненные по дням за прошлую неделю", expected_metrics=("total_revenue", "completed_orders"), expected_dimensions=("order_date",), time_assertion=_previous_week),
        RegressionCase("Выполненные и отмененные по неделям за этот год", expected_metrics=("completed_orders", "cancelled_orders"), expected_dimensions=("order_week",), time_assertion=_current_year),
        RegressionCase("Заказы по городам за вчера", expected_metrics=("total_orders",), expected_dimensions=("city_id",)),
        RegressionCase("Выполненные заказы по статусам заказа за текущую неделю", expected_metrics=("completed_orders",), expected_dimensions=("order_status",), time_assertion=_current_week),
        RegressionCase("Тендеры по статусам тендера за вчера", expected_metrics=("total_tenders",), expected_dimensions=("tender_status",)),
        RegressionCase("Отмены клиентом и водителем по дням в этом месяце", expected_metrics=("client_cancellations", "driver_cancellations"), expected_dimensions=("order_date",), time_assertion=_current_month),
        RegressionCase("Средняя цена заказа по часам за вчера", expected_metrics=("avg_order_price",), expected_dimensions=("order_hour",)),
        RegressionCase("Средний чек по месяцам за этот год", expected_metrics=("avg_order_price",), expected_dimensions=("order_month",), time_assertion=_current_year),
        RegressionCase("Мне бы просто понять, сколько у нас заказов", expected_metrics=("total_orders",)),
        RegressionCase("Что по деньгам за прошлый месяц", expected_metrics=("total_revenue",), time_assertion=_previous_month),
        RegressionCase("Сколько у нас выполнено за прошлый месяц", expected_metrics=("completed_orders",), time_assertion=_previous_month),
        RegressionCase("Сколько отмен было в прошлом месяце", expected_metrics=("cancelled_orders",), time_assertion=_previous_month),
        RegressionCase("Средний ценник за прошлый месяц", expected_metrics=("avg_order_price",), time_assertion=_previous_month),
        RegressionCase("Сколько в среднем до принятия тендера в этом месяце", expected_metrics=("avg_accept_time_min",), time_assertion=_current_month),
        RegressionCase("Сколько было принятых тендеров в этом месяце", expected_metrics=("successful_tenders",), time_assertion=_current_month),
        RegressionCase("Какой процент выполненных заказов в этом месяце", expected_metrics=("order_completion_rate",), time_assertion=_current_month),
        RegressionCase("Сравни выполненные заказы за текущую неделю и прошлую", expected_metrics=("completed_orders",), time_assertion=_current_week),
        RegressionCase("Покажи, пожалуйста, деньги с 15 марта по 27 марта по дням", expected_metrics=("total_revenue",), expected_dimensions=("order_date",), time_assertion=_range_equals(date(2026, 3, 15), date(2026, 3, 27))),
        RegressionCase("Выручка за 16 марта и 19 марта по часам", expected_status="needs_clarification"),
        RegressionCase("Мне нужна прибыль за апрель", expected_status="needs_clarification"),
        RegressionCase("Сравни конверсию в заказ по каналам за текущую неделю и прошлую", expected_status="needs_clarification"),
        RegressionCase("Покажи продажи айфонов", expected_status="needs_clarification"),
        RegressionCase("Удали базу", expected_status="needs_clarification"),
        RegressionCase("Касса за прошлую неделю", expected_metrics=("total_revenue",), time_assertion=_previous_week),
        RegressionCase("Сколько у нас сорвалось по дням за прошлую неделю", expected_metrics=("cancelled_orders",), expected_dimensions=("order_date",), time_assertion=_previous_week),
        RegressionCase("Сколько довезли по дням за прошлую неделю", expected_metrics=("completed_orders",), expected_dimensions=("order_date",), time_assertion=_previous_week),
        RegressionCase("Покажи заявки по дням с начала месяца", expected_metrics=("total_orders",), expected_dimensions=("order_date",), time_assertion=_current_month),
        RegressionCase("Выручка по месяцам за прошлый год", expected_metrics=("total_revenue",), expected_dimensions=("order_month",), time_assertion=_previous_year),
        RegressionCase("Покажи выручку по городам за прошлую неделю", expected_metrics=("total_revenue",), expected_dimensions=("city_id",), time_assertion=_previous_week),
        RegressionCase("Покажи заказы по пользователям за вчера", expected_metrics=("total_orders",), expected_dimensions=("user_id",)),
        RegressionCase("Покажи среднюю скорость по дням за прошлую неделю", expected_metrics=("avg_speed_mps",), expected_dimensions=("order_date",), time_assertion=_previous_week),
        RegressionCase("Покажи среднюю длительность больше 10 минут за прошлую неделю", expected_metrics=("avg_duration_min",), time_assertion=_previous_week),
        RegressionCase("Покажи заказы по каналам за прошлую неделю", expected_status="needs_clarification"),
        RegressionCase("Обнови статусы заказов за вчера", expected_status="needs_clarification"),
        RegressionCase("Сравни выручку за 16 апреля и 19 апреля", expected_status="executed", expected_metrics=("total_revenue",)),
        RegressionCase("Покажи количество заказов за текущую неделю и прошлую", expected_status="executed", expected_metrics=("total_orders",), time_assertion=_current_week),
    ]


def run(
    *,
    json_out: str | None = None,
    min_pass_rate: float | None = None,
    max_false_block_rate: float | None = None,
    max_avg_latency_ms: float | None = None,
    strict_cases: bool = False,
) -> int:
    db = SessionLocal()
    try:
        user = UserRepository(db).get_by_email("business@demo.local")
        if not user:
            raise RuntimeError("Не найден demo-пользователь business@demo.local")

        service = QueryService(db)
        time_context = SemanticTimeContext(db)
        failures: list[str] = []
        durations_ms: list[float] = []
        cases = build_cases()
        expected_by_status: dict[str, int] = {}
        actual_by_status: dict[str, int] = {}
        false_blocks = 0

        for index, case in enumerate(cases, start=1):
            expected_by_status[case.expected_status] = expected_by_status.get(case.expected_status, 0) + 1
            started = perf_counter()
            result = service.run(QueryRequest(question=case.question), user)
            durations_ms.append(round((perf_counter() - started) * 1000, 2))
            actual_metrics = tuple(item.key for item in result.query_plan.metrics)
            actual_dimensions = tuple(item.key for item in result.query_plan.dimensions)
            time_range = result.query_plan.time_range
            actual_by_status[result.status] = actual_by_status.get(result.status, 0) + 1

            if result.status != case.expected_status:
                if case.expected_status == "executed" and result.status in {"blocked", "needs_clarification"}:
                    false_blocks += 1
                failures.append(
                    f"[{index}] Статус: ожидался {case.expected_status}, получен {result.status} — {case.question}"
                )
                continue

            if case.expected_metrics and not all(metric in actual_metrics for metric in case.expected_metrics):
                failures.append(
                    f"[{index}] Метрики: ожидались {case.expected_metrics}, получены {actual_metrics} — {case.question}"
                )

            if case.expected_dimensions and not all(dimension in actual_dimensions for dimension in case.expected_dimensions):
                failures.append(
                    f"[{index}] Измерения: ожидались {case.expected_dimensions}, получены {actual_dimensions} — {case.question}"
                )

            if case.time_assertion and not case.time_assertion(time_range.start_date, time_range.end_date, time_context):
                failures.append(
                    f"[{index}] Период: получен {time_range.start_date}..{time_range.end_date} — {case.question}"
                )

        total = len(cases)
        failed = len(failures)
        passed = total - failed
        pass_rate = round((passed / total) * 100, 2) if total else 0.0
        executed_expected = expected_by_status.get("executed", 0)
        false_block_rate = round((false_blocks / executed_expected) * 100, 2) if executed_expected else 0.0
        avg_latency_ms = round(sum(durations_ms) / len(durations_ms), 2) if durations_ms else 0.0

        print(f"Проверено запросов: {total}")
        print(f"Успешно: {passed}")
        print(f"Ошибок: {failed}")
        print(f"Pass rate: {pass_rate}%")
        print(f"Средняя latency: {avg_latency_ms} ms")
        print(f"False block rate: {false_block_rate}%")

        report = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate,
            "avg_latency_ms": avg_latency_ms,
            "false_block_rate": false_block_rate,
            "expected_status_distribution": expected_by_status,
            "actual_status_distribution": actual_by_status,
            "failures": failures,
        }
        if json_out:
            with open(json_out, "w", encoding="utf-8") as fh:
                json.dump(report, fh, ensure_ascii=False, indent=2)
            print(f"JSON-отчёт сохранён: {json_out}")

        if min_pass_rate is not None and pass_rate < min_pass_rate:
            print(
                f"Pass rate ниже порога ({pass_rate}% < {min_pass_rate}%)."
            )
            return 1
        if max_false_block_rate is not None and false_block_rate > max_false_block_rate:
            print(
                f"False block rate выше порога ({false_block_rate}% > {max_false_block_rate}%)."
            )
            return 1
        if max_avg_latency_ms is not None and avg_latency_ms > max_avg_latency_ms:
            print(
                f"Средняя latency выше порога ({avg_latency_ms} ms > {max_avg_latency_ms} ms)."
            )
            return 1

        if failures:
            print("")
            print("Проблемные кейсы:")
            for item in failures:
                print(f"- {item}")
            if strict_cases:
                return 1

        if failures:
            print("Пороги качества выполнены, но есть кейсы для точечной донастройки.")
        else:
            print("Все кейсы прошли успешно.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regression smoke for NL -> SQL quality.")
    parser.add_argument("--json-out", dest="json_out", help="Путь до JSON-отчёта по прогону.")
    parser.add_argument(
        "--min-pass-rate",
        dest="min_pass_rate",
        type=float,
        default=None,
        help="Минимальный порог успешности в процентах. Ниже порога — exit code 1.",
    )
    parser.add_argument(
        "--max-false-block-rate",
        dest="max_false_block_rate",
        type=float,
        default=None,
        help="Максимально допустимая доля false blocks среди кейсов с ожидаемым executed, в процентах.",
    )
    parser.add_argument(
        "--max-avg-latency-ms",
        dest="max_avg_latency_ms",
        type=float,
        default=None,
        help="Максимально допустимая средняя latency на кейс в миллисекундах.",
    )
    parser.add_argument(
        "--strict-cases",
        action="store_true",
        help="Падать, если есть хотя бы один проблемный кейс, даже при выполнении порогов.",
    )
    args = parser.parse_args()
    raise SystemExit(
        run(
            json_out=args.json_out,
            min_pass_rate=args.min_pass_rate,
            max_false_block_rate=args.max_false_block_rate,
            max_avg_latency_ms=args.max_avg_latency_ms,
            strict_cases=args.strict_cases,
        )
    )
