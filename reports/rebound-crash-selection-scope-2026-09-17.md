# Rebounder selection from crash positions: scope

Written for: Jamie and the sessions deciding whether to move rebounder selection onto crash positions. Read-only pass; nothing was built, reordered or committed.

**Short answer.** Selection can't read crash *arrival* positions on both arms today:
- **The destinations are random.** HCO crash spots are a uniform integer draw in a fixed box beside the rim.
- **Arrival positions exist only on played,** and nothing computes an arrival window before selection on either arm.
- **The destinations are on the turn result for both arms,** and there is no circular dependency.

So the destinations would need designing first, and arrival depends on the shared kinematics function.

## Footing (rule 6e): applies to every number unless a line says otherwise

- **Worker:** equiv-v3, `scratch_equiv3_fbdedupe.py` at `5d44194c1`. Lancaster vs Bentley-Truman, sliders 2, traps 5, `SEED_PLAYS=1`, **`SEED_DEFENSES=1`**, `PYTHONHASHSEED=0`, one game per process, game id `0xE0000+(seed-8000)`, `ALIGN_RNG=0`, seeds 8000–8015 (n=16).
- **Played arm:** `ARM=played`. **`_is_full_simulation` is False only inside** `Animator.capture_fast_break_animation / capture_free_throw_animation / capture_halfcourt_animation / skeleton_to_animations`, True elsewhere. The HCO emitter still runs on this arm because the render animations exist.
- **Sim arm:** `ARM=sim`, **`_is_full_simulation` True** throughout the quarter loop.
- **Probe:** `scratchpad/rb/reb_probe.py` in the session scratchpad, not committed. Its game rows match the `d9a4f1517` reference **32/32**.
- **Replay check:** the probe records each HCO selection's dice (`calculate_rebound_score`), pools, coords, team bonus and penalties. Replaying with live coords reproduces today's winner **743/743 (played) and 855/855 (sim)**, so every counterfactual below uses the same dice, pools and bounce spot as the real game.
- **Arm divergence:** the two arms play different games from turn 1, so per-game counts differ partly because of that. Rates are the comparable figures.

---

## G1a: Are HCO crash destinations principled or random?

**Random.** The HCO miss path authors them after selection (`shot_manager.py:2536-2569`):

```
offense (:2537-2548): for each pos in offense_rebounders, skipping the shooter:
    home shooting: {"x": random.randint(85, 92), "y": random.randint(20, 30)}
    away shooting: {"x": random.randint(8, 15),  "y": random.randint(20, 30)}
defense (:2559-2569): the same draw for each pos in defense_rebounders
```

- **No real inputs:** the destination doesn't depend on shot origin, bounce spot, the player's start position, matchup, box-out geometry, or AG/ST. It is an 8×11 uniform box beside the attacked rim, the same box the fast-break branch uses (`:2437-2457`, left untouched).
- **Unrelated to the ball:** crash destination to bounce is mean 10.47 / p90 19.65 grid on played, 10.69 / 20.10 on sim.
- **Who crashes is decided before selection and is partly principled:**
  - Offensive get-back count: `roll_num_getback(offense_reb_value, rand)` plus `select_offense_getback_list` / `try_emergency_getback_vs_poised_fb` (`:1848-1888`).
  - Defensive release: a fast-break slider probability, then `select_covert_release_position` (`:1787-1822`).
  - Everyone else is in the crash pool.
- **Get-back and release coords are random inside principled bands:** `covert_release.sample_getback_coords` / `sample_release_coords` (`covert_release.py:~140-181`) draw `randint` inside an x/y band whose bounds come from the player's AG and an IQ read (`good_d` / `good_release`).
- **Board-crash overlay:** `transition_shot_board_crash.maybe_stamp_transition_shot_board_crash_overlays` covers FAST_BREAK / HCT / FCP only ("Idle players outside 11 of the basket get a random destination within 11 of the basket"). It is a no-op for HCO.
- **The only principled geometry at selection is the bounce spot:** `_compute_miss_bounce_spot` (`:383-399`) calls `calculate_bounce_spot` (`shared.py:1509`) from the shooter's grid position, with distance-based variance.

Selecting by distance to these destinations would be a second dice roll labelled as positioning.

## G1b: Does the crash / getback / release computation run on sim?

**Yes, on both arms. Its only downstream use for HCO runs on played only.** Per game (n=16):

| | played | sim |
|---|---|---|
| HCO rebound selections (`:2483`) | 46.4 | 53.4 |
| HCO misses whose result carries crash maps | **46.4 (100%)** | **53.4 (100%)** |
| crash map entries authored | 375.1 | 427.2 |
| `_calculate_getback_coordinates` calls | 32.7 | 49.4 |
| `_calculate_release_coordinates` calls | 11.6 | 15.3 |
| HCO post-shot sub-step builder (`skeleton_step_emitter._build_post_shot_sub_steps`, reads the crash maps) | 207.4 | **0** |

The post-shot builder figure includes throwaway emits and makes. **Poison for the sim zero:** calling the counted builder once per HCO miss reads 53 / 55 / 55 / 58 on sim (seeds 8000–8003), exactly matching the 53 / 55 / 55 / 58 HCO resolves. Played reads 277 / 267 / 251 / 272 against 220 / 209 / 206 / 215 unpoisoned.

## G1c: Where do the crash destinations live?

**On the turn result, on both arms. Only emitters turn them into positions, and for HCO that happens on played only.**

- **Write:** `result["offense_rebounder_coords"]` at `shot_manager.py:2548` and `result["defense_rebounder_coords"]` at `:2569`. Both run on both arms (G1b).
- **Getback / release:** `result["offense_getback_coords"]` `:2521`, `result["defense_release_coords"]` `:2531`.
- **Readers of the rebounder crash maps:**
  - `shared.canonicalize_post_shot_overlays` (`shared.py:3507-3584`), both arms: a role-exclusivity filter only.
  - HCO emitter `_build_post_shot_sub_steps` / `_apply_overlay_motion_to_shoot_step` (`skeleton_step_emitter.py:2936-2943`, `:~3580-3700`) and the legacy `_apply_post_shot_overlay` (`:3960`): bake them into `animation_steps` end coords. **Played only for HCO** (207.4 vs 0/game).
  - `hct_step_emitter._apply_post_shot_overlay` (`:458`) and `covert_release_step_emitter` (`:1740`): emitters for other turn types.
  - `eoq_perfection.strip_terminal_rebound_fields` (`:1076`): deletes them at end of quarter.
- **Not readers:**
  - `sync_lineup_coords_from_turn` deliberately does not apply overlay maps (`shared.py:3826-3844`).
  - The DREB turn (`game_manager._build_dreb_turn_from_miss`, `:1144-1157`) reads `player.coords`. Its docstring still says the sync applies the overlays, which is stale.
  - The DREB / OREB emitters don't read the maps.
- **Getback / release maps are also read by resolvers on both arms:** `phase_resolution.py:1817-1974` and `covert_release_drive_integration.py:69-112`.
- **Net:** positions derived from the crash destinations reach `player.coords` only through the HCO emitter's final step on played. On sim the maps are written and never applied.

---

## C1: Circularity

**No logical dependency, but the draw order is coupled.**

- **Inputs to crash / getback / release authoring (`:2510-2569`):**
  - `offense_rebounders`, `defense_rebounders`, `offense_getback_list`, `defense_release_list` (all decided at `:1783-1888`).
  - `d_read` (`:1833`), `good_release_flag` (`:1834`), shooter id, `is_home_team_shooting`, getback/release player AG.
  - None of them is the rebounder, the rebound stat, `last_rebound` or `rebounderId`.
  - The only rebounder-aware exclusion in `canonicalize_post_shot_overlays` is the FB-only `roles.outlet_passer`.
- **The coupling:** selection draws first (`calculate_rebound_score` `randint(1,6)` per candidate, plus `random.choice` on ties), then the crash spots draw two `randint`s per crasher. Reordering would change which `sim_rng` values each consumer receives: not a dependency, but not draw-neutral.

## A1: The arrival window

**It does not exist before selection.**

- **Available at selection time on both arms:**
  - Bounce spot (`:2459-2463`).
  - Shot spot.
  - The miss shot variant: `select_shot_variant` / `roll_shot_variant_extras` at `:2299-2306`, before selection.
- **Not available:** `uses_shot_arc`, which sets the flight rate (27 vs 20 grid/game-s), is decided at `:2734`, after selection.
- **Where the window is actually computed (only in the emitter's post-shot sub-steps):**
  - `flight_t = max(0.05, dist(shot_spot → _variant_flight_end) / shot_ball_flight_grid_rate(uses_arc))` (`skeleton_step_emitter.py:~3672-3684`).
  - Rattle hops N × `RATTLE_HOP_GAME_SECONDS` (0.114 s).
  - `BOUNCE_STEP_GAME_SECONDS` (0.857 s) (`constants/__init__.py:377`, `:406`).
- **Measured on played:** the emitted HCO post-shot window (sum of step T after the shoot step) is mean **1.59 s** (n=734).

## A1b: Does the window exist on sim?

**No, played only.** The HCO post-shot builder runs 0 times on sim (poisoned, G1b). Sim has most inputs (shot spot, variant, bounce spot) but not `uses_shot_arc` before selection, and never does the arithmetic. The destinations exist on both arms; arrival exists on played only. **This increment depends on the shared kinematics function; it isn't independent of it.**

## A2: Who moves, and from where

At the shot (`_freeze_hco_shot_attempt_geometry`, just before `resolve_shot`):

| | played | sim |
|---|---|---|
| defenders: coords vs StepState stamp at shot step | mean **1.14**, p50 0.00, p90 3.82 (n=3,505) | mean **26.40**, p50 19.89, p90 58.57 (n=3,965) |
| offense: coords vs skeleton shot-step spot | mean **0.00**, max 0.1 (n=1,918) | mean **21.43**, p50 16.12, p90 57.94 (n=2,137) |
| rebound pool: coords at selection vs bounce | mean 14.12, p90 24.04 | mean **29.31**, p90 61.40 |
| rebound pool: coords at selection vs crash destination | mean 14.52 | mean **35.92** |

- **Played:** coords are refreshed to the emitted shoot-step ends.
  - The defender residual (1.14) is the pre-shot-step interruption plus the placement draw, as in the kinematics pass.
  - Offense matches its skeleton spots exactly. Poison: offensive PG +3 after the emitted sync reads 3.00, others 0.00 (seeds 8000–8001).
- **Sim:** coords are stale by ~21–26 grid units at the shot (sim writes no coords during HCO). Today's selection on sim scores players at about twice the real distance from the bounce.

## S1: Box-out and physical contest in the rebound path today

**No box-out, seal or contact model. Only a score with a distance discount.**

- `calculate_rebound_score` (`shared.py:2201-2208`): `(RB×0.5 + ST×0.3 + IQ×0.1 + CH×0.1) × randint(1,6)`. ST enters only as the 0.3 weight, inside a 1–6× dice roll.
- `select_rebounder_by_score` (`shared.py:1728-1811`) applies:
  - The team bonus (`team_chemistry × rebound_modifier × 0.5`).
  - `× 1/(1 + distance_to_bounce/8)` (`REBOUND_DISTANCE_SCALE`).
  - `× 0.8` for offense (`OREB_REBOUND_SCORE_DISCOUNT`; its constant comment calls it "the defense's box-out / positioning advantage", a flat factor).
  - `× 0.8` for the shooter.
  - Tie-breaks on rebound_modifier, then MO, then chemistry, then `random.choice`.
- **Nearest thing to physical contact:** `resolve_over_the_back_foul` (`shared.py:878-940`). An opponent within 4 units of the rebounder triggers discipline thresholds, an IQ gate and a 1-in-2 call. It's a foul check after selection, not part of selection.
- **Cosmetic only:** the DREB emitter's failed-attemptor collapse (bounce ± 4x / 6y).

## B1: Blast radius

The counterfactual replays the same dice, pools and bounce spot. It is static: follow-on turns are not re-simulated.

| | played | sim |
|---|---|---|
| HCO selections / game | 46.4 | 53.4 |
| **today** OREB share of HCO misses | **25.4%** (11.8/game) | **30.9%** (16.5/game) |
| **select from crash destinations:** picks changed / game | **16.4 (35.4%)** | **27.5 (51.5%)** |
|   OREB↔DREB side flips / game | 8.8 | 13.9 |
|   OREB share | 27.1% (+1.6 pp, +0.75/game) | 26.4% (−4.4 pp, −2.38/game) |
|   DREB share | 72.9% | 73.6% |
| **select from emitted post-shot positions (arrival):** picks changed / game | 16.8 (36.5%), n=734 | **not computable (played only)** |
|   side flips / game; OREB share | 8.6; 27.5% vs 25.6% today | — |
| second-chance points per HCO OREB (until the possession flips or the next miss) | 1.656 (n=189) | 1.714 (n=262) |
| **estimated** Δ second-chance points / game (static, both teams) | **+1.24** | **−4.07** |

- **The arms converge.** The played−sim OREB gap goes from **5.5 pp** today to **0.7 pp** with crash-destination selection. The destinations come from the same random box on both arms, so sim's staleness drops out. That's by construction, not because the positioning is meaningful.
- **Ties** in the replay: 0 on both arms. Continuous scores; not poisoned.
- **Caveats:**
  - The shooter has no crash destination (46.4 / 53.4 per game), so he keeps live coords in the replay.
  - About 18 defenders per game (played 18.1, sim 18.0) are in the final `defense_rebounders` list but have no entry in `defense_rebounder_coords` on the returned result. They are not the release player (0 of 40 checked), the outlet passer (0) or the contest defender (0); 1 of 40 was the blocker. Something between authoring at `:2569` and the return removes them; not traced. They keep live coords in the replay.
  - The fallback-pool branch was never taken (winner outside pool: 0). Not poisoned.

**Other consumers that would shift** (readers of `rebounderId` / `rebound_type` / `last_rebound` / the stat). They shift with the identity changes and side flips above, not with the selection method:
- OREB turn (`turn_manager.resolve_offensive_rebound_turn`): putback / kickout routing, putback defender `_resolve_oreb_putback_defender`, over-the-back. These read the rebounder's `player.coords`, which are stale on sim.
- DREB turn (`game_manager._build_dreb_turn_from_miss`): over-the-back, capture animation.
- DREB fast-break arming and outlet: `shot_manager._build_dreb_outlet_pass_contract` / `_resolve_dreb_outlet_receiver`, `dreb_fast_break_arming`, covert release (`covert_release_drive_integration.py:85` resets `last_rebound`).
- `transition_event_detector.py:62-206`: FB eligibility on OREB/DREB.
- `eoq_clock_progression.apply_post_miss_rebound_routing` / `should_route_eoq_rebound` (`:324`).
- `game_manager.py:1050-1101`: `last_rebounder` / `last_rebound` stamping.
- Box score OREB/DREB/REB via `record_stat`, and whatever reads those (EOG progression, scouting).

---

## Deliverable

- **G1a:** random. HCO crash destinations are `randint(85,92)/(8,15) × randint(20,30)`, independent of shot, bounce, player, matchup or attributes. Get-back and release are random within AG/IQ bands; only the bounce spot is geometric.
- **G1b:** crash / getback / release authoring runs on both arms (100% of HCO misses: 46.4 played / 53.4 sim per game). The only HCO reader that turns them into positions runs 207.4/game on played and 0 on sim (poisoned).
- **G1c:** written onto the turn result at `shot_manager.py:2548 / :2569`, readable by both arms. Applied to positions only by the HCO emitter's post-shot sub-steps, which run on played only; sync and the DREB/OREB turns never read them.
- **C1:** no logical circularity. Draw order is coupled (selection dice before crash `randint`s), so a reorder is not draw-neutral.
- **A1:** does not exist before selection. `uses_shot_arc` (flight rate) is set after it (`:2734`); `flight_t` + rattle hops + bounce step are computed only in `_build_post_shot_sub_steps` (played window mean 1.59 s).
- **A1b:** played only. Sim holds most inputs but never computes it, so this increment depends on shared kinematics.
- **A2:** played is refreshed (defenders 1.14, offense 0.00 from intended spots); sim is stale (defenders 26.40, offense 21.43 grid units at the shot).
- **S1:** score × distance discount, flat 0.8 offensive discount described as box-out, ST as a 0.3 weight inside a 1–6× dice roll; no box-out or contact model. Over-the-back is a post-selection proximity foul check.
- **B1:** crash-destination selection changes 16.4 (played) / 27.5 (sim) picks per game, flips side on 8.8 / 13.9, moves OREB% +1.6 pp / −4.4 pp, and estimates +1.24 / −4.07 second-chance points per game. It closes the arm OREB gap from 5.5 pp to 0.7 pp.

**Can selection read crash arrival positions on both arms, and what comes first?** No. The destinations are an unprincipled random draw, and arrival positions plus the flight window exist only on played. The crash destinations have to be designed first, and arrival on sim needs the shared kinematics function.
