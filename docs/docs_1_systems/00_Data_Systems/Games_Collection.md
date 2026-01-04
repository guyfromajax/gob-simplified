# Games Collection ✅ **PARTIALLY DOCUMENTED** (January 2025)

## Base Constants

**Purpose:** Documents the MongoDB `games` collection structure and how game documents are stored after gameplay.

**Collection:** `games`  
**Location:** MongoDB `games` collection  
**Key Files:**
- `BackEnd/utils/shared.py` - `summarize_game_state()` (saves game documents)
- `BackEnd/api/franchise_routes.py` - `get_scouting_report()` (queries game documents)
- `BackEnd/api/api.py` - Game initialization and quarter simulation endpoints

## Game Document Structure

### Core Fields

**Game Identification:**
- `_id` (ObjectId) - Game document ID (generated UUID or ObjectId)
- `game_id` (str) - Duplicate game identifier (for compatibility)
- `mode` (str) - Game mode: "single", "tournament", or "franchise"
- `franchise_id` (str) - Franchise ID (for franchise mode only)
- `tournament_id` (str) - Tournament ID (for tournament mode only)
- `week` (int) - Week number (for franchise mode only)

**Game State:**
- `quarter` (int) - Current quarter number (1-4, or 5+ for overtime)
- `is_final` (bool) - Whether the game is completed
- `clock` (str) - Game clock (e.g., "8:00")
- `time_remaining` (int) - Time remaining in seconds
- `opening_tip_winner` (str) - Team that won opening tip (team_id string)

**Team Identification:**
- `home_team_id` (str) - Home team identifier (team_id string like "XAVIEN")
- `away_team_id` (str) - Away team identifier (team_id string like "LANCASTER")
- `home_team` (dict) - Home team data (score, points_by_quarter, box_score, etc.)
- `away_team` (dict) - Away team data (score, points_by_quarter, box_score, etc.)

**Teams Object:**
- `teams` (dict) - Team data keyed by team_id strings (e.g., `{"XAVIEN": {...}, "LANCASTER": {...}}`)
  - Keys are `team_id` strings (like "XAVIEN"), NOT ObjectId strings
  - Each team entry contains:
    - `strategy_settings` (dict) - Strategy settings (0-4 scale)
    - `strategy_calls` (dict) - User override calls
    - `plays` (dict) - Plays data with `game_stats` (play usage, success tracking)
    - `attributes` (dict) - Team attributes (shot_threshold, discipline, fight, etc.)
    - `scouting` (dict) - Scouting data (offense/defense tracking)
    - `playbook_settings` (dict) - Playbook distribution settings

**Players:**
- `players` (array) - Array of player objects with stats and attributes

**Game Data:**
- `score` (dict) - Score object: `{team_name: score}`
- `text_log` (array) - Game event log
- `turns` (array) - Turn data (empty for persisted games, excluded for database saves)

**Note:** The `turns` array is excluded from database saves (`exclude_animations=True` in `summarize_game_state()`) to prevent document size issues. Only game state metadata is persisted.

## Key Features

### Team Identification Fields

**Critical Fix (January 2025):**
- Game documents use `home_team_id` and `away_team_id` fields (team_id strings like "XAVIEN")
- These fields store `team_id` strings (e.g., "XAVIEN", "LANCASTER"), NOT ObjectId strings
- The `teams` object uses the same `team_id` strings as keys (e.g., `teams["XAVIEN"]`)
- **Previous Bug:** Scouting report queries incorrectly used `team1_id` and `team2_id` fields (which don't exist)
- **Fix:** Updated queries to use `home_team_id` and `away_team_id` fields with `team_id` string values

**Example Game Document:**
```json
{
  "_id": "695998fbce8a88b9d679262b",
  "game_id": "695998fa44b63e818daa513b",
  "mode": "franchise",
  "franchise_id": "69599145dc6870562452e70f",
  "week": 3,
  "home_team_id": "XAVIEN",
  "away_team_id": "LANCASTER",
  "teams": {
    "XAVIEN": {
      "plays": {
        "4-1 Motion": {
          "game_stats": {
            "times_run": 5,
            "successes": 3
          }
        }
      }
    },
    "LANCASTER": {
      "plays": {...}
    }
  }
}
```

### Querying Games

**For Scouting Reports:**
- Query using `home_team_id` and `away_team_id` fields (NOT `team1_id` / `team2_id`)
- Match against `team_id` strings (like "XAVIEN"), NOT ObjectId strings
- Example query:
  ```python
  last_game = db.games.find_one(
      {
          "franchise_id": str(franchise_id),
          "$or": [
              {"home_team_id": team_id_field},  # team_id string like "XAVIEN"
              {"away_team_id": team_id_field}
          ]
      },
      sort=[("_id", -1)]
  )
  ```

## System Flow

1. **Game Initialization**: Game document created with `home_team_id` and `away_team_id` (team_id strings)
2. **Gameplay**: Game state updated during gameplay (quarter saves, turn data)
3. **Game Completion**: Final game state saved via `summarize_game_state()` with `exclude_animations=True`
4. **Data Persistence**: Game document stored in `games` collection with full game state (except turns)
5. **Scouting Reports**: Games queried using `home_team_id` / `away_team_id` to retrieve plays data

## Long Form Documentation

### Game Document Creation

**Initialization:**
- Game documents are created during game initialization (`init_game()` endpoint)
- `home_team_id` and `away_team_id` are set from `TeamManager.team_id` (team_id strings like "XAVIEN")
- The `teams` object is populated with team data keyed by the same `team_id` strings

**During Gameplay:**
- Game state is saved periodically (quarter completions, turn saves)
- The `teams` object is updated with current team state (plays, scouting, strategy_settings)
- `plays` data includes `game_stats` tracking (times_run, successes, etc.)

**After Gameplay:**
- Final game state saved via `summarize_game_state()` with `exclude_animations=True`
- `turns` array is excluded (empty array) to prevent document size issues
- All game state metadata is persisted (score, teams object, players, box_score)

### Scouting Report Integration

**Query Pattern:**
- Scouting reports query the `games` collection for the last completed game for a team
- Query uses `home_team_id` and `away_team_id` fields (team_id strings)
- Matches against `team_id` field value from the teams collection (e.g., "XAVIEN")

**Plays Data Retrieval:**
- After finding the game document, extracts `teams` object
- Matches team key using `team_id` field (Strategy 1 in matching logic)
- Retrieves `plays` data from `teams[team_id]["plays"]`
- Filters plays with `times_run > 0` to show only plays that were actually executed

**Fix (January 2025):**
- Updated `get_scouting_report()` in `BackEnd/api/franchise_routes.py` (lines 1678-1692)
- Changed query from `team1_id` / `team2_id` (non-existent fields) to `home_team_id` / `away_team_id`
- Changed match value from ObjectId string to `team_id` string (like "XAVIEN")
- Moved `team_id_field` lookup earlier in the function (line 1674)

### Teams Object Structure

**Key Format:**
- Keys are `team_id` strings (like "XAVIEN", "LANCASTER"), NOT ObjectId strings
- These match the `home_team_id` and `away_team_id` fields in the game document
- This format is consistent across all game documents

**Team Data:**
- Each team entry in the `teams` object contains:
  - `plays` (dict) - Plays data with `game_stats` (times_run, successes, effectiveness)
  - `scouting` (dict) - Scouting data (offense/defense tracking, playcall stats)
  - `attributes` (dict) - Team attributes (shot_threshold, discipline, fight, etc.)
  - `strategy_settings` (dict) - Strategy settings (0-4 scale)
  - `strategy_calls` (dict) - User override calls
  - `playbook_settings` (dict) - Playbook distribution settings

## Key Files

- **`BackEnd/utils/shared.py`** - `summarize_game_state()` (lines 709-1003)
  - Creates game document structure
  - Sets `home_team_id` and `away_team_id` from `TeamManager.team_id`
  - Populates `teams` object with team data keyed by `team_id` strings

- **`BackEnd/api/franchise_routes.py`** - `get_scouting_report()` (lines 1647-1756)
  - Queries games collection using `home_team_id` / `away_team_id`
  - Extracts plays data from `teams` object
  - **Fixed (January 2025):** Query now uses correct fields and match values

- **`BackEnd/api/api.py`** - Game initialization endpoints
  - `init_game()` - Creates initial game document
  - `simulate_quarter_endpoint()` - Saves game state during gameplay

## Future Documentation

This document will be expanded with:
- Complete field descriptions for all game document fields
- Detailed structure of nested objects (teams, players, box_score)
- Query patterns for different use cases
- Data persistence patterns across game modes
- Document size optimization strategies

