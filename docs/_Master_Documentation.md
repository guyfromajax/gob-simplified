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
- Game Plan and Playbooks settings are loaded from `franchise_teams.{team_id}`
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
- `POST /api/playbooks` - Saves Playbooks settings
- `POST /api/franchise/training` - Runs training session, updates attributes/stats
- `GET /api/training-report` - Loads training report data

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

*[To be documented]*

---

