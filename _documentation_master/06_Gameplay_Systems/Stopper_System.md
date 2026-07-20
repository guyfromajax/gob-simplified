## Stopper System (Jan 2025; **verified + updated 2026-06-13**)

> **UESS render status (2026-06-13).** The backend truncation logic described here is current for **FCP** (and legacy HCT when `USE_DYNAMIC_HCT = False`). **Live HCT** uses `build_dynamic_hct_animation_steps()` — no skeleton stopper. HCO / FCP stopper outcomes ship unified `animation_steps[]` and are **schema-rendered** by the UESS playback engine.

### Overview

The **Stopper System** is an SS&S (Single Source & Scalable) system that interrupts skeleton animations at strategic points to execute non-shot outcomes (fouls, turnovers, steals, shot-clock violations). Instead of using result-specific skeletons, the stopper system uses standard playcall skeletons and truncates them at a determined "stopper step," then appends a final stopper action step.

**Key Design Principles:**
- **SS&S Architecture**: Uses shared helper functions (`get_ball_handler_from_skeleton()`, `select_foul_player()`, `resolve_non_shooting_foul()`, `resolve_turnover_logic()`) for consistency across turn types
- **Skeleton Reuse**: Uses existing skeleton variants (HCO: successful, mid_play_change, contested, broken; **FCP**: base variant; **legacy HCT** base variant) instead of creating result-specific skeletons
- **Dynamic Interruption**: Determines stop step based on result type (random for fouls, strategic for turnovers/steals)
- **Deep Copy Protection**: Always creates a deep copy of the skeleton before modification to prevent cache mutation

### When Stopper System Activates

The stopper system activates in **HCO and FCP** turns (and **legacy HCT** when `USE_DYNAMIC_HCT = False`) when a non-SHOT result is determined:

**Possible Results:**
- `SHOT` - Normal flow, proceeds to shot resolution (no stopper)
- `O_FOUL` - Offensive foul (stopper activates)
- `D_FOUL` - Defensive foul (stopper activates)
- `DEAD_BALL_TURNOVER` - Dead ball turnover (stopper activates)
- `STEAL` - Steal (stopper activates)
- `SHOT_CLOCK_VIOLATION` - Shot clock expires mid-play (HCO only; stopper activates, mapped to the `dead_ball_turnover` stopper action). Set in `resolve_half_court_offense_logic` when the per-step clock check finds the shot clock hitting 0; the truncation step is precomputed (`game_state["shot_clock_violation_step_index"]`).
- `HCO` - Break through pressure (FCP/HCT only, no stopper - returns full skeleton)

**Result Determination by Turn Type:**

**HCO Turns:**
- Uses `resolve_hco_outcome()` in `phase_resolution.py` (~L2981)
- Sequential resolution system with randomized event checks:
  1. Standard Fouls Check (O_FOUL, D_FOUL)
  2. Steal Attempt Check (STEAL)
  3. Dead Ball Turnover Check (DEAD_BALL_TURNOVER)
  4. Shot Attempt (if no event occurred)
- See `HCO_Turn_Resolution_System.md` for detailed resolution flow

**FCP Turns** (result math owned by `FCP_System.md` — summarized here, do not re-spec):
- Score-based: `offenseScore`/`defenseScore` from the PG-weighted (×3) BH/AG/IQ vs OD/AG/IQ formulas, each ×`randint(1,6)`. See `resolve_full_court_press_logic()` (~L5724).

**HCT Turns (legacy fallback only):** When `USE_DYNAMIC_HCT = False`, HCT used the same score/stopper path as FCP with HCT BSM/DST constants — see `HCT_System.md` § Legacy Fallback. **Live HCT** (`USE_DYNAMIC_HCT = True`, default) does **not** use this math or the stopper system; outcomes emerge from the dynamic loop in `dynamic_hct.py`. HCT schema playback uses `build_dynamic_hct_animation_steps()` instead of skeleton stopper truncation.

**FCP score math (reference):**
- **Success gate** `(offenseScore + BSM) > defenseScore`, where `BSM` = **400** `+ 10×offense fight`, then chemistry adjustments via `pt_opp_modifier` / `pt_efficiency`.
- **Dominant** success `offenseScore - defenseScore > DST`, where `DST` = **600** + discipline/chemistry adjustment:
  - Dominant → weighted choice **`D_FOUL` 30% / `HCO` 40% / `SHOT` 30%**
  - Regular success → `result_type = "HCO"` (break through)
- **Failure** (defense wins) → weighted choice `O_FOUL` 20% / `DEAD_BALL_TURNOVER` 50% / `STEAL` 30%

> Earlier versions listed flat `+500`/`+300` gates — stale. HCT live path: `HCT_System.md` (not this math).

### Stopper Step Selection

The system determines which step to stop at based on result type:

**Fouls (O_FOUL, D_FOUL):**
- Random step between step 1 and second-to-last step
- Example: For a 7-step skeleton (steps 0-6), chooses randomly from steps 1-5
- Rationale: Fouls can organically happen at any point during the play

**Turnovers/Steals (DEAD_BALL_TURNOVER, STEAL):**
- **Blast radius around the middle step** (excluding step 0 and final step). Compute `middle_step = 1 + (len(steps) - 2 - 1) // 2`, then pick randomly from `[max(1, middle−2), min(len(steps)−2, middle+2)]`.
- (Earlier doc described this as the exact middle step; it's now a ±2 random spread around the middle.)
- TODO: Enhance with player attribute analysis (ball handler's BH, defender's ST, IQ) and positioning
- Rationale: Turnovers are more likely during high-pressure situations (passes, drives)

**Shot Clock Violations (SHOT_CLOCK_VIOLATION):**
- Uses the **precomputed** step where the shot clock hits 0 (`game_state["shot_clock_violation_step_index"]`, stamped by the HCO per-step shot-clock check).
- Falls back to `max(1, len(steps) − 2)` if that index is missing or out of range. The index is popped after use so it doesn't leak to the next turn.

### Skeleton Truncation Process

All steps below live inside `apply_stopper_system_to_skeleton()` (~L3502, `phase_resolution.py`).

1. **Deep Copy Creation**:
   - Immediately creates a deep copy of the skeleton after retrieval
   - Prevents in-place modification from mutating the cached skeleton
   - Critical for preventing truncated skeletons in future turns

2. **Stop Step Determination**:
   - Calculates `stop_step_index` based on result type
   - Truncates skeleton to `steps[:stop_step_index + 1]` (includes the stop step)

3. **Ball Handler Identification**:
   - Finds ball handler at the stop step (checks for "handle_ball", "receive", "pass" actions)
   - Falls back to previous step if not found in stop step
   - Determines ball handler position and location for stopper step

4. **Stopper Step Creation**:
   - Creates final stopper step with timestamp = stop_step.timestamp + 300ms
   - Maps result to stopper action: `O_FOUL` → "o_foul", `D_FOUL` → "d_foul", `DEAD_BALL_TURNOVER` / `SHOT_CLOCK_VIOLATION` → "dead_ball_turnover", `STEAL` → "steal"
   - Adds ball handler to stopper step's `pos_actions` (ball remains with them until stopper)
   - Adds stopper event to `events` array

5. **Skeleton Assembly**:
   - Replaces `skeleton["steps"]` with `truncated_steps + [stopper_step]`
   - The schema emitter then turns this truncated skeleton into `animation_steps[]` (legacy path: frontend animates the truncated skeleton directly — see UESS render note at top)

6. **Stop Step Index Storage**:
   - Stores `stop_step_index` in `game_state["steal_stop_step_index"]` for all non-shot results
   - Used later in defender determination to identify the ball handler at the actual stop step
   - Critical for Motion plays where the ball handler changes throughout the motion

### Frontend Animation Handling (legacy fallback path)

> **This section describes the legacy `playTurnAnimation()` renderer.** Post-UESS, HCO/FCP/HCT stopper outcomes carry `animation_steps[]` and render through the schema playback engine (which handles its own per-step positioning/timing). The detail below applies only when a turn falls back to the legacy renderer (no `animation_steps`).

**Step 0 Positioning Requirement:**
- Truncated skeletons still include step 0 (the truncation preserves step 0: `truncated_steps = steps[:stop_step_index + 1]`)
- **Critical**: Frontend must position players at step 0 positions **before** starting the step loop
- Without step 0 positioning, step 1 (first pass) can fire before players reach their step 0 positions, causing slow/fast first pass animations

**Implementation:**
- **Shot Attempts (Full Skeletons)**: Route through `ShotAnimationSystem.executeCompleteShotSequence()` which calls `runSetupTween()` at line 162 before starting the step loop
- **Non-Shooting Results (Truncated Skeletons)**: Route through `playTurnAnimation()` which must also call `runSetupTween()` before the step loop starts
- **Location**: `FrontEnd/static/js/phaser/animation/turnAnimation.js` - `runSetupTween()` function
- **Execution**: `runSetupTween()` moves all players to their step 0 positions using distance-based duration, then the step loop begins at step 1

**Exception: BIP → FCP/HCT Transitions**
- **Skip `runSetupTween()`** when coming from BASELINE_INBOUND (`fromInbound === true`) AND the turn is FCP/HCT (`isFCPHCT === true`)
- **Reason**: BIP already positions players at skeleton step 0 positions (from `offense_setup_positions`), so `runSetupTween()` is redundant
- **Prevents Timing Conflicts**: The inbound pass animation may still be completing when HCT/FCP starts, and redundant positioning can cause conflicts
- **Location**: `FrontEnd/static/js/phaser/animation/turnAnimation.js` - `playTurnAnimation()` (the guard is `if (!fromInbound || !isFCPHCT) { await runSetupTween({...}); }`, ~L4868; `isFCPHCT`/`fromInbound` derived ~L3500/L3520)

**Why This Matters:**
- Truncated skeletons (o foul, d foul, dead ball turnover, steal) use `playTurnAnimation()` which was missing the `runSetupTween()` call
- Shot attempts use `ShotAnimationSystem` which correctly calls `runSetupTween()` before animation
- The fix ensures both paths position players at step 0 before step 1 starts, preventing animation hitches
- **Exception handling** prevents redundant positioning when BIP already handled it, ensuring smooth BIP → FCP/HCT transitions

**Key Files:**
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` - `playTurnAnimation()` and `runSetupTween()` functions
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js` - `executeCompleteShotSequence()` and `runSetupTween()` functions

### Player Role Population

The stopper system uses SS&S helper functions to populate player roles, ensuring consistency across HCO, FCP, and HCT:

**Ball Handler Determination:**
- Uses `get_ball_handler_from_skeleton(skeleton, off_lineup)` - same across all turn types
- Determines ball handler from skeleton steps (from stopper step or last step)
- For HCO: Uses `game_state["steal_stop_step_index"]` to get ball handler at the actual stop step (critical for Motion plays)

**Defender Determination:**
- **For Non-Shot Outcomes (Steals, Turnovers, Fouls)**: Overrides defender assignment to be based on ball handler's position, not shooter's position
  - `assign_roles()` assigns defender based on shooter position (for shot attempts)
  - For steals/turnovers/fouls, we need whoever is guarding the ball handler at the time of the steal
  - **✅ FIX (January 2025)**: Uses `get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=stop_step_index)` to get the ball handler at the **stop step** where the steal/foul/turnover occurs
    - Critical for Motion plays where the ball handler changes throughout the motion
    - The stop step index is stored in `game_state["steal_stop_step_index"]` by `apply_stopper_system_to_skeleton()`
    - Falls back to `roles.get("ball_handler")` if stop step index is not available (backwards compatibility)
  - **Man-to-Man Defense**: Defender matches ball handler position (e.g., if ball handler is SF, defender is defensive SF)
  - **Zone Defense**: Uses actual zone assignment logic (`assign_all_zone_defenders()`) to determine which defender(s) are actually guarding the ball handler
    - Checks `defender_to_offensive_player` mapping to find which defender(s) are assigned to guard the ball handler
    - **Overlapping Zones**: If ball handler is in overlapping zones:
      - If only one defender is guarding the ball handler → uses that defender
      - If two or more defenders are guarding the ball handler → randomly picks one
      - This respects the zone overlap resolution logic (if one defender is assigned to guard a different player in their zone, they won't be considered)
    - Falls back to position match if no defender is assigned (shouldn't happen, but safety fallback)
- **Stopper System Protection**: The stopper system preserves the defender if already set by override logic (prevents overwriting the correct defender)
  - Checks if `roles["defender"]` is already set before recalculating
  - Only recalculates if defender wasn't set by override logic
- **Implementation**: 
  - HCO: Located in `resolve_half_court_offense_logic()` after `assign_roles()` is called
  - FCP/HCT: Defender determined based on ball handler position before roles are built

**Foul Player Selection:**
- Uses `select_foul_player(foul_team_type, ball_handler, off_lineup, def_lineup)` - same across all turn types
- Probabilistic selection: 60% chance it's the matched defender (or ball handler for O_FOUL), 10% chance for each other player

### Event Routing and Handlers

**Event Type Mapping:**
- Maps result from resolution system to `event_type`:
  - `O_FOUL` → `O_FOUL`
  - `D_FOUL` → `D_FOUL` or `FOUL` (FCP/HCT)
  - `DEAD_BALL_TURNOVER` → `TURNOVER` or `"DEAD BALL"` (with space)
  - `STEAL` → `TURNOVER` or `"STEAL"`

**Handler Routing:**
- **Turnovers**: Calls `resolve_turnover_logic(roles, game, turnover_type, from_resolution_system=True)` - shared function
- **Fouls**: Calls `resolve_non_shooting_foul(roles, game)` - shared function
- Both handlers return result with skeleton and animations included

**Animation Generation:**
- **Primary (UESS):** the truncated skeleton is converted to `animation_steps[]` by `build_skeleton_animation_steps()` (HCO/FCP) or `build_dynamic_hct_animation_steps()` (dynamic HCT) and rendered by the schema playback engine.
- **Legacy fallback:** `animator.skeleton_to_animations()` converts the truncated skeleton to `animations[]`; only used when no `animation_steps` are present (HCO Phase 2 drops the legacy `animations[]` field entirely).

### Possession Flip and Transition Handling

**Possession Flips:**
- Handled by shared functions (`resolve_non_shooting_foul()`, `resolve_turnover_logic()`)
- `resolve_non_shooting_foul()` sets `possession_flips: True` for offensive fouls, `False` for defensive fouls
  - **✅ FIX (January 2025):** Does NOT flip possession itself - sets flag only
  - The actual flip happens in `game_manager.py` `simulate_macro_turn()` before `setup_side_inbound()`
  - This prevents double-flipping and ensures consistent behavior (same pattern as dead ball turnovers)
  - **Why:** If `resolve_non_shooting_foul()` flipped possession AND SIP setup also flipped, we'd flip twice (back to original team)
- `resolve_turnover_logic()` sets `possession_flips: True` for all turnovers
  - Same pattern: sets flag only, actual flip happens in `game_manager.py` SIP setup
  - **✅ FIX (January 2025):** Added `from_resolution_system` parameter to respect resolution system's determination
    - When `from_resolution_system=True`, the function respects the `turnover_type` passed (either "STEAL" or "DEAD BALL") and does not randomly convert "DEAD BALL" to "STEAL"
    - This ensures dead ball turnovers from the HCO Resolution System are correctly tracked and displayed
    - Nomenclature conversion: `DEAD_BALL_TURNOVER` (from resolution system) is converted to `"DEAD BALL"` (with space) before calling `resolve_turnover_logic()`

**Transition Handling:**
- Handled by shared functions (sets `offensive_state`, `next_play_type`)
- For steals with Fast Break: Sets `next_play_type = "FAST_BREAK"` to trigger possession flip in `game_manager.py`
- For steals with HCO: Sets `next_play_type = "HCO"` for direct HCO transition
- For dead ball turnovers: Routes to Side Inbound Pass (SIP) → HCO
- For FCP/HCT breaks (`result_type == "HCO"`): Routes to HCO (no stopper, full skeleton returned)
- **SIP Setup Possession Flip:** `game_manager.py` checks `result.get("possession_flips")` and flips possession BEFORE creating the SIP turn payload (in `simulate_macro_turn`, before `setup_side_inbound`; see `Possession_Mgmt_System.md`)
  - This ensures the correct team is on offense for the inbound pass
  - Clears `possession_flips` flag after flipping to prevent frontend double flip
  - **Flow Example (Offensive Foul):**
    1. HCO turn: Bentley-Truman commits offensive foul
    2. `resolve_non_shooting_foul()` sets `possession_flips: True`, returns result with `offense_team_id: "BENTLEY_TRUMAN"` (team on offense DURING the foul)
    3. `game_manager.py` checks `possession_flips=True`, calls `game.switch_possession()` → Lancaster is now offense team
    4. SIP turn created with `offense_team_id: "LANCASTER"` (new offense team after flip)
    5. Next HCO turn will have `offense_team_id: "LANCASTER"` (correct)

### Stat Tracking

**Player Stats:**
- Handled by shared functions:
  - `resolve_non_shooting_foul()`: Records `F` (fouls) for foul player
  - `resolve_turnover_logic()`: Records `TO` (turnovers) for ball handler, `STL` (steals) for defender

**Team Stats:**
- Handled by shared functions (team fouls, scouting data)
- FCP/HCT: Tracks defensive success/failure in scouting data

### Announcement System

**Announcement Data:**
- Result structure includes all necessary IDs:
  - `foul_player_id` - For foul announcements
  - `victim_id`, `victim_name` - For turnover announcements
  - `stealer_id`, `stealer_name` - For steal announcements

**Announcement Timing:**
- Announcements occur after animation completes (frontend handles timing)

### Dead-ball turnover fumble beat (UESS, 2026-06)

For travel / double-dribble class dead-ball turnovers (not shot clock, ten-second, over-and-back, steals, or batted OOB), the backend inserts a **fumble schema step** immediately before the terminal `turn_stop: DEAD_BALL_TURNOVER`:

1. **Stumble** — stationary step, `flourish[fumble]` on the ball handler, `wall_clock_hold_ms` (660 ms), zero game/shot clock burn.
2. **Whistle headline** — `step.end.announcement` with backend 50/50 `"Travel!"` / `"Double Dribble!"` + `whistle-1-lowervol.wav`.

**Announce migration:** The fumble step owns the turnover headline. On inject, the backend stamps:

- `turnover_type` — `"TRAVEL"` or `"DOUBLE_DRIBBLE"` (BE roll, not FE random)
- `suppress_turn_prep_turnover_announce: true` — skips legacy turn-prep turnover announce

**FE guards (both must respect suppress):**

- `turnPreparation.js` → `finalizeTurnAfterAnimation` → `announceGameEvent('TURNOVER', …)`
- `announcements.js` → `announceFromTurnData` (legacy non-router path)

**Universal finalization:** `TurnManager.run_micro_turn()` calls `finalize_dead_ball_fumble_for_turn()` after schema emission and before player-object serialization. This makes the fumble beat apply to any turn type that has `animation_steps[]` ending in `turn_stop: DEAD_BALL_TURNOVER`. Existing emitter-local calls (`skeleton_step_emitter`, `dynamic_hct_step_emitter`, `hct_step_emitter`, `covert_release_step_emitter`; dynamic FCP via `build_dynamic_fcp_animation_steps` → `build_dynamic_hct_animation_steps`) remain valid because the injector is idempotent and will not append a second fumble step.

**Dynamic FCP copy contract:** `build_dynamic_fcp_animation_steps` shallow-copies the turn dict before calling the HCT emitter (FCP alias keys). Fumble inject mutates that **copy**. `propagate_fumble_turn_flags(payload, turn_result)` merges `suppress_turn_prep_turnover_announce` and `turnover_type` back onto the canonical turn so the FE does not double-fire (in-step announce + turn-prep announce).

**Excluded:** `turnover_type == "SHOT_CLOCK"`, `TEN_SECOND`, `OVER_BACK`; steals; batted OOB (`bat_oob`, `rim_runner_bat_oob`).

**Key files:** `BackEnd/engine/dead_ball_fumble.py`, `BackEnd/constants/dead_ball_fumble_constants.py`, `BackEnd/models/turn_manager.py`, `BackEnd/engine/dynamic_fcp_step_emitter.py`, `FrontEnd/static/js/phaser/animation/flourishes.js`, `tests/test_dead_ball_fumble.py`.

### Key Implementation Details

**Deep Copy Protection** (in `apply_stopper_system_to_skeleton`, after the HCO/SHOT early-returns):
```python
# CRITICAL: Always create a deep copy to avoid mutating cached skeleton
skeleton = copy.deepcopy(skeleton)
```
- Prevents truncated skeletons from affecting future turns
- Must be done immediately after skeleton retrieval, before any modifications

**Skeleton Variants:**
- **HCO**: Stopper system works consistently across all skeleton variants (successful, mid_play_change, contested, broken)
- **FCP/HCT**: Uses "base" variant skeleton (has step 0 with press/trap break positions)
- Simply truncates the skeleton at the determined step, regardless of variant

**Ball Handling for Steals:**
- If stopper step has a pass: Ball attaches to receiver, then defender steals it
- If no pass: Ball remains with previous ball handler, then defender steals it
- TODO: Implement pass interception logic for future enhancement

**HCO Result Handling:**
- For FCP/HCT turns, if `result_type == "HCO"`, the stopper system returns the full skeleton (no truncation)
- This allows the offense to break through pressure and proceed to normal HCO play

### Future Enhancements

**1. Strategic Step Selection for Turnovers/Steals**

**Current State:**
- Turnovers (`DEAD_BALL_TURNOVER`) and steals (`STEAL`) use a blast radius around the middle step (middle ±2, random) — a rough placeholder, not yet attribute-driven
- Fouls use random step selection (which is appropriate)
- Shot-clock violations use the precomputed expiry step (not a placeholder)

**Enhancement Needed:**
- Implement strategic step selection based on:
  - Player attributes (ball handler's `BH` vs defender's `ST`)
  - Player dynamics at each step
  - Defensive matchup effectiveness
  - Game situation (score, time, quarter)

**Location:** `BackEnd/engine/phase_resolution.py` — turnover/steal stop-step branch inside `apply_stopper_system_to_skeleton()` (~L3546)

**Rationale:** Turnovers are more likely during high-pressure situations (passes, drives), so the stop step should reflect the most likely point of failure based on player attributes and game context.

**2. Defensive Player Selection for Steals**

**Current State:**
- ✅ **COMPLETE** (January 2025): Defender assignment for steals is now implemented
  - For non-shot outcomes (steals, turnovers, fouls), defender is determined based on ball handler's position, not shooter's position
  - **Man-to-Man**: Defender matches ball handler position
  - **Zone Defense**: Uses actual zone assignment logic to find which defender(s) are guarding the ball handler
  - Handles overlapping zones correctly (uses defender actually assigned to guard ball handler)
  - Stopper system preserves the correctly set defender (prevents overwriting)
  - See "Defender Determination" section above for full implementation details

**Future Enhancement:**
- The stopper step itself doesn't specify which defensive player makes the steal in the skeleton's `pos_actions`
- Currently, the defender is determined in role assignment based on ball handler position
- **Enhancement Needed:** Add the defensive player to the stopper step's `pos_actions` with "steal" action based on:
  - Defensive positioning at the stop step
  - Player attributes (defender's `ST` vs ball handler's `BH`)
  - Matchup analysis
  - Proximity to ball handler

**Location:** `BackEnd/engine/phase_resolution.py` — stopper-step creation inside `apply_stopper_system_to_skeleton()` (~L3502+)

**Pass Interception Logic:**
- Currently treats all steals as steals from the ball handler
- TODO: For steps with passes, implement pass interception logic:
  - Ball attaches to receiver
  - Defender intercepts the pass (different animation than steal from handler)

### Key Files

_(Line numbers approximate, verified 2026-06-13; `phase_resolution.py` shifts frequently.)_

- `BackEnd/engine/phase_resolution.py`
  - `apply_stopper_system_to_skeleton()` - Core stopper system function (~L3502)
  - `resolve_half_court_offense_logic()` - HCO stopper system implementation (~L4479)
  - `resolve_full_court_press_logic()` - FCP stopper system implementation (~L5724)
  - `resolve_half_court_trap_logic()` - HCT stopper system implementation (~L7155)
  - `resolve_hco_outcome()` - HCO result determination (~L2981)
  - `resolve_turnover_logic()` - Shared turnover handler (~L2447)
  - `resolve_non_shooting_foul()` - Shared foul handler (~L562)
  - `get_ball_handler_from_skeleton()` - SS&S helper (~L314)
  - `select_foul_player()` - SS&S helper (~L479)
- `BackEnd/engine/skeleton_step_emitter.py` (**UESS schema path**)
  - `build_skeleton_animation_steps()` - Converts the (truncated) HCO/FCP skeleton to `animation_steps[]`
  - `_is_fcp_stopper_action_step()` / `_resolve_fcp_stopper_gate_ids()` - Stopper-step gating for FCP schema playback
- `BackEnd/engine/dynamic_hct_step_emitter.py`
  - `build_dynamic_hct_animation_steps()` - Schema steps for dynamic HCT
- `BackEnd/engine/dynamic_fcp_step_emitter.py`
  - `build_dynamic_fcp_animation_steps()` - Dynamic FCP wrapper; merges fumble announce flags back to canonical turn
- `BackEnd/engine/dead_ball_fumble.py`
  - `inject_dead_ball_fumble_before_turn_stop()` - Fumble beat + announce migration flags
  - `propagate_fumble_turn_flags()` - Copy suppress / turnover_type from emitter working copy
- `BackEnd/models/turn_manager.py`
  - `_emit_hco_animation_steps()` - Single HCO injection point (calls `build_skeleton_animation_steps`); also stamps `current_turn="HCO"` so stopper outcomes pass the FE schema-playback gate
  - FCP/HCT schema emission wiring in `run_micro_turn`
- `BackEnd/models/animator.py`
  - `skeleton_to_animations()` - **Legacy fallback** - converts truncated skeleton to `animations[]`
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` (**legacy fallback renderer**)
  - `playTurnAnimation()` - Handles truncated skeleton animation
  - `runSetupTween()` - Positions players at step 0 before animation
