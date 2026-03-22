## Statistics System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Stat Categories**:
   - **Standard Basketball Stats**: FGM, FGA, 3PTM, 3PTA, FTM, FTA, PTS, REB, OREB, DREB, AST, STL, BLK, TO, F, PIP, MIN
   - **Special Situational Stats**: Fast Break (FB_A, FB_S, FB_A_D, FB_S_D, FB_F_D), FCP/HCT (FCP_A, FCP_S, FCP_A_D, FCP_S_D, HCT_A, HCT_S, HCT_A_D, HCT_S_D), Outlet Pass (Outlet_A, Outlet_S, Outlet_Score, Outlet_Score_List, Outlet_Score_Cum), Defensive Attempts/Success (DEF_A, DEF_S), Screen Attempts/Success (SCR_A, SCR_S), Help Defense (HELP_D)
   - **Team-Level Stats**: Scouting data (offense/defense success rates), team totals, team-level situational stats

2. **Stat Calculation Formulas**:
   - **PTS**: `(2 * FGM) + 3PTM + FTM` (auto-calculated)
   - **REB**: `OREB + DREB` (auto-calculated)
   - **Outlet_Score**: Average of `Outlet_Score_List` (auto-calculated)

3. **Stat Initialization**:
   - All stats initialized to `0` at game start (except `Outlet_Score_List` which is initialized as empty array `[]`)
   - Initialized in `Player._init_stats()` for all stat levels (game, season, career)

**Statistics System Flow (5 Steps)**

1. **Stat Initialization** - All stats set to `0` (or `[]` for lists) at game start for all players
2. **Real-Time Tracking** - Stats incremented during gameplay via `player.record_stat()` calls
3. **Auto-Calculation** - PTS, REB, Outlet_Score calculated automatically when component stats change
4. **Stat Aggregation** - Team totals calculated by summing all player stats from roster
5. **Stat Persistence** - Game stats stored in game document, season/career stats aggregated at game end

**Long Form Documentation**

### Overview

The Statistics System tracks comprehensive player-level and team-level statistics across all game situations. Stats are tracked in real-time during gameplay and aggregated at game, season, and career levels.

**Location:** `BackEnd/models/player.py`, `BackEnd/models/shot_manager.py`, `BackEnd/engine/phase_resolution.py`  
**Status:** ✅ Fully implemented for all game situations  
**Scope:** All player stats, team stats, and scouting data

### Stat Initialization

**Player-Level Stats:**
- All stats initialized to `0` at game start (except `Outlet_Score_List` which is initialized as empty array `[]`)
- Initialized in:
  - `Player._init_stats()` - For all stat levels (game, season, career)
  - `_init_game_stats_dict()` in `BackEnd/main.py` - For single game mode
  - Tournament and Franchise mode initialization functions

**Stat Calculation:**
- **PTS**: Automatically calculated as `(2 * FGM) + 3PTM + FTM` when FGM, 3PTM, or FTM are recorded
- **REB**: Automatically calculated as `OREB + DREB` when OREB or DREB are recorded
- **Outlet_Score**: Automatically calculated as average of `Outlet_Score_List` when new scores are added

### HCO (Half Court Offense) Stat Tracking

**Player-Level Stats:**

**Standard Stats Tracked:**
- **FGA** (Field Goal Attempts): Incremented for shooter on all shot attempts
- **3PTA** (Three-Point Attempts): Incremented for shooter if shot is a three-pointer
- **FGM** (Field Goals Made): Incremented for shooter when shot is made (via `apply_scoring()`)
- **3PTM** (Three-Pointers Made): Incremented for shooter when three-pointer is made (via `apply_scoring()`)
- **PTS** (Points): Automatically calculated from FGM, 3PTM, FTM
- **AST** (Assists): Incremented for passer when shot is made (if passer exists)
  - **Passer Identification Criteria (applies to both Set Plays and Motion Plays):**
    1. Last player to make a pass to the shooter
    2. Pass and receive happened in the same step (passer has "pass" action, shooter has "receive" action)
    3. Pass was within 5 steps of the shot being taken
  - **Implementation:**
    - **Set Plays:** Passer identified during `assign_roles()` via `derive_roles_from_steps()` function
    - **Motion Plays:** Passer re-derived after `resolve_motion_offense_shot()` modifies skeleton and adds pass/receive steps (uses same `derive_passer_from_steps()` logic)
    - **Location:** `BackEnd/models/turn_manager.py` - `derive_passer_from_steps()` method, called from `BackEnd/engine/phase_resolution.py` for Motion plays
- **PIP** (Points in Paint): Incremented for shooter when a **non-fast-break** shot is made from the paint (amount = points scored). Fast-break field goals are **not** counted toward PIP; they are tracked under **FB_PTS** instead. Implementation: `pip_stat_eligible = is_paint and not is_fast_break` in `BackEnd/models/shot_manager.py` (`resolve_shot`).
- **TO** (Turnovers): Incremented for ball handler on dead ball turnovers
- **F** (Fouls): Incremented for foul player (offensive or defensive)
- **BLK** (Blocks): Incremented for defender when shot is blocked
- **DEF_A** (Defensive Attempts): Incremented for defender on shot attempts
- **DEF_S** (Defensive Success): Incremented for defender when shot is missed (without defensive foul)
- **SCR_A** (Screen Attempts): Incremented for screener on screen attempts
- **SCR_S** (Screen Success): Incremented for screener when screen leads to made shot (50% chance per attempt)
- **HELP_D** (Help Defense): Tracked for help defenders in zone defense
- **MIN** (Minutes Played): Tracked for all active players (both teams) at the end of each turn
  - **Tracking Logic:**
    - At the end of each turn, `time_elapsed` (in seconds) is added to `player.stats["game"]["MIN"]` for all players in the active lineup (both home and away teams, 10 players total)
    - Only tracked if `time_elapsed > 0` (timeouts and other 0-time turns are skipped)
    - **Location:** `BackEnd/models/turn_manager.py` - `update_clock_and_possession()` method
  - **Storage Format:**
    - **Game Stats:** Stored in **seconds** (e.g., 240 seconds = 4 minutes of gameplay)
    - **Season/Career Stats:** Stored in **minutes** (e.g., 4 minutes) - converted from game seconds using integer division (`// 60`) at end of game
  - **Display Format:**
    - **Box Score:** Displays integer minutes only (e.g., "4", not "4:00" or "4 min")
    - **Command Centers (TCC/FCC):** Displays season stats directly (already in minutes format)
    - **Conversion:** `Math.floor(game_minutes / 60)` for game stats display
  - **End of Game Accumulation:**
    - **Tournament Mode:** Game MIN (seconds) converted to minutes (`// 60`) and added to `season.MIN`
    - **Franchise Mode:** Game MIN (seconds) converted to minutes (`// 60`) and added to both `season.MIN` and `career.MIN`
    - **Location:** `BackEnd/utils/stat_updater.py` - `apply_stats_from_summary()` and `finalize_game()` functions

**Team-Level Stats (Scouting Data):**

**Offensive Attempt and Success Tracking:**
- **`off_scouting["offense"]["Playcalls"][type_label]["overall"]["attempts"]`**: Incremented when a playcall is executed
- **`off_scouting["offense"]["Playcalls"][type_label][focus]["attempts"]`**: Incremented by play focus (inside/attack/outside)
  - **Set Plays**: Attempts tracked using intended play focus from strategy settings (tracked in `turn_manager.py` before shot resolution)
  - **Motion Plays**: Attempts tracked using actual shot attempt type (tracked in `phase_resolution.py` after shot resolution)
    - Uses `motion_shot_type` from `roles["motion_shot_type"]` (the actual shot type that was attempted)
    - Reflects the actual shot location, not the strategy setting focus
- **`off_scouting["offense"]["Playcalls"][type_label]["overall"]["success"]`**: Incremented when:
  - Shot is made (`MAKE`), or
  - Defensive foul occurs (`FOUL` where `foul_team == "DEFENSE"`)
- **`off_scouting["offense"]["Playcalls"][type_label][focus]["success"]`**: Same criteria, tracked by play focus (inside/attack/outside)
  - **Set Plays**: Uses intended play focus from strategy settings (what the play was designed for)
  - **Motion Plays**: Uses actual shot attempt type (inside/attack/outside) based on where the shot was taken
    - Determined dynamically from `motion_shot_type` (stored in `roles["motion_shot_type"]`)
    - Reflects the actual shot location, not the strategy setting focus
- **`off_scouting["offense"]["Playcalls"]["Cumulative"][focus]["attempts"]`**: Cumulative attempts across all play types
- **`off_scouting["offense"]["Playcalls"]["Cumulative"][focus]["success"]`**: Cumulative success across all play types

**Key Difference:**
- **Set Plays**: Both attempts and successes use the intended focus (tracked at playcall selection time)
- **Motion Plays**: Both attempts and successes use the actual shot type (tracked after shot resolution)
  - This ensures attempts and successes are tracked consistently for the same shot type
  - Example: If a Motion play starts with "Outside" focus but player chooses "Attack" shot, both attempt and success are tracked under "Attack"

**Expected Value (EV) and Execution Score Tracking:**
- **EV Scores** (`ev_scores`): Expected Value percentage (-99.0 to +99.0) calculated for each playcall matchup
  - **Calculation**: Calculated via `calculate_ev()` in `turn_manager.py` before play execution
    - **For Motion Plays**: Uses `game_state["offense_play_focus"]` (chosen focus from strategy settings: inside/attack/outside)
    - **For Set Plays**: Uses `play_doc.get("play_focus")` (intended focus from database)
    - Motion plays have `play_focus = null` in database, so chosen focus from strategy settings is used
  - **Storage**: Stored in `off_scouting["offense"]["Playcalls"][type_label]["overall"]["ev_scores"]` and focus-specific buckets
    - Also stored in `def_scouting["defense"][tracking_name]["game_stats"]["ev_scores"]` and vs_* buckets
    - Stored via `_store_ev_score()` after EV calculation
  - **Focus Usage**: EV uses the **chosen focus** (from strategy settings) for both Motion and Set Plays
    - This represents the intended offensive strategy before execution
- **Execution Scores** (`lean_scores`): Execution quality score (0-100) representing how well the play was executed
  - **Calculation**: Calculated in `resolve_hco_outcome()` during HCO turn resolution (for ALL HCO results: SHOT, O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER)
    - Step 1: Calculate raw `result = (offensive_efficiency + o_random) - (defensive_efficiency + d_random)`
    - Step 2: Cap `result` at -100 to +100 range: `capped_result = max(-100, min(100, result))`
    - Step 3: Store `capped_result` in `game_state["lean_result_value"]` for lean meter display (-100 to +100)
    - Step 4: Scale to 0-100 for stat tracking: `execution_score = (capped_result + 100) / 2`
    - Formula maps: -100 → 0%, 0 → 50%, +100 → 100%
    - **Note**: Execution score calculation does NOT use focus - it's based solely on team efficiency attributes
  - **Lean Meter Display**: Uses the raw `capped_result` value (-100 to +100) directly, not the scaled execution_score
    - Stored in `game_state["lean_result_value"]` and added to turn text as `"lean:XX.X"` for frontend parsing
    - Frontend `animateLeanMeter()` receives the -100 to +100 value and scales it to visual fill percentage
  - **Storage**: Stored as `lean_scores` (converted to -1.0 to +1.0 format for backward compatibility)
    - Stored in `off_scouting["offense"]["Playcalls"][type_label]["overall"]["lean_scores"]` and focus-specific buckets
    - Also stored in `def_scouting["defense"][tracking_name]["game_stats"]["lean_scores"]` and vs_* buckets
    - Conversion: `lean_score = (execution_score - 50) / 50` (maps 0-100 to -1.0 to +1.0)
    - Calculated and stored via `_store_execution_score()` in `phase_resolution.py` after shot resolution
  - **Focus Usage**: Execution scores use the **actual shot type** for focus tracking
    - **For Motion Plays**: Uses actual shot type (`motion_shot_type`: inside/attack/outside) determined during execution
    - **For Set Plays**: Uses intended focus from strategy settings (same as EV)
    - This means Motion Plays can have EV stored under one focus (chosen) and execution score stored under a different focus (actual)

**Defensive Success Tracking:**
- **`def_scouting["defense"][tracking_name]["used"]`**: Incremented each time defense is used (by defensive playcall: Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone)
- **`def_scouting["defense"][tracking_name]["success"]`**: Incremented when:
  - Shot is missed (`MISS` without defensive foul), or
  - Turnover occurs (`TURNOVER`), or
  - Offensive foul occurs (`O_FOUL`)
- **Granular Tracking**: Success tracked by:
  - Play type (vs_motion, vs_set)
  - Focus type (vs_inside, vs_attack, vs_outside)
  - Defense type (vs_man, vs_2-3_zone, vs_3-2_zone, vs_1-3-1_zone, vs_zone aggregate)
  - Combinations (vs_motion_inside, vs_set_attack, etc.)

**Stat Tracking Location:**
- `BackEnd/models/shot_manager.py` - `resolve_shot()` method
- `BackEnd/engine/phase_resolution.py` - `resolve_half_court_offense_logic()` method

### OREB (Offensive Rebound) Stat Tracking

**Player-Level Stats:**

**Standard Stats Tracked:**
- **OREB** (Offensive Rebounds): Incremented for rebounder when offensive rebound is secured
- **DREB** (Defensive Rebounds): Incremented for rebounder when defensive rebound is secured
- **REB** (Total Rebounds): Automatically calculated as `OREB + DREB`
- **FGA** (Field Goal Attempts): Incremented for rebounder on putback attempts
- **FGM** (Field Goals Made): Incremented for rebounder when putback is made (via `apply_scoring()`)
- **PTS** (Points): Automatically calculated from FGM, 3PTM, FTM
- **PIP** (Points in Paint): Incremented for rebounder when putback is made (always 2 points, putbacks are from paint)
- **DEF_A** (Defensive Attempts): Incremented for defender on putback attempts
- **DEF_S** (Defensive Success): Incremented for defender when putback is missed

**Putback vs Kickout:**
- **Putback (90% chance)**: Rebounder attempts shot immediately
  - Tracks FGA, FGM, PTS, PIP for rebounder
  - Tracks DEF_A, DEF_S for defender
- **Kickout (10% chance)**: Rebounder passes out, transitions to HCO
  - Only tracks OREB for rebounder
  - No shot attempt stats tracked

**Stat Tracking Location:**
- `BackEnd/utils/shared.py` - `resolve_offensive_rebound()` function
- `BackEnd/models/rebound_manager.py` - `handle_rebound()` method

### Free Throw Stat Tracking

**Player-Level Stats:**

**Standard Stats Tracked:**
- **FTA** (Free Throw Attempts): Incremented for shooter on each free throw attempt
- **FTM** (Free Throws Made): Incremented for shooter when free throw is made (via `apply_scoring()`)
- **PTS** (Points): Automatically calculated from FGM, 3PTM, FTM
- **OREB** (Offensive Rebounds): Incremented for rebounder if free throw is missed and offensive rebound secured
- **DREB** (Defensive Rebounds): Incremented for rebounder if free throw is missed and defensive rebound secured

**Free Throw Scenarios:**
- **Regular Free Throws**: 1-3 attempts based on foul situation
- **1-and-1 Free Throws**: Front end must be made to unlock second attempt
- **Bonus/Double Bonus**: Automatic free throws based on team foul count

**Stat Tracking Location:**
- `BackEnd/engine/phase_resolution.py` - `resolve_free_throw_logic()` function

**Team-Level Stats:**
- No specific team-level tracking for free throws (standard scoring stat)

### Fast Break Stat Tracking

**Player-Level Stats:**

**Offensive Stats (Release Player / Outlet Receiver):**
- **`FB_A`** (Fast Break Attempts): Always incremented when player is the outlet receiver on a Fast Break
- **`FB_S`** (Fast Break Success): Incremented when Fast Break results in:
  - Shot Make (`MAKE`), or
  - Defensive Foul (non-shooting) (`FOUL` where `foul_team == "DEFENSE"`)
- **Retired**: **`FB_F`** / **`FB_N`** are no longer tracked; situational display uses **S / A / %** from **`FB_S`** and **`FB_A`** only.
- **Standard Stats**: FGA, FGM, 3PTM, PTS, **FB_PTS** (fast break points only—does not add to PIP), AST (if assist on made shot)

**Defensive Stats (Get-Back Players):**
- **`FB_A_D`** (Fast Break Attempts Defense): Always incremented when player is a get-back defender on a Fast Break
- **`FB_S_D`** (Fast Break Success Defense): Incremented when Fast Break results in:
  - `DEFENSIVE_STOP`
- **`FB_F_D`** (Fast Break Failure Defense): Incremented when Fast Break results in:
  - Shot Make (`MAKE`), or
  - Shot Make + Foul, or
  - Shot Miss + Foul, or
  - Defensive Foul (non-shooting)

**Outlet Pass Stats (Outlet Passer):**
- **`Outlet_A`** (Outlet Pass Attempts): Always incremented when player makes an outlet pass
- **`Outlet_S`** (Outlet Pass Successes): Incremented when outlet pass leads to a shot attempt (not a defensive stop)
- **`Outlet_Score`** (Average Outlet Pass Score): Average of all outlet pass scores (1-100 scale)
- **`Outlet_Score_List`** (Outlet Pass Score List): Array of individual outlet pass scores
- **`Outlet_Score_Cum`** (Cumulative Outlet Pass Score): Sum of all outlet pass scores

**Outlet Pass Score Calculation:**
- **Formula**: `(PS * 0.6 + ST * 0.2 + IQ * 0.2) * random.randint(1, 6)`
- **Scaling**: Raw score (1-600 range, midpoint 175) is scaled to 1-100 range (midpoint 50)
- **Function**: `calculate_outlet_pass_score()` in `BackEnd/utils/shared.py`
- **Scaling Function**: `scale_score_to_100()` in `BackEnd/utils/shared.py` (universal helper for all attribute-based scores)

**Team-Level Stats (Scouting Data):**
- **`Fast_Break_Entries`** (Offense): Incremented each time a team runs a Fast Break (same total as sum of **`fast_break_plays[*].A`**)
- **`Fast_Break_Success`** (Offense): Incremented only when Fast Break result_type is:
  - `MAKE`, or
  - `FOUL` where `foul_team == "DEFENSE"` (defensive foul on the break)
  - **Note**: `MISS` or `TURNOVER` do NOT count as team success (they count as defensive success)
- **`fast_break_plays`** (Offense): Per-play **attempts (`A`)** and **successes (`S`)** for `covert_release`, `rim_runner`, `thirty_two`, `after_steal`; same success rules as **`Fast_Break_Success`**, applied to the play bucket for that possession. **`Fast_Break_Entries`** / **`Fast_Break_Success`** are incremented in parallel (both aggregate and per-play rows). Defense has **no** per-play FB scouting.
- **`vs_Fast_Break.used`** (Defense): Incremented each time defending a Fast Break
- **`vs_Fast_Break.success`** (Defense): Incremented when Fast Break result_type is:
  - `DEFENSIVE_STOP`, or
  - `MISS`, or
  - `TURNOVER`, or
  - `FOUL` where `foul_team == "OFFENSE"`

**Stat Tracking Location:**
- `BackEnd/engine/phase_resolution.py` - `resolve_fast_break_logic()` function
- `BackEnd/engine/phase_resolution.py` - `_record_fast_break_stats()` helper function
- `BackEnd/engine/phase_resolution.py` - `_record_outlet_pass_stats()` helper function

**Special Handling:**
- **`Outlet_Score_List`**: Excluded from stat delta calculations (it's a list, not numeric)
- **Team Stats Aggregation**: `Outlet_Score_List` is concatenated (not summed) when aggregating team stats
- **Stat Deltas**: `Outlet_Score_List` and `REB` are excluded from delta calculations in `turn_manager.py`

### FCP (Full Court Press) Stat Tracking

**Player-Level Stats:**

**Offensive Stats (All 5 Players in Active Lineup):**
- **`FCP_A`** (FCP Attempts): Always incremented for all offensive players in active lineup
- **`FCP_S`** (FCP Success): Incremented for all offensive players when FCP result_type is:
  - `MAKE` (made shot), or
  - `HCO` (press break - successfully broke through), or
  - `FOUL` where `foul_team == "DEFENSE"` (defensive foul)

**Defensive Stats (All 5 Players in Active Lineup):**
- **`FCP_A_D`** (FCP Attempts Defense): Always incremented for all defensive players in active lineup
- **`FCP_S_D`** (FCP Success Defense): Incremented for all defensive players when FCP result_type is:
  - `MISS` (missed shot), or
  - `TURNOVER`, `STEAL`, `DEAD BALL`, or
  - `FOUL` where `foul_team == "OFFENSE"` (offensive foul)

**Standard Stats (When Applicable):**
- **FGA, FGM, 3PTM, PTS**: Tracked for shooter on shot attempts
- **AST**: Tracked for passer on made shots
- **TO**: Tracked for ball handler on turnovers/steals
- **STL**: Tracked for defender on steals
- **F**: Tracked for foul player

**Team-Level Stats (Scouting Data):**

**Defensive Success Tracking:**
- **`def_scouting["defense"]["FCP"]["used"]`**: Incremented each time defense applies Full Court Press
- **`def_scouting["defense"]["FCP"]["success"]`**: Incremented when FCP result_type is:
  - `MISS` (missed shot during press break)
  - `O_FOUL` (offensive foul)
  - `DEAD_BALL_TURNOVER` (dead ball turnover)
  - `STEAL` (steal)

**Offensive Success (Derived):**
- `offensive_successes = total_attempts - defensive_successes`
- `offensive_failures = defensive_successes`
- `defensive_failures = total_attempts - defensive_successes`

**Stat Tracking Location:**
- `BackEnd/engine/phase_resolution.py` - `resolve_full_court_press_logic()` function
- `BackEnd/engine/phase_resolution.py` - `_record_fcp_stats()` helper function

**Stat Tracking Timing:**
- **SHOT Results**: Tracked after shot resolution (MAKE/MISS) in `resolve_full_court_press_logic()`
- **Non-SHOT Results**: Tracked after result type determination (O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER, HCO)

### HCT (Half Court Trap) Stat Tracking

**Player-Level Stats:**

**Offensive Stats (All 5 Players in Active Lineup):**
- **`HCT_A`** (HCT Attempts): Always incremented for all offensive players in active lineup
- **`HCT_S`** (HCT Success): Incremented for all offensive players when HCT result_type is:
  - `MAKE` (made shot), or
  - `HCO` (trap break - successfully broke through), or
  - `FOUL` where `foul_team == "DEFENSE"` (defensive foul)

**Defensive Stats (All 5 Players in Active Lineup):**
- **`HCT_A_D`** (HCT Attempts Defense): Always incremented for all defensive players in active lineup
- **`HCT_S_D`** (HCT Success Defense): Incremented for all defensive players when HCT result_type is:
  - `MISS` (missed shot), or
  - `TURNOVER`, `STEAL`, `DEAD BALL`, or
  - `FOUL` where `foul_team == "OFFENSE"` (offensive foul)

**Standard Stats (When Applicable):**
- **FGA, FGM, 3PTM, PTS**: Tracked for shooter on shot attempts
- **AST**: Tracked for passer on made shots
- **TO**: Tracked for ball handler on turnovers/steals
- **STL**: Tracked for defender on steals
- **F**: Tracked for foul player

**Team-Level Stats (Scouting Data):**

**Defensive Success Tracking:**
- **`def_scouting["defense"]["HCT"]["used"]`**: Incremented each time defense applies Half Court Trap
- **`def_scouting["defense"]["HCT"]["success"]`**: Incremented when HCT result_type is:
  - `MISS` (missed shot during trap break)
  - `O_FOUL` (offensive foul)
  - `DEAD_BALL_TURNOVER` (dead ball turnover)
  - `STEAL` (steal)

**Offensive Success (Derived):**
- `offensive_successes = total_attempts - defensive_successes`
- `offensive_failures = defensive_successes`
- `defensive_failures = total_attempts - defensive_successes`

**Stat Tracking Location:**
- `BackEnd/engine/phase_resolution.py` - `resolve_half_court_trap_logic()` function
- `BackEnd/engine/phase_resolution.py` - `_record_hct_stats()` helper function

**Stat Tracking Timing:**
- **SHOT Results**: Tracked after shot resolution (MAKE/MISS) in `resolve_half_court_trap_logic()`
- **Non-SHOT Results**: Tracked after result type determination (O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER, HCO)

### Other Turn Types with Stat Tracking

**Steals:**
- **STL** (Steals): Incremented for defender who steals the ball
- **TO** (Turnovers): Incremented for ball handler (victim of steal)
- **Fast Break Stats**: May trigger fast break opportunity, tracking `FB_A`, `FB_S` for release player / ball handler and `FB_A_D`, `FB_S_D`, `FB_F_D` for get-back players

**Turnovers (Dead Ball):**
- **TO** (Turnovers): Incremented for ball handler
- **Fast Break Stats**: May trigger fast break opportunity (same as steals)

**Fouls:**
- **F** (Fouls): Incremented for foul player (offensive or defensive)
- **Team Fouls**: Incremented for foul team
- **Free Throws**: May trigger free throw sequence (tracks FTA, FTM)

**Rebounds:**
- **OREB** (Offensive Rebounds): Incremented for rebounder on offensive rebounds
- **DREB** (Defensive Rebounds): Incremented for rebounder on defensive rebounds
- **REB** (Total Rebounds): Automatically calculated as `OREB + DREB`
- **Fast Break Stats**: DREB may trigger fast break opportunity

### Stat Aggregation and Team Totals

**Player Stat Aggregation:**
- Team totals calculated by summing all player stats from roster (not just active lineup)
- Includes bench players who may have played earlier in the game
- Aggregated in `TeamManager.get_team_game_stats()` method

**Team-Level Stats:**
- **Team Stats**: Aggregated from player stats (PTS, FGM, FGA, etc.)
- **Scouting Data**: Tracked separately at team level (offense/defense success rates)
- **Team Stats Dictionary**: Tracks team-level metrics (release_instances, get_back_instances, actual_releases, fast break defender counts)

**Stat Deltas:**
- Calculated between turns to show stat changes
- Excludes calculated stats (REB, PTS) and list stats (Outlet_Score_List)
- Used for frontend stat updates without full roster refresh

**Stat Persistence:**
- Game stats: Stored in game document
- Season stats: Aggregated across games in tournament/franchise mode
- Career stats: Aggregated across all seasons for franchise mode

**Stats Page Scoped Leaders:**
- `stats.html` shows Individual Leaders for `conference`, `region`, and `national` scopes.
- Each leaders card must display the true top `10` players within the selected view scope for that stat category.
- Scope filtering occurs before ranking and before limiting.
- Conference and region leader boards must not be derived from a pre-limited national list.

### Key Files

**Backend:**
- `BackEnd/models/player.py` - Player stat initialization and recording (`record_stat()`, `_init_stats()`)
- `BackEnd/models/shot_manager.py` - Shot stat tracking (FGA, FGM, AST, BLK, DEF_A, DEF_S)
- `BackEnd/engine/phase_resolution.py` - Fast Break, FCP, HCT, Free Throw stat tracking (`_record_fast_break_stats()`, `_record_fcp_stats()`, `_record_hct_stats()`, `_record_outlet_pass_stats()`)
- `BackEnd/utils/shared.py` - OREB stat tracking, outlet pass score calculation (`calculate_outlet_pass_score()`, `scale_score_to_100()`)
- `BackEnd/models/rebound_manager.py` - Rebound stat tracking
- `BackEnd/models/turn_manager.py` - MIN tracking (`update_clock_and_possession()`), passer identification (`derive_passer_from_steps()`)
- `BackEnd/models/team_manager.py` - Team stat aggregation (`get_team_game_stats()`)
- `BackEnd/constants/__init__.py` - `BOX_SCORE_KEYS` definition (all trackable stats)
- `BackEnd/utils/stat_updater.py` - Stat persistence and aggregation (`apply_stats_from_summary()`, `finalize_game()`)
- `BackEnd/api/franchise_routes.py` - Franchise leaders/team-stats endpoints (`/franchise/leaders`, `/franchise/team-stats`)
