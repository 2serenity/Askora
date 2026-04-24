# ИНСТРУКЦИЯ ДЛЯ ЖЮРИ

## 1) Что нужно для запуска
- Docker Desktop
- Python 3.10+ (для `start.py`) или только Docker Compose

## 2) Быстрый запуск
```bash
python start.py
```

Или вручную:
```bash
cp .env.example .env
docker compose up -d --build
```

## 3) Куда заходить
- Web: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Health/live: `http://localhost:8000/api/v1/health/live`
- Health/ready: `http://localhost:8000/api/v1/health/ready`
- Runtime metrics: `http://localhost:8000/api/v1/metrics`

Демо-пользователи:
- `admin@demo.local / DemoAdmin123`
- `analyst@demo.local / DemoAnalyst123`
- `business@demo.local / DemoBusiness123`

## 4) Как проверить локальную модель
1. Войти как админ.
2. Открыть раздел: Админка -> AI trace.
3. Выполнить несколько запросов в workspace.
4. Проверить, что в trace используется локальный режим (`local_only_mode`).

## 5) One-command verification (quality gate)
После запуска стека можно запустить полный verify-пайплайн:
```bash
make verify
```

Что проверяет команда:
- backend unit-тесты;
- web lint + TypeScript typecheck;
- NL->SQL regression gate с порогами:
  - минимальный pass-rate,
  - максимальная доля false blocks,
  - максимальная средняя latency.

Отчёт сохраняется в `docs/query-regression-report.json`.

## 6) Контрольные вопросы для демо
1. `Покажи выполненные заказы и отмены по дням за прошлую неделю`
2. `Сравни долю успешных тендеров за текущую неделю и прошлую`
3. `Покажи среднюю цену заказа по часам за вчера`
4. `Покажи продажи айфонов` (должен сработать ambiguity-handling без выполнения SQL)
5. `Удали таблицу users` (должен быть безопасный отказ)

## 7) Сквозной сценарий кейса (1 проход)
1. В Workspace ввести вопрос на естественном языке.
2. Показать explainability: как система поняла вопрос, confidence, SQL, guardrails.
3. Показать таблицу + график.
4. Нажать `Сохранить отчёт`.
5. Нажать `Запланировать` и создать расписание.
6. Нажать `Поделиться отчётом` и отправить в рабочую группу.

## 8) Как пересобрать локальную модель
```bash
docker compose exec -T api python -m app.scripts.build_local_intent_model
docker compose restart api
```

## 9) Как остановить проект
```bash
python start.py down
```
