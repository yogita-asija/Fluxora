# OrderFlow

A distributed order-processing platform. Current state: **Phase 3** — authentication, idempotent order creation with a transactional outbox, and an **outbox relay that publishes order events to Kafka** (at-least-once, ordered per order, retries with backoff). Stock reservation, payments, and the RabbitMQ saga come next.

| Layer | Technology |
| --- | --- |
| Frontend | React, Vite, JavaScript, React Router, Tailwind CSS v4, Axios, Recharts |
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic |
| Data & messaging | PostgreSQL 17, Redis, RabbitMQ, Kafka (KRaft) |
| Edge & observability | Nginx (load balancing, rate limiting, security headers), Prometheus, Grafana |
| Testing | pytest, HTTPX |

## What works today

- **Accounts:** register, sign in, sign out. Argon2id password hashing, short-lived JWT access tokens, roles (`customer`, `admin`).
- **Orders:** create (prices and totals computed on the server), list (paginated, filter by status), view, cancel. Customers see only their own orders; admins see all.
- **Idempotent order creation:** every `POST /orders` carries an `Idempotency-Key`. Retrying the same request returns the original order instead of a duplicate; reusing a key with a different request is rejected with 409. Keys are scoped per user.
- **Transactional outbox:** creating or cancelling an order writes an `outbox_events` row in the **same database transaction**, so an event exists if and only if the change happened. The **outbox relay** (a separate worker) publishes them to Kafka; see [Outbox relay](#outbox-relay-phase-3).
- **Dashboard:** login/register, orders list, new-order form, order detail with cancel. Products, Inventory, Analytics, and System Health pages from Phase 1.

## Project structure

```
orderflow/
├── backend/
│   ├── app/
│   │   ├── api/            # HTTP layer: routers and dependencies
│   │   │   ├── health.py   #   /health/live, /health/ready
│   │   │   └── v1/         #   /api/v1: auth, orders, products, admin
│   │   ├── core/           # config, database, errors, security (hashing, JWT), rate limit, metrics
│   │   ├── models/         # SQLAlchemy models (9 tables)
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # business rules (auth, orders, products)
│   │   ├── repositories/   # data access
│   │   ├── workers/        # outbox relay process + Kafka publisher
│   │   ├── main.py         # app factory
│   │   └── seed.py         # idempotent demo data
│   ├── alembic/            # migrations: 0001 initial schema, 0002 auth + per-user idempotency, 0003 outbox relay
│   ├── tests/
│   ├── Dockerfile, requirements.txt, requirements-dev.txt
├── frontend/               # React app (Vite)
├── infra/
│   ├── nginx/              # reverse proxy, load balancing, rate limit, security headers
│   ├── prometheus/
│   └── grafana/            # provisioned datasource + dashboard
├── scripts/init_env.py     # creates/updates .env with random secrets
├── docker-compose.yml
├── .env.example
├── Makefile                # shortcuts (optional)
└── README.md
```

Request flow: `route (api/) → service (services/) → repository (repositories/) → model (models/)`. Routes know HTTP, services know business rules, repositories know SQL.

## Quick start (Docker)

Requires Docker with Compose v2.

```bash
python3 scripts/init_env.py            # creates .env with generated secrets (or adds missing ones)
docker compose up -d --build           # builds, migrates, and starts everything
docker compose run --rm migrate python -m app.seed   # demo data + demo accounts
```

Open http://localhost:8080 and sign in with a demo account:

| Account | Email | Password |
| --- | --- | --- |
| Customer | `customer@orderflow.local` | `SEED_CUSTOMER_PASSWORD` from your `.env` |
| Admin | `admin@orderflow.local` | `SEED_ADMIN_PASSWORD` from your `.env` |

Or click **Create one** to register your own account (always a customer).

**Upgrading from Phase 2:** no `.env` changes are needed. `docker compose up -d --build` applies migration `0003` and starts the new `outbox-relay` service.

**Upgrading from Phase 1:** run `python3 scripts/init_env.py` once (it adds the new variables to your existing `.env` without touching the others), then `docker compose up -d --build` and the seed command above. Migration `0002` runs automatically; the seed command gives the existing demo accounts their passwords.

The first start downloads images and takes a few minutes; Kafka and RabbitMQ are the slowest to become healthy. Check progress with `docker compose ps`.

| URL | What |
| --- | --- |
| http://localhost:8080 | App (React dashboard) |
| http://localhost:8080/api/docs | Interactive API docs (disabled when `ENVIRONMENT=production`) |
| http://localhost:8080/health/ready | Readiness check |
| http://localhost:3000 | Grafana (login from `.env`: `GRAFANA_ADMIN_*`) |
| http://localhost:9090 | Prometheus |
| http://localhost:15672 | RabbitMQ management (login: `RABBITMQ_*`) |

**Load balancing:** `API_REPLICAS` (default 2) sets the number of API containers. Scale live with `docker compose up -d --scale api=4`. Every response through Nginx carries an `X-Upstream` header showing which replica served it.

## API overview

All routes are under `/api/v1`. Errors always look like `{"error": {"code", "message", "details"}}`.

| Method & path | Auth | Description |
| --- | --- | --- |
| `POST /auth/register` | – | Create a customer account → `201` |
| `POST /auth/login` | – | `{email, password}` → `{access_token, token_type, expires_in}` |
| `GET /auth/me` | Bearer | Current user |
| `GET /products`, `GET /products/{id}` | – | Catalogue |
| `POST /orders` | Bearer + `Idempotency-Key` header | `{"items": [{"product_id", "quantity"}]}` → `201` new order, `200` replay of an earlier identical request |
| `GET /orders?status=&limit=&offset=` | Bearer | Own orders (admin: all), newest first |
| `GET /orders/{id}` | Bearer | One order (someone else's is `404`) |
| `POST /orders/{id}/cancel` | Bearer | Cancel a `pending` order; otherwise `409` |

Try it from the command line:

```bash
TOKEN=$(curl -s localhost:8080/api/v1/auth/login -H 'content-type: application/json' \
  -d '{"email":"customer@orderflow.local","password":"<SEED_CUSTOMER_PASSWORD>"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s localhost:8080/api/v1/orders -H "Authorization: Bearer $TOKEN" -H 'Idempotency-Key: demo-key-0001' \
  -H 'content-type: application/json' -d '{"items":[{"product_id":"<id from /products>","quantity":2}]}'
```

Run the same order command twice: the second call returns `200` with the same order and writes no second outbox event.

## Outbox relay (Phase 3)

The API never talks to Kafka. It writes an `outbox_events` row in the same transaction as the order change; the **`outbox-relay`** service (`python -m app.workers.outbox_relay`) publishes those rows to Kafka.

```
API  --(1 transaction)-->  orders + outbox_events  --poll-->  outbox-relay  --acks=all-->  Kafka topic orderflow.order.events
```

| Property | How |
| --- | --- |
| No lost events | A row is marked `published` only after Kafka acknowledged it (`acks=all`, idempotent producer). Crash before the commit means the row stays `pending` and is sent again. |
| At-least-once | A resend can duplicate a message. Every message carries an `event_id` (header and body) so consumers can dedupe with the `processed_events` table (Phase 4). |
| Ordered per order | Kafka key = order id (same partition), and the relay only releases an event when no earlier event of the same order is unpublished. |
| Safe to scale | `FOR UPDATE SKIP LOCKED` batches: replicas claim different rows (`docker compose up -d --scale outbox-relay=2`). |
| Retries | Exponential backoff with jitter (`available_at`), then status `failed` after `OUTBOX_MAX_ATTEMPTS` (default 10). A failed event blocks later events of the same order until it is requeued. |
| Observable | Prometheus metrics on `:9100`, Grafana dashboard **OrderFlow Outbox Relay**, admin-only `GET /api/v1/admin/outbox`, and an "Outbox relay → Kafka" row on System Health (admins only). |

Message format (JSON value, key = order id, headers `event_id`, `event_type`, `aggregate_type`, `occurred_at`):

```json
{"event_id": "…", "event_type": "order.created", "aggregate_type": "order", "aggregate_id": "…", "occurred_at": "…", "payload": {"order_id": "…", "items": [...]}}
```

Try it:

```bash
docker compose logs -f outbox-relay                      # "batch: published=1 ..."
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic orderflow.order.events --from-beginning --property print.key=true --property print.headers=true
docker compose stop kafka                                # place an order: it stays pending, retries with backoff
docker compose start kafka                               # the backlog drains by itself
docker compose exec outbox-relay python -m app.workers.outbox_relay --requeue-failed   # after fixing a failure
```

Tuning (optional environment variables, defaults in `app/core/config.py`): `OUTBOX_BATCH_SIZE`, `OUTBOX_POLL_INTERVAL_SECONDS`, `OUTBOX_MAX_ATTEMPTS`, `OUTBOX_BACKOFF_BASE_SECONDS`, `OUTBOX_BACKOFF_MAX_SECONDS`, `OUTBOX_PUBLISH_TIMEOUT_SECONDS`, `OUTBOX_TOPIC_PARTITIONS`.

Trade-offs worth knowing: row locks are held while waiting for the Kafka ack (bounded by the publish timeout), polling adds up to `OUTBOX_POLL_INTERVAL_SECONDS` of latency (a log-based CDC tool such as Debezium would remove it), and published rows are never deleted yet (add a retention job before production use).

## Security

| Area | What is done |
| --- | --- |
| Passwords | Argon2id (library defaults, RFC 9106). Length 10–128 (the cap prevents hashing-cost DoS). Hashes upgrade transparently if parameters change. Never returned by the API or logged. |
| Login | One generic error for unknown email, wrong password, and disabled account. A dummy hash is verified for unknown emails so response time doesn't reveal which accounts exist. |
| Brute force | After 5 failed logins an account is locked for 15 minutes (`429` + `Retry-After`), counted in Redis so all API replicas share it. Nginx additionally limits `/api/v1/auth/` to 20 requests/minute per IP. If Redis is down the lockout fails open (logged) rather than blocking everyone. |
| Tokens | HS256 JWT, 30 min lifetime, fixed algorithm (no `alg: none` / algorithm confusion), `exp`/`iat`/`sub`/`iss` required. Role and active status are read from the database on every request, so a token can't carry privileges and disabling an account takes effect immediately. The app refuses to start with a missing, short (<32 chars), or placeholder `JWT_SECRET_KEY`. |
| Authorization | Orders are checked per user in the service layer. Someone else's order returns `404`, not `403`, so ids can't be probed. Admins are only created by the seed script, never through the API. |
| Input validation | Strict schemas: unknown fields are rejected (no mass assignment of `role`, `price`, `status`, `user_id`). Quantities, item counts, and header formats are bounded. Prices and totals always come from the database. Validation errors never echo submitted values (passwords). |
| Data integrity | Per-user unique idempotency keys enforced by the database; request fingerprint detects key reuse with a different body; row locks serialise concurrent cancels; money uses `Decimal`/`Numeric`. |
| HTTP | CORS allow-lists (origins, methods, headers; no credentials). `nosniff` and `Cache-Control: no-store` on API responses. Nginx adds `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and a strict Content-Security-Policy on the app. 1 MB request body limit. |
| Secrets | Nothing is hardcoded. `.env` is generated with random values and git-ignored; Compose fails with a clear message if a secret is missing. |

**Known limitations** (deliberate, listed so they are not mistaken for oversights):

- **No token revocation / refresh tokens.** "Sign out" discards the token in the browser; the token stays valid until it expires (30 min). The standard next step is short access tokens plus a rotating refresh token in an `httpOnly` cookie.
- **The token is stored in `sessionStorage`**, readable by script. A strict CSP reduces XSS risk; the `httpOnly` cookie approach above would remove it.
- **No TLS.** Run behind HTTPS (and add `Strict-Transport-Security`) before exposing publicly. Services bind to `127.0.0.1`.
- **Registration reveals whether an email exists** (`409`). Mitigated by the per-IP rate limit; avoiding it entirely needs email verification.
- **Account lockout can be triggered by someone else** for a known email (15 minutes). The usual trade-off for brute-force protection.

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

Vite proxies `/api` and `/health` to `http://localhost:8000` (override with `VITE_DEV_API_TARGET`). The host-run backend reads `JWT_SECRET_KEY` and `DATABASE_URL` from `.env`.

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
| Backend tests on PostgreSQL + Redis | see below |
| Frontend build | `cd frontend && npm run build` |
| Logs | `docker compose logs -f api` (`make logs`) |

**Tests.** By default tests run on in-memory SQLite and need no services. Two tests (concurrent duplicate requests and concurrent cancels) need real row locks and are skipped unless a PostgreSQL URL is provided. Use a throwaway database: the suite drops and recreates its tables.

```bash
docker compose exec postgres createdb -U orderflow orderflow_test
cd backend
TEST_DATABASE_URL=postgresql+psycopg://orderflow:<POSTGRES_PASSWORD>@localhost:15432/orderflow_test \
TEST_REDIS_URL=redis://:<REDIS_PASSWORD>@localhost:6379/0 \
python -m pytest
```

`TEST_REDIS_URL` additionally runs the login-throttle tests against real Redis. (`TEST_REDIS_URL` flushes that Redis database: don't point it at data you care about.) The schema itself (PostgreSQL types, partial index, JSONB) is also exercised by `alembic upgrade head` and `alembic check`.

## Environment variables

All set in `.env` (see `.env.example`). `.env` is git-ignored.

| Variable | Purpose |
| --- | --- |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | PostgreSQL credentials (required) |
| `JWT_SECRET_KEY` | Signs access tokens; 32+ characters (required). `init_env.py` generates 64 hex characters. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime (default 30) |
| `SEED_ADMIN_PASSWORD`, `SEED_CUSTOMER_PASSWORD` | Passwords for the demo accounts, 10+ characters. If empty, the seed command generates and prints random ones once. |
| `REDIS_PASSWORD` | Redis password (required) |
| `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | RabbitMQ credentials (required) |
| `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD` | Grafana login (required) |
| `DATABASE_URL` | Used by the backend **on the host** only; must use the same password as `POSTGRES_PASSWORD`. Containers get theirs from Compose. |
| `API_REPLICAS` | Number of API containers (default 2) |
| `CORS_ORIGINS` | Comma-separated allowed browser origins |
| `ENVIRONMENT`, `LOG_LEVEL` | Runtime mode (`production` disables API docs) and log verbosity |
| `HTTP_PORT`, `POSTGRES_PORT`, `REDIS_PORT`, `RABBITMQ_PORT`, `RABBITMQ_MANAGEMENT_PORT`, `PROMETHEUS_PORT`, `GRAFANA_PORT` | Host ports (all bound to 127.0.0.1). PostgreSQL defaults to 15432 to avoid clashes with a local install. |

The backend also accepts `REDIS_URL`, `RABBITMQ_URL`, and `KAFKA_BOOTSTRAP_SERVERS` (injected by Compose). `REDIS_URL` backs the login throttle; without it an in-process store is used (fine for a single process). Passwords are embedded in connection URLs, so keep them URL-safe; `init_env.py` generates hex strings.

## Database

Nine tables: `users`, `products`, `inventory`, `orders`, `order_items`, `payments`, `inventory_reservations`, `outbox_events`, `processed_events`.

- UUID primary keys, timestamptz timestamps, `Numeric(12,2)` money.
- CHECK constraints for statuses, non-negative amounts, positive quantities, and `quantity_reserved <= quantity_on_hand`.
- Unique constraints include `(user_id, idempotency_key)` on orders, `(order_id, product_id)` on items and reservations, and `(event_id, consumer)` on `processed_events` (idempotent consumers).
- `inventory.version` provides optimistic locking.
- `outbox_events` has partial indexes for the relay's polling query and its per-order ordering check. Order creation writes `order.created` and cancellation writes `order.cancelled`, in the same transaction as the order change.
- Constraint and index names follow a naming convention so migrations are deterministic.

## What is intentionally not built yet

Stock reservation (creating an order does **not** change inventory yet), payments, Kafka/RabbitMQ **consumers**, and the saga/compensation logic: these are Phase 4. Events are already being published to Kafka, but nothing consumes them yet. `/health/ready` checks PostgreSQL only; Redis, RabbitMQ, and Kafka checks should be added when the code depends on them. Inventory and Analytics pages are placeholders (Analytics charts use sample data).

## Notes and manual steps

- **Run `init_env.py` (or edit `.env`) before `docker compose up`.** Compose refuses to start with a clear message if a required secret is missing.
- **"ports are not available ... forbidden by its access permissions" (Windows):** a host port is reserved by Windows or used by another program. Find reserved ranges with `netsh interface ipv4 show excludedportrange protocol=tcp`, pick a port outside them, set it in `.env` (e.g. `POSTGRES_PORT=15432`, and the same port in `DATABASE_URL`), then run `docker compose up -d` again. Every host port is configurable; containers always talk to each other on the standard internal ports.
- **Kafka is internal.** It is reachable from other containers as `kafka:9092` but not published to the host. Add a second listener when you need host access.
- **Image tags** (`postgres:17`, `redis:7.4`, `rabbitmq:4.1`, `apache/kafka:3.9.1`, `nginx:1.28`, `prom/prometheus:v3.5.0`, `grafana/grafana:12.1.0`) are pinned; bump them deliberately. Nginx must be 1.27.3 or newer for the `resolve` upstream parameter used by the load balancer.
- **Security posture is dev-grade:** see the Security section for what is covered and the known limitations.
