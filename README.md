<img src="https://avatars.githubusercontent.com/u/323290598?s=100&v=4" align="left" width="70" style="margin-right: 15px;">

# Weatherender Foundation

Production-grade weather intelligence for skiers.
# Weatherender

Production-grade weather application with a Flask web interface, a CLI tool, and a high-performance async FastAPI v2 API, built as a portfolio project demonstrating real-world engineering practices, has been developed by Alexey Lyapin.

![CI](https://github.com/LyapinAlexey/Weatherender/actions/workflows/ci.yml/badge.svg)
[![Release](https://img.shields.io/github/v/release/LyapinAlexey/Weatherender?logo=python&logoColor=306998&link=https%3A%2F%2Fgithub.com%2FLyapinAlexey%2FWeatherender%2Freleases%2Flatest)](https://github.com/LyapinAlexey/Weatherender/releases/latest)
[![Codecov](https://codecov.io/github/LyapinAlexey/Weatherender/graph/badge.svg?token=VIAZVWQ81B)](https://codecov.io/github/LyapinAlexey/Weatherender)
![Lines of Code](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FLyapinAlexey%2FWeatherender%2Fmain%2F.github%2Fbadge.json)
![License](https://img.shields.io/badge/SSCI-Custom_License-green) <br>
![Python](https://img.shields.io/badge/python-3.13-blue?logo=python&logoColor=306998)
![Flask](https://img.shields.io/badge/Flask-Framework-000000?logo=flask&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Container-2496ED?logo=docker&logoColor=white)

## 🌐 Live Demo

> The application is currently in a fully stable, containerized, and production-grade state. It will remain active and autonomously maintained in the cloud.

**[weather-7icc.onrender.com](https://weather-7icc.onrender.com)**

> ⚡ **Infrastructure Note:** Hosted on the Render free tier. To bypass the default 15-minute spin-down restriction, the application is kept active via a dedicated background automated worker ([UptimeRobot](https://uptimerobot.com/)) targeting the lightweight database-free `/api/ping` endpoint every 10 minutes.

### Availability and Known Limitations:
* **Cold Starts:** Despite the cron-ping system, occasional "cold starts" (30–50s delays) may still occur due to Render's internal container recycling or rare service interruptions.
* **Database Pauses:** The production storage operates on a free Supabase instance. If the database receives absolutely no client traffic for 7+ consecutive days, Supabase will automatically pause the project. If this occurs, feel free to open an issue to request a manual wake-up.

Stack in production: Render (app) + Supabase (PostgreSQL) + Upstash (Redis).


## Features

- 🌦 Current weather + 3-day forecast via [WeatherAPI](https://www.weatherapi.com/)
- ❄️ Advanced Snow Surface Condition Index(SSCI): A *unique* algorithmic snow condition and quality detection system (featuring statuses like *Dry champagne powder!*, *Ice crust*, *Spring slush*, *Wind slab*, etc.). The analysis evaluates diurnal temperature cycles, wind speed, snow density, and 24-hour precipitation metrics.
- 🖥 Web interface (Flask) and CLI tool, sharing a common service/model layer
- 📍 Automatic city detection by IP (with fallback chain: ip-api.com → ipinfo.io)
- 🗄 PostgreSQL persistence via SQLAlchemy + Alembic migrations
- 🧹 Automated DB cleanup: Background storage rotation powered by `APScheduler` (running weekly with a file-lock mechanism to prevent duplicate worker triggers) to safely stay within DB limits.
- ✅ Input validation with Marshmallow (sync) and pydantic v2 (async)
- 🛡️ Resilience & Retries (`tenacity`): Exponential backoff wrapper for upstream WeatherAPI calls (synchronous for v1 Flask `requests`, asynchronous non-blocking for v2 FastAPI `httpx`).
- 🚦 Rate Limiting & Protection: Granular per-worker rate limiting (`flask-limiter` for v1, `slowapi` for v2), confirmed experimentally via `scripts/check_limit.sh` (400 sequential requests, graceful `429 Too Many Requests` degradation beyond the quota).
- 🐳 Fully containerized with Docker Compose
- 🔄 CI pipeline via GitHub Actions (build, migrate, health check)
- 🧪 119+ automated tests (pytest): unit, mocked service, Flask route, and real PostgreSQL integration tests
- 🔌 JSON REST API (`/api/weather`) with interactive Swagger/OpenAPI docs
- ⚡ Redis caching for WeatherAPI responses (TTL-based, graceful fallback on Redis unavailability)
- 📊 Prometheus metrics endpoint (`/metrics`) for observability
- ❤️ Readiness health check (`/health`) with Docker/Compose integration
- 🔒 Security hardening: secure headers (Talisman), request size limits, User-Agent validation
- 📝 Structured JSON logging
- 🚀 Load-tested with [k6](https://k6.io/) (smoke, load, stress, spike) — see [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)
- ☁️ Production Cloud Deployment: Hosted on Render, integrated with Supabase (PostgreSQL) and Upstash (Redis), featuring an automated heartbeat worker ([UptimeRobot](https://uptimerobot.com/)) to maintain 24/7 web service availability

### Tech Stack

- **Backend:** `Python 3.13`, `FastAPI (ASGI core)`, `Flask WSGI via WSGIMiddleware`, `Uvicorn`, `Gunicorn (gevent workers)`, `SQLAlchemy (sync/async)`, `Alembic`, `Marshmallow`, `Pydantic v2`, `Flask-Limiter`, `SlowAPI`, `Tenacity`
- **Database:** `PostgreSQL`
- **Infrastructure & DevOps:** `Docker`, `Docker Compose`, `GitHub Actions (CI/CD)`, `APScheduler (for db clear)`
- **Testing & Quality:** `Pytest`, `unittest.mock`, `Codecov`, `k6 (smoke, load, stress, spike)`
- **API & Docs:** `FastAPI Auto Docs (Swagger/ReDoc)`, `apispec`, `flask-swagger-ui (OpenAPI 3.0)`
- **Observability:** `prometheus-flask-exporter`, `structured JSON logging`
- **Security:** `flask-talisman`
- **Caching:** `Redis`, `redis-py`

## Quick Start (Docker)

> Prefer not to run it locally? Try the [live demo](https://weather-7icc.onrender.com) above.

1. Clone the repo and copy the environment template:
```bash
   cp .env.example .env
```
2. Fill in `.env` — at minimum you'll need a free API key from [weatherapi.com](https://www.weatherapi.com/) (`WEATHER_API_KEY`) and a `SECRET_KEY`:
```bash
   python -c "import secrets; print(secrets.token_hex(32))"
```

3. Start the stack:
```bash
   docker compose up -d
   docker compose run --rm cli alembic upgrade head
```
4. Open [http://localhost:5001](http://localhost:5001)

## Running the CLI

```bash
docker compose run --rm cli python main.py
```
## API

The app exposes a JSON REST API alongside the web UI.

| Endpoint             | Method | Description                                                |
|----------------------|--------|------------------------------------------------------------|
| `/api/v2/weather`	   | GET	  | High-performance Async API v2 with Pydantic validation (Rate limited: 25 req/min)     |
| `/api/v2/health`	   | GET	  | Async DB health check                                      |
| `/v2/redoc`          | GET	  | Alternative FastAPI ReDoc documentation                    |
| `/v2/docs`	         | GET	  | Interactive FastAPI OpenAPI/Swagger documentation          |
| `/api/weather`       | GET    | Get current weather + forecast for a city (`?city=Berlin`) |
| `/api/apispec.json`  | GET    | Raw OpenAPI 3.0 specification                              |
| `/health`            | GET    | Readiness check (verifies DB connectivity)                 |
| `/metrics`           | GET    | Prometheus metrics                                         |
| `/api/ping`          | GET    | Ping endpoint for uptime monitors (no DB connection)       |
| `/apidocs`           | GET    | Interactive Swagger/OpenAPI documentation                  |

> `/api/weather` responses are cached in Redis for 5 minutes (configurable via `REDIS_TTL`). If Redis is unavailable, the app falls back to fetching fresh data from WeatherAPI directly.

## Performance & Caching Strategy

To ensure high performance and minimize reliance on external services, the application implements a multi-layered caching and optimization architecture:

* **Redis Integration:** Weather data fetched from WeatherAPI is cached in an Upstash Redis instance with a 5-minute TTL (`REDIS_TTL`). Subsequent requests for the same city are served instantly from the cache, saving external API quotas
* **Graceful Degradation:** If the Redis instance becomes temporarily unavailable, the application automatically catches the exception and gracefully falls back to direct API fetching without disrupting the user experience
* **Database Efficiency:** The automated uptime monitor triggers a lightweight `/api/ping` route that does not open SQLAlchemy sessions or hit the database. This prevents creating redundant connections on the free Supabase tier, keeping the connection pool clean

## Performance Testing

The application has been load, stress, and spike tested with [k6](https://k6.io/) — both against the live Render deployment and locally via Docker Compose. Full methodology and results, including a real bottleneck investigation (sync → gevent Gunicorn workers), are documented in [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md). Scripts live in `load_tests/`.

### Running Load Tests Locally

k6 must be installed locally (it isn't bundled as a Docker Compose service). Smoke and load tests target the live Render deployment directly; stress and spike tests require the local stack running first.

#### 1. Smoke Test (Render — verify the live deployment is alive and stable)
```bash
k6 run load_tests/smoke.js
```
#### 2. Load Test (Render — realistic traffic across all endpoints)
```bash
k6 run load_tests/load.js
```

#### 3. Stress Test (local — find the system's breaking point) — [running locally](#quick-start-docker)
```bash
docker compose up -d
k6 run load_tests/stress.js
```
#### 4. Spike Test (local — validate resilience against sudden traffic bursts) — [running locally](#quick-start-docker)
```bash
docker compose up -d
k6 run load_tests/spike.js
```

## Further Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — component responsibilities, request/data flow, infrastructure
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — how the production deployment (Render + Supabase + Upstash) is set up and reproduced
- [`docs/API.md`](docs/API.md) — full API reference (endpoints, params, error formats, rate limiting)
- [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) — load-testing methodology and results
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md) — project history by date/theme

## Running Tests

Tests require a dedicated PostgreSQL test container (kept separate from the dev/prod database):

```bash
docker compose up -d weather_test_db
DATABASE_URL="postgresql://test_user:test_password@localhost:5433/test_weather_db" alembic upgrade head
pytest -v
```
Note: `test_cache.py` mocks the Redis client directly and does not require a running Redis instance.

## 🛠️ Engineering Standards & Git Flow

This repository strictly adheres to professional enterprise software development practices:
* **Feature Branching:** Every bug fix, optimization, and component expansion is developed in isolated branches (`feature/*`, `fix/*`) to ensure the `main` branch remains stable and deployable at all times
* **True Merging:** The project utilizes explicit Merge Commits via the `--no-ff` (No Fast-Forward) strategy to preserve a rich, readable, and non-linear history of architectural iterations
* **Conventional Commits:** Commit messages are heavily standardized using strict semantic prefixes (`feat:`, `fix:`, `docs:`, `refactor:`, `tests:`) to provide transparency in project growth and documentation maintenance
* **Issue-Driven Post-Mortems:** Real infrastructure incidents and complex bug fixes are rigorously documented in the repository's closed Issues as production post-mortems, tracking root cause analysis and technical resolutions
* **Automated CI/CD & Safe Deployment:** Completely automated integration via GitHub Actions. The workflow forces strict validation layers (Ruff linting, Mypy type-checking, and full Pytest execution) before triggering a production release. Automated deployment via Render Webhooks is strictly gated and will automatically block if any unit test or linting check fails, ensuring 100% production uptime and stability.

## Roadmap & Future Enhancements

The next major architectural evolution of **Weatherender** is fully planned:

- [ ] **Dynamic Radar Maps:** Integrate interactive precipitation radar and dynamic weather maps using GIS/Leaflet tools to visualize snow and rain fronts
- [x] **Asynchronous API v2 (FastAPI Integration):** Designed a high-performance `api/v2` microservice using **FastAPI** (`asyncio`, `asyncpg`, `httpx`, `Pydantic v2`) mounted alongside Flask via `WSGIMiddleware`
- [ ] **User Authentication & Custom Alerts:** Implement secure JWT or session-based user authentication via Supabase Auth, allowing skiers to save favorite resorts and customize automated notification limits

## Project Structure & Architecture

Two main web components share a common core: `WEB/` (Flask app + v1 JSON API) and `API/` (FastAPI async v2 service), combined into a single ASGI process via `WSGIMiddleware` in `API/main.py`. The repository also includes `CLI/` (command-line tool) and shared modules (`services.py`, `models.py`, `cache.py`, `config.py`, `schemas.py`, `snow.py`). Full breakdown, component responsibilities, and request/data flow diagrams: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

![Project architecture](docs/architecture.svg)

## Engineering Challenges & Bug Investigations

A full technical deep-dive into blockers, edge cases, and architectural updates can be tracked in closed [Project Issues](https://github.com/LyapinAlexey/Weatherender/issues). Key production-level engineering challenges solved during development include:

### 1. Database Pollution Mitigation & HTTP HEAD Short-Circuiting ([Issue #9](https://github.com))
* **The Incident (Post-Mortem):** Continuous 10-minute uptime checks from [UptimeRobot](https://uptimerobot.com) targeting the root route (`/`) were heavily polluting the operational logs and telemetry within the Supabase PostgreSQL storage layer, triggering unintended database writes and accumulating thousands of empty automated tracking rows.
* **Root Cause Analysis:** The external monitor was explicitly configured to use the `HTTP HEAD` method. However, because Flask by default implicitly converts unhandled `HEAD` requests to `GET` on routes without explicit declaration, the request bypassed custom `User-Agent` string filtering layers. This initiated a redundant `SessionLocal()` DB connection and triggered execution of an unpredictable insert query lifecycle on every health probe.
* **Engineering Solution & Shield:**
  1. Updated the internal `/api/ping` route configuration within `api_routes.py` to explicitly support both `GET` and `HEAD` methods to handle direct infrastructure probes natively.
  2. Overhauled the core index (`/`) route decorator in `app.py` by introducing explicit `HEAD` support (`methods=["GET", "POST", "HEAD"]`).
  3. Placed a high-priority, zero-cost early return check (`if request.method == "HEAD": return ""`) at the very first line of execution.
* **Results:** Database pollution was successfully brought down to **0%**, server resources were completely preserved, and database sessions are now never initialized for non-human monitoring traffic.

### 2. Flask-Limiter Blueprint Registry Mismatch & Circular Dependency Resolution ([Issue #10](https://github.com/LyapinAlexey/Weatherender/issues/10))
* **The Incident:** During pre-merge manual load testing using a custom `check_limit.sh` script (firing 400 sequential requests), the automated uptime monitor health checks against `/api/ping` consistently failed with `429 Too Many Requests`. The endpoint kept throttling traffic even though an explicit `limiter.exempt(ping)` rule was active in `app.py`.
* **Root Cause Analysis:** A deep-dive revealed a lifecycle mismatch in how `flask-limiter==4.1.1` registers routes. When applying a blueprint-wide limit (`api_bp`), the `@limiter.exempt` decorator failed because it looked up the bare function name, whereas Flask resolves the request's endpoint at dispatch time using the prefixed name (`api.ping`). Furthermore, attempting to apply decorators directly inside `api_routes.py` introduced immediate circular imports between `app.py` and the routing module.
* **Engineering Solution:**
  1. Broke the circular dependency chain by decoupling the `Limiter` instance instantiation, moving it into an uninitialized state inside a newly designed infrastructure layer: `WEB/extensions.py`.
  2. Late-bound the engine during the application factory setup in `app.py` via `limiter.init_app(app)`.
  3. Dropped the fragile blueprint-wide mapping logic entirely. Instead, explicitly declared per-route limits using `@limiter.limit("25 per minute")` directly on the protected production endpoints (`get_weather` and `get_apispec`), leaving the critical `/api/ping` route cleanly undecorated and inherently immune to rate-limiting blocks.
* **Results:** Re-running the 400-request load test confirmed 100% success on `/api/ping` (returning pure `200 OK` metrics alongside expected gevent network socket resets), while public endpoints correctly isolated and blocked aggressive traffic bursts.

---

## About the Author

```text
It's been developing since I was 13 years old.
```

I'm an active alpine skier (currently holding the 2nd adult sports rank and training for the 1st) and a full-time student at **Gymnasium 1514**. Due to intensive academic tracking and a demanding winter training schedule on the ski slopes, my development velocity temporarily transitions into a maintenance phase during the winter season — full-scale feature development resumes during the next summer cycle.

I also write about the engineering side of this project on my [Habr profile](https://habr.com/en/users/LyapinAlexey/).

---

## License

This project is licensed under the **SSCI Custom License v1.1**.

Non-commercial use is allowed with mandatory attribution.
Commercial use of any part of this project (including code, algorithms, formulas,
models, API, or documentation) is strictly prohibited without explicit written
permission from the author.

Full license text:
[SSCI Custom License v1.1](./LICENSE)

For commercial licensing inquiries, contact:

<p align="center">
  <a href="mailto:lehacomp16@gmail.com" style="display: inline-block; margin-bottom: 8px;">
    <img src="https://img.shields.io/badge/Email-lehacomp16%40gmail.com-blue?style=for-the-badge&logo=gmail&logoColor=white" height="32" alt="Email" />
  </a>
  <br>
  <a href="https://t.me/LyapinAlexey" style="display: inline-block;">
    <img src="https://img.shields.io/badge/Telegram-%40LyapinAlexey-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" height="32" alt="Telegram" />
  </a>
</p>
