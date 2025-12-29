# Master Documentation

> **Last Updated:** February 2025  
> **Purpose:** Comprehensive documentation of data persistence, key variables, and system architecture across all instance types

---

## Instance Types

1. **Non-Account (NA)** - User is not logged into an account
2. **General Account (GA)** - User is logged in but not in a specific game mode instance
3. **Game Mode Only (GMO)** - User is in a Tournament Mode or Franchise Mode instance, but not actively playing a game
4. **Gameplay (GP)** - User is actively playing a game (in gameplay experience)

---

## Non-Account (NA)

*[To be documented]*

---

## General Account (GA)

*[To be documented]*

---

## Game Mode Only (GMO)

**Definition:** User is in a Tournament Mode or Franchise Mode instance, but not actively playing a game.

**Sub-categories:**
- **GMO - Franchise Mode:** Franchise Command Center, Training, Playbooks, Game Plan, Team Roster, Standings/Stats
- **GMO - Tournament Mode:** Tournament Command Center, Training, Playbooks, Game Plan, Team Roster, Standings/Stats

**Examples:**
- Tournament/Franchise Command Center
- Training screen (before/after gameplay)
- Training Report screen
- Playbooks screen
- Game Plan screen
- Team Roster screen
- Standings/Stats screens

### GMO - Franchise Mode

#### Data Persistence

**Data Evolutions (All Teams):**
1. **Team Stats, Team Attributes**
   - Team Stats: Aggregation of player stats and play stats (Offense, Defense, Fast Break, Press Trap)
   - Team Attributes: `team_chemistry`, `offensive_efficiency`, `shot_threshold`, `turnover_modifier`, `foul_modifier`, `rebound_modifier`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`

2. **Player Stats, Player Attributes**
   - Player Stats: Season and career statistics (PTS, REB, AST, etc.)
   - Player Attributes: All 30+ attributes (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT, NG, EM, MO, CH, etc.) with `anchor_` prefixed versions
   - Position Ratings: PG, SG, SF, PF, C ratings

3. **Plays Data**
   - `plays[playName].effectiveness` (0-100) - Evolves via training and gameplay
   - `plays[playName].momentum` (0-10) - Evolves via training and gameplay
   - `plays[playName].cloaking` (0-10) - Evolves via training and gameplay
   - `plays[playName].game_stats` - Per-game statistics (times_run, shot_attempts, made_shots, turnovers, etc.)
   - `plays[playName].season_stats` - Cumulative season statistics

4. **Scouting Data**
   - `scouting_data.defense[defenseType].effectiveness` (0-100) - Evolves via training and gameplay
   - `scouting_data.defense[defenseType].momentum` (0-10) - Evolves via training and gameplay
   - `scouting_data.defense[defenseType].cloaking` (0-10) - Evolves via training and gameplay
   - `scouting_data.defense[defenseType].game_stats` - Per-game statistics
   - `scouting_data.defense[defenseType].season_stats` - Cumulative season statistics
   - Defense Types: Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone, vs_Fast_Break, FCP, HCT

5. **Training Reports (User Team Only)**
   - Stored in `franchise_teams.{user_team_id}.training_reports.{week}`
   - Also stored in `latest_training` at document level for quick access
   - Includes player changes, team changes, coaching focus, session type, week

#### Training System

**Location:** `BackEnd/models/training_execution_v2.py`

**Overview:**
The Training System applies training points to player attributes, team attributes, and plays/defenses based on user allocations. Training points are distributed across drills, and the system applies coaching focus amplifiers and generates training reports.

**Training Modes:**

1. **Current Playbooks Mode** (`playbook_training_mode: "current-playbooks"`)
   - Distributes training points only to plays currently in the user's playbook settings
   - Respects playbook percentages and slot assignments
   - Uses `strategy_settings['offense']` to determine motion vs set play split
   - **Requires:** `strategy_settings['offense']` must be set (not `None`)

2. **All Plays Even Distribution Mode** (`playbook_training_mode: "all-plays-even"`)
   - **✅ FIXED (February 2025):** Now distributes training points evenly across **ALL plays** (motion AND set plays)
   - **Previous Bug:** Only distributed to motion plays, completely ignoring set plays
   - **Fix Applied:** Removed `play_type == "motion"` filter, now includes all plays regardless of type
   - **Code Location:** `BackEnd/models/training_execution_v2.py` - `_apply_offense_play_training()` (lines 1335-1354)

3. **Custom Mode** (`playbook_training_mode: "custom"`)
   - User manually selects which plays receive training points
   - Uses custom play selection logic

**Critical Settings:**

- **`strategy_settings['offense']`** (Required for playbook-based training)
  - **What it does:** Determines the split between motion plays and set plays (0-4 scale)
  - **Where it lives:** `franchise_teams.{team_id}.strategy_settings.offense`
  - **Default Value:** `2` (balanced split)
  - **⚠️ CRITICAL:** If `None`, playbook-based training will fail
  - **✅ FIXED (February 2025):** `get_default_settings()` now includes `'offense'` with default value of `2`
  - **Code Location:** `BackEnd/api/gameplan_routes.py` - `get_default_settings()` (lines 77-96)

**Training Point Distribution Logic:**

```python
# ✅ CORRECT: "all-plays-even" includes ALL plays (motion + set plays)
if not use_playbooks or playbook_training_mode == "all-plays-even":
    all_plays = []
    for play_name, play_data in updated_plays.items():
        if isinstance(play_data, dict):  # No play_type filter!
            all_plays.append((play_name, play_data))
    
    # Distribute evenly across all plays
    points_per_play = total_points / len(all_plays) if all_plays else 0
```

**Previous Bug (Fixed February 2025):**

```python
# ❌ WRONG: Only included motion plays
if not use_playbooks or playbook_training_mode == "all-plays-even":
    motion_plays = []
    for play_name, play_data in updated_plays.items():
        if isinstance(play_data, dict) and play_data.get("play_type") == "motion":
            motion_plays.append((play_name, play_data))  # Set plays excluded!
```

**Game Plan Settings Persistence:**

- **✅ FIXED (February 2025):** Game Plan settings now save correctly from Franchise Command Center
- **Root Cause:** `update_gameplan` endpoint was not correctly resolving `team_id` for franchise mode
- **Fix Applied:** Uses `get_user_team_from_franchise()` to get authoritative `user_team_object_id`
- **Code Location:** `BackEnd/api/gameplan_routes.py` - `update_gameplan()` (lines 889-896)
- **Result:** Settings now persist correctly, ensuring `strategy_settings['offense']` is available for training

**Key Normalization:**

- **Legacy Keys:** `'half_court_trap'`, `'full_court_press'` (old format)
- **Current Keys:** `'hc_trap'`, `'fc_press'` (normalized format)
- **Fix Applied:** `get_gameplan()` now normalizes legacy keys when loading settings
- **Code Location:** `BackEnd/api/gameplan_routes.py` - `get_gameplan()` (lines 830-831)

**User Inputs (User Team Only):**
1. **Game Plan Settings (`strategy_settings`)**
   - `offense`, `inside`, `attack`, `outside` (0-4)
   - `tempo`, `defense`, `aggression` (0-4)
   - `hc_trap`, `fc_press`, `rebounding` (0-4)
   - Persist across all GMO and GP instances until changed

2. **Playbooks Settings (`playbook_settings`)**
   - Percentage distributions: `motion`, `set_play_inside`, `set_play_attack`, `set_play_outside`, `zone_defense`, `man_defense`
   - Slot assignments: `slot_assignments` (for Playcall Center slots 1-6)
   - Motion dropdowns: `motion_dropdowns` (Inside/Attack/Outside for motion plays)
   - Position filters: `position_filters` (Standard, PG, SG, SF, PF, C play assignments)
   - Even distribution toggles: Per-container toggle state
   - Persist across all GMO and GP instances until changed

#### Stats Tracking

**Storage Path:** `franchise_document.players.{player_id}`

**⚠️ CRITICAL - Single Source of Truth:** All player stats (season and career) are stored in the `players` object, NOT in `player_stats`. The `players` object is the authoritative location for:
- Player metadata (`meta`: first_name, last_name, team, team_id)
- Evolved attributes (`attributes`: all 30+ attributes with `anchor_` prefixed versions)
- Evolved position ratings (`position_ratings`: PG, SG, SF, PF, C ratings)
- Season stats (`season`: PTS, REB, AST, etc. - direct totals)
- Career stats (`career`: PTS, REB, AST, etc. - direct totals)

**Structure:**
```javascript
{
  players: {
    "player_id": {  // Keyed by player ObjectId (string)
      "meta": {
        "first_name": "CJ",
        "last_name": "Castleman",
        "team": "Bentley-Truman",
        "team_id": "BENTLEY_TRUMAN"
      },
      "attributes": {
        "SC": 78,  // Evolved from training
        "SH": 73,
        "anchor_SC": 78,
        // ... all 30+ attributes
      },
      "position_ratings": {
        "PG": 70,
        "SG": 85,
        "SF": 92,
        "PF": 72,
        "C": 55
      },
      "season": {
        "PTS": 450,
        "REB": 120,
        "AST": 85,
        "FGM": 180,
        "FGA": 400,
        "GP": 5,
        // ... all stat fields (direct totals, no wrapper)
      },
      "career": {
        "PTS": 1234,
        "REB": 456,
        // ... all stat fields (direct totals, no wrapper)
      }
    }
  }
}
```

**Stats Rollup Process:**

1. **After Game Completion:**
   - `finalize_game()` reads from game document's `box_score` to get all player stats
   - `finalize_game()` increments `players.{pid}.season.{stat}` and `players.{pid}.career.{stat}`
   - `rollup_game_to_franchise()` should also write to `players.{pid}.season.{stat}` (not `player_stats`)
   - Both functions use `$inc` operator to increment totals
   - `applied_games` array prevents double-counting (game_id added after rollup)

2. **Box Score Structure (Game Documents):**
   
   **Storage Location:** `games_collection` game documents
   
   **Structure:** `box_score` is stored nested under team objects in the game document:
   ```javascript
   {
     home_team: {
       name: "Morristown",
       box_score: {
         "PG": { name: "Player Name", playerId: "...", jersey: 1, FGM: 5, FGA: 10, PTS: 12, ... },
         "SG": { ... },
         "SF": { ... },
         "PF": { ... },
         "C": { ... },
         "BENCH_1234...": { ... },  // Bench players with unique keys
         // ... all 12 players (lineup + bench)
       }
     },
     away_team: {
       name: "Bentley-Truman",
       box_score: { ... }
     }
   }
   ```
   
   **⚠️ IMPORTANT:** `box_score` is NOT stored at the top level of the game document. It's nested under `home_team["box_score"]` and `away_team["box_score"]`.
   
   **How Box Score is Generated:**
   - `GameManager.get_box_score()` is called during game completion
   - Includes **all players** from `team.players.values()` (lineup + bench), not just active lineup
   - First adds lineup players with their positions (PG, SG, SF, PF, C)
   - Then adds bench players (players not in current lineup)
   - Bench players use their position attribute or default to "BENCH"
   - If multiple bench players have the same position, keys are made unique by appending player_id
   
   **Retrieval Pattern:**
   - `/api/game/{game_id}` endpoint builds `box_score` from nested structure if not found at top level
   - `finalize_game()` builds `box_score` from nested structure when processing stats rollup
   - Frontend box score page displays all players from `box_score` (merges with roster for complete player info)

3. **Stat Fields:**
   - All standard box score stats: `PTS`, `REB`, `AST`, `STL`, `BLK`, `FGM`, `FGA`, `3PTM`, `3PTA`, `FTM`, `FTA`, `TO`, `F`, `MIN`, etc.
   - `MIN` is converted from seconds (game) to minutes (season/career) during rollup
   - `GP` (Games Played) is incremented by 1 for each game
   - **Note:** Frontend displays `3PTM`/`3PTA` but maps to `TPM`/`TPA` for display compatibility

4. **Team Stats Aggregation:**
   - Team stats are calculated by aggregating all player stats from `players` object
   - Filter by `meta.team_id` to get players for a specific team
   - Sum all stat fields across players on that team
   - Stored in `franchise_teams.{team_id}` or computed on-demand for display

**Why `players` and Not `player_stats`:**

- **`players`** is the complete player data structure used throughout the system:
  - Training system writes to `players.{pid}.attributes`
  - Frontend expects `franchiseDoc.players[playerId].season`
  - `get_leaders()` reads from `players.{pid}`
  - Architecture documentation specifies `players` structure
  - Single unified location for all player data (attributes + stats)

- **`player_stats`** was an incomplete migration attempt:
  - Only contains stats (no attributes, no position_ratings)
  - Not used by training system
  - Not expected by frontend
  - Creates dual storage paths = inconsistency

**API Endpoints for Stats:**

- `GET /franchise/state` - Returns full franchise document including `players` object
- `GET /franchise/roster` - Returns roster with player attributes (stats loaded separately from `players`)
- `GET /franchise/leaders` - Reads from `players.{pid}.{scope}` to get category leaders
- `GET /franchise/team-stats` - Aggregates from `players` object, filters by `meta.team_id`
- `GET /api/game/{game_id}` - Returns game state including `box_score`
  - **Box Score Handling:** Builds `box_score` from nested `home_team["box_score"]` and `away_team["box_score"]` if not found at top level
  - **Includes:** All players (lineup + bench) with game stats for display

**Frontend Loading Pattern:**

```javascript
// ✅ CORRECT: Load stats from players object
const franchiseDoc = await fetchJSON(`/franchise/state?franchise_id=${franchiseId}`);
const playerStats = franchiseDoc.players[playerId];
const seasonStats = playerStats?.season || {};
const careerStats = playerStats?.career || {};
```

**Backend Rollup Pattern:**

```python
# ✅ CORRECT: Write to players object
inc_doc[f"players.{pid}.season.{stat}"] = val
inc_doc[f"players.{pid}.career.{stat}"] = val
inc_doc[f"players.{pid}.season.GP"] = 1
inc_doc[f"players.{pid}.career.GP"] = 1

db.franchises.update_one(
    {"_id": fid, "applied_games": {"$ne": game_id}},
    {"$inc": inc_doc, "$addToSet": {"applied_games": game_id}}
)
```

#### Key Variables

**Core Navigation Anchor Set (Required for all navigation):**

These three variables form the foundation for seamless navigation across all GMO screens. They must be preserved in every URL and are used to identify which franchise document and team to load data for.

1. **`mode`** (string)
   - **What it does:** Tells the system you're in franchise mode (versus tournament or single game mode)
   - **Where it lives:** URL parameter (e.g., `?mode=franchise`)
   - **Nested?** No - standalone string value
   - **Example:** `mode=franchise`

2. **`franchise_id`** (ObjectId string)
   - **What it does:** Identifies which franchise document to use (like a unique ID for your franchise save file)
   - **Where it lives:** 
     - URL parameter (e.g., `?franchise_id=507f1f77bcf86cd799439011`)
     - Database: The `_id` field of the franchise document
     - localStorage (as fallback)
   - **Nested?** No - top-level field in the franchise document
   - **Example:** `franchise_id=507f1f77bcf86cd799439011`

3. **`team_id`** (ObjectId string)
   - **What it does:** Identifies the user's team (ObjectId format) - this is your team anchor that ensures all navigation and data access points to the correct team
   - **Where it lives:**
     - URL parameter (e.g., `?team_id=507f1f77bcf86cd799439011`)
     - Database: Stored as `user_team_object_id` in the franchise document (source of truth)
     - localStorage (as fallback, stored as `franchise_user_team_id`)
   - **Nested?** No - top-level field in the franchise document (as `user_team_object_id`)
   - **Note:** Always ObjectId format, never team name
   - **⚠️ CRITICAL:** The franchise document's `user_team_object_id` is the **authoritative source of truth**. Always resolve `team_id` from the franchise document, not from URL parameters. URL parameters are for navigation only - the database value is authoritative.
   - **Example:** `team_id=507f1f77bcf86cd799439011`

**Document-Level Variables (Stored in franchise document):**

These variables are stored in the database franchise document and track the current state of the franchise.

4. **`user_team_id`** (string)
   - **What it does:** Human-readable team name (e.g., "Morristown") - the friendly name for your team
   - **Where it lives:** Database: `franchises.{franchise_id}.user_team_id`
   - **Nested?** No - top-level field in the franchise document
   - **Example:** `user_team_id="Morristown"`

5. **`user_team_object_id`** (ObjectId string)
   - **What it does:** Database ObjectId for the user's team (same value as `team_id` in URLs) - the database key that matches the URL parameter
   - **Where it lives:** Database: `franchises.{franchise_id}.user_team_object_id`
   - **Nested?** No - top-level field in the franchise document
   - **Relationship:** `user_team_object_id === team_id` (URL param)
   - **⚠️ CRITICAL - SOURCE OF TRUTH:** This is the **authoritative value** for the user's team. All backend operations (training, training reports, schedule lookups) must use this value from the franchise document, not from URL parameters. If URL `team_id` doesn't match `user_team_object_id`, use the franchise document value.
   - **Example:** `user_team_object_id="507f1f77bcf86cd799439011"`

6. **`week` / `current_week`** (integer)
   - **What it does:** Current week number (1-14) - tracks which week of the season you're in
   - **Where it lives:**
     - Database: `franchises.{franchise_id}.week`
     - URL parameter (optional, for navigation context)
     - localStorage (as fallback, stored as `franchise_week`)
   - **Nested?** No - top-level field in the franchise document
   - **Example:** `week=5`

7. **`current_season`** (integer)
   - **What it does:** Current season number (starts at 1, increments each season) - tracks which season of the franchise you're in
   - **Where it lives:** Database: `franchises.{franchise_id}.current_season`
   - **Nested?** No - top-level field in the franchise document
   - **Example:** `current_season=1`

**Context Variables (URL parameters for navigation context):**

These variables provide additional context for navigation but aren't required for core data persistence.

8. **`from`** (string, optional)
   - **What it does:** Tracks where you came from (e.g., "command_center" or "lineup") - used to determine back navigation behavior
   - **Where it lives:** URL parameter only (e.g., `?from=command_center`)
   - **Nested?** No - standalone string value
   - **Example:** Game Plan uses this to show "Back to Lineup" vs "Back to Locker Room" button

9. **`view_team_id`** (ObjectId string, optional)
   - **What it does:** ObjectId of the team you're viewing (for viewing opponent/other team rosters) - your `team_id` stays the same, this is just for display
   - **Where it lives:** URL parameter only (e.g., `?view_team_id=507f1f77bcf86cd799439011`)
   - **Nested?** No - standalone string value
   - **Note:** Display context only, not part of navigation anchor

**Transition Variables (When moving to/from gameplay):**

10. **`game_id`** (ObjectId string, optional)
    - **What it does:** Identifies the active game document when you're in gameplay (GP instance)
    - **Where it lives:**
      - URL parameter (e.g., `?game_id=507f1f77bcf86cd799439011`)
      - Database: `_id` field of the game document in `games_collection`
      - localStorage (as fallback)
    - **Nested?** No - top-level field in the game document
    - **Note:** Only present when transitioning to/from gameplay

**Summary:**

- **Core Three:** `mode`, `franchise_id`, and `team_id` form the navigation anchor set and must be preserved across all GMO screens
- **Storage Pattern:** Most variables are NOT nested - they're top-level fields in the franchise document or standalone URL parameters
- **Franchise Document Structure:**
  ```javascript
  {
    _id: "franchise_id",                    // top-level
    user_team_id: "Morristown",             // top-level
    user_team_object_id: "507f...",          // top-level
    week: 5,                                 // top-level
    current_season: 1,                       // top-level
    franchise_teams: {                       // nested object
      "507f...": {                           // team_id as key
        // team data here
      }
    },
    players: {                               // nested object
      // player data
    }
  }
  ```
- **URL Parameters:** Flat key-value pairs (e.g., `?mode=franchise&franchise_id=507f...&team_id=507f...`)

#### Navigation Requirements

**Navigation Anchor Set (Required):**
- **Mode:** `"franchise"` (determines collection/endpoints)
- **Doc ID:** `franchise_id` (ObjectId string)
- **Team ID:** `team_id` (ObjectId string) - User's team anchor

**Validation:**
- All three parameters must be present for seamless navigation
- `team_id` must be ObjectId format (not team name)
- `franchise_id` must be valid ObjectId

#### State Management

**Document-Level State:**
- `week` / `current_week` - Current week number (1-14)
- `current_season` - Current season number (starts at 1, increments each season)
- `schedule` - Pre-generated schedule array `[[team_A_id, team_B_id], ...]` (14 weeks)
- `results` - Weekly game result summaries `{week: [{away_id, home_id, scores}]}`
- `training_status` - `{current_week, training_completed, session_type, last_training_date}`
- `latest_training` - `{player_logs, team_log, session_type, week}`
- `applied_games` - Array of game IDs (prevents double-counting stats)
- `stats` / `leaderboards` - Document-level aggregated statistics
- `created_at` - Document creation timestamp
- `user_team_id` - User's team name (string)
- `user_team_object_id` - User's team ObjectId (string) - **⚠️ SOURCE OF TRUTH for all team operations**

**Team ID Resolution Pattern (SS&S):**
- **Always resolve `team_id` from `user_team_object_id` in the franchise document**
- **Never trust URL parameters alone** - verify against franchise document
- **Backend pattern:**
  ```python
  # ✅ CORRECT: Always use franchise document as source of truth
  user_team_id, user_team_object_id = get_user_team_from_franchise(franchise_doc)
  authoritative_team_id = user_team_object_id  # Use this for all operations
  
  # ❌ WRONG: Don't trust URL params
  team_id = req.team_id  # Might be wrong!
  ```
- **Frontend pattern:**
  ```javascript
  // ✅ CORRECT: Load from command-center/data endpoint (uses franchise document)
  const topData = await fetchJSON(`/franchise/command-center/data?franchise_id=${franchiseId}`);
  const authoritativeTeamId = topData.team_id;  // This comes from user_team_object_id
  
  // Use authoritativeTeamId for all API calls and navigation
  ```

#### Data Flow

**GMO → GP (Starting a Game):**
- Game Plan and Playbooks settings are loaded from `franchise_teams.{user_team_object_id}`
  - **✅ SS&S:** Backend uses `get_user_team_from_franchise()` to get authoritative `user_team_object_id`
  - **✅ SS&S:** URL `team_id` parameter is ignored if it doesn't match franchise document
- Settings are applied to game document when game is created
- Game document is created in `games_collection` with `franchise_id` reference

**GP → GMO (Returning from Gameplay):**
- Game stats are rolled up to franchise document via `rollup_game_to_franchise()`
- Player stats, team stats, plays stats, scouting stats are aggregated
- Game Plan and Playbooks settings persist (unchanged unless user modified during gameplay)

**GMO → GMO (Navigation Between Screens):**
- All settings and state persist via URL parameters (`franchise_id`, `team_id`, `mode`)
- Database is single source of truth for all data
- Frontend loads data from API on each screen load

#### API Endpoints

**Key Endpoints:**
- `GET /api/franchise/command-center-data` - Loads franchise state, team data, schedule
- `GET /api/gameplan` - Loads Game Plan settings (`strategy_settings`)
- `PUT /api/gameplan` - Saves Game Plan settings
- `GET /api/playbooks` - Loads Playbooks settings (`playbook_settings`)
  - **✅ SS&S:** Uses `user_team_object_id` from franchise document as authoritative source
  - **✅ SS&S:** Ignores URL `team_id` parameter if it doesn't match franchise document
- `POST /api/playbooks` - Saves Playbooks settings
  - **✅ SS&S:** Uses `user_team_object_id` from franchise document as authoritative source
  - **✅ SS&S:** Ignores URL `team_id` parameter if it doesn't match franchise document
- `POST /api/franchise/training` - Runs training session, updates attributes/stats
  - **✅ SS&S:** Uses `user_team_object_id` from franchise document as authoritative source
- `GET /api/training-report` - Loads training report data
  - **✅ SS&S:** Uses `user_team_object_id` from franchise document as authoritative source

#### User Actions

**Available Actions:**
- View Command Center (schedule, standings, stats)
- Configure Game Plan (strategy settings)
- Configure Playbooks (playbook settings, slot assignments, position filters)
- Run Training (allocate training points, select coaching focus)
- View Training Report (see attribute changes)
- View Team Roster (player attributes, stats)
- View Standings/Stats (league-wide statistics)
- Start Game (navigate to GP instance)

#### Validation Rules

**Navigation Validation:**
- `franchise_id` must exist in `franchises_collection`
- `team_id` must exist in `franchise_teams` dict
- `team_id` must be ObjectId format (resolved from team name if needed)

**Data Validation:**
- Game Plan: At least one offense setting must be > 0
- Playbooks: Container totals must sum to 100% (after filtering)
- Training: Total training points must = 24, coaching focus must be selected

#### Transition Patterns

**To GMO (Franchise - same mode):**
- Preserve all navigation anchor set (`mode`, `franchise_id`, `team_id`)
- Load state from franchise document

**To GMO (Franchise - different mode):**
- **NOT ALLOWED** - Must go through Mode Select first

**To GP (Starting Game):**
- Preserve `mode`, `franchise_id`, `team_id`
- Add `game_id` to navigation anchor set
- Create game document in `games_collection`

**From GP (Returning to GMO):**
- Preserve `mode`, `franchise_id`, `team_id`
- Remove `game_id` from navigation anchor set
- Stats rolled up to franchise document

---

### GMO - Tournament Mode

#### Data Persistence

**Data Evolutions (All Teams):**
1. **Team Stats, Team Attributes**
   - Team Stats: Aggregation of player stats and play stats (Offense, Defense, Fast Break, Press Trap)
   - Team Attributes: `team_chemistry`, `offensive_efficiency`, `shot_threshold`, `turnover_modifier`, `foul_modifier`, `rebound_modifier`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`

2. **Player Stats, Player Attributes**
   - Player Stats: Tournament statistics (PTS, REB, AST, etc.)
   - Player Attributes: All 30+ attributes (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT, NG, EM, MO, CH, etc.) with `anchor_` prefixed versions
   - Position Ratings: PG, SG, SF, PF, C ratings

3. **Plays Data**
   - `plays[playName].effectiveness` (0-100) - Evolves via training and gameplay
   - `plays[playName].momentum` (0-10) - Evolves via training and gameplay
   - `plays[playName].cloaking` (0-10) - Evolves via training and gameplay
   - `plays[playName].game_stats` - Per-game statistics (times_run, shot_attempts, made_shots, turnovers, etc.)
   - `plays[playName].season_stats` - Cumulative tournament statistics

4. **Scouting Data**
   - `scouting_data.defense[defenseType].effectiveness` (0-100) - Evolves via training and gameplay
   - `scouting_data.defense[defenseType].momentum` (0-10) - Evolves via training and gameplay
   - `scouting_data.defense[defenseType].cloaking` (0-10) - Evolves via training and gameplay
   - `scouting_data.defense[defenseType].game_stats` - Per-game statistics
   - `scouting_data.defense[defenseType].season_stats` - Cumulative tournament statistics
   - Defense Types: Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone, vs_Fast_Break, FCP, HCT

5. **Training Reports (User Team Only)**
   - Stored in `teams.{user_team_id}.training_reports.{round}`
   - Also stored in `latest_training` at document level for quick access
   - Includes player changes, team changes, coaching focus, session type, round

**User Inputs (User Team Only):**
1. **Game Plan Settings (`strategy_settings`)**
   - `offense`, `inside`, `attack`, `outside` (0-4)
   - `tempo`, `defense`, `aggression` (0-4)
   - `hc_trap`, `fc_press`, `rebounding` (0-4)
   - Persist across all GMO and GP instances until changed

2. **Playbooks Settings (`playbook_settings`)**
   - Percentage distributions: `motion`, `set_play_inside`, `set_play_attack`, `set_play_outside`, `zone_defense`, `man_defense`
   - Slot assignments: `slot_assignments` (for Playcall Center slots 1-6)
   - Motion dropdowns: `motion_dropdowns` (Inside/Attack/Outside for motion plays)
   - Position filters: `position_filters` (Standard, PG, SG, SF, PF, C play assignments)
   - Even distribution toggles: Per-container toggle state
   - Persist across all GMO and GP instances until changed

#### Key Variables

**Core Navigation Anchor Set (Required for all navigation):**

These three variables form the foundation for seamless navigation across all GMO screens. They must be preserved in every URL and are used to identify which tournament document and team to load data for.

1. **`mode`** (string)
   - **What it does:** Tells the system you're in tournament mode (versus franchise or single game mode)
   - **Where it lives:** URL parameter (e.g., `?mode=tournament`)
   - **Nested?** No - standalone string value
   - **Example:** `mode=tournament`

2. **`tournament_id`** (ObjectId string)
   - **What it does:** Identifies which tournament document to use (like a unique ID for your tournament instance)
   - **Where it lives:**
     - URL parameter (e.g., `?tournament_id=507f1f77bcf86cd799439011`)
     - Database: The `_id` field of the tournament document
     - localStorage (as fallback, stored as `activeTournament._id`)
   - **Nested?** No - top-level field in the tournament document
   - **Example:** `tournament_id=507f1f77bcf86cd799439011`

3. **`team_id`** (ObjectId string)
   - **What it does:** Identifies the user's team (ObjectId format) - this is your team anchor that ensures all navigation and data access points to the correct team
   - **Where it lives:**
     - URL parameter (e.g., `?team_id=507f1f77bcf86cd799439011`)
     - Database: Stored as `user_team_object_id` in the tournament document
     - localStorage (as fallback, stored as `userTeamId`)
   - **Nested?** No - top-level field in the tournament document (as `user_team_object_id`)
   - **Note:** Always ObjectId format, never team name
   - **Example:** `team_id=507f1f77bcf86cd799439011`

**Document-Level Variables (Stored in tournament document):**

These variables are stored in the database tournament document and track the current state of the tournament.

4. **`user_team_id`** (string)
   - **What it does:** Human-readable team name (e.g., "Morristown") - the friendly name for your team
   - **Where it lives:** Database: `tournaments.{tournament_id}.user_team_id`
   - **Nested?** No - top-level field in the tournament document
   - **Example:** `user_team_id="Morristown"`

5. **`user_team_object_id`** (ObjectId string)
   - **What it does:** Database ObjectId for the user's team (same value as `team_id` in URLs) - the database key that matches the URL parameter
   - **Where it lives:** Database: `tournaments.{tournament_id}.user_team_object_id`
   - **Nested?** No - top-level field in the tournament document
   - **Relationship:** `user_team_object_id === team_id` (URL param)
   - **Example:** `user_team_object_id="507f1f77bcf86cd799439011"`

6. **`current_round`** (integer)
   - **What it does:** Current round number (1-3) - tracks which round of the tournament you're in (Round of 16, Quarterfinals, Finals)
   - **Where it lives:**
     - Database: `tournaments.{tournament_id}.current_round`
     - URL parameter (optional, for navigation context as `round`)
   - **Nested?** No - top-level field in the tournament document
   - **Example:** `current_round=2` (Quarterfinals)

7. **`completed`** (boolean)
   - **What it does:** Whether the tournament is finished (true after final round is complete, false otherwise) - tracks if tournament has ended
   - **Where it lives:** Database: `tournaments.{tournament_id}.completed`
   - **Nested?** No - top-level field in the tournament document
   - **Example:** `completed=false`

8. **`bracket`** (object)
   - **What it does:** Tournament bracket structure containing matchups for each round - stores all matchups and results
   - **Where it lives:** Database: `tournaments.{tournament_id}.bracket`
   - **Nested?** Yes - nested object with structure: `{round1: [...], round2: [...], final: [...]}`
   - **Example:** `bracket.round1[0] = {home_id, away_id, winner, game_id, ...}`

**Context Variables (URL parameters for navigation context):**

These variables provide additional context for navigation but aren't required for core data persistence.

9. **`round`** (integer, optional)
   - **What it does:** Round number for navigation context (1-3) - used for training report and round-specific screens
   - **Where it lives:** URL parameter only (e.g., `?round=2`)
   - **Nested?** No - standalone integer value
   - **Note:** Matches `current_round` from database, but URL param provides navigation context

10. **`from`** (string, optional)
    - **What it does:** Tracks where you came from (e.g., "command_center" or "lineup") - used to determine back navigation behavior
    - **Where it lives:** URL parameter only (e.g., `?from=command_center`)
    - **Nested?** No - standalone string value
    - **Example:** Game Plan uses this to show "Back to Lineup" vs "Back to Locker Room" button

11. **`view_team_id`** (ObjectId string, optional)
    - **What it does:** ObjectId of the team you're viewing (for viewing opponent/other team rosters) - your `team_id` stays the same, this is just for display
    - **Where it lives:** URL parameter only (e.g., `?view_team_id=507f1f77bcf86cd799439011`)
    - **Nested?** No - standalone string value
    - **Note:** Display context only, not part of navigation anchor

**Transition Variables (When moving to/from gameplay):**

12. **`game_id`** (ObjectId string, optional)
    - **What it does:** Identifies the active game document when you're in gameplay (GP instance)
    - **Where it lives:**
      - URL parameter (e.g., `?game_id=507f1f77bcf86cd799439011`)
      - Database: `_id` field of the game document in `games_collection`
      - localStorage (as fallback)
    - **Nested?** No - top-level field in the game document
    - **Note:** Only present when transitioning to/from gameplay

**Summary:**

- **Core Three:** `mode`, `tournament_id`, and `team_id` form the navigation anchor set and must be preserved across all GMO screens
- **Storage Pattern:** Most variables are NOT nested - they're top-level fields in the tournament document or standalone URL parameters (except `bracket` which is nested)
- **Tournament Document Structure:**
  ```javascript
  {
    _id: "tournament_id",                    // top-level
    user_team_id: "Morristown",              // top-level
    user_team_object_id: "507f...",          // top-level
    current_round: 2,                          // top-level
    completed: false,                          // top-level
    bracket: {                                 // nested object
      round1: [...],                          // nested array
      round2: [...],                          // nested array
      final: [...]                            // nested array
    },
    teams: {                                   // nested object
      "507f...": {                            // team_id as key
        // team data here
      }
    },
    players: {                                 // nested object
      // player data
    }
  }
  ```
- **URL Parameters:** Flat key-value pairs (e.g., `?mode=tournament&tournament_id=507f...&team_id=507f...`)
- **Key Differences from Franchise Mode:**
  - Uses `tournament_id` instead of `franchise_id`
  - Uses `current_round` (1-3) instead of `week` (1-14)
  - Uses `completed` (boolean) instead of `current_season` (integer)
  - Uses `bracket` structure instead of `schedule` array
  - Uses `round` URL parameter instead of `week`
  - localStorage key is `userTeamId` instead of `franchise_user_team_id`

#### Navigation Requirements

**Navigation Anchor Set (Required):**
- **Mode:** `"tournament"` (determines collection/endpoints)
- **Doc ID:** `tournament_id` (ObjectId string)
- **Team ID:** `team_id` (ObjectId string) - User's team anchor

**Validation:**
- All three parameters must be present for seamless navigation
- `team_id` must be ObjectId format (not team name)
- `tournament_id` must be valid ObjectId

#### State Management

**Document-Level State:**
- `current_round` - Current round number (1-3)
- `completed` - Whether tournament is finished (boolean)
- `bracket` - Tournament bracket structure `{round1: [...], round2: [...], final: [...]}`
- `training_status` - `{round, training_completed, session_type, last_training_date}`
- `latest_training` - `{round, player_logs, team_log, session_type}`
- `applied_games` - Array of game IDs (prevents double-counting stats)
- `stats` / `leaderboards` - Document-level aggregated statistics
- `created_at` - Document creation timestamp
- `user_team_id` - User's team name (string)
- `user_team_object_id` - User's team ObjectId (string)

#### Data Flow

**GMO → GP (Starting a Game):**
- Game Plan and Playbooks settings are loaded from `teams.{team_id}`
- Settings are applied to game document when game is created
- Game document is created in `games_collection` with `tournament_id` reference

**GP → GMO (Returning from Gameplay):**
- Game stats are rolled up to tournament document via `rollup_game_to_tournament()`
- Player stats, team stats, plays stats, scouting stats are aggregated
- Game Plan and Playbooks settings persist (unchanged unless user modified during gameplay)

**GMO → GMO (Navigation Between Screens):**
- All settings and state persist via URL parameters (`tournament_id`, `team_id`, `mode`)
- Database is single source of truth for all data
- Frontend loads data from API on each screen load

#### API Endpoints

**Key Endpoints:**
- `GET /api/tournament/state` - Loads tournament state, team data, bracket
- `GET /api/gameplan` - Loads Game Plan settings (`strategy_settings`)
- `PUT /api/gameplan` - Saves Game Plan settings
- `GET /api/playbooks` - Loads Playbooks settings (`playbook_settings`)
- `POST /api/playbooks` - Saves Playbooks settings
- `POST /api/tournament/training` - Runs training session, updates attributes/stats
- `GET /api/training-report` - Loads training report data

#### User Actions

**Available Actions:**
- View Command Center (bracket, standings, stats)
- Configure Game Plan (strategy settings)
- Configure Playbooks (playbook settings, slot assignments, position filters)
- Run Training (allocate training points, select coaching focus)
- View Training Report (see attribute changes)
- View Team Roster (player attributes, stats)
- View Standings/Stats (tournament-wide statistics)
- Start Game (navigate to GP instance)

#### Validation Rules

**Navigation Validation:**
- `tournament_id` must exist in `tournaments_collection`
- `team_id` must exist in `teams` dict
- `team_id` must be ObjectId format (resolved from team name if needed)

**Data Validation:**
- Game Plan: At least one offense setting must be > 0
- Playbooks: Container totals must sum to 100% (after filtering)
- Training: Total training points must = 24, coaching focus must be selected

#### Transition Patterns

**To GMO (Tournament - same mode):**
- Preserve all navigation anchor set (`mode`, `tournament_id`, `team_id`)
- Load state from tournament document

**To GMO (Tournament - different mode):**
- **NOT ALLOWED** - Must go through Mode Select first

**To GP (Starting Game):**
- Preserve `mode`, `tournament_id`, `team_id`
- Add `game_id` to navigation anchor set
- Create game document in `games_collection`

**From GP (Returning to GMO):**
- Preserve `mode`, `tournament_id`, `team_id`
- Remove `game_id` from navigation anchor set
- Stats rolled up to tournament document

---

## Gameplay (GP)

**Definition:** User is actively playing a game (in gameplay experience).

**Sub-categories:**
- **GP - Franchise Mode:** Lineup Select Experience, Game Plan, Playbooks, Play Details, Gameplay Screen, Box Score
- **GP - Tournament Mode:** Similar structure but with tournament context
- **GP - Single Game Mode:** Similar structure but without mode context

**Examples:**
- Lineup Select Experience (set-lineup.html)
- Game Plan screen (during game)
- Playbooks screen (during game)
- Play Details pages (individual play pages)
- Gameplay Screen (court.html)
- Box Score screen (after game)

### GP - Franchise Mode

#### Data Persistence

**Game State (Per Game):**
1. **Game Document** (`games_collection`)
   - Game ID (composite key: `{week}-{away_id}-{home_id}`)
   - Scores, quarter, clock, time_remaining
   - Full player stats (accumulated per quarter)
   - Box score data
   - Game metadata (mode, franchise_id, week)

2. **Game Settings** (Applied to Game Document)
   - Game Plan settings (`strategy_settings`) - Loaded from franchise document
   - Playbooks settings (`playbook_settings`) - Loaded from franchise document
   - Lineups (home_lineup, away_lineup) - Set by user during game

**User Settings (Persist Across GP Instances):**
1. **Game Plan Settings (`strategy_settings`)**
   - `offense`, `inside`, `attack`, `outside` (0-4)
   - `tempo`, `defense`, `aggression` (0-4)
   - `hc_trap`, `fc_press`, `rebounding` (0-4)
   - Stored in franchise document, persist across all GP screens until changed

2. **Playbooks Settings (`playbook_settings`)**
   - Percentage distributions: `motion`, `set_play_inside`, `set_play_attack`, `set_play_outside`, `zone_defense`, `man_defense`
   - Slot assignments: `slot_assignments` (for Playcall Center slots 1-6)
   - Motion dropdowns: `motion_dropdowns` (Inside/Attack/Outside for motion plays)
   - Position filters: `position_filters` (Standard, PG, SG, SF, PF, C play assignments)
   - Even distribution toggles: Per-container toggle state
   - Stored in franchise document, persist across all GP screens until changed

**Game Context (During Active Game):**
- Current quarter, clock, scores
- Lineup selections (home_lineup, away_lineup)
- Timeout state (if resuming from timeout)
- Game ID (identifies active game document)

#### Key Variables

**Core Navigation Anchor Set (Required for all GP navigation):**

These three variables form the foundation for seamless navigation across all GP screens. They must be preserved in every URL and are used to identify which franchise document and team to load data for.

1. **`mode`** (string)
   - **What it does:** Tells the system you're in franchise mode gameplay (versus tournament or single game mode)
   - **Where it lives:** URL parameter (e.g., `?mode=franchise`)
   - **Nested?** No - standalone string value
   - **Example:** `mode=franchise`

2. **`franchise_id`** (ObjectId string)
   - **What it does:** Identifies which franchise document to use (the same franchise you're playing in)
   - **Where it lives:**
     - URL parameter (e.g., `?franchise_id=507f1f77bcf86cd799439011`)
     - Database: The `_id` field of the franchise document
     - localStorage (as fallback)
   - **Nested?** No - top-level field in the franchise document
   - **Example:** `franchise_id=507f1f77bcf86cd799439011`

3. **`team_id`** (ObjectId string)
   - **What it does:** Identifies the user's team (ObjectId format) - this is your team anchor that ensures all navigation and data access points to the correct team
   - **Where it lives:**
     - URL parameter (e.g., `?team_id=507f1f77bcf86cd799439011`)
     - Database: Stored as `user_team_object_id` in the franchise document (source of truth)
     - localStorage (as fallback, stored as `franchise_user_team_id`)
   - **Nested?** No - top-level field in the franchise document (as `user_team_object_id`)
   - **Note:** Always ObjectId format, never team name
   - **⚠️ CRITICAL:** The franchise document's `user_team_object_id` is the **authoritative source of truth**. Always resolve `team_id` from the franchise document, not from URL parameters. URL parameters are for navigation only - the database value is authoritative.
   - **Example:** `team_id=507f1f77bcf86cd799439011`

**Game-Specific Variables (Required when game is active):**

These variables track the current game state and are required when in an active game:

4. **`game_id`** (ObjectId string)
   - **What it does:** Identifies the active game document (composite key: `{week}-{away_id}-{home_id}`)
   - **Where it lives:**
     - URL parameter (e.g., `?game_id=1-507f...-507f...`)
     - Database: `_id` field of the game document in `games_collection`
     - localStorage (as fallback)
   - **Nested?** No - top-level field in the game document
   - **When Required:** Always required when game is active (quarter > 1, or resuming from timeout, or during gameplay)
   - **Example:** `game_id=1-507f1f77bcf86cd799439011-507f1f77bcf86cd799439012`

5. **`quarter`** (integer)
   - **What it does:** Tracks current quarter number (1-4, or higher for overtime)
   - **Where it lives:**
     - URL parameter (e.g., `?quarter=2`)
     - Database: `games.{game_id}.quarter`
   - **Nested?** No - top-level field in the game document
   - **When Required:** Always required during gameplay
   - **Example:** `quarter=2`

6. **`week`** (integer)
   - **What it does:** Identifies which week of the franchise season this game belongs to (1-14)
   - **Where it lives:**
     - URL parameter (e.g., `?week=5`)
     - Database: `games.{game_id}.week` and `franchises.{franchise_id}.week`
     - localStorage (as fallback, stored as `franchise_week`)
   - **Nested?** No - top-level field in both game and franchise documents
   - **Required:** Yes - for franchise context
   - **Example:** `week=5`

**Lineup Variables (Required for lineup management):**

7. **`my_team`** (string)
   - **What it does:** Identifies which side the user's team is on ("home" or "away")
   - **Where it lives:** URL parameter (e.g., `?my_team=home`)
   - **Nested?** No - standalone string value
   - **Example:** `my_team=home`

8. **`home`** (string)
   - **What it does:** Home team name for display (e.g., "Morristown")
   - **Where it lives:** URL parameter (e.g., `?home=Morristown`)
   - **Nested?** No - standalone string value
   - **Example:** `home=Morristown`

9. **`away`** (string)
   - **What it does:** Away team name for display (e.g., "Bentley-Truman")
   - **Where it lives:** URL parameter (e.g., `?away=Bentley-Truman`)
   - **Nested?** No - standalone string value
   - **Example:** `away=Bentley-Truman`

10. **`home_id`** (ObjectId string)
    - **What it does:** Home team ObjectId for backend lookups and data access
    - **Where it lives:** URL parameter (e.g., `?home_id=507f1f77bcf86cd799439011`)
    - **Nested?** No - standalone ObjectId string
    - **Example:** `home_id=507f1f77bcf86cd799439011`

11. **`away_id`** (ObjectId string)
    - **What it does:** Away team ObjectId for backend lookups and data access
    - **Where it lives:** URL parameter (e.g., `?away_id=507f1f77bcf86cd799439012`)
    - **Nested?** No - standalone ObjectId string
    - **Example:** `away_id=507f1f77bcf86cd799439012`

12. **Lineup Position Parameters** (optional, but recommended)
    - **Format:** `{my_team}_{position}` (e.g., `home_pg`, `away_sg`)
    - **Positions:** `pg`, `sg`, `sf`, `pf`, `c`
    - **What it does:** Preserves lineup selections during navigation (which players are in which positions)
    - **Where it lives:** URL parameters
    - **Nested?** No - individual URL parameters per position
    - **When Required:** When lineup is set (user has selected players)
    - **Example:** `home_pg=507f...&home_sg=507f...&home_sf=507f...&home_pf=507f...&home_c=507f...`

**Timeout/Resume Variables (Conditionally required):**

13. **`resume_from_timeout`** (boolean, optional)
    - **What it does:** Indicates game is resuming from a timeout (true) or not (false/missing)
    - **Where it lives:** URL parameter (e.g., `?resume_from_timeout=true`)
    - **Nested?** No - standalone boolean string value
    - **When Required:** Only when resuming from timeout
    - **Example:** `resume_from_timeout=true`

14. **`clock`** (string, optional)
    - **What it does:** Preserves game clock time during timeout navigation (e.g., "12:00", "8:34")
    - **Where it lives:** URL parameter (e.g., `?clock=8:34`)
    - **Nested?** No - standalone string value
    - **When Required:** Only when resuming from timeout (to restore clock position)
    - **Example:** `clock=8:34`

**Context Variables (Optional, for navigation context):**

15. **`from`** (string, optional)
    - **What it does:** Tracks where you came from (e.g., "lineup", "game-plan", "command_center") - used to determine back navigation behavior
    - **Where it lives:** URL parameter only (e.g., `?from=lineup`)
    - **Nested?** No - standalone string value
    - **Example:** Game Plan uses this to show "Back to Lineup" vs "Back to Locker Room" button

16. **`play_name`** (string, optional)
    - **What it does:** Identifies which play to display when on Play Details page (e.g., "3-2 Motion", "Base Post Play")
    - **Where it lives:** URL parameter only (e.g., `?play_name=3-2 Motion`)
    - **Nested?** No - standalone string value
    - **When Required:** Only when viewing Play Details page
    - **Example:** `play_name=3-2 Motion`

**Summary:**
- **Core Three:** `mode`, `franchise_id`, and `team_id` form the navigation anchor set and must be preserved across all GP screens
- **Game State:** `game_id`, `quarter`, `week` track the active game
- **Lineup State:** `my_team`, `home`, `away`, `home_id`, `away_id`, lineup position parameters preserve lineup selections
- **Timeout State:** `resume_from_timeout`, `clock` preserve timeout resume context
- **Navigation Context:** `from`, `play_name` provide navigation context
- **Storage Pattern:** Most variables are NOT nested - they're URL parameters or top-level fields in documents

#### Navigation Requirements

**Navigation Anchor Set (Required):**
- **Mode:** `"franchise"` (determines collection/endpoints)
- **Doc ID:** `franchise_id` (ObjectId string)
- **Team ID:** `team_id` (ObjectId string) - User's team anchor
- **Game ID:** `game_id` (composite key) - Required when game is active

**Validation:**
- All three core parameters (`mode`, `franchise_id`, `team_id`) must be present for seamless navigation
- `game_id` required when `quarter > 1` or `resume_from_timeout=true` or during active gameplay
- `team_id` must be ObjectId format (not team name)
- `franchise_id` must be valid ObjectId
- `game_id` must exist in database

#### State Management

**Game State (Stored in game document):**
- `game_id` - Composite key (`{week}-{away_id}-{home_id}`)
- `quarter` - Current quarter number (1-4+)
- `clock` - Current game clock display (e.g., "12:00")
- `time_remaining` - Time remaining in seconds
- `score` - Current scores `{home_team: X, away_team: Y}`
- `home_lineup` / `away_lineup` - Current lineups (player IDs by position)
- `franchise_id` - Reference to franchise document
- `week` - Week number (1-14)
- `mode` - "franchise"
- `players[]` - Player stats (accumulated per quarter)
- `box_score` - Box score data structure
- `is_final` - Boolean flag (true when game is complete)

**Franchise Context (Stored in franchise document):**
- `week` / `current_week` - Current week number (1-14)
- `current_season` - Current season number
- `user_team_object_id` - User's team ObjectId (source of truth for `team_id`)
- Game Plan settings (`franchise_teams.{team_id}.strategy_settings`)
- Playbooks settings (`franchise_teams.{team_id}.playbook_settings`)

**Timeout State (Stored in game document):**
- `timeout_next_play_type` - "SIDE_INBOUND" or "FREE_THROW"
- `timeout_offense_team_id` - Team that had possession
- `timeout_calling_team` - Team that called timeout

#### Data Flow

**GMO → GP (Starting a Game):**
- User clicks "Play Next Game" from FCC
- Navigate to Lineup Select Experience with `mode`, `franchise_id`, `team_id`, `week`
- User sets lineup, then navigates to Game Plan or directly to Gameplay Screen
- Game Plan and Playbooks settings are loaded from `franchise_teams.{user_team_object_id}`
  - **✅ SS&S:** Backend uses `get_user_team_from_franchise()` to get authoritative `user_team_object_id`
  - **✅ SS&S:** URL `team_id` parameter is ignored if it doesn't match franchise document
- Game is initialized via `/api/init-game` endpoint
- Game document is created in `games_collection` with `franchise_id`, `week` references
- Settings are applied to game document when game starts

**GP → GP (Navigation Between GP Screens):**
- All settings and state persist via URL parameters
- Core navigation anchor set (`mode`, `franchise_id`, `team_id`) preserved
- Game state (`game_id`, `quarter`, `clock`) preserved when game is active
- Lineup state preserved via position parameters
- Settings persist via database (loaded from franchise document on each screen)

**GP → GP (Timeout Navigation):**
- Game state saved to database with `timeout_next_play_type`, `timeout_offense_team_id`
- Navigate to Lineup Select Experience with `game_id`, `quarter`, `clock`, `resume_from_timeout=true`
- All game context preserved via `TimeoutNavigationHelper.buildGameNavigationParams()`
- Backend restores timeout state from database on resume

**GP → GMO (Returning from Gameplay):**
- Game stats are rolled up to franchise document via `rollup_game_to_franchise()`
- Player stats, team stats, plays stats, scouting stats are aggregated
- Game Plan and Playbooks settings persist (unchanged unless user modified during gameplay)
- Navigate to FCC with `mode`, `franchise_id`, `team_id` preserved

**GP → GP (Quarter Breaks):**
- Game state persists in database
- Navigate to Lineup Select Experience for next quarter
- `game_id`, `quarter` (incremented), lineup parameters preserved
- Game continues with same game document

**GP → GP (Game Completion):**
- Final stats rolled up to franchise document
- Box Score shows final game stats
- Navigate to FCC or continue to next game

#### API Endpoints

**Key Endpoints:**
- `POST /api/init-game` - Initializes new game, creates game document
- `POST /api/simulate-quarter` - Simulates a quarter, returns turn data
- `GET /api/game/{game_id}` - Loads game state from database
- `GET /api/gameplan` - Loads Game Plan settings (`strategy_settings`)
- `PUT /api/gameplan` - Saves Game Plan settings
- `GET /api/playbooks` - Loads Playbooks settings (`playbook_settings`)
  - **✅ SS&S:** Uses `user_team_object_id` from franchise document as authoritative source
  - **✅ SS&S:** Ignores URL `team_id` parameter if it doesn't match franchise document
- `POST /api/playbooks` - Saves Playbooks settings
  - **✅ SS&S:** Uses `user_team_object_id` from franchise document as authoritative source
  - **✅ SS&S:** Ignores URL `team_id` parameter if it doesn't match franchise document
- `POST /franchise/complete-week` - Completes game, rolls up stats to franchise

#### User Actions

**Available Actions:**
- Set Lineup (select players for home/away teams)
- Configure Game Plan (strategy settings) - persists to franchise document
- Configure Playbooks (playbook settings, slot assignments) - persists to franchise document
- View Play Details (individual play information)
- Start Game (navigate to Gameplay Screen)
- Resume from Timeout (continue game after timeout)
- View Box Score (after game completion)
- Navigate Between GP Screens (Lineup ↔ Game Plan ↔ Playbooks ↔ Play Details ↔ Gameplay)

#### Validation Rules

**Navigation Validation:**
- `franchise_id` must exist in `franchises_collection`
- `team_id` must exist in `franchise_teams` dict
- `team_id` must be ObjectId format (resolved from franchise document if needed)
- `game_id` must exist in `games_collection` when game is active
- `week` must be valid (1-14)

**Game State Validation:**
- `quarter` must be valid (1-4, or higher for overtime)
- `game_id` required when `quarter > 1` or `resume_from_timeout=true`
- Lineup must have 5 players per team (if set)

**Data Validation:**
- Game Plan: At least one offense setting must be > 0
- Playbooks: Container totals must sum to 100% (after filtering)
- Lineup: Each position must have a valid player ID (if lineup is set)

#### Transition Patterns

**GMO → GP (Starting Game):**
- Preserve all navigation anchor set (`mode`, `franchise_id`, `team_id`)
- Add `week` for franchise context
- Initialize game document via `/api/init-game`
- Add `game_id` to navigation anchor set after initialization

**GP → GP (Between GP Screens):**
- Preserve all navigation anchor set (`mode`, `franchise_id`, `team_id`)
- Preserve `game_id` if game is active
- Preserve `quarter`, `clock`, `resume_from_timeout` if applicable
- Preserve lineup parameters if lineup is set
- Preserve `from` parameter for back navigation context
- Use `TimeoutNavigationHelper.buildGameNavigationParams()` for consistency

**GP → GP (Timeout Navigation):**
- Preserve all navigation anchor set (`mode`, `franchise_id`, `team_id`)
- Preserve `game_id`, `quarter`, `clock`
- Add `resume_from_timeout=true`
- Preserve all lineup parameters
- Backend saves timeout state to database

**GP → GP (Quarter Breaks):**
- Preserve all navigation anchor set (`mode`, `franchise_id`, `team_id`)
- Preserve `game_id`
- Increment `quarter` parameter
- Preserve lineup parameters (or allow user to change lineup)

**GP → GMO (Returning to FCC):**
- Preserve all navigation anchor set (`mode`, `franchise_id`, `team_id`)
- Remove `game_id` from navigation anchor set (game is complete)
- Stats rolled up to franchise document
- Navigate to FCC

---

## Gameplay (GP) - Single Game Mode

**Definition:** User is actively playing a single game (not part of a franchise or tournament).

**Sub-categories:**
- **GP - Single Game Mode:** Lineup Select Experience, Game Plan, Playbooks, Play Details, Gameplay Screen, Box Score

**Examples:**
- Lineup Select Experience (set-lineup.html)
- Game Plan screen (during game)
- Playbooks screen (during game)
- Play Details pages (individual play pages)
- Gameplay Screen (court.html)
- Box Score screen (after game)

### GP - Single Game Mode

#### Data Persistence

**Game State (Per Game):**
1. **Game Document** (`games_collection`)
   - Game ID (ObjectId format)
   - Scores, quarter, clock, time_remaining
   - Full player stats (accumulated per quarter)
   - Box score data
   - Game metadata (mode: "single")

2. **Game Settings** (Applied to Game Document)
   - Game Plan settings (`strategy_settings`) - Loaded from game document or team document
   - Playbooks settings (`playbook_settings`) - Loaded from game document or team document
   - Lineups (home_lineup, away_lineup) - Set by user during game

**User Settings (Persist Across GP Instances):**
1. **Game Plan Settings (`strategy_settings`)**
   - `offense`, `inside`, `attack`, `outside` (0-4)
   - `tempo`, `defense`, `aggression` (0-4)
   - `hc_trap`, `fc_press`, `rebounding` (0-4)
   - Stored in `teams.{team_id}.strategy_settings`, persist across all GP screens until changed

2. **Playbooks Settings (`playbook_settings`)**
   - Percentage distributions: `motion`, `set_play_inside`, `set_play_attack`, `set_play_outside`, `zone_defense`, `man_defense`
   - Slot assignments: `slot_assignments` (for Playcall Center slots 1-6)
   - Motion dropdowns: `motion_dropdowns` (Inside/Attack/Outside for motion plays)
   - Position filters: `position_filters` (Standard, PG, SG, SF, PF, C play assignments)
   - Even distribution toggles: Per-container toggle state
   - Stored in `teams.{team_id}.playbook_settings`, persist across all GP screens until changed

**Game Context (During Active Game):**
- Current quarter, clock, scores
- Lineup selections (home_lineup, away_lineup)
- Timeout state (if resuming from timeout)
- Game ID (identifies active game document)

#### Key Variables

**Core Navigation Variables (Required for all GP navigation):**

1. **`mode`** (string)
   - **What it does:** Tells the system you're in single game mode (versus tournament or franchise mode)
   - **Where it lives:** URL parameter (e.g., `?mode=single`)
   - **Nested?** No - standalone string value
   - **Example:** `mode=single`

2. **`team_id`** (string - team name format)
   - **What it does:** Identifies the user's team (team name format, e.g., "Four Corners") - used for loading/saving settings
   - **Where it lives:**
     - URL parameter (e.g., `?team_id=Four+Corners`)
     - Database: Team name in `teams_collection` or game document
   - **Nested?** No - standalone string value
   - **Note:** In Single Game mode, `team_id` is the team name (not ObjectId format like Franchise/Tournament)
   - **Example:** `team_id=Four+Corners`

**Game-Specific Variables (Required when game is active):**

3. **`game_id`** (ObjectId string)
   - **What it does:** Identifies the active game document
   - **Where it lives:**
     - URL parameter (e.g., `?game_id=507f1f77bcf86cd799439011`)
     - Database: `_id` field of the game document in `games_collection`
     - localStorage (as fallback)
   - **Nested?** No - top-level field in the game document
   - **When Required:** Always required when game is active (quarter > 1, or resuming from timeout, or during gameplay)
   - **Example:** `game_id=507f1f77bcf86cd799439011`

4. **`quarter`** (integer)
   - **What it does:** Tracks current quarter number (1-4, or higher for overtime)
   - **Where it lives:**
     - URL parameter (e.g., `?quarter=2`)
     - Database: `games.{game_id}.quarter`
   - **Nested?** No - top-level field in the game document
   - **When Required:** Always required during gameplay
   - **Example:** `quarter=2`

**Lineup Variables (Required for lineup management):**

5. **`my_team`** (string)
   - **What it does:** Identifies which side the user's team is on ("home" or "away")
   - **Where it lives:** URL parameter (e.g., `?my_team=home`)
   - **Nested?** No - standalone string value
   - **Example:** `my_team=home`

6. **`home`** (string)
   - **What it does:** Home team name for display (e.g., "Four Corners")
   - **Where it lives:** URL parameter (e.g., `?home=Four+Corners`)
   - **Nested?** No - standalone string value
   - **Example:** `home=Four+Corners`

7. **`away`** (string)
   - **What it does:** Away team name for display (e.g., "Ocean City")
   - **Where it lives:** URL parameter (e.g., `?away=Ocean+City`)
   - **Nested?** No - standalone string value
   - **Example:** `away=Ocean+City`

8. **`home_id`** (ObjectId string, optional)
   - **What it does:** Home team ObjectId for backend lookups (may not be present in Single Game mode)
   - **Where it lives:** URL parameter (e.g., `?home_id=507f1f77bcf86cd799439011`)
   - **Nested?** No - standalone ObjectId string
   - **Note:** May not be present in Single Game mode - `team_id` (team name) is used instead
   - **Example:** `home_id=507f1f77bcf86cd799439011`

9. **`away_id`** (ObjectId string, optional)
   - **What it does:** Away team ObjectId for backend lookups (may not be present in Single Game mode)
   - **Where it lives:** URL parameter (e.g., `?away_id=507f1f77bcf86cd799439012`)
   - **Nested?** No - standalone ObjectId string
   - **Note:** May not be present in Single Game mode - `team_id` (team name) is used instead
   - **Example:** `away_id=507f1f77bcf86cd799439012`

10. **Lineup Position Parameters** (optional, but recommended)
    - **Format:** `{my_team}_{position}` (e.g., `home_pg`, `away_sg`)
    - **Positions:** `pg`, `sg`, `sf`, `pf`, `c`
    - **What it does:** Preserves lineup selections during navigation (which players are in which positions)
    - **Where it lives:** URL parameters
    - **Nested?** No - individual URL parameters per position
    - **When Required:** When lineup is set (user has selected players)
    - **Example:** `home_pg=507f...&home_sg=507f...&home_sf=507f...&home_pf=507f...&home_c=507f...`

**Timeout/Resume Variables (Conditionally required):**

11. **`resume_from_timeout`** (boolean, optional)
    - **What it does:** Indicates game is resuming from a timeout (true) or not (false/missing)
    - **Where it lives:** URL parameter (e.g., `?resume_from_timeout=true`)
    - **Nested?** No - standalone boolean string value
    - **When Required:** Only when resuming from timeout
    - **Example:** `resume_from_timeout=true`

12. **`clock`** (string, optional)
    - **What it does:** Preserves game clock time during timeout navigation (e.g., "12:00", "8:34")
    - **Where it lives:** URL parameter (e.g., `?clock=8:34`)
    - **Nested?** No - standalone string value
    - **When Required:** Only when resuming from timeout (to restore clock position)
    - **Example:** `clock=8:34`

**Context Variables (Optional, for navigation context):**

13. **`from`** (string, optional)
    - **What it does:** Tracks where you came from (e.g., "lineup", "game-plan", "playbooks") - used to determine back navigation behavior
    - **Where it lives:** URL parameter only (e.g., `?from=lineup`)
    - **Nested?** No - standalone string value
    - **Example:** Game Plan uses this to show "Back to Lineup" vs "Back to Locker Room" button

14. **`play_name`** (string, optional)
    - **What it does:** Identifies which play to display when on Play Details page (e.g., "3-2 Motion", "Base Post Play")
    - **Where it lives:** URL parameter only (e.g., `?play_name=3-2 Motion`)
    - **Nested?** No - standalone string value
    - **When Required:** Only when viewing Play Details page
    - **Example:** `play_name=3-2 Motion`

**Summary:**
- **Core Two:** `mode` and `team_id` form the navigation anchor set for Single Game mode
- **Game State:** `game_id`, `quarter` track the active game
- **Lineup State:** `my_team`, `home`, `away`, lineup position parameters preserve lineup selections
- **Timeout State:** `resume_from_timeout`, `clock` preserve timeout resume context
- **Navigation Context:** `from`, `play_name` provide navigation context
- **Key Difference from Franchise/Tournament:** `team_id` is team name (string) in Single Game mode, not ObjectId format

#### Navigation Requirements

**Navigation Anchor Set (Required):**
- **Mode:** `"single"` (determines collection/endpoints)
- **Team ID:** `team_id` (team name string) - User's team anchor
- **Game ID:** `game_id` (ObjectId string) - Required when game is active

**Validation:**
- `mode` must be `"single"`
- `team_id` required for settings loading/saving (team name format, not ObjectId)
- `game_id` required when `quarter > 1` or `resume_from_timeout=true` or during active gameplay
- `game_id` must exist in database

#### State Management

**Game State (Stored in game document):**
- `game_id` - ObjectId format
- `quarter` - Current quarter number (1-4+)
- `clock` - Current game clock display (e.g., "12:00")
- `time_remaining` - Time remaining in seconds
- `score` - Current scores `{home_team: X, away_team: Y}`
- `home_lineup` / `away_lineup` - Current lineups (player IDs by position)
- `mode` - "single"
- `players[]` - Player stats (accumulated per quarter)
- `box_score` - Box score data structure
- `is_final` - Boolean flag (true when game is complete)

**Team Context (Stored in team document or game document):**
- Game Plan settings (`teams.{team_id}.strategy_settings`)
- Playbooks settings (`teams.{team_id}.playbook_settings`)

**Timeout State (Stored in game document):**
- `timeout_next_play_type` - "SIDE_INBOUND" or "FREE_THROW"
- `timeout_offense_team_id` - Team that had possession
- `timeout_calling_team` - Team that called timeout

#### Data Flow

**Starting a Game:**
- User selects teams and navigates to Lineup Select Experience
- User sets lineup, then navigates to Game Plan or directly to Gameplay Screen
- Game Plan and Playbooks settings are loaded from `teams.{team_id}`
- Game is initialized via `/api/init-game` endpoint
- Game document is created in `games_collection` with `mode: "single"`
- Settings are applied to game document when game starts

**GP → GP (Navigation Between GP Screens):**
- All settings and state persist via URL parameters
- Core navigation anchor set (`mode`, `team_id`) preserved
- Game state (`game_id`, `quarter`, `clock`) preserved when game is active
- Lineup state preserved via position parameters
- Settings persist via database (loaded from team document on each screen)

**GP → GP (Timeout Navigation):**
- Game state saved to database with `timeout_next_play_type`, `timeout_offense_team_id`
- Navigate to Lineup Select Experience with `game_id`, `quarter`, `clock`, `resume_from_timeout=true`
- All game context preserved via `TimeoutNavigationHelper.buildGameNavigationParams()`
- Backend restores timeout state from database on resume

**GP → GP (Quarter Breaks):**
- Game state persists in database
- Navigate to Lineup Select Experience for next quarter
- `game_id`, `quarter` (incremented), lineup parameters preserved
- Game continues with same game document

**GP → GP (Game Completion):**
- Final stats available in game document
- Box Score shows final game stats
- Game document remains in database for review

#### API Endpoints

**Key Endpoints:**
- `POST /api/init-game` - Initializes new game, creates game document
- `POST /api/simulate-quarter` - Simulates a quarter, returns turn data
- `GET /api/game/{game_id}` - Loads game state from database
- `GET /api/gameplan` - Loads Game Plan settings (`strategy_settings`)
  - **Parameters:** `mode=single`, `team_id={team_name}`, `game_id={game_id}`
- `PUT /api/gameplan` - Saves Game Plan settings
  - **Parameters:** `mode=single`, `team_id={team_name}`, `game_id={game_id}` (optional)
- `GET /api/playbooks` - Loads Playbooks settings (`playbook_settings`)
  - **Parameters:** `mode=single`, `team_id={team_name}`, `game_id={game_id}`
- `POST /api/playbooks` - Saves Playbooks settings
  - **Parameters:** `mode=single`, `team_id={team_name}`, `game_id={game_id}` (optional)

#### User Actions

**Available Actions:**
- Set Lineup (select players for home/away teams)
- Configure Game Plan (strategy settings) - persists to team document
- Configure Playbooks (playbook settings, slot assignments) - persists to team document
- View Play Details (individual play information)
- Start Game (navigate to Gameplay Screen)
- Resume from Timeout (continue game after timeout)
- View Box Score (after game completion)
- Navigate Between GP Screens (Lineup ↔ Game Plan ↔ Playbooks ↔ Play Details ↔ Gameplay)

#### Validation Rules

**Navigation Validation:**
- `mode` must be `"single"`
- `team_id` must be valid team name (string format)
- `game_id` must exist in `games_collection` when game is active
- `game_id` required when `quarter > 1` or `resume_from_timeout=true`

**Game State Validation:**
- `quarter` must be valid (1-4, or higher for overtime)
- `game_id` required when `quarter > 1` or `resume_from_timeout=true`
- Lineup must have 5 players per team (if set)

**Data Validation:**
- Game Plan: At least one offense setting must be > 0
- Playbooks: Container totals must sum to 100% (after filtering)
- Lineup: Each position must have a valid player ID (if lineup is set)

#### Transition Patterns

**Starting Game:**
- Navigate to Lineup Select Experience with `mode=single`, `team_id={team_name}`
- Initialize game document via `/api/init-game`
- Add `game_id` to navigation anchor set after initialization

**GP → GP (Between GP Screens):**
- Preserve navigation anchor set (`mode`, `team_id`)
- Preserve `game_id` if game is active
- Preserve `quarter`, `clock`, `resume_from_timeout` if applicable
- Preserve lineup parameters if lineup is set
- Preserve `from` parameter for back navigation context
- Use `TimeoutNavigationHelper.buildGameNavigationParams()` for consistency

**GP → GP (Timeout Navigation):**
- Preserve navigation anchor set (`mode`, `team_id`)
- Preserve `game_id`, `quarter`, `clock`
- Add `resume_from_timeout=true`
- Preserve all lineup parameters
- Backend saves timeout state to database

**GP → GP (Quarter Breaks):**
- Preserve navigation anchor set (`mode`, `team_id`)
- Preserve `game_id`
- Increment `quarter` parameter
- Preserve lineup parameters (or allow user to change lineup)

#### Known Issues & Fixes

**Issue (February 2025):** `team_id` parameter not being extracted correctly in Single Game mode when navigating from Playbooks → Game Plan.

**Root Cause:**
- In Single Game mode, the URL has `team_id=Four+Corners` (team name format)
- The code was only checking for `home_id`/`away_id` or `user_team_id` (for Tournament/Franchise modes)
- Single Game mode was not checking for `team_id` parameter

**Fix Applied:**
- Added check for `team_id` parameter in Single Game mode (lines 55-60 in `game-plan.js`)
- Ensures `team_id` is extracted from URL when `mode=single`
- Allows Game Plan settings to load/save correctly in Single Game mode

**Code Pattern:**
```javascript
// ✅ CORRECT: Check for team_id parameter in Single Game mode
if (modeParam === 'single') {
  const teamIdParam = urlParams.get('team_id');
  if (teamIdParam) {
    teamId = teamIdParam;
    teamName = teamIdParam; // In single mode, team_id is the team name
  }
}
```

---

## GP Supporting Systems

### Energy System

**Location:** `BackEnd/utils/energy_system.py`, `BackEnd/main.py`, `BackEnd/models/game_manager.py`, `BackEnd/engine/phase_resolution.py`

**Overview:**
The Energy System manages player energy depletion during active gameplay and energy restoration during breaks (quarter breaks, halftime, timeouts). Energy affects player performance through the NG (Natural Growth) attribute, which scales other attributes.

#### Energy Replenishment

**1. Quarter Break Recharge (Non-Halftime)**
- **When:** Between Q1→Q2, Q3→Q4, or before any overtime quarters
- **Who:** All active lineup players (10 players total)
- **Amount:** Random per player from `[0.7, 0.8, 0.9, 1.0, 1.1, 1.2]`
- **Code Location:** `BackEnd/main.py` - `simulate_quarter()` (lines 414-422)

**2. Halftime Break Recharge**
- **When:** Between Q2→Q3 (halftime break)
- **Who:** All active lineup players (10 players total)
- **Amount:** Random per player from `[1.5, 1.6, 1.7, 1.8, 1.9, 2.0]`
- **Code Location:** `BackEnd/main.py` - `simulate_quarter()` (lines 416-418)

**3. Timeout Break Recharge**
- **When:** At the start of any timeout (user-initiated, computer-initiated, or foul out)
- **Who:** All players (active lineup + bench players)
- **Amount:** Random per player from `[0.03, 0.04, 0.05, 0.06]`
- **Code Location:** `BackEnd/models/game_manager.py` - `call_timeout()` (lines 217-225)
- **Note:** Recharge happens before lineup selection screen, so user sees updated energy values

**4. Bench Recharge**
- **When:** During HCO (Half Court Offense) turns only
- **Who:** All bench players (players not in active lineup)
- **Amount:** Per turn, per bench player:
  - 20% chance: no recharge (0)
  - 70% chance: +0.01 energy
  - 10% chance: +0.02 energy
- **Code Location:** `BackEnd/engine/phase_resolution.py` - `apply_bench_energy_recharge()` (lines 80-113), called from `resolve_half_court_offense_logic()` (line 3630)
- **⚠️ IMPORTANT:** Bench recharge does NOT happen during Fast Break, FCP, or HCT turns - only during HCO turns

#### Energy Depletion

**When:** Applied to all 10 active lineup players during the following turn types:
- **HCO** (Half Court Offense) turns
- **Fast Break** turns
- **FCP** (Full Court Press) turns
- **HCT** (Half Court Trap) turns

**Amount:** Determined by each player's `get_fatigue_decay_amount()` method, which is based on their **ND (Natural Durability)** attribute.

**Code Locations:**
- `BackEnd/engine/phase_resolution.py` - `apply_energy_decay()` (lines 60-77)
- Called from:
  - `resolve_half_court_offense_logic()` (line 3627)
  - `resolve_fast_break_logic()` (line 689)
  - `resolve_full_court_press_logic()` (line 4279)
  - `resolve_half_court_trap_logic()` (line 5272)

**Depletion Calculation:**
The `get_fatigue_decay_amount()` method in `BackEnd/models/player.py` uses the player's ND attribute to determine depletion:
- Higher ND = less energy depletion per turn
- Lower ND = more energy depletion per turn
- Returns a random amount based on ND thresholds

#### Summary

| Situation | Who | Amount | Frequency |
|-----------|-----|--------|-----------|
| Quarter Break (non-halftime) | Active lineup | Random: [0.7, 0.8, 0.9, 1.0, 1.1, 1.2] | Per quarter break |
| Halftime Break | Active lineup | Random: [1.5, 1.6, 1.7, 1.8, 1.9, 2.0] | Once per game |
| Timeout | All players | Random: [0.03, 0.04, 0.05, 0.06] | Per timeout |
| Bench Recharge | Bench players | 20%: 0, 70%: +0.01, 10%: +0.02 | Per HCO turn only |
| Energy Depletion | Active lineup | ND-based (via `get_fatigue_decay_amount()`) | Per HCO/Fast Break/FCP/HCT turn |

---

### Computer Team Strategy Settings

**Location:** `BackEnd/models/team_manager.py` - `_init_strategy_settings()` method

**Overview:**
When computer teams are initialized (for all game modes: Single Game, Tournament, Franchise), their `strategy_settings` are randomly generated using weighted distributions. This ensures most teams play with balanced strategies (value = 2), while some teams have more extreme preferences.

**Initialization Method:**
- **Code Location:** `BackEnd/models/team_manager.py` - `_init_strategy_settings()` (lines 118-141)
- **When Called:** During `TeamManager.__init__()` when `strategy_settings` is not provided or is empty
- **Applies To:** All game modes (Single Game, Tournament, Franchise)

#### Strategy Settings Distribution

**Weighted Distribution (Most Settings):**
The following settings use a weighted random distribution that favors balanced play (value = 2):
- `offense` - Motion vs Set Play split (0=motion only, 4=set plays only)
- `tempo` - Pace of play preference
- `defense` - Man vs Zone defense preference (0=man only, 4=zone only)
- `aggression` - Defensive aggression level
- `hc_trap` - Half court trap usage preference
- `fc_press` - Full court press usage preference
- `rebounding` - Crash boards vs get back preference

**Weighted Distribution Probabilities:**
- **5% chance** for value **0** (extreme low)
- **15% chance** for value **1** (low)
- **60% chance** for value **2** (normal/balanced) ⭐
- **15% chance** for value **3** (high)
- **5% chance** for value **4** (extreme high)

**Uniform Distribution (Shot Focus Settings):**
The following settings use uniform random distribution (1-4, never zero):
- `inside` - Inside shot focus preference
- `attack` - Attack shot focus preference
- `outside` - Outside shot focus preference

**Uniform Distribution Range:**
- Random integer from **1 to 4** (inclusive)
- **Never zero** - ensures teams always have some preference for each shot type

#### Implementation Details

**Code Pattern:**
```python
# Weighted distribution for most settings
weighted_choice = random.choices(
    [0, 1, 2, 3, 4],
    weights=[5, 15, 60, 15, 5],  # 5%, 15%, 60%, 15%, 5%
    k=1
)[0]

# Uniform distribution for shot focus settings
inside = random.randint(1, 4)  # Never zero
```

**Future Enhancements:**
- Current implementation uses simple weighted randomization
- Future versions may implement more strategic AI that considers:
  - Team strengths/weaknesses
  - Opponent tendencies
  - Game situation (score, time remaining)
  - Player matchups

#### Summary Table

| Setting | Distribution | Range | Notes |
|---------|-------------|-------|-------|
| `offense` | Weighted | 0-4 | 60% chance of 2 (balanced) |
| `inside` | Uniform | 1-4 | Never zero |
| `attack` | Uniform | 1-4 | Never zero |
| `outside` | Uniform | 1-4 | Never zero |
| `tempo` | Weighted | 0-4 | 60% chance of 2 (balanced) |
| `defense` | Weighted | 0-4 | 60% chance of 2 (balanced) |
| `aggression` | Weighted | 0-4 | 60% chance of 2 (balanced) |
| `hc_trap` | Weighted | 0-4 | 60% chance of 2 (balanced) |
| `fc_press` | Weighted | 0-4 | 60% chance of 2 (balanced) |
| `rebounding` | Weighted | 0-4 | 60% chance of 2 (balanced) |

---

### OREB System

**Location:** `BackEnd/utils/shared.py` - `resolve_offensive_rebound()` and `oreb_shot_attempt()` functions

**Overview:**
The OREB (Offensive Rebound) System handles offensive rebounds and putback attempts. When a player secures an offensive rebound, they have a 90% chance to attempt a putback shot and a 10% chance to kick the ball out to reset the offense.

#### Putback Shot Calculation

**Shot Score Formula:**
Putback attempts use a dedicated `oreb_shot_attempt()` function that calculates shot score based on finishing ability:
- **SC (Shooting Close)** × 0.5
- **ST (Strength)** × 0.3
- **CH (Clutch)** × 0.2
- Multiplied by random die roll (1-6)

**Code Location:** `BackEnd/utils/shared.py` - `oreb_shot_attempt()` function (lines 118-130)

**Formula:**
```python
shot_score = (
    player_attrs["SC"] * 0.5 +
    player_attrs["ST"] * 0.3 +
    player_attrs["CH"] * 0.2
) * random.randint(1, 6)
```

#### Defense Penalty

After calculating the base shot score, a defense penalty is applied:
- Defender is randomly selected (weighted toward bigs: C, C, C, PF, PF, SF, SF, SG, PG)
- Defense penalty formula:
  - **ID (Interior Defense)** × 0.6
  - **ST (Strength)** × 0.2
  - **IQ (Intelligence)** × 0.1
  - **CH (Clutch)** × 0.1
  - Multiplied by random die roll (1-6) × 0.7
- Defense penalty is subtracted from shot score

**Code Location:** `BackEnd/utils/shared.py` - `resolve_offensive_rebound()` function (lines 145-154)

#### Shot Threshold

**Uniform Threshold:** All OREB putback attempts use a **uniform shot threshold of 0**.

This means putback success is determined purely by:
- Player's finishing ability (SC, ST, CH)
- Defender's defensive ability (ID, ST, IQ, CH)
- Random die rolls

**Code Location:** `BackEnd/utils/shared.py` - `resolve_offensive_rebound()` function (line 159)

**Comparison:**
```python
oreb_threshold = 0
made = shot_score >= oreb_threshold
```

**Note:** This is different from regular shots, which use the team's `shot_threshold` attribute (0-200 range). Putbacks use a fixed threshold of 0, making them more dependent on player attributes and defensive pressure.

#### Putback vs Kickout Decision

**90% Putback Attempt:**
- Player attempts immediate putback shot
- Uses `oreb_shot_attempt()` calculation
- Threshold = 0

**10% Kickout:**
- Player passes ball out to PG
- Resets offense (no shot attempt)
- Time elapsed: 1-3 seconds

**Code Location:** `BackEnd/utils/shared.py` - `resolve_offensive_rebound()` function (line 136)

#### Putback Outcomes

**Make:**
- 2 points scored
- FGM, FGA, PTS, PIP stats recorded
- Possession flips (defense gets ball)
- Time elapsed: 2-5 seconds

**Miss:**
- DEF_S stat recorded for defender
- Rebound determined (can be OREB or DREB)
- If DREB: possession flips
- If OREB: same team continues (can result in consecutive putback attempts)
- Time elapsed: 2-5 seconds

#### Summary

| Aspect | Details |
|--------|---------|
| **Shot Score Formula** | SC × 0.5 + ST × 0.3 + CH × 0.2, multiplied by die roll (1-6) |
| **Defense Penalty** | ID × 0.6 + ST × 0.2 + IQ × 0.1 + CH × 0.1, multiplied by die roll (1-6) × 0.7 |
| **Shot Threshold** | **0** (uniform for all putback attempts) |
| **Putback Chance** | 90% |
| **Kickout Chance** | 10% |
| **Points** | Always 2 (putbacks are from paint) |
| **Time Elapsed** | 2-5 seconds |

---

## Data & Settings Persistence

> **Last Updated:** February 2025  
> **Purpose:** Documents the single source of truth architecture for data persistence across all game modes

### Single Source of Truth Principle

**Core Principle:** The database (API) is the **single source of truth** for all persistent data. localStorage is reserved **only** for temporary UI preferences that don't affect gameplay or data consistency.

**Why This Matters:**
- **Consistency:** Eliminates synchronization bugs between localStorage and database
- **Reliability:** Database is authoritative - no stale data from localStorage cache
- **Simplicity:** One code path for all modes (no mode-specific localStorage logic)
- **Stability:** Settings persist correctly across all navigation scenarios (timeouts, quarter breaks, gameplay breaks)

### What Uses Database (Persistent Data)

**All persistent data is stored in the database and loaded via API:**

1. **Game Plan Settings (`strategy_settings`)**
   - Stored in: `franchise_teams.{team_id}.strategy_settings` (Franchise), `teams.{team_id}.strategy_settings` (Tournament/Single)
   - Loaded via: `GET /api/gameplan`
   - Saved via: `PUT /api/gameplan`
   - **All modes:** Single, Tournament, Franchise

2. **Playbooks Settings (`playbook_settings`)**
   - Stored in: `franchise_teams.{team_id}.playbook_settings` (Franchise), `teams.{team_id}.playbook_settings` (Tournament/Single)
   - Loaded via: `GET /api/playbooks`
   - Saved via: `POST /api/playbooks`
   - Includes: Percentages, slot assignments, motion dropdowns, position filters
   - **All modes:** Single, Tournament, Franchise

3. **Game State**
   - Stored in: `games_collection` (game documents)
   - Includes: Scores, quarter, clock, lineups, player stats, box score
   - **All modes:** Single, Tournament, Franchise

4. **Team/Player Data**
   - Stored in: Franchise/Tournament documents, `teams_collection`, `players_collection`
   - Includes: Attributes, stats, plays data, scouting data
   - **All modes:** Single, Tournament, Franchise

### What Uses localStorage (Temporary UI State Only)

**localStorage is used ONLY for ephemeral UI preferences that don't affect data consistency:**

1. **Position Filter Selections** (Playbooks)
   - Key: `playbooks_position_filters_{mode}_{teamId}`
   - Purpose: Remembers which position filter buttons are selected (Standard, PG, SG, SF, PF, C)
   - **Why localStorage:** UI preference only - doesn't affect saved playbook percentages
   - **Location:** `playbooks.js` - `savePositionFilterSelections()`, `loadPositionFilterSelections()`

2. **Even Distribution Toggle States** (Playbooks)
   - Stored in: Playbooks UI state (not persisted to database)
   - Purpose: Remembers toggle state for "Even Distribution" buttons per container
   - **Why localStorage:** UI preference only - percentages are what matter, not toggle state
   - **Note:** Toggle state is not saved to database (only the resulting percentages are saved)

3. **Navigation Context** (Fallback only)
   - Keys: `franchise_id`, `franchise_week`, `game_id` (as fallback if URL params missing)
   - Purpose: Fallback for navigation if URL parameters are lost
   - **Why localStorage:** Navigation convenience only - database is still source of truth
   - **Note:** URL parameters are primary, localStorage is fallback only

### What Does NOT Use localStorage

**The following were previously using localStorage but now use database exclusively:**

1. ❌ **Game Plan Settings** - Now uses database for all modes (previously localStorage for single mode)
2. ❌ **Playbooks Settings** - Now uses database for all modes (previously localStorage cache)
3. ❌ **Playbook Percentages** - Now uses database (previously localStorage full state cache)
4. ❌ **Slot Assignments** - Now uses database (previously localStorage full state cache)
5. ❌ **Motion Dropdowns** - Now uses database (previously localStorage full state cache)

### Implementation Details

**Loading Pattern (All Modes):**
```javascript
// ✅ CORRECT: Always load from database
const params = new URLSearchParams();
params.set('mode', mode);
params.set('team_id', teamId);
if (mode === 'franchise' && franchiseId) params.set('franchise_id', franchiseId);
if (mode === 'tournament' && tournamentId) params.set('tournament_id', tournamentId);
if (mode === 'single' && gameId) params.set('game_id', gameId);

const res = await fetch(`/api/gameplan?${params.toString()}`);
const settings = await res.json();
```

**Saving Pattern (All Modes):**
```javascript
// ✅ CORRECT: Always save to database
const payload = {
  mode,
  team_id: teamId,
  playcall_settings: currentSettings.playcall_settings,
  strategy_settings: currentSettings.strategy_settings
};
if (mode === 'franchise' && franchiseId) payload.franchise_id = franchiseId;
if (mode === 'tournament' && tournamentId) payload.tournament_id = tournamentId;
if (mode === 'single' && gameId) payload.game_id = gameId;

await fetch('/api/gameplan', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload)
});
```

**❌ WRONG Patterns (Removed):**
```javascript
// ❌ WRONG: Don't use localStorage for persistent data
localStorage.setItem(`gameplan_${teamName}`, JSON.stringify(settings));

// ❌ WRONG: Don't use URL params for settings data
params.set('game_plan_settings', JSON.stringify(settings));

// ❌ WRONG: Don't cache playbook data in localStorage
localStorage.setItem(`playbooks_full_state_${mode}_${teamId}`, JSON.stringify(fullState));
```

### Benefits of This Architecture

1. **No Synchronization Bugs:** Database is always authoritative - no localStorage/database conflicts
2. **Consistent Behavior:** Same code path for all modes (no mode-specific localStorage logic)
3. **Reliable Persistence:** Settings persist correctly across all navigation scenarios
4. **Simpler Code:** One source of truth = less code complexity
5. **Easier Debugging:** Single source makes it easier to trace data flow

### Migration Notes

**Refactored (February 2025):**
- Removed localStorage caching for playbook settings (percentages, slots, dropdowns)
- Removed localStorage for game plan settings in single mode
- Removed URL param approach for `game_plan_settings`
- All modes now use database exclusively for persistent data
- localStorage reserved only for temporary UI preferences

**Files Updated:**
- `FrontEnd/static/playbooks.js` - Removed full state localStorage caching
- `FrontEnd/static/game-plan.js` - Removed localStorage for single mode, removed URL param approach
- `FrontEnd/static/js/phaser/bootGame.js` - Always load from database for all modes
- `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js` - Removed URL param approach

---
