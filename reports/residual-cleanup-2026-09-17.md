# Residual cleanup: R1 Final Turn, R2 stopper path

Written for: Jamie and the sessions deciding what to do with the two sim-coord residuals left by `4f856721a`.

**Short answer.** Neither residual can be closed for free, so neither was landed. Both would need a new placement build on the sim arm, which the brief's hard stop rules out.

| residual | status | why |
|---|---|---|
| **R1: Final Turn shot** | **DOCUMENTED AND LEFT OPEN** | No placement stamp exists on the Final Turn path on either arm (poison-verified). Played writes all ten from its own render build. |
| **R2: stopper path** | **DOCUMENTED AND LEFT OPEN** | Played's stopper coords come from a render build of the appended stopper step. That step authors only the ball handler, so nothing is derivable without a build. |

- **Step 0** (a new sim reference at `4f856721a`) was cut and written to `_documentation_master/projects/references/equiv_v3_sim_reference_4f856721a.json`.
- **Not committed:** `git commit` failed on a lock, `/Users/jamesdavies/gob-simplified/.git/worktrees/gob-animation-reward/index.lock` (0 bytes, created 12:38, no git process writing it, Cursor's `gitWorker.js` running). I didn't delete a lock another tool may own. Once it's cleared, the commit is one command (see Part 2).
- **No code changed.**

## Footing (rule 6e)

- **Worker:** equiv-v3 `scratch_equiv3_fbdedupe.py`. Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`.
- **Tree:** `4f856721a` (`GOB_SIM_HCO_COORD_WRITE=1`, default).
- **Played arm:** `ARM=played`, `_is_full_simulation` False only inside the four gated Animator methods (Pattern A).
- **Sim arm:** `ARM=sim`, `_is_full_simulation` True for the whole quarter loop.
- **Both footings:** `SEED_DEFENSES=1` and `SEED_DEFENSES=0`, seeds 8000–8039 (n=40), published CI = 1.96 × SEM.
- **Probes** (session scratchpad, not committed): `res/res_probe.py`, `res/taint_probe.py`. **Probe integrity:** every probe's game rows match the Step 0 reference runs, 160/160 each.

## Step 0: sim reference at `4f856721a`

| | `SEED_DEFENSES=1` | `SEED_DEFENSES=0` |
|---|---|---|
| played vs `d9a4f1517` | **40/40 byte-identical**, 0 errors (played reference stands, not re-cut) | **40/40 byte-identical**, 0 errors |
| sim cut reproduces pre-commit verification rows | 40/40 | 40/40 |
| sim pts/team | 82.74 ±3.23 | 84.69 ±3.63 |
| sim possessions | 48.30 ±2.65 | 50.30 ±2.21 |
| sim draws | 76,863.4 ±952.1 | 62,248.5 ±824.0 |
| independence, seed 8000 × 3 processes | identical (95.0 / 510 turns / 75,196), matches n=40 cell | identical (72.5 / 430 / 58,120), matches n=40 cell |
| FT-honour (windowed) | 2,420/2,427 = 99.7% | 2,954/2,968 = 99.5% |
| errors | 0 | 0 |

---

## Part 1: Scope

### R1-a: The premise on both arms

`resolve_final_turn_shot_logic`, `phase_resolution.py:8237-8261` at `4f856721a`:

```python
final_turn_animations = None
try:
    final_turn_animations = Animator(game).skeleton_to_animations(
        skeleton, off_lineup, def_lineup, add_defenders=True
    )
    apply_coords_from_animations_list(game, final_turn_animations)
except Exception as _ft_sync_err:
    ...
_ft_terminal = (
    _uess_sync_emitted_shot_coords(game, skeleton, final_turn_animations, roles, "HCO")
    if final_turn_animations else None
)
if _ft_terminal is not None:
    roles["shot_spot"] = dict(_ft_terminal)
else:
    set_shooter_coords_from_skeleton_last_step(game, skeleton, roles)  # fallback: skeleton shot location
...
shot_result = game.shot_manager.resolve_shot(roles)
```

- **Played:** `skeleton_to_animations` builds (the flag is False inside the gated method), `apply_coords_from_animations_list` writes all ten row-ends, then `_uess_sync_emitted_shot_coords` writes all ten to the emitted shoot-step coords.
- **Sim:** `skeleton_to_animations` returns `[]` (`animator.py:1213`), so the apply is a no-op, `_ft_terminal` is `None`, and only `set_shooter_coords_from_skeleton_last_step` writes: **shooter only**.
- **The arms do diverge.** And this `resolve_shot` passes **no `shot_attempt_geometry`**, so the Final Turn contest reads `player.coords` directly (`shot_manager._player_xy`): stale defenders on sim.

### R1-b: Is there a stamp to read?

**No, on either arm.** Per game, n=40:

| | played `D=1` | sim `D=1` | played `D=0` | sim `D=0` |
|---|---|---|---|---|
| Final Turn shots (`TurnManager.resolve_final_turn_shot`) | 2.48 | 3.77 | 2.48 | 3.90 |
| reaching the Final Turn `skeleton_to_animations` call (rest route to FLSS) | 2.20 | 3.35 | 2.23 | 3.45 |
| `compute_defender_grid` calls during Final Turn shots | **0** | **0** | **0** | **0** |
| complete defense+offense stamp on the last step | **0** | **0** | **0** | **0** |
| any defense stamp on any step | **0** | **0** | **0** | **0** |

- **Poison:** one extra `compute_defender_grid` per Final Turn shot moves the counter by exactly the Final Turn-shot count on every seed (`SEED_DEFENSES=1`, 8000–8007): played 2/3/1/2/2/3/3/2 against 2/3/1/2/2/3/3/2 shots; sim 5/3/5/4/1/4/3/4 against 5/3/5/4/1/4/3/4. The zero is real.
- **Cost of creating a stamp** (a new placement build per Final Turn shot on sim), measured as the real `compute_placement_grids` build on this footing:
  - Seeded: 1.87 ms and 80 draws per build (5.7-step skeletons). × 3.35 per game ≈ **6.3 ms and ~270 new draws per game**.
  - Unseeded: 0.50 ms and 43 draws per build ≈ **1.7 ms and ~150 draws per game**.
  - The Final Turn skeleton is shorter (alignment → pass → shoot), so the per-build figures are an upper-side estimate.
- **Hard stop applies:** new build, new draws.
- **No build-free substitute:** the alignment destinations (`_build_final_turn_defense_alignment` / `_offense_alignment`, fixed `HCO_STRING_SPOTS`, drawn before resolution on both arms) are not played's Final Turn positions. Distance to the coords played's contest reads:
  - defense 12.16 (`D=1`) / 18.29 (`D=0`)
  - offense 23.36 / 23.81
  - shooter 22.77 / 22.64

  Sim today reads 30.67 / 28.10 from those destinations on defense. Writing them would swap one wrong position for another; not a same-shape fix.

### R1-c: Frequency and consumers

Final Turn shots per game are in R1-b.

**Next turn after a Final Turn shot, per game:**
- played `D=1`: BASELINE_INBOUND 1.35, DREB 0.57, HCO 0.17
- sim `D=1`: BASELINE_INBOUND 2.23, DREB 0.75, OREB 0.25, HCO 0.07
- played `D=0`: BASELINE_INBOUND 1.20, DREB 0.47, HCO 0.38, OREB 0.12
- sim `D=0`: BASELINE_INBOUND 2.45, DREB 0.60, HCO 0.28, OREB 0.10

**`player.coords` reads per game, from the Final Turn write point to the end of that turn:**

| consumer | played `D=1` | sim `D=1` | played `D=0` | sim `D=0` |
|---|---|---|---|---|
| `eoq_debug_log._coords_for_player` | 112.2 | 137.3 | 113.5 | 141.4 |
| `position_snapshot_ledger.collect_lineup_positions` | 22.0 | 33.5 | 22.2 | 34.5 |
| `shot_micro_movements.build_micro_coords_snapshot` | 22.2 | 33.5 | 23.0 | 34.5 |
| **shot contest `shot_manager._player_xy`** (no frozen geometry) | 6.2 | **17.1** | 8.8 | 16.3 |
| **rebound selection `shared._rebound_distance`** | 11.4 | **13.4** | 9.3 | 8.5 |
| `shot_manager.resolve_shot` | 2.6 | 3.5 | 2.8 | 3.6 |
| getback selection (`_player_xy` + `_matchup_spot_at_shot`) | 2.7 | 2.6 | 8.6 | 11.2 |
| `covert_release._player_x` | 1.9 | 1.8 | 1.4 | 2.4 |

**The turn after a Final Turn shot:**

| consumer | played `D=1` | sim `D=1` | played `D=0` | sim `D=0` |
|---|---|---|---|---|
| `eoq_debug_log._coords_for_player` | 100.5 | 164.6 | 100.5 | 143.3 |
| rebound selection `_rebound_distance` | 3.0 | 6.7 | 3.0 | 3.9 |
| position snapshots | 3.5 | 10.5 | 7.0 | 11.8 |
| `select_defender_closest_to_victim` | 0.1 | 0.6 | 0.4 | — |
| over-the-back `resolve_over_the_back_foul` | **0** (none listed) | **0** | **0** | **0** |
| putback defender `_resolve_oreb_putback_defender` | **0** | **0** | **0** | **0** |

- **Over-the-back and putback zeros:** absent from the census; not separately poisoned. The read counter itself is poisoned in the previous report and reads them 7–212/game elsewhere.
- **Next-turn coord seed:** `sync_lineup_coords_from_turn` read the Final Turn-written value (the shooter) 3.35/game on sim, 3.45 unseeded. Most Final Turn shots end the quarter and the next turn is a BASELINE_INBOUND.
- **Buzzer putbacks are rare:** a Final Turn shot is followed by an OREB turn 0.25/game on sim (0.10 unseeded), 0–0.12 on played.
- **What R1 actually affects:** the Final Turn **contest** (17/game stale defender reads on sim) and its **rebound pick** (13/game), not putbacks.

### R1-d: Guard

Not landed, so no guard.

### R2-a: Where played's stopper-step coord comes from

`resolve_half_court_offense_logic`, stopper branch, `phase_resolution.py:9070-9083` at `4f856721a`:

```python
animator = Animator(game)
animations = []
if skeleton and "steps" in skeleton:
    animations = animator.skeleton_to_animations(
        skeleton, off_lineup, def_lineup, add_defenders=True
    )
if animations:
    apply_coords_from_animations_list(game, animations)
else:
    _write_sim_hco_placement_coords(game, skeleton, off_lineup, def_lineup, "HCO stopper")
```

On played, `skeleton` here is the output of `apply_stopper_system_to_skeleton`: truncated to the stop step plus the appended stopper step. `skeleton_to_animations` builds that skeleton, including placement of every defender on the appended step, and `apply_coords_from_animations_list` writes each player's row **end**, the appended step. **Matching it exactly on sim requires that build.** Per the hard stop: not done.

### R2-b: Is there a post-append stamp?

**No.** `compute_defender_grid` calls after `apply_stopper_system_to_skeleton` returns a truncated skeleton within the same turn: **0** on both arms and footings (18.05 / 19.70 stopper turns per game `D=1`; 14.93 / 17.30 `D=0`). The counter is the same wrapper the R1 poison verified. `_stamp_contest_defender_grid` runs only on the pre-walk, walk-time and coverage-pass skeletons, all before the stopper transform.

### R2-c: Is the stopper step derivable without a build?

**No.** The appended stopper step carries `pos_actions` for **the ball handler only** (`apply_stopper_system_to_skeleton`, `phase_resolution.py:~4127-4150`: `{"timestamp": stop+300, "pos_actions": {}, "events": [...]}` plus the ball handler's `handle_ball` at his stop location). There are no authored destinations for defenders or the other four offense players.

On played, defender positions on that step come from placement (`get_defender_coords`, zone assignment), which draws from `sim_rng`. Nothing on the skeleton is a (start, destination, duration, rate) travel problem, and `apply_coords_from_animations_list` uses placement row-ends, not interruption, so the rate helpers have nothing to compute.

Emulated decomposition on played: defender row-end from played's own render vs the stop-step stamp the sim write uses. Grid units, n=40.

| component | `SEED_DEFENSES=1` (n=3,050) | `SEED_DEFENSES=0` (n=2,090) |
|---|---|---|
| **total** (played render row-end vs stop-step stamp) | mean **2.99**, p50 1.00, p90 9.06, max 24.3 | mean **0.71**, p50 0.00, p90 2.00 |
| stopper-step effect (same render draw: row-end vs its own stop-step row) | mean **2.68**, p90 9.06 | mean **0.06** |
| stop step: render draw vs stamp draw | mean 1.13, p90 3.00 | mean 0.74 |
| subset: lagged read on stop step (28.9% / 34.2%) | total 2.95 (stopper effect 2.36) | total 1.18 (0.15) |
| subset: subtle-beat stop step (15.6% / 2.2%) | total 4.37 (3.61) | total 0.49 (0.09) |
| subset: attack-drive override on stop step | 0% | 0% |
| subset: none of these (55.5% / 63.7%) | total 2.61 (2.59) | total 0.47 (0.02) |

- **The residual is almost entirely zone.** The stopper-step effect is 2.68 with the catalogue seeded and 0.06 without, so appended-step re-placement moves defenders under zone and barely under man.
- **Why this differs from last report's 4.13:** that emulation measured played consumers' coords against the *nearest* fully stamped step, which was 2–5 steps back on 26% of stopper turns. Here the stop step is fixed at −2 and compared against the render row-end.
- **No candidate fix exists** that doesn't build the appended step.

### R2-d: Does it matter?

**Next turn after a stopper turn, per game:**
- played `D=1`: SIDE_INBOUND 11.85, HCO 5.12, TIMEOUT 1.07
- sim `D=1`: 12.40 / 5.85 / 1.45
- played `D=0`: 8.88 / 5.15 / 0.88
- sim `D=0`: 10.35 / 5.83 / 1.12

**Reads of a coord whose value is unchanged since the stopper-path write**, per game (value-tainted census: a later write of the same value keeps the taint, any change clears it):

| consumer | played `D=1` | sim `D=1` | played `D=0` | sim `D=0` |
|---|---|---|---|---|
| **next-turn seeds** `sync_lineup_coords_from_turn` | 302.8 | 450.8 | 242.5 | 424.9 |
| **next-turn seeds** `build_final_coords` | 151.9 | 285.3 | 124.2 | 272.4 |
| position snapshots (ledger) | 186.8 | 269.4 | 155.8 | 261.0 |
| `turn_manager._ensure_lineup_fields` | 3.6 | 27.6 | 3.4 | 35.0 |
| bounce-spot lineup filter | 1.9 | 24.4 | 1.5 | 21.4 |
| **steal fast-break routing** `steal_fast_break_routing._coord_of` | 11.9 | 15.9 | 9.5 | 10.4 |
| `phase_resolution.add_player_movement` | — | 16.1 | — | 10.2 |
| **rebound selection** `_rebound_distance` | 1.1 | 12.5 | 0.9 | 12.1 |
| `summarize_game_state` | 7.6 | 12.8 | 7.0 | 12.1 |
| `game_manager._maybe_stamp_hco_setup` | — | 8.2 | — | 5.0 |
| **DREB turn** `_build_dreb_turn_from_miss` | 0.5 | 8.1 | 0.4 | 6.5 |
| after-steal drive integration | 7.7 | 9.7 | 2.6 | 6.9 |
| **over-the-back** `resolve_over_the_back_foul` | 0.7 | 7.4 | 0.6 | 6.6 |
| **turnover** `resolve_turnover_logic` | 2.4 | 7.3 | 1.9 | 4.7 |
| free throw `resolve_free_throw_logic` | 0.3 | 7.0 | 0.3 | 8.5 |
| `capture_free_throw_animation` (played render) | 26.3 | — | 30.8 | — |
| `setup_baseline_inbound` | 0.1 | 3.2 | 0.1 | 4.3 |
| offensive rebound `resolve_offensive_rebound` | — | 2.2 | — | 2.3 |
| **putback defender** `_resolve_oreb_putback_defender` | — | 1.6 | 0.03 | 1.7 |
| rim-runner FB `_player_x/_y` | 0.2 | 2.6 | — | 2.7 |
| DREB FB arming `_coords_of` | 0.05 | 1.5 | 0.07 | 0.8 |

- **Stopper-path coords are read, mostly as next-turn seeds** (≈450 sync / ≈285 `build_final_coords` reads per game on sim).
- **Gameplay consumers on sim:**
  - steal fast-break routing (~16/game)
  - turnover resolution (~7)
  - rebound selection (~12)
  - over-the-back (~7)
  - DREB build (~8)
  - free throws (~7)
  - putback defender (~1.6)
- **It's still a small residual:** mean 2.99 units seeded, 0.71 unseeded, against the 26–35 units the sim write already removed.
- **Verdict:** meaningfully read, but not closable without a build.

### R2-e: Land?

**No.** R2-c yields no build-free, draw-free fix. **Cost of closing it:** a placement build of the truncated skeleton on each sim stopper turn, 19.70/game seeded × (1.87 ms, ~80 draws) ≈ **37 ms and ~1,580 new draws per game**; unseeded 17.30 × (0.50 ms, ~43) ≈ **9 ms and ~740 draws**. That's a Sim Perf Capstone decision, not a cleanup.

---

## Part 2: What was landed

- **R1:** nothing (hard stop).
- **R2:** nothing (hard stop).
- **Step 0 reference artifact:** written to `_documentation_master/projects/references/equiv_v3_sim_reference_4f856721a.json`, **uncommitted** because of the git lock above. Once the lock is released:

  ```
  git add _documentation_master/projects/references/equiv_v3_sim_reference_4f856721a.json
  git commit -m "Record the equiv-v3 sim-arm reference cut at 4f856721a"
  ```

  It holds per-seed rows (points, possessions, draws, turns, fingerprint) for 8000–8039 on both footings, the aggregate cells, the independence and FT-honour results, and the played re-confirmation.

## Verification

Nothing was landed, so the per-change verification (played 40/40, flag-off 40/40, residual before/after with poison, draws, gates, wall-clock, blast radius) has nothing to verify. Step 0's gates are in the Step 0 table: played 40/40 vs `d9a4f1517` on both footings; sim reference independence and FT-honour pass; 0 errors.

## Not covered

- **R1 Final Turn:** sim still updates only the shooter, and the Final Turn contest reads stale defenders on sim (~17 reads/game). Closing it needs a placement build on the Final Turn skeleton, ≈3.35 builds/game on sim.
- **R2 stopper:** sim writes the stop step's placement. Played renders the appended stopper step (+2.68 units under zone, +0.06 under man).
- **Crash destinations, rebound selection, the 1–6 dice roll in `calculate_rebound_score`:** untouched (next workstream).
- **`animator.py:1213` full-sim skip, the played arm, `get_ball_handler_from_skeleton`'s accept list:** untouched.
- **Untracked files not created by this session:** `reports/READY--TEST-can-you-see-this-in-cursor.md` and `reports/READY--sim-coord-fix-landed-3-calls-for-you.md`, left alone.
