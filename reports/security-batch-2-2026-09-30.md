# Security batch 2: 2026-09-30

Branch `fix/security-batch-2` (worktree `../gob-sec2`), backend only. No `FrontEnd/` file touched. Python 3.11.16 venv from `requirements-dev.txt`.

## 1. Request body cap: 413

### Legitimate body sizes (measured read-only on gob-staging, `GOB_DB_ACCESS=read`)

| Body | Source | Size |
|---|---|---|
| **phase-a / complete-week POST** (one final game document) | 1,871 final franchise game docs on staging: BSON median 80.5 KB, p90 114 KB, p99 123 KB, max 130 KB. The JSON of a full phase-a body built from the 5 largest docs peaks at **129,897 B** | **~130 KB (largest)** |
| `playbooks` POST (playbook_settings) | max on staging `franchise_team_data` | 2.7 KB |
| gameplan PUT (strategy_settings) | max on staging | 190 B |
| team-builder apply / drafts / portraits | model fields only. The court is a colour recipe ("never a rendered image", `franchise_routes.py:3430`); art is generated client-side and never posted | a few KB |
| feedback / alpha feedback | field `max_length`s (5,000 chars max) | < 10 KB |
| billing webhook | Stripe event JSON | tens of KB |
| simulate-quarter / simulate-turn requests | settings + lineups | < 10 KB |

- **phase-a never posts the turn history.** `gameScene.js` hands `finalizeGame` the final game document (`final_game_document`, or `GET /api/game`), not the whole simulate-quarter response. Stored franchise docs carry no turns.
- **No upload endpoints exist.** There is no `UploadFile` or `File(`, and no image or base64 posting from the frontend.
- **Desktop:** `loopback_app.py` adds no routes, and the desktop client posts the same bodies. So the cap is the same everywhere.

### Chosen limit: **1 MiB (1,048,576 B), env `GOB_MAX_REQUEST_BYTES`**

- **Headroom:** about 8× the largest real body, above the brief's "e.g. 4×" for game-doc growth such as overtime and new stat fields. A 57 MB junk body is still refused outright.
- **Bad values:** an invalid or non-positive env value falls back to the default.

### How it works (`BackEnd/utils/request_limits.py`, `RequestSizeLimitMiddleware`, pure ASGI)

- **Declared `Content-Length` over the cap:** 413 `{"detail": "Request body too large"}` before the body is read or the app runs.
- **Streamed or undeclared body** (chunked, or a lying length): the byte count is checked on every `receive()`. On crossing the cap it raises a Starlette `HTTPException(413)`, the one exception FastAPI's body reader re-raises (any other becomes a 400 "error parsing the body"). The app's exception middleware renders it as the same 413. That covers handlers that read the raw body too (billing webhook).
- **Placement:** appended to `app.user_middleware` right after `CORSMiddleware`, so it sits **inside** CORS (same pattern as the slowapi limiter) and a 413 carries `Access-Control-Allow-Origin`. That matters because a browser would otherwise report a CORS failure instead of 413. It sits outside the slowapi limiter, so an oversize request is refused before it counts against the rate limit.

## 2. 422 responses: no more input echo

- **Change:** a new `RequestValidationError` handler (`api.py`) returns `{"detail": [{"loc", "msg", "type"}, ...]}`. It drops `input` (the offending value, which for a junk body was the whole 57 MB), `ctx` and `url`. Status 422 and the `detail` key are unchanged.
- **Frontend check.** Grepping `FrontEnd/static` finds nothing that reads `.input`, `['input']`, `detail[0]`, `.loc` or `.msg` from an error. The only 422 mention is a comment in `recruiting-hub.js:556`. Frontend error paths show `body.detail` generically.
- **Test and desktop check.** Tests only assert `status_code == 422` (`test_schedule_week.py:125`, `test_user_data_exposure.py:112`, `test_recruit_detail_endpoint.py:217`). Nothing in `desktop/` reads it.

## 3. Unauthenticated game routes: all three deleted, no callers

**Caller search** (FrontEnd, desktop, tests, scripts, BackEnd; all quote styles and string-built URLs; handler and model names):

```
grep -rnE "/games['\"`?]|/games\)|'/games|\"/games|/simulate['\"`?]|'/simulate|\"/simulate|api/simulate['\"`]" FrontEnd desktop tests scripts BackEnd
  -> only the route definitions themselves (plus an unrelated /simulate-tournament-round in a sunset contract test)
grep -rn "simulate_game\b|get_games\b|SimulationRequest" -> definitions only
```

| Route | Callers | Change |
|---|---|---|
| `GET /games` (`api.py` ~8043) | none | **Deleted.** It returned the 10 most recent full game documents of any user, with no auth. |
| `POST /api/simulate` + `POST /simulate` (same handler, `api.py` ~2180) | none | **Deleted**, with `SimulationRequest` and the api.py-only imports `run_simulation` and `Player`, which became unused. `run_simulation` itself stays in `BackEnd/main.py`: `franchise_manager.simulate_game` uses it. No test only asserted these routes existed, so none needed updating. |

- **Auth check:** all three were read handler-first. None checks auth inside the handler either, and `simulate_game` did `games_collection.insert_one(summary)`.

## Tests: `tests/test_request_limits.py` (11)

- 413 by `Content-Length`, and 413 by a chunked streamed body.
- A 413 carries `access-control-allow-origin` for an allowed origin.
- Real-sized phase-a bodies (130 KB = the measured max, and 1 MiB − 4 KB) reach the handler (404 for the made-up franchise, not 413/422). The bodies are synthetic but phase-a-shaped. I did not copy staging data into the repo.
- The standalone middleware caps both declared and streamed raw-body reads (cap 100).
- Env override parsing.
- A 422 has only `loc/msg/type` and doesn't echo a 4 KB marker.
- `GET /games`, `POST /api/simulate`, `POST /simulate` → 404/405.
- **Proof they bite:** with develop's `api.py`, 7 of 11 fail (all the 413, 422 and deleted-route tests). The 4 that still pass are the env parsing, the legit-body and the standalone-middleware tests, as expected.

## Unsure / follow-ups

- **1 MiB vs 4×.** I went with 8× headroom. If you want tighter, `GOB_MAX_REQUEST_BYTES=524288` (4×) works with today's data.
- **Railway's edge may have its own request-size limit.** Not measured. Earlier 32 MB uploads got through, so the app is the only effective cap now.
- **Staging data left in the scratchpad.** While measuring, one staging game document (no user identifiers) was exported to the session scratchpad at `…/scratchpad/sec2/raw_doc.json`. The deletion was not permitted from here; please remove it. It was never added to the repo.

Migration gates: passed (Gate A 0, Gate B 136 lines / 44 files).
Full suite: 4271 passed, 20 skipped, 109 xfailed, 1 xpassed, 0 failed (the xpass is the known `test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference`, unchanged from develop).
