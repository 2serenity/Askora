# Analytics Workspace

Production-style MVP+/hackathon-ready платформа self-service аналитики для non-tech пользователей. Продукт принимает вопрос на русском языке, интерпретирует его через semantic layer, строит безопасный SQL, показывает explainability, визуализирует результат, сохраняет отчёты и поддерживает расписания.

## Что внутри
- `Next.js 14 + TypeScript + Tailwind + shadcn-style UI + React Query + Recharts`
- `FastAPI + SQLAlchemy + Alembic + PostgreSQL + Redis`
- `Portable local intent model + semantic layer + approved templates + ambiguity handling`
- `sqlglot guardrails + whitelist + audit trail + RBAC`
- `APScheduler + schedules + stub email delivery`

## Запуск одним файлом
Главный launcher находится в корне репозитория: [`start.py`](start.py)

Что нужно для первого запуска:
- установленный Docker Desktop с доступной командой `docker compose`
- Python 3.11+ для запуска `start.py`
- никаких дополнительных файлов скачивать не нужно: полный demo-датасет уже лежит в `data/train.csv`

Базовый запуск:

```bash
python start.py
```

Что делает `start.py`:
- сам создаёт `.env` из `.env.example`, если файла ещё нет
- подставляет настройки из переменных окружения (если они уже заданы)
- использует встроенный `data/train.csv` и при необходимости копирует его в рабочую папку
- проверяет `docker compose`
- поднимает `web + api + postgres + redis`

Полезные режимы:
- `python start.py` — поднять всё в фоне
- `python start.py dev` — поднять всё в foreground
- `python start.py down` — остановить стек
- `python start.py logs` — смотреть логи
- `python start.py seed` — повторно досидить demo-данные

После запуска:
- Web: [http://localhost:3000](http://localhost:3000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Демо-пользователи
- `admin@demo.local` / `DemoAdmin123`
- `analyst@demo.local` / `DemoAnalyst123`
- `business@demo.local` / `DemoBusiness123`

## Основные сценарии
- `Покажи выполненные заказы и отмены по дням за прошлую неделю`
- `Сравни долю успешных тендеров за текущую неделю и прошлую`
- `Покажи выручку по дням за текущую неделю`
- `Покажи среднюю цену заказа по часам за вчера`
- `Количество заказов с 19 февраля по 20 марта`
- `Сравни выручку за 16 апреля и 19 апреля`
- `Покажи продажи айфонов` → сработает ambiguity handling и запрос не будет исполняться вслепую

## Структура репозитория
```text
.
├── apps
│   ├── api
│   │   ├── alembic
│   │   ├── app
│   │   │   ├── ai
│   │   │   ├── api
│   │   │   ├── core
│   │   │   ├── db
│   │   │   ├── models
│   │   │   ├── query_engine
│   │   │   ├── repositories
│   │   │   ├── scheduler
│   │   │   ├── schemas
│   │   │   ├── seed
│   │   │   ├── semantic_layer
│   │   │   ├── services
│   │   │   └── sql_guardrails
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── web
│       ├── app
│       ├── components
│       ├── hooks
│       ├── lib
│       └── types
├── docs
├── docker-compose.yml
├── Makefile
└── README.md
```

## Make targets
`Makefile` оставлен как дополнительный DX-инструмент для разработчиков, но для обычного локального старта он больше не нужен.

- `make up` — поднять весь стек в фоне
- `make dev` — поднять стек в foreground
- `make down` — остановить контейнеры
- `make logs` — смотреть логи
- `make migrate` — прогнать миграции
- `make seed` — досидить demo-данные
- `make test` — прогнать backend unit-тесты
- `make regression` — прогнать регрессионный набор NL→SQL кейсов
- `make web-lint` — проверить фронтенд линтером
- `make web-typecheck` — проверить TypeScript без сборки
- `make web-build` — выполнить production-сборку web
- `make verify` — единый quality gate (backend tests + web lint/typecheck + regression с порогами)

## Semantic layer и реальная БД
Сейчас проект работает на demo schema `analytics.*` и seed-данных под домен такси/поездок/заказов/отмен. Для переключения на реальную БД не нужно переписывать продукт:

1. Меняется `DATABASE_URL`
2. Обновляется `apps/api/app/semantic_layer/config/catalog.yaml`
3. При необходимости пополняются `semantic_dictionary_entries` и `approved_query_templates`
4. Актуализируется whitelist в `app/sql_guardrails/validator.py`

UI, orchestration, auth, audit, reports и schedules при этом остаются без изменений.

## Guardrails
- только `SELECT`
- whitelist таблиц/alias
- запрет DDL/DML и системных таблиц
- complexity score
- rate limit на интерактивные NL-запросы
- pre-execution `EXPLAIN (FORMAT JSON)` для оценки стоимости
- блокировка по порогу прогнозной стоимости (`MAX_QUERY_COST`)
- row limit
- `statement_timeout`
- audit log для blocked/failed/executed запросов

## Explainability
После каждого запроса пользователь видит:
- исходный вопрос
- распознанные метрики, измерения, фильтры и период
- confidence
- SQL
- оценку сложности и прогноз по `EXPLAIN` (cost/rows) до выполнения
- предупреждения guardrails
- результат в таблице и графике
- причины блокировки, если исполнение запрещено

## Observability
- `GET /api/v1/health/live` — liveness API-процесса
- `GET /api/v1/health/ready` — готовность зависимостей (PostgreSQL + Redis)
- `GET /api/v1/metrics` — технические и продуктовые метрики рантайма (HTTP, query outcomes, rate-limit blocks)
- Все HTTP-ответы содержат `X-Request-ID`, что упрощает корреляцию логов и разбор инцидентов.

## Security hardening
- Rate limiting реализован через Redis-backed sliding window (корректно работает при масштабировании API).
- Аудит/превью результатов проходит через санитизацию чувствительных полей и ограничение объёма текстовых payload.
- Cookie-сессии используют `secure` режим на production автоматически (или через `AUTH_COOKIE_SECURE`).

## Полезные документы
- [Архитектура](docs/architecture.md)

## Переносимая локальная модель
Проект запускается в режиме `LLM_PROVIDER=local` и не требует внешних API-ключей.

Артефакт модели хранится в репозитории: `apps/api/app/ai/model/local_intent_model.json`.

Пересобрать локальную модель внутри docker-окружения:

```bash
docker compose exec -T api python -m app.scripts.build_local_intent_model
```

## Переключение LLM
Текущая продуктовая конфигурация использует только локальный режим:
- `LLM_PROVIDER=local` — переносимая модель из файла `apps/api/app/ai/model/local_intent_model.json`

Дополнительные настройки локальной модели:
- `LOCAL_INTENT_MIN_SIMILARITY` — минимальный порог похожести
- `LOCAL_INTENT_MIN_MARGIN` — минимальный отрыв лучшего совпадения от второго

Опционально (вне основного demo/jury-флоу) в кодовой базе сохранены legacy-интеграции внешних провайдеров для исследовательских экспериментов. Для защиты и проверки жюри они не требуются.

## Jury Quick Start
Ниже шаги, которые жюри может выполнить на чистой машине без дополнительных файлов: полный demo-датасет уже включён в репозиторий (`data/train.csv`).

### 1) Запуск проекта
```bash
python start.py
```

Альтернатива:
```bash
docker compose up -d --build
```

После запуска:
- Web: [http://localhost:3000](http://localhost:3000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2) Проверка, что используется именно локальная модель
1. Войти в систему под `admin@demo.local / DemoAdmin123`.
2. Открыть админку и раздел AI trace.
3. Выполнить несколько запросов из workspace.
4. Убедиться, что в trace указан локальный режим (`local_only_mode`) без внешних провайдеров.

### 3) Проверка переносимости модели
Артефакт хранится в репозитории:
- `apps/api/app/ai/model/local_intent_model.json`

Пересборка модели внутри docker-контейнера:
```bash
docker compose exec -T api python -m app.scripts.build_local_intent_model
docker compose restart api
```

### 4) Что с `train.csv`
В репозитории уже лежит полный demo-датасет:
- `data/train.csv`

Поэтому типовой сценарий для жюри и локального запуска не требует ручного подкладывания CSV. Если файл убрать, проект всё равно стартует: сидер автоматически подгрузит встроенный fallback-датасет, чтобы можно было войти и протестировать NL→SQL и локальную модель, но для полного демо рекомендуется использовать именно `data/train.csv`.
