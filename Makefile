# Convenience wrappers. Every target is a plain command you can also run by hand (see README).
# Assumes macOS/Linux; on Windows run the underlying commands from the README.

VENV := backend/.venv

.PHONY: env up down logs migrate seed test install infra-up dev-backend dev-frontend migrate-local seed-local

# --- Docker: whole stack ---------------------------------------------------
env:            ## create .env with generated secrets
	python3 scripts/init_env.py

up:             ## build and start everything
	docker compose up -d --build

down:           ## stop everything (data volumes are kept)
	docker compose down

logs:
	docker compose logs -f --tail=100

migrate:        ## apply database migrations inside Docker
	docker compose run --rm migrate

seed:           ## load demo data inside Docker (idempotent)
	docker compose run --rm migrate python -m app.seed

# --- Local development (backend + frontend on the host) ----------------------
install:        ## create the Python venv and install all dependencies
	python3 -m venv $(VENV)
	$(VENV)/bin/python -m pip install -r backend/requirements-dev.txt
	cd frontend && npm install

infra-up:       ## start only PostgreSQL, Redis, RabbitMQ, Kafka
	docker compose up -d postgres redis rabbitmq kafka

migrate-local:
	cd backend && .venv/bin/alembic upgrade head

seed-local:
	cd backend && .venv/bin/python -m app.seed

dev-backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test:           ## backend tests (in-memory SQLite, no services required)
	cd backend && .venv/bin/python -m pytest
