# GOB: agent rules

Geeked-Out Basketball (GOB) is Football Manager for basketball: a deep-tactical coaching sim, not an action game. **Franchise mode is the only active product**; Tournament and Single game are sunset (see [docs/agents.md](docs/agents.md)). Build everything simple, stable, scalable (SS&S).

These rules apply to every task unless the task explicitly overrides one.

## Repo map

| Path | What |
|---|---|
| `BackEnd/` | FastAPI app (`api/api.py` + routers in `api/*_routes.py`), sim engine (`engine/`, `models/`), persistence adapter (`persistence/`: Mongo on hosted, SQLite on desktop) |
| `FrontEnd/static/` | Vanilla JS/HTML/CSS + Phaser court. Served by Netlify; `api.py` also reads it (templates) |
| `desktop/` | Electron shell for the offline desktop build |
| `_documentation_master/` | System docs, runbooks, project notes (`projects/bugs.md`, `00_Operations/`) |
| `docs/` | Older architecture/system docs; [docs/agents.md](docs/agents.md) is the architecture/scope primer |
| `reports/` | Agent task reports (untracked by convention) |
| `scripts/` | One-off and maintenance scripts (DB access through `BackEnd/script_db.py`) |
| `tests/` | pytest (mongomock) + `tests/e2e/` Playwright |
| `base_league.*`, `catalog.*` | Runtime data bundles: never delete or exclude |

## Workflow

- **Always work in a git worktree.** Other agents share the main folder, so never switch branches or edit files there:
  ```bash
  git fetch origin
  git worktree add ../<name> -b <branch> origin/develop
  ```
- **Python:** `../gob-simplified/.venv/bin/python` (bare `python` isn't on PATH).
- **Push only your branch.** Never merge into `develop` yourself, never push `develop`/`main`. Stop at **"ready for review"**.
- **Design calls are not yours.** If the brief is ambiguous, a rule would have to change, or something the task relies on turns out to be wrong, stop and report rather than choosing.
- **No drive-by refactors.** Touch only what the task names.

## Reports

- Write the full final report to `reports/<task>-<YYYY-MM-DD>.md` inside your worktree, **untracked**, with the same content as your chat summary.
- Include root cause / what changed, files touched, test results, and anything you were unsure about.
- End the chat reply with the **full-suite result line**.

## Testing

- Tests run on **mongomock**; no `.env` needed.
- Run **targeted** tests while iterating.
- Run the **full suite once** at the end with the **default** pytest config: `../gob-simplified/.venv/bin/python -m pytest -q`. No extra flags; `-p no:logging` breaks every `caplog` test.
- Compare against [tests/known_failures.py](tests/known_failures.py): known reds are skipped/xfailed there, so any `FAILED`/`ERROR` is new, and an `XPASS` means a known failure started passing (report it, don't edit the list unless asked).
- `tests/conftest.py` **overrides auth for every test** (fake user). If a change touches auth or ownership, say so, and test the real dependency explicitly.
- A new test should fail on the old code: verify by reverting the fix and re-running it.

## Data safety

- **Never write to the production DB (`gob`).**
- Read-only diagnostics against a real DB: `GOB_DB_ACCESS=read`.
- **Staging (`gob-staging`) writes only when the task explicitly says so.** Never delete or replace existing documents.
- Scripts connect through `BackEnd/script_db.py` (`connect_script_database`); destructive production access requires `--confirm-db <target>`.
- Detail: [Environment_Operations.md](_documentation_master/00_Operations/Environment_Operations.md), [SECURITY_BASELINE.md](_documentation_master/SECURITY_BASELINE.md).

## Deploys

- `develop` → staging, `main` → production (Netlify + Railway).
- **Nothing merges to `main` without Jamie.**
- Runbook: [Deploy_To_Live_System.md](_documentation_master/00_Operations/Deploy_To_Live_System.md).

## Persistence adapter rule

A **new collection** must be registered in **all** of these places, or on desktop it silently becomes `RemoteUnavailable`:
- `LOCAL_COLLECTIONS` or `REMOTE_COLLECTIONS` in `BackEnd/persistence/sqlite.py`
- `_COLLECTION_BINDINGS` in both `BackEnd/persistence/sqlite.py` and `BackEnd/persistence/mongo.py`
- `BackEnd/persistence/protocol.py`

Code must work on both Mongo (hosted) and SQLite (desktop).

## Engine rule

- Engine randomness goes through `BackEnd/utils/sim_random` (`sim_rng`), **never the global `random` module** (pymongo consumes global RNG; a guard logs stray draws).
- Other subsystems use their own streams (e.g. training uses `BackEnd/utils/training_random`).
- The **equiv-v3 reference fingerprints must stay byte-identical** unless the task says the change is meant to move them. The runner is `scratch_equiv3_fbdedupe.py`; references live under `_documentation_master/projects/references/`.

## CI migration gates

`scripts/ci/check_migration_gates.py` runs in CI and freezes the desktop-migration pile; it may only shrink ([scripts/ci/README.md](scripts/ci/README.md)).
- **Gate A:** don't add `from BackEnd.db import ...`. Use the persistence adapter (`from BackEnd.persistence import get_store`; `_store = get_store()`).
- **Gate B:** don't add `URLSearchParams` / `location.search` / `.searchParams` reads for franchise identity (`franchise_id`, `team_id`, `runtime`, `game_id`, ...) outside `FrontEnd/static/js/shared/franchiseContext.js`. Read `window.FranchiseContext`, which is also correct on desktop.
- **Never run `--write-allowlist` to paper over a new violation** without Jamie's approval. It is only for tightening after a real removal.

## Don't commit

- `scratch_*.py`: never commit new ones, and never delete existing ones (some are live tools, e.g. the equiv-v3 runner).
- Logs (`*.log`), `tmp/`, `.arm/`, `.DS_Store`, local DB files (`*.sqlite` other than the `base_league`/`catalog` bundles), large binaries, `.env*` (except `.env.example`).
- Reports under `reports/`.

## Frontend

- UI, colour and live-gameplay screen rules: [_documentation_master/00_Agent_Docs/CLAUDE.md](_documentation_master/00_Agent_Docs/CLAUDE.md). Follow it; don't restate or re-map the RT/energy/momentum ramps.
- Shell, navigation and settings construction: [UX_System.md](_documentation_master/11_Design_Systems/UX_System.md).
- Don't touch frontend/UX files unless the task says so.

## Further reading

- Architecture, scope and engineering playbook: [docs/agents.md](docs/agents.md)
- Known bugs and test-suite hygiene: [_documentation_master/projects/bugs.md](_documentation_master/projects/bugs.md)
- Manual QA: [Manual_QA_Checklist.md](_documentation_master/00_Operations/Manual_QA_Checklist.md)
