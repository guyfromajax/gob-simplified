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

