# Observability hardening: 2026-09-30 (audit §6 item 22, §3.7)

Branch `chore/observability` (based on develop `f6a7cff7d`). Not merged. **Ready for review.** Backend only; no FrontEnd edits.
**Python:** all checks ran in a **Python 3.11.16 venv built from `requirements-dev.txt`** (sentry-sdk 2.71.0), which matches CI and Railway.

## SETUP FOR JAMIE
**(a) Sentry alert rules** (Sentry → Alerts → Create; filter every rule by **environment**). Events are now tagged `production` / `staging` / `development`, with `release` = the deployed SHA.

| Rule | Type | Condition | Action |
|---|---|---|---|
| New production issue | Issue alert | *A new issue is created*, environment = `production` | Email/Slack immediately |
| Production regression | Issue alert | *An issue changes state from resolved to unresolved*, `production` | Email/Slack |
| Production error spike | Metric alert | Number of errors > **25 in 5 min** (tune after a week), `production` | Critical: page. Warning at 10 |
| Hot production issue | Issue alert | *Issue seen more than **50 times in 1 hour***, `production` | Email/Slack |
| Staging digest | Issue alert | *A new issue is created*, `staging` | Daily digest (low priority) |

- **Useful searches:** `franchise_id:<id>`, `week:<n>`, `endpoint:/franchise/complete-week/phase-b` (new tags, below).

**(b) Free uptime monitor** (UptimeRobot free: 50 monitors at 5-min intervals; or Better Stack free):
- **Production:** `https://api.geekedoutbasketball.com/health/ready`
- **Staging:** `https://gob-simplified-staging.up.railway.app/health/ready`

  (The staging custom domain `api-staging.geekedoutbasketball.com` didn't resolve from here; use it instead if it's live.)
- **Settings:** HTTP(S) monitor, expect **200**, keyword `ready` (optional), timeout 10 s, alert after 2 failures.
- **Optionally a second monitor on `/health`** (liveness). If `/health` is up while `/health/ready` is down, the process is alive but the DB, or startup, isn't.

**(c) Railway variables:**

| Var | Staging | Production | Notes |
|---|---|---|---|
| `ENVIRONMENT` | `staging` | `production` | **Now the source of the Sentry environment.** Staging already reports `staging` at /health; confirm production says `production` |
| `SENTRY_DSN` | set | set | Backend. The same DSN is fine; the environment tag separates them |
| `SENTRY_DSN_FRONTEND` | set | set | Browser SDK (via /app-config) |
| `SENTRY_TRACES_SAMPLE_RATE` | optional (default **0.02**) | optional (default **0.1**) | See quota notes |
| `GOB_DESKTOP_SENTRY` | never | never | Desktop-only opt-in; leave unset everywhere |

`RAILWAY_GIT_COMMIT_SHA` is injected by Railway and is used as the release, so nothing to set.

## What changed
1. **Privacy** (`BackEnd/utils/observability.py`):
   - **`send_default_pii=False`.**
   - **`before_send` / `before_send_transaction` scrubber:**
     - **Headers:** `Authorization`, `Cookie`, `Set-Cookie`, `X-API-Key` and `Proxy-Authorization` are filtered. Cookies and the client IP are dropped.
     - **`user`:** only `id` is kept (no email or IP).
     - **Auth routes (`/api/auth/*`):** the whole request body is replaced.
     - **Any other body, `extra`, `contexts`, breadcrumbs, frame vars, frame source-context lines and exception messages:**
       - keys matching password / token / secret / otp / code / access_code / email / api_key are redacted
       - **JWTs**, `Bearer …` and **email addresses** are replaced inside any string
       - `token`, `email`, `code` and `otp` query parameters are redacted in the URL and query string
     - **Size:** bulky engine keys (`game_document`, `turns`, `box_score`, `game_state`, `animations`, …) over 1 KB become `[truncated <key>: N bytes]`. Strings are capped at 2 KB and lists at 50 items.
     - **Failure:** if the scrubber itself throws, the event is **dropped**, never sent unscrubbed.
   - The **real-SDK test** found that stack frames carry *source context lines*. They're scrubbed too.
2. **Release and environment:**
   - `release` = the deployed SHA (`RAILWAY_GIT_COMMIT_SHA`, then `GIT_COMMIT_SHA`, `SOURCE_VERSION`, `GOB_BUILD_ID` or the `BUILD_ID` stamp), 12 characters.
   - `environment` comes from the app's **`ENVIRONMENT`** (`production` / `staging` / `development` / `test`; `prod` → `production`), and `desktop` on loopback.
   - **Bug fixed:** the old code used `RAILWAY_ENVIRONMENT`, which isn't in [Railway's variable reference](https://docs.railway.com/reference/variables); the documented one is `RAILWAY_ENVIRONMENT_NAME`. Staging and production are **separate Railway projects, each with an environment named "production"**, so staging errors were most likely filed as `production`.
3. **Desktop:** it stays **off unless `GOB_DESKTOP_SENTRY=1`**. Previously it was always off (`not is_loopback()`); now there's an explicit opt-in, and nothing sets it.
4. **Noise:**
   - One line demoted at source (below).
   - `before_send` drops two known healthy-game diagnostic templates **only when the event has no exception**: `[HCO ENTRY BUG] current_bh_id is None` (belt and braces) and `🔴🔴🔴 [DIAG] FALLING BACK TO DB`.
   - Real exceptions, unhandled errors and 5xx always flow. Strict-mode violations raise, so they arrive as exceptions.
5. **Sampling:** `SENTRY_TRACES_SAMPLE_RATE` (clamped 0–1). The default is **0.1 in production and 0.02 elsewhere**; before, it was a hard-coded 0.1 everywhere.
6. **League tags (no PII):** `franchise_id` (24-hex only) and `week` (numeric) from the query string or JSON body, plus `endpoint` (the path, with ObjectIds replaced by `{id}`).
7. **Readiness endpoint, `GET /health/ready`** (`_bootstrap.py`):
   - **200 `{"status":"ready"}`** only when app startup has completed (`mark_startup_complete`, called at the end of api.py's startup) **and** the DB answers a ping within **2 s**. The ping is a Mongo `admin.command("ping")`, or `SELECT 1` on the desktop SQLite store.
   - **Otherwise 503 `{"status":"not_ready"}`**, with no internal details.
   - **Exempt from the default rate limit**, like `/health`.
   - **`/health` is unchanged** (Railway's healthcheck).
8. **`/app-config`** additively returns `sentryEnvironment` and `release`, so the browser SDK can tag events the same way (see the frontend section).

## Log lines demoted (with evidence)
| Line | Where | Was → now | Evidence |
|---|---|---|---|
| `❌❌❌ [HCO ENTRY BUG] current_bh_id is None — prior turn failed to stamp a final ball handler…` | `BackEnd/engine/skeleton_step_emitter.py` (~1821) | `logging.error` → **`logging.warning`** | **119 occurrences across 12 healthy games** (6 full-sim + 6 played, seeds 8000–8005, equiv-v3 harness `scratch_equiv3_fbdedupe.run_arm`, mongomock, Python 3.11). Every game finished with `err=None` and plausible scores (162–204 points). That's about **10 per healthy game**, each of which the default Sentry logging integration (ERROR → event) would have turned into an event. The code recovers right after logging. Matches the earlier note "fires ~7x per healthy game" |

**Not demoted** (no evidence of firing on healthy games, so filtered instead):
- `🔴🔴🔴 [DIAG] FALLING BACK TO DB` (`turn_manager.py:3132`): **0 occurrences** in the same 12 games. It's cited by the audit as noise, so it's dropped in `before_send` (event only, without an exception). The log line itself is unchanged.
- `🛑 [DEFENSE-IDENTITY] … ZERO usable documents`: fired 3× in the harness only because it doesn't seed the defense catalog (`SEED_DEFENSES=0`). That's a harness artifact, so it's left alone.

## Frontend Sentry (`FrontEnd/static/js/shared/sentryInit.js`): findings for the UX agents (not edited)
**What it sends today:**
- **PII:** `Sentry.setUser({ id: user.user_id || user.email, email: user.email })` sends the **email**, and uses it as the id when `user_id` is missing.
- **No `environment` and no `release`.** Staging and production browser errors are indistinguishable.
- **No `beforeSend`.** Page URLs go out as-is: `reset-password.html?token=…` would ship the **reset token**, and query strings carry `franchise_id` / `game_id`.
- **`tracesSampleRate: 0.1`** is hard-coded.
- **The SDK** (`browser.sentry-cdn.com/8.34.0/bundle.min.js`) is loaded **without an `integrity` (SRI) hash**.
- **The DSN** comes from `/app-config` (`SENTRY_DSN_FRONTEND`). Browser DSNs are public by design.
- **Desktop is correctly skipped** (`GOB_BUILD_PROFILE=desktop`).

**Recommended changes:**
1. `setUser({ id: user.user_id })` only: no email, and no email fallback.
2. Pass `environment: config.sentryEnvironment` and `release: config.release`; `/app-config` now returns both.
3. Add a `beforeSend` that strips `token`, `email`, `code` and `otp` query parameters from `event.request.url` and breadcrumbs, and drops the event on `reset-password.html` unless it's scrubbed.
4. Read the traces rate from config (or drop it to 0.02 on staging).
5. Add `integrity` plus `crossorigin` to the CDN script, or self-host the bundle.

## Quota implications
- **Errors:** healthy games no longer generate events. The HCO line alone was ~10 events per game at ERROR, which at scale is thousands a day. What's left should be real issues.
- **Transactions:** at 0.1, about 1 in 10 requests is traced. Volume is dominated by `/api/simulate-turn` (hundreds per played game) and `/api/simulate-quarter`. On Sentry's free Developer tier the monthly transaction quota runs out fast.
  - **Recommendation:** start production at **0.02–0.05** via `SENTRY_TRACES_SAMPLE_RATE`.
  - **Next step (not done):** add a `traces_sampler` that samples `simulate-turn`, `/health*` and `/app-config` near 0 and week-advance endpoints higher.

## Tests
`tests/test_observability.py`, 29 tests:

| Area | Covered |
|---|---|
| Environment | Staging tagged `staging` even when Railway's environment name is "production"; prod aliases; desktop |
| Release | Uses the SHA |
| Sample rate | Defaults, override, clamping, junk values |
| Desktop | Off unless opted in; no DSN means off |
| Scrubber | Headers, cookies, IP and user email. Auth bodies dropped (signup, reset). Secrets, JWTs and emails nested anywhere, including query strings, `extra`, exceptions and breadcrumbs. A ~2 MB `game_document` truncated (over 50× smaller). Long strings capped. Transactions scrubbed. A scrubber failure drops the event |
| Tags | `franchise_id`, `week`, `endpoint` (with `{id}` templating) |
| Noise | Both known lines dropped; an exception is kept, even alongside a noise message |
| **Real `sentry_sdk` client** (in-memory transport) | `logging.error` of both noise lines plus one real exception → **exactly 1 event**, tagged `environment=staging` and `release=feedfacecafe`, with no email or JWT anywhere (including frame source context). The client is re-inited with no DSN afterwards |
| `/health/ready` | 503 before startup; 200 when the ping succeeds; 503 when the ping raises (the body has no `mongodb` details); 503 within 1.5 s when the ping hangs; exempt from the default limit (6× ready and 6× /health at a 2/min limit) while `/app-config` hits 429 |
| `/app-config` | Exposes `sentryEnvironment` and `release` |

## Unsure / notes
- **Uncontrolled log volume:** the ERROR→event logging integration is left at SDK defaults. Any *other* diagnostic lines at ERROR that fire in production but not in these 12 games will still create events. Watch the first days of Sentry and add them to the noise list with evidence.
- **Hung pings:** a hung Mongo ping keeps its worker thread until pymongo's own server-selection timeout (30 s) after `/health/ready` has already answered 503. That's fine at monitor frequency (every 1–5 min).
- **Two DSNs:** if production and staging use different Sentry projects, the alert rules apply per project and the environment filter is still useful.

---
Gate: `Migration gates passed.`
Full suite (Python 3.11 venv from `requirements-dev.txt`, default config): `= 4225 passed, 20 skipped, 109 xfailed, 1 xpassed, 28 warnings in 232.12s (0:03:52) =`. The same venv on the clean develop base (`f6a7cff7d`) gives 4196 passed, 20 skipped, 109 xfailed, 1 xpassed, 28 warnings, so +29 = the new tests. No new failures; the XPASS is the pre-existing leaders-view test.
