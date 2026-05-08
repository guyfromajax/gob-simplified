# Movement Rate Refactor

> **Status: ✅ Shipped (Phases 0–4d, May 2026).** Full retirement of legacy pace constants complete; AG-driven timing live across HCO/HCT/FCP/fast-break; visual and game-clock synchronized via per-waypoint `game_seconds`. This doc remains as the design record. For runtime behavior, see code in `BackEnd/utils/shared.py` (`calc_ag_segment_seconds`, `calc_cruise_segment_seconds`, `ag_to_grid_per_game_sec`) and `FrontEnd/static/js/phaser/animation/turnAnimation.js` (waypoint `game_seconds` consumption).

## Goal

Replace the current "flat pace constants per movement archetype" model with a two-tier movement system that unifies game-clock timing and visual animation:

- **AG-driven steps** — max-effort situations (drives, fast breaks, defensive close-outs, in-shot motion). Game-time and visual time both derived from the player's AG attribute. Faster players cover the same distance in less game-clock time AND less wall-clock time.
- **Cruise-speed steps** — comfortable-jog situations (HCO bring-up, HCT step 1 BH advance). Game-time and visual time both derived from a cruise rate constant. AG does not affect timing. Optional BH randomness for organic feel.

The two tiers eliminate the current divergence between backend `step_clock_seconds[]` (clock authority) and frontend AG-based `getPlayerDuration()` (visual authority). Once the frontend uses `step_clock_seconds[]` as the duration source-of-truth (Phase 3), they are synchronized by construction.

## Current state — pace constants

[`BackEnd/constants/__init__.py:208-213`](BackEnd/constants/__init__.py#L208-L213):

| Constant | Rate (grid/game-sec) | Original semantic |
|---|---|---|
| `OPEN_FLOOR_GRID_PER_GAME_SECOND` | 20 | OF: bring-up, fallback |
| `CHALLENGED_OPEN_FLOOR_GRID_PER_GAME_SECOND` | 16 | COF: HCT/FCP steps, Fast Break |
| `ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND` | 12 | Drive to basket |
| `COMPRESSED_HCO_GRID_PER_GAME_SECOND` | 10 | HCO non-drive non-shoot |
| `HCO_SHOT_GRID_PER_GAME_SECOND` | 10 | HCO shot with movement |
| `PASS_GRID_SPOTS_PER_GAME_SECOND` | 36 | Ball-in-air pass (out of scope — keep as-is) |

## Call-site map

Every backend site that currently uses a pace constant, classified for the new model. **Pass speed is out of scope** (it's ball physics, not player movement; AG doesn't affect a player's pass speed).

### Cruise-speed sites (move to `calc_cruise_segment_seconds`)

| File:line | Function | Current rate | What it computes | Cruise role |
|---|---|---|---|---|
| `BackEnd/utils/shared.py:287` | `_calc_hco_bringup_overhead_seconds` (BIP→HCO branch) | OF=20 | Max distance across offense from inbound spot to HCO step 0 | All 10 cruise; BH random rate, others baseline |
| `BackEnd/utils/shared.py:304` | `_calc_hco_bringup_overhead_seconds` (DREB→HCO branch) | OF=20 | BH step 0 → step 1 distance | BH random rate |
| `BackEnd/engine/dynamic_hct.py:267` | `_step_1_arrival_time` (HCT step 1 BH advance) | COF=16 | BH inbound spot → (44, y_target) | BH random rate |
| `BackEnd/engine/dynamic_hct.py:438` | HCT step 1 non-BH offense | COF=16 | Other 4 offensive players' partway move | Cruise baseline |
| `BackEnd/engine/dynamic_hct.py:451` | HCT step 1 defenders | COF=16 | 5 defenders move toward zone-Normal centroids | Cruise baseline |
| `BackEnd/engine/dynamic_hct.py:465` | HCT step 1 end-coord computation (parameter) | COF=16 | Used in `_move_at_pace` for step 1 endpoint | Cruise baseline |

### AG-driven sites (move to `calc_ag_segment_seconds`)

| File:line | Function | Current rate | What it computes | AG-driven role |
|---|---|---|---|---|
| `BackEnd/utils/shared.py:376` | HCO step movement, `step_has_shoot=True` | HCO Shot=10 | Player moving into a shot | AG (per-player) |
| `BackEnd/utils/shared.py:378` | HCO step movement, `step_has_shoot=False` | Compressed HCO=10 | Players cutting/screening during HCO | AG (per-player) |
| `BackEnd/utils/shared.py:383` | HCT/FCP step movement (skeleton-driven, post-step-1) | COF=16 | All players in HCT/FCP skeleton steps | AG (per-player) |
| `BackEnd/utils/shared.py:387` | Fallback for any other phase | OF=20 | Default for unclassified phases | AG (per-player) |
| `BackEnd/utils/shared.py:473` | `calc_drive_segment_seconds` | Drive=12 | Drive to basket | AG (per-player, drive multiplier) |
| `BackEnd/engine/dynamic_hct.py:464-467` | HCT step 2 defensive PG converge | COF=16 | Defender converges to engagement spot | AG (defender's AG) |
| `BackEnd/engine/dynamic_hct.py:512-515` | HCT step 3 attack (DEAD BALL branch) | Drive=12 | BH partial dribble before turnover | AG (BH AG, drive multiplier) |
| `BackEnd/engine/dynamic_hct.py:537` | HCT step 3 attack (HCO branch) | Drive=12 | BH dribble all the way to deep key | AG (BH AG, drive multiplier) |
| `BackEnd/engine/phase_resolution.py:956` | Fast break BH cover-ground timing | COF=16 | Fast break runner's path | AG (BH AG) |

### Out of scope (keep as-is)

| File:line | Function | Constant | Why excluded |
|---|---|---|---|
| `BackEnd/utils/shared.py:486` | `calc_pass_segment_seconds` | `PASS_GRID_SPOTS_PER_GAME_SECOND=36` | Ball-in-air; AG doesn't apply |

## New helper spec

Add to `BackEnd/utils/shared.py` (or a new `BackEnd/utils/movement_rates.py` module if we want a clean separation):

```python
def calc_cruise_segment_seconds(start, end, *, role="default"):
    """
    Cruise-speed movement: AG-independent, lineup-independent.
    role="bh"      → BH random rate in [BH_CRUISE_MIN, BH_CRUISE_MAX]
    role="default" → fixed CRUISE_BASELINE
    """

def calc_ag_segment_seconds(start, end, player, *, archetype="default"):
    """
    AG-driven movement: speed scales with player AG.
    archetype:
      "default"     → ag_to_grid_per_game_sec(player.AG)
      "drive"       → ag_to_grid_per_game_sec(player.AG) × DRIVE_MULTIPLIER (slower)
      "shot_motion" → ag_to_grid_per_game_sec(player.AG) × SHOT_MOTION_MULTIPLIER
    """
```

Plus the underlying:

```python
def ag_to_grid_per_game_sec(ag: int) -> float:
    """
    AG attribute → grid units per game second.
    Calibrated so an average-AG player matches today's COF rate (16 grid/sec)
    for the default archetype. Higher AG → higher rate.
    """
```

**Constants to define:**

```python
CRUISE_BASELINE_GRID_PER_GAME_SEC = 16    # all cruise movers (non-BH)
BH_CRUISE_MIN_GRID_PER_GAME_SEC   = 8     # BH random low end
BH_CRUISE_MAX_GRID_PER_GAME_SEC   = 16    # BH random high end
DRIVE_MULTIPLIER                  = 0.75  # drive is 75% of free-running AG rate (preserves current Drive=12 vs COF=16 ratio)
SHOT_MOTION_MULTIPLIER            = 0.625 # shooting motion (preserves current HCO Shot=10 vs COF=16 ratio exactly)
```

**AG curve (resolved, AG attribute is 1-100 with 50 average; rare values above 100):**

```python
def ag_to_grid_per_game_sec(ag: int) -> float:
    """Linear curve calibrated to:
      AG=0   → 10  (slow)
      AG=50  → 16  (average — matches current COF default)
      AG=100 → 22  (fast)
      AG>100 → extends linearly (rare; AG=120 → 24.4)
    Soft cap at 30 grid/game-sec to bound runaway extrapolation.
    """
    rate = 10.0 + (ag / 100.0) * 12.0
    return min(rate, 30.0)
```

## Phased plan

### Phase 0 — This document
**Status:** ✅ shipped. **Output:** the spec you're reading. **Risk:** zero (no code).

### Phase 1 — Introduce helpers, no behavior change
**Status:** ✅ shipped.
- Added `calc_cruise_segment_seconds`, `calc_ag_segment_seconds`, `ag_to_grid_per_game_sec` to `BackEnd/utils/shared.py`.
- Initial implementations routed to legacy pace constants. `ag_to_grid_per_game_sec` was a stub returning 16 (fully implemented in Phase 4a).
- Zero behavior change at any existing call site.

### Phase 2 — Route HCO + HCT bring-up through cruise helper, with BH variation
**Status:** ✅ shipped.
- Updated `_calc_hco_bringup_overhead_seconds` to call `calc_cruise_segment_seconds(role="bh")` for the BH's leg of the max-distance computation, and `role="default"` for other players.
- Update `dynamic_hct.py` step 1 to call `calc_cruise_segment_seconds(role="bh")` for BH advance and `role="default"` for the other 9.
- Implement BH random rate in the helper.
- Visuals still AG-driven (frontend not yet inverted) — so this round is **clock-only**. The user will see clock burn variation but not visual variation in the BH.
- **PR-able alone.**
- **Risk:** low. Only HCO bring-up and HCT step 1 timing change. Easy to A/B by toggling the helper to fall back to the old constant.

### Phase 3 — Frontend authority shift
**Status:** ✅ shipped (split into 3a + 3b for safety).

**3a — HCT visual sync via `waypoint.game_seconds`.**
- Backend `dynamic_hct.py` stamps `game_seconds` on each waypoint (BH cruise time for step 1, step_2_seconds for step 2, step_3_seconds for step 3).
- Frontend `playTurnAnimation` step loop now prefers `curr.game_seconds × clockSecondMs` as authoritative tween duration; falls back to distance-based AG when absent. Existing zero-distance hold floor preserved as fallback.
- HCT BH visibly varies in pace (slow random rate → visibly slower drive); other 9 players move at constant cruise rate. Synced by construction.
- Side-fix landed alongside: BIP `inboundHoldMs` 400ms holds removed; `runPass` duration 500→250ms; redundant BH hold waypoint dropped when `BH_HOLD_GAME_SECONDS = 0`.

**3b — HCO bring-up visual sync via per-player `bringup_per_player_seconds`.**
- Backend `_calc_hco_bringup_per_player_seconds` (split from overhead helper) returns dict of `{pos: game_seconds}`. Single random roll for BH; consistent with `step_clock_seconds[0]` overhead by construction.
- `bringup_per_player_seconds` propagated through `calc_skeleton_step_timing_contract` return value to HCO turn payloads via `phase_resolution.py` (3 sites) and `shot_manager.py` (1 site).
- Frontend `runSetupTween` reads `turnData.bringup_per_player_seconds[scene.playerInfo[playerId].pos]` and uses `× clockSecondMs` as authoritative duration; falls back to AG-based when absent.
- BH visibly varies during HCO bring-up; other offense players at constant cruise rate.

### Phase 4 — Migrate remaining sites, retire constants
**Status:** ✅ shipped (split into 4a → 4d).

**4a — Real AG curve + dual-path helper.**
- `ag_to_grid_per_game_sec` linear curve: `10 + (AG/100)*12`, soft-capped at 30, defaults to 50 on None/junk.
- `calc_ag_segment_seconds` dual-path: `player=None` falls back to legacy constants (preserves Phase 1 behavior); `player=<obj>` uses curve × archetype multiplier.
- Critical invariant verified: AG=50 player produces *identical* timing to legacy at every archetype.

**4b — Migrate AG sites with locally accessible Player.**
- `dynamic_hct.py`: Step 2 PG defender converge → `calc_ag_segment_seconds(default)` with defender's AG. Step 3 BH drives (DEAD BALL + HCO branches) → `bh_drive_rate = ag_to_grid_per_game_sec(BH.AG) * DRIVE_MULTIPLIER`.
- `phase_resolution.py:apply_fast_break_cg_time` → `calc_ag_segment_seconds(default)` with BH.

**4c — `calc_skeleton_step_timing_contract` lineup plumbing.**
- Function gained optional `off_lineup` parameter. Inner loop dual-paths between AG-driven (when provided) and legacy literal-rate fallback (when not).
- 10 callers migrated: `shot_manager.py` (4) + `phase_resolution.py` (6, including HCO turnover/O_FOUL/D_FOUL/shot-clock-recalibration, FCP, HCT).
- One unmigrated caller: `calc_skeleton_time_elapsed` (generic helper, no game/lineup context). Stays on legacy fallback.

**4d — Retire legacy pace constants.**
- `BackEnd/constants/__init__.py`: 5 legacy constants deleted (`OPEN_FLOOR_GRID_PER_GAME_SECOND`, `CHALLENGED_OPEN_FLOOR_GRID_PER_GAME_SECOND`, `ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND`, `COMPRESSED_HCO_GRID_PER_GAME_SECOND`, `HCO_SHOT_GRID_PER_GAME_SECOND`). `PASS_GRID_SPOTS_PER_GAME_SECOND` kept (ball physics).
- Internal legacy fallback paths in `shared.py` use private module-level constants (`_LEGACY_DRIVE_RATE = 12`, `_LEGACY_OF_RATE = 20`, etc.) — readable but no longer part of the public API.
- `dynamic_hct.py` step 1 non-BH/defenders use `CRUISE_BASELINE_GRID_PER_GAME_SEC` (semantic clarity; same value).
- Result: zero direct references to retired constants anywhere in `BackEnd/` or `FrontEnd/`.

## Final state — what's where

| Concern | Source of truth |
|---|---|
| AG curve (1-100 → grid/game-sec) | `BackEnd/utils/shared.py:ag_to_grid_per_game_sec` |
| AG-driven segment timing (drives, fast breaks, HCO/HCT/FCP skeleton steps) | `BackEnd/utils/shared.py:calc_ag_segment_seconds` |
| Cruise-speed segment timing (HCO bring-up, HCT step 1) | `BackEnd/utils/shared.py:calc_cruise_segment_seconds` |
| Per-step game-clock budget | `calc_skeleton_step_timing_contract` (returns `step_clock_seconds[]` + `bringup_per_player_seconds`) |
| Per-player visual tween duration (HCT) | Waypoint `game_seconds` field, populated in `dynamic_hct.py` |
| Per-player visual tween duration (HCO bring-up) | Turn payload `bringup_per_player_seconds`, consumed in `runSetupTween` |
| Cruise-rate constants | `BackEnd/constants/__init__.py:CRUISE_BASELINE_GRID_PER_GAME_SEC`, `BH_CRUISE_MIN/MAX`, `DRIVE_MULTIPLIER`, `SHOT_MOTION_MULTIPLIER` |
| Pass speed | `BackEnd/constants/__init__.py:PASS_GRID_SPOTS_PER_GAME_SECOND` (unchanged; ball physics, not AG) |

## Rollback strategy

Pre-refactor checkpoint: tag current `develop` HEAD as `pre-movement-refactor` after the user pushes the in-flight changes (BH_HOLD=0.0 + Animation_Cleanup.md).

```bash
# After the user's checkpoint commit lands on develop:
git tag pre-movement-refactor <sha>
git push --tags
```

Each Phase 1-4 ships as its own PR, mergeable independently. To roll back any phase:

```bash
git revert <phase-pr-merge-sha>   # safe undo (preserves history)
```

To roll back the entire refactor in an emergency:

```bash
git reset --hard pre-movement-refactor
git push --force-with-lease         # ONLY with explicit user approval
```

## Open questions — resolved

1. **Pass speed treatment** — out of scope. Ball physics, AG doesn't apply. No change.
2. **AG curve calibration** — linear, AG=50 average → 16 grid/game-sec (matches current COF), AG=0 → 10, AG=100 → 22, soft-capped at 30 for rare AG>100 cases. See `ag_to_grid_per_game_sec` above.
3. **Phase 3 feature flag** — none. Direct cutover; revert via PR if needed. Phased PRs already provide revert granularity.
4. **Drive multiplier** — 0.75× free-running (preserves current Drive=12 vs COF=16 ratio).
5. **Shot-motion multiplier** — 0.625× free-running exactly (preserves current HCO Shot=10 vs COF=16 ratio; zero complexity to keep the precise value).

## Cross-references

- `_documentation_master/projects/Animation_Cleanup.md` — broader animation system cleanup queue; this refactor is one of the major projects listed there.
- `_documentation_master/projects/Dynamic_HCT_Turns.md` — HCT spec; HCT step 1 bring-up is one of the cruise-speed sites in this refactor.
- `BackEnd/utils/shared.py` — most pace-constant call sites live here.
- `BackEnd/engine/dynamic_hct.py` — HCT-specific call sites.
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` — frontend-authority-shift target (Phase 3).
- `FrontEnd/static/js/phaser/utils/playerMovementSpeed.js` / `playerMovementDuration.js` — frontend AG-based pacing; needs sync with backend AG-curve in Phase 4.
