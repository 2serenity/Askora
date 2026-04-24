DC=docker compose --project-name analytics_workspace

up:
	$(DC) up --build -d

dev:
	$(DC) up --build

down:
	$(DC) down

logs:
	$(DC) logs -f

migrate:
	$(DC) exec api alembic upgrade head

seed:
	$(DC) exec api python -m app.seed.seed_demo

test:
	$(DC) exec api python -m unittest discover -s tests -p "test_*.py"

regression:
	$(DC) exec api python -m app.scripts.query_regression --strict-cases

stress:
	$(DC) exec api python -m app.scripts.local_intent_stress

web-lint:
	node ./apps/web/node_modules/next/dist/bin/next lint ./apps/web

web-typecheck:
	node ./apps/web/node_modules/typescript/bin/tsc -p ./apps/web/tsconfig.json --noEmit

web-build:
	node ./apps/web/node_modules/next/dist/bin/next build ./apps/web

verify:
	$(DC) exec api python -m unittest discover -s tests -p "test_*.py"
	node ./apps/web/node_modules/next/dist/bin/next lint ./apps/web
	node ./apps/web/node_modules/typescript/bin/tsc -p ./apps/web/tsconfig.json --noEmit
	$(DC) exec api python -m app.scripts.query_regression --strict-cases --min-pass-rate 90 --max-false-block-rate 8 --max-avg-latency-ms 1200 --json-out /tmp/query-regression-report.json
	$(DC) exec api python -m app.scripts.local_intent_stress
	docker cp analytics-api:/tmp/query-regression-report.json ./docs/query-regression-report.json

restart:
	$(DC) restart

rebuild:
	$(DC) down
	$(DC) up --build -d

