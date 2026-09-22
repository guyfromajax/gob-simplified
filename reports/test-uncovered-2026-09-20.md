# The 7 uncovered test failures — fixed

Full suite after: **0 failed, 0 XPASS.** 2813 passed, 20 skipped, 112 xfailed.

Nothing was added to `tests/known_failures.py`, no assertion was loosened, and nothing was skipped. **One dependency install and one four-line test-hygiene fix account for all seven.**

`develop` is merged in (`db7628f25`, `git rev-list --count HEAD..develop` = 0).

## A. `test_alpha_access.py::test_check_access_code_rate_limit`

**Fixed by installing the dependency. No repo change.**

`slowapi>=0.1.9,<0.2` is line 18 of `requirements.txt`, so production has it. It was not in this venv. `BackEnd/api/auth_routes.py:25-30` wraps the import in `try/except Exception` and falls back to a no-op decorator:

```python
try:
    from BackEnd.utils.rate_limiter import limiter as _limiter, AUTH_RATE_LIMIT
    _auth_rate_limit = _limiter.limit(AUTH_RATE_LIMIT)
except Exception:
    def _auth_rate_limit(f):
        return f
```

With no limiter attached, no request is ever throttled, and the test's `assert 429 in statuses` saw `[200, 200, 200, …]`.

```
venv/bin/pip install "slowapi>=0.1.9,<0.2"   →  slowapi-0.1.10 (+ limits, deprecated, wrapt)
pytest tests/test_alpha_access.py::test_check_access_code_rate_limit  →  1 passed
```

Note `venv` here is a symlink to `/Users/jamesdavies/gob-simplified/venv`, so the install covers the main checkout and every worktree.

**This one dependency also explains part C.** See below.

## B. The six seam tests

`test_sa1_within_step_pass` ×1 and `test_unrendered_and_ball_seam` ×5 — passing alone, failing in a full run on assertions against an empty `caplog.text`.

### B1. What reconfigures logging

**Four test modules call `logging.disable(logging.CRITICAL)` at module scope:**

| file:line | |
|---|---|
| `tests/test_deferred_offseason.py:13` | |
| `tests/test_entry_tier_persistence.py:19` | |
| `tests/test_in_season_invariants.py:15` | `# execute_training is chatty` |
| `tests/test_offseason_attractor.py:18` | |

`logging.disable(level)` is a **process-wide** switch stored on `logging.root.manager.disable`. It is not a logger setting, it has no owner, and none of the four restored it. Because the calls sit at module scope they fire during **collection**, before any test runs — so from the moment pytest imports the first of them, every later test in the process gets no log records at all. `caplog.text` is `''`, not wrong.

**Production is clean.** Grepping all of `BackEnd/` outside `BackEnd/tests/` for `logging.disable`, `basicConfig`, `dictConfig`, `.propagate`, `removeHandler`, `handlers = [...]` and `root.setLevel` returns **nothing**. No production module reconfigures root logging as an import side effect, and none strips pytest's handler. The offender was test code, which is why the fix is in test code — see B3.

### B2. The minimal reproducing pair

```
pytest tests/test_deferred_offseason.py::test_week1_noop_when_no_marker \
       tests/test_unrendered_and_ball_seam.py::TestSyncReadsDrawable::test_final_ball_helpers_read_drawable
→ 1 failed, 1 passed
```

The same seam test **alone → 1 passed**. All four disabler modules reproduce it independently:

| paired with the 6 seam tests | result |
|---|---|
| seam tests alone | **27 passed** |
| `+ tests/test_deferred_offseason.py` | **6 failed** |
| `+ tests/test_entry_tier_persistence.py` | **6 failed** |
| `+ tests/test_in_season_invariants.py` | **6 failed** |
| `+ tests/test_offseason_attractor.py` | **6 failed** |

The pair above pins it to **import**, not to the test: `test_week1_noop_when_no_marker` itself touches no logging, and it is the module's import that trips the switch.

### B3. The fix, and why it is in the test

The offending code **is** test code, so there is no source to fix — but the fix still follows the rule the brief states, because the defect is the same one: a global reconfiguration performed as an import side effect, with no restore.

Each of the four now scopes the silence to its own tests:

```python
@pytest.fixture(autouse=True)
def _quiet_chatty_training_logs():
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(previous)
```

The previous value is restored rather than `NOTSET`, so nesting cannot clobber an outer disable.

**Evidence that the module-scope placement bought nothing.** The `logging.disable` lines sat *above* the `BackEnd` imports, which would only matter if importing those modules logged. Instrumenting the root logger at level 0 and importing everything the four files import — `player_development`, `training_execution_v2`, `player_generation`, `franchise_routes` — emits **0 log records**. The pre-import placement suppressed nothing that existed; it only leaked. (The `🔵 [DEBUG] db.py` lines are `print`, not logging, and `logging.disable` never affected them.)

The authors' intent — quiet output while these chatty tests run — is preserved exactly, and all 19 of their tests still pass.

### B4. The guards still bite

**The assertions were not weakened.** Proved by poisoning the source and confirming the guards fail.

**Poison 1 — the behavioural defect (item 41/42).** Make `last_rendered_step` return the array tail instead of the last drawn step, i.e. read the ghost:

```python
return len(steps) - 1, steps[-1]   # POISON
```

→ **2 failed**: `test_sync_reads_the_drawn_step_not_the_ghost` and `test_final_ball_helpers_read_drawable`, with `- drawn / + ghost`. Exactly the defect they exist to refuse.

**Poison 2 — the silent repair.** Rename the guard's warning prefix so the announcement no longer names the tail:

→ **2 failed**: `test_poison_appended_after_turn_stop_is_named` and `test_sync_reads_the_drawn_step_not_the_ghost`.

Both poisons reverted; the files are byte-identical to `HEAD` (`git status` shows nothing outside `tests/`).

**And a regression guard so the global form cannot come back.** `tests/test_logging_isolation.py` walks every `tests/**/test_*.py` with an AST visitor that skips function and class bodies — so it flags only calls reachable at import — and fails on `logging.disable`, `logging.basicConfig`, `logging.shutdown`, `logging.config.dictConfig` and `fileConfig` at module scope. Four tests back it:

- the exact poisoned line is detected at its line number
- a `basicConfig` inside a module-level `try:` is detected (the visitor descends into `if`/`try`/`with`)
- the scoped-fixture form is **not** flagged
- a runtime check that importing a quieting module leaves `logging.root.manager.disable == 0` and that `caplog` still captures afterwards

## C. The two "over-covered" XPASS entries — I was wrong, and they stay

**Do not remove them.** My previous report called them over-covered; that was an artifact of the same missing dependency as part A.

| id | before this pass | after installing slowapi |
|---|---|---|
| `test_simulate_quarter_endpoint.py::test_simulate_quarter_restores_team_stats_from_unified_teams` | XPASS | **XFAIL** |
| `test_simulate_quarter_endpoint.py::test_simulate_quarter_restores_team_stats_from_legacy_team_fields` | XPASS | **XFAIL** |

Their listed reason is *"broken-harness: request must be a Starlette Request"*, and it is accurate. The tests drive the endpoint with `api.QuarterSimulationRequest`, a pydantic model, not a Starlette `Request`. With slowapi absent, `_auth_rate_limit` degraded to a no-op and the endpoint accepted the pydantic object, so the tests passed and showed as XPASS. With slowapi present — the production configuration — the limiter requires a real Starlette request and the tests fail as listed.

So `known_failures.py` was right about these two all along; my machine was wrong. **Both entries stay.** The `XPASS` count in the final run is **0**.

### Is making the xfails strict advisable?

**Not yet — and this pass is the reason.** `strict=False` means an entry that starts passing shows as XPASS and does not fail the suite; `strict=True` would turn that XPASS into a failure, forcing the list to be pruned.

The hygiene argument for strict is real: non-strict entries rot silently, and a fixed test can sit on the list forever. But these two ids flipped between XPASS and XFAIL **purely on whether one dependency was installed**. Under `strict=True` every developer without `slowapi` would get two hard failures for tests that are correctly listed, and the node-loader and mongomock skips are the same class of environment sensitivity.

**Recommendation: pin the environment first, then flip.** Once a `pip install -r requirements.txt` is a precondition for running the suite and the node/mongomock harness gaps are closed, `strict=True` is the right setting and XPASS becomes a real signal. Flipping it today would trade one uncovered-failure problem for an environment-dependent one. **I have not changed strictness.**

## The 129, line by line

`reports/test-triage-2026-09-19.md` listed 129 failing ids.

| | count | status now |
|---|---|---|
| covered by `known_failures.py`, **xfail** | **109** | still red, still listed, correctly suppressed |
| covered by `known_failures.py`, **skip** | **13** | 5 node `--loader` + 6 node ESM + 2 mongomock `$replaceAll`; still environment-gated |
| **uncovered** | **7** | **all fixed in this pass** — 1 by the slowapi install, 6 by the logging-isolation fix |
| **total** | **129** | |

| id | was | now |
|---|---|---|
| `test_alpha_access.py::test_check_access_code_rate_limit` | failed everywhere | **passes** — slowapi installed |
| `test_sa1_within_step_pass.py::TestSeamGuard::test_poison_truncate_without_carry_fires` | passed alone, failed in a full run | **passes** |
| `test_unrendered_and_ball_seam.py::TestUnrenderedTail::test_poison_appended_after_turn_stop_is_named` | same | **passes** |
| `…::TestSyncReadsDrawable::test_sync_reads_the_drawn_step_not_the_ghost` | same | **passes** |
| `…::TestSyncReadsDrawable::test_final_ball_helpers_read_drawable` | same | **passes** |
| `…::TestBallOwnerSeam::test_item_47_poison_names_step_owners_and_family` | same | **passes** |
| `…::TestPostStealPrematureAttach::test_poison_start_attached_stealer_is_named` | same | **passes** |

Plus the 2 entries in `known_failures.py` that were **not** in the 129: both now XFAIL rather than XPASS, explained in part C.

**The final run reconciles exactly:** 112 xfailed = 111 `XFAIL` entries + 1 pre-existing in-test `@pytest.mark.xfail`. 20 skipped = 13 known-failure skips + 7 pre-existing. 2813 passed = the previous 2801 + the 7 fixed here + the 5 new logging-isolation tests.

## D. Neutrality

**No file outside `tests/` changed.** `git status` against `HEAD` lists only the four test modules and the new guard file, so the engine is untouched by construction.

The one non-repo change — installing `slowapi` — *does* alter an import path (`BackEnd/api/api.py:473` now succeeds), so it was verified rather than assumed:

| cell | arm | fingerprint | draws | errors |
|---|---|---|---|---|
| `SEED_DEFENSES=1` | sim | **40/40** | **40/40** | 0 |
| `SEED_DEFENSES=1` | played | **40/40** | **40/40** | 0 |
| `SEED_DEFENSES=0` | sim | **40/40** | **40/40** | 0 |
| `SEED_DEFENSES=0` | played | **40/40** | **40/40** | 0 |

against `equiv_v3_reference_ec4f5acfc_poslookup2.json`, which **remains current**.

| gate | result |
|---|---|
| independence (seed 8000 × 3 processes) | **PASS** in all four cells |
| **§8.1 coord-continuity corrections** | **0 across 160 games** |
| FT-honour windowed | sim 99.8% / 99.8%; played 99.7% / 99.7% — unchanged |
| FT-honour strict | 95.9–96.6% — unchanged |
| errors across 160 games | **0** |

**Nothing retuned.**

### Footing (rule 6e)

equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, n=40 seeds 8000–8039, CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`. **sim arm** = `_is_full_simulation` **True** throughout; **played arm** = **False only inside the four gated Animator methods** at Pattern A.

## Reported, not fixed

1. **The suite depends on an unpinned dev environment.** Three of the failure classes here and in the triage — slowapi, the node `--loader` harness, mongomock's missing `$replaceAll` — are all "the machine is not set up", and they are indistinguishable from real reds until someone checks. A documented `pip install -r requirements.txt` precondition (and a node harness check) would let `known_failures.py` shrink to genuine reds and make `strict=True` safe.
2. **`known_failures.py` was built from per-file runs.** That is why exactly the order-dependent tests were missed: run their files alone and they are green. Any future rebuild of that list should come from a single full-suite run.
3. **`BackEnd/tests/test_potential_factor.py` and `BackEnd/tests/test_training_system.py`** also reconfigure logging at module scope (`logging.disable`, `basicConfig`). They are not collected by `pytest tests/`, so they did not contribute here, and the new guard only walks `tests/`. Worth the same treatment if `BackEnd/tests/` is ever added to the run.
