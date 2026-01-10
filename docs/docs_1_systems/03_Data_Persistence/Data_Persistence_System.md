# Data Persistence System ✅ **COMPLETE** (January 2025)

## Base Constants

**Purpose:** Documents what data is persisted in each game mode when the user is in non-gameplay situations (Command Center, Game Plan, Playbooks, Training, Training Report). Critical for understanding what state needs to be maintained across navigation transitions.

**Collections:**
- `franchises` - Franchise mode documents
- `tournaments` - Tournament mode documents
- `games` - Single Game mode documents
- `teams` - Universal team collection (source of truth for initial values)
- `players` - Universal player collection (baseline attributes)

**Common Data Fields (All Modes):**
- Team attributes: `shot_threshold`, `discipline`, `fight`, `rebound_modifier`, `offensive_efficiency`, `team_chemistry`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`
- Strategy settings: `{offense, inside, attack, outside, tempo, defense, aggression, hc_trap, fc_press, rebounding}` (0-4)
- Playbook settings: `{motion, set_play_inside, set_play_attack, set_play_outside, zone_defense, man_defense, slot_assignments, motion_dropdowns, position_filters}`
- Plays data: `{[playName]: {effectiveness, momentum, cloaking, game_stats, season_stats}}`
- Scouting data: `{defense: {Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone, vs_Fast_Break, FCP, HCT: {effectiveness, momentum, cloaking, game_stats, season_stats}}}`

## System Flow

1. **Franchise Mode**: Data stored in `franchises` collection → `franchise_teams.{team_id}` and `players.{player_id}`
2. **Tournament Mode**: Data stored in `tournaments` collection → `teams.{team_id}` and `player_stats.{player_id}`
3. **Single Game Mode**: Data stored in `games` collection → `teams.{team_id}` (temporary, reset for each game)

## Long Form Documentation

### Overview

This system documents data persistence across all three game modes when users are in non-gameplay situations. Understanding what data persists is critical for maintaining state across navigation transitions and ensuring data consistency.

**Reference Documentation:**
- `docs/franchise_mode_architecture.md` - Complete franchise mode data structure
- `docs/COMMON_DATA_SET.md` - Common data structure across all modes
- `docs/docs_1_systems/01_Game_Mode_Systems/` - Mode-specific system documentation

---

### Franchise Mode (Non-Gameplay)

**When:** User is in Franchise Mode but not actively playing a game (Command Center, Game Plan, Playbooks, Training, Training Report)

**Collection:** `franchises`  
**Document ID:** `_id: ObjectId("franchise_id")`

#### A. Franchise Document Fields

**Season Progress:**
- `week`: Current week number (1-14)
- `current_week`: Alias for week
- `schedule`: Pre-generated schedule array `[[team_A_id, team_B_id], ...]` (14 weeks)

**Game Results (Summaries Only):**
- `results`: Object with weekly summaries
  ```javascript
  {
    "1": [{away_id, home_id, away_score, home_score}, ...],
    "2": [{away_id, home_id, away_score, home_score}, ...],
    // ... up to week 14
  }
  ```

**Training State:**
- `training_status`: 
  ```javascript
  {
    "current_week": number,
    "training_completed": boolean,
    "session_type": "preseason" | "in-season"
  }
  ```
- `latest_training`:
  ```javascript
  {
    "player_logs": {...},  // What improved
    "team_log": {...},
    "session_type": "preseason" | "in-season",
    "week": number
  }
  ```

**Stat Tracking:**
- `applied_games`: Array of game IDs `["game_id_1", "game_id_2"]` (prevents double-counting stats)

**Recruiting:**
- `recruits`: Array of recruit objects (franchise-specific pool)

#### B. Team Objects (`franchise_teams.{team_id}`)

**For each of the 8 teams in the franchise:**

**Team Attributes** (mode-specific, randomized on init, updated by training):
- `team_chemistry`: 7-13 (franchise mode range)
- `offensive_efficiency`: -3 to +3
- `shot_threshold`: -10 to 190 (randomized, center at 90 for pill display)
- `discipline`: -3 to +3 (formerly `turnover_modifier`)
- `fight`: -3 to +3 (formerly `foul_modifier`)
- `rebound_modifier`: 0.2 (fixed center value for Franchise mode)
- `defensive_efficiency`: -3 to +3
- `fb_efficiency`: -3 to +3
- `pt_efficiency`: -3 to +3
- `fb_opp_modifier`: -3 to +3
- `pt_opp_modifier`: -3 to +3

**Strategy Settings** (user-configurable, persist across all instances):
- `strategy_settings`: `{offense, inside, attack, outside, tempo, defense, aggression, hc_trap, fc_press, rebounding}` (all 0-4)

**Plays Data** (updated by training):
- `plays`: Object with play data including `effectiveness`, `momentum`, `cloaking` (0-100, 0-10, 0-10), `game_stats`, `season_stats`

**Scouting Data** (updated by training):
- `scouting_data`: Defense structures (Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone, vs_Fast_Break, FCP, HCT) with `effectiveness`, `momentum`, `cloaking`, `game_stats`, `season_stats`

**Playbook Settings** (user-configurable, persist across all instances):
- `playbook_settings`: `{motion, set_play_inside, set_play_attack, set_play_outside, zone_defense, man_defense, slot_assignments, motion_dropdowns, position_filters}`

**Legacy playcall_settings** (still present for backward compatibility)

**Initialization:** Team objects are created for all 8 teams when franchise is initialized via `FranchiseManager.initialize_season()` or lazily via `ensure_team_objects_exist()` when accessing Game Plan/Playbooks.

#### C. Player Objects (`players.{player_id}`)

**For each player in the franchise:**

- **Player Metadata** (`meta`: first_name, last_name, team, team_id)
- **Evolved Attributes** (`attributes`: all 30+ attributes with `anchor_` prefixed versions, updated by training)
- **Evolved Position Ratings** (`position_ratings`: PG, SG, SF, PF, C ratings, updated by training)
- **Statistics** (`season`: season stats, `career`: career stats)

#### D. Additional Collections (Not in Franchise Document)

**Training Logs (`training_logs` collection):**
- Historical training sessions (separate collection)
- Each session includes allocations, logs, and changes

**Games Collection (`games` collection):**
- Active game documents (during gameplay)
- Not part of franchise document during non-gameplay

**Summary:**
- All team and player data is franchise-specific and isolated from other franchises
- Changes to strategy settings, playbook settings, and training improvements persist across the franchise season
- Team objects include all common data fields (attributes, strategy_settings, plays, scouting_data, playbook_settings)

**For complete structure details, see:** `docs/franchise_mode_architecture.md` Section 7: NON-GAMEPLAY DATA PERSISTENCE

---

### Tournament Mode (Non-Gameplay)

**When:** User is in Tournament Mode but not actively playing a game (Command Center, Game Plan, Playbooks, Training, Training Report)

**Collection:** `tournaments`  
**Document ID:** `_id: ObjectId("tournament_id")`

#### A. Tournament Document Fields

**Tournament Progress:**
- `current_round`: Current round number (1, 2, or 3)
- `bracket`: Bracket structure with matchups and results
  ```javascript
  {
    "round1": [{away_id, home_id, away_score, home_score, winner_id}, ...],
    "round2": [{away_id, home_id, away_score, home_score, winner_id}, ...],
    "final": [{away_id, home_id, away_score, home_score, winner_id}]
  }
  ```

**Training State:**
- `training_status`: 
  ```javascript
  {
    "round": number,  // 1, 2, or 3
    "training_completed": boolean,
    "last_training_date": datetime
  }
  ```
- `latest_training`:
  ```javascript
  {
    "round": number,
    "player_logs": {...},
    "team_log": {...},
    "session_type": "tournament"
  }
  ```
- `training_reports`: Per-round training reports
  ```javascript
  {
    "1": {...},  // First Round training report
    "2": {...},  // Semifinals training report
    "3": {...}   // Championship training report
  }
  ```

**Stat Tracking:**
- `applied_games`: Array of game IDs `["game_id_1", "game_id_2"]` (prevents double-counting stats)

**Leaderboards:**
- `stats`: Tournament leaderboards `{top_10_points, top_10_rebounds, ...}`

#### B. Team Objects (`teams.{team_id}`)

**For each of the 8 teams in the tournament:**

**Team Attributes** (mode-specific, randomized on init, updated by training):
- `team_chemistry`: 7-25 (tournament mode range)
- `offensive_efficiency`: -10 to +10
- `shot_threshold`: -10 to 190 (randomized, center at 90 for pill display)
- `discipline`: -10 to +10 (formerly `turnover_modifier`)
- `fight`: -10 to +10 (formerly `foul_modifier`)
- `rebound_modifier`: 0.0-0.4 (random in 0.01 increments)
- `defensive_efficiency`: -10 to +10
- `fb_efficiency`: -10 to +10
- `pt_efficiency`: -10 to +10
- `fb_opp_modifier`: -10 to +10
- `pt_opp_modifier`: -10 to +10

**Strategy Settings** (user-configurable, persist across all instances):
- `strategy_settings`: `{offense, inside, attack, outside, tempo, defense, aggression, hc_trap, fc_press, rebounding}` (all 0-4)

**Plays Data** (updated by training):
- `plays`: Object with play data including `effectiveness`, `momentum`, `cloaking` (0-80 randomized on init, 0-10, 0-10), `game_stats`, `season_stats`

**Scouting Data** (updated by training):
- `scouting_data`: Defense structures (Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone, vs_Fast_Break, FCP, HCT) with `effectiveness`, `momentum`, `cloaking` (0-80 randomized on init, 0-10, 0-10), `game_stats`, `season_stats`

**Playbook Settings** (user-configurable, persist across all instances):
- `playbook_settings`: `{motion, set_play_inside, set_play_attack, set_play_outside, zone_defense, man_defense, slot_assignments, motion_dropdowns, position_filters}`

**Initialization:** Team objects are created for all 8 teams when tournament is created via `TournamentManager.create_tournament()` or lazily via `ensure_team_objects_exist()` when accessing Game Plan/Playbooks.

#### C. Player Objects (`player_stats.{player_id}`)

**For each player in the tournament:**

- **Player Attributes** (`attributes`: all 30+ attributes, updated by training)
- **Statistics** (`game`: game stats, `season`: tournament stats)

**Note:** Tournament mode uses unified attribute storage pattern - all attributes stored in `tournament.player_stats.{player_id}.attributes` (not just EM, CH, MO).

#### D. Additional Collections (Not in Tournament Document)

**Games Collection (`games` collection):**
- Active game documents (during gameplay)
- Not part of tournament document during non-gameplay

**Summary:**
- All team and player data is tournament-specific and isolated from other tournaments
- Changes to strategy settings, playbook settings, and training improvements persist throughout the tournament
- Team objects include all common data fields (attributes, strategy_settings, plays, scouting_data, playbook_settings)
- Training is mandatory before each round (First Round, Semifinals, Championship)

---

### Single Game Mode (Non-Gameplay)

**When:** User is in Single Game Mode but not actively playing (Lineup Selection, Game Plan, Playbooks)

**Collection:** `games`  
**Document ID:** `_id: UUID string or ObjectId("game_id")`

#### A. Game Document Fields

**Game State:**
- `mode`: "single" (identifies as Single Game mode)
- `home_team_id`: Home team ObjectId
- `away_team_id`: Away team ObjectId
- `quarter`: Current quarter (1-4, or OT)
- `clock`: Game clock (e.g., "8:00")
- `time_remaining`: Time remaining in seconds
- `score`: `{team_name: score}`

**Game Settings:**
- `home_lineup`: Selected lineup for home team
- `away_lineup`: Selected lineup for away team
- `user_team_side`: "home" or "away" (user's team)

#### B. Team Objects (`teams.{team_id}`)

**For each of the 2 teams in the game:**

**Team Attributes** (mode-specific, randomized on init, NOT updated by training):
- `team_chemistry`: 7-25 (single game mode range)
- `offensive_efficiency`: -10 to +10
- `shot_threshold`: -10 to 190 (randomized, center at 90 for pill display)
- `discipline`: -10 to +10 (formerly `turnover_modifier`)
- `fight`: -10 to +10 (formerly `foul_modifier`)
- `rebound_modifier`: 0.0-0.4 (random in 0.01 increments)
- `defensive_efficiency`: -10 to +10
- `fb_efficiency`: -10 to +10
- `pt_efficiency`: -10 to +10
- `fb_opp_modifier`: -10 to +10
- `pt_opp_modifier`: -10 to +10

**Strategy Settings** (user-configurable, persist during game):
- `strategy_settings`: `{offense, inside, attack, outside, tempo, defense, aggression, hc_trap, fc_press, rebounding}` (all 0-4)

**Plays Data** (loaded from universal collection, NOT updated):
- `plays`: Object with play data from universal `plays` collection

**Scouting Data** (loaded from universal collection, NOT updated):
- `scouting_data`: Defense structures from universal collection

**Playbook Settings** (user-configurable, persist during game):
- `playbook_settings`: `{motion, set_play_inside, set_play_attack, set_play_outside, zone_defense, man_defense, slot_assignments, motion_dropdowns, position_filters}`

**Legacy playcall_settings** (still present for backward compatibility)

**Initialization:** Team objects are created lazily when user accesses Game Plan or Playbooks page via `ensure_team_objects_exist()`.

**Persistence:**
- Team objects persist for the duration of the game
- When a new game is started, new team objects are created (no carryover from previous games)
- Team attributes are reset to universal `teams` collection values or randomly generated for each new game

#### C. Player Objects

**Player data is loaded from universal `players` collection:**
- Player attributes are NOT modified in Single Game mode
- Player stats are tracked per game but not persisted across games
- No player evolution or training in Single Game mode

**Summary:**
- Team objects are temporary and reset for each new game
- Strategy settings and playbook settings persist during the game but reset for new games
- No training or attribute evolution in Single Game mode
- All data is game-specific and isolated from other games

---

### Key Files

**Franchise Mode:**
- `BackEnd/models/franchise_manager.py` - `initialize_season()` (lines 109-235)
- `BackEnd/api/franchise_routes.py` - `get_franchise_team_data()` (lines 832-881)
- `BackEnd/api/franchise_routes.py` - `run_franchise_training()` (lines 1802-2123)

**Tournament Mode:**
- `BackEnd/tournament/tournament_manager.py` - `create_tournament()` (initializes all 8 teams)
- `BackEnd/api/tournament_routes.py` - `run_tournament_training()` (training execution)
- `BackEnd/api/tournament_routes.py` - `get_tournament_team_data()` (team data retrieval)

**Single Game Mode:**
- `BackEnd/api/api.py` - `init_game()` (game initialization)
- `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (lazy team object creation)

**Common:**
- `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (lines 152-299)
- `BackEnd/models/team_manager.py` - `init_team_attributes()` (lines 185-226)
- `docs/franchise_mode_architecture.md` - Complete franchise mode architecture
- `docs/COMMON_DATA_SET.md` - Common data structure across all modes

---

## Known Issues & Fixes (January 2025-2026)

### ✅ Fixed: Playbook Percentage Persistence (0% Values)

**Issue:** Playbook percentages were not persisting correctly, especially 0% values. When users set percentages and saved, then reloaded the playbooks page, percentages would reset to 0 or default values.

**Root Cause:**
- Frontend `savePlaybookSettings()` only saved percentages > 0 (filtered out 0% values)
- When loading, all percentages were reset to 0 first, then saved values applied
- If a play wasn't in the saved percentages object (because it was 0%), it stayed at 0
- This created a mismatch where the database didn't have complete percentage data

**Fix (January 2025):**
- Modified `FrontEnd/static/playbooks.js` `savePlaybookSettings()` to save ALL percentages including 0%
- Changed condition from `playData.percentage > 0` to save all percentages (using `playData.percentage || 0`)
- This ensures the database is the complete source of truth for all play percentages

**Files Changed:**
- `FrontEnd/static/playbooks.js` (lines 2073-2120)

---

### ✅ Fixed: Plays Not Populating After Training

**Issue:** After running training in Franchise/Tournament mode, when revisiting the Playbooks page, offense play containers were empty (no plays listed). Defense plays still appeared because they come from hardcoded data.

**Root Cause:**
- Training execution (`execute_training()`) modifies plays data and returns `updated_plays`
- Backend only saved `updated_plays` if it was truthy: `if updated_plays:`
- If `updated_plays` was an empty dict `{}` or `None`, plays weren't saved
- When playbooks page reloaded, `/api/playbooks` endpoint read `team_obj.get("plays", {})` which was empty
- Frontend had no plays to display in containers

**Fix (January 2025):**
- Modified `BackEnd/api/franchise_routes.py` and `BackEnd/api/tournament_routes.py` to always save plays data after training
- Changed condition from `if updated_plays:` to `if updated_plays is not None:`
- This ensures plays structure is preserved even if training doesn't modify plays
- Added logging to track when plays are saved vs. preserved
- Enhanced plays initialization logging to track when plays are populated from universal collection

**Files Changed:**
- `BackEnd/api/franchise_routes.py` (lines 2204-2213, 2328-2334)
- `BackEnd/api/tournament_routes.py` (lines 1104-1122, 1184-1190)

**Prevention:**
- Plays are now initialized before training if empty (prevents empty plays_data from being passed to training)
- Training always returns plays data (even if unchanged)
- Backend always saves plays data after training (preserves structure)

---

### Playbook Settings Structure

**Complete Playbook Settings Object:**
```javascript
{
  "motion": { "Play Name": percentage (0-100), ... },
  "set_play_inside": { "Play Name": percentage (0-100), ... },
  "set_play_attack": { "Play Name": percentage (0-100), ... },
  "set_play_outside": { "Play Name": percentage (0-100), ... },
  "zone_defense": { "Defense Name": percentage (0-100), ... },
  "man_defense": { "Defense Name": percentage (0-100), ... },
  "slot_assignments": { "playId": slotNumber, ... },
  "motion_dropdowns": { "playId": dropdownValue, ... },
  "position_filters": { "standard": [...], "PG": [...], ... },
  "even_distribution_all": boolean
}
```

**Key Points:**
- All percentages are saved (including 0%) to ensure database is complete source of truth
- Plays data structure must be preserved through training to prevent empty containers
- Defense plays come from hardcoded `DEFENSE_PLAY_DATA` (not from database), so they always appear
- Offense plays come from database `plays` object, so structure must be maintained

---

### ✅ Fixed: `even_distribution_all` Flag Auto-Redistribution Bug (January 2026)

**Issue:** When `even_distribution_all: true`, percentages were being redistributed on every page load, overwriting saved percentages that users had manually set. Users could not persist custom percentages when the flag was `true`.

**Root Cause:**
- `loadState()` method checked `even_distribution_all` flag and automatically redistributed percentages on every page load
- This overwrote saved percentages that were already correctly stored in the database
- The flag was being used as a "behavior instruction" (redistribute on load) instead of a "preference indicator" (user wants even distribution)

**Fix (January 2026):**
- Modified `FrontEnd/static/playbooks.js` `loadState()` to never redistribute on page load
- Flag now only controls UI state (button appearance), not redistribution behavior
- Saved percentages are always respected regardless of flag value
- Redistribution only happens when user explicitly clicks "Even Distribution - All" button
- When user saves after redistribution, the evenly-distributed percentages are saved to database
- On next load, saved evenly-distributed percentages are loaded (no redistribution occurs)

**Behavior After Fix:**
- `even_distribution_all: true` means "user last used even distribution" (percentages were already evenly distributed when saved)
- On page load, saved percentages are always loaded and displayed (no redistribution)
- When position filters change and flag is `true`, percentages redistribute among new visible plays (intentional behavior)
- Flag controls UI state (button appearance) only - does not auto-redistribute on load

**Files Changed:**
- `FrontEnd/static/playbooks.js` (lines 469-503)

**Related Documentation:**
- `docs/To Do/play_percentage_persistence.md` - Complete analysis and fix documentation

---

### ✅ Fixed: Playbook Percentage Loading - State Sections Only Contained First N Plays (January 2026)

**Issue:** Some plays showed 0% even though they had saved percentages in the database. Specifically, plays that weren't in the first N plays (first 3 for set plays, first 4 for motion) didn't get their percentages loaded.

**Root Cause:**
- `initDefaults()` created state entries only for first N plays from API response (based on array index)
- `loadPlaybookPercentagesFromAPI()` iterated through `this.state.sections[sectionKey]` which only contained first N plays
- If a play wasn't in the first N plays (e.g., "SG Pass & Cut" at index 5), it wasn't in state sections, so its percentage couldn't be loaded
- Position filters could also cause visible plays to not be in state sections

**Fix (January 2026):**
- Modified `FrontEnd/static/playbooks.js` `loadPlaybookPercentagesFromAPI()` to iterate through **ALL plays** in `this.playData[settingsKey]`
- For each play, find or create the corresponding state entry (by playId)
- Apply saved percentage using `play.name` as key
- This ensures ALL plays from database are matched, not just the first N that were initialized in state

**Matching Strategy:**
- **Database/API Storage:** Uses **play names** as keys (`{"Base Post Play": 50, "SG Pass & Cut": 50}`)
- **Frontend State:** Uses **generated IDs** like `set-inside-1`, `set-inside-2` based on array index
- **Matching Process:**
  1. Iterate through ALL plays in `playData` (not just state sections)
  2. For each play, find or create state entry by `playId`
  3. Look up saved percentage using `play.name` as key
  4. Apply percentage to state entry

**Files Changed:**
- `FrontEnd/static/playbooks.js` (lines 505-622)

**Related Documentation:**
- `docs/To Do/play_percentage_persistence.md` - Complete analysis and fix documentation

**Future Enhancement:**
- Consider using `play_id` (database ID) instead of play names for more robust matching
- This would prevent issues if play names change in database

