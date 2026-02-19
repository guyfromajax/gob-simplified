# Data Persistence System ✅ **COMPLETE** (January 2025)

**Status:** All major refactoring complete (January 2026)  
**Related:** See `Unified_State_Persistence_Work_Plan.md` for complete implementation history and all phases (1.1-1.3, 2, 3, 4, 5.1-5.7)

---

## Base Constants

**Purpose:** Documents what data is persisted in each game mode when the user is in non-gameplay situations (Command Center, Game Plan, Playbooks, Training, Training Report). Critical for understanding what state needs to be maintained across navigation transitions.

**Collections:**
- `franchises` - Franchise mode documents
- `tournaments` - Tournament mode documents
- `games` - Single Game mode documents, game documents in franchise or tournament mode
- `teams` - Universal team collection (source of truth for initial values)
- `players` - Universal player collection (baseline attributes)

**Common Data Fields (All Modes):**
- Team attributes: `shot_threshold`, `discipline`, `fight`, `rebound_modifier`, `offensive_efficiency`, `team_chemistry`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`
- Strategy settings: `{offense, inside, attack, outside, tempo, defense, aggression, hc_trap, fc_press, rebounding}` (0-4)
- Playbook settings: `{motion, set_play_inside, set_play_attack, set_play_outside, zone_defense, man_defense, slot_assignments, motion_dropdowns, position_filters}`
- Plays data: `{[playName]: {effectiveness, momentum, cloaking, game_stats, season_stats}}`
- Scouting data: `{defense: {Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone, vs_Fast_Break, FCP, HCT: {effectiveness, momentum, cloaking, game_stats, season_stats}}}`

## System Flow

1. **Franchise Mode**: Team data stored in `franchise_team_data` (FTD) collection; player data in `franchise_players_data`. Franchise doc no longer uses `franchise_teams` (deprecated).
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

#### B. Team Objects (FTD: `franchise_team_data` collection)

**For each of the 8 teams in the franchise**, team-level data (attributes, settings, plays, scouting) is stored in the `franchise_team_data` collection, keyed by `(franchise_id, team_id)`. The franchise document no longer stores `franchise_teams` (deprecated).

**Team Attributes** (mode-specific, randomized on init, updated by training):
- `team_chemistry`: 7-10 (franchise mode range)
- `offensive_efficiency`: -1 to +1
- `shot_threshold`: -10 to 190 (randomized, center at 90 for pill display)
- `discipline`: -1 to +1 (formerly `turnover_modifier`)
- `fight`: -1 to +1 (formerly `foul_modifier`)
- `rebound_modifier`: 0.2 (fixed center value for Franchise mode)
- `defensive_efficiency`: -1 to +1
- `fb_efficiency`: -1 to +1
- `pt_efficiency`: -1 to +1
- `fb_opp_modifier`: -1 to +1
- `pt_opp_modifier`: -1 to +1

**Strategy Settings & Playbook Settings:**
- See "Game Plan & Playbook Settings Persistence" section below for complete documentation

**Plays Data** (updated by training):
- `plays`: Object with play data including `effectiveness`, `momentum`, `cloaking` (0-100, 0-10, 0-10), `game_stats`, `season_stats`

**Scouting Data** (updated by training):
- `scouting_data`: Defense structures (Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone, vs_Fast_Break, FCP, HCT) with `effectiveness`, `momentum`, `cloaking`, `game_stats`, `season_stats`

**Legacy playcall_settings** (still present for backward compatibility)

**Initialization:** Team objects are created for all 8 teams when franchise is initialized via `FranchiseManager.initialize_season()` or lazily via `ensure_team_objects_exist()` when accessing Game Plan/Playbooks.

#### C. Player Objects (`players.{player_id}`)

**For each player in the franchise:**

- **Player Metadata** (`meta`: first_name, last_name, team, team_id)
- **Evolved Attributes** (`attributes`: all 30+ attributes with `anchor_` prefixed versions, updated by training)
- **Evolved Position Ratings** (`position_ratings`: PG, SG, SF, PF, C ratings, updated by training)
- **Statistics** (`season`: season stats, `career`: career stats)

**Note:** Player attributes from training are loaded during game initialization. See `Franchise_Mode_Systems.md` section "3.5. Player Attribute Loading During Game Initialization" for complete details.

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

**Strategy Settings & Playbook Settings:**
- See "Game Plan & Playbook Settings Persistence" section below for complete documentation

**Plays Data** (updated by training):
- `plays`: Object with play data including `effectiveness`, `momentum`, `cloaking` (0-80 randomized on init, 0-10, 0-10), `game_stats`, `season_stats`

**Scouting Data** (updated by training):
- `scouting_data`: Defense structures (Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone, vs_Fast_Break, FCP, HCT) with `effectiveness`, `momentum`, `cloaking` (0-80 randomized on init, 0-10, 0-10), `game_stats`, `season_stats`

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

**Strategy Settings & Playbook Settings:**
- See "Game Plan & Playbook Settings Persistence" section below for complete documentation

**Plays Data** (loaded from universal collection, NOT updated):
- `plays`: Object with play data from universal `plays` collection

**Scouting Data** (loaded from universal collection, NOT updated):
- `scouting_data`: Defense structures from universal collection

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

**Note:** All major persistence issues have been resolved through the Unified State Persistence refactoring (Phases 1-5.7) and the single-source-of-truth simplification (February 2026). The fixes documented below are historical and have been integrated into the current system. For complete implementation history, see `Unified_State_Persistence_Work_Plan.md`.

### ✅ Fixed: Single Source of Truth for Franchise/Tournament Game Plan & Playbooks (February 2026)

**Issue:** In franchise and tournament mode, game plan and playbook settings could appear to be "lost" when returning to the lineup screen after a timeout or when navigating during gameplay. Persistence worked before the game but not consistently during the game.

**Root Cause:** Settings were sometimes read from or written to the game document and sometimes to the master store (FTD or tournament doc). When the backend chose the wrong source (e.g. read from master after writing to game doc, or overwrite in-memory state from game doc), the UI showed stale or empty settings.

**Fix:** Franchise and tournament now use a **single source of truth** for game plan and playbook settings. Settings are **always** read from and written to the master store (FTD for franchise, tournament document for tournament). The game document is not used for these settings in franchise or tournament mode. Implementation: (1) `get_save_location_for_franchise_tournament()` always returns `is_game_doc = False` for franchise and tournament. (2) GET gameplan and GET playbooks never set `load_from_game_doc = True` for franchise or tournament, so they always load from FTD or tournament doc. (3) **Follow-up (February 2026):** Tournament save in `team_settings_manager.py` was updated to resolve the authoritative `user_team_object_id` from the tournament document (same as franchise uses from franchise doc); request `team_id` is ignored for tournament master save. This ensures save and load use the same key (`teams.{user_team_object_id}`) and fixes tournament settings not persisting from TCC or in-game.

**Files Changed:** `BackEnd/api/gameplan_routes.py` (get_save_location_for_franchise_tournament, get_gameplan, get_playbooks); `BackEnd/utils/team_settings_manager.py` (tournament master save uses authoritative user_team_object_id)

### ✅ Fixed: Franchise EOG Reading Wrong Game Snapshot (February 2026)

**Issue:** End-of-game team attribute calculations intermittently used zero totals/scouting even when box score showed real stats.

**Root Cause:**
- Franchise completion flow could touch game docs using different `_id` types (string vs `ObjectId`).
- In some cases this produced a partial duplicate doc (metadata only) and EOG read that doc instead of the canonical gameplay snapshot.

**Fix:**
- In `complete_week`, when `game_document` is provided, persist that snapshot before finalization/EOG.
- In `_save_game_result`, prefer string `_id` and only use `ObjectId` if an existing ObjectId doc already exists.
- In `update_team_attributes_after_game`, evaluate both `_id` candidates and use the richer doc for EOG input generation.

**Operational Check:**
- Railway logs should show:
  - `🧭 [EOG-GAME-DOC-SELECT] ...`
  - `🧪 [EOG-SNAPSHOT-SOURCES]` with `teams.totals` or `teams.box_score` (not `none`) for completed games.

### ✅ Fixed: In-Game Game Plan/Playbook Save Not Persisting (February 15, 2026)

**Issue:** Game Plan and Playbook settings changed during gameplay (e.g. from lineup or timeout) did not persist in Franchise or Tournament mode. Save returned 200 but reopening the page showed previous/default values.

**Root Cause:**
- `init-game` creates game documents with `_id` stored as a **string** (24-char hex from `generate_game_id()`); it uses `update_one({"_id": game_id}, ..., upsert=True)` with string `game_id`.
- `save_team_settings()` when saving to the game doc was querying with **ObjectId** only (`_id: ObjectId(doc_id)`). In MongoDB, `_id: "69921c08..."` (string) does not match `_id: ObjectId("69921c08...")`, so `update_one` matched 0 documents and no write occurred.

**Fix:**
- In `BackEnd/utils/team_settings_manager.py`, when saving to a game doc (franchise or tournament), try `update_one({"_id": doc_id}, ...)` (string) first. If `matched_count == 0` and `doc_id` is 24-char hex, retry with `update_one({"_id": ObjectId(doc_id)}, ...)`. This works whether the game doc was stored with string or ObjectId `_id`.

**See also:** Game Plan & Playbook Settings Persistence → Key Implementation Details (“Game document `_id` when saving to game doc”).

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

---

## Game Plan & Playbook Settings Persistence ✅ **COMPLETE** (January 2026, simplified February 2026)

### Overview

Game Plan (`strategy_settings`) and Playbook (`playbook_settings`) settings use a unified persistence system. **Franchise and Tournament use a single source of truth:** settings are always read from and written to the master store (FTD for franchise, tournament document for tournament). The game document is **not** used for these settings in franchise or tournament mode—neither before the game nor during gameplay (lineup, timeout, in-game). This eliminates sync bugs and "lost on comeback" issues.

**Franchise:** All strategy/playbook settings live in the `franchise_team_data` (FTD) collection, keyed by `(franchise_id, user_team_object_id)`. Save uses **upsert** so the first save creates the FTD doc if missing. **FCC / pre-game save:** `save_team_settings()` uses **authoritative** `user_team_object_id` from the franchise document; request `team_id` is ignored. Load (GET gameplan, GET playbooks, init-game, simulate-quarter) always reads from FTD for franchise—never from the game document.

**Tournament:** All strategy/playbook settings live in the tournament document → `teams.{team_id}.{settings_type}`. Save and load always use the tournament document—never the game document.

**Single Game Mode:** Settings are stored in and read from the game document only (no master doc).

### Unified Functions

**Core Functions (`BackEnd/utils/team_settings_manager.py`):**

1. **`save_team_settings()`** - Unified save function for both settings types
   - Handles team ID resolution to canonical format
   - Determines save location (game doc vs master doc) using Phase 5.7 logic
   - Updates database with correct team_id keys
   - Optionally applies settings to cached GameManager instance

2. **`extract_team_settings()`** - Unified extract function for both settings types
   - Resolves team identifier to correct format for lookup
   - Extracts settings from saved document using consistent key matching
   - Handles both ObjectId keys (master docs) and canonical keys (game docs)

3. **`load_and_apply_team_settings_to_gamemanager()`** - Unified load and apply function
   - Loads both settings from DB/request
   - Applies to GameManager consistently
   - Handles request overrides (if user visited respective page)

### Save Location Logic (Phase 5.7, simplified February 2026)

**Determined by `get_save_location_for_franchise_tournament()`:**

**Franchise and Tournament (single source of truth):**
- **Always save to master store.** `get_save_location_for_franchise_tournament()` always returns `is_game_doc = False` for franchise and tournament, regardless of whether a game is in progress. No branching on `game_id`.
  - **Franchise:** `franchise_team_data` collection (FTD). One doc per `(franchise_id, team_id)`. Settings stored as `strategy_settings` / `playbook_settings` top-level fields. Save uses **upsert**: if no FTD doc exists, one is created on first save.
  - **Tournament:** `tournaments` document → `teams.{team_id}.{settings_type}`
- **Team ID Format:** ObjectId string (e.g., `"68c98b08674d3f9b04546b2f"`). Franchise FTD and tournament `teams` use ObjectId strings as keys (from `user_team_object_id`).
- **Read path:** GET gameplan and GET playbooks never load from the game document for franchise/tournament; they always load from FTD (franchise) or tournament doc (tournament). So in-game changes persist because they are written to and read from the same master store.

**Single Game Mode:**
- Always saves to and loads from the game document (no master doc).
- Uses canonical team_id format.

### Team ID Resolution

**Critical Rule:** Different document types use different team_id formats:

1. **Master store (Franchise / Tournament):**
   - **Franchise:** FTD collection, keyed by `(franchise_id, team_id)` with ObjectIds. `team_id` = `user_team_object_id`.
   - **Tournament:** `teams` on tournament document; keys = ObjectId strings (e.g. `"68c98b08674d3f9b04546b2f"`).
   - Source: `user_team_object_id` from franchise/tournament document.
   - **Save:** Use ObjectId string directly (no normalization). **Franchise:** resolve `team_id` from franchise doc (`user_team_object_id`); request `team_id` ignored. FTD upsert. **Tournament:** resolve `team_id` from tournament doc (`user_team_object_id`); request `team_id` ignored. Both use the same key for save and load.
   - **Load:** Franchise → FTD lookup by `(franchise_id, user_team_object_id)`; tournament → `extract_team_settings` on doc.

2. **Game Documents (All Modes):**
   - Keys: Canonical format (e.g., `"FOUR_CORNERS"`, `"MORRISTOWN"`)
   - Source: Resolved from team names or ObjectIds via `normalize_team_id_to_canonical()`
   - **Save:** Normalize to canonical format
   - **Load:** Resolve to canonical format for lookup

**Why This Matters:**
- Mismatched keys cause settings to be saved to one key but loaded from another
- This was the root cause of persistence bugs in TCC/FCC
- Unified functions ensure consistent key resolution

**Command Center (FCC) data wiring:**
- **Franchise-level data** (Standings, Schedule, Leaders, Team Stats, Team Traits, Recruits): use **`franchise_id`** only in request URLs.
- **User's team–scoped data** (Team tab, roster, Training link, Game Plan link): use **`team_id`** (the user's team ObjectId string, e.g. `userTeamId`) as the canonical key. Do **not** wire by team name.
- **Team tab:** `/franchise/team-data?franchise_id=...&team_id=...`; roster for top-scorer lookup: `/roster/{team_id}?franchise_id=...`. Both use the same `team_id` from URL or command-center/data.
- **Backend:** `/roster/{team_identifier}` and `/franchise/team-data` accept `team_id` (path or query); roster supports ObjectId string in path. This keeps FCC aligned with FTD keying by `(franchise_id, team_id)`.

**FCC Play Next Game → set-lineup URL ("your team" resolution):**
- Same approach as tournament: **do not** rely on `localStorage` `franchise_user_team` for building the set-lineup URL. Use **API-sourced** user team first, then **id-derived** fallback.
- **Resolution order** (in `franchise-command-center.js` Play Next Game handler): (1) Compare API-sourced team name (`userTeamNameForLeaders` from `topData.team`) to play-next-game response `home`/`away` → set `my_team` to `'home'` or `'away'`. (2) If no match, derive from `userTeamId` vs `home_id`/`away_id` (String comparison). (3) Append `team_id` and `my_team` to the set-lineup URL when present.
- **Set-lineup contract:** Set-lineup expects **`my_team`** (home/away) or **`user_team_id`** to resolve "your team"; it does not read `team_id`. So FCC must send `my_team` (and optionally `team_id`) for the lineup screen to load correctly.

### Complete Flow

#### 1. Pre-Game (FCC/TCC)

**User Flow:**
1. User accesses Game Plan/Playbooks from FCC or TCC
2. User changes settings and clicks "Save"
3. Settings saved to master document (franchise/tournament doc)
4. User navigates away and returns
5. Settings loaded from master document (persist correctly)

**Backend Flow:**
- `save_team_settings()` called with `game_id=None` or game not active
- `get_save_location_for_franchise_tournament()` returns master (franchise → FTD, tournament → tournament doc)
- **Franchise:** Team ID resolved from franchise doc (`user_team_object_id`); request `team_id` ignored. Settings saved to `franchise_team_data` via `update_one(..., upsert=True)`. First save creates FTD doc if missing.
- **Tournament:** Team ID resolved from tournament doc (`user_team_object_id`); request `team_id` ignored. Settings saved to `teams.{user_team_object_id}.{settings_type}` in tournament document.
- **Load:** Franchise master settings loaded from FTD (`load_team_settings_from_doc()` queries FTD by `franchise_id` + `user_team_object_id`). Tournament uses `extract_team_settings()` on tournament doc.

#### 2. Game Start

**User Flow:**
1. User starts new game in franchise/tournament mode
2. Settings are read from master (FTD or tournament doc) when needed (e.g. init-game, simulate-quarter)
3. Game begins with master settings as starting point

**Backend Flow:**
- **Franchise/Tournament:** Settings are always loaded from the master store (FTD or tournament doc). Init-game and simulate-quarter read from FTD/tournament doc. No copy of settings is stored in the game document for franchise/tournament.
- **Single Game:** Settings are copied from or stored in the game document as before.

#### 3. During Active Gameplay (Franchise/Tournament)

**User Flow:**
1. User changes settings during game (e.g. from lineup or timeout)
2. Settings saved to master store (FTD or tournament doc)—same as pre-game
3. Settings persist through timeout/quarter breaks because they are always read from the same master store

**Backend Flow:**
- `save_team_settings()` called with `game_id` (e.g. from lineup or in-game). For franchise/tournament, `get_save_location_for_franchise_tournament()` always returns master (FTD or tournament doc), so settings are written there.
- No game-document write for game plan/playbooks in franchise or tournament mode.

#### 4. Timeout Resume (Franchise/Tournament)

**User Flow:**
1. User calls timeout during game
2. User navigates to Game Plan/Playbooks (or changes 6 presets in Playcall Center on court)
3. Settings loaded from master store (FTD or tournament doc)—same source as before and during game
4. User makes changes (or keeps current)
5. Settings saved to master store (if changed)
6. User returns to game
7. Settings persist correctly (single source of truth)

**Backend Flow:**
- GET gameplan and GET playbooks never load from the game document for franchise/tournament; they always load from FTD or tournament doc. So the lineup screen and Game Plan/Playbooks pages always show and save to the same store.
- `load_and_apply_team_settings_to_gamemanager()` and simulate-quarter load settings from the same master store when building game state.
- **Single Game:** Settings may still be read from the game document when `game_id` is present; behavior unchanged.

**Playcall Center (court) and the 6 presets:**  
When the user changes one of the 6 preset plays in the Playcall Center during a timeout, the court must **also** call **POST /api/playbooks** with the updated `slot_assignments` (and `game_id`, `franchise_id`/`tournament_id`, etc.). If the court only calls `/api/set-playcall-override`, that sets the *next play* override in memory but does **not** persist slot_assignments. POST /api/playbooks writes to the correct store (FTD for franchise, tournament doc for tournament, game doc for single) so GET /api/playbooks returns the updated presets on reopen.

### Key Implementation Details

**Unified Save Function:**
```python
# Franchise/tournament: always master (FTD or tournament doc); single: game doc
if mode in ["franchise", "tournament"]:
    collection, doc_id, is_game_doc = get_save_location_for_franchise_tournament(...)
    # is_game_doc is always False for franchise/tournament (single source of truth)
    actual_team_id = team_id  # Master doc - use ObjectId string (Franchise: resolved from franchise doc)
elif mode == "single" and game_id:
    actual_team_id = normalize_team_id_to_canonical(team_id, mode, None)
```

**Game document `_id` when saving to game doc (Single Game only):**  
Franchise and tournament no longer write game plan/playbooks to the game doc. For **single game mode**, game documents are created by `init-game` with `_id` set to a **string** (24-char hex from `generate_game_id()`). When `save_team_settings()` writes to a game doc (single mode), it must try `_id` as **string** first (`update_one({"_id": doc_id}, ...)`). If no document is matched and `doc_id` is 24-char hex, retry with `ObjectId(doc_id)`. This ensures the update finds the document regardless of whether it was stored with string or ObjectId `_id`.

**Unified Extract Function:**
- **Tournament / game docs:** `extract_team_settings()` uses `teams` (or `franchise_teams` for legacy paths). Resolves team_identifier; tries direct lookup, then name matching.
- **Franchise master (pre-game):** Settings are **not** read from `franchise_teams` (now empty post-FTD migration). `load_team_settings_from_doc()` loads directly from **FTD** by `(franchise_id, user_team_object_id)` and returns `strategy_settings` / `playbook_settings`. Used by init-game, simulate-quarter, and other master-doc load paths.

**Unified Load Function:**
```python
# Loads both settings from DB/request
home_strategy_db = extract_team_settings(saved_doc, home_team_name, "strategy_settings", mode, game_doc)
home_playbook_db = extract_team_settings(saved_doc, home_team_name, "playbook_settings", mode, game_doc)

# Override with request if valid (user visited page)
if request_strategy_settings and is_valid(request_strategy_settings):
    home_strategy = request_strategy_settings
else:
    home_strategy = home_strategy_db

# Apply to GameManager
if gm:
    gm.home_team.strategy_settings = home_strategy
    gm.home_team.playbook_settings = home_playbook
```

### Benefits

1. **Single Source of Truth (Franchise/Tournament):** Game plan and playbooks always read from and written to FTD (franchise) or tournament doc (tournament). No game document for these settings—eliminates sync bugs and "lost on comeback" when returning to lineup after timeout.
2. **Consistency:** Same save/load logic across all modes and contexts
3. **Correct Key Resolution:** Handles ObjectId vs canonical format correctly
4. **Timeout Persistence:** Settings persist through timeout navigation because the same store is used before, during, and after the game
5. **Unified Functions:** `save_team_settings()`, `get_save_location_for_franchise_tournament()`, and GET endpoints enforce the single source

### Key Files

**Backend:**
- `BackEnd/utils/team_settings_manager.py`: Unified save/extract/load. Franchise master save writes to FTD with **upsert**. Tournament master save resolves authoritative `user_team_object_id` from tournament doc (same key as load).
- `BackEnd/api/gameplan_routes.py`: `get_save_location_for_franchise_tournament()`, `normalize_team_id_to_canonical()`
- `BackEnd/api/gameplan_routes.py`: `save_playbooks()`, `update_gameplan()` endpoints (use `save_team_settings`)
- `BackEnd/api/api.py`: `simulate_quarter_endpoint()` (uses unified load), `load_team_settings_from_doc()` (franchise master → FTD, tournament → extract)

**Frontend:**
- `FrontEnd/static/game-plan.js`: Sends settings in save request
- `FrontEnd/static/playbooks.js`: Sends settings in save request
- `FrontEnd/static/js/phaser/bootGame.js`: Loads settings before game start
- `FrontEnd/static/js/phaser/gameScene.js`: Sends settings in simulate-quarter request

### Related Documentation

- `docs/docs_1_systems/05_GP_Supporting_Systems/Timeout_System.md` - Timeout settings persistence
- `docs/docs_1_systems/03_Data_Persistence/Unified_State_Persistence_Work_Plan.md` - Complete implementation history

---

## In-Game Data Persistence (Hybrid Approach) ✅ **COMPLETE** (January 2025)

### Overview

During active gameplay, game state (scores, clock, quarter, fouls, timeouts, lineups) must be persisted and retrieved consistently. The system uses a **hybrid approach** that balances performance (cache for gameplay) with consistency (database for critical reads).

### Strategy: Cache for Performance, Database for Consistency

**Problem:** Using database as single source of truth for every read would be too expensive (hundreds of DB calls per game). But using only in-memory cache can lead to stale state bugs.

**Solution:** Hybrid approach with clear rules:

1. **During Active Gameplay:** Use `ongoing_games` in-memory cache (fast, many calls)
2. **After State Changes:** Refresh cache from database (timeout saves, quarter breaks)
3. **For Lineup Screen:** Always read from database (infrequent, ~13 reads per game)

### Performance Characteristics

**Cache Usage (Active Gameplay):**
- Turn-by-turn simulation: Uses `ongoing_games` cache
- Many calls per game (hundreds of turn simulations)
- Fast response times (no DB queries)

**Database Usage (Critical Reads):**
- Timeout saves: ~8 reads per game (user + computer timeouts)
- Quarter breaks: ~4 reads per game (Q2, Q3, Q4, OT)
- Lineup screen loads: ~13 reads per game total
- Acceptable performance cost for consistency

### Implementation Details

#### 1. Cache Refresh After State Changes

After any state change (timeout save, quarter break), the `ongoing_games` cache is refreshed from the database:

```python
# After saving timeout state to DB
games_collection.update_one({"_id": game_id}, {"$set": db_summary}, upsert=True)

# Refresh cache from DB
if game_id in ongoing_games and saved_doc:
    refresh_game_cache_from_db(ongoing_games[game_id], saved_doc)
```

**Function:** `refresh_game_cache_from_db(gm, saved)`
- Updates critical game state in existing GameManager instance
- Updates: scores, clock, time_remaining, quarter, fouls, timeouts, timeout state
- Ensures cache matches database after state changes

#### 2. Database Reads for Lineup Screen

The `/api/game/{game_id}` endpoint supports a `source` parameter:

- `source=db`: Always reads from database (for lineup screen consistency)
- `source=cache` or omitted: Uses `ongoing_games` cache if available (for gameplay performance)

**Frontend Usage:**
```javascript
// Lineup screen always uses source=db for fresh data
const gameRes = await fetch(`/api/game/${gameId}?quarter=1&source=db`);
```

**Lineup header during timeout resume:** The lineup page header (time remaining and score) must show the state at the moment the user entered the timeout. **Clock** is read from the **URL** when `resume_from_timeout=true` (timeout navigation puts the displayed clock in the URL). **Scores** are read from the URL when `home_score`/`away_score` are present (same rationale as clock); otherwise scores are loaded from the API with `source=db`. Quarter breaks force clock to 8:00 or 4:00 (OT) and do not use URL clock.

**Court display on return (timeout / quarter break / foul-out):** When the user returns to court with an existing `game_id`, the scoreboard (scores, clock, TOL, fouls) and the Player and Team box scores must show current game state, not stale start-of-quarter data. Scoreboard immediacy and the force-update of Player and Team box scores from `GET /api/game/{game_id}` are documented in **`docs/docs_1_systems/05_GP_Supporting_Systems/Timeout_System.md`** — see “Scoreboard Display Immediacy System” and “Player and Team Box Score Force-Update on Resume”.

**Backend Implementation:**
```python
@app.get("/api/game/{game_id}")
def get_game_state(game_id: str, quarter: int | None = None, source: str | None = None):
    force_db_read = source == "db"
    
    # Skip cache if forcing DB read
    if not force_db_read:
        gm = ongoing_games.get(game_id)
        if gm:
            return response_from_cache(gm)
    
    # Always read from DB if source=db or cache miss
    saved = games_collection.find_one({"_id": game_id})
    return response_from_db(saved)
```

#### 3. State Changes That Trigger Cache Refresh

**Timeout Saves:**
- User timeout: `/api/call-timeout` → Save to DB → Refresh cache
- Computer timeout: `/api/simulate-turn` → Save to DB → Refresh cache

**Quarter Breaks:**
- Quarter completion: Save to DB → Refresh cache (if game still in memory)

**Other State Changes:**
- Score changes: Saved to DB during turn completion
- Foul/timeout changes: Saved to DB during turn completion
- Cache refreshed after timeout saves (most critical for consistency)

### Player Energy (NG) Persistence ✅ **FIXED** (January 2025)

**Problem:** After timeouts and quarter breaks, player energy (NG) values were displaying as 100% on the lineup screen and initial court.html load, even though backend maintained correct values.

**Root Causes:**
1. `summarize_game_state()` only saved lineup players, not bench players, causing bench players to default to 1.0 NG when loading from DB
2. `/api/game/{game_id}` DB read path was checking top-level `NG` first (which doesn't exist), then defaulting to 1.0 before checking `attributes.NG`

**Solution:**
1. **Save All Players:** Modified `summarize_game_state()` to save ALL players (lineup + bench) using `team.get_all_players()`, ensuring all players' real-time NG values are persisted
2. **Correct NG Extraction:** Modified `/api/game/{game_id}` DB read path to extract NG from `attributes.NG` first (where it's saved), with fallback to top-level `NG`, then default to 1.0

**Key Points:**
- NG values in saved documents are **real-time** values from in-memory Player objects at the moment of save (timeout/quarter break)
- All players (lineup + bench) are saved to ensure complete energy state
- Frontend correctly reads NG from `attributes.NG` with proper fallback chain

**Files Changed:**
- `BackEnd/utils/shared.py` - `summarize_game_state()` (lines 745-768): Save all players, not just lineup
- `BackEnd/api/api.py` - `get_game_state()` (lines 1097-1120): Extract NG from `attributes.NG` correctly

### Playbook Settings Persistence ✅ **FIXED** (February 2025; franchise/tournament simplified February 2026)

**Note (February 2026):** In franchise and tournament mode, playbook (and game plan) settings are no longer stored in the game document. They are always read from and written to the master store (FTD or tournament doc). The fix below applies to **single game mode** and to the historical behavior when franchise/tournament used the game doc.

**Problem:** Playbook settings were not persisting through timeouts. When users navigated to the Playbooks page during timeout, settings were missing or incorrect, even though they were saved correctly during the timeout.

**Root Cause:**
- `summarize_game_state()` correctly preserved `playbook_settings` from the game document when saving timeout state
- However, when loading the game from the database after timeout, `playbook_settings` were extracted from the saved document but never explicitly restored back to the game document
- Additionally, team_id key resolution was inconsistent between save and restore, causing settings to be restored to wrong keys
- The Playbooks page loads settings from the game document (single mode) or from FTD/tournament doc (franchise/tournament), so missing/incorrectly-keyed settings caused the bug in single mode

**Solution:**
- Added explicit restoration of `playbook_settings` to the game document after GameManager creation
- **Consistent Key Resolution:** Uses same team name matching logic as `summarize_game_state()` to ensure consistent team_id keys between save and restore
- Settings are extracted from the saved document and written back using `games_collection.update_one()` with the correctly-resolved team keys
- Added detailed logging to trace playbook_settings save/restore for debugging

**Key Points:**
- **Single game:** `playbook_settings` are stored in the game document (`teams.{team_id}.playbook_settings`). Settings must be explicitly restored to the game document after loading when using the game doc. **Franchise/tournament:** Settings are in FTD or tournament doc only; GET playbooks loads from there, so no game-doc restore is needed.
- Team_id key resolution uses: name match → direct team_id lookup → saved document home_team_id/away_team_id → GameManager team_id
- `strategy_settings` (Game Plan settings) are validated before use - only uses request if valid, otherwise preserves DB settings

**Files Changed:**
- `BackEnd/api/api.py` - `simulate_quarter_endpoint()` (lines 1824-1847): Restore playbook_settings with consistent key resolution
- `BackEnd/utils/shared.py` - `summarize_game_state()` (lines 971-974): Enhanced logging for playbook_settings save

### Game Plan Settings Persistence ✅ **FIXED** (February 2025; franchise/tournament simplified February 2026)

**Note (February 2026):** In franchise and tournament mode, game plan (and playbook) settings are always loaded from the master store (FTD or tournament doc), not from the game document. The fix below applies to **single game mode** and to request-vs-DB prioritization when loading from the game doc.

**Problem:** Game plan settings (strategy_settings) were not persisting through timeouts when users didn't visit the Game Plan page during timeout navigation.

**Root Cause:**
- When loading game from database after timeout, code always prioritized `request.strategy_settings` over DB settings
- If user didn't visit Game Plan page, `request.strategy_settings` could be stale/empty/invalid
- This caused correct DB settings to be overwritten with invalid request settings

**Solution:**
- Added validation to check if `request.strategy_settings` has all required keys (valid settings)
- Only uses `request.strategy_settings` if it's valid (indicates user visited Game Plan page and settings are current)
- If `request.strategy_settings` is invalid/missing, preserves DB settings instead
- This ensures settings persist through timeout even if user doesn't visit Game Plan page

**Key Points:**
- **Single game:** `strategy_settings` are stored in the game document (`teams.{team_id}.strategy_settings`) and on GameManager objects. **Franchise/tournament:** Settings are in FTD or tournament doc only; GET gameplan loads from there.
- Settings are preserved from GameManager objects when timeout is called via `summarize_game_state()` (single mode / game doc path)
- Request settings are only used if valid (has all required keys), otherwise DB settings are preserved
- Added logging to trace strategy_settings extraction and validation

**Files Changed:**
- `BackEnd/api/api.py` - `simulate_quarter_endpoint()` (lines 1573-1611): Validate request.strategy_settings before use

### Computer Timeout Per-Quarter Tracking Persistence ✅ **COMPLETE** (February 2025)

**Purpose:** Enforce "max 1 computer timeout per quarter" in Q1–Q3 after any load from DB (e.g. returning from timeout or lineup screen). Without persistence, the per-quarter count lived only in memory and was lost on reload, allowing the computer to call multiple timeouts in the same quarter.

**Solution:**
- `computer_timeouts` (per-team, per-quarter `count` and `checked_conditions`) is persisted to the game document on every save via `summarize_game_state()`. `checked_conditions` sets are serialized to lists for JSON/DB.
- Restored when loading from DB in `apply_timeout_resume_state_to_gm()` (timeout resume path) and in the simulate-quarter load path so the limit is enforced after any DB load.
- Source of truth for persisted values is the database; in-memory `game_state["computer_timeouts"]` is repopulated from the saved document on load.

**Key Points:**
- Serialize/deserialize helpers live in `BackEnd/utils/shared.py` (`serialize_computer_timeouts`, `deserialize_computer_timeouts`).
- Team-level "timeouts remaining" (TOL on scoreboard) was already persisted in the teams structure; this addition persists only the **per-quarter usage** used to enforce the max-per-quarter rule.

**Files:**
- `BackEnd/utils/shared.py` - `serialize_computer_timeouts()`, `deserialize_computer_timeouts()`, and `summarize_game_state()` (persists `computer_timeouts`)
- `BackEnd/api/api.py` - `apply_timeout_resume_state_to_gm()` and simulate-quarter load path (restore `computer_timeouts` from saved doc)

**Full system (limits, conditions, flow):** `docs/docs_1_systems/05_GP_Supporting_Systems/Computer_Timeout_System.md`

### Mixed Sim→Play Quarter Restore (Unified Teams) ✅ **FIXED** (February 2026)

**Problem:** In mixed gameplay flows (simulate Q1–Q3, then play Q4), box score/team totals could appear mostly zero after loading from DB.

**Root Cause:**
- `simulate_quarter_endpoint()` restored team-level cumulative stats (score, team fouls, timeouts, totals, points-by-quarter) from legacy `home_team` / `away_team` fields.
- Current saved game format stores authoritative team state in unified `teams.{team_id}` structure.
- When legacy fields were absent, restore skipped cumulative values and produced partial/zeroed box score context.

**Solution:**
- Updated the DB restore path to prefer unified `teams[home_team_id]` / `teams[away_team_id]`.
- Kept backward compatibility fallback to legacy `home_team` / `away_team` only when unified team records are unavailable.

**Files Changed:**
- `BackEnd/api/api.py` - simulate-quarter DB restore block for team-level cumulative stats
- `tests/test_simulate_quarter_endpoint.py` - added focused regression test:
  - `test_simulate_quarter_restores_team_stats_from_unified_teams`

### EOG Canonical Snapshot Persistence ✅ **FIXED** (February 2026)

**Problem:** EOG team-attribute deltas could drift from expected PT/FB results due to mixed reads across `team_stats`, `teams.scouting`, and totals paths.

**Solution:**
- Added a single canonical `eog_inputs` snapshot on each finalized game document.
- Snapshot is built once from:
  - `teams[team_id].scouting` for FB/PT special-situations
  - `team_totals` (fallback: aggregated `box_score`) for totals-based metrics
- `update_team_attributes_after_game()` now computes EOG attribute changes from `eog_inputs` only.

**Files Changed:**
- `BackEnd/eog_attr_rules.py` - `build_eog_inputs_from_game_doc(...)` canonical snapshot builder
- `BackEnd/api/franchise_routes.py` - persists `games.eog_inputs` and uses it as the sole EOG calculation source

### Quarter Scoring Canonical Sync ✅ **FIXED** (February 2026)

**Problem:** In some restore/finalization paths, quarter scores in postgame display could drift from final totals due to mixed reads between runtime team arrays and `game_state` mirrors.

**Solution:**
- Canonical runtime quarter scoring is `team.points_by_quarter`.
- Every point write now updates both:
  - `team.points_by_quarter` (source of truth),
  - `game_state["points_by_quarter"]` (compatibility mirror).
- Persistence/summary prefers team runtime arrays, with mirror fallback only.

**Files Changed:**
- `BackEnd/utils/shared.py` - quarter scoring write + summary sourcing
- `BackEnd/api/api.py` - restore path writes to both runtime arrays and mirror
- `BackEnd/utils/game_summary_builder.py` - quarter arrays sourced from team runtime state

### Unified Foul-Out Timeout Persistence Path ✅ **FIXED** (February 2026)

**Problem:** Foul-out timeout creation previously had divergence risk from standard timeout creation/persistence flow.

**Solution:**
- Foul-out timeout now enters the same backend timeout pipeline as user/computer timeout:
  - `game_manager.call_timeout(...)`
  - `turn_manager.setup_timeout_turn(...)`
- This unifies timeout state fields and DB persistence behavior across timeout reasons.

**Files Changed:**
- `BackEnd/models/game_manager.py`

### Key Files

**Backend:**
- `BackEnd/api/api.py`:
  - `refresh_game_cache_from_db()` (lines 630-680): Refreshes cache from DB
  - `get_game_state()` (lines 823-1050): Supports `source=db` parameter, extracts NG from `attributes.NG`
  - `call_timeout_endpoint()` (lines 2825-2891): User timeout save + cache refresh
  - `simulate_turn_endpoint()` (lines 2390-2600): Computer timeout save + cache refresh
- `BackEnd/utils/shared.py`:
  - `summarize_game_state()` (lines 745-768): Saves all players (lineup + bench) with real-time NG values; persists `computer_timeouts` (per-quarter count + checked_conditions) for computer timeout limit enforcement
  - `serialize_computer_timeouts()` / `deserialize_computer_timeouts()`: DB-safe serialization for `computer_timeouts`

**Frontend:**
- `FrontEnd/static/set-lineup.js`:
  - `loadRoster()` (line 190): Uses `source=db` for player energy, reads from `attributes.NG`
  - `setHeader()`: During timeout resume, **clock** from URL (and **scores** from URL when `home_score`/`away_score` present); otherwise scores from API with `source=db`. Quarter breaks force clock to 8:00/4:00 (OT).

### Benefits

1. **Performance:** Active gameplay uses fast cache (hundreds of calls)
2. **Consistency:** Lineup screen always gets fresh data from database
3. **Low Overhead:** Only ~13 DB reads per game (timeouts + quarter breaks)
4. **Cache Freshness:** Cache refreshed after state changes prevents stale data

### Trade-offs

**Accepted Trade-offs:**
- Lineup screen DB reads are acceptable (~13 per game)
- Cache refresh after timeout saves adds minimal overhead
- Slight complexity in managing two sources (cache + DB)

**Avoided Trade-offs:**
- Not using DB for every read (would be too expensive)
- Not using only cache (would cause stale state bugs)
- Not refreshing cache (would cause inconsistency)

### Related Documentation

- `docs/docs_1_systems/05_GP_Supporting_Systems/Timeout_System.md` - Timeout state persistence
- `docs/docs_1_systems/05_GP_Supporting_Systems/Computer_Timeout_System.md` - Computer timeout flow
