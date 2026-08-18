# Weatherender

Production-grade weather application with a Flask web interface and CLI tool, built as a portfolio project demonstrating real-world engineering practices, has been developed by Alex Lyapin. The application provides current weather information, a 3-day forecast, and a unique Snow Surface Condition Index (SSCI) for skiers and outdoor enthusiasts.

![CI](https://github.com/LyapinAlexey/Weatherender/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)
[![codecov](https://codecov.io/github/LyapinAlexey/Weatherender/graph/badge.svg?token=VIAZVWQ81B)](
  https://codecov.io/github/LyapinAlexey/Weatherender
)

## 🌐 Live Demo

**[weather-7icc.onrender.com](https://weather-7icc.onrender.com)**

> ⚡ **Infrastructure Note:** Hosted on the Render free tier. To bypass the default 15-minute spin-down restriction, the application is kept active via a dedicated background automated worker ([UptimeRobot](https://uptimerobot.com/)) targeting the lightweight database-free `/api/ping` endpoint every 10 minutes.

### Availability and Known Limitations:
* **Cold Starts:** Despite the cron-ping system, occasional "cold starts" (30–50s delays) may still occur due to Render's internal container recycling or rare service interruptions.
* **Database Pauses:** The production storage operates on a free Supabase instance. If the database receives absolutely no client traffic for 7+ consecutive days, Supabase will automatically pause the project. If this occurs, feel free to open an issue to request a manual wake-up.

Stack in production: Render (app) + Supabase (PostgreSQL) + Upstash (Redis).


## Features

- 🌦 Current weather + 3-day forecast via [WeatherAPI](https://www.weatherapi.com/)
- Advanced Snow Surface Condition Index(SSCI): A *unique* algorithmic snow condition and quality detection system (featuring statuses like *Dry champagne powder!*, *Ice crust*, *Spring slush*, *Wind slab*, etc.). The analysis evaluates diurnal temperature cycles, wind speed, snow density, and 24-hour precipitation metrics.
- 🖥 Web interface (Flask) and CLI tool, sharing a common service/model layer
- 📍 Automatic city detection by IP (with fallback chain: ip-api.com → ipinfo.io)
- 🗄 PostgreSQL persistence via SQLAlchemy + Alembic migrations
- 🧹 Automated probabilistic storage rotation (`clear()` triggered on 1% of web requests) to safely stay within DB storage limits
- ✅ Input validation with Marshmallow
- 🚦 Rate limiting (flask-limiter)
- 🐳 Fully containerized with Docker Compose
- 🔄 CI pipeline via GitHub Actions (build, migrate, health check)
- 🧪 73+ automated tests (pytest): unit, mocked service, Flask route, and real PostgreSQL integration tests
- 🔌 JSON REST API (`/api/weather`) with interactive Swagger/OpenAPI docs
- ⚡ Redis caching for WeatherAPI responses (TTL-based, graceful fallback on Redis unavailability)
- 📊 Prometheus metrics endpoint (`/metrics`) for observability
- ❤️ Readiness health check (`/health`) with Docker/Compose integration
- 🔒 Security hardening: secure headers (Talisman), request size limits, User-Agent validation
- 📝 Structured JSON logging
- 🚀 Load-tested with [k6](https://k6.io/) (smoke, load, stress, spike) — see [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)
- ☁️ Production Cloud Deployment: Hosted on Render, integrated with Supabase (PostgreSQL) and Upstash (Redis), featuring an automated heartbeat worker ([UptimeRobot](https://uptimerobot.com/)) to maintain 24/7 web service availability

### Tech Stack

- **Backend:** `Python 3.13`, `Flask`, `Gunicorn` (gevent workers + `psycogreen`), `SQLAlchemy`, `Alembic`, `Marshmallow`, `Flask-Limiter`
- **Database:** `PostgreSQL`
- **Infrastructure & DevOps:** `Docker`, `Docker Compose`, `GitHub Actions (CI/CD)`
- **Testing & Quality:** `Pytest`, `unittest.mock`, `Codecov`
- **API & Docs:** `apispec`, `flask-swagger-ui` (OpenAPI/Swagger)
- **Observability:** `prometheus-flask-exporter`, structured JSON logging
- **Security:** `flask-talisman`
- **Caching:** `Redis`, `redis-py`

## Quick Start (Docker)

> Prefer not to run it locally? Try the [live demo](#-live-demo) above.

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
- [ ] **Asynchronous API v2 (FastAPI Migration):** Design a high-performance `api/v2` microservice using **FastAPI** and asynchronous drivers (`asyncio`, `asyncpg`) to dramatically increase request throughput and study async patterns
- [ ] **User Authentication & Custom Alerts:** Implement secure JWT or session-based user authentication via Supabase Auth, allowing skiers to save favorite resorts and customize automated notification limits

### Project Stability
The application is currently in a fully stable, containerized, and production-grade state. It will remain active and autonomously maintained in the cloud.

## Project Structure & Architecture

Three top-level pieces share a common core: `WEB/` (Flask app + JSON API), `CLI/` (command-line tool), and shared modules (`services.py`, `models.py`, `cache.py`, `config.py`, `schemas.py`). Full breakdown, component responsibilities, and request/data flow diagrams: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

![Project architecture](docs/architecture.svg)

---

## About the Author

```text
It's been developing since I was 13 years old.
```

I'm an active alpine skier (currently holding the 2nd adult sports rank and training for the 1st) and a full-time student at **Gymnasium 1514**. Due to intensive academic tracking and a demanding winter training schedule on the ski slopes, my development velocity temporarily transitions into a maintenance phase during the winter season — full-scale feature development resumes during the next summer cycle.

I also write about the engineering side of this project on my [Habr profile](https://habr.com/en/users/LyapinAlexey/).

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
  <a href="mailto:lehacomp16@gmail.com">
    <img src="https://img.shields.io/badge/EMAIL-lehacomp16@gmail.com-red?style=for-the-badge&logo=gmail" />
  </a>
  <a href="https://t.me/LyapinAlexey">
    <img src="https://img.shields.io/badge/TELEGRAM-@LyapinAlexey-blue?style=for-the-badge&logo=telegram" />
  </a>
  <a href="https://wa.me/">
    <img src="https://img.shields.io/badge/WHATSAPP-@LyapinAlex-green?style=for-the-badge&logo=whatsapp" />
  </a>
</p>
