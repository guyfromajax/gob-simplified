# Sim Playcalling System ✅ **COMPLETE** (January 2025)

## Base Constants

**Purpose:** Determines which offensive and defensive plays are selected during gameplay using weighted random selection based on playbook settings.

**Core Components:**
- **Play Type Selection**: Motion vs Set Play (based on `offense_setting` strategy slider)
- **Play Focus Selection**: Inside/Attack/Outside (for Set Plays only, based on strategy sliders)
- **Play Selection**: Weighted random from playbook percentages (user teams) or equal weights (CPU teams)
- **Defense Selection**: Man (single option) or Zone (weighted selection from playbook percentages)

**Key Methods:**
- `set_playcalls()` - Main entry point for play selection (line 800)
- `_load_playbook_settings(team_id)` - Loads playbook settings from database (line 1208)
- `_select_play_with_playbook_weights()` - Weighted play selection (line 1289)
- `_select_zone_defense_with_playbook_weights()` - Weighted zone defense selection (line 1341)

**Storage Locations:**
- **Single Game**: `games.{game_id}.teams.{team_id}.playbook_settings` + `teams.{team_id}.playbook_settings` (cross-instance)
- **Tournament**: `tournaments.{tournament_id}.teams.{team_id}.playbook_settings`
- **Franchise**: `franchises.{franchise_id}.franchise_teams.{team_id}.playbook_settings`

**Key Files:**
- `BackEnd/models/turn_manager.py` - `set_playcalls()` method and helper functions
- `BackEnd/api/gameplan_routes.py` - Playbook settings save/load endpoints
- `BackEnd/utils/shared.py` - `summarize_game_state()` preserves playbook settings

## System Flow

1. **User Override Check**: Check for user-set `offense_call` or `defense_call` in `strategy_calls`
2. **Play Type Determination**: If no override, use `offense_setting` to select Motion vs Set Play
3. **Play Focus Determination**: If Set Play, use `inside`/`attack`/`outside` sliders to select focus
4. **Play Selection**: Query matching plays, apply playbook weights (user teams) or equal weights (CPU teams)
5. **Defense Selection**: Use `defense_setting` or user override, convert Zone to specific zone type with playbook weights
6. **Storage**: Selected playcalls stored in `game_state["current_playcall"]` and `game_state["defense_playcall"]`

## Long Form Documentation

### Overview

The Sim Playcalling System determines which offensive and defensive plays are selected during gameplay. It uses weighted random selection based on playbook settings configured by the user, with fallbacks for CPU teams and when no settings exist.

**Location:** `BackEnd/models/turn_manager.py` - `set_playcalls()` method (line 800)  
**Status:** ✅ Fully implemented with playbook integration, user overrides, and mode support

**Key Features:**
- ✅ Playbook-weighted selection for user teams
- ✅ Equal weights fallback for CPU teams
- ✅ User override support (one-time offense calls, persistent defense calls)
- ✅ Mode-specific storage and persistence
- ✅ Cross-instance persistence for Single Game mode

### Play Selection Flow

#### 1. User Override Check

**Offensive Play Override:**
- Checks `offense_team.strategy_calls.get("offense_call")` for user-selected play
- If set, uses the specific play name (e.g., "3-2 Motion", "Base Post Play")
- Override is cleared after use (one-time override)
- Looks up play details from database to determine `play_type` and `play_focus`

**Defensive Play Override:**
- Checks `user_team.strategy_calls.get("defense_call")` (regardless of current offense/defense)
- If set, uses the specific defense (e.g., "Man", "2-3 Zone", "Zone")
- Override is persistent until manually cleared by user
- If "Zone" is selected, converts to specific zone type using playbook weights

#### 2. Determine Play Type (Motion vs Set Play)

**If no user override:**
- Uses `offense_setting` from strategy settings (0-4 slider)
- Weighted random selection between "motion" and "set_play":
  - Setting 0: 100% Motion, 0% Set Play
  - Setting 1: 75% Motion, 25% Set Play
  - Setting 2: 50% Motion, 50% Set Play
  - Setting 3: 25% Motion, 75% Set Play
  - Setting 4: 0% Motion, 100% Set Play

#### 3. Determine Play Focus (Inside/Attack/Outside)

**Only applies to Set Plays** (Motion plays don't filter by focus):
- Uses `inside`, `attack`, `outside` values from strategy settings
- Weighted random selection:
  - Roll random number from 1 to total (inside + attack + outside)
  - If roll <= inside_val → "inside"
  - Else if roll <= inside_val + attack_val → "attack"
  - Else → "outside"

#### 4. Select Specific Play

**Motion Plays:**
- Queries all motion plays from universal `plays` collection: `{"play_type": "motion"}`
- Uses weighted selection based on playbook percentages from `playbook_settings.motion`
- Falls back to equal weights if no playbook settings exist

**Set Plays:**
- Queries plays matching play_type + play_focus: `{"play_type": "set_play", "play_focus": chosen_focus}`
- Uses weighted selection based on playbook percentages from `playbook_settings.set_play_{focus}`
- Falls back to equal weights if no playbook settings exist

**Zone Defense:**
- When "Zone" is selected (from strategy settings or user override), converts to specific zone type
- Uses weighted selection from playbook percentages in `playbook_settings.zone_defense`
- Available zone types: "2-3 Zone", "3-2 Zone", "1-3-1 Zone"
- Falls back to equal weights if no playbook settings exist

### Playbook Integration

**Weighted Selection System:**
- Loads playbook settings from team document: `teams.{team_id}.playbook_settings` (or `franchise_teams.{team_id}.playbook_settings` for Franchise mode)
- Uses `weighted_random_from_dict()` utility for selection
- Only applies to user teams (CPU teams use equal weights)

**Motion Offense Selection:**
- Uses `playbook_settings.motion` dictionary
- Keys are play names, values are percentages (0-100)
- Example: `{"5-0 Motion": 50, "4-1 Motion": 30, "3-2 Motion": 20}`
- When motion offense is selected:
  - 50% chance: 5-0 Motion
  - 30% chance: 4-1 Motion
  - 20% chance: 3-2 Motion

**Set Play Selection:**
- Uses `playbook_settings.set_play_inside`, `playbook_settings.set_play_attack`, or `playbook_settings.set_play_outside`
- Same structure as motion plays (play name → percentage)
- Selection based on chosen focus (inside/attack/outside)

**Zone Defense Selection:**
- Uses `playbook_settings.zone_defense` dictionary
- Keys are zone type names, values are percentages (0-100)
- Example: `{"2-3 Zone": 40, "3-2 Zone": 35, "1-3-1 Zone": 25}`
- When zone defense is selected:
  - 40% chance: 2-3 Zone
  - 35% chance: 3-2 Zone
  - 25% chance: 1-3-1 Zone

**Fallback Behavior:**
- If no playbook settings exist → Equal weights for all plays
- If CPU team → Equal weights (playbook settings ignored)
- If "To Be Added" play → Excluded from selection (0% weight, filtered out)

### Defense Selection

**Man Defense:**
- Currently only one option ("Man")
- No weighting needed (always selects "Man")
- Future: Will support multiple man defense variants with playbook percentages

**Zone Defense:**
- When "Zone" is selected (from strategy settings or user override), converts to specific zone type
- Uses playbook percentages from `playbook_settings.zone_defense`
- Falls back to equal weights if no playbook settings exist or for CPU teams

### Storage and Mode Support

**Storage Locations:**

**Single Game Mode:**
- `games_collection` → `game_doc.teams.{team_id}.playbook_settings` (per game instance)
- `teams_collection` → `team_doc.playbook_settings` (shared across all Single Game instances for the same team)
- **Cross-Instance Persistence:** Settings saved to both locations. When loading, checks game document first, then falls back to core `teams` collection if game document has no settings.

**Tournament Mode:**
- `tournaments_collection` → `tournament_doc.teams.{team_id}.playbook_settings`

**Franchise Mode:**
- `franchises_collection` → `franchise_doc.franchise_teams.{team_id}.playbook_settings`

**Mode Isolation:**
- Each game mode maintains its own playbook settings
- Settings from one mode don't affect another
- Settings persist across games within the same mode
- **Single Game Mode:** Settings persist across Single Game instances for the same team (via core `teams` collection)

### Data Persistence

**Game State Saves:**
- ✅ **`playbook_settings` is preserved when saving game state** - When `summarize_game_state()` saves game state (timeouts, quarter breaks, etc.), it loads existing `playbook_settings` from the database and includes them in the `teams.{team_id}` object (or `franchise_teams.{team_id}` for franchise mode)
- **Implementation:** `BackEnd/utils/shared.py` `summarize_game_state()` (lines 659-726) preserves `playbook_settings` from database when `exclude_animations=True` (database saves)

**Navigation Persistence:**
- ✅ **Settings persist across navigation** - When navigating Playbooks → Game Plan → Lineup → Gameplay, settings are preserved. When returning to Playbooks page, settings are loaded from API and applied to UI state.
- **Implementation:** `FrontEnd/static/playbooks.js` `loadPlaybookPercentagesFromAPI()` and `loadSlotAssignmentsFromAPI()` load and apply settings to UI state

**Cross-Instance Persistence (Single Game):**
- ✅ **Settings set in one Single Game instance persist to the next Single Game instance for the same team** (stored in core `teams` collection)

**Mode-Specific Path Handling:**
- ✅ **The `get_playbooks()` function correctly uses `franchise_teams.{team_id}` for franchise mode and `teams.{team_id}` for tournament/single mode** when initializing missing `playbook_settings` and reloading team objects. This ensures settings saved from Command Centers (FCC/TCC) are correctly loaded during gameplay.
- **Implementation:** `BackEnd/api/gameplan_routes.py` `get_playbooks()` (lines 1070-1095) correctly initializes missing `playbook_settings` using mode-specific paths

**Save Implementation:**
- `BackEnd/api/gameplan_routes.py` `save_playbooks()` saves to both game document and core `teams` collection (Single Game mode), or to `franchise_teams.{team_id}` (Franchise mode) or `teams.{team_id}` (Tournament mode)

**Result:** `slot_assignments`, percentages, and other playbook settings persist across all game state saves and page navigation.

### Key Methods

#### `set_playcalls()`

**Location:** `BackEnd/models/turn_manager.py` (line 800)  
**Purpose:** Main entry point for play selection

**Process:**
1. Check for user overrides (`offense_call`, `defense_call`)
2. If no offense override, determine play type (motion/set_play) using `offense_setting`
3. If Set Play, determine focus (inside/attack/outside) using strategy sliders
4. Call `_select_play_with_playbook_weights()` for offense
5. Call `_select_zone_defense_with_playbook_weights()` for zone defense
6. Store results in `game_state["current_playcall"]` and `game_state["defense_playcall"]`

**User Override Handling:**
- If `offense_call` is set, uses specific play name and clears after use
- If `defense_call` is set, uses specific defense (persistent until manually cleared)

#### `_load_playbook_settings(team_id)`

**Location:** `BackEnd/models/turn_manager.py` (line 1208)  
**Purpose:** Loads playbook settings from database

**Process:**
1. Checks if team is user team (CPU teams return None)
2. Determines game mode from game document
3. Loads from appropriate mode document:
   - Single Game: `games.{game_id}.teams.{team_id}` or `teams.{team_id}`
   - Tournament: `tournaments.{tournament_id}.teams.{team_id}`
   - Franchise: `franchises.{franchise_id}.franchise_teams.{team_id}`
4. Returns `playbook_settings` dict or None

**Returns:** `playbook_settings` dict or None (for CPU teams or if not found)

#### `_select_play_with_playbook_weights(matching_plays, play_type, play_focus)`

**Location:** `BackEnd/models/turn_manager.py` (line 1289)  
**Purpose:** Weighted play selection based on playbook percentages

**Process:**
1. Filters out "To Be Added" plays
2. Loads playbook settings via `_load_playbook_settings()`
3. Builds weights dict from percentages:
   - Motion plays: `playbook_settings.motion[play_name]`
   - Set plays: `playbook_settings.set_play_{focus}[play_name]`
4. Falls back to equal weights if no playbook settings exist
5. Uses `weighted_random_from_dict()` for selection
6. Returns selected play document

**Returns:** Selected play document from `matching_plays`

#### `_select_zone_defense_with_playbook_weights()`

**Location:** `BackEnd/models/turn_manager.py` (line 1341)  
**Purpose:** Weighted zone defense selection based on playbook percentages

**Process:**
1. Loads playbook settings for defense team
2. Uses `zone_defense` percentages from playbook settings
3. Falls back to equal weights if no settings exist or for CPU teams
4. Uses `weighted_random_from_dict()` for selection
5. Returns selected zone type name

**Returns:** Selected zone type name (e.g., "2-3 Zone", "3-2 Zone", "1-3-1 Zone")

### Integration Points

**Turn Manager:**
- `set_playcalls()` method called at start of each HCO turn
- Results stored in `game_state["current_playcall"]` and `game_state["defense_playcall"]`
- Selected playcall used by `resolve_half_court_offense_logic()`

**Game Engine:**
- Selected playcall used by `resolve_half_court_offense_logic()` for skeleton retrieval
- Skeleton retrieved based on selected playcall
- Shot resolution uses playcall for scoring calculations

**Playbook Settings:**
- Settings configured via Playbooks page (`/static/playbooks.html`)
- Saved via `BackEnd/api/gameplan_routes.py` `save_playbooks()` endpoint
- Loaded via `BackEnd/api/gameplan_routes.py` `get_playbooks()` endpoint

### Key Files

**Backend:**
- `BackEnd/models/turn_manager.py` - `set_playcalls()` method and helper functions
  - `set_playcalls()` - Main entry point (line 800)
  - `_load_playbook_settings()` - Loads playbook settings (line 1208)
  - `_select_play_with_playbook_weights()` - Weighted play selection (line 1289)
  - `_select_zone_defense_with_playbook_weights()` - Weighted zone defense selection (line 1341)
- `BackEnd/api/gameplan_routes.py` - Playbook settings save/load endpoints
  - `save_playbooks()` - Saves playbook settings to database
  - `get_playbooks()` - Loads playbook settings from database (lines 1070-1095)
- `BackEnd/utils/shared.py` - `summarize_game_state()` preserves playbook settings (lines 659-726)

**Frontend:**
- `FrontEnd/static/playbooks.js` - Playbook settings UI and API integration
  - `loadPlaybookPercentagesFromAPI()` - Loads percentages from API
  - `loadSlotAssignmentsFromAPI()` - Loads slot assignments from API

**Reference Documentation:**
- `docs/docs_1_systems/06_GMO_Supporting_Systems/Plays_System.md` - Plays system functionality
- `docs/docs_1_systems/06_GMO_Supporting_Systems/Playbooks_Page.md` - Playbooks page UI documentation

