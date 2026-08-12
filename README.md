# Weathernetic

```text
It's been developing since I was 13 years old.
```
Production-grade weather application with a Flask web interface and CLI tool, built as a portfolio project demonstrating real-world engineering practices.

![CI](https://github.com/LyapinAlexey/Weather/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)
[![codecov](https://codecov.io/github/LyapinAlexey/Weather/graph/badge.svg?token=VIAZVWQ81B)](
  https://codecov.io/github/LyapinAlexey/Weather
)

## 🌐 Live Demo

**[weather-7icc.onrender.com](https://weather-7icc.onrender.com)**

> Hosted on Render free tier — spins down after 15 min of inactivity, so the first request may take 30–50s to wake up.

Stack in production: Render (app) + Supabase (PostgreSQL) + Upstash (Redis).

## Features

- 🌦 Current weather + 3-day forecast via [WeatherAPI](https://www.weatherapi.com/)
- 🖥 Web interface (Flask) and CLI tool, sharing a common service/model layer
- 📍 Automatic city detection by IP (with fallback chain: ip-api.com → ipinfo.io)
- 🗄 PostgreSQL persistence via SQLAlchemy + Alembic migrations
- ✅ Input validation with Marshmallow
- 🚦 Rate limiting (flask-limiter)
- 🐳 Fully containerized with Docker Compose
- 🔄 CI pipeline via GitHub Actions (build, migrate, health check)
- 🧪 58+ automated tests (pytest): unit, mocked service, Flask route, and real PostgreSQL integration tests
- 🔌 JSON REST API (`/api/weather`) with interactive Swagger/OpenAPI docs
- ⚡ Redis caching for WeatherAPI responses (TTL-based, graceful fallback on Redis unavailability)
- 📊 Prometheus metrics endpoint (`/metrics`) for observability
- ❤️ Readiness health check (`/health`) with Docker/Compose integration
- 🔒 Security hardening: secure headers (Talisman), request size limits, User-Agent validation
- 📝 Structured JSON logging

### Tech Stack

- **Backend:** `Python 3.13`, `Flask`, `Gunicorn`, `SQLAlchemy`, `Alembic`, `Marshmallow`, `Flask-Limiter`
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

Interactive API documentation (Swagger UI) is available at:
```url
http://localhost:5001/apidocs
```
> `/api/weather` responses are cached in Redis for 5 minutes (configurable via `REDIS_TTL`). If Redis is unavailable, the app falls back to fetching fresh data from WeatherAPI directly.

## Running Tests

Tests require a dedicated PostgreSQL test container (kept separate from the dev/prod database):

```bash
docker compose up -d weather_test_db
DATABASE_URL="postgresql://test_user:test_password@localhost:5433/test_weather_db" alembic upgrade head
pytest -v
```
Note: `test_cache.py` mocks the Redis client directly and does not require a running Redis instance.

## Project Structure
```text
Weather/
├── WEB/ # Flask web app
|   ├── api_routes.py    # JSON API routes (/api/weather, /api/apispec.json)
│   ├── swagger_config.py # OpenAPI spec configuration
│   └── logging_config.py # Structured JSON logging setup
├── CLI/ # CLI tool
├── tests/ # pytest suite
├── alembic/ # DB migrations
├── schemas.py # Marshmallow validation
├── services.py # Shared weather/geo service layer
├── cache.py # Redis caching layer (get/set with TTL, graceful fallback)
├── models.py # SQLAlchemy models
├── config.py # Env-based configuration
└── docker-compose.yml
```

## Project architecture

![Project architecture](docs/architecture.svg)
