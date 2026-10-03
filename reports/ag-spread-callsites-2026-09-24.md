# Closing the remaining `_interrupted_coord` call sites

**No — the tween/endpoint mismatch is not back at the floor.** It is **7.95%**
(52,519 / 660,230) against a 0.0301% floor, and it moved the **wrong way**: wiring the
remaining sites took it from 7.80% to 7.95%, and the worst single mismatch from 24.43 to
26.10 grid units.

**Step duration did not stay put in the mean, but it did not move for the reason that
matters.** Mean T went from +0.32% to **−0.34%**, while **total** animated time is flat at
**−0.02%** (237,771.0 → 237,717.0 game-seconds). The mean moved because the flag-ON arm now
emits 704 more steps across the same total time, not because any step changed length. No
duration anywhere in `BackEnd` is formed from the widened rate — that is now a test, not a
claim. **The pacing trap has not reappeared.**

`GOB_DEFENDER_AG_SPREAD` remains **OFF**. Nothing merged. Nothing re-cut. No constant retuned.

---

## 1. The list — 31 sites, not 18

I re-derived it rather than trusting the build report's §6 table, and that table was wrong
again. `_interrupted_coord` is **not one function**: there are **four separate definitions**
(`transition_bridge:112`, `reset_step_helper:99`, `fb_outlet_pass_step_emitter:60`,
`rim_runner_step_emitter:243`), so no single-function assertion can cover this.

**31 static call sites**, resolved by parsing the rate argument back to its assignment:

| | sites | state |
|---|---|---|
| Already wired by the build | 10 | `transition_bridge` ×6, `reset_step_helper` ×3, `dynamic_hct_step_emitter:349` |
| **Wired this brief** | **16** | below |
| Offence — deliberately left raw | 5 | below |
| **Total** | **31** | |

### Wired this brief (16)

| file | call line | how the defence test was established |
|---|---|---|
| `dynamic_hct.py` | 379 | `pg_def` comes from `def_lineup.get("PG")` |
| `dynamic_hct.py` | 1936, 2582 | player is `def_lineup.get(pos)` |
| `dynamic_hct.py` | 2703 | `chase_def` from `def_lineup.get(trail_pos)` |
| `dynamic_hct_shot.py` | 640 | loop is over `def_lineup.items()` |
| `dynamic_hct_step_emitter.py` | 473, 592 | **mixed** lineups → `_is_defender_id(pid, def_lineup)` |
| `fb_outlet_pass_step_emitter.py` | 184 | **mixed** → `_is_defender_id` |
| `rim_runner_step_emitter.py` | 391, 1653 | **mixed** → `not _is_offense_player(pid, off_lineup)` |
| `rim_runner_step_emitter.py` | 602, 2063 | **mixed** → `_is_defender_id` |
| `rim_runner_step_emitter.py` | 1234, 1777 | explicit `defender_id` in scope |
| `triangle_step_emitter.py` | 196, 660 | **mixed** → `_is_defender_id`; 660 explicit `d_player` |

Where the offence/defence test was not already in scope I used **`def_lineup` membership** —
never a variable name, never an action string. Two sites labelled `"cut"` are defenders and
two labelled like defenders are not; the action label is not evidence.

### Not defender placements — left alone (5)

| file | line | what it places |
|---|---|---|
| `dynamic_hct.py` | 374 | `bh_rate` — the ball handler's own rate |
| `dynamic_hct.py` | 2647 | `bh_drive_rate` — the handler breaking his man down |
| `dynamic_hct.py` | 1991, 2018 | the off-ball **offence** walk (`off_lineup` / `off_coords`) |
| `rim_runner_step_emitter.py` | 963 | an unconditional `actions[pid] = "cut"` — an offence cutter |

Two of these — `dynamic_hct:2018` (7.2% of calls) and `fcp_offball_attack:364` (1.9%) —
were listed in the build report's table as **sites to wire**. Both are offence. Wiring them
would have changed offence, which this build must not do.

---

## 2. The acceptance number — missed, and it got worse

| state | tween/endpoint mismatch | worst single |
|---|---|---|
| flag OFF (pre-existing floor) | 194 / 645,259 = **0.0301%** | 17.34 grid |
| flag ON, 10 sites wired *(build)* | 51,402 / 659,245 = **7.80%** | 24.43 grid |
| **flag ON, all 26 defender sites wired** | **52,519 / 660,230 = 7.95%** | **26.10 grid** |

Worst case detail `(distance, duration, rate, T)` = `(70.214, 4.2995, 10.26, 4.2995)`: a
defender asked to cover 70.2 grid units in 4.30s at a widened rate of 10.26, which carries
him 44.1. The animation is 26.1 units behind the simulation.

**Why closing these sites could not reach the floor.** Attributing every mismatching
placement to the function that built it (5 games, flag ON, 3,205 mismatches):

| builder | share |
|---|---|
| `skeleton_step_emitter.py:build_skeleton_animation_steps` | **88.8%** |
| `shot_micro_movements.py:build_shot_micro_steps` | 6.8% |
| `after_steal_fast_break_step_emitter.py` (`_build_drive_step`, `_build_meet_drive_step`) | 3.0% |
| `skeleton_step_emitter.py:_scramble_leg` | 1.1% |
| everything else (incl. all `_interrupted_coord` paths) | **0.3%** |

**99.7% of the residue is built by functions that never call `_interrupted_coord`.** They
place defenders through two *combined* endpoint+tween helpers that do not consult the
wrapper:

- `skeleton_step_emitter.py:2936` `_interpolate_step_end` — 7 callers
- `animation_step_helpers.py:664` `_motion_end_toward_dest` — 6 callers

The residue is overwhelmingly **cruise** archetype (2,920 of 3,205) at low AG — exactly the
signature of a long HCO skeleton step placed at the shipped rate while the tween plays at
the widened one.

**Is it the same class as the pre-existing floor? No — see §3.**

**Why the number went UP.** The 16 newly wired sites do change endpoints (they receive a
widened rate 4,235 times per 3 games), so the flag-ON arm is a *different game*: 221,741
steps against the build's 220,696. More steps means more skeleton placements, and the
skeleton path is 88.8% of the residue. Wiring removed mismatches at the sites it touched and
added more elsewhere by lengthening the game. That is a real result, not noise: the
mismatch is not dominated by anything this brief could reach.

### What would reach the floor

Threading the defender test into `_interpolate_step_end` and `_motion_end_toward_dest`, and
wiring their 13 callers. **I did not do this.** It changes two shared helper signatures
rather than closing call sites, which is the refactor Jamie filed separately and the build
brief explicitly warned off. It is also the *right* shape — both helpers return endpoint and
duration together, so widening the rate inside them moves both at once and they cannot
diverge, and neither touches step T (T is passed in). That is a decision for Jamie, not a
continuation of this brief.

---

## 3. The pre-existing 0.0301% — characterised, not fixed

194 placements of 645,259, flag OFF. Attributed over 5 games (15 mismatches):

| builder | share | what it places |
|---|---|---|
| `skeleton_step_emitter.py:append_hco_bat_oob_trajectory` | 33.3% | defender chasing a batted ball |
| `skeleton_step_emitter.py:append_hco_loose_ball_trajectory` | 33.3% | defender chasing a loose ball |
| `dynamic_hct_step_emitter.py:_build_bat_oob_steps` | 20.0% | same, HCT variant |
| `dynamic_hct_step_emitter.py:_build_interception_pass_step` | 13.3% | defender arriving at an interception |

**Every one is the `sprint` archetype, every one is a defender, and every one is a
ball-chase.** Worst case 17.34 grid units on a 0.30s step
`(d=22.847, dur=0.3, rate=18.36, T=0.3)`.

**It is a different root cause from the flag-ON residue.** These four builders place the
chasing defender on the **ball's** trajectory — at the pass/flight rate, over the ball's
flight time — rather than at the player's own movement rate. The tween then plays him at his
own rate and cannot keep up. The flag-ON residue is the opposite: the player's own rate,
just not the widened one. Fixing one would not fix the other.

**Reported only. Not touched.**

---

## 4. Re-confirming what the build proved

| check | result |
|---|---|
| Reference `equiv_v3_reference_1f4af0ede_loosesag_nogate.json`, flag OFF | **160/160 on fp AND draws**, all four cells (SD=1/0 × sim/played) |
| `s = 0.10` byte-identical to the shipped formula | pass — 7 archetypes × AG 0–144 |
| Midpoint AG=50 fixed at every s | pass |
| Offence untouched | 74,258 wrapper calls, 42,873 with `is_defender`, **42,492 widened — every widened call was a defender**; the 5 offence sites are frozen in a test |
| Spread absent from `_ag_grid_per_game_sec` / `ag_to_grid_per_game_sec` | pass |
| **Step T** | mean **−0.34%**, **total −0.02%** — composition, not pacing. See below. |
| No new RNG draws | pass — and flag OFF reproduces the reference **draw counts** exactly |
| Flag ON vs reference | **1/160** cells match; 159 differ in fp and draws. **Not re-cut.** |

### Step T, in detail

The brief's stop condition was "if any new site applies the spread BEFORE its step duration
is fixed". It does not. Two of the newly wired sites form a `t` from a rate, and I read both:

- `dynamic_hct_step_emitter:449` — `t = max(0.3, dist / rate)` where `rate` is
  `RESET_INBOUND_PASS_GRID_PER_GAME_SECOND`, a **pass constant**, not a player rate, and `t`
  is frozen 22 lines before the wrapper is called.
- `triangle_step_emitter:177` — `recv_rate = _ag_grid_per_game_sec(...)`, deliberately the
  **raw** function, feeding `t`; the wrapper is used only for endpoints afterwards. This is
  the same shape as `build_walk_up_step` and is now pinned by a test.

Mean T fell while **total T is flat**, because the ON arm emits 704 more (slightly shorter)
steps over the same 237.7k game-seconds. The build's +0.32% was the same composition
artefact in the other direction.

---

## 5. Geometry re-measured (n=40, seeds 8000–8039, both arms, SD=1)

| metric | build | now |
|---|---|---|
| ends short, flag ON | 35.17% | **36.76%** |
| p10→p90 endpoint gap, standard / sprint / cruise | 3.49 / 1.69 / 0.62 | **3.49 / 1.69 / 0.62** |
| changes proximity band | 2.44% | **2.44%** |
| crosses the 11 gate | 1.14% | **1.14%** |

**Three of these four cannot move, by construction, and are not evidence about the wiring.**
The gap, band and gate figures are *counterfactuals* recomputed on the flag-OFF arm's own
records under both rates — and the flag-OFF arm is byte-identical to the build's (160/160).
They reproduce to the digit because they are the same arithmetic on the same numbers.

Only **ends-short** is measured per-arm from each arm's own endpoints, and it rose
**1.59pp (+4.5% relative)**. That is **consistent with, and smaller than, the extra wired
mass**: the 16 new sites carry **16.2% of all defender placements** (3,943 of 24,395 per 3
games), and roughly half their defenders are AG≥50, who under the spread end short *less*,
not more. A 4.5% relative rise off a 16.2% mass share with half of it pulling the other way
is the expected order. It is not larger than it should be.

---

## 6. Outcomes (n=120, seeds 8000–8119, played arm, SD=1, seed-paired)

**Nothing clears.** Same as the build.

| metric | OFF | ON | delta | 95% CI | cleared |
|---|---|---|---|---|---|
| points per team | 74.825 | 74.763 | −0.062 | 1.823 | no |
| points per possession | 3.992 | 3.984 | −0.008 | 0.211 | no |
| FG% | 40.989 | 40.814 | −0.174 | 0.992 | no |
| 3PT% | 34.287 | 33.727 | −0.560 | 1.893 | no |
| 3PA share | 36.650 | 36.552 | −0.098 | 0.980 | no |
| possessions | 38.700 | 39.133 | +0.433 | 1.217 | no |
| rim attempts | 4.458 | 4.567 | +0.108 | 0.485 | no |
| blocks | 9.508 | 9.542 | +0.033 | 0.655 | no |
| **steals** | 16.058 | 16.800 | **+0.742** | 0.920 | no *(closest)* |
| fouls | 30.975 | 31.408 | +0.433 | 1.244 | no |
| interceptions | 3.525 | 3.367 | −0.158 | 0.438 | no |
| bat OOB | 5.142 | 5.367 | +0.225 | 0.540 | no |
| turns | 418.900 | 420.925 | +2.025 | 5.174 | no |
| FT awards | 55.317 | 55.675 | +0.358 | 3.109 | no |

**Nothing retuned.**

---

## 7. Tests

`tests/test_defender_ag_spread_flags.py` — **15 → 20 tests**. The five new ones:

| test | what it pins |
|---|---|
| `test_every_interrupted_coord_site_resolves_to_a_rate_we_recognise` | no site may be unresolvable — that would hide an unwired defender |
| `test_every_defender_interrupted_coord_site_reads_the_wrapper` | parses `BackEnd`, resolves all 31 rate arguments; the 5 offence exemptions are **frozen with a reason each** |
| `test_the_wrapper_reaches_every_emitter_that_places_defenders` | the module-level import trap, from both sides |
| `test_step_duration_is_frozen_before_the_spread_at_every_new_site` | the triangle ordering: `recv_rate` stays raw, `t` frozen first |
| `test_no_new_site_forms_a_duration_from_the_widened_rate` | structural — `defender_movement_rate` may never be divided into a distance to make a time, anywhere |

**Full suite, both flag states, identical:**

```
flag OFF: 3536 passed, 20 skipped, 110 xfailed, 0 failed, 0 XPASS  (241.6s)
flag ON:  3536 passed, 20 skipped, 110 xfailed, 0 failed, 0 XPASS  (157.2s)
```

### The bug the new tests caught — in my own previous commit

`test_the_wrapper_reaches_every_emitter_that_places_defenders` failed on
`triangle_step_emitter`. My wiring commit had added `_is_defender_id` and
`defender_movement_rate` to a **function-local import block** buried in an `if dr_steps:`
branch (~line 983) instead of at module level. It parsed, it imported, and it passed every
existing test — but the two call sites that use those names are in *other* functions
(`_build_parallel_move_step`, `_build_triangle_shot_motion_step`), so **both would have
raised `NameError` the first time a triangle fast-break parallel move was emitted.**

It survived the sims only because that path never fired in the sampled games — the
call-site census records **zero** calls from `triangle_step_emitter` across 5 games. A
latent crash on a live path, invisible to the reference.

Fixed in `39444b872` by taking both names from the module-level `rim_runner` re-export at
line 40, which is where this file already gets `_interrupted_coord`, `_traversal_seconds`
and `_ag_grid_per_game_sec`.

---

## 8. Pictures — skipped, and why

`pics.py` builds its panels as **counterfactuals recomputed from the flag-OFF arm's own
records** under both rates. The flag-OFF arm is byte-identical to the build's (160/160), so
re-running it emits the **same four panels** the build report already carries — the same
arithmetic on the same numbers.

A genuinely new panel would have to show a newly wired path's actual flag-ON endpoint. That
picture makes the same point the existing four already make (a low-AG defender ends shorter)
in a different emitter, on a build that is **not flip-ready**. Drawing it would be
manufacturing a figure, so I did not.

---

## Footing (Rule 6e)

| | |
|---|---|
| Worktree / branch | `gob-animation-reward` / `feature/animation-reward` |
| HEAD | `39444b872` — **0 commits behind `develop`** |
| Worker | `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5 |
| Env | `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process |
| Game id | `0xE0000 + (seed − 8000)` |
| Acceptance / geometry | n=40, seeds 8000–8039, **both arms**, **both `SEED_DEFENSES=1` and `=0`** — 320 cells |
| Outcomes | n=120, seeds 8000–8119, played arm, SD=1, seed-paired — 240 cells |
| Attribution probes | 5 games (seeds 8000–8004) for the mismatch and call-site censuses, 3 for the wrapper census |
| CI | 1.96 × SEM on seed-paired deltas |
| Defences | seeded in the SD=1 cells; the SD=0 cells run the empty-catalog path (zones behave as man) |

### Two contaminations, both discarded and re-run

1. **Source edited mid-run.** Fixing the triangle `NameError` changed source while 260 of
   560 cells had completed. Python will not reload, so the *next* cell is the one that
   breaks. All 260 were **deleted** and the full 560 re-run from `39444b872`.

2. **A symlink that silently read the wrong data.** I pointed `analyse.py` at the new cells
   with `ln -sfn .../r2on refon` — but `refoff`/`refon` were **real directories** left by the
   build brief, so the link was created *inside* them and the analysis re-read the **build's
   old numbers**. It returned a mismatch of 51,402/659,245 and a worst case of 24.4247 —
   byte-identical to the build report, including the float. That identity is what exposed
   it: 16 wired sites cannot change nothing. Stray links removed, analysis re-run from a
   clean directory of real symlinks, and every figure in this report is from that re-run.

---

## Where this leaves the flag

`GOB_DEFENDER_AG_SPREAD` stays **OFF**. The call sites this brief set out to close are
closed — all 26 defender `_interrupted_coord` sites now read the one wrapper, and a test
makes a 27th impossible to add silently. But that was not where the mismatch lived. At 7.95%
the rendered motion still disagrees with the simulation on roughly one defender placement in
thirteen, by up to 26 grid units, and **closing every remaining `_interrupted_coord` site
cannot fix it** — 99.7% of it is built elsewhere, by two helpers that were never in scope.

Not flip-ready. The next move is Jamie's call, and it is the helper refactor, not more call
sites.
