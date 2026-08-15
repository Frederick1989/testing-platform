.PHONY: up down build logs migrate seed backup restore demo psql test api-test

# --- Compose --------------------------------------------------------------
up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

# --- Backend ops ----------------------------------------------------------
migrate:
	docker compose exec api alembic upgrade head

seed:
	docker compose exec api python -m app.services.demo

# --- Backups --------------------------------------------------------------
backup:
	./scripts/backup_database.sh

restore:
	./scripts/restore_database.sh $(FILE)

# --- Local (no Docker) dev -------------------------------------------------
api-dev:
	cd services/test-manager-api && .venv/bin/uvicorn app.main:app --port 7000 --reload

frontend-dev:
	cd frontend && npm run dev

api-test:
	cd services/test-manager-api && .venv/bin/python -m pytest tests
