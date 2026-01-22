# Unified State & Persistence Work Plan

**Version:** 1.0  
**Status:** Active Implementation  
**Last Updated:** January 2026  
**Purpose:** Single unified work plan consolidating audit findings and contract implementation phases.

---

## Current Status

**Completed:**
- ✅ Playcall Center slot assignments display fixed (frontend UI)
- ✅ Slot assignment button highlighting fixed (frontend UI)
- ✅ Settings persistence through timeouts (backend fixes)
- ✅ Initial state sources audit completed (core variables documented)
- ✅ Phase 1.1: Fix Critical Violations (all tasks complete)

**In Progress:**
- None

**Next Step:** Phase 1.3 - Add Improvements

---

## Unified Implementation Plan

### Phase 1: Establish Truth Sources & Fix Critical Violations (Week 1)

**Goal:** Document and enforce single authoritative source for each variable, fix critical contract violations.

#### Phase 1.1: Fix Critical Violations (Priority 1)

**Status:** ✅ Complete

**Tasks:**
1. ✅ **Remove `game_id` localStorage fallbacks**
   - **Files:** `FrontEnd/static/set-lineup.js`, `FrontEnd/static/game-plan.js`
   - **Issue:** URL → localStorage fallback chains
   - **Action:** Removed all localStorage fallbacks, fail loudly if URL missing
   - **Validation:** ✅ Missing `game_id` triggers explicit error screen

2. ✅ **Remove `franchise_id` localStorage fallback**
   - **File:** `FrontEnd/static/js/phaser/bootGame.js`
   - **Issue:** URL → localStorage fallback
   - **Action:** Verified no localStorage fallback exists (already compliant)
   - **Validation:** ✅ Missing `franchise_id` triggers explicit error screen

3. ✅ **Simplify `playbook_settings` team ID resolution**
   - **File:** `BackEnd/api/gameplan_routes.py`
   - **Issue:** Complex resolution logic may save to wrong key (team name vs team_id)
   - **Action:** Simplified resolution to 3-step pattern (direct match → name match → home/away fallback)
   - **Validation:** ✅ All settings saved to `team_id` keys only

4. ✅ **Add explicit error handling for missing required pointers**
   - **Action:** Created `errorHandler.js` with `showMissingPointerError()` function
   - **Action:** Added error screens for missing `game_id`, `franchise_id`, `tournament_id`
   - **Action:** Added recovery flows (redirect to lineup, redirect to mode select)
   - **Validation:** ✅ All missing pointers trigger explicit errors with recovery paths

5. ✅ **Add `game_id` normalization at API entry points**
   - **Action:** Standardized to ObjectId format (24-character hex string)
   - **Endpoints normalized:**
     - ✅ `GET /api/game/{game_id}` (path param)
     - ✅ `POST /api/simulate-quarter` (request.game_id)
     - ✅ `GET/PUT /api/gameplan` (game_id query/body param)
     - ✅ `GET/POST /api/playbooks` (game_id query/body param)
     - ✅ `POST /api/call-timeout` (request.game_id if present)
   - **Implementation:** Using `normalize_game_id()` at entry point
   - **Backward Compatibility:** ✅ Try-both format lookup in DB queries (temporary)
   - **Telemetry:** ✅ Logging when normalization occurs
   - **Validation:** ✅ All API entry points normalize `game_id` format

6. ✅ **Validate Lineup Screen Data Display** (Post-Phase 1.1 Validation)
   - **Action:** Fixed critical indentation bug in `get_game_state()` endpoint
   - **Issue:** `return response_data` was inside `if total_time > 100:` conditional, only returning for slow queries
   - **Fix:** Moved `return response_data` outside performance check - always returns when document found
   - **Validation:** ✅ 
     - ✅ Lineup screen correctly displays NG (energy) values during timeout/quarter breaks
     - ✅ Lineup screen correctly displays player stats (PTS, REB, AST, etc.) during timeout/quarter breaks
     - ✅ Data matches values from game state (no defaulting to 100% or 0)

**Success Criteria:**
- ✅ No localStorage fallbacks for `game_id` or `franchise_id`
- ✅ Missing pointers trigger explicit error screens
- ✅ Team ID resolution uses canonical `team_id` keys only
- ✅ All API entry points normalize `game_id` format
- ✅ Lineup screen displays accurate player data (NG and stats) from game state
- ✅ All tests pass

---

#### Phase 1.2: Fix Medium Priority Violations (Week 1-2)

**Status:** ✅ Complete

**Tasks:**
1. **Restrict localStorage writes to explicit "Resume Last Game" feature only**
   - ✅ **Files:** `FrontEnd/static/js/phaser/bootGame.js`, `FrontEnd/static/js/phaser/gameScene.js`, `FrontEnd/static/js/phaser/finalizeGame.js`
   - ✅ **Action:** Removed all automatic localStorage writes for `game_id` from gameplay files
   - ✅ **Action:** Only write `last_game_id` to localStorage when user quits mid-game (beforeunload event) for single mode
   - ✅ **Action:** Clear `last_game_id` when game completes (in `finalizeGame.js`)
   - ✅ **Validation:** localStorage only used for explicit resume feature

2. **Add explicit "Resume Last Game" button/feature (if needed)**
   - ✅ **Files:** `FrontEnd/static/mode-select.html`, `FrontEnd/static/mode-select.js`, `FrontEnd/static/mode-select.css`
   - ✅ **Action:** Implemented "Continue Your Game" section on mode-select screen (Option 2 design)
   - ✅ **Action:** Shows teams, scores, quarter, and time remaining
   - ✅ **Action:** Stores `last_game_id` in localStorage only when user quits mid-game (beforeunload)
   - ✅ **Action:** Button navigates to lineup screen with `game_id` and clears `last_game_id` (one-time use)
   - ✅ **Validation:** Resume feature works correctly, no automatic fallbacks

**Success Criteria:**
- ✅ localStorage only used for explicit "Resume Last Game" feature
- ✅ No automatic localStorage writes
- ✅ Resume feature works correctly

---

#### Phase 1.3: Add Improvements (Week 2)

**Status:** ⏳ Pending

**Tasks:**
1. **Add optional frontend cache for `playbook_settings` in gameStore**
   - **Action:** Add cache mirror in `gameStore` (disposable, rebuild from truth)
   - **Action:** Invalidate cache after DB writes
   - **Validation:** Cache improves performance, doesn't affect correctness

2. **Add telemetry for state read/write sources**
   - **Action:** Log every state read (which source, which variable)
   - **Action:** Log every state write (which source, which variable)
   - **Action:** Log cache hits/misses
   - **Action:** Log contract violations (state read from wrong source)
   - **Validation:** Telemetry captures all state operations

**Success Criteria:**
- ✅ Frontend cache improves performance without affecting correctness
- ✅ Telemetry captures all state operations
- ✅ Contract violations are logged and monitored

---

### Phase 2: Fix Pointer Flow (Week 1-2)

**Goal:** Ensure URL pointers are always present and point to valid truth.

**Status:** ⏳ Pending (depends on Phase 1.1)

**Tasks:**
1. **Fix Navigation Flow**
   - **Action:** Ensure `game_id`/`franchise_id`/`tournament_id` always in URL
   - **Action:** Update all navigation helpers to include required pointers
   - **Validation:** All navigation includes required pointers in URL

2. **Add URL Validation**
   - **Action:** Check pointers exist on page load, fail if missing
   - **Action:** Add validation in `bootGame.js`, `set-lineup.js`, `game-plan.js`
   - **Validation:** Missing pointer triggers explicit error screen

3. **Add Truth Validation**
   - **Action:** Check pointer points to existing document, fail if not found
   - **Action:** Validate `game_id` points to existing game document
   - **Action:** Validate `franchise_id` points to existing franchise document
   - **Action:** Validate `tournament_id` points to existing tournament document
   - **Validation:** Invalid pointer triggers explicit error screen

4. **Remove localStorage Fallbacks** (if not completed in Phase 1.2)
   - **Action:** Keep only explicit "Resume last game" feature
   - **Validation:** No localStorage fallbacks remain

**Success Criteria:**
- ✅ All navigation includes required pointers in URL
- ✅ Missing pointer triggers explicit error screen
- ✅ Invalid pointer triggers explicit error screen
- ✅ No localStorage fallbacks (except explicit resume feature)

---

### Phase 3: Simplify Cache Layer (Week 2)

**Goal:** Make caches explicit mirrors, not hidden fallbacks.

**Status:** ⏳ Pending

**Tasks:**
1. **Document Cache Usage**
   - **Action:** List all caches (`ongoing_games`, `gameStore`, etc.)
   - **Action:** Document refresh triggers for each cache
   - **Validation:** All caches documented with clear refresh logic

2. **Remove Cache Fallbacks**
   - **Action:** Never read from cache if truth is available
   - **Action:** Always prefer DB reads over cache reads
   - **Validation:** No code path reads from cache when truth is available

3. **Add Cache Invalidation**
   - **Action:** Clear cache after DB writes
   - **Action:** Clear cache on navigation
   - **Action:** Clear cache on version mismatch
   - **Validation:** Cache is always fresh, never stale

4. **Add Cache Telemetry**
   - **Action:** Log cache hits/misses for performance monitoring
   - **Action:** Log cache invalidation events
   - **Validation:** Cache performance metrics captured

**Success Criteria:**
- ✅ Caches are always rebuilt from truth when needed
- ✅ No code path reads from cache when truth is available
- ✅ Cache performance metrics captured

---

### Phase 4: Enforce Failure Modes (Week 2-3)

**Goal:** Replace silent failures with explicit error screens and recovery flows.

**Status:** ⏳ Pending

**Tasks:**
1. **Define Error Screens**
   - **Action:** Create error UI for missing pointer
   - **Action:** Create error UI for missing truth
   - **Action:** Create error UI for version mismatch
   - **Validation:** All error screens have clear messages

2. **Add Recovery Flows**
   - **Action:** Create explicit path back to valid state (redirect to lineup)
   - **Action:** Create explicit path back to valid state (redirect to mode select)
   - **Validation:** All errors have explicit recovery paths

3. **Remove Silent Defaults**
   - **Action:** Replace with explicit errors or user prompts
   - **Action:** Remove all "guess and hope" logic
   - **Validation:** No silent failures remain

4. **Add Error Telemetry**
   - **Action:** Log all state failures for monitoring
   - **Action:** Log recovery actions (error screen shown, redirect performed)
   - **Validation:** All failures are logged and tracked

**Success Criteria:**
- ✅ No silent failures or "guess and hope" logic
- ✅ All errors have clear user-facing messages
- ✅ All errors have explicit recovery paths

---

### Phase 5: Architecture Simplification & Redesign (Week 2-3)

**Goal:** Simplify the persistence architecture by removing complexity, standardizing formats, and establishing clear ownership.

**Status:** ⏳ Pending (depends on Phase 1.1, 1.2)

**Rationale:** Current architecture has too many moving parts (team ID resolution, multiple document reloads, legacy compatibility, dual application). This creates multiple failure points and makes debugging difficult. Simplification will reduce bugs, improve maintainability, and increase reliability.

**Core Principles:**
1. **Single Source of Truth:** DB only (no in-memory cache for settings)
2. **Single Format:** Standardize on `team_id` (e.g., "MORRISTOWN") - no ObjectId, no team names
3. **Single Save Point:** `/api/playbooks` and `/api/gameplan` save to DB and apply to GameManager in one transaction
4. **Single Load Point:** `simulate-quarter` loads settings once and applies them
5. **Fail Loudly:** No silent fallbacks - if team_id can't be resolved, error immediately
6. **Clear Ownership:** Each setting has one place it's saved, one place it's loaded

#### Phase 5.1: Standardize Team ID Format

**Tasks:**
1. **Decision:** Use canonical `team_id` format everywhere (e.g., "MORRISTOWN", "OCEAN_CITY")
2. **Actions:**
   - Remove ObjectId format handling (normalize to string at API entry points)
   - Remove team name → team_id resolution (require team_id everywhere)
   - Update all API endpoints to accept only `team_id` format
   - Update frontend to always send `team_id` (not team name)
3. **Validation:** All API calls use `team_id` format, no name resolution needed

#### Phase 5.2: Remove Legacy Compatibility

**Tasks:**
1. **Decision:** Migrate existing data once, then remove all fallbacks
2. **Actions:**
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
3. **Validation:** All code paths use `team_id` only, no fallback logic remains

#### Phase 5.3: Simplify Settings Save/Load Flow

**Tasks:**
1. **Decision:** Single save point, single load point, clear data flow
2. **Actions:**
   - **Save Flow:**
     - `save_playbooks()` / `update_gameplan()` → Save to DB (with team_id key) → Apply to GameManager (if in cache) → Return success
     - Remove all intermediate reloads and fallbacks
   - **Load Flow:**
     - `simulate-quarter` → Load from DB once (by team_id) → Apply to GameManager → Start simulation
     - Remove multiple document reloads in `get_playbooks()` and `get_gameplan()`
     - Remove cross-instance persistence fallbacks (core teams collection lookup)
3. **Validation:** Settings save/load happens in exactly one place each, no duplicate logic

#### Phase 5.4: Create Settings Manager Class (Optional)

**Tasks:**
1. **Decision:** Extract all save/load logic into single class for better organization
2. **Actions:**
   - Create `SettingsManager` class in `BackEnd/utils/settings_manager.py`
   - Move all save/load logic from scattered locations into this class
   - Methods: `save_playbook_settings()`, `load_playbook_settings()`, `save_strategy_settings()`, `load_strategy_settings()`
   - Update all API endpoints to use SettingsManager
3. **Validation:** All settings operations go through SettingsManager, no scattered code

#### Phase 5.5: Simplify Mode Handling

**Tasks:**
1. **Decision:** Same storage structure for all modes, just different document types
2. **Actions:**
   - Ensure all modes use identical `teams.{team_id}.playbook_settings` structure
   - Ensure all modes use identical `teams.{team_id}.strategy_settings` structure
   - Remove mode-specific branching in save/load logic (use mode only to select collection)
3. **Validation:** Save/load logic is identical across all modes, only collection differs

#### Phase 5.6: Add Comprehensive Tests

**Tasks:**
1. **Actions:**
   - Test: Save playbook settings → Verify DB write → Verify GameManager update
   - Test: Save game plan settings → Verify DB write → Verify GameManager update
   - Test: Load settings on game start → Verify settings applied to GameManager
   - Test: Settings persist through timeout → Verify settings loaded correctly on resume
   - Test: Team ID resolution fails → Verify explicit error (not silent fallback)
2. **Validation:** All tests pass, no silent failures

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

#### Phase 5.7: Game-Scoped Settings for Franchise/Tournament Mode (Week 3)

**Goal:** Enable game-specific settings in franchise/tournament mode without affecting master settings.

**Status:** ⏳ Pending (depends on Phase 5.1-5.6)

**Rationale:** Currently, settings changes during franchise/tournament gameplay save to the franchise/tournament document (master settings), affecting all games. This feature allows users to make game-specific adjustments during gameplay without disrupting their master playbooks/game plans. Settings are scoped to the active game document and revert to master settings when the game ends.

**User Value:**
- Master settings in franchise/tournament document remain unchanged
- Game-specific adjustments possible during active gameplay
- Settings automatically revert to master when starting new game
- Flexibility to experiment without affecting long-term strategy

**Prerequisites:**
- Phase 5.1-5.5 complete (simplified architecture in place)
- Phase 5.6 complete (base architecture tested and working)

**Tasks:**

1. **Game Initialization: Copy Settings from Master**
   - **Action:** In `init-game`, copy `playbook_settings` and `strategy_settings` from franchise/tournament doc to game doc
   - **Files:** `BackEnd/api/api.py` → `init_game()`
   - **Logic:** On game start, copy master settings to game doc as baseline
   - **Validation:** Game doc initialized with master settings, franchise/tournament doc unchanged

2. **Save Flow: Conditional Save Location**
   - **Action:** Modify `save_playbooks()` and `update_gameplan()` to save to game doc if game is active, otherwise save to franchise/tournament doc
   - **Files:** `BackEnd/api/gameplan_routes.py` → `save_playbooks()`, `update_gameplan()`
   - **Logic:**
     ```
     If F/T mode:
       If game_id provided AND game exists AND game is active (quarter > 0):
         Save to game doc (game-specific settings)
       Else:
         Save to franchise/tournament doc (master settings)
     ```
   - **Validation:** Settings saved to correct document based on context

3. **Load Flow: Game Doc → Master Fallback**
   - **Action:** Modify `get_playbooks()` and `get_gameplan()` to load from game doc first, fallback to franchise/tournament doc
   - **Files:** `BackEnd/api/gameplan_routes.py` → `get_playbooks()`, `get_gameplan()`
   - **Logic:**
     ```
     If F/T mode:
       If game_id provided AND game exists AND game has settings:
         Load from game doc (game-specific settings)
       Else:
         Load from franchise/tournament doc (master settings)
     ```
   - **Validation:** Settings loaded from correct document based on context

4. **Settings Application: Game Doc → Master Fallback**
   - **Action:** Modify `simulate-quarter` to load from game doc first, fallback to franchise/tournament doc
   - **Files:** `BackEnd/api/api.py` → `simulate_quarter_endpoint()`, `load_team_settings_from_doc()`
   - **Logic:** Try game doc first, fallback to master if missing
   - **Validation:** Settings applied from correct source at game start

5. **Timeout Persistence: Preserve Game Doc Settings**
   - **Action:** Ensure `summarize_game_state()` preserves game doc settings during timeout
   - **Files:** `BackEnd/utils/shared.py` → `summarize_game_state()`
   - **Logic:** Game doc settings already preserved (no change needed)
   - **Validation:** Game-scoped settings survive timeouts

6. **Comprehensive Testing**
   - **Action:** Test all scenarios:
     - Settings initialized from master at game start
     - Settings changes during gameplay save to game doc
     - Master settings in franchise/tournament doc unchanged
     - Settings persist through timeout
     - Settings revert to master when starting new game
     - Settings load correctly from game doc during active gameplay
     - Settings load correctly from master when no active game
   - **Validation:** All scenarios work correctly

**Edge Cases to Handle:**
- User changes settings before starting game → Saves to master (franchise/tournament doc)
- User changes settings during active gameplay → Saves to game doc
- User changes settings during timeout → Saves to game doc
- User resumes game → Loads from game doc
- User starts new game → Loads from master (franchise/tournament doc)
- User visits Command Center → Loads from master (franchise/tournament doc)

**Complexity Assessment:**
- **Game Initialization:** Low (2 hours) - straightforward copy operation
- **Save Flow Updates:** Medium (4-6 hours) - conditional logic, game state detection
- **Load Flow Updates:** Medium (4-6 hours) - similar conditional logic
- **Settings Application:** Low (2 hours) - fallback logic adjustment
- **Timeout Persistence:** Low (1 hour) - already works if settings in game doc
- **Testing:** Medium (4-6 hours) - comprehensive scenario coverage
- **Total:** 16-22 hours (2-3 days)

**Success Criteria:**
- ✅ Settings initialized from franchise/tournament doc at game start
- ✅ Settings changes during active gameplay save to game doc only
- ✅ Master settings in franchise/tournament doc remain unchanged
- ✅ Settings persist through timeouts (scoped to game doc)
- ✅ Settings revert to master when starting new game
- ✅ Settings load correctly from game doc during active gameplay
- ✅ Settings load correctly from master when no active game
- ✅ All tests pass
- ✅ All existing functionality continues to work

**Dependencies:**
- Phase 5.1-5.5 must be complete (simplified architecture foundation)
- Phase 5.6 must be complete (base architecture tested and validated)
- Helper function `get_settings_source()` recommended to reduce complexity

---

### Phase 6: Migration & Cleanup (Week 3)

**Goal:** Remove all patchwork code and enforce new contract.

**Status:** ⏳ Pending

**Tasks:**
1. **Remove Legacy Fallbacks**
   - **Action:** Delete all multi-source merging logic
   - **Action:** Remove all "try URL, then localStorage, then default" chains
   - **Validation:** No fallback chains remain

2. **Update All State Reads**
   - **Action:** Use single source per variable
   - **Action:** Remove all multi-source reads
   - **Validation:** Each variable read from exactly one source

3. **Update All State Writes**
   - **Action:** Write to authoritative source only
   - **Action:** Remove all duplicate writes
   - **Validation:** Each variable written to exactly one source

4. **Add Contract Tests**
   - **Action:** Verify no violations of state contract
   - **Action:** Test single source of truth per variable
   - **Validation:** Contract tests pass (no violations)

5. **Remove Tournament Training Code**
   - **Action:** Sunset all tournament training allocation functionality
   - **Validation:** Tournament training code removed

**Success Criteria:**
- ✅ No code reads from multiple sources for same variable
- ✅ All state writes go to authoritative source
- ✅ Contract tests pass (no violations)
- ✅ Tournament training code removed

---

### Phase 7: Testing & Validation (Week 3-4)

**Goal:** Ensure contract compliance through comprehensive testing.

**Status:** ⏳ Pending

**Tasks:**
1. **Write State Contract Tests**
   - **Action:** Verify single source of truth per variable
   - **Action:** Test that each variable has exactly one authoritative source
   - **Validation:** All contract tests pass

2. **Write Persistence Tests**
   - **Action:** Verify state persists correctly across navigation/timeouts/refresh
   - **Action:** Test `game_id` persistence across entire flow
   - **Action:** Test settings persistence through timeouts and quarter breaks
   - **Validation:** All persistence tests pass

3. **Write Integration Tests**
   - **Action:** Verify full game flow (init → settings → gameplay → timeout → resume)
   - **Action:** Test complete user journey
   - **Validation:** All integration tests pass

4. **Write Cache Tests**
   - **Action:** Verify cache invalidation and refresh behavior
   - **Action:** Test cache rebuild from truth
   - **Validation:** All cache tests pass

5. **Run Tests in CI/CD**
   - **Action:** Automate contract compliance checking
   - **Action:** Run tests on every commit
   - **Validation:** CI/CD pipeline enforces contract compliance

**Test Coverage:**
- `game_id` persistence across entire flow (init → settings → Q1 → timeout → resume)
- Settings persistence through timeouts and quarter breaks
- Cache refresh points (timeout, foul out, quarter break)
- Error handling (missing pointers, missing truth)
- Multi-tab sync (if implemented)

**Success Criteria:**
- ✅ All contract tests pass
- ✅ All persistence tests pass
- ✅ All integration tests pass
- ✅ All cache tests pass
- ✅ CI/CD pipeline enforces contract compliance

---

## Progress Tracking

### Completed ✅
- Playcall Center slot assignments display fixed
- Slot assignment button highlighting fixed
- Settings persistence through timeouts (backend fixes)
- Initial state sources audit completed
- **Phase 1.1: Fix Critical Violations** (all 6 tasks complete)
  - ✅ Removed `game_id` localStorage fallbacks
  - ✅ Verified `franchise_id` compliance (no fallback needed)
  - ✅ Simplified team ID resolution
  - ✅ Added explicit error handling
  - ✅ Added `game_id` normalization at all API entry points
  - ✅ Fixed lineup screen data display (indentation bug fix)

### In Progress 🔄
- None

### Pending ⏳
- Phase 1.2: Fix Medium Priority Violations
- Phase 1.3: Add Improvements
- Phase 2: Fix Pointer Flow
- Phase 3: Simplify Cache Layer
- Phase 4: Enforce Failure Modes
- Phase 5: Architecture Simplification & Redesign
- Phase 6: Migration & Cleanup
- Phase 7: Testing & Validation

---

## Next Steps

1. ✅ **Phase 1.1 Complete** → All critical violations fixed
2. **Begin Phase 1.2** → Fix medium priority violations (restrict localStorage writes to explicit "Resume Last Game" feature only)
3. **Continue audit** → Document remaining state variables (player stats, NG, attributes, etc.)
4. **Plan Phase 5** → Design data migration strategy and SettingsManager class structure

---

**Document Status:** Phase 1.1 and Phase 1.2 complete. Next step: Phase 1.3 - Add Improvements.

