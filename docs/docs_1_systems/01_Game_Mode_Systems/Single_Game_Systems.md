# Single Game Mode Systems

**Status:** ✅ **PRODUCTION** - Fully operational

## Overview

Single Game Mode is designed for one-off games with no persistent state between games. Each game is independent and does not affect future games.

**Mode Value:** `mode="single"` (explicitly declared, never inferred)

## Base Constants

**Collection:** `games`  
**Document:** Game document (UUID string or ObjectId)  
**Path:** `games.{game_id}.teams.{team_id}`

**Team Attributes:**
- `shot_threshold`: `random.randint(-10, 190)`
- `discipline`: `random.randint(-10, 10)` (formerly `turnover_modifier`)
- `fight`: `random.randint(-10, 10)` (formerly `foul_modifier`)
- `rebound_modifier`: `random.randint(0, 40) / 100.0` (random 0.0-0.4 in 0.01 increments)
- `offensive_efficiency`: `random.randint(-10, 10)`
- `team_chemistry`: `random.randint(7, 25)`
- `defensive_efficiency`: `random.randint(-10, 10)`
- `fb_efficiency`: `random.randint(-10, 10)`
- `pt_efficiency`: `random.randint(-10, 10)`
- `fb_opp_modifier`: `random.randint(-10, 10)`
- `pt_opp_modifier`: `random.randint(-10, 10)`

**Settings:**
- `playcall_settings`: Default settings (all set to 2 = Normal)
- `strategy_settings`: Default settings (all set to 2 = Normal)
- `playbook_settings`: Even distribution across all plays in each category (not first play = 100%)

## System Flow

1. **Team Object Creation** - When user accesses Game Plan or Playbooks page
2. **Team Object Storage** - Stored in `games` collection under `teams.{team_id}`
3. **Team Object Loading** - Loaded when creating new game instance
4. **Team Object Updates** - Playbook and strategy settings saved during gameplay
5. **Team Object Persistence** - Persists for duration of game, reset for new games

## Long Form Documentation

### Team Object Lifecycle

#### 1. Team Object Creation

**Trigger:** When a user accesses the Game Plan or Playbooks page for the first time in a new game

**Location:** `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (lines 525-651)

**Process:**
1. Checks if team object exists in `games` collection under `teams.{team_id}`
2. If missing, creates team object with:
   - `playcall_settings`: Default settings (all set to 2 = Normal)
   - `strategy_settings`: Default settings (all set to 2 = Normal)
   - `plays`: Populated plays from universal collection via `populate_team_plays(mode="single")`
   - `scouting_data`: Initialized via `populate_scouting_data(mode="single")`
   - `playbook_settings`: Even distribution across all plays in each category (via `initialize_playbook_settings()`)
   - **Team attributes**: Initialized via `TeamManager.init_team_attributes(mode="single")`:
     - Uses mode-specific ranges (Single Game mode ranges)
     - All attributes randomized per Mode Initialization System

**Initialization Pattern:**
- **Lazy Initialization**: Team objects created on-demand when first accessed
- **Mode-Specific Attributes**: Uses Single Game mode attribute ranges
- **Playbook Settings**: Even distribution (not first play = 100%)

#### 2. Team Object Storage

**Collection:** `games`  
**Document:** Game document (UUID string or ObjectId)  
**Path:** `games.{game_id}.teams.{team_id}`

**Structure:**
```json
{
  "playcall_settings": {
    "Base": 2,
    "Freelance": 2,
    "Inside": 2,
    "Attack": 2,
    "Outside": 2,
    "Set": 2
  },
  "strategy_settings": {
    "offense": 2,
    "inside": 2,
    "attack": 2,
    "outside": 2,
    "tempo": 2,
    "defense": 2,
    "aggression": 2,
    "hc_trap": 2,
    "fc_press": 2,
    "rebounding": 2
  },
  "plays": {...},
  "scouting_data": {...},
  "playbook_settings": {
    "motion": {play_name: percentage}, // Even distribution
    "set_play_inside": {play_name: percentage}, // Even distribution
    "set_play_attack": {play_name: percentage}, // Even distribution
    "set_play_outside": {play_name: percentage}, // Even distribution
    "zone_defense": {defense_name: percentage}, // Even distribution
    "man_defense": {"Man": 100},
    "slot_assignments": {},
    "motion_dropdowns": {},
    "position_filters": {...}
  },
  "shot_threshold": random.randint(-10, 190),
  "discipline": random.randint(-10, 10),
  "fight": random.randint(-10, 10),
  "rebound_modifier": random.randint(0, 40) / 100.0,
  "offensive_efficiency": random.randint(-10, 10),
  "team_chemistry": random.randint(7, 25),
  "defensive_efficiency": random.randint(-10, 10),
  "fb_efficiency": random.randint(-10, 10),
  "pt_efficiency": random.randint(-10, 10),
  "fb_opp_modifier": random.randint(-10, 10),
  "pt_opp_modifier": random.randint(-10, 10)
}
```

#### 3. Team Object Loading

**Location:** `BackEnd/api/api.py` - `load_team_attributes_from_doc()` (lines 196-244)

**Process:**
1. `load_team_attributes_from_doc()` is called with `mode="single"` and `doc_id=game_id`
2. Loads team attributes from `games.{game_id}.teams.{team_id}`
3. If not found, falls back to the **universal `teams` collection** in MongoDB
4. Attributes are passed to `GameManager()` constructor
5. If no attributes are loaded, `TeamManager.init_team_attributes(mode="single")` generates random values

**Game Creation:**
- **Location:** `BackEnd/api/api.py` (lines 1246-1253, 1337-1344)
- Team attributes loaded before `GameManager` instantiation
- Fallback to universal collection ensures teams always have attributes

#### 4. Team Object Updates

**Playbook Settings:**
- Saved to `games.{game_id}.teams.{team_id}.playbook_settings`
- Updated when user submits playbook changes
- **Team Resolution:** Frontend sends team name (e.g., "Bentley-Truman"), backend resolves to `team_id` (e.g., "BENTLEY_TRUMAN") by matching team name in game document's `teams` object
- **Mode Handling:** Backend `/api/playbooks` endpoint explicitly handles `mode="single"` to save to game document using `game_id`

**Strategy Settings:**
- Saved to `games.{game_id}.teams.{team_id}.strategy_settings`
- Updated when user submits game plan changes

**Team Attributes:**
- Currently not updated during gameplay (training not implemented for single game mode)
- Attributes remain constant throughout the game

#### 5. Team Object Persistence

- Team objects persist for the duration of the game
- When a new game is started, new team objects are created (no carryover from previous games)
- Team attributes are reset to new random values for each new game (via `TeamManager.init_team_attributes(mode="single")`)

## Key Files

- `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (lines 525-651)
- `BackEnd/api/api.py` - `load_team_attributes_from_doc()` (lines 196-244)
- `BackEnd/api/api.py` - Game creation logic (lines 1246-1253, 1337-1344)
- `BackEnd/models/team_manager.py` - `TeamManager.__init__()` (lines 9-84)
  - Stores `mode` parameter as `self.mode` for use in `_init_scouting_data()` and other methods
- `BackEnd/models/team_manager.py` - `TeamManager.init_team_attributes()` (lines 185-226)

## See Also

- `Mode_Init_System.md` - Complete mode initialization system documentation
- `Playbooks_Page.md` - Playbook settings management

