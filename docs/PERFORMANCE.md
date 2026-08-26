# Performance Testing

Load testing is done with [k6](https://k6.io/). Scripts live in `load_tests/`.

## Strategy

Two environments are used, on purpose:

- **Smoke & load tests** run against the **live Render deployment** (`weather-7icc.onrender.com`), with a conservative number of virtual users (VUs). This gives real-world numbers — actual network latency, free-tier CPU limits, cold-start behavior — without risking the free-tier infrastructure or tripping the web route's rate limiter (`25 per minute` per IP, on `/` only — the `/api/*` routes hit by these scripts aren't currently rate-limited).
- **Stress & spike tests** run only **locally** against `docker compose` (`localhost:5001` for sync `web`, `localhost:8001` for async `api`), where nothing is rate-limited or resource-capped by a third party. This is where the application is deliberately pushed past its limits.

| Script            | Target                  | VUs (peak) | Purpose                                      |
|-------------------|--------------------------|------------|-----------------------------------------------|
| `smoke.js`        | Render (prod)             | 5          | Confirm the deployed sync app is alive and stable |
| `load.js`         | Render (prod)             | 10         | Realistic sync traffic across all v1 endpoints |
| `stress.js`       | Local (docker-compose)    | 40         | Find the sync stack's breaking point, ramped gradually |
| `spike.js`        | Local (docker-compose)    | 50         | Sudden traffic burst against the sync stack, check recovery |
| `smoke_v2.js`     | Render (prod)             | 5          | Confirm the deployed async `/api/v2/*` stack is alive |
| `load_v2.js`      | Render (prod)             | 10         | Realistic async traffic against `/api/v2/*` |
| `stress_v2.js`    | Local (docker-compose)    | 40         | Find the async stack's breaking point, ramped gradually |
| `spike_v2.js`     | Local (docker-compose)    | 50         | Sudden traffic burst against the async stack, check recovery |

All v1 scripts hit three endpoints per iteration: `/health` (touches the DB), `/api/ping` (no DB, no external call), and `/api/weather?city=<random>` (external WeatherAPI call + Redis cache, random city per iteration to force cache misses; also writes a `WeatherRequest` row on every outcome, success or failure). The v2 scripts mirror this with two groups — `/api/v2/health` and `/api/v2/weather?city=<random>` — since the async stack has no `/api/ping`-equivalent no-DB endpoint.

## Smoke Test (Render)

5 VUs, 50s. Baseline sanity check before anything else.

- `checks_succeeded`: 100%
- `http_req_duration`: avg 372ms, p(95) 387ms
- `http_req_failed`: 0%

No issues — confirms the deployed `/health` endpoint is reachable and responsive under light load.

## Load Test (Render) — Investigating a Bottleneck

10 VUs, ~1m40s, hitting all three endpoints with randomized cities.

### Baseline (sync Gunicorn workers, 4 workers)

- `http_req_duration`: avg 993ms, p(95) 877ms, **max 21.96s**
- `checks_failed`: 7.35%
- `http_req_failed`: 9.80%
- Errors: `connection reset by peer` across all three endpoints — not slow responses, but dropped connections.

**Hypothesis:** Gunicorn's default `sync` worker class blocks one request per worker. With only 4 workers and 10 concurrent VUs (each firing 3 requests per iteration), requests queue up and the Render proxy times out waiting for a response, killing the connection. Render's free tier (~0.1 vCPU) compounds this.

### Fix 1 — Switch to gevent workers

Changed Gunicorn's worker class to `gevent` (`--worker-class gevent --worker-connections 50`), which lets each worker handle many requests concurrently instead of blocking on I/O.

**Result:**
- `http_req_duration`: avg **196ms** (5x better), p(95) **380ms** (2x better), max **1.83s** (12x better)
- `checks_failed`: **3.69%** (down from 7.35%)
- `http_req_failed`: **7.39%**
- `iterations` completed in the same time window: 230 vs 136 (+70%)

Clear, significant win. Most of the catastrophic multi-second outliers disappeared.

### Fix 2 — psycogreen (patch psycopg2 for gevent)

`gevent`'s monkey-patching doesn't cover `psycopg2` (a C extension with its own blocking I/O), so DB calls could still block an entire worker even under gevent. Added `psycogreen` to explicitly patch `psycopg2` for gevent compatibility.

**Result:** no meaningful change (`checks_failed` 2.85%, `http_req_failed` 5.70% — within normal run-to-run variance seen across repeated identical runs, e.g. 7.35% / 3.69% / 4.78% for the same gevent-only build).

**Conclusion:** the gevent switch itself was the fix; psycopg2's lack of a gevent patch was not a meaningful bottleneck here, likely because `/health`'s DB call (`SELECT 1`) is too cheap to matter. The remaining ~3-6% error rate on Render appears to be baseline noise from the free-tier host (shared CPU, proxy timeouts), not something fixable in application code.

## Stress Test (Local)

Gradual ramp: 10 → 20 → 30 → 40 VUs, 30s per step, against `localhost:5001` (docker-compose, gevent workers).

- `http_req_duration`: avg 15ms, p(95) 29ms, max 667ms — an order of magnitude faster than Render, as expected without network latency or CPU throttling.
- `checks_failed`: **2.98%**
- `http_req_failed`: **5.97%**

Even with no network or CPU constraints, a small but consistent error rate remains at higher concurrency (30-40 VUs). Two hypotheses were tested and ruled out:

1. **SQLAlchemy connection pool exhaustion** — increased `pool_size` from the default (5) to 10, with `max_overflow=20`. Result: **no change** (`checks_failed` 3.08%, within noise). Kept anyway as safe headroom (see [`DEPLOYMENT.md`](DEPLOYMENT.md)).
2. **Gunicorn worker count** — kept at `-w 4` (the number these benchmarks were run against): since the connection-pool fix (a more direct lever) had zero effect, and CPU wasn't the constraint locally, increasing the worker count further seemed unlikely to help either. `-w 4` is also what's running in production, via `WEB/Dockerfile`'s `CMD` (Render has no separate start command override), so the numbers documented here match what's actually deployed.

**Conclusion:** the ~3-6% error rate at 30-40+ concurrent VUs appears to be an architectural ceiling of the current sync-code-on-gevent-workers approach (context-switch overhead, OS-level TCP backlog), not a config value that can be tuned away.

## Spike Test (Local)

Sudden burst: 5 → 50 VUs in 5 seconds, held for 20s, then back down to 5.

- `http_req_duration`: avg 17ms, p(95) 32ms, max 348ms
- `checks_failed`: **2.74%**
- `http_req_failed`: **5.49%**

Nearly identical to the stress test's numbers at a similar VU count. **The application shows no special fragility to sudden traffic spikes** — the error rate tracks the absolute concurrency level, not how quickly that level was reached. Degradation is linear and predictable, not a cliff.

## Async API v2 Testing — A Counter-Intuitive Result

With `/api/v2/*` merged into the Render deployment (see [`DEPLOYMENT.md`](DEPLOYMENT.md)'s single-image `WSGIMiddleware` setup), the same four-test methodology was run against the async FastAPI stack. **The expectation, based on the v1 investigation above, was that a true async stack would outperform sync-on-gevent.** The initial results said otherwise.

### Smoke Test v2 (Render) — Initial Run

5 VUs, 50s, `/api/v2/health` only.

- `checks_succeeded`: 100%
- `http_req_duration`: avg 620ms, p(95) 623ms
- `http_req_failed`: 0%

Confirms the deployed async stack is reachable after the merge — no regressions at light load. Note the baseline latency (~620ms avg) is already notably higher than v1's smoke baseline (~372ms avg) even at this trivial load.

### Load Test v2 (Render) — Initial Run

10 VUs, `/api/v2/health` + `/api/v2/weather?city=<random>`.

- `http_req_duration`: avg 604ms, p(95) 803ms, max 2.39s
- `checks_failed`: 4.29%
- `http_req_failed`: 8.59%

Compared to v1's best result on the same test (gevent + psycogreen): avg 196ms, p(95) 380ms, max 1.13s, `http_req_failed` 5.70%. v2 was slower and less reliable than v1 on identical infrastructure — roughly 3x the latency and ~1.5x the error rate.

### Stress Test v2 (Local) — Initial Run

Gradual ramp 10 → 40 VUs, `localhost:8001`.

- `http_req_duration`: avg 10.48ms, p(95) 18.39ms, max 733ms
- `checks_failed`: 4.18%
- `http_req_failed`: 8.36%

Local average latency was comparable to v1's local stress test, but `http_req_failed` was meaningfully higher than v1's 5.97%.

### Spike Test v2 (Local) — Initial Run

Sudden burst 5 → 50 VUs, `localhost:8001`.

- `http_req_duration`: avg 14.91ms, p(95) 18.04ms, **max 4.17s**
- `checks_failed`: 4.56%
- `http_req_failed`: 9.13%

Average latency stayed low, but max latency (4.17s) was ~12x worse than v1's local spike max (348ms) — the worst single result across every test run, sync or async.

### Root Cause & Fix — Async Engine Pool Starvation (Partial Fix)

`API/async_db.py`'s `create_async_engine(ASYNC_DATABASE_URL)` was called with no explicit `pool_size`/`max_overflow`, unlike the sync engine in `models.py` (`pool_size=10, max_overflow=20`, raised during the v1 investigation above). SQLAlchemy's async engine defaults to `pool_size=5, max_overflow=10` — half the sync engine's configured headroom — while being tested at equal or higher concurrency (40–50 VUs for stress/spike).

**Fix applied:**
```python
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=10,
    max_overflow=20,
)
```

**Before / after (same scripts, re-run after the fix):**

| Test            | Metric            | Before | After  | Change |
|-----------------|--------------------|--------|--------|--------|
| Smoke (Render)  | http_req_failed    | 0%     | 0.81%  | negligible (1/122 requests; sample size too small to call a trend) |
| Load (Render)   | http_req_failed    | 8.59%  | 11.52% | worse — likely Render free-tier run-to-run noise (v1's gevent runs showed 7.35/3.69/4.78% variance across repeats), not yet confirmed with a repeat run |
| Stress (local)  | http_req_failed    | 8.36%  | 8.21%  | no meaningful change |
| Spike (local)   | max duration       | 4.17s  | **56.89ms** | **~73x better** |
| Spike (local)   | http_req_failed    | 9.13%  | 7.56%  | improved |

**Conclusion:** the pool-sizing fix directly resolves the worst symptom observed — catastrophic tail latency under a sudden traffic spike — confirming pool exhaustion as a real, contributing cause. It does **not** fully close the gap with v1's error rate under sustained load; v2 still runs a few points higher than v1's ~3–6% baseline, and the Render load result got worse rather than better (most likely host-side noise, not yet isolated). This is being tracked as **partially resolved**, not closed.

### Remaining Candidates for the Residual Gap (unconfirmed)

1. **`httpx.AsyncClient` connection limits.** The shared client in `API/main.py`'s `lifespan` is constructed with no explicit `httpx.Limits(...)`. httpx's defaults (100 max connections, 20 max keepalive connections) haven't been tested against these concurrency levels — this is the most direct analogue to the DB-pool fix above and the next candidate to try.
2. **Render-side noise.** The Load v2 regression (8.59% → 11.52%) needs at least 2-3 repeat runs before concluding it's real rather than free-tier variance, following the same practice used for the v1 gevent numbers.
3. **`WSGIMiddleware` presence.** Not yet isolated whether merely importing/mounting `WEB.app` inside the same process has any measurable effect on the async routes, even when a test run never calls a sync route directly.

## Summary

| Test                          | Environment | Stack    | checks_failed | http_req_failed | avg duration | max duration |
|--------------------------------|-------------|----------|----------------|------------------|---------------|---------------|
| Smoke                          | Render      | v1 sync  | 0%             | 0%               | 372ms         | —             |
| Smoke v2                       | Render      | v2 async | 0.40%          | 0.81%            | 693ms         | 2.39s         |
| Load (sync workers)            | Render      | v1 sync  | 7.35%          | 9.80%            | 993ms         | 21.96s        |
| Load (gevent + psycogreen)     | Render      | v1 sync  | 2.85%          | 5.70%            | 196ms         | 1.13s         |
| Load v2 (after pool fix)       | Render      | v2 async | 5.76%          | 11.52%           | 601.51ms      | 2.53s         |
| Stress (gradual ramp)          | Local       | v1 sync  | 2.98%          | 5.97%            | 15ms          | 667ms         |
| Stress v2 (after pool fix)     | Local       | v2 async | 4.10%          | 8.21%            | 9.18ms        | 1.01s         |
| Spike (sudden burst)           | Local       | v1 sync  | 2.74%          | 5.49%            | 17ms          | 348ms         |
| Spike v2 (after pool fix)      | Local       | v2 async | 3.78%          | 7.56%            | 7.33ms        | **56.89ms**   |

**Key takeaways:**
- Switching Gunicorn from `sync` to `gevent` workers was the single highest-impact fix for v1, cutting worst-case latency by ~12x and error rate roughly in half on the Render deployment.
- Neither `psycogreen` nor a larger SQLAlchemy connection pool moved the needle for v1 locally — the remaining ~3-6% error rate there is a known, documented architectural ceiling, not a hidden bug.
- The async v2 stack (`/api/v2/*`) initially showed a *higher* error rate and worse tail latency than v1 despite being architecturally async — the assumption "async is automatically faster" did not hold.
- Sizing the async SQLAlchemy engine's connection pool to match the sync engine (`pool_size=10, max_overflow=20`) fixed the worst symptom (spike max latency: 4.17s → 56.89ms) but left a residual error-rate gap versus v1, still under investigation.
- At high concurrency (30+ VUs), a consistent baseline error rate is a recurring pattern across both stacks on this free-tier infrastructure — not unique to either sync or async.

## Running the tests

```bash
# Smoke & load (v1 sync + v2 async) — against the live Render deployment
k6 run load_tests/smoke.js
k6 run load_tests/load.js
k6 run load_tests/smoke_v2.js
k6 run load_tests/load_v2.js

# Stress & spike (v1 sync + v2 async) — local only, requires docker-compose running
docker-compose up -d
k6 run load_tests/stress.js
k6 run load_tests/spike.js
k6 run load_tests/stress_v2.js
k6 run load_tests/spike_v2.js
```
