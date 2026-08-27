.PHONY: start up down ingest reset-db eval test fmt

start:
	docker compose up --build

up:
	docker compose up --build

down:
	docker compose down

ingest:
	docker compose exec backend python -m app.ingestion.pipeline || python -m backend.app.ingestion.pipeline

reset-db:
	docker compose exec postgres psql -U postgres -d rag -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	docker compose exec backend alembic -c alembic.ini upgrade head || (cd backend && alembic -c alembic.ini upgrade head)

eval:
	docker compose exec backend python evaluation/run_eval.py

test:
	pytest backend/tests -v

fmt:
	ruff check --fix .
	ruff format .
