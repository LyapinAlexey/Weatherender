# Changelog

All notable changes to **Weatherender** (formerly *Weather*), organized by date and grouped by theme. Reconstructed directly from `git log`.

> Note: the repository's earliest history (24–30 June) contains a run of commits literally named `v1.0.0` through `v4.2.4` — an early, pre-conventional-commits naming habit rather than meaningful version releases. They're omitted below in favor of the descriptive commit messages from the same period, once a proper (`feat:`/`fix:`/`docs:`) commit style was adopted.

## 2026-08-26 — Async test suite and Mocking refactor for Weatherender
- Added: Comprehensive asynchronous unit and integration tests (`test_api_cache.py`, `test_api_services.py`) covering Redis caching operations and `httpx`-based asynchronous weather service endpoints.
- Refactored: Integrated **`respx`** for intercepting and mocking `httpx` requests in async services, matching the production-grade architecture of the FastAPI / Flask single-image deployment.
- Improved: Replaced legacy/synchronous mock definitions in service tests with fully compliant `AsyncMock` and parametrized test cases, pushing test coverage to **89%** across **120** passing test scenarios.

## 2026-08-26 — Async v2 load testing, pool starvation fix, WSGI adapter switch
- Added `load_tests/smoke_v2.js`, `load_tests/load_v2.js` (Render), and `load_tests/stress_v2.js`, `load_tests/spike_v2.js` (local) — k6 coverage for `/api/v2/*`, mirroring the existing v1 scripts' structure and stage timings (`health` + `weather` groups; no `ping`-equivalent exists for the async stack).
- Fixed `load_tests/load.js`: it was targeting `localhost:5001` instead of the live Render deployment, contradicting the documented strategy in `PERFORMANCE.md` — found while preparing the v2 k6 scripts.
- Found and partially fixed a real performance bug: `API/async_db.py`'s `create_async_engine` had no explicit `pool_size`/`max_overflow`, defaulting to SQLAlchemy's `5`/`10` — half the sync engine's configured `10`/`20` (`models.py`) — under equal or higher test concurrency. Matching the sync engine's pool settings cut spike-test max latency from 4.17s to 56.89ms (~73x) and modestly improved spike/stress error rates; load-test error rate on Render did not improve and needs repeat runs to rule out host-side noise before further conclusions. Full before/after data and remaining hypotheses (`httpx.AsyncClient` limits, Render variance) documented in `docs/PERFORMANCE.md`.
- Made `API/main.py`'s `httpx.AsyncClient` connection limits explicit (`max_connections=100, max_keepalive_connections=20`) to rule out the shared HTTP client as a contributing factor to the residual v2 error-rate gap — values match httpx's own defaults, so no behavior change is expected, but the limits are now documented in code rather than implicit.
- Switched `API/main.py`'s WSGI adapter from `fastapi.middleware.wsgi.WSGIMiddleware` to `a2wsgi.WSGIMiddleware` — a preference for a more actively maintained standalone package over FastAPI's own (increasingly deprecated) built-in WSGI bridge. Already present in `requirements.txt`.
- Updated `docs/PERFORMANCE.md` with a full "Async API v2 Testing" section: initial v1-vs-v2 comparison, root cause analysis, before/after pool-fix data, and an updated summary table covering both stacks.

## 2026-08-25 — Pydantic v2 validation for `/api/v2/weather` & Docker fix
- Added: `API/schemas.py` with a `WeatherQueryParams` Pydantic v2 model, replacing the bare `city: str = Query(...)` parameter with `Annotated[WeatherQueryParams, Query()]` — enforces `city` length (1–100 chars) via `Field(...)` plus a `field_validator` rejecting blank/whitespace-only input (stripped and re-validated).
- Added: test coverage in `tests/test_api_routes.py` for the new validation branches — blank city, whitespace-only city, and city over 100 characters (all `422`), alongside the pre-existing missing-city case.
- Fixed: `WEB/Dockerfile` was missing `COPY snow.py /app` after the earlier `get_snow_state` extraction refactor — caused gunicorn workers in the `web` container to crash with `ModuleNotFoundError` on `from snow import get_snow_state`. Verified both `web` and `api` containers start clean after the fix.
- Fixed: `API/main.py`'s `/favicon.ico` route referenced `WEB/static/images/favicon.ico` despite `API/Dockerfile` copying files flat — adjusted the `COPY` to bring the favicon into the flat `API/` image layout (also fixed a `.png`/`.ico` extension mismatch along the way).

## 2026-08-24 — `API/` test suite
- Added `tests/test_api_routes.py`: async test suite for `API/` using `httpx.AsyncClient` + `ASGITransport` + `pytest-asyncio` (explicit `@pytest.mark.asyncio`, STRICT mode).
- Added `api_client` fixture in `conftest.py`, wrapping app startup/shutdown via `app.router.lifespan_context(app)` so `lifespan`-managed state (`app.state.http_client`) is available in tests.
- Covered: `/api/v2/health` (DB ok / DB error → 503), `/api/v2/weather` (success with snow_state/snow_forecast, city-not-found → 404, missing city → 422, empty-forecast edge case).
- Mocking pattern for async SQLAlchemy sessions: `AsyncSessionLocal` patched as a plain `MagicMock` with `__aenter__`/`__aexit__` manually wired to an `AsyncMock` session (since `AsyncSessionLocal()` itself isn't awaited — only entering the `async with` block is).
- Fixed: Resolved `AttributeError` caused by cross-module import singleton conflicts in `AsyncCacheService`. Swapped explicit event-loop initialization in `lifespan` for a thread-safe, lazy-loaded initialization pattern (`_get_client`).
- Improved: Hardened cache data pipeline serialization safety by adding `default=str` helper within `json.dumps()` execution, safely coercing Pydantic dynamic objects and datetimes.
- Added: Mounted explicit `/favicon.ico` endpoint utilizing `FileResponse` to handle automatic browser icon lookups natively.
- Fixed: Corrected Docker image context build path for `favicon.png` targeting the web source asset directory (`WEB/static/images/favicon.png`) within `Dockerfile`.

## 2026-08-23 — DB writes, health check, Dockerization for `API/`
- Added DB write-on-request logging to `GET /api/weather` (sync) and `GET /api/v2/weather` (async), mirroring the existing pattern used by `/`. Both log `WeatherRequest` rows (success/error, `temp_c`/`condition` or `error_message`) with distinct `source` values (`"api"`, `"api-v2"`).
- Added `API/async_db.py`: a new async SQLAlchemy engine (`create_async_engine` + `async_sessionmaker`, `asyncpg` driver) local to `API/` only — derives `ASYNC_DATABASE_URL` from the existing `Config.DATABASE_URL` by swapping the driver scheme to `postgresql+asyncpg://`.
- Added `GET /api/v2/health`: async mirror of the sync `/health` endpoint, running a real `SELECT 1` through the new async engine.
- **Refactor**: extracted `get_snow_state` out of `WeatherService` into a new standalone module `snow.py` at the repo root — it's a pure function with no I/O, so it never needed to be a class method. This decouples snow calculations from `services.py`'s module-level `cache_service = CacheService()` singleton, letting `API/` use `get_snow_state` without pulling in the sync Redis client it doesn't need. All call sites (`WEB/app.py`, `WEB/api_routes.py`, `API/main.py`) and tests updated accordingly.
- Added `API/Dockerfile` (flat-copy style, matching `WEB/Dockerfile`) and a new `api` service in `docker-compose.yml`, mirroring `web`'s dependency structure (`weather_db`, `cache`, `migration`). Verified end-to-end via `docker-compose up --build`: `/api/v2/health` and `/api/v2/weather` both respond correctly through the Docker network.
- Added `asyncpg` to `requirements.txt`.

## 2026-08-22 — New async FastAPI service (`API/`)
- Added a new, fully separate third service (`API/`) alongside `WEB/` and `CLI/`, built on FastAPI + Uvicorn, sharing root-level `models.py`/`config.py`. `WEB/services.py` (sync, `requests`) stays completely untouched; `API/async_services.py` is a new, independent async mirror using `httpx.AsyncClient`.
- Implemented `GET /api/v2/weather`: mirrors the existing sync `/api/weather` contract exactly — `city` is a required query parameter, no IP auto-detection, no elevation lookup (deferred; not in scope for v1). Also returns `snow_state`/`snow_forecast` (added to `/api/weather` on 2026-08-21), reusing `WeatherService.get_snow_state` directly — pure function, no I/O, safe to call from async code as-is.
- `API/main.py`: FastAPI `lifespan` context manager creates a single `httpx.AsyncClient` at startup (stored in `app.state.http_client`) and closes it on shutdown, avoiding per-request client creation/TCP handshake overhead.
- `API/async_services.py`: `AsyncWeatherService.get_weather_async` — async mirror of `WeatherService.get_weather` (same cache-aside logic, same error handling for 401/403/400/non-JSON/network errors), using the shared `httpx.AsyncClient` passed in as a parameter.
- `API/async_cache.py`: `AsyncCacheService` — async mirror of `WEB/cache.py`'s `CacheService`, using `redis.asyncio` instead of sync `redis-py`.
- Added `API/__init__.py` and `CLI/__init__.py` (re-export pattern, matching `WEB/__init__.py`) to fix a `mypy` "Duplicate module named 'main'" conflict between `API/main.py` and `CLI/main.py`.
- Added `fastapi`, `uvicorn`, `httpx` to `requirements.txt`, reorganized the file into commented sections (WEB/Flask, API/FastAPI, shared HTTP/DB/caching/validation, scheduling, dev tooling).
- Verified end-to-end locally via `uvicorn API.main:app --reload` against the real WeatherAPI.
- **Not yet done** (tracked as follow-ups): `API/` test suite, `API/Dockerfile` + docker-compose integration, Pydantic v2 request/response schemas, DB write-on-request logging (planned for both `/api/weather` and `/api/v2/weather`, the latter requiring a new async SQLAlchemy engine).

## 2026-08-21 — Snow forecast in JSON API
- Extended `/api/weather` response with two derived fields built from `WeatherService.get_snow_state`: `snow_state` (today's snow conditions) and `snow_forecast` (per-day snow conditions across the returned forecast window), mirroring logic already used by the web UI (`/`).
- Added `tests/test_routes.py` coverage for both the populated-forecast case and the empty-forecast edge case (falls back to `{"status": "No snow data"}` and an empty `snow_forecast` list).
- Updated the `/api/weather` Swagger/OpenAPI description (`docs`/`/apidocs`) to document the new fields.

## 2026-08-18 — Periodic DB cleanup via APScheduler
- Replaced the probabilistic (0.01% per-request) call to `dbclear.clear()` in `app.py` with a deterministic scheduled job: new `WEB/scheduler.py` uses APScheduler's `BackgroundScheduler` to run cleanup every 7 days.
- Solved the multi-worker duplication problem (4 Gunicorn workers would otherwise each start their own scheduler) with a leader-election-via-lock-file pattern: workers race to atomically create `/tmp/scheduler_leader.lock` via `os.open(..., O_CREAT | O_EXCL | O_WRONLY)`; only the worker that wins runs the scheduler. Documented as a known limitation: a restarted leader worker won't reclaim leadership until the next container redeploy.
- `init_scheduler()` wired into `app.py`, called after `Config.validate()`.
- Added `tests/test_scheduler.py` (5 tests): lock-file acquisition (file absent/present), `run_dbclear_job` session handling, and `init_scheduler` branch coverage (leader vs. non-leader) via mocking.
- Updated `docs/ARCHITECTURE.md`: documented the new module and the leader-election design, removed the stale reference to probabilistic cleanup, corrected the outdated `-w 8` worker count to the actual `-w 4`.

## 2026-08-17 – Snow state calculation logic fix & unit tests

- Fixed a logic bug in `WeatherService.get_snow_state`: eliminated false-positive `Ice crust` statuses on bare ground during near-zero or positive temperatures by enforcing strict snow depth checks (`snow_depth_cm > 0` or `snow_24h_cm > 0`) and proper diurnal freeze-thaw evaluation (`max_temp_c > 0 and min_temp_c < 0`).
- Fully integrated previously unaccessed parameters and variables into the snow state decision tree: `min_temp_c`, `max_temp_c`, `wind_kph`, and the calculated `snow_density`.
- Added a comprehensive parameterized unit test suite in `tests/test_snow_state.py` covering all 11 distinct meteorological scenarios and branching paths, fully verified via `pytest`.
- Maintained clean code quality standards: all modifications successfully passed `mypy` type checking alongside `ruff` and `isort` pre-commit hooks.
- Updated `docs/API.md` and `docs/ARCHITECTURE.md` to match the code: removed the "not rate-limited" notes for `/api/weather`/`api_bp`, documented the actual per-route limits, the `WEB/extensions.py` module, and the `exempt()`-on-blueprint gotcha as a rate-limiting design note.

## 2026-08-17 — API rate limiting
- Closed the documented gap where `/api/weather` and the rest of the `api_bp` blueprint were not rate-limited: applied the same `flask-limiter` limit used on `/` (25 requests/minute per worker, in-memory) directly to `/api/weather` and `/api/apispec.json` via `@limiter.limit("25 per minute")`. `/api/ping` (liveness endpoint for uptime monitors) and `/health` remain unlimited.
- Along the way, moved `limiter = Limiter(...)` out of `app.py` into a new `WEB/extensions.py`, created without an app binding (`limiter.init_app(app)` called separately in `app.py`) — needed so `api_routes.py` could import `limiter` directly for the per-route decorators without a circular import back to `app.py`.
- Initially tried a single blueprint-wide `limiter.limit(...)(api_bp)` plus `limiter.exempt(ping)` to keep `/api/ping` unlimited — in practice `exempt()` didn't take effect on a blueprint-registered view in this `flask-limiter` version (4.1.1): `/api/ping` kept returning `429` under load even after the exempt call ran. Switched to per-route `@limiter.limit(...)` decorators on `get_weather` and `get_apispec` instead, leaving `ping` undecorated — more explicit and it actually works.
- Verified under load (400 sequential requests against 8 gevent workers): `/api/weather` split roughly evenly between `200` and `429` as expected; `/api/ping` returned `200` for effectively all 400 requests with no rate limiting.
- Correction: earlier docs referenced the `/` rate limit as 15/min — the actual code has always been **25/min per worker** (`25 per minute`, ×4 workers in production docs, ×8 workers in the local docker-compose setup which runs gevent with `-w 8`). Docs will be updated to reflect this.

## 2026-08-17 — Logging audit closed & config normalization test coverage
- Completed the logging-level audit (`logger.warning()` vs `logger.error()`/`.exception()`) across `app.py`, `api_routes.py`, `CLI/main.py`, and `services.py` — previously only 1-2 call sites had been reviewed.
- Added `tests/test_config.py` covering the `postgres://` → `postgresql://` normalization in `config.py`: legacy scheme gets rewritten, an already-correct `postgresql://` URL is left untouched (exact-match assertion, not just a prefix check), and the unset case correctly yields `None`.
- Along the way, worked out the correct pattern for testing module-level config computed at import time: `monkeypatch.setenv`/`delenv` plus `importlib.reload(sys.modules["config"])`, with an `autouse` fixture restoring the module to its real state after each test. Also had to patch `dotenv.load_dotenv` at its source (not the `config.load_dotenv` reference) — `reload` re-runs the `from dotenv import load_dotenv` line, which would otherwise silently re-fetch `DATABASE_URL` from `.env` and undo the `delenv`.

## 2026-08-14 — Documentation restructure & spike testing
- Added a spike test (`spike.js`) for sudden traffic bursts, completing the k6 test suite (smoke/load/stress/spike).
- Split documentation: removed the original `performance.md`, added dedicated `PERFORMANCE.md` and `ARCHITECTURE.md`, and added `SECURITY.md` + `CODE_OF_CONDUCT.md` for security policy and community standards.
- Updated README title and structure.

## 2026-08-13 — Gevent migration & load testing
- Investigated a load-testing bottleneck on Render (`connection reset by peer`, multi-second latency) and switched Gunicorn from `sync` to `gevent` workers (`--worker-class gevent --worker-connections 50`), with a follow-up fix pinning a working `psycogreen` version to patch `psycopg2` for gevent compatibility.
- Added `smoke.js` and `load.js` k6 scripts, then `stress.js` (local-only, health/ping/weather endpoints).
- Fixed IP-based city detection to correctly handle datacenter/cloud-provider IPs (e.g. Render's own outbound IP), defaulting to London instead of misidentifying the server as the user.
- Updated the CI/CD workflow to trigger Render deployment via a dedicated deploy action (iterated a few times to get the trigger step right).

## 2026-08-12 — Cloud deployment (Render + Supabase + Upstash)
- Deployed to Render for the first time: added `PORT` environment variable support to the Dockerfile, updated `HEALTHCHECK` and the Gunicorn command to use it (dynamic port binding).
- Added `/api/ping` — a lightweight, database-free liveness endpoint for uptime monitors, plus stronger `User-Agent` checks and an explicit bypass for the ping route so monitors without a `User-Agent` header aren't rejected.
- Added `HEAD` method support to the root route and ping endpoints for monitors that use `HEAD` requests.
- Documented the live deployment: infrastructure notes, availability/known limitations, and a live demo link in the README.
- Renamed the project.
- Added a roadmap, maintenance notice, and a "live engineering" section (git flow, commit conventions) to the README.

## 2026-08-11 — Redis config hardening & UI refactor
- Refactored Redis configuration to accept a single `REDIS_URL` (replacing separate host/port config) — required for Upstash's `rediss://` connection string format; updated tests accordingly.
- Fixed cache initialization to handle empty/placeholder/localhost Redis hosts gracefully.
- Refactored the weather app's HTML template to use server-side Jinja2 rendering, removing an earlier client-side JS-fetching approach (which had briefly replaced the original Jinja2 template).
- Added, then effectively abandoned, a `vercel.json` for potential Vercel deployment — the architecture (server-rendered Flask, not a separate frontend) doesn't fit Vercel's model.

## 2026-08-10 — Redis caching
- Added Redis caching for `WeatherService` responses (cache-aside pattern), with tests for cache hits.
- Fixed a Content-Security-Policy conflict that broke `/apidocs` (Swagger UI): added a custom `after_request` security-headers hook, registered before `Talisman(app, ...)` so it overrides Talisman's default CSP for Swagger's inline script — Flask runs `after_request` hooks in reverse registration order.
- Updated the architecture diagram and README with Redis caching details.

## 2026-08-01 — Documentation
- Updated the README with the project's development history.

## 2026-07-25 — Security & observability
- Added security hardening via `flask-talisman`.
- Added Prometheus metrics integration (`/metrics`).
- Updated the README and architecture diagram with API details.

## 2026-07-24 — JSON REST API
- Added `api_routes.py` with the `/api/weather` endpoint (and tests), plus an OpenAPI/Swagger-documented JSON REST API served at `/apidocs`.
- Refactored logging into a structured JSON format with clearer error handling.

## 2026-07-23 — Health checks & CI fixes
- Added health-check endpoints for both the web app and database connectivity, wired into CI.
- Fixed a CI healthcheck failure caused by environment variables being scoped incorrectly (moved to job level).
- Updated the project architecture diagram and README to reflect the new structure.

## 2026-07-20 – 2026-07-22 — Testing infrastructure & CI maturity
- Added `mypy` static type checking across the codebase.
- Added a `.gitignore` entry for cache directories.
- Built out the GitHub Actions CI workflow: PostgreSQL readiness checks, corrected pytest volume mounts and commands, `TEST_DATABASE_URL` wiring, improved coverage reporting, and a test for the automated DB-clearing job (`db_clear`).
- Added Codecov integration and badge.
- Added `pre-commit` configuration (and did a pass fixing imports/formatting across the whole codebase to match it).
- Added contributing guidelines and license information, and the initial project README with setup instructions and a CI badge.

## 2026-07-14 – 2026-07-19 — Test suite build-out
- Built the pytest suite incrementally: `CityRequestSchema` validation tests, `WeatherService.get_weather` tests (including error branches, network failures, and the `get_city_by_ip` fallback chain), Flask route tests with mocked dependencies, and integration tests against a dedicated test PostgreSQL container.
- Fixed the CI Docker build to run the full suite correctly.

## 2026-07-10 – 2026-07-11 — Persistence & containerization
- Added PostgreSQL persistence via SQLAlchemy, with Alembic migrations and Marshmallow input validation.
- Added Docker Compose (app + database) and the initial GitHub Actions CI workflow.

## 2026-06-28 – 2026-06-30 — Web interface
- Added a Flask web interface alongside the existing CLI, reorganizing the project into separate `CLI/` and `WEB/` directories.
- Extracted a shared service layer used by both the CLI and the web app.
- Bug fixes across the web interface and shared services.

## 2026-06-24 — Initial CLI prototype
- Initial CLI weather app: fetches and displays current conditions and forecast for a city.
- Iterated on CLI output formatting and forecast features across several same-day commits.
- Added a first README.
