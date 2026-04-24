from __future__ import annotations

from pathlib import Path

import psycopg
from sqlalchemy import text
from sqlalchemy import func, select

import app.models  # noqa: F401
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.data_source import DataSource
from app.models.order_tender import OrderTenderFact
from app.models.semantic import ApprovedQueryTemplate, SemanticDictionaryEntry
from app.models.user import User, UserRole

CSV_COLUMNS = [
    "city_id",
    "order_id",
    "tender_id",
    "user_id",
    "driver_id",
    "offset_hours",
    "status_order",
    "status_tender",
    "order_timestamp",
    "tender_timestamp",
    "driveraccept_timestamp",
    "driverarrived_timestamp",
    "driverstarttheride_timestamp",
    "driverdone_timestamp",
    "clientcancel_timestamp",
    "drivercancel_timestamp",
    "order_modified_local",
    "cancel_before_accept_local",
    "distance_in_meters",
    "duration_in_seconds",
    "price_order_local",
    "price_tender_local",
    "price_start_local",
]

FALLBACK_DEMO_ROWS = [
    (
        67,
        "43ec5acf92391314",
        "ec68754185bac5ba",
        "278ff124e76aef84",
        "e1747bf59e03eec5",
        9,
        "done",
        "decline",
        "2026-01-05 19:17:35",
        "2026-01-05 19:17:38",
        None,
        None,
        None,
        None,
        None,
        None,
        "2026-01-05 19:24:02",
        None,
        1021,
        151,
        150.98,
        151.13,
        143.14,
    ),
    (
        67,
        "43ec5acf92391314",
        "81b9e10993311776",
        "278ff124e76aef84",
        "f266ab6d54ead9c8",
        9,
        "done",
        "done",
        "2026-01-05 19:10:35",
        "2026-01-05 19:10:42",
        "2026-01-05 19:10:46",
        "2026-01-05 19:13:47",
        "2026-01-05 19:15:06",
        "2026-01-05 19:17:02",
        None,
        None,
        "2026-01-05 19:17:02",
        None,
        1053,
        155,
        136.53,
        164.78,
        153.18,
    ),
    (
        67,
        "5bac6c399e48fc93",
        "5deee9c4af45c9b8",
        "2d2309439f5f4251",
        "856ff8479f007be3",
        9,
        "done",
        "done",
        "2026-01-05 19:12:18",
        "2026-01-05 19:12:36",
        "2026-01-05 19:12:46",
        "2026-01-05 19:13:40",
        "2026-01-05 19:15:35",
        "2026-01-05 19:16:30",
        None,
        None,
        "2026-01-05 19:16:30",
        None,
        255,
        38,
        99.51,
        96.6,
        95.57,
    ),
    (
        67,
        "fallback-cancelled-order-01",
        "fallback-cancelled-tender-01",
        "fallback-user-01",
        "fallback-driver-01",
        9,
        "cancelled",
        "decline",
        "2026-01-06 10:05:00",
        "2026-01-06 10:05:06",
        None,
        None,
        None,
        None,
        "2026-01-06 10:06:50",
        None,
        "2026-01-06 10:06:50",
        "2026-01-06 10:05:20",
        750,
        90,
        110.0,
        113.0,
        109.0,
    ),
    (
        68,
        "fallback-order-city68-01",
        "fallback-tender-city68-01",
        "fallback-user-02",
        "fallback-driver-02",
        9,
        "done",
        "done",
        "2026-01-07 15:10:00",
        "2026-01-07 15:10:08",
        "2026-01-07 15:10:20",
        "2026-01-07 15:12:00",
        "2026-01-07 15:13:30",
        "2026-01-07 15:22:00",
        None,
        None,
        "2026-01-07 15:22:00",
        None,
        3200,
        720,
        280.5,
        282.0,
        270.0,
    ),
]

SEEDED_SEMANTIC_ENTRIES = [
    {
        "term": "успешные тендеры",
        "entity_type": "metric",
        "target_key": "successful_tenders",
        "synonyms_json": ["принятые тендеры", "тендеры со статусом done"],
        "description": "Метрика по тендерам, успешно принятым водителем.",
    },
    {
        "term": "доля успешных тендеров",
        "entity_type": "metric",
        "target_key": "tender_acceptance_rate",
        "synonyms_json": ["конверсия тендера", "доля принятых тендеров", "долю успешных тендеров", "долю принятых тендеров"],
        "description": "Процент тендеров со статусом done от общего числа тендеров.",
    },
    {
        "term": "источник отмены",
        "entity_type": "dimension",
        "target_key": "cancel_source",
        "synonyms_json": ["кто отменил", "отмена клиентом или водителем"],
        "description": "Показывает, кто инициировал отмену: клиент, водитель или не указано.",
    },
]

SEEDED_TEMPLATES = [
    {
        "name": "Выполненные заказы и отмены по дням",
        "description": "Ежедневная сводка по успешным заказам и отменам.",
        "pattern": "<метрики> по дням за <период>",
        "guidance": "Используй метрики completed_orders и cancelled_orders с измерением order_date.",
        "example_question": "Покажи выполненные заказы и отмены по дням за прошлую неделю",
        "output_shape_json": {"chart": "line", "granularity": "day"},
        "owner_role": UserRole.analyst,
    },
    {
        "name": "Сравнение доли успешных тендеров",
        "description": "Сравнение успешности тендеров между периодами без лишней детализации.",
        "pattern": "Сравни <метрику> за <период> и прошлый период",
        "guidance": "Используй metric=tender_acceptance_rate и comparison.previous_period без дополнительного измерения, если его не просили.",
        "example_question": "Сравни долю успешных тендеров за текущую неделю и прошлую",
        "output_shape_json": {"chart": "bar", "comparison": True},
        "owner_role": UserRole.analyst,
    },
    {
        "name": "Средняя стоимость заказа по часам",
        "description": "Показывает, как меняется средняя стоимость заказа в течение дня.",
        "pattern": "<метрика> по часам за <период>",
        "guidance": "Используй metric=avg_order_price и dimension=order_hour.",
        "example_question": "Покажи среднюю цену заказа по часам за вчера",
        "output_shape_json": {"chart": "bar", "granularity": "hour"},
        "owner_role": UserRole.analyst,
    },
    {
        "name": "Выручка по дням",
        "description": "Динамика суммы выполненных заказов по дням.",
        "pattern": "<метрика> по дням за <период>",
        "guidance": "Используй metric=total_revenue и dimension=order_date.",
        "example_question": "Покажи выручку по дням за текущую неделю",
        "output_shape_json": {"chart": "line", "granularity": "day"},
        "owner_role": UserRole.analyst,
    },
    {
        "name": "Отмены клиентом и водителем",
        "description": "Сравнение клиентских и водительских отмен по дням.",
        "pattern": "<метрики отмен> по дням за <период>",
        "guidance": "Используй metrics=client_cancellations,driver_cancellations и dimension=order_date.",
        "example_question": "Покажи отмены клиентом и водителем по дням за текущий месяц",
        "output_shape_json": {"chart": "line", "granularity": "day"},
        "owner_role": UserRole.analyst,
    },
    {
        "name": "Количество заказов за выбранный период",
        "description": "Сводка без группировки для ответа одним числом.",
        "pattern": "<метрика> за <период>",
        "guidance": "Если пользователь не просит разрез, не добавляй измерение по дням автоматически.",
        "example_question": "Количество заказов с 19 февраля по 20 марта",
        "output_shape_json": {"chart": "kpi"},
        "owner_role": UserRole.analyst,
    },
]

LEGACY_TEMPLATE_NAMES = {
    "Заказы и отмены по дням",
    "Сравнение acceptance rate тендеров",
}

LEGACY_TEMPLATE_MARKERS = (
    "acceptance rate",
    "order-level",
    "csv-датасете",
)


def _psycopg_conn_string() -> str:
    return settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def ensure_demo_users(db) -> None:
    if db.scalar(select(func.count(User.id))) not in (None, 0):
        return

    users = [
        User(
            email="admin@demo.local",
            full_name="Анна Администратор",
            password_hash=hash_password("DemoAdmin123"),
            role=UserRole.admin,
        ),
        User(
            email="analyst@demo.local",
            full_name="Илья Аналитик",
            password_hash=hash_password("DemoAnalyst123"),
            role=UserRole.analyst,
        ),
        User(
            email="business@demo.local",
            full_name="Мария Бизнес",
            password_hash=hash_password("DemoBusiness123"),
            role=UserRole.business_user,
        ),
    ]
    db.add_all(users)
    db.commit()


def ensure_semantic_metadata(db) -> None:
    _sync_semantic_entries(db)
    _sync_templates(db)
    _sync_data_sources(db)
    db.commit()


def _sync_semantic_entries(db) -> None:
    target_keys = [item["target_key"] for item in SEEDED_SEMANTIC_ENTRIES]
    existing_entries = {
        entry.target_key: entry
        for entry in db.query(SemanticDictionaryEntry)
        .filter(SemanticDictionaryEntry.target_key.in_(target_keys))
        .all()
    }

    for payload in SEEDED_SEMANTIC_ENTRIES:
        existing = existing_entries.get(payload["target_key"])
        if existing:
            existing.term = payload["term"]
            existing.entity_type = payload["entity_type"]
            existing.synonyms_json = payload["synonyms_json"]
            existing.description = payload["description"]
            existing.is_active = True
            db.add(existing)
            continue
        db.add(SemanticDictionaryEntry(**payload))


def _sync_templates(db) -> None:
    existing_templates = db.query(ApprovedQueryTemplate).all()
    existing_by_name = {item.name: item for item in existing_templates}

    for template in existing_templates:
        searchable_text = " ".join(
            [
                template.name or "",
                template.description or "",
                template.pattern or "",
                template.guidance or "",
                template.example_question or "",
            ]
        ).lower()
        if template.name in LEGACY_TEMPLATE_NAMES or any(marker in searchable_text for marker in LEGACY_TEMPLATE_MARKERS):
            db.delete(template)

    for payload in SEEDED_TEMPLATES:
        existing = existing_by_name.get(payload["name"])
        if existing:
            existing.description = payload["description"]
            existing.pattern = payload["pattern"]
            existing.guidance = payload["guidance"]
            existing.example_question = payload["example_question"]
            existing.output_shape_json = payload["output_shape_json"]
            existing.owner_role = payload["owner_role"]
            existing.is_active = True
            db.add(existing)
            continue
        db.add(ApprovedQueryTemplate(**payload))


def _sync_data_sources(db) -> None:
    existing = db.query(DataSource).filter(DataSource.key == settings.default_data_source_key).one_or_none()
    if existing:
        existing.name = "Основной PostgreSQL"
        existing.description = "Локальный основной источник для demo и подключения реальной витрины."
        existing.dialect = "postgres"
        existing.connection_url = settings.database_url
        existing.schema_name = "analytics"
        existing.is_active = True
        existing.is_default = True
        existing.allowed_roles_json = ["admin", "analyst", "business_user"]
        existing.capabilities_json = {"scheduler": True, "guardrails": True}
        db.add(existing)
        return

    db.add(
        DataSource(
            key=settings.default_data_source_key,
            name="Основной PostgreSQL",
            description="Локальный основной источник для demo и подключения реальной витрины.",
            dialect="postgres",
            connection_url=settings.database_url,
            schema_name="analytics",
            is_active=True,
            is_default=True,
            allowed_roles_json=["admin", "analyst", "business_user"],
            capabilities_json={"scheduler": True, "guardrails": True},
        )
    )


def import_csv_dataset_if_needed(db) -> None:
    current_rows = db.scalar(select(func.count(OrderTenderFact.row_id))) or 0
    if current_rows > 0:
        return

    dataset_path = Path(settings.dataset_csv_path)
    if not dataset_path.exists():
        _import_embedded_dataset(db)
        return

    copy_sql = f"""
        COPY analytics.order_tender_facts ({", ".join(CSV_COLUMNS)})
        FROM STDIN WITH (FORMAT CSV, HEADER TRUE)
    """
    with psycopg.connect(_psycopg_conn_string()) as connection:
        with connection.cursor() as cursor:
            with dataset_path.open("r", encoding="utf-8", newline="") as file_obj:
                with cursor.copy(copy_sql) as copy:
                    while chunk := file_obj.read(1024 * 1024):
                        copy.write(chunk)
        connection.commit()


def _import_embedded_dataset(db) -> None:
    insert_sql = text(
        """
        INSERT INTO analytics.order_tender_facts (
            city_id,
            order_id,
            tender_id,
            user_id,
            driver_id,
            offset_hours,
            status_order,
            status_tender,
            order_timestamp,
            tender_timestamp,
            driveraccept_timestamp,
            driverarrived_timestamp,
            driverstarttheride_timestamp,
            driverdone_timestamp,
            clientcancel_timestamp,
            drivercancel_timestamp,
            order_modified_local,
            cancel_before_accept_local,
            distance_in_meters,
            duration_in_seconds,
            price_order_local,
            price_tender_local,
            price_start_local
        ) VALUES (
            :city_id,
            :order_id,
            :tender_id,
            :user_id,
            :driver_id,
            :offset_hours,
            :status_order,
            :status_tender,
            :order_timestamp,
            :tender_timestamp,
            :driveraccept_timestamp,
            :driverarrived_timestamp,
            :driverstarttheride_timestamp,
            :driverdone_timestamp,
            :clientcancel_timestamp,
            :drivercancel_timestamp,
            :order_modified_local,
            :cancel_before_accept_local,
            :distance_in_meters,
            :duration_in_seconds,
            :price_order_local,
            :price_tender_local,
            :price_start_local
        )
        """
    )
    payloads = [
        {
            "city_id": row[0],
            "order_id": row[1],
            "tender_id": row[2],
            "user_id": row[3],
            "driver_id": row[4],
            "offset_hours": row[5],
            "status_order": row[6],
            "status_tender": row[7],
            "order_timestamp": row[8],
            "tender_timestamp": row[9],
            "driveraccept_timestamp": row[10],
            "driverarrived_timestamp": row[11],
            "driverstarttheride_timestamp": row[12],
            "driverdone_timestamp": row[13],
            "clientcancel_timestamp": row[14],
            "drivercancel_timestamp": row[15],
            "order_modified_local": row[16],
            "cancel_before_accept_local": row[17],
            "distance_in_meters": row[18],
            "duration_in_seconds": row[19],
            "price_order_local": row[20],
            "price_tender_local": row[21],
            "price_start_local": row[22],
        }
        for row in FALLBACK_DEMO_ROWS
    ]
    for payload in payloads:
        db.execute(insert_sql, payload)
    db.commit()


def normalize_demo_statuses(db) -> int:
    """Normalize raw dataset status values to platform conventions."""
    result = db.execute(
        text(
            """
            UPDATE analytics.order_tender_facts
            SET status_order = 'cancelled'
            WHERE status_order = 'cancel'
            """
        )
    )
    db.commit()
    return int(getattr(result, "rowcount", 0) or 0)


def seed() -> None:
    if not settings.seed_demo_data:
        return

    db = SessionLocal()
    try:
        ensure_demo_users(db)
        ensure_semantic_metadata(db)
        import_csv_dataset_if_needed(db)
        normalize_demo_statuses(db)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
