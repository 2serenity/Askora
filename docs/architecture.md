# Архитектура продукта

## Product vision
Это не чат-бот ради красивого промпта, а `analytics workspace` для non-tech пользователей. Пользователь формулирует вопрос на русском языке, а платформа:

1. извлекает намерение и бизнес-термины;
2. резолвит их через внешний semantic layer;
3. строит нормализованный `QueryPlan`;
4. генерирует SQL только из whitelisted выражений;
5. прогоняет SQL через guardrails и precheck;
6. выполняет запрос и сохраняет аудит, историю, отчёты и расписания.

## Почему архитектура подходит кейсу
- `Hybrid NL2SQL`: LLM помогает с пониманием формулировки, но не получает право генерировать произвольный SQL.
- `Metadata-driven semantic layer`: metrics, dimensions, filters, joins, aliases и templates вынесены в YAML и DB overrides.
- `Guardrails-first`: все запросы проходят через SQL parser, whitelist таблиц/полей, complexity scoring, row limit и execution timeout.
- `Product shell`: есть auth, роли, explainability, history, reports, schedules и admin-контур, поэтому решение выглядит как зрелый продукт, а не как демо-скрипт.

## Хакатон-компромиссы без потери product-feel
- Scheduler отправляет stub email вместо реальной доставки, но модели, UI и audit уже готовы под реальный канал.
- Semantic layer редактируется через минимальный admin UI и DB overrides поверх YAML-базы, без тяжёлого enterprise-конструктора.
- NL2SQL extractor сочетает rules + OpenAI Responses API + approved templates, а при отсутствии ключа gracefully деградирует в rule-based режим.

## Монорепо
- `apps/api`: FastAPI, SQLAlchemy, Alembic, scheduler, seed, guardrails, audit, semantic layer.
- `apps/web`: Next.js App Router, Tailwind, shadcn-style UI components, React Query, Recharts, RHF + zod.
- `docs`: архитектурные заметки, сценарии замены demo schema на реальную.

## Как заменить demo DB на реальную позже
1. Подключить новую PostgreSQL БД через `DATABASE_URL`.
2. Обновить `apps/api/app/semantic_layer/config/catalog.yaml`:
   - `datasets.table`
   - `joins`
   - physical fields в metrics/dimensions/filters
3. При необходимости добавить или обновить `semantic_dictionary_entries` и `approved_query_templates`.
4. Проверить whitelist в `app/sql_guardrails/validator.py`.
5. Если отличаются временные поля или бизнес-формулы, обновить expressions в semantic catalog, не меняя frontend и orchestration.

## End-to-end flow
1. Пользователь логинится.
2. Отправляет вопрос в workspace.
3. Backend строит `QueryIntent`.
4. `SemanticResolver` собирает `QueryPlan`.
5. `SQLBuilder` превращает plan в SQL.
6. `SQLGuardrailsValidator` валидирует и оценивает риск.
7. `QueryExecutor` выполняет запрос.
8. `VisualizationPlanner` выбирает график.
9. История, audit и отчёты сохраняются в БД.

