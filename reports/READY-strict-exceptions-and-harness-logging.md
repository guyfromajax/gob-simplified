# READY — strict exceptions + harness gate: both runs 240/240, and strict mode found 5 real things

Report: `reports/strict-exceptions-and-harness-logging.md`. Branch `feature/animation-reward`,
on `ca374fcd5`. Verified against the brief by Claude.

## Result

**Run 1 (`GOB_STRICT_EXCEPTIONS` unset): 240/240**, fingerprint AND draws, 0 emitter-failure
sidecars, 0 non-zero cell exits. The change is inert in production — that was the gate.

**Run 2 (`GOB_STRICT_EXCEPTIONS=1`): 240/240**, and **zero** strict-type exceptions across 240
games (40 seeds x both arms x both footings) with all 86 handlers re-raising. The 8-game census
in the audit was not missing anything at 30x the sample. Production is clean.

Rule 6e footing: worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 /
traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process,
`SEED_DEFENSES=1` production footing, `GOB_DEFENDER_AG_SPREAD` unset = ON.

## THE FINDING — 5 tests were exercising the fallback path, not the path they are named for

Suite: 5 failed / 3,567 passed. All five share ONE root cause:

```
AttributeError: 'types.SimpleNamespace' object has no attribute 'strategy_calls'
raise site:  defender_placement.py:1030
             aggression = game.defense_team.strategy_calls.get("aggression_call", "normal")
caught at:   phase_resolution.py:8407  except Exception as _ft_sync_err:
             (Final Turn UESS single-coord-source animator build; its comment says the intent is
             to fall back to prior behaviour rather than crash final-turn resolution)
```

Failing: `test_final_turn_attack_shot_unwraps_attack_drive_steps`,
`test_final_turn_attack_step0_floor_stamps_hold`,
`test_final_turn_outside_step0_floor_stamps_hold`,
`test_pacing_hold_floor_accounts_for_move_beats`,
`test_resolve_reuses_gate_shooter_without_repick`.

**It is a test-fixture gap, not a production bug** — Run 2 is the control: with real game objects
across 240 games this AttributeError never occurs. The stub is a `types.SimpleNamespace` that
does not carry `strategy_calls`.

**But it is a real and useful finding:** those five tests have been silently running the FALLBACK
path for as long as the stub has been incomplete. The animator build they appear to cover has
been failing and being swallowed. Strict mode did exactly its job.

Not fixed, per the brief. No test weakened, no handler exempted, stub not completed. **Follow-up
task: give the fixture a `strategy_calls` mapping, then re-run those five and check they still
assert what they mean to** — they may have been passing for the wrong reason.

## Handler count: 86, not 66 — the audit under-counted

The audit's static sweep omitted `BackEnd/models/turn_manager.py`, which holds **20** handlers
including **the one that caught the Stage 2 error** (`turn_manager.py:4107`). The audit found that
handler by reproduction rather than by the sweep, which is why the gap did not show. 66 + 20 = 86,
all now wired. The audit's conclusions are unaffected.

## The gate is in-process, not a shell redirect

Better than the brief asked. A `logging.Handler` on the root logger at WARNING+ collects matching
records in-process (including the formatted traceback when `exc_info` is present), writes
`<OUT>.emitterfail.log` and **exits 3**. The payload is written first so a failing cell stays
inspectable. **A shell redirect cannot hide these records — which was the actual Stage 2 failure
mode.** The per-cell runner also now redirects to `$OUT.out` / `$OUT.err` instead of `/dev/null`
and appends non-zero exits to `FAILURES.txt`. Logs land beside `$OUT` in the scratchpad, outside
the repo tree, so no `.gitignore` entry was needed.

## The matcher was built against evidence, not guessed

A healthy 6-cell run emits **4,379 stderr lines**, 343 distinct shapes, **45 containing `failed`**
and **43 at ERROR level**. Matching on `failed` or on ERROR level would have fired 45 times on
every clean run. Anchored instead to `EMITTER EXCEPTION`, `build_<name>(...) failed`, and
`Traceback (most recent call last)`. Validated both ways: 0 false positives on the clean corpus,
trips on all four real shapes, passes both legitimate `failed` lines.

## `as e` added at 48 sites — with a shadow-deletion check

`except ... as e:` ends with an implicit `del e`. If a function already had an `e` bound and used
it after the block, adding `as e` would silently delete it — exactly the bug class this change
exists to prevent. A first pass flagged 7 apparent collisions; all 7 were other handlers' own
independently-scoped bindings, so 0 true collisions. **Acting on the first pass would have
introduced the bug.** No caught type narrowed, no handler removed; the 38 that already bound a
name kept it.

## Flag design

`BackEnd/utils/strict_exceptions.py`, default **OFF** (deliberately the opposite of
`GOB_DEFENDER_AG_SPREAD` — the `"1"` idiom was not copied). Read at **call time** through
`os.environ`, not captured at import: handlers are cold (~0 calls/game) so there is no hot path
to optimise, and an import-time constant cannot be monkeypatched. `reraise_if_strict` is wrapped
so a guard that corrects can never itself become the fault. `conftest.py` uses `setdefault`, so a
test needing production behaviour can export `"0"`.

## SECOND FOLLOW-UP WORTH TAKING SERIOUSLY

A clean run logs this **43 times per 6 cells** (~7 per game), at ERROR level:

```
ERROR:root: [HCO ENTRY BUG] current_bh_id is None — prior turn failed to stamp a final ball
            handler ... Falling back to minimum walk-up
```

That is not just log noise. It says the turn chain is failing to stamp a final ball handler and a
fallback is papering over it, on every healthy game, and it has been shouting into a channel that
was piped to `/dev/null`. Pre-existing and out of scope for this task, but it deserves its own
audit — and a log line that fires on every clean run trains people to ignore the channel.

## Confirmed

Stage 3 defects (four `12.0` fallbacks, three missing `max(0.0, ...)` floors) untouched.

No merge by Claude. Jamie merges.
