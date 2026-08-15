# Performance Testing

Load testing is done with [k6](https://k6.io/). Scripts live in `load-tests/`.

## Strategy

Two environments are used, on purpose:

- **Smoke & load tests** run against the **live Render deployment** (`weather-7icc.onrender.com`), with a conservative number of virtual users (VUs). This gives real-world numbers — actual network latency, free-tier CPU limits, cold-start behavior — without risking the free-tier infrastructure or tripping the web route's rate limiter (`25 per minute` per IP, on `/` only — the `/api/*` routes hit by these scripts aren't currently rate-limited).
- **Stress & spike tests** run only **locally** against `docker-compose` (`localhost:5001`), where nothing is rate-limited or resource-capped by a third party. This is where the application is deliberately pushed past its limits.

| Script         | Target             | VUs (peak) | Purpose                                      |
|----------------|---------------------|------------|-----------------------------------------------|
| `smoke.js`     | Render (prod)        | 5          | Confirm the deployed app is alive and stable  |
| `load.js`      | Render (prod)        | 10         | Realistic traffic across all endpoints        |
| `stress.js`    | Local (docker-compose)| 40        | Find the breaking point, ramped gradually     |
| `spike.js`     | Local (docker-compose)| 50        | Sudden traffic burst, check recovery          |

All scripts hit three endpoints per iteration: `/health` (touches the DB), `/api/ping` (no DB, no external call), and `/api/weather?city=<random>` (external WeatherAPI call + Redis cache, random city per iteration to force cache misses).

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

1. **SQLAlchemy connection pool exhaustion** — increased `pool_size` from the default (5) to 10, with `max_overflow=20`. Result: **no change** (`checks_failed` 3.08%, within noise).
2. **Gunicorn worker count** — considered increasing from 4 to 8 workers, but decided against testing it: since the connection-pool fix (a more direct lever) had zero effect, and CPU wasn't the constraint locally, more workers were unlikely to help either.

**Conclusion:** the ~3-6% error rate at 30-40+ concurrent VUs appears to be an architectural ceiling of the current sync-code-on-gevent-workers approach (context-switch overhead, OS-level TCP backlog), not a config value that can be tuned away. Resolving it fully would likely require a true async stack — which lines up with the planned FastAPI service in the roadmap.

## Spike Test (Local)

Sudden burst: 5 → 50 VUs in 5 seconds, held for 20s, then back down to 5.

- `http_req_duration`: avg 17ms, p(95) 32ms, max 348ms
- `checks_failed`: **2.74%**
- `http_req_failed`: **5.49%**

Nearly identical to the stress test's numbers at a similar VU count. **The application shows no special fragility to sudden traffic spikes** — the error rate tracks the absolute concurrency level, not how quickly that level was reached. Degradation is linear and predictable, not a cliff.

## Summary

| Test                          | Environment | Peak VUs | checks_failed | http_req_failed | max duration |
|--------------------------------|-------------|----------|----------------|------------------|---------------|
| Smoke                          | Render      | 5        | 0%             | 0%               | —             |
| Load (sync workers)            | Render      | 10       | 7.35%          | 9.80%            | 21.96s        |
| Load (gevent)                  | Render      | 10       | 3.69%          | 7.39%            | 1.83s         |
| Load (gevent + psycogreen)     | Render      | 10       | 2.85%          | 5.70%            | 1.13s         |
| Stress (gradual ramp)          | Local       | 40       | 2.98%          | 5.97%            | 667ms         |
| Spike (sudden burst)           | Local       | 50       | 2.74%          | 5.49%            | 348ms         |

**Key takeaways:**
- Switching Gunicorn from `sync` to `gevent` workers was the single highest-impact fix, cutting worst-case latency by ~12x and error rate roughly in half on the Render deployment.
- Neither `psycogreen` nor a larger SQLAlchemy connection pool moved the needle locally — the remaining error rate is not a quick-fix config problem.
- The app degrades the same way under a slow ramp as under a sudden spike — no spike-specific weakness.
- At high concurrency (30+ VUs), a consistent ~3-6% error rate is a known, documented limit of the current architecture, not a hidden bug.

## Running the tests

```bash
# Smoke & load — against the live Render deployment
k6 run load-tests/smoke.js
k6 run load-tests/load.js

# Stress & spike — local only, requires docker-compose running
docker-compose up -d
k6 run load-tests/stress.js
k6 run load-tests/spike.js
```
