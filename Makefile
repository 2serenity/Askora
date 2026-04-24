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
	$(DC) exec api python -m app.scripts.query_regression

web-lint:
	npm --prefix apps/web run lint

web-typecheck:
	npm --prefix apps/web run typecheck

web-build:
	npm --prefix apps/web run build

verify:
	$(DC) exec api python -m unittest discover -s tests -p "test_*.py"
	npm --prefix apps/web run lint
	npm --prefix apps/web run typecheck
	$(DC) exec api python -m app.scripts.query_regression --min-pass-rate 90 --max-false-block-rate 8 --max-avg-latency-ms 1200 --json-out /tmp/query-regression-report.json
	docker cp analytics-api:/tmp/query-regression-report.json ./docs/query-regression-report.json

restart:
	$(DC) restart

rebuild:
	$(DC) down
	$(DC) up --build -d

