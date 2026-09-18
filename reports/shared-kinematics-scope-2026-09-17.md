# Shared kinematics: scope

Written for: Jamie and the sessions deciding whether to build a shared kinematics function. Read-only pass; nothing was built or committed.

**Short answer.** The function can be built for HCO skeleton steps. Every input exists before the emitter runs, except two: the entry steps (walk-up, handoff, kickout) and the post-shot sub-steps, which only exist inside the emitter. Together those are about 4.2 s of every half-court turn.

The premise holds in kind but not in size. Sim's contest reads the per-step placement target and has no notion of partial travel. But on the shot, played's contest defenders differ from sim's by only 1.2–1.4 grid units on average. The "42 units" on seed 8000 was sim's stale stored coords, which the contest never reads. The payoff is the clock, rebounds, over-the-back, putbacks and next-turn starting positions, not the shot contest.

## Footing

Unless a line says otherwise:
- **Harness:** equiv-v3 worker at `5d44194c1`, Lancaster vs Bentley-Truman, sliders 2, traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, game id `0xE0000+(seed-8000)`.
- **Played arm:** `ARM=played`, the hybrid arm (full-sim mode is off only inside the four gated Animator methods).
- **Samples:** 16 seeds (8000–8015) unaligned, both `SEED_DEFENSES=0` and `=1`. The aligned turn-1 cut uses `ALIGN_RNG=1`, `SEED_DEFENSES=1`, seeds 8000–8007.
- **Reproducibility:** the probe game rows match the `d9a4f1517` reference 64/64, with 0 errors.
- **Probe location:** `scratchpad/sk/kin_probe.py` in the session scratchpad. It is outside the repo and not committed, so the numbers below can't be re-run from the repo alone.

---

## V1: The premise

**Verdict: correct in kind, overstated in size.**

### What sim's contest reads
- **Read path:** sim's HCO contest reads `ShotAttemptGeometry`. On sim, `_freeze_hco_shot_attempt_geometry` (`phase_resolution.py:4851-4864`) fills it from the StepState stamp at the shot step. In 2/game cases the stamp is missing and it falls back to a fresh `compute_defender_grid` (source `hco-final-grid-shot-step`).
- **Stamp contents:** the stamp is `defender_grid_from_animations` (`defender_placement.py:1285`) over one `_build_all_animations` build. Each defender's value is `movement[i].coords` from `position_standard_defenders` / `position_zone_defenders`: the placement's target for skeleton step *i*, computed from the offense's skeleton spot at *i*.
- **Tactical modifiers, not travel:**
  - Lag: `_defender_lag_fraction`, `defender_placement.py:1209-1223`. On sim, 6.5% of lag calls are below 1.0 and 4.1% are exactly 0 (a freeze).
  - A hold at pass steps (`:1225-1235`), never applied on the final step.
- **Partial travel:** none. The stamp has no duration, rate or arrival time.
- **Check:** sim contest geometry vs the stamp at the shot step is **0.00** (n=4,070 man, 3,450 zone, `SEED_DEFENSES=1`). Poisoned by shifting PG's stamp +3 before the freeze: PG reads **3.00**, the others 0.00 (`SEED_DEFENSES=1`, seeds 8000–8003).
- **Intended, start, or neither:** the stamp at the shot step is the intended destination for that step. It equals the previous step's stamp (the step start) on 69.7% of defenders under man and 37.8% under zone (`SEED_DEFENSES=1`, sim arm).

### What played's contest reads
- **Read:** `shot_manager.py:946`, `:981`, `:1011` call `_shot_defender_xy` (`:188-203`), which calls `ShotAttemptGeometry.defender_coord`.
- **Freeze:** the geometry is frozen at `phase_resolution.py:4846-4850` from `player.coords`.
- **Written by:** `_uess_sync_emitted_shot_coords` (`:4641-4716`) runs the full HCO emitter on a throwaway turn result, with sim_rng saved and restored, and copies the shoot step's `end.coords` onto every player (`:4697-4705`).
- **Check:** played contest geometry vs the emitted shoot-step end is **0.00** (n=3,565 man, 3,395 zone). Poisoned by +3 on PG after the sync: PG reads **3.00**, the others 0.00.

The shoot step itself is stationary in the emitter. In 100% of samples its start = destination = end for defenders (0.00, n=6,960), because the render's movement rows are one short. The movement row for the shot step equals the pre-shot step's destination in 100% of samples. So played's contest reads **the render's placement for the shot step, after interruption during the step before the shot**.

### Played contest vs sim stamp (`SEED_DEFENSES=1`, per defender, shot turns)

| component | man: mean / p90 / % > 0.5 | zone: mean / p90 / % > 0.5 |
|---|---|---|
| total (played contest − stamp) | 1.16 / 3.67 / 42.0% | 1.43 / 5.04 / 35.4% |
| different placement draw (stamp vs render row) | 0.35 / 1.00 / 27.9% | 0.60 / 2.00 / 19.5% |
| interruption in the pre-shot step | 0.90 / 3.51 / 19.6% | 1.00 / 3.85 / 20.9% |

`SEED_DEFENSES=0` is the same shape: total 1.05 man / 1.08 zone.

### Seed 8000, turn 1: the "42"

On the aligned footing, the played-vs-sim contest difference per defender is small:

| defender | total | draw | interruption |
|---|---|---|---|
| C | 0.6 | 1.0 | 0.4 |
| PF | 1.6 | 2.0 | 2.2 |
| PG | 0.7 | 0.0 | 0.7 |
| SF | 2.7 | 4.0 | 1.3 |
| SG | 3.8 | 5.1 | 1.3 |

Draw and interruption are vectors, so they can partly cancel. Over 8 aligned seeds, the total is mean 1.52, max 15.8 (seed 8004: C and PF interrupted 15.8 and 13.3 in a 0.05 s pre-shot step).

The 42 was the pre-shot **position snapshot**, which is stored `player.coords`. On sim those coords are stale, because sim writes no defender coords during HCO. Played contest vs sim's stored coords is mean **26.3**, max 40.2 over those 40 defenders; for seed 8000's defenders it is 8.8–33.1. The 42 was the maximum over all ten players, offense included. **None of it is interruption or a placement draw, and the HCO contest does not read it.**

Conclusion: sim's contest reads fully-arrived per-step targets, so the premise is right in kind. A shared function would move HCO contest inputs by only ~1.2–1.4 units on average. Its value lies elsewhere (V4, V6).

---

## V2: Does interruption exist on sim?

**HCO interruption is render-only. Other families already have interruption and travel-time math on sim.**

The HCO implementation:
- Interruption per player: `skeleton_step_emitter.py:827-866` `_build_step_end_coords_with_interrupts`, which calls `_interpolate_step_end` (`:2902-2932`).
- Gate travel: `_natural_t` (`:801-824`).
- Duration selection: the step loop (`:2318-2470`).

Calls per game (16 seeds):

| function | played `D=1` | sim `D=1` | played `D=0` | sim `D=0` |
|---|---|---|---|---|
| `SSE._build_step_end_coords_with_interrupts` (HCO/FCP) | 1,417 | **0** | 1,471 | **0** |
| `SSE._natural_t` (HCO/FCP gate) | 1,409 | **0** | 1,455 | **0** |
| `SSE._interpolate_step_end` (post-shot sub-steps via FB/OREB) | 14,017 | 332 | 14,474 | 312 |
| `TB._interrupted_coord` (transition walk-up) | 8,995 | 6,435 | 9,131 | 6,729 |
| `CR._interpolate` (cutoff resolution) | 4,011 | 4,646 | 4,153 | 5,021 |
| `ASH._motion_end_toward_dest` | 1,009 | 907 | 1,111 | 872 |
| `RRS._interrupted_coord` (rim runner) | 207 | 305 | 271 | 221 |
| `FTP._travel_seconds` (final-turn pacing) | 60 | 299 | 63 | 260 |
| `DHS._build_loop_step` (dynamic HCT) | 220 | 251 | 223 | 260 |
| `FOP._interrupted_coord` (FB outlet) | 67 | 125 | 100 | 123 |
| `PC._earliest_contact` (pass contest arrival walk) | 94 | 103 | 91 | 109 |
| `FDR._traverse_seconds` (FB drive resolution) | 34 | 60 | 39 | 56 |
| `ASH._ag_grid_per_game_sec` (the one rate function) | 42,873 | 14,736 | 44,202 | 14,902 |
| `RSH/CRS/ASF/SMM` interrupt/traversal helpers | 0 | 0 | 0 | 0 |

- **Poison for the sim zeros:** calling `_build_step_end_coords_with_interrupts` once per HCO turn reads 141 / 132 / 124 / 132 per game on sim (seeds 8000–8003, `D=1`). Points were unchanged.
- **Split by arm, not flag:** the hybrid played arm has full-sim mode on outside the four gated methods, so a per-flag split mixes that arm. The sim arm runs with full-sim mode on throughout the quarter loop.
- **The last row's zeros are not poisoned.** Those four helpers read 0 on both arms, but no counter check was injected for them.

---

## V3: Inputs

| input | sim has it pre-emit? | where / note |
|---|---|---|
| step-0 start coords | **stale** | The emitter seeds from `prior_turn["final_coords"]` (`skeleton_step_emitter.py:2062-2066`, `:1711-1713`), stamped by `build_final_coords` (`game_manager.py:981`) from `player.coords`. Sim never writes defender coords during HCO (displacement 0.00, arm-gap pass). |
| per-step start coords | **no** | Only the emitter chains step N end → step N+1 start (`:2135-2145`). Sim has only per-step placement targets. |
| intended destinations (all 10) | **yes, partly thrown away** | `compute_defender_grid` (`animator.py:1241-1271`) runs the full offense+defense `_build_all_animations` on sim, but `defender_grid_from_animations` keeps defense rows only. The offense rows are computed and discarded. |
| archetype per player per step | derivable, not computed | `_build_archetype_map` (`:737`) / `_archetype_for_action` (`:132`): a pure function of skeleton `pos_actions` plus lineup, but it runs only in the emitter. |
| AG / rate | **yes** | `_ag_grid_per_game_sec` (`animation_step_helpers.py:795`), already ~14.7k calls/game on sim. |
| gate | derivable, decided during emit | Step loop `:2318-2370`: shooter on the last step, `_attack_drive.driver_gate` driver, FLSS driver, else slowest offensive player by start→end distance. Its skeleton flags come from the resolver (sim has them); its start/end distances need the interruption chain. `gate_offense_required_count` is FCP BIP (`transition_bridge.build_walk_up_step`) only, not HCO. |
| step floors | **yes** | `_step_t_floor_game_seconds` is stamped on the skeleton by the resolver; `HCO_STEP_T_FLOOR_GAME_SECONDS = 0.5` (`constants/__init__.py:345`). |
| ball owner walk / pass flight time | derivable, emitter-only | `_walk_ball_owners`, `_compute_pass_meet_point` in the emitter; inputs are skeleton + coords. |
| **entry steps** (walk-up / handoff / kickout) | **emit-only: design problem** | The orchestrator (`:1690-2000`) decides from prior final coords and ball-handler position. Played burns 3.09 s/turn here (`D=1`, man). The played arm also draws **global stdlib `random`** in `transition_bridge._pick_pg_receive_target:98-99` and `_pick_kickout_*:131/154`, which would be an RNG-isolation leak if run on sim. |
| **post-shot sub-steps** | **emit-only: design problem** | 1.09 s/turn played (`fixed_duration` 0.58 + `shot_resolved` 0.51, `D=1`, man). Their inputs (the overlay maps) exist on the sim result. |

---

## V4: Consumers that would read a different value

Per-game counts below are from the committed arm-gap probe (`scratch_staleness_probe2.py`, `5d44194c1`), played arm, `SEED_DEFENSES=1`, 16 seeds. A "flip" means the answer changes between played's refreshed coords and the start-of-turn (sim-equivalent) coords, which is exactly what sim would gain.

| consumer | reads | would change (per game) | correction or regression |
|---|---|---|---|
| HCO shot contest (`_shot_defender_xy` via frozen geometry) | stamp on sim; interrupted render placement on played | defender inputs move mean 1.16 man / 1.43 zone units; 58–65% of samples unchanged (V1) | Correction, small. Contest tuning has always been on sim. |
| **Rebounder selection** (`select_rebounder_by_score` → `_rebound_distance`, `shared.py:1658`) | `player.coords`, stale on sim | in HCO turn: **41.1 of 46.6** picks change identity, **20.9** flip OREB/DREB side; next turn: 5.1 of 5.9, 2.3 side flips | Correction. OREB/DREB rates will move and were tuned on stale coords (recalibration risk). |
| **Over-the-back** (`resolve_over_the_back_foul`, `shared.py:878`) | `player.coords` (≤ 4-unit gate) | in HCO turn: **21.5 of 42.1** in-play decisions flip; next turn 2.6 of 5.4 | Correction. It also changes the draw count, since the rolls only happen inside the gate. |
| **Putback defender** (`_resolve_oreb_putback_defender`, `shared.py:848`) | `player.coords` | **5.4 of 6.8** in HCO turn; 0.8 of 1.1 next turn | Correction. |
| Force-foul closest defender (`select_defender_closest_to_victim`) | overrides first, then `player.coords` | 0.4 calls, **0 flips**. A zero, not poisoned. | Neutral. |
| Next-turn seeds (`final_coords` → HCO entry orchestrator, transition walk-up, FB starts) | `player.coords` | not counted; `TB._interrupted_coord` alone runs 6,435/game on sim from these seeds | Correction, not measured. |
| Pass interception / steal (`_hco_step_def_xy`, `phase_resolution.py:5382-5415`; `pass_contest._earliest_contact`) | the **stamp on both arms** | 0 today; changes only if the function's arrival positions replaced the stamp here | If switched: better fidelity, but it moves calibrated intercept rates. **Regression risk.** |
| Shooter spot / 2PT-3PT classification | skeleton spot on sim (`set_shooter_coords_from_skeleton_last_step`, `:4719`); emitted shoot end on played | **not measured** | Likely correction; unknown size. |
| Foul selection (`select_foul_player`) | position-based roll, not coords (`d190a7520`) | none | Unchanged. |
| Zone credited / moment defender | placement assignment map | none | Unchanged. |

**Correction to the arm-gap report's summary:** it said about 21 of about 47 rebounder picks change. The measured figure is **41.1 of 46.6 picks change identity**; the **~21 is the OREB/DREB side flips** (20.9).

---

## V5: Cost and risk

**There are many duration models, not one.** One rate function (`_ag_grid_per_game_sec`) feeds at least 13 separate duration or interruption implementations:

1. HCO/FCP emitter step loop: `skeleton_step_emitter.py:2373-2470`, floor branches `:2437-2464`, interruption `:827` / `:2902`.
2. **Sim's HCO clock**, a different model: `calc_skeleton_step_timing_contract` (`shared.py:447`). Slowest offensive mover between skeleton spots, AG rate, **rounded to whole seconds per step with a 1 s minimum**, no entry or post-shot steps. It has 15 call sites (HCO, FCP `:10304`, HCT `:12440`, `shot_manager`).
3. `transition_bridge.build_walk_up_step` (slowest gate / N-of-M).
4. `animation_step_helpers._motion_end_toward_dest` (a copy of #1's interruption).
5. `floor_step_t_to_traversal`.
6. `rim_runner_step_emitter` (own `_interrupted_coord`).
7. `fb_outlet_pass_step_emitter` (own `_interrupted_coord`).
8. `reset_step_helper` (own `_interrupted_coord`).
9. `covert_release_step_emitter._traversal_seconds`.
10. `dynamic_hct_step_emitter` (`t = max(0.3, dist/rate)`).
11. `final_turn_pacing`.
12. `shot_micro_movements._compute_step_t`.
13. Resolution-side: `fb_drive_resolution`, `pass_contest`, `fast_break_shot_geometry` / `after_steal_*` interpolation, `cutoff_resolution` / `dynamic_hct` interpolation.

**Can it be extracted without changing behaviour?** For HCO skeleton steps, yes. The T selection, gate choice and interruption math (`:2318-2470`, `:801-866`, `:2902-2932`) contain no RNG calls and are pure functions of coords, archetype, AG, skeleton flags and floors. The emitter's draws (dead-ball fumble label, post-steal transition) sit outside that block. A pure code move should leave played byte-identical; that must be proven with the existing 40/40 fingerprint gate on both arms.

**Effect on the played arm:** byte-identical by construction, if it is a move and the function isn't fed different inputs. Having sim call it changes sim outcomes by construction (clock, rebounds, over-the-back, the draw count through over-the-back), so it needs a fresh n=40 baseline.

**Rough size:**
- Extract the HCO skeleton-step duration + interruption function and prove played unchanged: **2–3 days**.
- Sim adoption for HCO skeleton steps: feed the offense rows sim already computes, write arrival positions, take clock authority from the function. **About 1 week.**
- Plus the two emit-only pieces (entry orchestrator with its global-random draws; post-shot sub-step timing) and a recalibration pass: **another 1–2 weeks**.
- All families (FB ×4 emitters, FCP, HCT, final turn, transition), reconciling 13 implementations: **3–6 weeks**.

---

## V6: Why zone half-court turns run longer

**Defenders do not gate HCO steps.** The gate is the shooter, the drive/FLSS driver, or the slowest offensive player (`:2318-2370`). Defender-gated steps: 0.01 per turn, 0.00 s.

Decomposition from emitted steps, played arm, 16 seeds, non-final HCO turns. Zone minus man, seconds per turn:

| component | `SEED_DEFENSES=1` Δ | `SEED_DEFENSES=0` Δ (control) |
|---|---|---|
| **total time_elapsed per turn** | **+1.02** (10.91 → 11.93) | −0.31 |
| offense-gated skeleton move steps | **+1.05** (6.10 → 7.15) | −0.19 |
|   of which natural travel above the floor | **+0.84** (3.17 → 4.01; 2.67 → 3.02 steps; gate distance 15.53 → 17.49 grid; rate 13.15 → 13.25 grid/s) | −0.09 |
|     gates with `stationary` archetype | **+0.64** (0.66 → 1.30) | −0.01 |
|     gates with `cruise` archetype | +0.20 (2.51 → 2.71) | −0.07 |
|   of which explicit step floors (subtle beats / forced shot) | +0.13 (0.69 → 0.74 steps) | −0.06 |
|   of which pass / mixed | +0.09 | −0.04 |
|   of which generic 0.5 s floor | −0.01 | −0.01 |
| entry steps (walk-up / handoff / kickout) | −0.02 (3.09 → 3.07) | −0.01 |
| post-shot sub-steps | −0.01 | −0.04 |
| ball-gated pass steps | −0.02 | −0.06 |

Also:
- Skeleton steps per turn: 6.46 → 6.48.
- Drive steps per turn fall under zone: 0.92 → 0.61.
- Play-type mix is unchanged (motion 467/923 man, 485/935 zone).

So under zone the offense's slowest mover travels **2 grid units further per gated step**, at the same rate, on **0.35 more gated steps per turn**. Most of the extra comes from offensive players tagged `stationary` covering longer distances. **Not established:** why stationary-tagged offensive players move further under zone. A plausible lead, not measured, is the interruption carried from the previous step (a non-gate offense player interrupted at step N starts step N+1 further from his spot).

---

## Deliverable

- **V1:** premise correct in kind (the stamp is the per-step placement target with tactical lag and no travel; played reads that placement after pre-shot interruption), overstated in size (mean 1.16 / 1.43 units). The 42 was stale stored coords the contest never reads.
- **V2:** HCO interruption is render-only (0 calls on sim, poisoned). Transition, FB, HCT and final-turn kinematics do run on sim.
- **V3:** see the table. Destinations, AG, floors, archetype inputs and gate inputs exist before emit. Per-step start chain, entry steps and post-shot sub-steps exist only inside the emitter.
- **V4:** see the table. The main change is rebounding (41.1 of 46.6 picks, 20.9 side flips/game), then over-the-back (21.5 of 42.1) and putback (5.4 of 6.8). All corrections with recalibration risk; pass interception is a regression risk only if switched off the stamp.
- **V5:** 13+ duration models. HCO skeleton-step extraction 2–3 days; HCO sim adoption with entry/post-shot ~2–3 weeks; all families 3–6 weeks.
- **V6:** +1.05 s/turn is offense-gated skeleton moves (+0.84 s natural travel, +0.64 s of it from `stationary`-archetype gates travelling further), not defenders.

**Is it buildable, and what is the first increment?** Yes, for HCO skeleton steps, since every input is available before emit except the entry steps and post-shot sub-steps. The first increment is to move the emitter's HCO duration and interruption math into a pure function the emitter calls, proven byte-identical on played and sim at 40/40, before sim reads it.
