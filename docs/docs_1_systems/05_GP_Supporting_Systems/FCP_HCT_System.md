## FCP/HCT System ✅ **COMPLETE** (January 2025)

**Base Constants**
1. FCP Success Threshold: `offenseScore + 500 > defenseScore`
2. HCT Success Threshold: `offenseScore + 300 > defenseScore` (lower than FCP)
3. Dominant Success Threshold: `offenseScore - defenseScore > 1000` (for both FCP and HCT)
4. Success Result Weights: `["D_FOUL", "HCO", "SHOT"]` with weights `[0.3, 0.5, 0.2]`
5. Failure Result Weights: `["O_FOUL", "DEAD_BALL_TURNOVER", "STEAL"]` with weights `[0.2, 0.5, 0.3]`
6. Turnover Type Weights: `["TRAVEL", "DOUBLE DRIBBLE", "BAD PASS"]` with weights `[0.6, 0.3, 0.1]`

**FCP/HCT Resolution Flow (10 Steps)**
1. Apply Energy Decay
   - Apply energy decay to all active players (offense and defense) via `apply_energy_decay()`

2. Track Defensive Attempt Stat
   - Increment `def_scouting["defense"]["FCP"]["used"]` or `def_scouting["defense"]["HCT"]["used"]`

3. Calculate Offense Score
   - For each offensive player (PG, SG, SF): Calculate `(BH * 0.6 + AG * 0.2 + IQ * 0.2)`
   - PG gets 3x weight, SG/SF get 1x weight
   - Sum all player contributions, then multiply total by `random.randint(1, 6)`
   - **Note**: Scores are attribute-based (not purely random), with a random multiplier applied

4. Calculate Defense Score
   - For each defensive player (PG, SG, SF): Calculate `(OD * 0.4 + AG * 0.4 + IQ * 0.2)`
   - PG gets 3x weight, SG/SF get 1x weight
   - Sum all player contributions, then multiply total by `random.randint(1, 6)`
   - **Note**: Scores are attribute-based (not purely random), with a random multiplier applied

5. Determine Outcome Type
   - BSM (Base Success Modifier) = 500 for FCP, 300 for HCT
      - BSM += random.randint(1, offense team chemistry) * offense team fight if offense team fight > 0, else += random.randint(1, offense team chemistry)
      - BSM -= random.randint(1, defenese team chemistry) * defense team discipline if defense team discipline > 0 else -= random.randint(1, defense team chemistry)
    - DST (Defense Safety Threshold) = 600 for FCP, 800 for HCT
      - DST += random.randint(1, defense team chemistry) * defense team discipline if defense team discipline > 0 else += random.randint(1, defense team chemistry)
   - **FCP Success**: `if (offenseScore + BSM) > defenseScore`
     - If `offenseScore - defenseScore > DST`: Weighted random `["D_FOUL", "HCO", "SHOT"]` with weights `[0.3, 0.5, 0.2]`
     - Otherwise: `"HCO"` (press break)
   - **FCP Failure**: Otherwise → Weighted random `["O_FOUL", "DEAD_BALL_TURNOVER", "STEAL"]` with weights `[0.2, 0.5, 0.3]`
   - **HCT Success**: `if (offenseScore + BSM) > defenseScore` (lower threshold than FCP)
     - If `offenseScore - defenseScore > DST`: Weighted random `["D_FOUL", "HCO", "SHOT"]` with weights `[0.3, 0.5, 0.2]`
     - Otherwise: `"HCO"` (trap break)
   - **HCT Failure**: Otherwise → Weighted random `["O_FOUL", "DEAD_BALL_TURNOVER", "STEAL"]` with weights `[0.2, 0.5, 0.3]`

6. Handle SHOT Result (if applicable)
   - Build shot roles: Passer (PG), Shooter (random PF or C), Defender (defensive PG)
   - Call `shot_manager.resolve_shot()` for full shot resolution
   - If MISS with shooting foul: Route to FREE_THROW
   - If MISS without foul: Route to HCO (track defensive success)
   - If MAKE: Route to BASELINE_INBOUND (pressure may apply again)
   - Get "shot" variant skeleton and generate animations
   - Track FCP/HCT stats for all players

7. Handle Non-SHOT Results
   - Get "base" variant skeleton (has step 0 with press/trap break positions)
   - Apply stopper system (truncate and add stopper step if not HCO)
   - Determine ball handler from skeleton using `get_ball_handler_from_skeleton()`
   - Determine defender by position-matching to ball handler

8. Process Specific Result Types
   - **O_FOUL**: Select foul player using `select_foul_player()` (60% ball handler, 10% each other player), route to SIDE_INBOUND → HCO
   - **D_FOUL**: 
     - Select foul player using `select_foul_player()` (60% defender matched to ball handler's position, 10% each other defender)
     - In Bonus (5-9 fouls): Route to FREE_THROW (1 & 1)
     - In Double Bonus (10+ fouls): Route to FREE_THROW (2 shots)
     - Not in Bonus (<5 fouls): Route to SIDE_INBOUND → HCO
   - **DEAD_BALL_TURNOVER**: Random turnover type (TRAVEL/DOUBLE DRIBBLE/BAD PASS), route to SIDE_INBOUND → HCO
   - **STEAL**: Check fast break chance, route to FAST_BREAK or HCO
   - **HCO**: Route to HCO (no possession change)

9. Generate Animations
   - Convert skeleton to animations via `animator.skeleton_to_animations()`
   - Include player movements, ball movements, and defender positioning

10. Track Stats and Set Next Play
    - Record FCP/HCT player stats for all players in active lineup
    - Track team-level defensive success (if applicable)
    - Set `next_play_type` and `offensive_state` for transition system

**Stopper System**

The stopper system truncates FCP/HCT "base" variant skeletons at strategic points to execute non-shot outcomes (fouls, turnovers, steals). It applies to all non-SHOT results except HCO (which uses the full skeleton).

**Stopper System Flow (5 Steps)**

1. **Determine if Stopper System Applies**
   - Applies to: `O_FOUL`, `D_FOUL`, `DEAD_BALL_TURNOVER`, `STEAL`
   - Does NOT apply to: `SHOT` (uses full "shot" variant skeleton), `HCO` (uses full "base" variant skeleton)

2. **Select Stop Step Index**
   - **Fouls (O_FOUL/D_FOUL)**: Random step between step 1 and second-to-last step
     - Excludes step 0 (initial positions) and final step
     - Example: 7-step skeleton → randomly selects from steps 1-5
   - **Steals/Turnovers (STEAL/DEAD_BALL_TURNOVER)**: Middle step blast radius
     - Calculates middle of steps 1 through second-to-last
     - Excludes step 0 and final step
     - Choose a step randomly ±2 from the middle step, clamped to valid range
     - Example: 8-step skeleton (0-7) → excludes step 0 and step 7 → available steps 1-6 → middle step is 3 → blast radius is steps 1-5 → randomly selects from steps 1-5

3. **Truncate Skeleton**
   - Deep copy skeleton to avoid mutating cached original
   - Truncate to: `steps[:stop_step_index + 1]` (includes the stop step)
   - Preserves step 0 (press/trap break positions)

4. **Find Ball Handler at Stop Step**
   - Check stop step for ball possession actions: `"handle_ball"`, `"receive"`, `"pass"`
   - If not found, check previous step
   - Extract ball handler position, location, and coordinates

5. **Create Stopper Step**
   - Timestamp: `stop_step.timestamp + 300ms`
   - Action mapping: `O_FOUL` → "o_foul", `D_FOUL` → "d_foul", `DEAD_BALL_TURNOVER` → "dead_ball_turnover", `STEAL` → "steal"
   - Add ball handler to stopper step's `pos_actions` (ball remains with them)
   - Add stopper event to `events` array
   - Replace skeleton: `truncated_steps + [stopper_step]`

**Integration with FCP/HCT:**
- Uses "base" variant skeleton (has step 0 with press/trap break positions)
- Ball handler determined from stop step (where event occurs)
- Defender determined by position-matching to ball handler
- Frontend animates truncated skeleton normally (no special handling needed)

**Long Form Documentation**

### Overview

The **Full Court Press (FCP)** and **Half Court Trap (HCT)** system handles defensive pressure situations that occur after made shots. Both systems use skeleton-based animations to simulate press break sequences and can result in various outcomes: turnovers, fouls, press breaks, or shot attempts.

**Key Functions:**
- `resolve_full_court_press_logic()` - Handles FCP outcomes in `BackEnd/engine/phase_resolution.py`
- `resolve_half_court_trap_logic()` - Handles HCT outcomes in `BackEnd/engine/phase_resolution.py`
- `get_ball_handler_from_skeleton()` - Determines ball handler dynamically from skeleton steps
- `determine_defensive_pressure_type()` - Determines if FCP/HCT should be applied (in `BackEnd/models/turn_manager.py`)

### When FCP/HCT Activates

**Trigger Conditions:**
- After made shots when defense applies full court press or half court trap
- Set via `offensive_state = "FCP"` or `offensive_state = "HCT"` in `game_state`
- Determined by `turn_manager.determine_defensive_pressure_type()` in `shot_manager.py`

**State Flow:**
1. Made shot → Sets `offensive_state` based on defensive pressure type
2. BASELINE_INBOUND turn generated (if applicable)
3. Next API call routes to FCP/HCT handler based on `offensive_state`
4. Handler generates outcome turn (FOUL/TURNOVER/HCO/SHOT)

### Possible Outcomes

Both FCP and HCT can result in:

1. **Offensive Foul (O_FOUL)**
   - Possession change
   - Routes to: Side Inbound Pass → HCO
   - Foul player: Determined dynamically from ball handler (60% ball handler, 10% each other player)

2. **Defensive Foul (D_FOUL)**
   - **In Bonus (5-9 fouls)**: Routes to FREE_THROW (1 & 1)
   - **In Double Bonus (10+ fouls)**: Routes to FREE_THROW (2 shots)
   - **Not in Bonus (<5 fouls)**: Routes to Side Inbound Pass → HCO
   - Foul player: Determined dynamically from defender guarding ball handler

3. **Steal (STEAL)**
   - Possession change
   - Routes to: HCO or FAST_BREAK (based on fast break chance)
   - Stealer: Defender guarding ball handler (position-matched)
   - Victim: Ball handler (determined from skeleton)

4. **Dead Ball Turnover (DEAD_BALL_TURNOVER)**
   - Possession change
   - Routes to: Side Inbound Pass → HCO
   - Turnover player: Ball handler (determined from skeleton)
   - Turnover type: Random choice from `["TRAVEL", "DOUBLE DRIBBLE", "BAD PASS"]` with weights `[0.6, 0.3, 0.1]`

5. **Press/Trap Break (HCO)**
   - Successful press break
   - Routes to: HCO (half court offense)
   - No possession change

6. **Press/Trap Break Shot (SHOT)**
   - Shot attempt during press break
   - **Full shot resolution**: Uses `shot_manager.resolve_shot()` to determine MAKE/MISS, fouls, etc.
   - **Shot roles**: Passer (PG), Shooter (random PF or C), Defender (defensive PG)
   - **After shot resolution**:
     - If MISS with shooting foul: Routes to FREE_THROW
     - If MISS without foul: Routes to HCO (defensive success tracked)
     - If MAKE: Routes to BASELINE_INBOUND (pressure may apply again)
   - Uses FCP/HCT-specific "shot" variant skeleton for animation

### Dynamic Player Assignment System ✅ **NEW** (January 2025)

**Previous Behavior:**
- Ball handler was hardcoded to PG (or first player in lineup)
- Defender was hardcoded to defensive PG
- All events (fouls, steals, turnovers) assigned to these hardcoded players

**Current Behavior:**
- **Ball Handler**: Determined dynamically from skeleton steps
  - Checks skeleton steps for actions: `"handle_ball"`, `"receive"`, `"shoot"`
  - Defaults to last step (where event occurs)
  - Falls back to PG if no ball handler found in skeleton
- **Defender**: Position-matched to ball handler
  - Uses same position as ball handler (e.g., if ball handler is SG, defender is defensive SG)
  - Falls back to defensive PG if position not found
- **All Events**: Use dynamic players
  - Offensive foul: Uses dynamic ball handler
  - Defensive foul: Uses dynamic ball handler and defender
  - Steal: Uses dynamic ball handler (victim) and defender (stealer)
  - Dead ball turnover: Uses dynamic ball handler

### Per-Step Ball Handler Tracking for Defender Positioning ✅ **NEW (March 2025)**

- **FCP**: Defenders still match their assigned offensive player, but at each step, if their assignment is the current ball handler, they switch to `guard_ball`; ball handler is determined **per timestamp** (not just step 0).
- **HCT**: Per-step ball handler detection drives trap logic:
  - Defensive PG tracks the **current** ball handler each step (not the initial handler).
  - Other defenders track their assignments with tighter offsets and respect half-court boundaries.
- **Why it matters**: Prevents PG/SF "swap" behavior when the ball changes hands mid-sequence; defenders always respond to the live ball handler.

**Implementation:**

```python
def get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=None):
    """
    Determine the ball handler from skeleton steps.
    
    Args:
        skeleton: Skeleton dict with "steps" key
        off_lineup: Dictionary of offensive players by position
        step_index: Optional step index to check (defaults to last step if None)
    
    Returns:
        Player object who has the ball, or PG (or first player) as fallback
    """
    # Check skeleton steps for ball possession actions
    # Actions that indicate ball possession: "handle_ball", "receive", "shoot"
    # Defaults to last step (where event likely occurs)
    # Falls back to PG if no ball handler found
```

**Benefits:**
- ✅ More accurate player assignments based on actual game flow
- ✅ Removes hardcoded PG assumption
- ✅ Better stat tracking (correct players get credited)
- ✅ More realistic game simulation

### FCP/HCT Stat Tracking ✅ **NEW** (January 2025)

**Player-Level Stats:**

**Offensive Stats (FCP_A, FCP_S / HCT_A, HCT_S):**
- **FCP_A / HCT_A**: Attempts - Incremented for **ALL players in active offensive lineup**
- **FCP_S / HCT_S**: Success - Incremented for **ALL players in active offensive lineup** when:
  - `MAKE` (made shot)
  - `HCO` (press/trap break - successfully broke through)
  - `FOUL` where `foul_team == "DEFENSE"` (defensive foul)
- **Note**: There are no explicit failure stats (FCP_F/HCT_F). Failure is implicit (if success isn't incremented, it's a failure).

**Defensive Stats (FCP_A_D, FCP_S_D / HCT_A_D, HCT_S_D):**
- **FCP_A_D / HCT_A_D**: Defensive Attempts - Incremented for **ALL players in active defensive lineup**
- **FCP_S_D / HCT_S_D**: Defensive Success - Incremented for **ALL players in active defensive lineup** when:
  - `MISS` (missed shot)
  - `DEAD_BALL_TURNOVER` (dead ball turnover)
  - `STEAL` (steal)
  - `FOUL` where `foul_team == "OFFENSE"` (offensive foul)
- **Note**: There are no explicit failure stats (FCP_F_D/HCT_F_D). Failure is implicit (if success isn't incremented, it's a failure).

**Stat Initialization:**
- All FCP/HCT stats initialized to `0` at game start
- Initialized in:
  - `Player._init_stats()` - For all stat levels (game, season, career)
  - `_init_game_stats_dict()` in `BackEnd/main.py` - For single game mode
  - Tournament and Franchise mode initialization functions

**Stat Tracking Timing:**
- **SHOT Results**: Tracked after shot resolution (MAKE/MISS) in `resolve_full_court_press_logic()` and `resolve_half_court_trap_logic()`
- **Non-SHOT Results**: Tracked after result type determination (O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER, HCO)
- Stats are recorded via `_record_fcp_stats()` and `_record_hct_stats()` helper functions

**Team-Level Stats (Scouting Data):**

**Defensive Success Tracking:**
- **`def_scouting["defense"]["FCP"]["used"]`**: Incremented each time defense applies Full Court Press
- **`def_scouting["defense"]["FCP"]["success"]`**: Incremented when FCP result_type is:
  - `MISS` (missed shot during press break)
  - `O_FOUL` (offensive foul)
  - `DEAD_BALL_TURNOVER` (dead ball turnover)
  - `STEAL` (steal)
- **`def_scouting["defense"]["HCT"]["used"]`**: Incremented each time defense applies Half Court Trap
- **`def_scouting["defense"]["HCT"]["success"]`**: Incremented when HCT result_type is:
  - `MISS` (missed shot during trap break)
  - `O_FOUL` (offensive foul)
  - `DEAD_BALL_TURNOVER` (dead ball turnover)
  - `STEAL` (steal)

**Note:** Team-level offensive success/failure can be derived from defensive tracking:
- `offensive_successes = total_attempts - defensive_successes`
- `offensive_failures = defensive_successes`
- `defensive_failures = total_attempts - defensive_successes`

**Special Handling:**
- **HCO (Press/Trap Break)**: Counts as offensive success at player level (FCP_S/HCT_S) and defensive failure at player level (implicit - FCP_S_D/HCT_S_D not incremented), but is NOT tracked as defensive success at team level (correct - defense failed to stop the break)
- **MAKE**: Counts as offensive success at player level but NOT as defensive success at team level (correct - offense scored)
- **D_FOUL**: Counts as defensive failure at player level (implicit - FCP_S_D/HCT_S_D not incremented) but NOT as defensive success at team level (correct - defense fouled)

### Skeleton System ✅ **UPDATED** (January 2025)

**Skeleton Sources:**
- FCP skeletons: MongoDB `fcp_skeletons` collection
- HCT skeletons: MongoDB `hct_skeletons` collection
- **Variant Structure**: Two variants per skeleton type:
  - `"base"` - Standard press/trap break skeleton (used for all non-shot results: O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER, HCO)
  - `"shot"` - Shot attempt skeleton (used for SHOT results)
- **Critical**: FCP/HCT "base" variants have step 0 with press/trap break positions (unlike HCO skeletons which don't have step 0)
- **Skeleton Selection**: `get_fcp_skeleton(result_type, game)` or `get_hct_skeleton(result_type, game)` maps result types to variants
  - All non-shot result types map to `"base"` variant
  - SHOT results map to `"shot"` variant
- **Stopper System Integration**: FCP/HCT non-shot results use "base" variant skeletons with stopper system applied (truncation + stopper step)

**Skeleton Structure:**
- Each skeleton contains `steps` array
- Each step has `pos_actions` dict mapping positions to actions
- Actions include: `"handle_ball"`, `"receive"`, `"pass"`, `"shoot"`, `"screen"`, etc.
- Ball handler determined by checking for ball possession actions in steps

**Animation Generation:**
- Skeletons converted to animations via `animator.skeleton_to_animations()`
- Animations include player movements, ball movements, and defender positioning
- Frontend uses skeleton data to animate press break sequences

### Key Files

- `BackEnd/engine/phase_resolution.py`
  - `resolve_full_court_press_logic()` - FCP outcome resolution
  - `resolve_half_court_trap_logic()` - HCT outcome resolution
  - `get_ball_handler_from_skeleton()` - Dynamic ball handler determination
  - `select_foul_player()` - Probabilistic foul player selection
  - `_record_fcp_stats()` - FCP stat tracking helper
  - `_record_hct_stats()` - HCT stat tracking helper
  - `apply_energy_decay()` - Energy decay for active players
- `BackEnd/models/turn_manager.py`
  - `determine_defensive_pressure_type()` - Determines if FCP/HCT should be applied
- `BackEnd/playcall_skeletons/fcp_skeletons.py` - FCP skeleton definitions (legacy fallback)
- `BackEnd/playcall_skeletons/hct_skeletons.py` - HCT skeleton definitions (legacy fallback)
- `BackEnd/models/animator.py` - Skeleton to animation conversion
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js` - FCP/HCT detection and state tracking

### Future Enhancements

- **More Nuanced Defender Assignment**: Currently uses position matching. Future: Determine defender based on actual defensive assignments (zone/man coverage)
- **Enhanced Ball Handler Detection**: Improve detection logic for edge cases where ball handler isn't clear from skeleton
- **Skeleton Variants**: Add more skeleton variants for different press break scenarios

