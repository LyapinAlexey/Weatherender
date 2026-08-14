# Architecture and Project Structure

This document details the high-level architecture, design patterns, component interactions, and deployment structure of **Weatherrender** (also referred to as *Weathernetic*).

---

## 1. High-Level Architecture Overview

`Weatherrender` is a production-grade, containerized application providing both a RESTful Web Interface (Flask) and a Command Line Interface (CLI). It features external API integrations, multi-level fallback strategies, asynchronous production worker configurations, and real-time observability.

![Project Architecture](docs/architecture.svg)

### Key Architectural Characteristics:
- **Shared Core Services**: Both WEB and CLI interfaces leverage a unified business logic and data access layer.
- **Resilience & Fallback**: Automatic IP geolocation failover chain and graceful degradation when Redis caching is offline.
- **Production Performance**: Flask served via Gunicorn utilizing `gevent` standard workers with `psycogreen` patch for non-blocking asynchronous PostgreSQL network I/O.
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
Weather/
├── WEB/                   # Flask Web Application Layer
│   ├── api_routes.py      # REST endpoints (/api/weather, /health, /metrics, /api/ping, etc.)
│   ├── swagger_config.py  # OpenAPI 3.0 specification & Swagger UI configuration
│   └── logging_config.py  # Structured JSON logging initialization
├── CLI/                   # Standalone Command-Line Interface tool
├── tests/                 # Automated pytest suite (unit, mocked services, integration tests)
├── load-tests/            # k6 load performance scripts (smoke, load, stress, spike)
├── docs/                  # Technical documentation
│   ├── performance.md     # Benchmarks, load-testing methodology & bottleneck analysis
│   └── architecture.svg   # High-level architecture diagram
├── alembic/               # Database migration scripts and environment config
├── schemas.py             # Marshmallow input validation and output serialization schemas
├── services.py            # Shared business logic, external API integration & IP fallback chain
├── cache.py              # Redis caching layer (TTL execution & graceful fallback)
├── models.py             # SQLAlchemy ORM models
├── config.py             # Centralized environment-based settings (`.env`)
└── docker-compose.yml    # Orchestration for App, CLI, PostgreSQL, and Redis containers
```

---

## 4. Component Responsibilities

### 🔹 Web Layer (`WEB/`)
- **`api_routes.py`**: Handles incoming HTTP requests. Houses web endpoints, rate limits, CORS policies, security headers via Talisman, and integration with Prometheus exporters (`/metrics`).
- **`swagger_config.py`**: Exposes interactive API documentation at `/apidocs` and JSON specifications at `/api/apispec.json`.
- **`logging_config.py`**: Enforces structured JSON formatted logs across the application context for machine-readable log parsing.

### 🔹 Core Domain Services (`services.py`, `schemas.py`)
- **`services.py`**:
  - Encapsulates weather requests via [WeatherAPI](https://www.weatherapi.com/).
  - Executes **IP Geolocation Fallback Chain**: Attempts detection via `ip-api.com` first; if unavailable, falls back to `ipinfo.io`.
  - Executes **Automated Data Rotation**: Triggered probabilistically (1% chance on web traffic) to execute a lightweight `clear()` operation on stored logs/records to remain within PostgreSQL tier storage constraints.
- **`schemas.py`**: Strictly validates incoming query parameters (e.g., city names, coordinates) and standardizes API output formats using Marshmallow.

### 🔹 Data & Caching Engine (`models.py`, `cache.py`, `alembic/`)
- **`models.py`**: Defines database tables (queries, persistence records) managed via SQLAlchemy.
- **`cache.py`**:
  - Implements key-value operations against Redis with a default 5-minute Time-To-Live (`REDIS_TTL`).
  - Implements **Graceful Degradation**: Catches Redis connectivity errors automatically, ensuring the app proceeds to fetch data directly from upstream sources without breaking client execution.
- **`alembic/`**: Maintains database schema version control.

---

## 5. System Execution & Data Flow

```text
 Client / CLI Request
        │
        ▼
   [ WEB Layer ] ───(Rate Limiter / Security Check)
        │
        ▼
 [ Validation Layer ] ───(Marshmallow Validation in schemas.py)
        │
        ▼
  [ Service Layer ] (services.py)
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
        └──────────────► [ Write Back to Redis & DB ]
                                        │
                                        ▼
                             [ Format JSON Response ]
```

---

## 6. Infrastructure, Observability & Cloud Deployment

1. **Gunicorn + Gevent Async Stack**:
   In production, Gunicorn uses `gevent` workers alongside `psycogreen`. This patches Python's standard library socket calls and DB drivers to be non-blocking, maximizing concurrent throughput under async load.
2. **Cold-Start & Database Connection Optimization**:
   - Hosted on Render (App) + Supabase (PostgreSQL) + Upstash (Redis).
   - An external automated worker (**UptimeRobot**) sends an HTTP GET request to `/api/ping` every 10 minutes.
   - `/api/ping` bypasses the database completely, keeping the web container warm while preserving Supabase connection limits.
3. **Observability**:
   - `/metrics`: Exposes real-time application metrics formatted for **Prometheus**.
   - `/health`: Readiness check verifying database connectivity for Docker / Orchestration healthchecks.
   - Structured JSON logging facilitates monitoring and diagnostic ingestion.
4. **Automated CI/CD Pipeline**:
   - **GitHub Actions** enforces code quality checks (Ruff, Mypy) and executes full `pytest` suites before trigger-deploying webhooks to production environments.
