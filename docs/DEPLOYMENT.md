# Deployment Guide

This document describes how **Weatherender** is deployed to production, and how to reproduce or update that deployment.

---

## 1. Production Stack

| Component | Provider | Notes |
| :--- | :--- | :--- |
| **Application** | [Render](https://render.com/) | Docker runtime, free tier, auto-deploy on push to `main` |
| **Database** | [Supabase](https://supabase.com/) | Managed PostgreSQL, Session pooler connection mode |
| **Cache** | [Upstash](https://upstash.com/) | Managed Redis, Frankfurt region, TLS-only (`rediss://`) |
| **Uptime Monitor** | [UptimeRobot](https://uptimerobot.com/) | Pings `/api/ping` every 10 minutes to avoid free-tier spin-down |

Live URL: **[weather-7icc.onrender.com](https://weather-7icc.onrender.com)**

This is a pure [12-factor](https://12factor.net/config) setup: the same codebase runs locally and in production, with `DATABASE_URL` and `REDIS_URL` determining the backend. Locally, both are supplied via the `.env` file that `docker-compose.yml` loads (`env_file: .env`), pointing at the `weather_db`/`cache` containers; on Render, they're set directly in the dashboard to point at Supabase/Upstash. Note the asymmetry in `config.py`: `REDIS_URL` has a code-level default (`redis://cache:6379`), while `DATABASE_URL` does not — it must always come from the environment. There is no `if ENVIRONMENT == "production"` branching anywhere in the code.

---

## 2. Database Setup (Supabase)

1. Create a new Supabase project.
2. Use the **Session pooler** connection string, not Direct connection or Transaction pooler:
   - *Direct connection* requires IPv6, which is often unavailable on the client side.
   - *Transaction pooler* is meant for stateless/serverless workloads. Render runs a persistent long-lived process, so **Session pooler** is the correct mode per Supabase's own guidance.
   - Format: `postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`
3. ⚠️ **No `postgres://` → `postgresql://` normalization exists in the codebase.** Supabase (like most providers) may emit the legacy `postgres://` scheme, which SQLAlchemy 1.4+ rejects outright — but `Config.DATABASE_URL` is passed straight into `create_engine()` in `models.py` with no string replacement anywhere. In practice this has worked because Supabase's connection strings in this project have used `postgresql://` already, but it's an unhandled edge case, not a solved one — if a future Supabase connection string (or a different provider) comes back as `postgres://`, the app will fail to start. Worth adding the normalization defensively rather than relying on the current string happening to be in the right format.
4. Run migrations against the Supabase connection string once the project is created:
   ```bash
   DATABASE_URL="postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres" \
     alembic upgrade head
   ```
5. `models.py` configures the SQLAlchemy engine with `pool_size=10, max_overflow=20` (raised from SQLAlchemy's defaults of 5/10 during load testing — see [`PERFORMANCE.md`](PERFORMANCE.md)). This was tested as a hypothesis for reducing errors under concurrent load; it did not meaningfully change the error rate, but is kept as a safe, low-cost headroom increase for Supabase's free-tier connection limit (~60).

### ⚠️ Manual migration reminder (free tier limitation)

Render's **Pre-Deploy Command** (auto-running `alembic upgrade head` before every deploy) is a paid-tier-only feature. On the free tier, **migrations must be run manually** against the Supabase connection string whenever the schema changes (new model, new field, new Alembic revision). There is currently no automation for this — it's a deliberate, documented trade-off rather than an oversight.

---

## 3. Cache Setup (Upstash)

1. Create a free-tier Redis database (region: Frankfurt, for proximity to Render's default region).
2. Copy the TCP connection string directly into `REDIS_URL` — it already comes in the `rediss://default:<password>@<host>.upstash.io:6379` format that `redis.from_url()` expects, no parsing required.
3. `REDIS_TTL` (default 300s) controls how long weather responses stay cached.

If Redis is unreachable, the app catches the error and falls back to fetching fresh data directly from WeatherAPI — caching failure never breaks the request.

---

## 4. Application Deployment (Render)

1. Create a **Web Service** on Render, Docker runtime, pointing at `API/Dockerfile`, with build context `.` (repo root — the Dockerfile's `COPY . /app/` requires the full repo tree). `API/Dockerfile` is the **sole deployment image** — it starts an ASGI process (`uvicorn API.main:app`) that serves the async FastAPI routes directly and mounts the entire synchronous Flask app (`WEB/app.py`) via `WSGIMiddleware` at `/`. `WEB/Dockerfile` still exists and is still built by `docker-compose` for local development, but it is not what Render deploys.
2. Set the following environment variables:

   | Variable | Example / Notes |
   | :--- | :--- |
   | `WEATHER_API_KEY` | Free key from [weatherapi.com](https://www.weatherapi.com/) |
   | `DATABASE_URL` | Supabase Session pooler connection string |
   | `REDIS_URL` | Upstash `rediss://` connection string |
   | `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `REDIS_TTL` | `300` |
   | `FLASK_DEBUG` | `False` |
   | `LOG_LEVEL` | `INFO` |

3. Render auto-deploys on every push to `main`. Deployment is gated by CI — GitHub Actions must pass (Ruff, Mypy, full Pytest suite) before the deploy webhook fires.
4. After the first deploy, confirm both `/api/v2/health` (async) and `/health` (sync, served through the mounted Flask app) return `{"status": "ok"}`, and that a real weather request against either `/api/v2/weather` or `/api/weather` (proxied via `WSGIMiddleware`) writes a row into Supabase's `weather_requests` table. Also verify that sending more than 25 requests per minute to `/api/v2/weather` correctly triggers an HTTP `429 Too Many Requests` response enforced by `slowapi`.

### Dynamic port binding

Render assigns its own `$PORT` at runtime; it is **not** fixed. `API/Dockerfile` handles this with:
```dockerfile
ENV PORT=8001
CMD uvicorn API.main:app --host 0.0.0.0 --port ${PORT} --workers 4
```
`HEALTHCHECK` uses the same `${PORT}` variable. Note `uvicorn`'s CLI expands the shell variable the same way Gunicorn's shell-form `CMD` does — no array/exec-form syntax here either.

### Why one image serves both stacks

`WEB/` and `API/` remain two separate codebases with two separate `Dockerfile`s, built independently by `docker-compose` for local development (two containers, two ports). But Render's free tier only supports one active web service without added cost, so for production, `API/main.py` imports the Flask app object directly (`from WEB.app import app as flask_app`) and mounts it under FastAPI via `fastapi.middleware.wsgi.WSGIMiddleware`, exposing both the async v2 API and the full legacy v1 Flask app (including the HTML UI, `/health`, `/metrics`, `/apidocs`) from a single `uvicorn` process. Locally, both containers still exist side-by-side for isolated development and testing; only the Render deployment target changed.

This also drove two related fixes documented in the CHANGELOG: `API/schemas.py` was renamed to `API/pydantic_schemas.py` (a bare `import schemas` was resolving to `WEB/schemas.py`'s Marshmallow schema once both `ROOT_DIR` and `WEB_DIR` were added to `sys.path`), and both Dockerfiles switched from per-file `COPY` to `COPY . /app/` with a shared root `.dockerignore`, since `API/Dockerfile` now needs the entire `WEB/` package tree, not just its own flat file list.

---

## 5. Keeping the Free Tier Warm

Render's free tier spins down the container after 15 minutes of inactivity; the first request afterward can take 30–50s (cold start). To avoid this in normal operation, an external **UptimeRobot** monitor pings the lightweight `/api/ping` endpoint every 10 minutes. This endpoint deliberately opens no SQLAlchemy session and touches no database, so it doesn't consume Supabase's limited free-tier connection pool.

This is a mitigation, not a guarantee — cold starts can still happen if the monitor itself has downtime, or during Render's own container recycling. See [`PERFORMANCE.md`](PERFORMANCE.md) for what load the current setup can sustain once warm.

---

## 6. Rollback

Because deploys are triggered by pushes to `main`, rolling back a bad deploy is a normal Git operation, not a Render-specific one:

```bash
git revert <bad-commit-hash>
git push
```

This creates a new commit that undoes the change and triggers a fresh (safe) deploy. Avoid `git reset --hard` + force-push on `main` — it rewrites already-published history and can interact badly with Render's deploy webhook and anyone who has already pulled.

---

## 7. Local Development

See the [Quick Start](../README.md#quick-start-docker) section in the README for running the full stack locally via `docker-compose` — the same `WEB/`, `CLI/`, and database/cache setup used in production, minus the cloud-specific connection strings.

Note: locally, `docker-compose.yml` maps the host port using `FLASK_PORT` (`ports: "${FLASK_PORT}:${FLASK_PORT}"`), while the Dockerfile's Gunicorn command binds to `PORT` (defaulting to `5001`). These need to agree — set both to the same value (`5001`) in your `.env`, or the port mapping and the actual bound port will mismatch.
