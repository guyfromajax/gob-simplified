# Common Data Set for Navigation & Persistence

> **Last Updated:** January 2025  
> **Status:** Updated with Verified Structure

This document defines the **common data set** that persists across game instances and tournament/franchise mode instances. This is the data that needs to be managed consistently across all navigation transitions.

**Note:** This structure reflects the CURRENT implementation. `playcall_settings` has been removed and replaced by `strategy_settings` only.

---

## Common Data Structure

The following data structure is **identical** across all three modes, stored in different locations:

### Storage Locations

- **Single Game Mode:** `games.{game_id}.teams.{team_id}`
- **Tournament Mode:** `tournaments.{tournament_id}.teams.{team_id}`
- **Franchise Mode:** `franchises.{franchise_id}.franchise_teams.{team_id}`

### Common Data Fields

```javascript
{
  // Team Attributes (mode-specific initialization ranges)
  // ✅ These are initialized when team objects are created
  "team_chemistry": number,     // e.g., 15
  "offensive_efficiency": number, // e.g., 5
  "shot_threshold": number,     // e.g., 200
  "turnover_modifier": number,  // e.g., -1
  "foul_modifier": number,      // e.g., 1
  "rebound_modifier": number,   // e.g., 1
  "defensive_efficiency": number, // e.g., -5
  "fb_efficiency": number,      // e.g., -9
  "pt_efficiency": number,      // e.g., -1
  "fb_opp_modifier": number,    // e.g., -10
  "pt_opp_modifier": number,    // e.g., 7
  
  // Strategy Settings (persist across all instances)
  // ✅ Initialized with defaults (all = 2) when team objects are created
  "strategy_settings": {
    "offense": number,          // 0-4
    "inside": number,           // 0-4
    "attack": number,           // 0-4
    "outside": number,          // 0-4
    "tempo": number,            // 0-4
    "defense": number,          // 0-4
    "aggression": number,       // 0-4
    "hc_trap": number,          // 0-4 (half-court trap)
    "fc_press": number,         // 0-4 (full-court press)
    "rebounding": number        // 0-4
  },
  
  // Plays Data (persist across all instances, updated by training)
  // ✅ Added during initialization via populate_team_plays()
  "plays": {
    [playName]: {
      "play_id": string,           // Reference to universal plays collection
      "name": string,
      "play_type": string,
      "play_focus": string,
      "effectiveness": number,     // 0-100 (tournament: 0-80 randomized), updated by training
      "momentum": number,          // 0-10 (tournament: randomized), updated by training
      "cloaking": number,         // 0-10 (tournament: randomized), updated by training
      "game_stats": {
        "times_run": number,
        "shot_attempts": number,
        "made_shots": number,
        "turnovers": number,
        "offensive_fouls": number,
        "defensive_fouls": number,
        "effectiveness": number    // Calculated effectiveness from stats
      },
      "season_stats": { ... }     // Cumulative statistics (tournament/franchise only)
    }
  },
  
  // Scouting Data (persist across all instances, updated by training)
  // ✅ Added during initialization via populate_scouting_data()
  "scouting_data": {
    "defense": {
      "Man": {
        "effectiveness": number,   // 0-80 (tournament randomized) or 0-100 (franchise), updated by training
        "momentum": number,        // 0-10 (tournament randomized), updated by training
        "cloaking": number,        // 0-10 (tournament randomized), updated by training
        "game_stats": { ... },
        "season_stats": { ... }
      },
      "2-3 Zone": { ... },
      "3-2 Zone": { ... },
      "1-3-1 Zone": { ... },
      "vs_Fast_Break": { ... },
      "FCP": { ... },
      "HCT": { ... }
    },
    "offense": { ... }  // Optional, populated by TeamManager if needed
  },
  
  // Playbook Settings (persist across all instances)
  // ✅ Added during initialization with defaults (first play = 100%, others = 0%)
  "playbook_settings": {
    // Percentage distributions (play name → percentage)
    "motion": {
      "[firstPlayName]": 100,  // First motion play gets 100%
      // ... other motion plays = 0% (not included if 0%)
    },
    "set_play_inside": {
      "[firstPlayName]": 100,  // First inside set play gets 100%
      // ... other plays = 0% (not included if 0%)
    },
    "set_play_attack": {
      "[firstPlayName]": 100,  // First attack set play gets 100%
      // ... other plays = 0% (not included if 0%)
    },
    "set_play_outside": {
      "[firstPlayName]": 100,  // First outside set play gets 100%
      // ... other plays = 0% (not included if 0%)
    },
    "zone_defense": {
      "[firstPlayName]": 100,  // First zone defense gets 100%
      // ... other defenses = 0% (not included if 0%)
    },
    "man_defense": {
      "Man": 100  // Currently only "Man" exists, so it gets 100%
      // ... other man defenses = 0% (not included if 0%, future: when more man defenses are added)
    },
    
    // Slot Assignments (for Playcall Center slots 1-6)
    "slot_assignments": {},  // Empty by default - user must assign
    
    // Motion Dropdowns (Inside/Attack/Outside for motion plays)
    "motion_dropdowns": {}   // Empty by default - user must select
  }
}
```

---

## Fields NOT Included in Team Objects

### ❌ Universal Teams Collection Fields (NOT Copied)

The following fields from the universal `teams` collection are **NOT** copied to team objects in mode documents:

- `_id` - Team ObjectId (not stored in mode documents)
- `name` - Team name (not stored in mode documents)
- `player_ids` - Array of player ObjectIds (not stored in mode documents)
- `team_id` - Team identifier string (not stored in mode documents)
- `primary_color` - Primary team color (not stored in mode documents)
- `secondary_color` - Secondary team color (not stored in mode documents)
- `coaching` - Coaching attributes object (not stored in mode documents)
- `momentum_score` - Momentum score (not stored in mode documents)
- `PA` - Points Against (not stored in mode documents)
- `PF` - Points For (not stored in mode documents)
- `record` - Win/Loss record (not stored in mode documents)
- `stats` - Team statistics (not stored in mode documents)

**Note:** These fields are accessed from the universal `teams` collection when needed, not stored in mode documents.

---

## Removed Fields

### ❌ No Longer Used

- **`playcall_settings`** - Removed, functionality merged into `strategy_settings`

---

## Initialization Details

### When Team Objects Are Created

Team objects are created **lazily** when needed via `ensure_team_objects_exist()`:

1. **Franchise Mode:** All 8 teams are initialized when franchise is first accessed
2. **Tournament Mode:** Team objects are created when first accessed (e.g., when loading game plan)
3. **Single Game Mode:** Team objects are created when game is initialized

### What Gets Initialized

**During Initialization (via `ensure_team_objects_exist()`):**
- ✅ Team attributes (from `TeamManager.init_team_attributes()`)
- ✅ `strategy_settings` (defaults: all = 2)
- ✅ `plays` (from `populate_team_plays()`)
- ✅ `scouting_data` (from `populate_scouting_data()`)
- ✅ `playbook_settings` (defaults: first play = 100% per section, slot_assignments = {}, motion_dropdowns = {})

**NOT During Initialization:**
- ❌ Universal team fields - Never copied to mode documents

---

## Persistence Rules

### Single Game Mode

**During Game:**
- All common data persists across Lineup → Game Plan → Playbooks → Gameplay
- Settings persist for the duration of the current game instance

**Across Games:**
- Settings persist **per team** across Single Game instances
- Example: If user finishes a game as Lancaster, next time they play as Lancaster, settings from previous Lancaster game persist
- If they play as Morristown next, settings from last Morristown game persist

### Tournament & Franchise Modes

**Across All Instances:**
- All common data persists across:
  - Command Center → Game Plan → Playbooks
  - Command Center → Training → Training Report
  - Command Center → Lineup → Gameplay
  - Settings persist until explicitly changed

**Training Updates:**
- `plays` effectiveness, momentum, cloaking updated by training
- `scouting_data` defense effectiveness, momentum, cloaking updated by training
- Settings (`strategy_settings`, `playbook_settings`) used by training when "Current Playbooks" mode selected

---

## Key Functions for Accessing Common Data

### Backend Functions

**Location:** `BackEnd/api/gameplan_routes.py`

- `ensure_team_objects_exist(mode, doc_id, team_id)` - Ensures team object exists with all common data fields
  - Initializes: team attributes, strategy_settings, plays, scouting_data, playbook_settings
  - playbook_settings defaults: first play = 100% per section, slot_assignments = {}, motion_dropdowns = {}
- `get_gameplan(mode, team_id, ...)` - Retrieves strategy_settings
- `update_gameplan(mode, team_id, ...)` - Updates strategy_settings
- `populate_team_plays(mode)` - Initializes plays data structure
- `populate_scouting_data(mode)` - Initializes scouting data structure

**Location:** `BackEnd/api/gameplan_routes.py`

- `get_playbooks(mode, team_id, ...)` - Retrieves playbook_settings
- `save_playbooks(mode, team_id, ...)` - Updates playbook_settings (overwrites defaults if already initialized)

**Location:** `BackEnd/api/tournament_routes.py` & `BackEnd/api/franchise_routes.py`

- `get_tournament_team_data(tournament_id, team_id)` - Retrieves all common data for tournament
- `get_franchise_team_data(franchise_id, team_id)` - Retrieves all common data for franchise

### Frontend Functions

**Location:** `FrontEnd/static/game-plan.js`

- `loadSettings()` - Loads strategy_settings from backend
- `saveSettings()` - Saves strategy_settings to backend
- `strategySliders` - Maps slider IDs to strategy_settings keys:
  - 'offense', 'inside', 'attack', 'outside', 'tempo', 'defense', 'aggression', 'hc_trap', 'fc_press', 'rebounding'

**Location:** `FrontEnd/static/playbooks.js`

- `loadPlaybookSettings()` - Loads playbook_settings from backend
- `savePlaybookSettings()` - Saves playbook_settings to backend

---

## Navigation Data Requirements Impact

### Bucket 2 (Game Mode Only - Non-Gameplay)

**Required Navigation Anchor:**
- `mode` - "tournament" or "franchise"
- `doc_id` - `tournament_id` or `franchise_id`
- `team_id` - User's team ObjectId

**State Data (from Common Data Set):**
- `strategy_settings` - Game plan strategy settings (replaces old playcall_settings + strategy_settings)
- `scouting_data` - Scouting data with defense effectiveness/momentum/cloaking
- `plays` - Plays data with effectiveness/momentum/cloaking
- `playbook_settings` - Playbook percentage settings (initialized with defaults: first play = 100% per section)

### Bucket 3 (Gameplay)

**Required Navigation Anchor:**
- `mode` - "single", "tournament", or "franchise"
- `game_id` - Game document ID
- `team_id` - User's team ObjectId
- Conditionally: `tournament_id` or `franchise_id` (if mode is tournament/franchise)

**State Data (from Common Data Set):**
- Same as Bucket 2, plus:
- Game state (score, clock, quarter, possession, etc.)
- Player stats (points, rebounds, assists, etc.)
- Timeout state (if applicable)

---

## Implementation Notes

1. **Data Access Pattern:**
   - Always use `team_id` (ObjectId) as the key
   - Access via: `{mode_doc}.{teams_key}.{team_id}`
   - Where `teams_key` is `"teams"` for single/tournament, `"franchise_teams"` for franchise

2. **Initialization:**
   - Common data initialized by `ensure_team_objects_exist()`
   - Uses mode-specific initialization for team attributes (see Mode Initialization System)
   - Uses default values for settings (all sliders = 2)
   - `playbook_settings` initialized with defaults: first play = 100% per section, slot_assignments = {}, motion_dropdowns = {}

3. **Persistence:**
   - Database is source of truth
   - URL params only for navigation/routing
   - No localStorage for common data (database only)

4. **Validation:**
   - Settings validated on save (at least one offense setting > 0)
   - Plays/scouting data validated on training update
   - Team attributes validated on initialization (mode-specific ranges)

---

## References

- **Code:** `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (lines 295-482)
- **Code:** `BackEnd/api/tournament_routes.py` - `get_tournament_team_data()` (lines 410-521)
- **Code:** `BackEnd/api/franchise_routes.py` - `get_franchise_team_data()` (lines 832-922)
- **Code:** `BackEnd/utils/shared.py` - `summarize_game_state()` (lines 507-907)
- **Code:** `FrontEnd/static/game-plan.js` - `strategySliders` mapping (lines 63-74)
- **Docs:** `docs/master_game_doc.md` - Mode Initialization System
