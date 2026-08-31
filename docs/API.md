# API Reference

Weatherender exposes a dual-stack JSON REST API alongside its server-rendered web UI:
- **FastAPI (v2 Async API):** Interactive Swagger UI is available at `/v2/docs` (or ReDoc at `/v2/redoc`).
- **Flask (v1 Sync API):** Interactive Swagger UI (OpenAPI 3.0) is available at `/apidocs`.

Base URL (production): `https://weather-7icc.onrender.com`

---

## Endpoints

| Endpoint | Method | Engine | Auth | Description |
| :--- | :--- | :--- | :--- | :--- |
| `/api/v2/weather` | `GET` | FastAPI | None | High-performance Async API v2 with Pydantic v2 validation |
| `/api/v2/health` | `GET` | FastAPI | None | Async DB health check (`AsyncSessionLocal`) |
| `/v2/docs` | `GET` | FastAPI | None | Interactive FastAPI OpenAPI/Swagger documentation |
| `/v2/redoc` | `GET` | FastAPI | None | Alternative FastAPI ReDoc documentation |
| `/v2/openapi.json` | `GET` | FastAPI | None | Raw OpenAPI specification for v2 |
| `/api/weather` | `GET` | Flask | None | Legacy sync API v1 (`?city=Berlin`) with Marshmallow validation |
| `/api/apispec.json` | `GET` | Flask | None | Raw OpenAPI 3.0 specification for v1 |
| `/health` | `GET` | Flask | None | Sync readiness check (verifies DB connectivity) |
| `/metrics` | `GET` | Flask | None | Prometheus metrics |
| `/api/ping` | `GET\|HEAD` | Flask | None | Lightweight liveness check (no DB connection) |
| `/apidocs` | `GET` | Flask | None | Interactive Swagger UI for v1 |

---

### `GET /api/v2/weather`

High-performance asynchronous endpoint powered by **FastAPI**, **Pydantic v2**, and `httpx`.

**Query parameters**

| Param | Type | Required | Notes |
| :--- | :--- | :--- | :--- |
| `city` | string | yes | 1–100 characters, validated via Pydantic v2 (`Annotated[WeatherQueryParams, Query()]`). Strips whitespace and rejects blank/whitespace-only input. |

**Example**
```bash
curl "https://weather-7icc.onrender.com/api/v2/weather?city=Berlin"
```

**Responses**

| Status | Meaning |
| :--- | :--- |
| `200` | Success — weather payload returned asynchronously |
| `422` | Unprocessable Entity — missing, empty, or invalid `city` parameter |
| `404` | City not found by the upstream weather provider |
| `429` | Too Many Requests — rate limit exceeded (25 req/min per worker) |
| `500` | Internal server error during upstream API processing |

**Caching:** Responses are cached in Redis for `REDIS_TTL` seconds (default 300) via `AsyncRedisCache`. If Redis is unavailable, the endpoint transparently falls back to a live async fetch via `httpx.AsyncClient`.

### Response Schema (`200 OK`)

API v2 uses a hybrid Pydantic v2 response model (`WeatherResponseV2`). External WeatherAPI payload blocks (`location`, `current`, `forecast`) pass through dynamically, while Weatherender-specific derived fields are strictly validated:

```json
{
  "location": { ... },
  "current": { ... },
  "forecast": { ... },
  "snow_state": {
    "status": "Powder / Excellent Snow"
  },
  "snow_forecast": [
    {
      "date": "2026-08-27",
      "snow_state": {
        "status": "Packed / Hardpack"
      }
    }
  ]
}
```

---

### `GET /api/v2/health`

Async readiness probe used to verify database connectivity for FastAPI routes via `AsyncSessionLocal` (`SELECT 1`).

| Status | Body |
| :--- | :--- |
| `200` | `{"status": "ok"}` |
| `503` | `{"status": "error", "detail": "503 Service Unavailable"}` |

---

### `GET /api/weather`

Returns current conditions and a 3-day forecast for a given city via the legacy synchronous **Flask** pipeline.

**Query parameters**

| Param | Type | Required | Notes |
| :--- | :--- | :--- | :--- |
| `city` | string | yes | 1–100 characters, validated via a Marshmallow schema |

**Example**
```bash
curl "https://weather-7icc.onrender.com/api/weather?city=Berlin"
```

**Responses**

| Status | Meaning |
| :--- | :--- |
| `200` | Success — weather payload returned |
| `400` | Missing or invalid `city` parameter |
| `404` | City not found by the upstream weather provider, or an upstream error occurred |

Rate limited to 25 requests/minute per IP per worker via `flask-limiter`. See [Rate Limiting](#rate-limiting) below.

**Caching:** Responses are cached in Redis for `REDIS_TTL` seconds (default 300). If Redis is unavailable, it gracefully falls back to a live fetch.

---

### `GET /health`

Synchronous readiness probe used by Docker Compose (`depends_on: condition: service_healthy`) and external monitors. Executes `SELECT 1` against the database via SQLAlchemy sync session.

| Status | Body |
| :--- | :--- |
| `200` | `{"status": "ok"}` |
| `503` | `{"status": "error", "detail": "503 Service Unavailable"}` |

---

### `GET / HEAD /api/ping`

A minimal liveness endpoint (defined in `api_routes.py` under the `api_bp` blueprint) that does **not** open a database session. Exists specifically so external monitors (UptimeRobot) can keep the Render instance warm without consuming Supabase's limited free-tier connection pool. Accepts `HEAD` requests and bypasses `User-Agent` verification checks.

| Status | Body |
| :--- | :--- |
| `200` | `{"status": "ok"}` |

---

### `GET /metrics`

Exposes application metrics in Prometheus text-exposition format via `prometheus-flask-exporter` — request counts, latencies, and status-code breakdowns by endpoint.

---

### `GET /api/apispec.json`

Returns the raw OpenAPI 3.0 spec generated by `apispec` for Flask v1 routes, which powers `/apidocs`.

---

## Rate Limiting

- **v1 API (`/api/weather`)**: Limiting is handled via `flask-limiter`.
- **v2 API (`/api/v2/weather`)**: Limiting is handled via `slowapi` (`Limiter(key_func=get_remote_address)`). Enforces **25 requests per minute per IP** on the weather endpoint only (`/api/v2/health` is unthrottled).

> **Note on Multi-Worker Architecture:**
> Rate limiting for both engines uses in-memory tracking per process. When running in multi-worker configurations (e.g. `uvicorn --workers 4`), each worker maintains its own isolated counter. As a result, requests distributed across workers yield an effective client limit of up to `limit × workers` (~100 requests/min total for 4 workers) rather than a strict global 25.

Health checks (`/health`, `/api/ping`, `/api/v2/health`) and documentation endpoints (`/v2/docs`, `/v2/redoc`, `/apidocs`) explicitly bypass rate limiting.

Where a limit applies, exceeding it returns `429 Too Many Requests`.

---

## Error Format

Error response formats depend on the endpoint engine:

### 1. FastAPI v2 Validation Errors (`422 Unprocessable Entity`)
Follows standard FastAPI/Pydantic v2 JSON structure:
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["query", "city"],
      "msg": "Value error, city must not be blank or whitespace-only",
      "input": "   "
    }
  ]
}
```

### 2. Flask v1 Validation Errors (`400 Bad Request`)
Marshmallow validation returns a field-keyed structure:
```json
{
  "error": {
    "city": ["Length must be between 1 and 100."]
  }
}
```

### 3. Upstream / Business Errors (`404 Not Found`)
Returned when a city is not found by WeatherAPI:
```json
{
  "error": {
    "message": "City 'Nowhereville' not found."
  }
}
```

### 4. Rate Limit Exceeded (`429 Too Many Requests`)
Returned by `slowapi` on `/api/v2/weather` when a client exceeds the per-minute request limit.
```json
{
  "error": "Rate limit exceeded: 25 per 1 minute"
}
```

---

## Resilience & Retries (Tenacity)

Both engines incorporate automatic exponential backoff retries via `tenacity` for resilience against upstream WeatherAPI network timeouts and transient errors:
- **v1 Flask (Sync):** Uses synchronous `@retry` logic wrapping upstream `requests` calls with exponential backoff.
- **v2 FastAPI (Async):** Uses asynchronous `@retry` logic wrapping `httpx.AsyncClient` calls without blocking the async event loop.

---

## Interactive Docs

Try live API calls and inspect schemas via:
* **FastAPI v2 Swagger UI:** [weather-7icc.onrender.com/v2/docs](https://weather-7icc.onrender.com/v2/docs)
* **Flask v1 Swagger UI:** [weather-7icc.onrender.com/apidocs](https://weather-7icc.onrender.com/apidocs)
