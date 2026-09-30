# Logout auth header · 429 on the week routes · Office leftovers

Branch `fix/logout-429-office` off `origin/develop`.

---

## 1. Logout sends the bearer token

Since fix/auth-hardening, `POST /api/auth/logout` only revokes the session
(bumps `token_version` — signs out everywhere) when it receives a bearer token.
All three callers were sending a **bare** POST with no `Authorization` header, so
the server-side revoke was a silent no-op.

**One shared helper.** Added `API_CONFIG.logout()` in the auth module the three
files already use (`FrontEnd/static/js/config/api-config.js`). It reads
`getAuthHeaders()` (the token) **first**, fires the POST with that header **and
`keepalive: true`** (so it survives the caller's immediate redirect), **then**
clears `auth_token` / `auth_user`, and never throws. Returns a Promise that
resolves after the request settles.

| Caller | Before | After |
|---|---|---|
| `mode-select.js` `logOutOfGob` (~1263) | `await fetch(buildUrl('/api/auth/logout'), { method:'POST' })` then clear then redirect | `await API_CONFIG.logout()` then `navigateFromModeSelect('/login.html')` |
| `js/shared/gobSettings.js` `logOut` (~216) | fire-and-forget bare POST, then clear, then redirect | `API_CONFIG.logout()` then `location.href='/mode-select.html'` (local-clear fallback if helper absent) |
| `js/shared/authBarInit.js` logout btn (~999) | fire-and-forget bare POST, then clear + UI toggle + redirect | `API_CONFIG.logout()` then the same UI toggle + redirect |

Each caller keeps its own redirect target, exactly as before.

**Desktop/offline.** `/api/auth` is an always-remote category (api-config
`ALWAYS_REMOTE_CATEGORIES`), so desktop logout hits the hosted auth server, same
as today. With no reachable server the `fetch` just rejects; `logout()` swallows
it, the local token is still cleared, and nothing crashes. `trophyCase.js` has its
own logout that only clears locally (never called the server) — out of scope, left
as-is (noted for a future pass).

**Test.** `tests/e2e/logout-auth-header.spec.js`: intercepts `**/api/auth/logout`,
calls `API_CONFIG.logout()` (the path all three callers share), and asserts the
request carried `Authorization: Bearer <token>` (POST) and that `auth_token` /
`auth_user` are cleared afterward. Second case aborts the route (offline) and
asserts it still clears and does not throw. **2/2 pass.**

---

## 2. 429 on the week routes

### a. Frontend callers of the rate-limited routes

No caller invokes these in a loop — each is one-shot per user action, and the two
CPU-sim clients are single-flight (deduped by `franchise:week`). List:

| Route (limit) | file:line | Context |
|---|---|---|
| `complete-week/phase-a` (10/min) | `js/phaser/finalizeGame.js:119` (`postPhaseA`) | EOG finalize; called once at :320, one retry-with-box at :326 |
| `complete-week/phase-b` (10/min) | `js/phaser/utils/franchisePhaseBClient.js:35` | Single-flight; callers: gobAdvance recovery :680, gameCompletionPopup :902/:1005, postGamePressConference :258 |
| `complete-week/start-cpu-sims` (6/min) | `js/phaser/utils/franchiseStartCpuSimsClient.js:59` | Single-flight + completed-key guard; caller bootGame.js:130 |
| `finish-season` (3/min) | `js/shared/gobAdvance.js:508` (`startFinishSeason`) | One-shot per "Go To Next Season" click |

No sim-to-date / auto-advance / tutorial fast-forward loop calls any of them
(franchise mode advances one game at a time; the only frontend "sim-to-date"-style
strings are in the Phaser vendor bundle). Flagged loops: **none found.**

### b. Retry behaviour

No existing 429/Retry-After path existed anywhere in the franchise/advance code
(only unrelated retries in potg.js / arrivalHeartbeat.js), so I built **one**
shared helper rather than a second path: `API_CONFIG.fetchWithRateLimitRetry(url,
options, cfg)` in `api-config.js`. On a 429 it reads `Retry-After` (seconds;
default **6** when absent/unparseable — `RATE_LIMIT_DEFAULT_RETRY_SECONDS`), waits,
and re-sends the **same** request, up to **5** times (`RATE_LIMIT_MAX_RETRIES`),
then returns the last 429 so the caller's existing `if (!res.ok) …` error path
fires. It surfaces **no UI** on a retried 429; any busy/disabled button the caller
already set simply stays put for the duration of the await (the Advance button
keeps its `is-loading`/`disabled` state). All four call sites above were swapped
from `fetch(...)` to `…fetchWithRateLimitRetry(...)`, keeping their own
ok/error handling verbatim.

**Test.** `tests/e2e/week-429-retry.spec.js`: routes `complete-week/phase-b` to
429 with `Retry-After: 1` once then 200, drives the **real** phase-b client, and
asserts the call resolves 200 in **exactly 2 requests** with no page error / dialog
("no error UI"). **1/1 pass.**

### c. Desktop/offline limiter finding

The limiter **does not apply on desktop/offline.** `user_rate_limit._check`
(`BackEnd/utils/rate_limiter.py:122-124`) early-returns when
`not limiter.enabled or is_loopback()` — the loopback engine (desktop) is exempt,
same note as `api.py`. So a single desktop player **cannot** hit the limit; no
backend change is needed (and none was made — out of scope for this branch). The
429 responses on hosted carry `Retry-After` in seconds (rate_limiter.py:134),
which is what the frontend helper reads.

---

## 3. Office leftovers

**"+N more" toggle SFX.** The weekly-card reveal (`officeHome.js` `weeklyAlso`,
~670) is not a navigation, so it never routed through `go()`/`clickTiny` and played
no sound. Added `toggle.setAttribute('data-sfx', 'SFX_SELECT')` so it ticks once
per click via the delegated `uiSfx` hook (the toggle's own handler stays silent →
one sound). Weekly-card links already go through `go()` → `clickTiny()` →
`playSelect()` = one `SFX_SELECT` per click; they carry no `data-sfx`, so they are
**not** doubled.

**Test.** `tests/e2e/office-weekly-sfx.spec.js`: renders the office with a digest
carrying `also` + `weekly_card_items`, spies `window.__gobSfxCalls`, and asserts
the toggle click → `['SFX_SELECT']` and a weekly link click → `['SFX_SELECT']`
(exactly one each). **1/1 pass.**

**Momentum removed from "Moved most" (display-only).** Jamie pulled Momentum from
Team Attributes and the Training Report's Team Report; the Office's Team snapshot
"Moved most" rows still could surface it, because `office_digest.moved_most()`
(`BackEnd/utils/office_digest.py:626`) ranks over **all** keys in `team_measures`
and `momentum_score` is deliberately kept in `TEAM_MEASURE_KEYS` (office_digest.py:40;
comment at 340-343 — it stays so the weekly snapshot stores it). Fixed frontend-only
in `snapshotCard` (`officeHome.js`): the `moved_most` array is filtered to drop any
`row.measure === 'momentum_score'` before the top-2 render, so Momentum can never
appear even as the biggest mover (the next real movers show instead). **The digest /
API is unchanged** — `momentum_score` is still stored and served.

With momentum filtered out, `labelize` no longer receives `momentum_score` from any
path (its only measure feeder was `moved_most`; the other `labelize` callers pass
attribute codes / todo keys), so the now-dead `momentum_score: 'Momentum'` entry was
**dropped from `MEASURE_LABELS`**. The rest of `MEASURE_LABELS` stays — its other
keys are still rendered by `moved_most`. `what_moved` is likewise still read
(weekly-card badges at officeHome.js and the header rank).

**Test.** `office-weekly-sfx.spec.js` second case renders a Team snapshot whose
top mover is `momentum_score` (next two are `offensive_efficiency` /
`shot_threshold`) and asserts the snapshot card shows "Moved most", "Offense" and
"Shooting" but **not** "Momentum". **Pass.**

---

## Gates

- **pytest** `--ignore=tests/e2e -q`: **4180 passed, 14 skipped, 109 xfailed, 1 xpassed, 0 failed** (199s). (The single XPASS is a pre-existing baseline known-failure that passes; not touched by this branch.)
- **check_ui_tokens.py** `--strict --no-write`: **exit 0** (no new hits; my diff changes JS only, no colour tokens).
- **check_migration_gates.py**: **passed** (Gate A 0/0; Gate B 136 lines/44 files — unchanged; no franchise-identity URLSearchParams added).
- **Full Playwright** (workers=1, port 8000, CI unset, no other run): **770 passed, 4 skipped, 0 failed** (10.7m).
- **New specs (targeted, workers=1):** 5 passed (logout 2, week-429 1, office-sfx 2 — SFX + no-Momentum).

## Files changed

| File | Task |
| --- | --- |
| `FrontEnd/static/js/config/api-config.js` | 1 & 2 — `logout()` + `fetchWithRateLimitRetry()` helpers |
| `FrontEnd/static/mode-select.js` | 1 — logout caller |
| `FrontEnd/static/js/shared/gobSettings.js` | 1 — logout caller |
| `FrontEnd/static/js/shared/authBarInit.js` | 1 — logout caller |
| `FrontEnd/static/js/shared/gobAdvance.js` | 2 — finish-season → retry helper |
| `FrontEnd/static/js/phaser/finalizeGame.js` | 2 — phase-a → retry helper |
| `FrontEnd/static/js/phaser/utils/franchisePhaseBClient.js` | 2 — phase-b → retry helper |
| `FrontEnd/static/js/phaser/utils/franchiseStartCpuSimsClient.js` | 2 — start-cpu-sims → retry helper |
| `FrontEnd/static/js/shared/officeHome.js` | 3 — "+N more" `data-sfx` |
| `tests/e2e/logout-auth-header.spec.js` | 1 — new test |
| `tests/e2e/week-429-retry.spec.js` | 2 — new test |
| `tests/e2e/office-weekly-sfx.spec.js` | 3 — new test |

STATUS: COMPLETE
