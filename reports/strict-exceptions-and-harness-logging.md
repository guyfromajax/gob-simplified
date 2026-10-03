# Harness stderr capture + `GOB_STRICT_EXCEPTIONS`

Two additive changes that make a Stage-2-class bug loud instead of silent.

**Both verification runs are clean: 240/240 with strict unset, 240/240 with strict on.** The
engine change is inert in production, and 240 games of strict mode surfaced **zero** programming
errors in the sim.

**Strict mode did surface something — in the test suite.** Five tests now fail with a real
`AttributeError` that a broad handler has been hiding. It is a **test-fixture gap, not a
production bug**, and per the brief I have reported it rather than fixed it or weakened anything.

---

## Footing (Rule 6e)

| | |
|---|---|
| Branch | `feature/animation-reward`, on `ca374fcd5` |
| Worker | `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5 |
| Env | `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process, game id `0xE0000+(seed−8000)` |
| **Defenses catalogue** | **`SEED_DEFENSES=1` — production footing, seeded.** The main reference also covers `SEED_DEFENSES=0`. |
| References | `equiv_v3_reference_f600628a4_agspread.json` (160 cells) + `equiv_v3_loose_baseline_f600628a4_agspread.json` (80) = **240** |
| Spread flag | `GOB_DEFENDER_AG_SPREAD` unset = ON, the shipped default |

---

# PART A — the harness stops throwing the evidence away

## The clean-run inventory (this had to come first)

I ran 6 healthy cells (seeds 8000–8002 × both arms, SD=1) with stdout and stderr captured
separately, and inventoried what a **healthy** run emits:

| | |
|---|---|
| stderr per cell | ~105 KB, **≈730 lines** |
| total across 6 cells | **4,379 lines**, **343 distinct line shapes** |
| lines containing `failed` | **45** |
| lines at `ERROR` level | **43** |
| lines containing `EMITTER EXCEPTION` | **0** |
| lines containing `build_skeleton_animation_steps` | **0** |
| lines containing `Traceback` | **0** |

The two shapes that would wreck a naive matcher, both **legitimate today**:

```
ERROR:root:❌❌❌ [HCO ENTRY BUG] current_bh_id is None — prior turn failed to stamp a final
           ball handler … Falling back to minimum walk-up                      (43 occurrences)
WARNING:root:Final Turn anchor verification failed after emit (shot_type=Outside, step_count=N)
                                                                                (2 occurrences)
```

> Matching on `failed`, or on `ERROR` level, would fire **45 times on every clean run**. A gate
> that cries wolf gets switched off, so the matcher is anchored to the emitter wrappers' own
> wording instead.

## The matcher

In `scratch_equiv3_fbdedupe.py`:

```python
EMITTER_FAILURE_RE = _re.compile(
    r"EMITTER EXCEPTION"                              # RR / TRIANGLE / CR / AFTER_STEAL
    r"|build_[A-Za-z_]+(?:\s*\([^)]*\))?\s+failed"    # "build_skeleton_animation_steps (HCO) failed"
    r"|Traceback \(most recent call last\)"           # logging.exception, and strict mode
)
```

The `build_` prefix is what keeps the two legitimate lines out — neither
`prior turn failed to stamp` nor `Final Turn anchor verification failed` is preceded by it.

Validated both directions:

| input | result |
|---|---|
| the clean 6-cell corpus (4,379 lines) | **0 false positives** |
| `build_skeleton_animation_steps (HCO) failed: name 'pid' is not defined` | trips ✓ |
| `🚨 [RR EMITTER EXCEPTION] result_type=MAKE: …` | trips ✓ |
| `build_dynamic_hct_animation_steps failed: x` | trips ✓ |
| `Traceback (most recent call last):` | trips ✓ |
| `[HCO ENTRY BUG] … prior turn failed to stamp …` | **passes** ✓ |
| `Final Turn anchor verification failed after emit` | **passes** ✓ |

## How the gate works, and where it lives

The fix is **in the worker, not in a shell script**. There is no runner in the repo — only
`scratch_equiv3_fbdedupe.py` — so a shell-level `tee` would have lived in per-session
scaffolding and evaporated. Instead:

1. A `logging.Handler` on the **root logger** at WARNING+ collects matching records into
   `EMITTER_FAILURES`, including the formatted traceback when the record carries `exc_info`
   (which is what `logging.exception` produces). It is wrapped so it can never raise.
2. In `__main__`, **after** the payload is written, a non-empty list writes
   `<OUT>.emitterfail.log`, prints the first three to stderr, and **exits 3**.

The payload is written first so a failing cell is still inspectable; the non-zero exit is what
a runner keys on. This catches the records **in-process**, so a shell redirect cannot hide them
— which is the actual Stage 2 failure mode.

Separately, the per-cell runner now redirects to `"$OUT.out"` and `"$OUT.err"` instead of
`/dev/null`, and appends any non-zero exit to a `FAILURES.txt` in the output directory.

**Where the logs land:** next to `$OUT` — in the scratchpad, **outside the repo tree**. No
`.gitignore` entry is needed or was added; nothing about this writes into the working copy.

## It does not change what is measured

Proven by **run 1 below: 240/240 on fingerprint AND draws.** The gate only observes log records.

---

# PART B — `GOB_STRICT_EXCEPTIONS`

## The helper — `BackEnd/utils/strict_exceptions.py` (new)

```python
STRICT_EXCEPTION_TYPES = (NameError, AttributeError, TypeError, UnboundLocalError)

def strict_exceptions_enabled() -> bool:
    return os.environ.get(STRICT_EXCEPTIONS_FLAG, "0") == "1"   # DEFAULT OFF

def reraise_if_strict(exc):
    try:
        if not isinstance(exc, STRICT_EXCEPTION_TYPES): return
        if not strict_exceptions_enabled(): return
    except Exception:
        return          # a guard that corrects must not become the fault
    raise exc
```

**Default OFF** — unset is today's behaviour exactly. This is deliberately the opposite default
from `GOB_DEFENDER_AG_SPREAD`; the `"1"` idiom was not copied.

**The flag is read at CALL TIME, through `os.environ`, not captured into a module constant at
import.** Two reasons, both from the audit: these handlers only execute when an exception has
already fired (~0 times per game per the census), so there is no hot path worth optimising; and
an import-time constant cannot be monkeypatched, which would make the whole thing untestable.
The B5 sketch suggested import-time — that was wrong, and this is the correction.

Unit-checked: re-raises `NameError` / `AttributeError` / `TypeError` / `UnboundLocalError` when
on; returns for `KeyError` / `ValueError` / `ZeroDivisionError`; returns for a `None` argument;
returns for everything when off.

## Handlers wired: **86, not 66**

> **The audit under-counted.** `reports/rebaseline-and-handler-audit.md` reported 66 because its
> static sweep did not include `BackEnd/models/turn_manager.py` — which holds **20** more, and is
> **exactly where the Stage 2 catcher lives** (`turn_manager.py:4107`). The audit found that
> handler by *reproduction*, not by the sweep, which is why the gap did not show at the time.
> 66 + 20 = 86. Every one is now wired.

| file | handlers | file | handlers |
|---|---|---|---|
| `phase_resolution.py` | 28 | `fb_drive_step_emitter.py` | 2 |
| `turn_manager.py` | **20** | `fb_outlet_pass_step_emitter.py` | 2 |
| `animation_step_helpers.py` | 5 | `rim_runner_drive_integration.py` | 2 |
| `dynamic_hct_shot.py` | 4 | `skeleton_step_emitter.py` | 2 |
| `rim_runner_step_emitter.py` | 4 | `after_steal_fast_break_step_emitter.py` | 1 |
| `after_steal_drive_integration.py` | 2 | `dreb_step_emitter.py` | 1 |
| `after_steal_fast_break.py` | 2 | `dynamic_fcp_step_emitter.py` | 1 |
| `covert_release_step_emitter.py` | 2 | `fb_uess_debug.py` | 1 |
| `dynamic_hct_step_emitter.py` | 2 | `ft_step_emitter.py` · `hct_step_emitter.py` · `oreb_step_emitter.py` · `triangle_step_emitter.py` · `animator.py` | 1 each |

**No handler was narrowed, removed, or had its caught types changed.** 38 already bound a name
and kept it; the call uses whatever name is there.

## The 48 `except` lines where `as e` was added

The only permitted edit to an except line, applied where the handler had no binding:

| file | sites | file | sites |
|---|---|---|---|
| `phase_resolution.py` | 11 | `dynamic_hct_step_emitter.py` | 2 |
| `turn_manager.py` | 6 | `rim_runner_drive_integration.py` | 2 |
| `animation_step_helpers.py` | 5 | `after_steal_fast_break.py` | 1 |
| `rim_runner_step_emitter.py` | 4 | `after_steal_fast_break_step_emitter.py` | 1 |
| `after_steal_drive_integration.py` | 2 | `dreb_step_emitter.py` | 1 |
| `covert_release_step_emitter.py` | 2 | `dynamic_fcp_step_emitter.py` | 1 |
| `dynamic_hct_shot.py` | 2 | `fb_drive_step_emitter.py` · `fb_outlet_pass_step_emitter.py` · `ft_step_emitter.py` · `hct_step_emitter.py` · `oreb_step_emitter.py` · `skeleton_step_emitter.py` · `triangle_step_emitter.py` · `animator.py` | 1 each |
| | | **TOTAL** | **48** |

### The shadow-deletion check I ran before doing this

`except ... as e:` ends with an implicit `del e`. If a function already had an `e` bound and
used it *after* the block, adding `as e` would delete it — a silent behaviour change of exactly
the class this whole exercise exists to prevent.

A first pass flagged **7 apparent collisions**. On inspection all 7 were *another* `except`
handler's own binding, which is independently scoped. Re-running the check while excluding
other handlers' bindings gave **0 true collisions**, so `as e` is safe at all 48 sites.

The diff confirms it: every changed line is either an inserted `reraise_if_strict(...)`, an
inserted import, or exactly `except Exception:` → `except Exception as e:` (48 of them,
trailing comments such as `# pragma: no cover` preserved). Nothing else moved.

`tests/conftest.py` sets `GOB_STRICT_EXCEPTIONS=1` via `setdefault`, so a test that needs
production behaviour can still export `"0"` for itself.

---

# Verification

## Run 1 — `GOB_STRICT_EXCEPTIONS` unset · **240/240**

```
  main reference         160/160    (SD=1 and SD=0, sim and played)
  loose baseline          80/80
  RUN 1 TOTAL            240/240    fingerprint AND draws
  emitter-failure sidecars: 0       non-zero cell exits: 0
```

**The change is inert in production.** This was the gate; it passed.

## Run 2 — `GOB_STRICT_EXCEPTIONS=1` · **240/240**

```
  main reference         160/160
  loose baseline          80/80
  RUN 2 TOTAL            240/240    fingerprint AND draws
  non-zero cell exits: 0            emitter-failure sidecars: 0
  strict-type exceptions in cell stderr: 0
```

> **The wide census found nothing.** 240 games — 40 seeds × both arms × both footings — with
> every one of the 86 handlers re-raising `NameError`, `AttributeError`, `TypeError` and
> `UnboundLocalError`, produced **zero**. The 8-game census in the audit was not missing
> anything at 30× the sample.

## Full suite — **5 failed, 3,567 passed**

This is the finding.

```
FAILED tests/test_final_turn_coordinate_contract.py::test_final_turn_attack_shot_unwraps_attack_drive_steps
FAILED tests/test_final_turn_coordinate_contract.py::test_final_turn_attack_step0_floor_stamps_hold
FAILED tests/test_final_turn_coordinate_contract.py::test_final_turn_outside_step0_floor_stamps_hold
FAILED tests/test_final_turn_pacing.py::test_pacing_hold_floor_accounts_for_move_beats
FAILED tests/test_final_turn_pacing.py::test_resolve_reuses_gate_shooter_without_repick
```

All five share **one** root cause:

```
  reraise_if_strict(_ft_sync_err)
BackEnd/utils/strict_exceptions.py:76: in reraise_if_strict
    raise exc
E   AttributeError: 'types.SimpleNamespace' object has no attribute 'strategy_calls'
BackEnd/engine/defender_placement.py:1030: AttributeError
```

- **Raise site** — `defender_placement.py:1030`:
  `aggression = game.defense_team.strategy_calls.get("aggression_call", "normal")`
- **Catching handler** — `phase_resolution.py:8407`, `except Exception as _ft_sync_err:`,
  the Final Turn UESS single-coord-source animator build. Its own comment documents the intent:
  *"if the build or coord-sync fails, fall back to the prior behavior (emitter rebuilds later)
  rather than crashing the final-turn resolution."*

### What it means — and why I did not fix it

The object is a `types.SimpleNamespace`: a **test stub** that does not carry `strategy_calls`.
Run 2 is the control — with real game objects, across 240 games, this `AttributeError` never
occurs. So this is a **test-fixture gap, not a production bug**.

But it is a real finding, and a useful one: **those five tests have been silently exercising the
*fallback* path, not the path their names describe.** The animator build they appear to cover
has been failing and being swallowed for as long as the stub has been incomplete. Strict mode is
working exactly as intended — it made a hidden failure visible.

Per the brief I have **not** weakened a test, **not** exempted the handler, and **not** completed
the stub. The fix (giving the fixture a `strategy_calls` mapping) is a separate task, and whoever
does it should re-run these five and check they still assert what they mean to.

---

## Anything that did not behave as expected

1. **86 handlers, not 66.** The audit's static sweep omitted `turn_manager.py`, which holds 20
   — including the one that caught the Stage 2 error. Corrected above; the audit's own
   conclusions are unaffected because it identified that handler by reproduction.
2. **Healthy runs are far noisier than expected** — 4,379 stderr lines per 6 cells, 45 containing
   `failed` and 43 at ERROR level, including an `ERROR ❌❌❌ [HCO ENTRY BUG]` that fires 43 times
   on a clean run. **That ERROR is pre-existing and out of scope here, but it is worth its own
   look:** a log line that shouts on every healthy run trains people to ignore the channel.
3. **Strict mode found nothing in 240 games but five things in the suite.** The right way round —
   production is clean, the test fixtures are not.
4. **The 7 apparent `as e` collisions were all false positives** on first analysis. Had I acted on
   the first pass I would have introduced exactly the class of silent breakage this change exists
   to prevent.
