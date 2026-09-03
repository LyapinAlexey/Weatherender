# Architecture and Project Structure

This document details the high-level architecture, design patterns, component interactions, and deployment structure of **Weatherender**.

---

## 1. High-Level Architecture Overview

`Weatherender` is a production-grade, containerized application providing a RESTful web interface (Flask), a command-line interface (CLI), and an asynchronous JSON API v2 (FastAPI). It features external API integrations, multi-level fallback strategies, asynchronous production worker configurations, and real-time observability. In production, the Flask and FastAPI stacks are merged into a single deployed image — see [Component 6.5](#6-infrastructure-observability--cloud-deployment) below.

The installable Python package lives under `src/weatherender/` (`pip install weatherender`). The production / GHCR image is `ghcr.io/weatherender-foundation/weatherender-api`.

![Project Architecture](architecture.svg)

### Key Architectural Characteristics

- **Shared Core Services:** Both WEB and CLI interfaces leverage a unified business logic and data access layer.
- **Resilience & Fallback:** Automatic IP geolocation failover chain and graceful degradation when Redis caching is offline.
- **Production Performance:** Flask served via Gunicorn utilizing `gevent` workers, with `psycogreen` patching `psycopg2` for non-blocking PostgreSQL network I/O.
- **Data Maintenance:** Deterministic periodic DB cleanup via APScheduler, guarded by a lock-file leader-election pattern to avoid duplicate execution across Gunicorn workers.
- **Single-Image Deployment:** Render (and GHCR) use a single `uvicorn` process from `src/weatherender/API/Dockerfile` that mounts the synchronous Flask app inside the async FastAPI app via `WSGIMiddleware`. Locally Compose still runs two containers: `web` on **5001** (Flask only) and `api` on **8001** (FastAPI + the same Flask app mounted). Production matches the `api` container, not `web`.


---

## 2. Tech Stack & Infrastructure

| Layer | Technologies & Tools |
| --- | --- |
| **Language & Web Engine** | Python 3.13, Flask, Gunicorn (`gevent` + `psycogreen`) |
| **Database & ORM** | PostgreSQL (Supabase in prod), SQLAlchemy, Alembic |
| **Caching Layer** | Redis / Upstash Redis (`redis-py`) |
| **Validation & Docs** | Marshmallow, `apispec`, `flask-swagger-ui` (OpenAPI 3.0) |
| **Security & Rate Limiting** | `flask-talisman` (headers), `Flask-Limiter` (v1), `SlowAPI` (v2) |
| **Observability** | `prometheus-flask-exporter`, structured JSON logging |
| **DevOps & Hosting** | Docker, Docker Compose, GitHub Actions, GHCR, Render, UptimeRobot |
| **Packaging** | `pyproject.toml` (`weatherender==2.0.0` on PyPI) |
| **Testing & Performance** | Pytest, `unittest.mock`, Codecov, k6 (load testing) |
| **Async Stack** | FastAPI, Uvicorn, httpx (async), Pydantic v2, `redis.asyncio`, `asyncpg` |

---

## 3. Directory & File Structure

```text
Weatherender/
├── src/weatherender/                 # installable package (PyPI: weatherender)
│   ├── WEB/                          # Flask web application layer
│   │   ├── app.py                    # Talisman, rate limiter, Prometheus, /, /health
│   │   ├── api_routes.py             # JSON API blueprint (/api/weather, /api/ping, /api/apispec.json)
│   │   ├── extensions.py             # flask-limiter instance (avoids circular imports)
│   │   ├── scheduler.py              # APScheduler DB cleanup with lock-file leader election
│   │   ├── swagger_config.py         # OpenAPI 3.0 + Swagger UI
│   │   ├── logging_config.py         # structured JSON logging
│   │   └── Dockerfile                # local Flask-only container (port 5001)
│   ├── API/                          # FastAPI v2 + mounted Flask — sole Render / GHCR image

│   │   ├── main.py                   # ASGI entry; mounts WEB.app via WSGIMiddleware
│   │   ├── async_services.py         # httpx.AsyncClient mirror of WeatherService
│   │   ├── async_cache.py            # redis.asyncio singleton cache
│   │   ├── async_db.py               # create_async_engine / AsyncSessionLocal (asyncpg)
│   │   ├── pydantic_schemas.py       # Pydantic v2 query + response models
│   │   └── Dockerfile                # GHCR + Render image (port 8001: Flask + FastAPI)

│   ├── CLI/
│   │   ├── main.py                   # console script: weatherender
│   │   └── Dockerfile
│   ├── config.py                     # environment-based settings
│   ├── models.py                     # SQLAlchemy ORM
│   ├── services.py                   # WeatherAPI + IP fallback chain
│   ├── cache.py                      # Redis TTL cache, graceful fallback
│   ├── dbclear.py                    # purge WeatherRequest rows older than 30 days
│   ├── schemas.py                    # Marshmallow validation
│   └── snow.py                       # SSCI snow-surface algorithm
├── tests/
├── load_tests/
├── docs/
│   ├── PERFORMANCE.md
│   ├── DEPLOYMENT.md
│   ├── API.md
│   ├── CHANGELOG.md
│   ├── ARCHITECTURE.md
│   └── architecture.svg
├── alembic/
├── scripts/
├── pyproject.toml
├── docker-compose.yml
└── .github/workflows/
    ├── ci.yml
    └── publish-github.yml            # build & push GHCR image
```

---

## 4. Component Responsibilities

### Web Layer (`src/weatherender/WEB/`)

- **`app.py`:** Registers `flask-talisman` (secure headers), `PrometheusMetrics` (`/metrics`), and `Flask-Limiter` (rate limiting, applied to `/` and, per-route, to `/api/weather` and `/api/apispec.json`).
- **`api_routes.py`:** A separate Flask Blueprint (`api_bp`) exposing the JSON REST API — `/api/weather`, `/api/ping`, `/api/apispec.json`. `/api/weather` and `/api/apispec.json` carry their own `@limiter.limit(...)` decorators (imported from `WEB/extensions.py`); `/api/ping` is intentionally left unlimited.
- **`swagger_config.py`:** Exposes interactive API documentation at `/apidocs` and the JSON specification at `/api/apispec.json`.
- **`logging_config.py`:** Enforces structured JSON formatted logs across the application context for machine-readable log parsing.
- **`scheduler.py`:** Runs periodic maintenance via APScheduler's `BackgroundScheduler`, calling `dbclear.clear()` every 7 days to purge `WeatherRequest` rows older than 30 days. Since Gunicorn runs multiple worker processes (`-w 4`), a naive scheduler start would run once per worker. This is solved with a **lock-file leader-election pattern**: each worker atomically attempts to create `/tmp/scheduler_leader.lock` via `os.open(path, O_CREAT | O_EXCL | O_WRONLY)`; only the worker that succeeds starts the scheduler. Known limitation: the lock file persists for the container's lifetime, so if Gunicorn restarts a crashed leader worker, the new process won't reclaim leadership until the next deploy (fresh filesystem). `init_scheduler()` is called from `app.py` after `Config.validate()`, so a failing config prevents lock acquisition rather than leaving a stale, unclaimed lock behind.

Local Compose command:

```text
gunicorn weatherender.WEB.app:app --worker-class gevent --worker-connections 50 -w 4 -b 0.0.0.0:5001
```

### Core Domain Services (`services.py`, `schemas.py`, `snow.py`)

- **`services.py`:** Encapsulates weather requests via [WeatherAPI](https://www.weatherapi.com/). Executes **IP geolocation fallback chain**: `ip-api.com` first, then `ipinfo.io`.
- **`schemas.py`:** Strictly validates incoming query parameters (e.g. city names) and standardizes API output formats using Marshmallow.
- **`snow.py`:** Snow Surface Condition Index (SSCI) algorithm used by both stacks.

### Async API Layer (`src/weatherender/API/`)

- **`main.py`:** FastAPI ASGI app exposing `/api/v2/weather` and `/api/v2/health`. `city` is validated via `Annotated[WeatherQueryParams, Query()]` (`pydantic_schemas.py`) rather than a bare `Query(...)` — 1–100 characters, blank/whitespace-only rejected. Rate limiting is enforced on `GET /api/v2/weather` via `slowapi` (25 req/min per IP). Mounts the entire synchronous Flask app at `/` via `a2wsgi.WSGIMiddleware`, making this the single process Render and GHCR deploy.
- **`async_services.py` / `async_cache.py` / `async_db.py`:** async counterparts to `services.py`, `cache.py`, and the sync engine in `models.py`, built on `httpx.AsyncClient`, `redis.asyncio`, and `create_async_engine` (asyncpg) respectively — intentionally separate from the sync stack rather than shared.
- **`pydantic_schemas.py`:** Pydantic v2 equivalent of `schemas.py`'s Marshmallow validation, scoped to `API/` only.

Production / GHCR command:

```text
uvicorn weatherender.API.main:app --host 0.0.0.0 --port ${PORT} --workers 4
```

### CLI (`src/weatherender/CLI/`)

Console script declared in `pyproject.toml`:

```toml
[project.scripts]
weatherender = "weatherender.CLI.main:main"
```

Run with `weatherender` after `pip install weatherender`, or `docker compose run --rm cli weatherender`.

### Data & Caching Engine (`models.py`, `cache.py`, `alembic/`)

- **`models.py`:** Defines database tables (request history records) managed via SQLAlchemy, with `pool_size=10, max_overflow=20` configured on the engine (raised from SQLAlchemy's defaults during load testing — see [`PERFORMANCE.md`](PERFORMANCE.md)).
- **`cache.py`:** Implements key-value operations against Redis with a default 5-minute TTL (`REDIS_TTL`). Implements **graceful degradation**: catches Redis connectivity errors automatically, ensuring the app proceeds to fetch data directly from upstream sources without breaking client execution.
- **`dbclear.py`:** Deletes `WeatherRequest` rows older than 30 days (`created_at < now - 1 month`). Invoked on a schedule by `WEB/scheduler.py`; can also be run standalone.
- **`alembic/`:** Maintains database schema version control.

---

## 5. System Execution & Data Flow

There are two distinct request paths that write different amounts of data — this distinction matters when interpreting load-test results (see [`PERFORMANCE.md`](PERFORMANCE.md)):

### Web UI (`/`) — writes a request record on every call

```text
Client (browser, form POST/GET)
│
▼
[ WEB Layer: app.py ] ─── (Rate Limiter: 25/min per IP, Security Headers)
│
▼
[ Validation Layer ] ─── (Marshmallow in schemas.py)
│
▼
[ Service Layer ] (services.py → WeatherService.get_weather)
│
├───────────────────────────────┐
▼                               ▼
[ Redis Cache Check ]           [ Cache Miss / Bypass ]
(cache.py with 5m TTL)          │
│                               ▼
├─ (Hit) ────────►              [ Fetch External API Data ]
│                               (WeatherAPI / IP Fallback Chain)
│                               │
│                               ▼
│                               [ Cache the fresh response in Redis ]
│                               │
▼                               ▼
└──────────────► [ Write a WeatherRequest row to PostgreSQL ]
│
▼
[ Render HTML template ]
```

### JSON API (`/api/weather`) — writes a request record on every call (including validation failures)

```text
Client (API consumer)
│
▼
[ WEB Layer: api_routes.py ] ─── (per-route rate limiter on /api/weather)
│
▼
[ Validation Layer ] ─── (Marshmallow in schemas.py)
│
├─ (Invalid) ──► [ Write a WeatherRequest row (success=0) ] ──► [ Return 400 ]
│
▼ (Valid)
[ Service Layer ] (services.py → WeatherService.get_weather)
│
├─ (Cache hit) ──────────► [ Return cached JSON ]
│
└─ (Cache miss) ─► [ Fetch External API Data ] ─► [ Cache in Redis ]
│
▼
[ Write a WeatherRequest row to PostgreSQL ]
(success=1 or success=0 depending on upstream result)
│
▼
[ Return JSON ]
```

### Async JSON API (`/api/v2/weather`) — writes a request record on every call, fully async

```text
Client (async API consumer)
│
▼
[ API Layer: main.py ] ─── (Rate Limiter: slowapi 25/min per IP)
│
▼
[ Validation Layer ] ─── (Pydantic v2 in pydantic_schemas.py)
│
▼
[ Async Service Layer ] (async_services.py → AsyncWeatherService.get_weather_async)
│
├─ (Cache hit) ──────────► [ Return cached JSON ]
│                          (async_cache.py, redis.asyncio)
│
└─ (Cache miss) ─► [ Fetch External API Data ] ─► [ Cache in Redis ]
│
▼
[ Write a WeatherRequest row to PostgreSQL ]
(async_db.py, AsyncSessionLocal)
│
▼
[ Return JSON ]
```

---

## 6. Infrastructure, Observability & Cloud Deployment

1. **Gunicorn + Gevent Stack:** In production (inside the mounted Flask app), Gunicorn uses `gevent` workers (`-w 4 --worker-class gevent --worker-connections 50`) alongside `psycogreen`, which patches `psycopg2` for non-blocking PostgreSQL I/O under gevent. This was adopted after load testing showed Gunicorn's default `sync` workers dropping connections under concurrent load — see [`PERFORMANCE.md`](PERFORMANCE.md) for the full investigation and before/after numbers.
2. **Cold-Start & Database Connection Optimization:**
   - Hosted on Render (app) + Supabase (PostgreSQL) + Upstash (Redis). Full setup steps in [`DEPLOYMENT.md`](DEPLOYMENT.md).
   - An external automated worker (**UptimeRobot**) sends an HTTP GET request to `/api/ping` every 10 minutes.
   - `/api/ping` bypasses the database completely, keeping the web container warm while preserving Supabase's limited free-tier connection pool.
3. **Observability:**
   - `/metrics`: Exposes real-time application metrics formatted for **Prometheus**.
   - `/health`: Readiness check verifying database connectivity, used by Docker Compose's `service_healthy` condition.
   - Structured JSON logging facilitates monitoring and diagnostic ingestion.
4. **Automated CI/CD Pipeline:**
   - **GitHub Actions** (`ci.yml`) enforces code quality checks (Ruff, Mypy) and executes the full `pytest` suite before triggering deploy webhooks to production.
   - **`publish-github.yml`** builds `src/weatherender/API/Dockerfile` and pushes `ghcr.io/weatherender-foundation/weatherender-api:{latest,$SHA}` on every push to `main`.
5. **Single-Image Production Deployment:**
   Render deploys only the image from `src/weatherender/API/Dockerfile` — it mounts `weatherender.WEB.app` internally via `WSGIMiddleware`, so one `uvicorn` process serves both the async v2 API and the full legacy Flask stack (UI, v1 API, `/health`, `/metrics`, `/apidocs`).

   Locally, Compose runs two containers:
   - `web` on **5001** — Gunicorn + Flask only (UI + sync API). No `/api/v2`.
   - `api` on **8001** — Uvicorn + FastAPI with Flask mounted. Async v2 **and** the full Flask stack. This is what production looks like.


---

## 7. Local vs production process model

| Environment | Process | What it serves | Port |
| --- | --- | --- | --- |
| Local Compose `web` | Gunicorn + Flask | HTML UI, sync v1 API, `/health`, `/metrics`, `/apidocs`, `/api/ping` | `5001` |
| Local Compose `api` | Uvicorn + FastAPI + Flask via `WSGIMiddleware` | Everything on `web` **plus** `/api/v2/*`, `/v2/docs`, `/v2/redoc` | `8001` |
| Production / GHCR | Same as local `api` | Combined stack | Render `$PORT` |
