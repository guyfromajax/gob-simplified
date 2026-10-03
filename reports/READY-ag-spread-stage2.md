# READY — AG spread stage 2: divergence closed, no outcome effect, ready for a default decision

Report: `reports/ag-spread-stage2.md`. Branch `feature/animation-reward`, on top of `c56abfe43`
(develop merged into the branch first — docs/review markers only). Verified against the Stage 2
brief by Claude.

## Headline

**Screen-vs-game divergence: 7.95% -> 0.0221%** (147 of 666,385 placements), which is BELOW the
0.0301% floor the engine already has with the flag off. That was the entire purpose of Stage 1
and it worked. The residue is the pre-existing ball-chase class (sprint-archetype placements put
on the BALL's trajectory, not the defender's rate) — untouched, Stage 3+ work.

`GOB_DEFENDER_AG_SPREAD` unchanged at **s = 0.50**, the value already in the code. Nothing tuned.

## Flag OFF — the gate

160/160 on `equiv_v3_reference_1f4af0ede_loosesag_nogate.json` (SD=1 and SD=0, sim and played)
and 80/80 on the loose baseline, fingerprint AND draws. Seed 8000 = fp `a1d150579771387a`,
draws `77689`. Full suite 3,570 passed / 0 failed.

Rule 6e footing stated throughout: worker `scratch_equiv3_fbdedupe.py`, Lancaster vs
Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game
per process, `SEED_DEFENSES=1` production footing.

## The gate caught a real bug — first build was 0/160

Every cell, both arms, fp and draws. Cause: `shot_micro_movements.build_shot_micro_steps` passed
the loop variable `pid` where the player was `defender_player` / `defender_id`. `pid` belongs to
earlier loops in the same 293-line function and is UNBOUND on the path that reaches the defender
clamp. **70 NameErrors per game**, raised while evaluating the argument list and **swallowed by
a handler upstream**, which silently skipped the defender clamp and moved the whole game.

Same class as the prior `triangle_step_emitter` incident. Invisible to unit tests and to
function-level equivalence checks; only the reference run caught it. The agent stopped and
diagnosed rather than adjusting anything, as instructed.

Guarded now by `test_the_id_passed_is_the_id_the_player_was_looked_up_with`: when the player
comes from `_player_lookup_by_id(off, def, X)` the id passed must be X. Audit of all 13 sites
found 0 remaining mismatches.

**SEPARATE LATENT HAZARD, worth its own task:** there is a handler upstream that swallows
NameErrors and silently skips work. That is why 70 exceptions per game produced no visible
error. This is a general hazard, not specific to Stage 2.

## Geometry — the spread is visible, but not everywhere

n=40, both arms, SD=1, moving placements only (the definition that reproduces the stated 0.35
baseline — measured 0.347 flag-off, confirming like-for-like).

| | flag OFF | flag ON (s=0.50) |
|---|---|---|
| mean p10->p90 arrival gap | 0.347 grid | **1.896 grid** |
| median | 0.000 | 0.000 |
| p90 | 1.031 | 5.455 |
| above the ~0.5-unit visibility floor | 26.9% | **40.6%** |
| above 1.0 unit | 10.3% | 38.0% |

**Read this honestly: on ~41% of moving placements a p10-AG and a p90-AG defender now end at
least half a cell apart; on ~59% they end in the same place.** The median is still 0.000 because
most moving placements have a short enough target that both defenders arrive fully and the rate
never binds. Built, no longer imperceptible, not universal.

Per-archetype endpoint gap: standard 0.66 -> 3.49, sprint 0.26 -> 1.69, cruise 0.11 -> 0.62.
Step duration T: mean +0.17% — composition, not a widened-rate duration.

## Outcomes — n=120 seeds 8000-8119, played, SD=1, seed-paired

Nothing clears. One metric nominally does — total rebounds +1.633 against a CI of 1.588, a ratio
of **1.03**, the narrowest possible margin — and the agent argues it away correctly:
per-possession rebounds move +0.0016 against a CI of 0.0365 (ratio 0.04), possessions rose
+1.000 (itself not clearing), and 15 metrics at 95% gives ~0.75 expected false positives.
**It is a pace artefact, not a rebounding change.** Agreed.

**One inconsistency to resolve before quoting this table:** the points-per-possession row (3.992
OFF / 3.806 ON) is not derivable from the points and possessions rows in the same table
(74.825 / 38.700 = 1.93). PPP is evidently computed on a different base than those two rows.
It does not change the conclusion — that metric does not clear either way — but the definition
should be pinned down before this number is reused.

## Offence did not move — proof accepted

Membership test (`_is_defender_id(pid, def_lineup)`), never an action label; a pid absent from
the lineup gets the raw rate whatever the step calls him, and an empty lineup spreads nobody.
Exhaustive sweep s in {0.10, 0.25, 0.50, 0.75, 1.00} x AG in {0,10,24,50,73,100,144} x 6
archetypes asserts an off-lineup player's rate is exactly `_ag_grid_per_game_sec`. 13/13 callers
tested for the per-player accessor; both `apply_spread=True` blanket cases fail. Midpoint fixed,
so this cannot be a stealth global speed change.

`shared.apply_sim_crash_destinations` (the SIM arm's counterpart of the played arm's
`_interpolate_step_end` callers) got the same per-player test off `game.defense_team.lineup` —
without it the two arms would have diverged.

## Two deviations from the brief — both disclosed, both accepted

1. **The per-player test is NOT inside the combined helper.** It sits in each of the 13 callers,
   via one shared `defender_aware_rate(player, archetype, pid, def_lineup)`. Reason given is
   evidence, not preference: the helper takes an ALREADY COMPUTED rate, 5 of the 13 callers
   reference `rate` again after the call, and `shared.apply_sim_crash_destinations` has no
   `def_lineup` in scope at all (it reaches the lineup through `game.defense_team`). Hoisting
   would mean 13 signature changes plus a special case for no behavioural gain. A test asserts
   all 13 go through the accessor, so a new caller that forgets fails the suite. Accepted.
2. **Two Stage-1 assertions were edited** — both in the agent's own
   `tests/test_movement_rate_accessor.py`, and both were written in Stage 1 explicitly to be
   superseded here ("must stay on the RAW rate in Stage 1 — wiring the spread in is a later
   stage"). Replacements assert STRICTER properties. No test outside that file touched, nothing
   weakened. Accepted.

## Stage 3 pins intact

The four hardcoded `12.0` fallbacks and the three missing `max(0.0, ...)` floors are untouched
and still enforced by `test_stage_3_defects_are_still_untouched`. Note the numbering collision:
Stage-1 source comments mark them `STAGE 2` while the brief defers them to Stage 3. The code did
not move, only the label.

## Harness change worth knowing

The equiv-v3 cell's `stats()` derived everything from turn `result_type`, which has **no rebound
category** — the first outcomes table had a silent `rebounds 0.000` row. The agent added
read-only OREB/DREB capture derived from `next_play_type` and re-ran all 240 outcome cells. The
harness now records rebounds; prior reports' rebound numbers, if any, were not real.

## Open decision for Jamie

Whether to flip `GOB_DEFENDER_AG_SPREAD` on by default. Divergence is below the pre-existing
floor, no outcome metric clears, and the arrival gap is visible on ~41% of moving placements.
Expectation to set: on most placements nothing will look different, because both defenders still
arrive.

No merge by Claude. Jamie merges.
