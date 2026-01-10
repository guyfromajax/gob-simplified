# Team Objects Data Architecture

**Created:** January 2026  
**Status:** Planning / Discussion  
**Related:** Playbook Persistence, Game Initialization

## Problem Statement

When accessing the Playbooks page from the lineup screen during gameplay in Franchise Mode, offensive plays are not displaying in the frontend containers. The percentages show correctly (100% totals), but the play names themselves are missing.

**Root Cause:**
- Backend `get_playbooks` endpoint always reads from franchise document when `mode="franchise"`
- During gameplay, `game_id` is present but ignored
- The game document has `teams.{team_id}.plays` populated, but backend reads from `franchise_teams.{team_id}.plays` in franchise document
- Projection issues or document reloads may be causing `plays` to be empty when reading from franchise document

## Architectural Decision: Hybrid Approach

**Decision:** Copy `plays` and `playbook_settings` from franchise document to game document at game start, then use game document as source of truth during gameplay.

### Principles

1. **Game Document = Complete Snapshot**
   - Contains all team state at game start (plays, playbook_settings, strategy_settings)
   - Self-contained - no dependency on franchise document during gameplay
   - Allows game-specific adjustments without affecting franchise settings

2. **Franchise Document = Persistent Season State**
   - Authoritative source for season-long team settings
   - Preserves settings as they were at game start
   - Only modified from FCC/TCC (not during gameplay)

3. **Gameplay vs. Command Center Access**
   - **Gameplay scenario** (`game_id` present): Read/write from game document
   - **FCC/TCC scenario** (`game_id` absent): Read/write from franchise document

## Data Flow Patterns

### Game Initialization (Franchise Mode)

```
Franchise Document (franchise_teams.{team_id})
  ├── plays: {play_name: {play_id, play_type, play_focus, ...}}
  ├── playbook_settings: {motion: {...}, set_play_inside: {...}, ...}
  └── strategy_settings: {...}

         ↓ (COPY at game start via init_game)

Game Document (teams.{team_id})
  ├── plays: {play_name: {play_id, play_type, play_focus, ...}}  ← COPIED
  ├── playbook_settings: {motion: {...}, set_play_inside: {...}, ...}  ← COPIED
  └── strategy_settings: {...}  ← COPIED (if applicable)
```

### During Gameplay (game_id present)

**Read Pattern:**
```
User accesses Playbooks page
  → Frontend passes: mode="franchise", franchise_id=..., game_id=...
  → Backend detects game_id present
  → Reads from: games.{game_id}.teams.{team_id}.plays
  → Returns plays to frontend
```

**Write Pattern:**
```
User saves Playbook settings
  → Frontend passes: mode="franchise", franchise_id=..., game_id=...
  → Backend detects game_id present
  → Saves to: games.{game_id}.teams.{team_id}.playbook_settings
  → Franchise document remains unchanged
```

### From Command Center (game_id absent)

**Read Pattern:**
```
User accesses Playbooks page from FCC
  → Frontend passes: mode="franchise", franchise_id=..., game_id=null
  → Backend detects game_id absent
  → Reads from: franchises.{franchise_id}.franchise_teams.{team_id}.plays
  → Returns plays to frontend
```

**Write Pattern:**
```
User saves Playbook settings from FCC
  → Frontend passes: mode="franchise", franchise_id=..., game_id=null
  → Backend detects game_id absent
  → Saves to: franchises.{franchise_id}.franchise_teams.{team_id}.playbook_settings
  → Settings persist for future games
```

## Current State vs. Desired State

### Current State (Broken)

**`init_game` endpoint:**
- ✅ Copies `playbook_settings` from franchise → game document
- ❌ Does NOT copy `plays` from franchise → game document

**`get_playbooks` endpoint:**
- ❌ Always reads from franchise document when `mode="franchise"` (ignores `game_id`)
- ❌ Uses projection that may exclude nested `plays` fields
- ❌ Multiple document reloads may lose `plays` data
- ❌ Added safeguard to populate `plays` when missing (workaround, not solution)

**`save_playbooks` endpoint:**
- ❌ Always saves to franchise document when `mode="franchise"` (ignores `game_id`)
- ❌ Gameplay changes modify franchise document (unintended)

### Desired State (Fixed)

**`init_game` endpoint:**
- ✅ Copies `playbook_settings` from franchise → game document (both teams)
- ✅ Copies `plays` from franchise → game document (both teams)
- ✅ Game document is complete snapshot at game start

**`get_playbooks` endpoint:**
- ✅ Detects `game_id` parameter
- ✅ If `game_id` present: Read from `games.{game_id}.teams.{team_id}.plays`
- ✅ If `game_id` absent: Read from `franchises.{franchise_id}.franchise_teams.{team_id}.plays`
- ✅ Removes safeguard (plays always exist in game document)

**`save_playbooks` endpoint:**
- ✅ Detects `game_id` parameter
- ✅ If `game_id` present: Save to `games.{game_id}.teams.{team_id}.playbook_settings`
- ✅ If `game_id` absent: Save to `franchises.{franchise_id}.franchise_teams.{team_id}.playbook_settings`
- ✅ Gameplay changes stay in game document (preserves franchise settings)

## Required Code Changes

### 1. `init_game` Endpoint (`BackEnd/api/api.py`)

**Location:** After line 2657 (after copying `playbook_settings`)

**Action:** Copy `plays` from franchise document to game document for both teams

**Logic:**
```python
# For each team (home and away):
# 1. Load plays from franchise_teams.{team_id}.plays
# 2. Copy to teams.{team_id}.plays in game document summary
# 3. Ensure structure matches expected format
```

**Files to modify:**
- `BackEnd/api/api.py` - `init_game()` function

### 2. `get_playbooks` Endpoint (`BackEnd/api/gameplan_routes.py`)

**Location:** Lines 1163-1460

**Actions:**
- Change collection selection logic to detect `game_id`
- If `game_id` present: Use `db.games` collection, read from `teams.{team_id}`
- If `game_id` absent: Use `db.franchises` collection, read from `franchise_teams.{team_id}`
- Remove safeguard code (lines ~1412-1447) that populates plays when missing

**Detection Pattern:**
```python
if game_id:
    # Gameplay scenario - use game document
    collection = db.games
    doc_id = game_id
    team_path_prefix = "teams"  # teams.{team_id}.plays
    mode_context = "gameplay"
else:
    # FCC/TCC scenario - use franchise document
    collection = db.franchises
    doc_id = franchise_id
    team_path_prefix = "franchise_teams"  # franchise_teams.{team_id}.plays
    mode_context = "command_center"
```

**Files to modify:**
- `BackEnd/api/gameplan_routes.py` - `get_playbooks()` function

### 3. `save_playbooks` Endpoint (`BackEnd/api/gameplan_routes.py`)

**Location:** Lines 1584-1868

**Actions:**
- Change collection selection logic to detect `game_id` (from `request.game_id`)
- If `game_id` present: Save to `games.{game_id}.teams.{team_id}.playbook_settings`
- If `game_id` absent: Save to `franchises.{franchise_id}.franchise_teams.{team_id}.playbook_settings`
- Ensure team_id resolution works correctly for both scenarios

**Detection Pattern:**
```python
if request.game_id:
    # Gameplay scenario - save to game document
    collection = db.games
    doc_id = request.game_id
    team_path = f"teams.{actual_team_id}.playbook_settings"
else:
    # FCC/TCC scenario - save to franchise document
    collection = db.franchises
    doc_id = request.franchise_id
    team_path = f"franchise_teams.{actual_team_id}.playbook_settings"
```

**Files to modify:**
- `BackEnd/api/gameplan_routes.py` - `save_playbooks()` function

### 4. `update_gameplan` Endpoint (`BackEnd/api/gameplan_routes.py`)

**Location:** Lines 1027-1160

**Actions:**
- Apply same `game_id` detection logic
- If `game_id` present: Read/write from game document
- If `game_id` absent: Read/write from franchise document

**Files to modify:**
- `BackEnd/api/gameplan_routes.py` - `update_gameplan()` and `get_gameplan()` functions

### 5. Frontend Parameter Verification

**Action:** Verify `game_id` is being passed in URL params when accessing Playbooks/Game Plan from lineup screen

**Files to check:**
- `FrontEnd/static/set-lineup.js` - Lineup screen navigation to Playbooks
- `FrontEnd/static/js/shared/timeoutNavigationHelper.js` - Parameter building logic
- `FrontEnd/static/playbooks.js` - Parameter reading logic

## Benefits of This Approach

1. **SS&S (Simple, Stable, Scalable)**
   - Clear separation: game document = snapshot, franchise document = persistent state
   - Predictable data flow: detect `game_id` → route to appropriate document
   - No projection issues: game document is loaded fully when needed

2. **Performance**
   - Gameplay reads are fast (self-contained game document)
   - No need to query large franchise document during gameplay
   - Reduced data transfer (game document is smaller than full franchise document)

3. **Data Integrity**
   - Franchise settings preserved at game start
   - Gameplay changes isolated to game instance
   - Clear audit trail: franchise document shows settings at game start, game document shows what happened

4. **User Experience**
   - Users can experiment with settings during gameplay without affecting franchise setup
   - Settings changes during gameplay are game-specific
   - Original franchise settings remain for future games

## Edge Cases to Consider

1. **Tournament Mode:** Similar logic applies (tournament document vs. game document)
2. **Single Game Mode:** Always uses game document (no franchise/tournament)
3. **Game Replay/Resume:** Game document already exists, reads should use existing data
4. **Missing Data:** If `plays` don't exist in franchise document at game start, should we initialize them or fail gracefully?

## Testing Checklist

- [ ] New game initialization copies `plays` correctly for both teams
- [ ] Playbooks page displays plays when accessed from lineup screen (gameplay)
- [ ] Playbooks page displays plays when accessed from FCC (command center)
- [ ] Saving playbook settings during gameplay updates game document only
- [ ] Saving playbook settings from FCC updates franchise document
- [ ] Franchise document settings unchanged after gameplay
- [ ] Game document has correct `plays` structure after initialization
- [ ] Both home and away teams have plays copied correctly

## Related Documentation

- `docs/To Do/play_percentage_persistence.md` - Playbook percentage persistence issues
- `docs/Persistence_Docs/COMMON_DATA_SET.md` - Common data structures
- `docs/_Master_Documentation.md` - Master documentation

## Notes

- This approach maintains backward compatibility: FCC/TCC access continues to work as before
- Game document structure is already established (has `teams` object)
- No frontend changes required (frontend already passes `game_id` when available)
- The safeguard code added earlier should be removed once this is implemented

---

## Phase 2: Team Objects Unification (Game Documents)

**Status:** In Progress  
**Priority:** High (Must complete before fixing playcall display bug)

### Problem Statement

Game documents currently have duplicate team data structures:
- `home_team` / `away_team` objects: Display fields (name, colors, score, timeouts, attributes, box_score, totals)
- `teams.{team_id}` objects: Persistence fields (attributes, strategy_settings, plays, scouting, playbook_settings)

**Issues:**
1. Data duplication: `attributes` exists in both structures with identical values
2. Confusion: Unclear which structure is source of truth
3. Inconsistency: Backend reads from `teams` when resuming, but frontend reads from `home_team`/`away_team`
4. Maintenance burden: Two structures to keep in sync

### Solution: Unify Under `teams` Object

**Decision:** Eliminate `home_team`/`away_team` objects entirely. Store ALL team data in `teams.{team_id}` object and use `home_team_id`/`away_team_id` for lookups.

### New Structure

**Game Document:**
```json
{
  "_id": "...",
  "home_team_id": "LANCASTER",  // Reference to teams object
  "away_team_id": "SOUTH_LANCASTER",  // Reference to teams object
  "teams": {
    "LANCASTER": {
      // ALL team data in one place:
      "name": "Lancaster",
      "team_id": "LANCASTER",
      "mascot": "",
      "colors": { "primary_color": "...", "secondary_color": "..." },
      "score": 0,
      "points_by_quarter": [0, 0, 0, 0],
      "team_fouls": 0,
      "timeouts": 4,
      "attributes": { "shot_threshold": 47, ... },  // Single source of truth
      "box_score": { ... },  // Player stats
      "totals": { ... },  // Team totals
      "strategy_settings": { ... },
      "strategy_calls": { ... },
      "plays": { ... },
      "scouting": { ... },
      "playbook_settings": { ... }
    },
    "SOUTH_LANCASTER": { ... }
  }
}
```

**Frontend Access Pattern:**
```javascript
// Instead of: gameData.home_team
const homeTeam = gameData.teams[gameData.home_team_id];
const awayTeam = gameData.teams[gameData.away_team_id];

// S3 tab attributes:
const homeAttrs = gameData.teams[gameData.home_team_id].attributes;
```

### Benefits

1. **Single Source of Truth**
   - All team data in one place (`teams.{team_id}`)
   - No duplication of `attributes` or other fields
   - Clear data ownership

2. **SS&S Architecture**
   - Simpler structure: one object, not two
   - Consistent: backend already reads from `teams` when resuming
   - Maintainable: only one structure to update

3. **Performance**
   - Reduced document size (no duplicate data)
   - Single lookup pattern (no confusion about which structure to use)

4. **Consistency**
   - Aligns with franchise/tournament document patterns (`franchise_teams`/`teams`)
   - Matches backend resumption logic (already uses `teams`)

### Required Changes

#### 1. Backend: `summarize_game_state()` (`BackEnd/utils/shared.py`)

**Location:** Lines 1003-1089

**Actions:**
- Remove `home_team_data` and `away_team_data` object creation
- Add ALL fields to `teams_obj` (name, mascot, colors, score, points_by_quarter, team_fouls, timeouts, box_score, totals)
- Keep `home_team_id` and `away_team_id` at top level for easy reference
- Remove `"home_team"` and `"away_team"` from return dict

**Current structure:**
```python
home_team_data = { "name": ..., "score": ..., "attributes": ... }
away_team_data = { "name": ..., "score": ..., "attributes": ... }
teams_obj = { team_id: { "strategy_settings": ..., "plays": ... } }
return { "home_team": home_team_data, "away_team": away_team_data, "teams": teams_obj }
```

**New structure:**
```python
teams_obj = {
  home_team_id: {
    "name": ..., "score": ..., "attributes": ..., 
    "strategy_settings": ..., "plays": ..., "box_score": ..., "totals": ...
  },
  away_team_id: { ... }
}
return { "home_team_id": home_team_id, "away_team_id": away_team_id, "teams": teams_obj }
```

#### 2. Backend: API Endpoints Reading Game State

**Files to update:**
- `BackEnd/api/api.py` - `get_game_state()` (lines 818-843)
- `BackEnd/api/api.py` - `simulate_quarter_endpoint()` (lines 1069-1090)
- `BackEnd/utils/stat_updater.py` - `finalize_game()` (lines 1497-1506)

**Actions:**
- Update code that reads from `home_team`/`away_team` to read from `teams[home_team_id]`/`teams[away_team_id]`
- Update team name extraction: `game.get("home_team", {}).get("name")` → `game.get("teams", {}).get(game.get("home_team_id"), {}).get("name")`

#### 3. Frontend: Game Scene (`FrontEnd/static/js/phaser/gameScene.js`)

**Locations:**
- Lines 346-366: Team name/ID/colors extraction
- Lines 611-612: Team object access
- Lines 1122-1123: Timeouts access
- Lines 2200-2210: Final game data team access

**Actions:**
- Update to read from `teams[home_team_id]` instead of `home_team`
- Add helper function: `getTeamById(teamId)` or use `gameData.teams[gameData.home_team_id]`

#### 4. Frontend: Box Score (`FrontEnd/static/box-score.js`)

**Locations:**
- Lines 258-277: Header rendering
- Lines 280-322: Quarter scoring

**Actions:**
- Update to read from `teams[home_team_id]` instead of `home_team`
- Update team name access: `gameData.home_team.name` → `gameData.teams[gameData.home_team_id].name`

#### 5. Frontend: Load Game Stats (`FrontEnd/static/js/phaser/utils/loadGameStats.js`)

**Location:** Lines 142-191 (Team Box Score display)

**Actions:**
- Update S3 tab attributes access: `gameData.home_team.attributes` → `gameData.teams[gameData.home_team_id].attributes`
- Update totals access: `gameData.team_totals[homeTeam]` → `gameData.teams[gameData.home_team_id].totals`

#### 6. Frontend: Other Files

**Files to check:**
- `FrontEnd/static/js/phaser/bootGame.js` - Team name passing
- `FrontEnd/static/js/phaser/finalizeGame.js` - Final game data
- `FrontEnd/static/js/state/gameStore.js` - Team state management

### Migration Strategy

1. **Backend First:** Update `summarize_game_state()` to create unified structure
2. **Backend APIs:** Update endpoints to read from new structure
3. **Frontend:** Update frontend code to use new structure
4. **Testing:** Verify all displays work (S3 tab, box score, gameplay)

### Testing Checklist

- [ ] New game creates unified `teams` structure correctly
- [ ] S3 tab displays attributes from `teams[team_id].attributes`
- [ ] Box score displays team names and scores correctly
- [ ] Team colors display correctly during gameplay
- [ ] Timeouts display correctly
- [ ] Game resumption loads team data correctly
- [ ] Final game data displays correctly
- [ ] No references to `home_team`/`away_team` in codebase

### Order of Operations

1. ✅ Document unification plan (this document)
2. ✅ Update `summarize_game_state()` to create unified structure
3. ✅ Update backend API endpoints to read from unified structure
   - ✅ `get_game_state()` - Updated to use unified structure, returns backward-compatible fields
   - ✅ `simulate_quarter_endpoint()` - Updated to read from unified structure
   - ✅ `finalize_game()` - Updated to read from unified structure
4. ⏳ Update frontend code to use unified structure
   - ⏳ `gameScene.js` - Team data extraction
   - ⏳ `box-score.js` - Team name/score display
   - ⏳ `loadGameStats.js` - S3 tab attributes
   - ⏳ Other files as needed
5. ⏳ Test thoroughly
6. ⏳ **Then** fix playcall display bug with unified structure

### Implementation Status

**Backend: COMPLETE**
- ✅ `summarize_game_state()` now creates unified `teams` object with all data
- ✅ Removed `home_team`/`away_team` from document structure
- ✅ Backend APIs read from unified structure
- ✅ API responses include backward-compatible `home_team`/`away_team` fields (built from `teams` object) for gradual frontend migration

**Frontend: IN PROGRESS**
- ⏳ Need to update all references from `gameData.home_team` to `gameData.teams[gameData.home_team_id]`
- ⏳ Helper functions may be useful to abstract the lookup
- ⏳ Backend currently returns backward-compatible fields, so frontend works but should be migrated

### Related Issues

- This fixes the confusion about where `attributes` should be stored
- Simplifies the playcall display bug fix (one structure to worry about)
- Aligns game document structure with franchise/tournament patterns

