# Changelog

All notable changes to **Weatherender** (formerly *Weather*), organized by date and grouped by theme. Reconstructed directly from `git log`.

> Note: the repository's earliest history (24–30 June) contains a run of commits literally named `v1.0.0` through `v4.2.4` — an early, pre-conventional-commits naming habit rather than meaningful version releases. They're omitted below in favor of the descriptive commit messages from the same period, once a proper (`feat:`/`fix:`/`docs:`) commit style was adopted.

## 2026-08-17 – Snow state calculation logic fix & unit tests

- Fixed a logic bug in `WeatherService.get_snow_state`: eliminated false-positive `Ice crust` statuses on bare ground during near-zero or positive temperatures by enforcing strict snow depth checks (`snow_depth_cm > 0` or `snow_24h_cm > 0`) and proper diurnal freeze-thaw evaluation (`max_temp_c > 0 and min_temp_c < 0`).
- Fully integrated previously unaccessed parameters and variables into the snow state decision tree: `min_temp_c`, `max_temp_c`, `wind_kph`, and the calculated `snow_density`.
- Added a comprehensive parameterized unit test suite in `tests/test_snow_state.py` covering all 11 distinct meteorological scenarios and branching paths, fully verified via `pytest`.
- Maintained clean code quality standards: all modifications successfully passed `mypy` type checking alongside `ruff` and `isort` pre-commit hooks.

## 2026-08-17 — Rate limiting docs sync
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
