## FCP/HCT System ✅ **COMPLETE** (January 2025; re-verified June 2026)

**Base Constants**
1. FCP Success Threshold: `offenseScore + BSM (defined below) > defenseScore`
2. HCT Success Threshold: `offenseScore + BSM (defined below) > defenseScore` (lower than FCP)
3. Dominant Success Threshold: `offenseScore - defenseScore > DST` — DST = **600 (FCP) / 800 (HCT)** plus discipline-based chemistry adjustment (see step 5). (Not a flat 1000.)
4. Success Result Weights: `["D_FOUL", "HCO", "SHOT"]` with weights `[0.3, 0.4, 0.3]`
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

5. Determine Outcome Type #
   - Calculate BSM (Base Success Modifier)
      - Starting FCP BSM = 400 + (10 * offense team's fight attribute value)
      - Starting HCT BSM = 200 + (10 * offense team's fight attribute value)
      - BSM += random.randint(1, offense team chemistry) * offense pt_opp_modifier if offense team pt_opp_modifier > 0, else += random.randint(1, offense team chemistry)
      - BSM -= random.randint(1, defense team chemistry) * defense team pt_efficiency if defense team pt_efficiency > 0 else -= random.randint(1, defense team chemistry)
    - DST (Defense Safety Threshold) = 600 for FCP, 800 for HCT
      - DST += random.randint(1, defense team chemistry) * defense team discipline if defense team discipline > 0 else += random.randint(1, defense team chemistry)
   - **FCP Success**: `if (offenseScore + BSM) > defenseScore`
     - If `offenseScore - defenseScore > DST`: Weighted random `["D_FOUL", "HCO", "SHOT"]` with weights `[0.3, 0.4, 0.3]`
     - Otherwise: `"HCO"` (press break)
   - **FCP Failure**: Otherwise → Weighted random `["O_FOUL", "DEAD_BALL_TURNOVER", "STEAL"]` with weights `[0.2, 0.5, 0.3]`
   - **HCT Success**: `if (offenseScore + BSM) > defenseScore` (lower threshold than FCP)
     - If `offenseScore - defenseScore > DST`: Weighted random `["D_FOUL", "HCO", "SHOT"]` with weights `[0.3, 0.4, 0.3]`
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

**Clock start and inbound pass**
- **Game and shot clocks** start only after the inbound receiver has the ball (same behavior as BIP→HCO and SIP).
- The **inbound pass** runs during the BASELINE_INBOUND (BIP) step; the frontend runs the full inbound sequence (positions + pass) for FCP/HCT as well as HCO.
- When the FCP/HCT turn directly follows a BIP, the backend now skips all leading inbound-equivalent skeleton steps (including both `inbound_left` and `inbound_right`), then starts at the first post-inbound step. This prevents double inbound-pass sequences when versions place inbound staging/pass in step 0 or step 1.
- Fallback behavior is preserved: if no dynamic match is found, legacy start index logic still applies so turns continue safely.
- Implemented in: `phase_resolution.py` (post-skeleton start-index selection in both FCP/HCT shot and non-shot paths), `turnAnimation.js` `runInboundSetup()` (inbound pass runs for FCP/HCT; no early return).

**Canonical skeleton contract (authoring)**
- BIP is the single owner of inbound-pass animation.
- FCP/HCT skeletons should encode inbound as **step 0 only** (`SF pass` -> `PG receive` at inbound spot), and step 1+ should be post-receive press/trap flow.
- Runtime now tolerates mixed legacy versions (step 0 hold + step 1 pass), but new versions should follow the canonical step-0 inbound format for consistency.

**Long Form Documentation**

### Overview

The **Full Court Press (FCP)** and **Half Court Trap (HCT)** system handles defensive pressure situations that occur after made shots. Both systems use skeleton-based animations to simulate press break sequences and can result in various outcomes: turnovers, fouls, press breaks, or shot attempts.

**Key Functions:**
- `resolve_full_court_press_logic()` - Handles FCP outcomes in `BackEnd/engine/phase_resolution.py`
- `resolve_half_court_trap_logic()` - Handles HCT outcomes in `BackEnd/engine/phase_resolution.py`
- `get_ball_handler_from_skeleton()` - Determines ball handler dynamically from skeleton steps
- `determine_defensive_pressure_type()` - Determines if FCP/HCT should be applied (in `BackEnd/models/turn_manager.py`)

### FCP Starting Alignment (BIP-end positions)

Set during the BASELINE_INBOUND turn that precedes an FCP turn (see `TurnManager._build_fcp_setup_positions` in `turn_manager.py`). Players are placed in their press-break formation at the end of BIP; the FCP turn then animates from these BIP-end coords toward the first post-inbound skeleton step (players who can't reach in step T freeze at their interrupted coord per UESS §9.5 — no teleport).

All coords below are in HOME orientation (home offense). For away offense, x is flipped via `getAwayTeamCoords`. Defenders use their own randomized ranges (no longer derived from offensive positions via `get_defender_coords`); dynamic per-step shadowing inside the FCP turn is unchanged.

**Offense ranges** (`FCP_OFFENSE_SETUP_RANGES` in `constants/__init__.py`):

| Pos | x range | y range | Notes |
|---|---|---|---|
| SF | 3 (fixed) | chemistry-aware | Inbounder. SF y mirrors HCO BIP's dynamic logic: chem > 15 → (25,35) if PG_y > 24 else (15,25); chem ≤ 15 → (15,35) |
| PG | random.randint(12, 18) | random.randint(15, 23) | Lower inbound receive option |
| SG | random.randint(12, 18) | random.randint(27, 35) | Upper inbound receive option |
| PF | random.randint(45, 55) | random.randint(20, 30) | Mid-court outlet |
| C  | random.randint(60, 70) | random.randint(20, 30) | Front-court anchor |

**Defense ranges** (`FCP_DEFENSE_SETUP_RANGES`):

| Pos | x range | y range |
|---|---|---|
| PG | random.randint(20, 25) | random.randint(23, 27) |
| SG | random.randint(26, 31) | random.randint(30, 36) |
| SF | random.randint(26, 31) | random.randint(14, 20) |
| PF | random.randint(50, 55) | random.randint(23, 27) |
| C  | random.randint(71, 76) | random.randint(23, 27) |

**Collision rule** (`FCP_SETUP_COLLISION_OFFSET_GRID = 2`):

- Trigger: any two of the 10 players (offense + defense) land on the exact same `(x, y)`.
- Resolution: pick one of the two at random; offset by exactly 2 grid spots in a random direction (random angle ∈ [0, 2π)). The moved player's new location is 2 grid spots from his original AND 2 grid spots from the other player.
- Re-checked iteratively (up to 10 rounds) in case the move creates a new collision.
- No clamp — the moved player may end up outside his declared range.

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
- FCP skeletons: MongoDB `fcp_skeletons` collection (stored in `gob-staging` database)
- HCT skeletons: MongoDB `hct_skeletons` collection (stored in `gob-staging` database)
- **Storage**: All skeletons saved to `gob-staging` for testing before production migration

**Variant Structure:**
- Two variants per skeleton type:
  - `"base"` - Standard press/trap break skeleton (used for all non-shot results: O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER, HCO)
  - `"shot"` - Shot attempt skeleton (used for SHOT results)
- **Critical**: FCP/HCT "base" variants have step 0 with press/trap break positions (unlike HCO skeletons which don't have step 0)
- **Skeleton Selection**: `get_fcp_skeleton(result_type, game)` or `get_hct_skeleton(result_type, game)` maps result types to variants
  - All non-shot result types map to `"base"` variant
  - SHOT results map to `"shot"` variant
- **Stopper System Integration**: FCP/HCT non-shot results use "base" variant skeletons with stopper system applied (truncation + stopper step)

**Version System:**
- **Structure**: Matches offensive plays structure - each variant supports multiple versions (v1, v2, v3, etc.)
- **Version Selection**: Engine randomly selects from available non-empty versions for each variant
- **Database Structure**:
  ```json
  {
    "_id": ObjectId("..."),
    "name": "Standard",
    "variants": {
      "base": {
        "versions": [
          {"version": "v1", "steps": [...], "complete": false},
          {"version": "v2", "steps": [...], "complete": false},
          {"version": "v3", "steps": [...], "complete": false}
        ]
      },
      "shot": {
        "versions": [
          {"version": "v1", "steps": [...], "complete": false}
        ]
      }
    }
  }
  ```
- **Version Fields**: Each version object includes:
  - `version` (str) - Version identifier ("v1", "v2", "v3", etc.)
  - `steps` (array) - Array of skeleton steps
  - `complete` (bool) - Completion status (optional)
- **Backward Compatibility**: Engine defaults to "v1" if version field is missing (supports old skeletons)

**Skeleton Structure:**
- Each version contains `steps` array
- Each step has `pos_actions` dict mapping positions to actions
- Actions include: `"handle_ball"`, `"receive"`, `"pass"`, `"shoot"`, `"screen"`, etc.
- Ball handler determined by checking for ball possession actions in steps

**Animation Generation:**
- Skeletons converted to animations via `animator.skeleton_to_animations()`
- Animations include player movements, ball movements, and defender positioning
- Frontend uses skeleton data to animate press break sequences

**Skeleton Builders:**
- **FCP Builder**: `FrontEnd/static/fcp-skeletons.html` - Create/edit FCP skeletons
- **HCT Builder**: `FrontEnd/static/hct-skeletons.html` - Create/edit HCT skeletons
- **Access**: Available via Netlify at `/fcp-skeletons.html` and `/hct-skeletons.html`
- **Save Behavior**: All new/updated skeletons save to `gob-staging` database (name-based upsert matching)
- **Version Management**: Builders support creating multiple versions (v1-v6) for each variant
- See `Plays_Page_System.md` for detailed builder documentation

### Key Files

**Backend:**
- `BackEnd/engine/phase_resolution.py`
  - `resolve_full_court_press_logic()` - FCP outcome resolution
  - `resolve_half_court_trap_logic()` - HCT outcome resolution
  - `get_fcp_skeleton()` - FCP skeleton retrieval with version selection
  - `get_hct_skeleton()` - HCT skeleton retrieval with version selection
  - `get_ball_handler_from_skeleton()` - Dynamic ball handler determination
  - `select_foul_player()` - Probabilistic foul player selection
  - `_record_fcp_stats()` - FCP stat tracking helper
  - `_record_hct_stats()` - HCT stat tracking helper
  - `apply_energy_decay()` - Energy decay for active players
- `BackEnd/api/skeleton_routes.py`
  - `create_fcp_skeleton()` - Create/update FCP skeleton (name-based upsert)
  - `create_hct_skeleton()` - Create/update HCT skeleton (name-based upsert)
  - `get_all_fcp_skeletons()` - Fetch all FCP skeletons
  - `get_all_hct_skeletons()` - Fetch all HCT skeletons
- `BackEnd/models/turn_manager.py`
  - `determine_defensive_pressure_type()` - Determines if FCP/HCT should be applied
- `BackEnd/playcall_skeletons/fcp_skeletons.py` - FCP skeleton definitions (legacy fallback)
- `BackEnd/playcall_skeletons/hct_skeletons.py` - HCT skeleton definitions (legacy fallback)
- `BackEnd/models/animator.py` - Skeleton to animation conversion

**Frontend:**
- `FrontEnd/static/fcp-skeletons.html` - FCP skeleton builder UI
- `FrontEnd/static/hct-skeletons.html` - HCT skeleton builder UI
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js` - FCP/HCT detection and state tracking

**Migration:**
- `scripts/migrate_fcp_hct_to_version_structure.py` - Migration script to add version fields to existing skeletons

### Future Enhancements

- **More Nuanced Defender Assignment**: Currently uses position matching. Future: Determine defender based on actual defensive assignments (zone/man coverage)
- **Enhanced Ball Handler Detection**: Improve detection logic for edge cases where ball handler isn't clear from skeleton
- **Skeleton Variants**: Add more skeleton variants for different press break scenarios
