# Architecture and Project Structure

This document details the high-level architecture, design patterns, component interactions, and deployment structure of **Weatherender**.

---

## 1. High-Level Architecture Overview

`Weatherender` is a production-grade, containerized application providing both a RESTful Web Interface (Flask) and a Command Line Interface (CLI). It features external API integrations, multi-level fallback strategies, asynchronous production worker configurations, and real-time observability.

![Project Architecture](docs/architecture.svg)

### Key Architectural Characteristics:
- **Shared Core Services**: Both WEB and CLI interfaces leverage a unified business logic and data access layer.
- **Resilience & Fallback**: Automatic IP geolocation failover chain and graceful degradation when Redis caching is offline.
- **Production Performance**: Flask served via Gunicorn utilizing `gevent` workers, with `psycogreen` patching `psycopg2` for non-blocking PostgreSQL network I/O.
- **Data Maintenance**: Probabilistic automated DB storage cleanup logic executed on active web traffic.

---

## 2. Tech Stack & Infrastructure

| Layer | Technologies & Tools |
| :--- | :--- |
| **Language & Web Engine** | Python 3.13, Flask, Gunicorn (`gevent` + `psycogreen`) |
| **Database & ORM** | PostgreSQL (Supabase in Prod), SQLAlchemy, Alembic |
| **Caching Layer** | Redis / Upstash Redis (`redis-py`) |
| **Validation & Docs** | Marshmallow, `apispec`, `flask-swagger-ui` (OpenAPI 3.0) |
| **Security & Rate Limiting**| `flask-talisman` (Headers), `Flask-Limiter` |
| **Observability** | `prometheus-flask-exporter`, Structured JSON Logging |
| **DevOps & Hosting** | Docker, Docker Compose, GitHub Actions, Render (Web Host), UptimeRobot (Heartbeat) |
| **Testing & Performance**| Pytest, `unittest.mock`, Codecov, k6 (Load Testing) |

---

## 3. Directory & File Structure

```text
Weatherender/
├── WEB/                   # Flask Web Application Layer
│   ├── app.py              # App entry point — Talisman, rate limiter, Prometheus metrics, web routes (/, /health)
│   ├── api_routes.py        # JSON API Blueprint (/api/weather, /api/ping, /api/apispec.json)
│   ├── swagger_config.py    # OpenAPI 3.0 specification & Swagger UI configuration
│   └── logging_config.py    # Structured JSON logging initialization
├── CLI/                    # Standalone Command-Line Interface tool
├── tests/                  # Automated pytest suite (unit, mocked services, integration tests)
├── load-tests/             # k6 load performance scripts (smoke, load, stress, spike)
├── docs/                   # Technical documentation
│   ├── PERFORMANCE.md       # Benchmarks, load-testing methodology & bottleneck analysis
│   ├── DEPLOYMENT.md        # Production deployment guide (Render + Supabase + Upstash)
│   ├── API.md                # API reference
│   └── architecture.svg     # High-level architecture diagram
├── alembic/                # Database migration scripts and environment config
├── schemas.py              # Marshmallow input validation and output serialization schemas
├── services.py              # Shared business logic, external API integration & IP fallback chain
├── cache.py                # Redis caching layer (TTL execution & graceful fallback)
├── models.py                # SQLAlchemy ORM models
├── config.py                # Centralized environment-based settings (`.env`)
└── docker-compose.yml       # Orchestration for App, CLI, PostgreSQL, and Redis containers
```

---

## 4. Component Responsibilities

### 🔹 Web Layer (`WEB/`)
- **`app.py`**: The application entry point. Registers `flask-talisman` (secure headers), `PrometheusMetrics` (`/metrics`), and `Flask-Limiter` (rate limiting, currently applied to the `/` route only). Handles the server-rendered web UI (`/`) and the DB-connectivity readiness check (`/health`).
- **`api_routes.py`**: A separate Flask Blueprint (`api_bp`) exposing the JSON REST API — `/api/weather`, `/api/ping`, `/api/apispec.json`. These routes are **not** currently covered by the rate limiter registered in `app.py`.
- **`swagger_config.py`**: Exposes interactive API documentation at `/apidocs` and the JSON specification at `/api/apispec.json`.
- **`logging_config.py`**: Enforces structured JSON formatted logs across the application context for machine-readable log parsing.

### 🔹 Core Domain Services (`services.py`, `schemas.py`)
- **`services.py`**:
  - Encapsulates weather requests via [WeatherAPI](https://www.weatherapi.com/).
  - Executes **IP Geolocation Fallback Chain**: Attempts detection via `ip-api.com` first; if unavailable, falls back to `ipinfo.io`.
  - Executes **Automated Data Rotation**: Triggered probabilistically (1% chance on web traffic) to execute a lightweight `clear()` operation on stored logs/records to remain within PostgreSQL tier storage constraints.
- **`schemas.py`**: Strictly validates incoming query parameters (e.g., city names) and standardizes API output formats using Marshmallow.

### 🔹 Data & Caching Engine (`models.py`, `cache.py`, `alembic/`)
- **`models.py`**: Defines database tables (request history records) managed via SQLAlchemy, with `pool_size=10, max_overflow=20` configured on the engine (raised from SQLAlchemy's defaults during load testing — see [`PERFORMANCE.md`](PERFORMANCE.md)).
- **`cache.py`**:
  - Implements key-value operations against Redis with a default 5-minute Time-To-Live (`REDIS_TTL`).
  - Implements **Graceful Degradation**: Catches Redis connectivity errors automatically, ensuring the app proceeds to fetch data directly from upstream sources without breaking client execution.
- **`alembic/`**: Maintains database schema version control.

---

## 5. System Execution & Data Flow

There are two distinct request paths that write different amounts of data — this distinction matters when interpreting load-test results (see [`PERFORMANCE.md`](PERFORMANCE.md)):

### Web UI (`/`) — writes a request record on every call

```text
 Client (browser, form POST/GET)
        │
        ▼
   [ WEB Layer: app.py ] ───(Rate Limiter: 25/min per IP, Security Headers)
        │
        ▼
 [ Validation Layer ] ───(Marshmallow Validation in schemas.py)
        │
        ▼
  [ Service Layer ] (services.py → WeatherService.get_weather)
        │
        ├───────────────────────────────┐
        ▼                               ▼
 [ Redis Cache Check ]        [ Cache Miss / Bypass ]
(cache.py with 5m TTL)                 │
        │                               ▼
        ├─ (Hit) ────────► [ Fetch External API Data ]
        │                  (WeatherAPI / IP Fallback Chain)
        │                               │
        │                               ▼
        │                  [ Cache the fresh response in Redis ]
        │                               │
        ▼                               ▼
        └──────────────► [ Write a WeatherRequest row to PostgreSQL ]
                                        │
                                        ▼
                             [ Render HTML template ]
```

### JSON API (`/api/weather`) — no database writes

```text
 Client (API consumer)
        │
        ▼
 [ WEB Layer: api_routes.py ] ───(no rate limiter, no DB session opened)
        │
        ▼
 [ Validation Layer ] ───(Marshmallow Validation in schemas.py)
        │
        ▼
  [ Service Layer ] (services.py → WeatherService.get_weather)
        │
        ├─ (Cache hit) ──────────► [ Return cached JSON ]
        │
        └─ (Cache miss) ─► [ Fetch External API Data ] ─► [ Cache in Redis ] ─► [ Return JSON ]
```

---

## 6. Infrastructure, Observability & Cloud Deployment

1. **Gunicorn + Gevent Stack**:
   In production, Gunicorn uses `gevent` workers (`-w 8 --worker-class gevent --worker-connections 50`) alongside `psycogreen`, which patches `psycopg2` for non-blocking PostgreSQL I/O under gevent. This was adopted after load testing showed Gunicorn's default `sync` workers dropping connections under concurrent load — see [`PERFORMANCE.md`](PERFORMANCE.md) for the full investigation and before/after numbers.
2. **Cold-Start & Database Connection Optimization**:
   - Hosted on Render (App) + Supabase (PostgreSQL) + Upstash (Redis). Full setup steps in [`DEPLOYMENT.md`](DEPLOYMENT.md).
   - An external automated worker (**UptimeRobot**) sends an HTTP GET request to `/api/ping` every 10 minutes.
   - `/api/ping` bypasses the database completely, keeping the web container warm while preserving Supabase's limited free-tier connection pool.
3. **Observability**:
   - `/metrics`: Exposes real-time application metrics formatted for **Prometheus**.
   - `/health`: Readiness check verifying database connectivity, used by Docker Compose's `service_healthy` condition.
   - Structured JSON logging facilitates monitoring and diagnostic ingestion.
4. **Automated CI/CD Pipeline**:
   - **GitHub Actions** enforces code quality checks (Ruff, Mypy) and executes the full `pytest` suite before triggering deploy webhooks to production.
