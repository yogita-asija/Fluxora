# OrderFlow

A distributed order-processing platform. This repository is the **foundation**: a runnable skeleton with clean layering, a complete database schema, and the full local infrastructure. Business logic, authentication, and the event-driven workflows come next.

| Layer | Technology |
| --- | --- |
| Frontend | React, Vite, JavaScript, React Router, Tailwind CSS v4, Axios, Recharts |
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic |
| Data & messaging | PostgreSQL 17, Redis, RabbitMQ, Kafka (KRaft) |
| Edge & observability | Nginx (load balancing), Prometheus, Grafana |
| Testing | pytest, HTTPX |

## Project structure

```
orderflow/
├── backend/
│   ├── app/
│   │   ├── api/            # HTTP layer: routers and dependencies
│   │   │   ├── health.py   #   /health/live, /health/ready
│   │   │   └── v1/         #   versioned routes mounted at /api/v1
│   │   ├── core/           # config, database, errors, logging, metrics
│   │   ├── models/         # SQLAlchemy models (9 tables)
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # business rules
│   │   ├── repositories/   # data access
│   │   ├── main.py         # app factory
│   │   └── seed.py         # idempotent demo data
│   ├── alembic/            # migrations (0001 = initial schema)
│   ├── tests/
│   ├── Dockerfile, requirements.txt, requirements-dev.txt
├── frontend/               # React app (Vite)
├── infra/
│   ├── nginx/              # reverse proxy + API load balancing
│   ├── prometheus/
│   └── grafana/            # provisioned datasource + dashboard
├── scripts/init_env.py     # generates .env with random secrets
├── docker-compose.yml
├── .env.example
├── Makefile                # shortcuts (optional)
└── README.md
```

Request flow: `route (api/) → service (services/) → repository (repositories/) → model (models/)`. Routes know HTTP, services know business rules, repositories know SQL. `products` is implemented end to end as the reference pattern; orders, inventory, and payments follow it.

## Quick start (Docker)

Requires Docker with Compose v2.

```bash
python3 scripts/init_env.py            # creates .env with generated secrets
docker compose up -d --build           # builds and starts everything
docker compose run --rm migrate python -m app.seed   # load demo data
```

The first start downloads images and takes a few minutes; Kafka and RabbitMQ are the slowest to become healthy. Check progress with `docker compose ps`.

| URL | What |
| --- | --- |
| http://localhost:8080 | App (React dashboard) |
| http://localhost:8080/api/docs | Interactive API docs |
| http://localhost:8080/health/ready | Readiness check |
| http://localhost:3000 | Grafana (login from `.env`: `GRAFANA_ADMIN_*`) |
| http://localhost:9090 | Prometheus |
| http://localhost:15672 | RabbitMQ management (login: `RABBITMQ_*`) |

Migrations run automatically on every `up` through the one-shot `migrate` service; the API replicas wait for it to finish.

**Load balancing:** `API_REPLICAS` (default 2) sets the number of API containers. Scale live with `docker compose up -d --scale api=4`. Every response through Nginx carries an `X-Upstream` header showing which replica served it:

```bash
for i in 1 2 3 4; do curl -sI localhost:8080/health/live | grep X-Upstream; done
```

## Local development (backend and frontend on the host)

Requires Python 3.13+, Node 22+, and Docker (for the databases).

```bash
python3 scripts/init_env.py

# backend
python3 -m venv backend/.venv
source backend/.venv/bin/activate            # Windows: backend\.venv\Scripts\activate
pip install -r backend/requirements-dev.txt

# frontend
cd frontend && npm install && cd ..

# infrastructure only
docker compose up -d postgres redis rabbitmq kafka

# schema + demo data
cd backend
alembic upgrade head
python -m app.seed

# run (two terminals)
uvicorn app.main:app --reload --port 8000    # in backend/
npm run dev                                  # in frontend/  -> http://localhost:5173
```

Vite proxies `/api` and `/health` to `http://localhost:8000` (override with `VITE_DEV_API_TARGET`).

## Command reference

| Task | Command |
| --- | --- |
| Install | see Local development above (`make install`) |
| Run everything | `docker compose up -d --build` (`make up`) |
| Stop | `docker compose down` (`make down`; add `-v` to also delete data) |
| Migrate (Docker) | `docker compose run --rm migrate` (`make migrate`) |
| Migrate (host) | `cd backend && alembic upgrade head` |
| Create a migration | `cd backend && alembic revision --autogenerate -m "describe change"` |
| Check models match migrations | `cd backend && alembic check` |
| Seed (Docker) | `docker compose run --rm migrate python -m app.seed` (`make seed`) |
| Seed (host) | `cd backend && python -m app.seed` |
| Backend tests | `cd backend && python -m pytest` (`make test`) |
| Frontend build | `cd frontend && npm run build` |
| Logs | `docker compose logs -f api` (`make logs`) |

Backend tests run on in-memory SQLite, so they need no running services. The schema itself (PostgreSQL types, partial index, JSONB) is exercised by `alembic upgrade head` and `alembic check` against a real PostgreSQL.

## Environment variables

All set in `.env` (see `.env.example`). `.env` is git-ignored.

| Variable | Purpose |
| --- | --- |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | PostgreSQL credentials (required) |
| `REDIS_PASSWORD` | Redis password (required) |
| `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | RabbitMQ credentials (required) |
| `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD` | Grafana login (required) |
| `DATABASE_URL` | Used by the backend **on the host** only; must use the same password as `POSTGRES_PASSWORD`. Containers get theirs from Compose. |
| `API_REPLICAS` | Number of API containers (default 2) |
| `CORS_ORIGINS` | Comma-separated allowed browser origins |
| `ENVIRONMENT`, `LOG_LEVEL` | Runtime mode and log verbosity |
| `HTTP_PORT`, `POSTGRES_PORT`, `REDIS_PORT`, `RABBITMQ_PORT`, `RABBITMQ_MANAGEMENT_PORT`, `PROMETHEUS_PORT`, `GRAFANA_PORT` | Host ports (all bound to 127.0.0.1) |

The backend also accepts `REDIS_URL`, `RABBITMQ_URL`, and `KAFKA_BOOTSTRAP_SERVERS` (injected by Compose) for later phases. Passwords are embedded in connection URLs, so keep them URL-safe; `init_env.py` generates hex strings.

## Database

Nine tables: `users`, `products`, `inventory`, `orders`, `order_items`, `payments`, `inventory_reservations`, `outbox_events`, `processed_events`.

- UUID primary keys, timestamptz timestamps, `Numeric(12,2)` money.
- CHECK constraints for statuses, non-negative amounts, positive quantities, and `quantity_reserved <= quantity_on_hand`.
- Unique constraints include `orders.idempotency_key`, `(order_id, product_id)` on items and reservations, and `(event_id, consumer)` on `processed_events` (idempotent consumers).
- `inventory.version` provides optimistic locking.
- `outbox_events` has a partial index on pending rows for the future outbox relay.
- Constraint and index names follow a naming convention so migrations are deterministic.

## What is intentionally not built yet

Authentication, order placement and its workflow, Kafka producers, RabbitMQ consumers, the outbox relay, and real payment handling. `/health/ready` currently checks PostgreSQL only; Redis, RabbitMQ, and Kafka checks should be added when code starts using them. Orders, Inventory, and Analytics pages are placeholders (Analytics charts use sample data).

## Notes and manual steps

- **Run `init_env.py` (or edit `.env`) before `docker compose up`.** Compose refuses to start with a clear message if a required secret is missing.
- **Kafka is internal.** It is reachable from other containers as `kafka:9092` but not published to the host. Add a second listener when you need host access.
- **Image tags** (`postgres:17`, `redis:7.4`, `rabbitmq:4.1`, `apache/kafka:3.9.1`, `nginx:1.28`, `prom/prometheus:v3.5.0`, `grafana/grafana:12.1.0`) are pinned; bump them deliberately. Nginx must be 1.27.3 or newer for the `resolve` upstream parameter used by the load balancer.
- **Security posture is dev-grade:** services bind to localhost, there is no TLS, and `/health/` and `/api/docs` are exposed through Nginx. Revisit before deploying anywhere public.
