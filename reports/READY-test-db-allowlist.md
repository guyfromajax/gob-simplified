# READY — test-db-allowlist.md (verified)

Verified 2026-09-25. **Accepted.** Branch `feature/test-db-allowlist` off develop `9f07d5650`
(develop had moved again from e4ff0d78e; the agent noticed and said so). Not merged.

## Verified myself, not taken from the report
- The old `_BLOCKED_DB_NAMES` deny-list is **gone from both conftests** — grepped, zero hits.
- Both conftests import the single shared module: `tests/conftest.py:49` and
  `BackEnd/tests/conftest.py:47`, both `from tests.db_guard import enforce`. The third-tree warning
  in BackEnd/tests/conftest.py's docstring is now structurally satisfied rather than a comment.
- Mock detection reads `type(obj).__module__.split(".")[0] == "mongomock"` on the live handle,
  then its client, then a bounded depth-4 unwrap. Not GOB_DB_MODE, not USING_MONGOMOCK (which is
  that env var renamed at persistence/mongo.py:96), not the name.
- `env_config.py:143-146` and `:191-199` confirmed by reading them directly — see the correction
  below.

## A CORRECTION TO WHAT I TOLD JAMIE
I told him his `.env.local` setting `MONGO_DB_NAME=gob-staging` meant his ordinary mongomock runs
carried a disallowed name, and that mock detection getting this wrong was the main risk of the
change. **That scenario was already impossible.** `BackEnd/env_config.py` raises
`"GOB_DB_MODE=mongomock requires ENVIRONMENT=test"` and
`"Mongomock database name must not be gob or gob-staging"`, and pins ENVIRONMENT → MONGO_DB_NAME
(development/staging → gob-staging, production → gob). A mongomock store simply cannot be named
gob-staging. The agent found this and stated it plainly in §7 rather than letting my framing stand.

The design conclusion is unchanged — mock-first ordering is still correct, and the allow-list is
still the right shape — but the REASON is different from the one I gave. The gap the deny-list
actually left is REAL-connection names it did not anticipate, not mock ones.

## The evidence that makes this worth merging
**`gob2` — a one-character typo of production — was PERMITTED by the old deny-list and is refused
now.** So is `gob-remote-memory`, which is a genuine remote client (`persistence/sqlite.py:271`)
carrying a name that reads disposable. That pair is the concrete case for the change.

**Poison tests, all four caught** — the flag-registry discipline applied properly:

| poison | tests that failed |
|---|---|
| revert to the deny-list | 4 |
| infer mock-ness from `GOB_DB_MODE` | 1 |
| widen the pattern to `^gob-` | 2 |
| escape hatch defaulting ON | 6 |

**End-to-end against real connections, not only unit tests:** real `gob-staging` refused, real
`gob-remote-memory` refused, real `gob2` refused, escape hatch lets `gob-staging` through with a
loud banner naming the database, and real `gob-test` is allowed by the guard then fails on a
genuine connection error — which proves the allowed-name branch is reachable rather than dead code.
That last one is the check most people would skip.

13 guard tests total, including anchoring (`agob-test`, suffix smuggling), a self-referential proxy
termination test so the guard cannot become its own outage, and `None` refused rather than treated
as a free pass.

## The pattern
`^gob-(?:test|scratch-test)(?:-[A-Za-z0-9._-]+)?$` — alternation rather than a prefix, because
`startswith("gob-test")` would have missed `gob-scratch-test`. Optional suffix admits per-worker
databases for parallel runs. Anchored both ends. Ambiguous names left disallowed:
`gob-s11-league-convergence` was the tempting one and is script-only, covered by the escape hatch
if ever needed.

## Gates — all passed
| gate | result |
|---|---|
| `pytest` (root) | 3,664 passed / 20 skipped / 110 xfailed |
| `pytest tests/` | 3,421 passed |
| `pytest BackEnd/tests/` | 243 passed |
| single file inside `BackEnd/tests/` (the IDE-gutter-click case) | 8 passed, **still guarded** |
| equiv-v3 | 240/240, fp+draws 480/480, 0 mismatches |
| seed 8000 played SD=1 | fp `0c3389cd41d0bbef`, draws `75363` ✓ |

The 3,421 for `tests/` is lower than the 3,651–3,712 on other recent branches because this branch
sits on a different develop tip and does not carry the flag-registry or depth-ordering test
additions. 3,421 + 243 = 3,664 reconciles exactly — the agent flagged the discrepancy itself
rather than leaving it to be noticed.

Rule 6e correctly scoped to the equiv-v3 row only.

## Scope held
The dozen-plus files calling `delete_many({})` are untouched — injecting collections via fixtures
instead of importing module globals remains the larger structural fix and is NOT started.
`.env.local`, `.env.example`, and the GOB_DB_MODE / GOB_DB_ACCESS / GOB_PERSISTENCE defaults are
all unchanged. No test assertion changed.

## Reported, not fixed (as instructed)
`GOB_PERSISTENCE` is read at three sites with two different defaults: `env_config.py:82` (the
authoritative one, reading a pristine pre-dotenv snapshot) defaults to `"mongo"`, while
`api/_bootstrap.py:60` and `loopback_app.py:50` read live `os.environ` and default to `"sqlite"`.
Both `"sqlite"` reads are health-payload REPORTING inside an `is_loopback()` branch, so with the
var unset a loopback `/health` can report `sqlite` while the resolved store is `mongo`. It does not
affect which store the guard sees — the guard reads the live `BackEnd.db` handle built once from
the `env_config` resolution.

## Unverified
Parallel/xdist per-worker databases. The pattern admits `gob-test-w1` but nothing in the repo
creates one, so that arm is unexercised.

## Still open elsewhere
- `feature/flag-registry` merge, parked under Operations.
- The palette-null fragility fix, still only on `feature/depth-ordering-fix`, unmerged.
- Landmine: `guard_ball` depends on `GOB_LINEUP_POSITION_LOOKUP`, #19 on the retirement list.
- `turns_fingerprint` hashes only `(result_type, next_turn)` + score — equiv-v3 is a RESULTS gate,
  not an animation gate.
