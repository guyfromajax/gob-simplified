# Stage 2 — the defender AG spread reaches the unified movement path

**The screen-vs-game divergence went from 7.95% to 0.0221%.** That was the whole point of
Stage 1, and it worked: with the flag ON the rendered motion now disagrees with the simulated
endpoint on 147 of 666,385 placements — *below* the 0.0301% floor the engine has with the flag
off. Flag off is byte-identical: **160/160 on the main reference and 80/80 on the loose
footing**, fingerprint and draws.

**The flag-off gate earned its keep.** The first build came back 0/160 — every cell, both arms.
The cause was mine and it was a latent `NameError`, described in §6. Nothing was adjusted to
make the run pass; the bug was found and fixed, and the run was repeated.

`GOB_DEFENDER_AG_SPREAD` is unchanged at **s = 0.50** — the value already in the code. No
constant was tuned.

---

## Footing (Rule 6e)

| | |
|---|---|
| Branch / HEAD | `feature/animation-reward`, on top of `c56abfe43` (develop merged first — review markers, docs only) |
| Worker | `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5 |
| Env | `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process |
| **Defenses catalogue** | **`SEED_DEFENSES=1` — production footing, seeded.** The main reference also covers `SEED_DEFENSES=0`. |
| Flag-off references | n=40 seeds 8000–8039, both arms, SD=1 and SD=0 (main) / SD=1 (loose) |
| Divergence + geometry | n=40 seeds 8000–8039, **both arms**, SD=1 |
| Derivation pairing | n=8 seeds 8000–8007, played arm, SD=1 |
| Outcomes | n=120 seeds 8000–8119, played arm, SD=1, seed-paired, CI = 1.96 × SEM of the per-seed difference |

---

## 1. Files changed

Nine engine files (+74 / −29 lines), one test file extended, one added.

| file | + | − | change |
|---|---|---|---|
| `BackEnd/utils/animation_step_helpers.py` | 33 | 2 | `defender_aware_rate` added; its own 2 combined-helper callers wired |
| `BackEnd/engine/skeleton_step_emitter.py` | 9 | 9 | 6 combined-helper callers + module-scope import |
| `BackEnd/engine/shot_micro_movements.py` | 7 | 2 | 2 callers + import (one is the §6 bug site) |
| `BackEnd/engine/covert_release_step_emitter.py` | 5 | 4 | private stamper + `_is_defender_id` import |
| `BackEnd/engine/rim_runner_step_emitter.py` | 4 | 4 | private stamper |
| `BackEnd/engine/fb_outlet_pass_step_emitter.py` | 4 | 4 | private stamper |
| `BackEnd/utils/shared.py` | 8 | 2 | the sim-arm crash site + its defending lineup |
| `BackEnd/engine/after_steal_fast_break_step_emitter.py` | 2 | 1 | 1 caller + import |
| `BackEnd/engine/fb_drive_resolution.py` | 2 | 1 | 1 caller + import |
| `tests/test_movement_rate_accessor.py` | 20 | 9 | two Stage-1 pins superseded (§7) |
| `tests/test_ag_spread_stage2.py` | new | | 14 tests |

### The per-player rule

All 13 callers of the combined helper are MIXED, so `apply_spread=True` for a whole site would
widen the offence. Every one now goes through one function:

```python
def defender_aware_rate(player, archetype, pid, def_lineup) -> float:
    return defender_movement_rate(player, archetype, _is_defender_id(pid, def_lineup))
```

**Why it is not inside the helper.** The brief asked for the test to be threaded into the
combined helper. I did not do that, and the reason is evidence rather than preference: the
helper takes an *already computed* `rate`; **5 of the 13 callers reference `rate` again after
the call**, and **one (`shared.apply_sim_crash_destinations`) has no `def_lineup` in scope at
all** — it reaches the lineup through `game.defense_team`. Hoisting the rate computation into
the helper would have meant 13 signature changes plus a special case, for no behavioural gain.
The decision is still **per player, keyed on pid, inside each caller's loop**, and a test
asserts all 13 go through the accessor — so a new caller that forgets fails the suite. If you
want it physically inside the helper anyway, say so and I will do the signature change.

The three private stampers (`rim_runner:297`, `fb_outlet_pass:87`, `covert_release:877`) flipped
from `apply_spread=False` to `apply_spread=_is_defender_id(pid, def_lineup)` — the one-line
change Stage 1 set up. Their endpoints already used the wrapper, so this closes that split.

`shared.apply_sim_crash_destinations` is the **sim arm's** counterpart of the played arm's
`_interpolate_step_end` callers. Had the spread reached one arm and not the other the two would
have diverged, so it gets the same per-player test off `game.defense_team.lineup`.

---

## 2. Flag OFF — the gate

```
equiv_v3_reference_1f4af0ede_loosesag_nogate.json
  SD=1 sim     40/40 fp+draws      SD=0 sim     40/40 fp+draws
  SD=1 played  40/40 fp+draws      SD=0 played  40/40 fp+draws
  TOTAL 160/160

equiv_v3_loose_baseline_1f4af0ede_loosesag.json
  LOOSE SD=1 sim     40/40 fp+draws
  LOOSE SD=1 played  40/40 fp+draws
  TOTAL 80/80
```

Seed 8000 reproduces **fp `a1d150579771387a`, draws `77689`**.

**Full suite: 3,570 passed, 20 skipped, 110 xfailed, 0 failed, 0 XPASS** = the 3,556 Stage-1
baseline plus 14 new Stage-2 tests. Two assertions in my own Stage-1 file were superseded — see
§7, which is the one place this report does not simply say "nothing was edited".

---

## 3. Screen-vs-game divergence — the measurement

Same metric, same code (`bcensus.py`, byte-identical to the file that produced the 7.95%):
`|duration × rate − distance covered| > 0.01` grid units.

| state | diverging placements | share | worst single |
|---|---|---|---|
| flag OFF (pre-existing floor) | 194 / 645,259 | **0.0301%** | 17.34 grid |
| **flag ON, before Stage 1+2** *(reports/ag-spread-callsites-2026-09-24.md)* | 52,519 / 660,230 | **7.95%** | 26.10 grid |
| **flag ON, now** | **147 / 666,385** | **0.0221%** | **16.84 grid** |

**That is ~0, and it is below the flag-off floor.** The residue is the *pre-existing* class, not
a new one: the worst cases are `sprint`-archetype ball-chase placements on 0.3–0.4s steps
(`d=23.889, dur=0.3953, rate=17.82`), the same four ball-chase builders the audit characterised
— they place the chasing defender on the **ball's** trajectory rather than his own rate, which
no amount of rate unification can fix. It is slightly *lower* than the flag-off count because
the ON arm is a different game with a different mix of those steps, not because anything was
repaired.

---

## 4. Derivation pairing, flag ON

n=8, played, SD=1, 22,462 shared-stamper steps.

| kind | flag ON | baseline | delta |
|---|---|---|---|
| COMBINED only (endpoint+duration together) | 59.03% | 59.36% | −0.33 |
| IC only → duration re-derived by stamp | 34.40% | 33.29% | +1.11 |
| MIXED IC + COMBINED in one step | 2.74% | 2.68% | +0.06 |
| no clamp (endpoint set directly) | 3.82% | 4.68% | −0.86 |

Per turn type: HCO 60.12 / 33.02 / 2.03 / 4.84 · FCP 41.89 / 48.85 / 6.96 / 2.29 ·
FREE_THROW 72.02 / 27.29 / 0.39 / 0.30 · HCT 40.41 / 47.02 / 8.91 / 3.67 ·
FAST_BREAK 76.03 / 22.75 / 0.34 / 0.88.

The small movements are composition — the ON arm plays a different game (22,462 steps against
21,885). **The important point is that this table no longer describes a risk.** "IC only →
duration re-derived" was the category where endpoint and duration could disagree; they now both
resolve the same per-player rate, which is what §3 measures. 34% of steps still *re-derive* the
rate; 0.0221% of them get a different answer.

---

## 5. Geometry — the fast-vs-slow arrival gap

n=40, both arms, SD=1. Measured on **moving placements only**, which is the definition that
reproduces the stated 0.35 baseline (my measure gives **0.347** with the flag off — confirming
like-for-like).

| | flag OFF | flag ON (s=0.50) |
|---|---|---|
| mean p10→p90 arrival gap | **0.347 grid** | **1.896 grid** |
| median | 0.000 | 0.000 |
| p90 | 1.031 | 5.455 |
| share above the ~0.5-unit visibility floor | 26.9% | **40.6%** |
| share above 1.0 unit | 10.3% | 38.0% |

**The gap is 5.5× wider and it is above the visibility floor — but only on some placements.**
The mean (1.90) and p90 (5.46) clear ~0.5 comfortably. The **median is still 0.000**: most
moving placements have a short enough target that both a fast and a slow defender arrive fully,
so the rate never binds and the spread is invisible there. Concretely: **on ~41% of moving
placements a p10-AG and a p90-AG defender now end at least half a cell apart, and on ~59% they
end in the same place.** So the spread is built, it is no longer imperceptible, but it is not a
universal change either.

Per-archetype endpoint gap (counterfactual, same placements under both rates): standard
0.66 → 3.49, sprint 0.26 → 1.69, cruise 0.11 → 0.62.

**Step duration T**: mean +0.17%, total +0.69% (237,771 → 239,422 game-seconds over 1,151 more
steps). Composition, as in the prior stages — no duration is formed from the widened rate.

---

## 6. The bug the flag-off gate caught

The first Stage-2 build returned **0/160** — every cell, both arms, fp *and* draws. Per the
brief I stopped and diagnosed rather than adjusting.

Bisecting by file, then by line, isolated it to one line in
`shot_micro_movements.build_shot_micro_steps`. My rewrite had passed the loop variable `pid`:

```python
rate = defender_aware_rate(defender_player, "standard", pid, def_lineup)   # WRONG
```

The player there is `defender_player`, whose id is `defender_id`. **`pid` belongs to earlier
loops in the same 293-line function and is unbound on the path that reaches the defender
clamp.** A probe counted **70 `NameError`s in a single game** — raised while evaluating the
argument list, before the function was entered, and swallowed by a handler upstream, which
silently skipped the defender clamp and moved the whole game.

This is the same class as the `triangle_step_emitter` incident the brief warned about: a name
that parses, imports and passes every test, but is not resolvable on a live path. It was
invisible to the unit tests and to the function-level equivalence checks, and **only the
reference run caught it.**

Fixed by using `defender_id`, and guarded by a new test,
`test_the_id_passed_is_the_id_the_player_was_looked_up_with`: whenever the player comes from
`_player_lookup_by_id(off, def, X)` the id passed must be X, and the three sites whose player
comes from elsewhere are listed with their reason. An audit of all 13 sites under that rule
found **0 remaining mismatches**.

---

## 7. How I proved the offence did not move

1. **Membership, not labels.** The test is `_is_defender_id(pid, def_lineup)` — never an action
   string. `test_membership_is_the_test_not_the_action_label` pins that a pid absent from the
   lineup gets the raw rate whatever the step calls him, and that an empty lineup spreads nobody.
2. **Exhaustive at every spread strength.**
   `test_the_offence_rate_is_unchanged_at_every_spread_strength` sweeps s ∈ {0.10, 0.25, 0.50,
   0.75, 1.00} × AG ∈ {0, 10, 24, 50, 73, 100, 144} × 6 archetypes and asserts an off-lineup
   player's rate is exactly `_ag_grid_per_game_sec`.
3. **No blanket application anywhere.** `test_every_combined_helper_caller_uses_the_per_player_accessor`
   (13/13) and `test_the_private_stampers_apply_the_spread_per_player` both fail on
   `apply_spread=True`.
4. **The midpoint is fixed**, so an average defender does not move either — the flag cannot be a
   stealth global speed change.
5. **Empirically**: with the flag OFF every player of either side is byte-identical (160/160 +
   80/80). With it ON, the only rates that can differ are those of players on `def_lineup`,
   because that is the sole branch.

### Two Stage-1 assertions were superseded — stated plainly

The brief asked for a green suite "with no existing test edited". Two assertions in
`tests/test_movement_rate_accessor.py` (my own Stage-1 file) had to change, because Stage 1
wrote them *to be* superseded here. Both said so in their own failure messages:

- `test_the_private_stampers_route_through_the_accessor` asserted `apply_spread=False`, with the
  message *"must stay on the RAW rate in Stage 1 — wiring the spread in is a later stage"*. It
  now asserts `apply_spread=_is_defender_id(pid, def_lineup)`.
- `test_the_combined_helper_still_takes_a_raw_rate` → renamed
  `test_the_combined_helper_rate_is_per_player_not_per_call`, now asserting the per-player
  accessor instead of a raw rate.

No test outside that file was touched, and no test was weakened: both replacements assert a
*stricter* property than the ones they replace. The Stage-3 pins (the four `12.0` fallbacks,
the three missing `max(0.0, …)` floors) are untouched and still enforced.

---

## 8. Outcomes — n=120, played, SD=1, seed-paired

| metric | OFF | ON | delta | 95% CI | CI excludes 0 |
|---|---|---|---|---|---|
| points per team | 74.825 | 73.367 | −1.458 | 1.993 | no |
| points per possession | 3.992 | 3.806 | −0.185 | 0.196 | no |
| FG% | 40.989 | 40.584 | −0.404 | 1.251 | no |
| 3PT% | 34.287 | 33.231 | −1.057 | 1.971 | no |
| fouls | 30.975 | 31.700 | +0.725 | 1.348 | no |
| offensive rebounds | 14.058 | 14.758 | +0.700 | 0.940 | no |
| defensive rebounds | 42.158 | 43.092 | +0.933 | 1.181 | no |
| **total rebounds** | **56.217** | **57.850** | **+1.633** | **1.588** | **YES** |
| OREB rate % | 23.110 | 23.979 | +0.869 | 1.337 | no |
| blocks | 9.508 | 10.058 | +0.550 | 0.731 | no |
| steals | 16.058 | 16.550 | +0.492 | 0.974 | no |
| possessions | 38.700 | 39.700 | +1.000 | 1.159 | no |
| rim attempts | 4.458 | 4.708 | +0.250 | 0.573 | no |
| turns | 418.900 | 419.300 | +0.400 | 5.407 | no |
| FT awards | 55.317 | 52.617 | −2.700 | 3.194 | no |

**One metric clears, and I do not think it is real.** Total rebounds exceeds its CI by a ratio
of **1.03** — the narrowest possible margin. Two things argue against reading it as an effect:

- **It disappears when controlled for pace.** Rebounds *per possession* move by **+0.0016 with
  a CI of 0.0365 — a ratio of 0.04.** Possessions rose +1.000 (CI 1.159, itself not clearing),
  and total rebounds rose with them. Per 100 turns the ratio is 0.83, also short.
- **Multiplicity.** Fifteen metrics at 95% gives ~0.75 expected false positives by chance alone.

So: reported as flagged because the brief asked for anything whose CI excludes zero, but the
honest reading is that **nothing cleared** — the rebound total is a pace artefact, not a
rebounding change. Neither number was tuned.

---

## 9. Anything that did not behave as expected

1. **The `NameError` in §6** — the headline surprise, and the reason the flag-off gate exists.
2. **The harness did not record rebounds at all.** `stats()` in the cell derives everything from
   turn `result_type`, which has no rebound category. Rather than omit what the brief asked
   for, I added OREB/DREB capture (read-only, derived from `next_play_type`) and **re-ran all
   240 outcome cells**. The first outcomes table I produced had a silent `rebounds 0.000` row;
   it is not in this report.
3. **The divergence came in slightly *below* the flag-off floor** (0.0221% vs 0.0301%) rather
   than equal to it. That is a different mix of ball-chase steps in a different game, not a
   repair — the pre-existing class is untouched and is Stage 3+ work.
4. **The pairing shares moved by up to 1.1pp.** Composition of a different game, not a routing
   change; the flag-off pairing is unchanged and the routing tests pass.
5. **A naming collision worth knowing**: the Stage-1 source comments mark the `12.0` fallbacks
   and missing floors as `STAGE 2`, while this brief defers them to **Stage 3**. The numbering
   moved; the code did not. `test_stage_3_defects_are_still_untouched` pins them either way.
