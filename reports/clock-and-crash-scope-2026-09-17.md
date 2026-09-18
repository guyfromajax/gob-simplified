# Sim half-court clock (Part A) and crash-destination parity (Part B)

Written for: Jamie and the sessions deciding whether to converge the sim clock and whether the crash-destination workstream is buildable.

**Short answer.**
- **Part A: the clock is CONFIRMED as the bulk of the arm gap** — pointing played at sim's clock closes it from **+11.39 ±3.46 to +0.50 ±3.93** pts/team (`SEED_DEFENSES=1`). **But both proposed levers are NULL**, and one points the wrong way. Nothing was landed.
- **Part B: buildable.** Applying crash destinations on sim is arithmetic over data it already has: **no new build, no new draw**, and the predicted positions land 0.05 grid units from played's.
- **No code changed in this pass.** No commits beyond the Step 0 reference already committed as `f28f52475`.

## Footing (rule 6e)

- **Worker:** equiv-v3 `scratch_equiv3_fbdedupe.py`. Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`.
- **Tree:** `f28f52475` (= `4f856721a` plus the reference commit; no code differences).
- **Played arm:** `ARM=played`, `_is_full_simulation` False only inside the four gated Animator methods at Pattern A.
- **Sim arm:** `ARM=sim`, `_is_full_simulation` True throughout the quarter loop.
- **Both footings**, seeds 8000–8039 (n=40), CI = 1.96 × SEM.
- **Reference:** `_documentation_master/projects/references/equiv_v3_sim_reference_4f856721a.json` for sim; `d9a4f1517` for played.
- **Probe integrity:** clock probe 160/160 and Part B probe 160/160 game rows identical to the `4f856721a` reference. Probes live in the session scratchpad (`clk/clock_probe.py`, `clk/b_probe.py`), uncommitted.

---

## Part A: sim half-court clock

### A1: The prior finding reproduces

**What the earlier experiment changed:** `scratch_armgap_cf.py` with `CF_CLOCK=1` wraps `TurnManager._emit_hco_animation_steps` on the **played** arm and restores `result["time_elapsed"]` to its pre-emit value, i.e. played keeps the legacy `calc_skeleton_step_timing_contract` estimate instead of the emitted-step clock. Played-only; sim untouched.

Re-run at this tree, n=40. The played CF rows are **identical 40/40** to the earlier run, so the experiment itself is unchanged; only the sim reference moved.

| | played pts/team | arm gap (sim − played) | possession gap |
|---|---|---|---|
| `D=1` played as-is | 71.35 ±2.55 | **+11.39 ±3.46** | +5.65 ±2.69 |
| `D=1` played with sim's clock | 82.24 ±3.59 | **+0.50 ±3.93** | +2.30 ±3.25 |
| `D=0` played as-is | 74.97 ±2.91 | **+9.71 ±4.05** | +3.67 ±2.56 |
| `D=0` played with sim's clock | 80.78 ±3.18 | **+3.91 ±4.08** | +0.90 ±2.88 |

The earlier "+13.75 → +2.86" was against the dead `d9a4f1517` sim reference; against the new one it is **+11.39 → +0.50** (`D=1`) and **+9.71 → +3.91** (`D=0`). 0 errors.

### A2: Decomposition

**Game clock consumed per HCO turn** (one `resolve_half_court_offense` call; a possession can contain several):

| | mean | p50 | p90 | n |
|---|---|---|---|---|
| played `D=1` all | 11.58 | 11 | 17 | 4,654 |
|   zone / man | 12.04 / 11.12 | 12 / 11 | 18 / 17 | 2,316 / 2,338 |
| sim `D=1` all | 10.42 | 9 | 19 | 5,111 |
|   zone / man | 10.77 / 10.08 | 9 / 9 | 21 / 18 | 2,537 / 2,574 |
| played `D=0` all | 11.17 | 11 | 17 | 4,758 |
|   zone / man | 11.11 / 11.24 | 11 / 11 | 17 / 17 | 2,395 / 2,363 |
| sim `D=0` all | 10.16 | 9 | 18 | 5,175 |
|   zone / man | 10.18 / 10.14 | 9 / 9 | 18 / 18 | 2,612 / 2,563 |

Distribution shape (whole seconds): played is single-peaked around 9–13 s. Sim carries a **spike at 3 s** (392 turns at `D=1`, 391 at `D=0`; played has 2 and 4) — short skeletons the per-step 1 s floor cannot lift further — and a fatter tail (p90 19–21 s under zone).

**Paired decomposition on the played arm** (each turn's own contract vs its own emitted clock, restricted to turns where the contract call matched the pre-emit `time_elapsed` and the replicated contract reproduced the real one exactly; 97.2–97.9% matched, replica ok on 18,024 of 18,593 calls):

| `SEED_DEFENSES=1` | all (n=4,370) | zone (2,126) | man (2,244) |
|---|---|---|---|
| contract, rounded (what sim uses) | 9.43 | 9.26 | 9.59 |
| **(a) rounding + 1 s floor + cap** | **−3.33** | −3.09 | −3.55 |
| contract, unrounded | 6.10 | 6.17 | 6.04 |
| **(b) gate-set effect** | **−0.13** | −0.13 | −0.14 |
| contract, unrounded, played's gate set | 5.97 | 6.04 | 5.90 |
| **(c) everything else** | **+5.18** | +5.41 | +4.95 |
| emitted `time_elapsed` (played) | 11.14 | 11.46 | 10.85 |
| (c) split: entry steps | 3.15 | 3.13 | 3.17 |
| (c) split: post-shot sub-steps | 1.03 | 1.03 | 1.03 |
| (c) split: skeleton steps vs the contract's model | ~1.00 | ~1.26 | ~0.75 |

`SEED_DEFENSES=0` is the same shape: (a) −3.55, (b) −0.11, (c) +4.77 (entry 3.21, post-shot 1.04), and **no zone/man split** (zone −3.54 / −0.09 / +4.71 vs man −3.56 / −0.12 / +4.84). The residual is **not** zone-only, unlike R2.

**Reading:**
- **(a) is the largest single term and it inflates sim.** Sim's rounded contract (9.43) is 3.33 s *above* its own unrounded value (6.10), because each step is rounded and floored at 1 s. Sim's clock is already 1.2 s/turn *shorter* than played's; unrounding it would take it to ~6.1 s against played's 11.1 and **widen** the gap.
- **(b) is null.** Played's HCO skeleton steps gate on the shooter, the drive driver, or the slowest offensive mover; **defenders never gate** (measured earlier at 0.01 steps/turn). The `transition_bridge.py:290` "slowest of all players" path applies to walk-up/transition steps, which the contract does not model at all.
- **(c) is where the divergence lives:** entry orchestration (3.15 s/turn: walk-up, handoff, kickout), post-shot sub-steps (1.03), and per-step model differences (~1.0: placement coords vs skeleton spots, archetype rates, the 0.5 s emitter floor, ball-flight time).

### A3: Can sim use the gate set without a build?

- **Gate set on played** is decided inside the emitter step loop (`skeleton_step_emitter.py:2318-2370`) from the skeleton's own flags (shoot action, `_attack_drive.driver_gate`, FLSS) plus start/end coords.
- **Available on sim?** Yes. The flags are on the skeleton, and post-`4f856721a` sim holds the placement grids for defense and offense. With `_ag_grid_per_game_sec` this is arithmetic: **no new build, no new draw.**
- **Emulated before writing code** (the S4 pattern), and the answer is that it isn't worth landing: predicted clock change **−0.13 s per HCO turn** (`D=1`; −0.11 unseeded), in the direction that *shortens* sim turns and therefore widens the arm gap. Predicted arm-gap change: worse by roughly 0.1–0.2 s/turn of clock, against an 11.4-point gap driven by a 1.2 s/turn shortfall.
- **The unrounding lever** is likewise counter-productive: **+3.33 s/turn removed** from a clock that is already too short.

### A4: Land

**Nothing landed.** Neither `GOB_SIM_CLOCK_UNROUNDED` nor `GOB_SIM_CLOCK_GATE_SET` was written, because A3 shows both move sim's clock away from played's. Landing flags proven null would add two branches to the sim clock path for no measurable convergence. The four-arm measurement (off/off, on/off, off/on, on/on) was not run for the same reason: the emulation already gives the per-turn effect of each.

### A5: Verification

Not applicable — no code changed. Step 0's gates stand (played 40/40 vs `d9a4f1517` on both footings; sim reference independence and FT-honour pass; 0 errors), and both probes reproduce the reference 160/160.

For context at the current tree, the divergence the brief called out:

| per game | played `D=1` | sim `D=1` | played `D=0` | sim `D=0` |
|---|---|---|---|---|
| Final Turn shots | 2.48 | 3.77 | 2.48 | 3.90 |
| HCO turns | 116.3 | 127.8 | 119.0 | 129.4 |
| clock per HCO turn | 11.58 | 10.42 | 11.17 | 10.16 |

Final Turn shots do **not** converge, and nothing in this pass changed them; sim reaches ~1.4 more per game because its shorter half-court turns leave more end-of-quarter windows.

### A6: Verdict

**CONFIRMED as a material share of the arm gap — and the two proposed levers are NULL.** The number: pointing played at sim's clock moves the gap from **+11.39 ±3.46 to +0.50 ±3.93** pts/team (`D=1`), so the clock accounts for essentially all of it; but of the 1.72 s/turn sim shortfall, rounding contributes **−3.33 s in the wrong direction**, the gate set **−0.13 s**, and the real content is entry orchestration (**3.15 s/turn**), post-shot sub-steps (**1.03**) and the per-step model (**~1.0**). Converging the clock means giving sim a model of those three, which is the shared-kinematics workstream, not a flag.

---

## Part B: crash-destination sim parity (scope only)

### B1: Author and apply

**Corrected:** crash destinations are authored in **five** branches, not two. All are `shot_manager.py`, all the same shape:

```python
if is_home_team_shooting:
    rebounder_coords = {"x": random.randint(85, 92), "y": random.randint(20, 30)}
else:
    rebounder_coords = {"x": random.randint(8, 15),  "y": random.randint(20, 30)}
```

| branch | offense map | defense map |
|---|---|---|
| MAKE | `:2057` | `:2076` |
| shooting foul on a miss | `:2160` | `:2172` |
| defensive foul on a miss | `:2264` | `:2279` |
| fast-break miss | `:2444` | `:2454` |
| **HCO miss** | `:2550` | `:2565` |

- **Confirmed:** random, independent of shot origin, bounce spot, player position, matchup and attributes (the only inputs are which team is shooting and the crash-pool membership).
- **Confirmed:** `select_rebounder_by_score` at **`:2483`** runs before the HCO miss crash coords are authored at `:2550`/`:2565`.
- **Confirmed:** sim never applies them. Applying happens only in the emitter, via `_build_post_shot_sub_steps` → `_apply_overlay_motion_to_shoot_step` / `_build_ball_motion_sub_step`, whose end coords reach `player.coords` through `sync_lineup_coords_from_turn`. That builder runs **206–219 times per game on played and 0 on sim**.
- **Correction to an earlier claim:** get-back and release destinations are *not* purely random — their bands come from the player's AG and an IQ read (`covert_release.sample_getback_coords` / `sample_release_coords`) — but the rebound-cluster destinations are.

### B2: Does sim parity need a build?

**No. It is arithmetic over data sim already has.**

Every post-shot sub-step interrupts each overlay player from his previous end toward the same destination at the same archetype rate (`_OVERLAY_ARCHETYPES`: rebounders `standard`, get-back/release `sprint`), so the whole sequence collapses to **one interruption from the shoot-step start toward the destination over T(shoot step) + Σ T(post-shot steps)**.

Emulated on played, predicting each overlay player's end from **sim-available inputs only** (start = the placement stamp `4f856721a` writes; destination = the map on the turn result; rate = `_ag_grid_per_game_sec`; duration = the emitted step times):

| `SEED_DEFENSES=1`, n=26,939 overlay players | mean | p50 | p90 | max |
|---|---|---|---|---|
| **arithmetic prediction** | **0.05** | 0.00 | 0.00 | 9.1 |
| snap straight to the destination | 1.20 | 0.00 | 4.53 | 38.1 |
| no crash motion (today's sim) | 13.36 | 12.17 | 22.85 | 51.1 |

By map: offense rebounders 0.00, defense rebounders 0.10, get-back 0.00, release 0.19. `SEED_DEFENSES=0` matches (0.06 / 1.24 / 12.78, n=28,458).

- **Draws:** `_build_post_shot_sub_steps` consumes **0 `sim_rng` draws** on played (206.2 calls/game seeded, 219.0 unseeded). Applying crash destinations on sim adds **no draw**.
- **Cost:** played spends 30–51 ms/game in the whole builder, most of which is building schema steps sim doesn't need. The arithmetic alone is one interpolation per overlay player, ~27k per game across 40 games ≈ 670 per game, microseconds each.
- **One input is not yet available pre-selection:** the duration. `T(shoot step)` is an emitter construct and the flight time needs `uses_shot_arc`, set at `:2734` *after* selection. For **applying** crash positions after resolution (parity with played) the durations are all known by then. For **selecting from** arrival positions (B3) they are not, without moving the arc flag earlier or adopting a duration rule.

### B3: Ordering — selection vs authoring

**What it would take:** author the crash maps before `:2483`, compute the arrival positions (B2 arithmetic), then select. Mechanically the authoring block depends on nothing that selection produces.

- **Inputs to the crash blocks:** the crash pools (`offense_rebounders` / `defense_rebounders`, fixed at `:1783-1888`), the get-back and release lists, `d_read` / `good_release_flag` (rolled at `:1833-1834`), the shooter id, and which team is shooting. **None is the rebounder, the rebound stat, `last_rebound` or `rebounderId`.**
- **What would break or shift:**
  - **RNG order.** Selection currently draws first (`calculate_rebound_score`'s `randint(1,6)` per candidate, plus a tie `random.choice`); the crash spots draw two `randint`s per crasher. Swapping the order reshuffles the stream for every downstream consumer on both arms: a full re-baseline, both references.
  - **The arrival duration** needs `uses_shot_arc` (`:2734`) moved ahead of selection, or a fixed rule. Moving it is itself a stream change.
  - **`canonicalize_post_shot_overlays`** (`shared.py:3507`) drops the shooter, get-back and release players from the rebounder maps; with selection reading those maps, the exclusion order becomes load-bearing for *selection*, not just rendering.
  - **The five authoring branches** would all need the same treatment or they diverge from each other (MAKE and foul branches author crash maps too).
  - **Consumers that read the maps after resolution** are unaffected in kind: the HCO/HCT/CR emitters, `strip_terminal_rebound_fields`, and the next-turn fast-break resolvers that read get-back/release coords.
  - **Not affected:** the DREB/OREB turns and `_build_dreb_turn_from_miss`, which read `player.coords` rather than the maps.

### B4: What the `randint(1,6)` is doing

`calculate_rebound_score` = `(RB×0.5 + ST×0.3 + IQ×0.1 + CH×0.1) × randint(1,6)`. Measured over every HCO rebound selection, n=40:

| | played `D=1` | sim `D=1` | played `D=0` | sim `D=0` |
|---|---|---|---|---|
| selections measured | 1,728 | 1,888 | 1,836 | 1,985 |
| **winner changes if the dice are replaced by their mean (3.5)** | **50.6%** | 49.8% | 50.3% | 51.0% |
| highest-composite eligible player loses | 69.2% | 71.2% | 70.5% | 69.3% |
| lowest-composite player wins | 0.3% | 0.6% | 0.2% | 0.5% |
| winner also holds the top dice roll | 25.3% | 25.6% | 27.0% | 26.3% |
| within-selection log SD, attribute composite | 0.403 | 0.411 | 0.407 | 0.412 |
| within-selection log SD, dice | 0.559 | 0.556 | 0.558 | 0.557 |
| **signal/noise** (log SD of score without dice ÷ log SD of dice) | **1.085** | 1.108 | 1.085 | 1.096 |

**Reading:** the dice decide the winner **half the time**. The attribute composite spreads candidates by 0.40 in log terms while the dice spread them by 0.56, so the roll is the larger single source of variation; distance to the bounce is what keeps signal/noise near 1.09 rather than below 1. The lowest-composite player almost never wins (0.2–0.6%), so the dice are not pure chaos — they scramble the middle of the field, not the extremes. **Not changed; Jamie's call.**

### B5: Recommendation

The crash-destination workstream **is buildable inside the SPC constraints**: applying crash destinations on the sim arm is a single interpolation per overlay player from data sim already holds after `4f856721a`, with no placement build, no `skeleton_to_animations` call, and zero new draws, and it reproduces played's positions to 0.05 grid units. That alone would close the over-the-back in-play gap (25.9/game sim vs 39.0 played) and give sim the same post-shot geometry as played for rebounds, putbacks and next-turn fast-break starts. If even that is judged too invasive, snapping players to their crash destination without the interruption is 1.20 units from played and needs no durations at all. What is **not** free is Jamie's actual goal — selecting the rebounder from crash *arrival* positions — because that requires reordering authoring ahead of selection, which reshuffles the RNG stream for both arms and needs `uses_shot_arc` moved earlier; that is a deliberate re-baseline, not a cleanup. The cheapest thing that gets most of the value is therefore: apply crash destinations on sim (parity, free), and treat selection-from-crash and the `randint(1,6)` as one combined design decision afterwards, since the dice already decide half of all rebounds and would swamp any positional signal the reorder introduces.

---

## Verification

Nothing landed, so there is no per-change verification. Standing gates at this tree:

| | `SEED_DEFENSES=1` | `SEED_DEFENSES=0` |
|---|---|---|
| played vs `d9a4f1517` | 40/40 byte-identical | 40/40 byte-identical |
| sim vs the `4f856721a` reference | 40/40 (both probes, 160/160 rows each) | 40/40 |
| independence (sim, seed 8000 × 3) | identical | identical |
| FT-honour (sim) | 99.7% | 99.5% |
| errors | 0 | 0 |

## Not covered

- **The clock convergence itself:** entry orchestration, post-shot sub-steps and the per-step model are the content of the gap; giving sim a model of them is the shared-kinematics workstream.
- **No fresh sim reference is owed** — no flag landed and no default flipped.
- **R1 (Final Turn) and R2 (stopper):** untouched. A3's gate-set finding does **not** make either free; both still need a placement build.
- **`animator.py:1213`, the played arm, `get_ball_handler_from_skeleton`'s accept list, rebound selection, the dice, crash destination values:** untouched.
- **Part B wrote no production code**, as instructed.
- **Untracked files not created by this session:** `reports/READY--TEST-can-you-see-this-in-cursor.md`, `reports/READY--sim-coord-fix-landed-3-calls-for-you.md`.
