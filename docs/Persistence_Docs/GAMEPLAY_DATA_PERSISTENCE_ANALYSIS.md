# Gameplay Data Persistence Analysis

**Date:** January 2025  
**Purpose:** Review data persistence when user presses Play Quarter, Sim To 4th Quarter, and Sim Full Game buttons across all three modes (Single Game, Tournament, Franchise)

---

## Overview

This document analyzes what data is actually persisted to the database when the user presses each of the three gameplay buttons, compares it against the documented data requirements, and identifies any discrepancies.

**Reference Documentation:**
- `docs/NAVIGATION_DATA_REQUIREMENTS.md` - Bucket 3 (Gameplay) data requirements
- `docs/COMMON_DATA_SET.md` - Common data structure across modes
- `docs/master_game_doc.md` - Data Persistence section

---

## Data Persistence Function: `summarize_game_state()`

**Location:** `BackEnd/utils/shared.py` (lines 507-786)

**Key Behavior:**
- **Database Saves:** `exclude_animations=True` → `turns = []` (empty array, no animations saved)
- **Frontend Response:** `exclude_animations=False` → `turns = deepcopy(game.turns)` (full turn data with animations)

**What Gets Persisted (All Modes):**

### Core Game State
- `game_id` - Game identifier
- `quarter` - Current quarter number
- `is_final` - Boolean (game complete)
- `opening_tip_winner` - Team that won opening tip
- `game_stats_initialized` - Flag for stats initialization
- `user_team_side` - "home" or "away" (user's team)
- `timeout_next_play_type` - Next play type after timeout (if applicable)
- `timeout_offense_team_id` - Offense team ID after timeout (if applicable)
- `clock` - Game clock (e.g., "8:00")
- `time_remaining` - Time remaining in seconds

### Score Data
- `score` - Top-level score map `{team_name: score}`
- `home_team_id` / `away_team_id` - Team ObjectIds

### Team Data (Nested)
- `home_team` - Full home team object:
  - `name`, `team_id`, `mascot`
  - `colors` (primary_color, secondary_color)
  - `score`, `points_by_quarter`, `team_fouls`, `timeouts`
  - `attributes` (team attributes)
  - `box_score` (player stats)
  - `totals` (team totals)
- `away_team` - Same structure as `home_team`

### Teams Object (By team_id)
- `teams.{team_id}` - Team state for persistence:
  - `strategy_settings` - Current strategy settings
  - `plays` - All plays with effectiveness, momentum, cloaking
  - `attributes` - Team attributes
  - `scouting` - Scouting data (defensive plays)
  - `playbook_settings` - Playbook settings including:
    - `motion`, `set_play_inside`, `set_play_attack`, `set_play_outside` - Play percentages by section
    - `zone_defense`, `man_defense` - Defense play percentages
    - `slot_assignments` - Playcall Center six plays (slots 1-6)
    - `motion_dropdowns` - Motion play dropdown selections (Inside/Attack/Outside)
    - `position_filters` - Position filter button assignments
    - ✅ **PRESERVED** from database when saving game state
    - ✅ **CROSS-INSTANCE PERSISTENCE (Single Game)**: Settings saved to core `teams` collection for persistence across Single Game instances

### Players Array
- `players[]` - Array of all players (lineup + referenced players):
  - `playerId`, `name`, `team`, `team_id`, `pos`, `jersey`, `photo`
  - `primary_color`, `secondary_color`
  - `x`, `y` (coordinates)
  - `stats` (game stats)
  - `attributes` (EM, CH, MO, NG)

### Game Data
- `turns` - **Empty array for database saves** (animations excluded)
- `text_log` - Game text log

### Mode-Specific Fields
- **Franchise:** `franchise_id`, `week` (added when game result is saved via `save_result()` or `_save_game_result()`, NOT during quarter saves)
- **Tournament:** `tournament_id`, `mode` (added during `simulate_quarter_endpoint()` saves at lines 1911-1913)
- **Single Game:** None (no mode-specific fields)

---

## Button Analysis

### 1. Play Quarter Button

**Frontend Handler:** `FrontEnd/static/js/phaser/bootGame.js:388-443` (`handleButtonClick()`)

**Backend Endpoint:** `POST /api/simulate-quarter` (`BackEnd/api/api.py:767-1650`)

**Flow:**
1. User clicks "Play Quarter" button
2. Frontend calls `startGame()` which makes turn-by-turn requests to `/api/simulate-turn`
3. Each turn is saved to database (every 10 turns or on quarter completion)
4. Quarter completion triggers final save via `summarize_game_state()`

**Data Persisted:**
- ✅ All core game state fields
- ✅ Full team data (home_team, away_team, teams object)
- ✅ Full players array
- ✅ Game metadata (quarter, score, clock, etc.)
- ⚠️ Mode-specific fields (tournament_id/mode for Tournament mode added during saves; franchise_id/week for Franchise mode added later when result is saved)

**Mode-Specific Behavior:**

#### Single Game Mode
- **Storage:** `games_collection` with `game_id` as `_id`
- **Fields Added:** None (just core game state)
- **Status:** ✅ **ALIGNED** - Matches documentation

#### Tournament Mode
- **Storage:** `games_collection` with `game_id` as `_id`
- **Fields Added:** `tournament_id` and `mode` (added during `simulate_quarter_endpoint()` saves at lines 1911-1913)
- **Status:** ✅ **ALIGNED** - `tournament_id` and `mode` are always set during quarter saves, regardless of game creation path

#### Franchise Mode
- **Storage:** `games_collection` with `game_id` as `_id` (ObjectId format, not composite key)
- **Fields Added During Gameplay:** `mode` only (added during `simulate_quarter_endpoint()` saves)
- **Fields Added When Result Saved:** `franchise_id`, `week` (added via `save_result()` at lines 331-336 or `_save_game_result()` at line 186)
- **Status:** ✅ **ALIGNED** - During gameplay, only `mode` is added. `franchise_id` and `week` are added later when the game result is saved (after gameplay completes)

---

### 2. Sim To 4th Quarter Button

**Frontend Handler:** `FrontEnd/static/js/phaser/bootGame.js:445-608` (`handleSimToFourth()`)

**Backend Endpoint:** `POST /api/simulate-quarter` (called multiple times for Q1-Q3)

**Flow:**
1. User clicks "Sim To 4th Quarter" button
2. Frontend loops through Q1, Q2, Q3:
   - Calls `/api/simulate-quarter` with `full_sim=true`
   - Each quarter is fully simulated (no animations)
   - Each quarter is saved to database
3. After Q3, user is redirected to set-lineup for Q4
4. Q4 is played normally (Play Quarter button)

**Data Persisted (Per Quarter Q1-Q3):**
- ✅ All core game state fields
- ✅ Full team data (home_team, away_team, teams object)
- ✅ Full players array
- ✅ Game metadata (quarter, score, clock, etc.)
- ⚠️ Mode-specific fields (tournament_id/mode for Tournament mode added during saves; franchise_id/week for Franchise mode added later when result is saved)

**Mode-Specific Behavior:**

#### Single Game Mode
- **Storage:** `games_collection` with `game_id` as `_id`
- **Fields Added:** None (just core game state)
- **Status:** ✅ **ALIGNED** - Matches documentation

#### Tournament Mode
- **Storage:** `games_collection` with `game_id` as `_id`
- **Fields Added:** `tournament_id` and `mode` (added during `simulate_quarter_endpoint()` saves at lines 1911-1913)
- **Status:** ✅ **ALIGNED** - `tournament_id` and `mode` are always set during quarter saves, regardless of game creation path

#### Franchise Mode
- **Storage:** `games_collection` with `game_id` as `_id` (ObjectId format, not composite key)
- **Fields Added During Gameplay:** `mode` only (added during `simulate_quarter_endpoint()` saves)
- **Fields Added When Result Saved:** `franchise_id`, `week` (added via `save_result()` at lines 331-336 or `_save_game_result()` at line 186)
- **Status:** ✅ **ALIGNED** - During gameplay, only `mode` is added. `franchise_id` and `week` are added later when the game result is saved (after gameplay completes)

**Note:** The `game_id` is preserved across all quarters (Q1 → Q2 → Q3), so the same game document is updated multiple times.

---

### 3. Sim Full Game Button

**Frontend Handler:** `FrontEnd/static/js/phaser/bootGame.js:610-830` (`handleSimFullGame()`)

**Backend Endpoint:** `POST /api/simulate-quarter` (called multiple times for Q1-Q4)

**Flow:**
1. User clicks "Sim Full Game" button
2. Frontend loops through Q1, Q2, Q3, Q4:
   - Calls `/api/simulate-quarter` with `full_sim=true`
   - Each quarter is fully simulated (no animations)
   - Each quarter is saved to database
3. After Q4 completes, game completion popup is shown
4. User is redirected to command center (tournament/franchise) or mode select (single game)

**Data Persisted (Per Quarter Q1-Q4):**
- ✅ All core game state fields
- ✅ Full team data (home_team, away_team, teams object)
- ✅ Full players array
- ✅ Game metadata (quarter, score, clock, etc.)
- ⚠️ Mode-specific fields (tournament_id/mode for Tournament mode added during saves; franchise_id/week for Franchise mode added later when result is saved)

**Mode-Specific Behavior:**

#### Single Game Mode
- **Storage:** `games_collection` with `game_id` as `_id`
- **Fields Added:** None (just core game state)
- **Status:** ✅ **ALIGNED** - Matches documentation

#### Tournament Mode
- **Storage:** `games_collection` with `game_id` as `_id`
- **Fields Added:** `tournament_id` and `mode` (added during `simulate_quarter_endpoint()` saves at lines 1911-1913)
- **Status:** ✅ **ALIGNED** - `tournament_id` and `mode` are always set during quarter saves, regardless of game creation path

#### Franchise Mode
- **Storage:** `games_collection` with `game_id` as `_id` (ObjectId format, not composite key)
- **Fields Added During Gameplay:** `mode` only (added during `simulate_quarter_endpoint()` saves)
- **Fields Added When Result Saved:** `franchise_id`, `week` (added via `save_result()` at lines 331-336 or `_save_game_result()` at line 186)
- **Status:** ✅ **ALIGNED** - During gameplay, only `mode` is added. `franchise_id` and `week` are added later when the game result is saved (after gameplay completes)

**Note:** The `game_id` is preserved across all quarters (Q1 → Q2 → Q3 → Q4), so the same game document is updated multiple times. After Q4, `is_final=true` is set.

---

## Discrepancies Identified

### ✅ RESOLVED: Tournament Mode `tournament_id` Now Always Set

**Issue:** Tournament mode game documents may not include `tournament_id` field if the game is created directly via `simulate_quarter_endpoint()` without going through `init_game()`.

**Previous Behavior:**
- **Normal Flow (set-lineup.html → init-game → simulate-quarter):**
  - `init_game()` sets `tournament_id` and `mode` in game document (lines 2141-2143)
  - `simulate_quarter_endpoint()` saves with `{"$set": db_summary}` which preserves existing fields
  - ✅ `tournament_id` is preserved throughout the game
- **Direct Flow (bypassing init-game):**
  - If game is created directly via `simulate_quarter_endpoint()` (e.g., from bootGame.js without set-lineup), `tournament_id` was NOT set
  - ❌ Game document could not be linked back to tournament

**Current Behavior (After Fix):**
- ✅ `tournament_id` and `mode` are now ALWAYS set during `simulate_quarter_endpoint()` saves
- ✅ Works for both normal flow and direct game creation
- Note: Franchise mode adds `franchise_id` and `week` when the game result is saved (not during quarter saves)

**Implementation:**
- `BackEnd/api/api.py:1636-1650` - `simulate_quarter_endpoint()` now adds `tournament_id` and `mode` to game document when saving
- Mode is inferred from `tournament_id`/`franchise_id` if not provided in request
- Note: Franchise mode adds `franchise_id` and `week` when the game result is saved (via `save_result()` or `_save_game_result()`), not during quarter saves

**Status:** ✅ **RESOLVED** - Tournament mode now consistently includes `tournament_id` and `mode` in game documents, regardless of game creation path.

---

## Alignment with Documentation

### Bucket 3 (Gameplay) Data Requirements

**Documentation:** `docs/NAVIGATION_DATA_REQUIREMENTS.md` (lines 200-283)

**Required State Data:**
- ✅ `game_id` - Persisted
- ✅ `quarter` - Persisted
- ✅ `score` - Persisted
- ✅ `clock` - Persisted
- ✅ `timeout_next_play_type` - Persisted (if applicable)
- ✅ `user_team_side` - Persisted
- ✅ `strategy_settings` - Persisted (in `teams` object)
- ✅ `plays` - Persisted (in `teams` object)
- ✅ `attributes` - Persisted (in `teams` object)
- ✅ `scouting` - Persisted (in `teams` object)

**Required Context Data:**
- ✅ `game_id` - Persisted
- ✅ `mode` - Persisted (added during `simulate_quarter_endpoint()` saves)
- ✅ `tournament_id` - Persisted (added during `simulate_quarter_endpoint()` saves for Tournament mode)
- ✅ `franchise_id` - Persisted (Franchise mode only)
- ✅ `team_id` - Persisted (in `home_team_id` / `away_team_id`)

**Status:** ✅ **ALIGNED** - All required fields are persisted correctly for all modes.

---

## Summary

### ✅ What's Working Well

1. **Core Game State:** All essential game state fields are persisted correctly
2. **Team Data:** Full team data (attributes, strategy, plays, scouting) is persisted in `teams` object
3. **Player Data:** Full player array with stats and attributes is persisted
4. **Franchise Mode:** Properly includes `franchise_id` and `week` in game document when result is saved (after gameplay completes)
5. **Timeout State:** Timeout resume state (`timeout_next_play_type`, `clock`, etc.) is persisted correctly

### ⚠️ Issues Identified

1. ✅ **RESOLVED: Tournament Mode `tournament_id`** - Now always set during `simulate_quarter_endpoint()` saves (see "Discrepancies Identified" section below)

### 📋 Recommendations

1. ✅ **IMPLEMENTED: Ensure `tournament_id` is Always Set in Tournament Mode Game Documents:**
   - Modified `BackEnd/api/api.py:1636` to add `tournament_id` when mode is "tournament" and `request.tournament_id` is available
   - This ensures `tournament_id` is always set, regardless of game creation path (normal flow or direct creation)
   - Note: Franchise mode adds `franchise_id` and `week` when the game result is saved (not during quarter saves), so Tournament mode actually adds its mode identifier earlier in the flow

2. ✅ **IMPLEMENTED: Add `mode` Field:**
   - Added `mode` field to game document when saving
   - Mode is inferred from `tournament_id`/`franchise_id` if not provided in request
   - Useful for querying games by mode and consistency with `init_game()` pattern

---

## Code References

### Key Functions

- **`summarize_game_state()`** - `BackEnd/utils/shared.py:507-786`
  - Creates game state summary for persistence
  - Handles both database saves (no animations) and frontend responses (with animations)

- **`simulate_quarter_endpoint()`** - `BackEnd/api/api.py:767-1650`
  - Handles all quarter simulation requests
  - Saves game state to database after quarter completion

- **`handleButtonClick()`** - `FrontEnd/static/js/phaser/bootGame.js:388-443`
  - Play Quarter button handler
  - Calls `startGame()` for turn-by-turn gameplay

- **`handleSimToFourth()`** - `FrontEnd/static/js/phaser/bootGame.js:445-608`
  - Sim To 4th Quarter button handler
  - Loops through Q1-Q3, then redirects to set-lineup for Q4

- **`handleSimFullGame()`** - `FrontEnd/static/js/phaser/bootGame.js:610-830`
  - Sim Full Game button handler
  - Loops through Q1-Q4, then shows completion popup

### Database Save Locations

- **Single Game / Tournament:** `BackEnd/api/api.py:1636` - `games_collection.update_one()`
- **Franchise Mode:** 
  - During gameplay: `BackEnd/api/api.py:1928` - `games_collection.update_one()` (via `simulate_quarter_endpoint()`)
  - When result saved: `BackEnd/api/franchise_routes.py:327-340` - `db.games.update_one()` (adds `franchise_id` and `week` via `save_result()`)

---

**End of Document**

