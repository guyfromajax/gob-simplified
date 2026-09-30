# Roster name-lookup on mongomock (2026-09-30)

## Cause

`GET /roster/{team_identifier}` tries three lookups. Strategy 1 is `team_id`. Strategy 2 is a 24-hex `ObjectId`. Strategy 3 is a hyphen-normalized **name** aggregate:

```
$toLower($replaceAll($name, "-", " "))
```

Real Mongo and SQLite implement `$replaceAll`. mongomock does not (`OperationFailure: Unrecognized expression '$replaceAll'`).

`647e8a6aa` (this morning’s ObjectId-shadowing fix) stopped a function-scoped `from bson import ObjectId` from raising `UnboundLocalError` on every name-based call. Those calls now reach Strategy 3 instead of 500-ing earlier. Playwright seeds use `aaaaaaaaaaaaaaaaaaaaaaaa` as a fake team/franchise id: 24 hex, so Strategy 2 runs, misses, then Strategy 3 runs the aggregate and mongomock raises.

## Fix

`lookup_team_doc_by_normalized_name` in `BackEnd/api/api.py`:

1. Run the same aggregate (Mongo / SQLite unchanged).
2. On `pymongo.errors.OperationFailure`, `find()` candidates with a cheap case-insensitive regex on the first token, then match in Python with the same rules:
   - query: `unidecode(strip.replace("-", " ")).lower()`
   - stored: `name.replace("-", " ").lower()` (no unidecode — the aggregate never did)
   - first match wins (`$limit: 1`)

No new indexes. No sim / finalize changes. Court `team_id` aliases in `seed_and_serve.py` stay so `/roster/Lancaster` still hits Strategy 1.

## Harness: why uvicorn died

Two different things were stacked in the batch-4 log.

**The `$replaceAll` request is not a clean FastAPI 500.** anyio wraps the sync `OperationFailure` in an `ExceptionGroup` (Python 3.11+ `BaseException`, not `Exception`). `@app.exception_handler(Exception)` logs an `error_id` but Starlette’s TestClient still **raises** `OperationFailure` when the helper is reverted (verified). uvicorn then logs `Exception in ASGI application`. That is ugly; it is not what calls `shutdown()`.

**The process exit is SIGTERM.** uvicorn 0.54 only sets `should_exit` on a signal (`handle_exit`) or `limit_max_requests`. After the lookup fix, a first full Playwright run still died at court-layout (~test 41/787) with a clean `INFO: Shutting down` and no `$replaceAll`. Same death with `PW_REUSE_SERVER=1` (Playwright started its own child after an externally started server was SIGTERM’d at 21s). The request path is not killing the process; something in this runner/Playwright webServer is delivering SIGTERM to the child.

**Trivial harness fix** in `seed_and_serve.py` only: `_E2EServer` ignores SIGTERM (`capture_signals` installs `SIG_IGN` instead of uvicorn’s `handle_exit`). Mid-suite SIGTERM can no longer tear the server down. Playwright still SIGKILLs the process at the end of the run. No app exception-handler change.

## Tests

`tests/test_roster_name_lookup.py`:

- mongomock HTTP: `/roster/{team_id}` and `/roster/{name}` (and hyphen/space) return the same team.
- `/roster/aaaaaaaaaaaaaaaaaaaaaaaa` is **404**, not 500.
- SQLite `SqliteStore`: name lookup returns the same `team_id` as `find_one({"team_id": ...})`.
- Forced `OperationFailure` on `aggregate()` hits the Python fallback.

Reverting Strategy 3 to the raw aggregate makes the two HTTP tests fail (`OperationFailure`).

Left `tests/known_failures.py` alone. `test_roster_api.py` is still skipped on mongomock (`MONGOMOCK_SKIPS`); those two would now pass if un-skipped.

## Gates

| Gate | Result |
|---|---|
| pytest `-q` | **4279 passed**, 16 skipped, 108 xfailed, **2 xpassed**, **0 failed** (250.39s) |
| Playwright `tests/e2e --workers=1`, PORT=8311, CI unset, `PYTHON_PATH=.venv/bin/python` | **Completed 787/787.** **778 passed**, 6 skipped, **3 failed** (21.6m). Failures are `invite-board.spec.js` seed-notice timeouts (dismissible / disappears once saved / saving posts the order) — not roster lookup. `t2-roster` and the rest of the suite ran after court-layout; no `$replaceAll`, no `ECONNREFUSED`. |
| `check_ui_tokens.py --strict --no-write` | exit 0 (new-design colour-law 0) |
| `check_migration_gates.py` | passed. Gate A 0/0, Gate B 136/44. No `--write-allowlist`. Script noted `training-report.html` and `training.html` are now clean of Gate B hits (pre-existing allowlist leftovers; not this change). |

XPASS (pre-existing on this develop tip, not this lookup): `tests/test_settings_application_to_gameplay.py::TestSettingsApplicationToGameplay::test_settings_loaded_and_applied_to_gameplay`. Second XPASS also on current develop (suite count 2); not edited in `known_failures.py`.

## Files

- `BackEnd/api/api.py` — helper + Strategy 3
- `tests/test_roster_name_lookup.py` — new
- `tests/e2e/helpers/seed_and_serve.py` — comment + SIGTERM-ignore `_E2EServer`
