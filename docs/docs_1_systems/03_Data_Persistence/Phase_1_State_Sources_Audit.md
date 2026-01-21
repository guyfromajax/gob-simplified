# Phase 1: State Sources Audit

**Date:** January 2026  
**Purpose:** Comprehensive audit of all state sources for core state variables, identifying current "patchwork" approach and contract violations.  
**Status:** In Progress

---

## Audit Methodology

For each state variable, we document:
1. **Read Sources:** Where the variable is read from (URL params, localStorage, gameStore, DB, ongoing_games)
2. **Write Sources:** Where the variable is written to (URL params, localStorage, gameStore, DB, ongoing_games)
3. **Fallback Chains:** Any fallback logic (e.g., "try URL, then localStorage, then default")
4. **Contract Violations:** Instances where multiple sources are used or silent fallbacks exist
5. **Current State:** Document the actual behavior (not what we want, but what exists)

---

## Core State Variables

### 1. `game_id`

**Contract Requirement:** Pointer (URL params), points to Truth (Server DB)

#### Frontend Reads (WHERE IT'S READ FROM):

**Location:** `FrontEnd/static/js/phaser/bootGame.js`
- **Line 84-118:** Reads from URL params: `urlParams.get('game_id')`
- **Line 1961-1968:** Fallback removed - now fails loudly if missing

**Location:** `FrontEnd/static/set-lineup.js`
- **Line 24-25:** Read from URL params with localStorage fallback:
  ```javascript
  let gameId = urlParams.get('game_id') ||
    (typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : null);
  ```
- **Line 57-65:** Additional localStorage fallback if still missing (checks if teams match)
- **Contract Violation:** ❌ Reads from multiple sources (URL → localStorage)

**Location:** `FrontEnd/static/game-plan.js`
- **Line 32:** Read from URL params with localStorage fallback:
  ```javascript
  const gameId = urlParams.get('game_id') || (typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : null);
  ```
- **Line 389:** Uses `TimeoutNavigationHelper.getGameId()` which may have fallbacks
- **Contract Violation:** ❌ Reads from multiple sources (URL → localStorage)

**Location:** `FrontEnd/static/box-score.js`
- **Line 9:** Read from URL params only: `urlParams.get('game_id')`
- **Contract Compliance:** ✅ Single source (URL)

**Location:** `FrontEnd/static/js/state/gameStore.js`
- **Line 55-60:** `getGameId()` returns in-memory state
- **Usage:** Minimal, only stores gameId temporarily

#### Frontend Writes (WHERE IT'S WRITTEN TO):

**Location:** `FrontEnd/static/js/phaser/bootGame.js`
- **Line 1961-1968:** No longer writes to localStorage (fallback removed)

**Location:** `FrontEnd/static/set-lineup.js`
- **Line 36-40:** Clears localStorage if new matchup detected
- **Line 63:** Sets gameId from localStorage if teams match

**Location:** `FrontEnd/static/js/shared/timeoutNavigationHelper.js`
- **Line 17-234:** Builds URL params with game_id, writes to navigation URLs
- **Contract Compliance:** ✅ Writes to URL (correct)

#### Backend Reads (WHERE IT'S READ FROM):

**Location:** `BackEnd/api/api.py`
- **Line 930:** `get_game_state(game_id: str)` - from URL path parameter
- **Line 951:** Reads from `ongoing_games` cache if `source != "db"`
- **Line 1051:** Reads from `games_collection` database if cache miss
- **Contract Compliance:** ✅ Reads from URL → cache → DB (correct precedence)

**Location:** `BackEnd/api/api.py`
- **Line 1316:** `simulate_quarter_endpoint(request: QuarterSimulationRequest)`
- **Line 2092:** Reads `request.game_id` (from request body)
- **Line 2098-2108:** Validates game document exists in DB (fails loudly if missing)
- **Contract Compliance:** ✅ Reads from request → validates in DB

**Location:** `BackEnd/api/api.py`
- **Line 3352:** `init_game(request: dict)` - generates new game_id

#### Backend Writes (WHERE IT'S WRITTEN TO):

**Location:** `BackEnd/api/api.py`
- **Line 2111:** `ongoing_games[game_id] = gm` (cache write)
- **Line 3473:** `games_collection.update_one({"_id": game_id}, ...)` (DB write)
- **Line 3477:** `ongoing_games[game_id] = gm` (cache write)

**Location:** `BackEnd/api/api.py`
- **Line 2593:** `games_collection.update_one({"_id": game_id}, ...)` (DB write on quarter save)

#### Contract Violations Summary:

1. **Frontend: Multiple Read Sources**
   - `set-lineup.js` line 24-25: URL → localStorage fallback
   - `game-plan.js` line 32: URL → localStorage fallback
   - `set-lineup.js` line 57-65: Additional localStorage check if URL missing
   - **Action Required:** Remove localStorage fallbacks, fail loudly if URL missing

2. **Frontend: localStorage Writes**
   - `set-lineup.js` line 36-40: Clears/writes to localStorage
   - **Action Required:** Only use localStorage for explicit "Resume Last Game" feature

---

### 2. `franchise_id`

**Contract Requirement:** Pointer (URL params), points to Truth (Server DB)

#### Frontend Reads:

**Location:** `FrontEnd/static/js/phaser/bootGame.js`
- **Line 89:** Read from URL params: `urlParams.get('franchise_id')`
- **Line 90-93:** Read from localStorage: `localStorage.getItem('franchise_id')`
- **Line 97:** Fallback: URL → localStorage (if mode === 'franchise')
- **Contract Violation:** ❌ Reads from multiple sources (URL → localStorage)

**Location:** `FrontEnd/static/set-lineup.js`
- **Line 18:** Read from URL params only: `urlParams.get('franchise_id')`

**Location:** `FrontEnd/static/game-plan.js`
- **Line 26:** Read from URL params only: `urlParams.get('franchise_id')`

**Location:** `FrontEnd/static/box-score.js`
- **Line 13:** Read from URL params only: `urlParams.get('franchise_id')`

#### Frontend Writes:

**Location:** `FrontEnd/static/js/phaser/bootGame.js`
- **Line 98-100:** Writes to localStorage if found in URL
- **Contract Violation:** ❌ Should only write for explicit "Resume Last Game" feature

#### Backend Reads:

**Location:** `BackEnd/api/api.py`
- **Line 1316:** `simulate_quarter_endpoint()` - reads `request.franchise_id`

**Location:** `BackEnd/api/gameplan_routes.py`
- **Line 912:** `get_gameplan()` - reads `franchise_id` from request params

**Location:** `BackEnd/api/api.py`
- **Line 3352:** `init_game()` - reads `request.get('franchise_id')`

#### Backend Writes:

**Location:** `BackEnd/api/api.py`
- **Line 2616-2617:** Writes `franchise_id` to game document if present

#### Contract Violations Summary:

1. **Frontend: Multiple Read Sources**
   - `bootGame.js` line 90-97: URL → localStorage fallback
   - **Action Required:** Remove localStorage fallback, fail loudly if URL missing

2. **Frontend: localStorage Writes**
   - `bootGame.js` line 98-100: Writes to localStorage
   - **Action Required:** Only use localStorage for explicit "Resume Last Game" feature

---

### 3. `tournament_id`

**Contract Requirement:** Pointer (URL params), points to Truth (Server DB)

#### Frontend Reads:

**Location:** `FrontEnd/static/js/phaser/bootGame.js`
- **Line 86:** Read from URL params only: `urlParams.get('tournament_id')`

**Location:** `FrontEnd/static/set-lineup.js`
- **Line 20:** Read from URL params only: `urlParams.get('tournament_id')`

**Location:** `FrontEnd/static/game-plan.js`
- **Line 28:** Read from URL params only: `urlParams.get('tournament_id')`

**Location:** `FrontEnd/static/box-score.js`
- **Line 14:** Read from URL params only: `urlParams.get('tournament_id')`

#### Backend Reads:

**Location:** `BackEnd/api/api.py`
- **Line 1316:** `simulate_quarter_endpoint()` - reads `request.tournament_id`

**Location:** `BackEnd/api/gameplan_routes.py`
- **Line 912:** `get_gameplan()` - reads `tournament_id` from request params

#### Backend Writes:

**Location:** `BackEnd/api/api.py`
- **Line 2616-2617:** Writes `tournament_id` to game document if present

#### Contract Violations Summary:

- **No Violations Found** ✅

---

### 4. `playbook_settings`

**Contract Requirement:** Truth (Server DB), cached in gameStore (frontend) and ongoing_games (backend)

#### Frontend Reads:

**Location:** `FrontEnd/static/playbooks.js`
- **Line 295-325:** `async init()` - reads from API endpoint `/api/playbooks`
- API endpoint reads from DB (game/franchise/tournament document)

**Location:** `FrontEnd/static/js/phaser/bootGame.js`
- **Line 142-178:** `async loadGamePlanSettings()` - reads from API endpoint `/api/gameplan`
- API endpoint reads from DB

#### Frontend Writes:

**Location:** `FrontEnd/static/playbooks.js`
- **Line 2095-2256:** `async savePlaybookSettings()` - writes to API endpoint `/api/playbooks`
- API endpoint writes to DB

#### Backend Reads:

**Location:** `BackEnd/api/gameplan_routes.py`
- **Line 1698:** `get_playbooks()` - reads from DB (game/franchise/tournament document)
- **Line 1807-1815:** Team ID resolution logic (may read from multiple sources)

**Location:** `BackEnd/utils/shared.py`
- **Line 718:** `summarize_game_state()` - reads playbook_settings from DB when preserving settings

#### Backend Writes:

**Location:** `BackEnd/api/gameplan_routes.py`
- **Line 1698:** `save_playbooks()` - writes to DB (game/franchise/tournament document)
- **Line 1807-1815:** Team ID resolution logic (may write to wrong key if resolution fails)

#### Contract Violations Summary:

1. **Backend: Team ID Resolution Issues**
   - `gameplan_routes.py` line 1807-1815: Complex resolution logic may save to wrong key (team name vs team_id)
   - **Action Required:** Simplify team ID resolution, ensure canonical team_id keys

2. **Frontend: No Cache**
   - Playbook settings read directly from API each time
   - **Action Required:** Add optional cache in gameStore (mirror only, disposable)

---

### 5. `strategy_settings` (Game Plan)

**Contract Requirement:** Truth (Server DB), cached in gameStore (frontend) and ongoing_games (backend)

#### Frontend Reads:

**Location:** `FrontEnd/static/game-plan.js`
- **Line 142-178:** Reads from API endpoint `/api/gameplan`
- API endpoint reads from DB

**Location:** `FrontEnd/static/js/phaser/bootGame.js`
- **Line 142-178:** `async loadGamePlanSettings()` - reads from API endpoint `/api/gameplan`
- API endpoint reads from DB

#### Frontend Writes:

**Location:** `FrontEnd/static/game-plan.js`
- **Line 356-445:** `async saveSettings()` - writes to API endpoint `/api/gameplan`
- API endpoint writes to DB

#### Backend Reads:

**Location:** `BackEnd/api/gameplan_routes.py`
- **Line 912:** `get_gameplan()` - reads from DB (game/franchise/tournament document)

**Location:** `BackEnd/utils/shared.py`
- **Line 718:** `summarize_game_state()` - reads strategy_settings from DB when preserving settings

#### Backend Writes:

**Location:** `BackEnd/api/gameplan_routes.py`
- **Line 1024:** `update_gameplan()` - writes to DB (game/franchise/tournament document)

#### Contract Violations Summary:

- **No Violations Found** ✅

---

### 6. `quarter`

**Contract Requirement:** Truth (Server DB), cached in gameStore (frontend) and ongoing_games (backend)

#### Frontend Reads:

**Location:** `FrontEnd/static/js/phaser/bootGame.js`
- **Line 117:** Read from URL params: `urlParams.has('quarter') ? parseInt(urlParams.get('quarter'), 10) : 0`
- Defaults to 0 if missing (pre-game screen)

**Location:** `FrontEnd/static/set-lineup.js`
- **Line 23:** Read from URL params with default: `parseInt(urlParams.get('quarter'), 10) || 1`

**Location:** `FrontEnd/static/game-plan.js`
- **Line 30:** Read from URL params with default: `parseInt(urlParams.get('quarter'), 10) || 1`

#### Backend Reads:

**Location:** `BackEnd/api/api.py`
- **Line 930:** `get_game_state()` - reads quarter from DB or ongoing_games cache
- **Line 2593:** `simulate_quarter_endpoint()` - reads `request.quarter`

#### Backend Writes:

**Location:** `BackEnd/api/api.py`
- **Line 2593:** `summarize_game_state()` - writes quarter to DB
- **Line 2111:** `ongoing_games[game_id].quarter` - updates in-memory cache

#### Contract Violations Summary:

- **No Violations Found** ✅ (defaults are acceptable for pre-game state)

---

## Summary of Contract Violations

### Critical Violations (Must Fix):

1. **`game_id` - Multiple Frontend Read Sources**
   - **Files:** `set-lineup.js`, `game-plan.js`
   - **Issue:** URL → localStorage fallback chains
   - **Impact:** Settings can be lost if wrong game_id is used
   - **Fix:** Remove all localStorage fallbacks, fail loudly if URL missing

2. **`franchise_id` - Multiple Frontend Read Sources**
   - **File:** `bootGame.js`
   - **Issue:** URL → localStorage fallback
   - **Impact:** Wrong franchise context can be loaded
   - **Fix:** Remove localStorage fallback, fail loudly if URL missing

3. **`playbook_settings` - Team ID Resolution Issues**
   - **File:** `gameplan_routes.py`
   - **Issue:** Complex resolution logic may save to wrong key
   - **Impact:** Settings saved to team name key instead of team_id key
   - **Fix:** Simplify resolution, ensure canonical team_id keys

### Medium Priority Violations:

4. **`game_id` - localStorage Writes**
   - **Files:** `set-lineup.js`, `bootGame.js`
   - **Issue:** Writes to localStorage (not just for explicit resume feature)
   - **Impact:** Creates invisible fallback chain
   - **Fix:** Only write to localStorage for explicit "Resume Last Game" feature

5. **`franchise_id` - localStorage Writes**
   - **File:** `bootGame.js`
   - **Issue:** Writes to localStorage (not just for explicit resume feature)
   - **Impact:** Creates invisible fallback chain
   - **Fix:** Only write to localStorage for explicit "Resume Last Game" feature

### Low Priority (Not Violations, But Improvements):

6. **`playbook_settings` - No Frontend Cache**
   - **Issue:** Settings read directly from API each time
   - **Impact:** Unnecessary API calls
   - **Fix:** Add optional cache in gameStore (mirror only, disposable)

---

## Recommended Implementation Order

### Phase 1.1: Fix Critical Violations (Week 1)
1. Remove `game_id` localStorage fallbacks from `set-lineup.js` and `game-plan.js`
2. Remove `franchise_id` localStorage fallback from `bootGame.js`
3. Simplify `playbook_settings` team ID resolution in `gameplan_routes.py`
4. Add explicit error handling for missing required pointers
5. **Add `game_id` normalization at API entry points** (Standardize to ObjectId format)
   - Normalize at route handler level for:
     - `GET /api/game/{game_id}` (path param)
     - `POST /api/simulate-quarter` (request.game_id)
     - `GET/PUT /api/gameplan` (game_id query/body param)
     - `GET/POST /api/playbooks` (game_id query/body param)
     - `POST /api/call-timeout` (request.game_id if present)
   - Use `normalize_game_id()` from `game_id_utils.py` at entry point
   - Keep try-both format lookup in DB queries (temporary backward compatibility)
   - Log when normalization occurs (to track format inconsistencies)

### Phase 1.2: Fix Medium Priority Violations (Week 1-2)
1. Restrict localStorage writes to explicit "Resume Last Game" feature only
2. Add explicit "Resume Last Game" button/feature if needed

### Phase 1.3: Add Improvements (Week 2)
1. Add optional frontend cache for `playbook_settings` in gameStore
2. Add telemetry for state read/write sources

### Phase 1.4: Architecture Simplification & Redesign (Week 2-3)
**Goal:** Simplify the persistence architecture by removing complexity, standardizing formats, and establishing clear ownership.

**Rationale:** Current architecture has too many moving parts (team ID resolution, multiple document reloads, legacy compatibility, dual application). This creates multiple failure points and makes debugging difficult. Simplification will reduce bugs, improve maintainability, and increase reliability.

**Core Principles:**
1. **Single Source of Truth:** DB only (no in-memory cache for settings)
2. **Single Format:** Standardize on `team_id` (e.g., "MORRISTOWN") - no ObjectId, no team names
3. **Single Save Point:** `/api/playbooks` and `/api/gameplan` save to DB and apply to GameManager in one transaction
4. **Single Load Point:** `simulate-quarter` loads settings once and applies them
5. **Fail Loudly:** No silent fallbacks - if team_id can't be resolved, error immediately
6. **Clear Ownership:** Each setting has one place it's saved, one place it's loaded

**Steps:**

1. **Standardize Team ID Format**
   - **Decision:** Use canonical `team_id` format everywhere (e.g., "MORRISTOWN", "OCEAN_CITY")
   - **Actions:**
     - Remove ObjectId format handling (normalize to string at API entry points)
     - Remove team name → team_id resolution (require team_id everywhere)
     - Update all API endpoints to accept only `team_id` format
     - Update frontend to always send `team_id` (not team name)
   - **Validation:** All API calls use `team_id` format, no name resolution needed

2. **Remove Legacy Compatibility**
   - **Decision:** Migrate existing data once, then remove all fallbacks
   - **Actions:**
     - Create one-time migration script to convert team name keys → team_id keys in all game documents
     - Run migration script on staging, verify data integrity
     - Remove legacy team name key fallbacks from:
       - `save_playbooks()` in `gameplan_routes.py`
       - `update_gameplan()` in `gameplan_routes.py`
       - `get_playbooks()` in `gameplan_routes.py`
       - `get_gameplan()` in `gameplan_routes.py`
       - `load_team_settings_from_doc()` in `api.py`
       - `summarize_game_state()` in `shared.py`
     - Remove ObjectId format fallbacks (keep normalization at entry points only)
   - **Validation:** All code paths use `team_id` only, no fallback logic remains

3. **Simplify Settings Save/Load Flow**
   - **Decision:** Single save point, single load point, clear data flow
   - **Actions:**
     - **Save Flow:**
       - `save_playbooks()` / `update_gameplan()` → Save to DB (with team_id key) → Apply to GameManager (if in cache) → Return success
       - Remove all intermediate reloads and fallbacks
     - **Load Flow:**
       - `simulate-quarter` → Load from DB once (by team_id) → Apply to GameManager → Start simulation
       - Remove multiple document reloads in `get_playbooks()` and `get_gameplan()`
       - Remove cross-instance persistence fallbacks (core teams collection lookup)
   - **Validation:** Settings save/load happens in exactly one place each, no duplicate logic

4. **Create Settings Manager Class (Optional)**
   - **Decision:** Extract all save/load logic into single class for better organization
   - **Actions:**
     - Create `SettingsManager` class in `BackEnd/utils/settings_manager.py`
     - Move all save/load logic from scattered locations into this class
     - Methods: `save_playbook_settings()`, `load_playbook_settings()`, `save_strategy_settings()`, `load_strategy_settings()`
     - Update all API endpoints to use SettingsManager
   - **Validation:** All settings operations go through SettingsManager, no scattered code

5. **Simplify Mode Handling**
   - **Decision:** Same storage structure for all modes, just different document types
   - **Actions:**
     - Ensure all modes use identical `teams.{team_id}.playbook_settings` structure
     - Ensure all modes use identical `teams.{team_id}.strategy_settings` structure
     - Remove mode-specific branching in save/load logic (use mode only to select collection)
   - **Validation:** Save/load logic is identical across all modes, only collection differs

6. **Add Comprehensive Tests**
   - **Actions:**
     - Test: Save playbook settings → Verify DB write → Verify GameManager update
     - Test: Save game plan settings → Verify DB write → Verify GameManager update
     - Test: Load settings on game start → Verify settings applied to GameManager
     - Test: Settings persist through timeout → Verify settings loaded correctly on resume
     - Test: Team ID resolution fails → Verify explicit error (not silent fallback)
   - **Validation:** All tests pass, no silent failures

**Trade-offs:**
- **One-time data migration required:** Need to migrate existing game documents to use `team_id` keys only
- **Backward compatibility broken:** Old data formats will no longer work (but migration handles this)
- **Short-term complexity:** Migration adds temporary complexity, but long-term simplification is worth it

**Success Criteria:**
- ✅ All team ID resolution uses single format (`team_id` string)
- ✅ No legacy fallback code remains
- ✅ Settings save/load happens in exactly one place each
- ✅ All tests pass
- ✅ Settings persist correctly through entire game flow (init → save → gameplay → timeout → resume)

**Dependencies:**
- Phase 1.1 must be complete (critical violations fixed)
- Phase 1.2 should be complete (localStorage restrictions)
- Data migration script must be tested on staging before production

---

## Next Steps

1. **Review this audit** → Confirm findings and priorities
2. **Begin Phase 1.1** → Fix critical violations
3. **Add tests** → Verify fixes don't break existing functionality
4. **Continue audit** → Document remaining state variables (player stats, NG, attributes, etc.)
5. **Plan Phase 1.4** → Design data migration strategy and SettingsManager class structure

---

**Document Status:** Initial audit complete for core state variables. Phase 1.4 (Architecture Simplification) added. Ready for review and Phase 1.1 implementation.

