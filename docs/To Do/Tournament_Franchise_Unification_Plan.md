# Tournament & Franchise Mode Unification Plan

**Date:** January 2025  
**Status:** 📋 Planning  
**Goal:** Unify Tournament and Franchise modes to use identical code patterns, with only mode variable differences and intentional feature differences (training, recruits, career stats, bracket vs schedule)

---

## Summary of Prior Discussion Agreements

1. ✅ **Field Name Standardization**: `franchise_teams` → `teams` (standardize to `teams`)
2. ✅ **Training**: Leave Franchise as-is (working perfectly). If simple, sunset Tournament training code (already disabled).
3. ✅ **Frontend Roster/Stats Rendering**: Extract shared functions to unify code
4. ✅ **API Patterns**: Identify and fix inconsistencies

---

## Phase 1: Field Name Standardization

### Change: `franchise_teams` → `teams`

**Rationale:** Both modes store identical team object structures. Using different field names creates unnecessary branching and maintenance burden.

**Files to Update:**

#### Backend:
- `BackEnd/api/franchise_routes.py` - All references to `franchise_teams`
- `BackEnd/api/gameplan_routes.py` - References in `ensure_team_objects_exist()`
- `BackEnd/utils/stat_updater.py` - References in `finalize_game()` and `_update_offensive_play_season_stats()`
- `BackEnd/models/franchise_manager.py` - Initialization code
- `BackEnd/tournament/eos_tournament.py` - References (if any)
- `BackEnd/utils/team_stats_aggregator.py` - Parameter name (already uses `team_ids` generically)

#### Frontend:
- `FrontEnd/static/franchise-command-center.js` - All references
- `FrontEnd/static/tournament.js` - Verify consistency (already uses `teams`)

#### Database Migration:
- **Backward Compatibility**: Add read fallback to check both `franchise_teams` and `teams` during transition
- **Migration Script**: Optional script to update existing franchise documents

**Impact:**
- Eliminates mode-specific branching in team data access
- Reduces code duplication
- Makes codebase more maintainable

---

## Phase 2: Tournament Training Code Removal

### Status: Already Disabled (Returns 404)

**Files to Clean Up:**

#### Backend:
- `BackEnd/api/tournament_routes.py`:
  - Remove `TournamentTrainingRequest` model (lines ~67-70)
  - Remove unreachable code block in `run_tournament_training()` (lines ~914-1198, wrapped in `if False:`)
  - Keep minimal stub endpoint returning 404 for backward compatibility:
    ```python
    @router.post("/tournament/run-training")
    def run_tournament_training(req: Any):
        raise HTTPException(status_code=404, detail="Training is not available in Tournament mode")
    ```

#### Frontend:
- `FrontEnd/static/tournament.js` - Verify no calls to training endpoint (should already be removed)
- `FrontEnd/static/training.js` - Verify tournament mode handling (should already handle 404 gracefully)

#### Documentation:
- `docs/docs_1_systems/01_Game_Mode_Systems/Tournament_Mode_Systems.md` - Update to reflect training is disabled
- Remove any references to tournament training functionality

**Impact:**
- Removes ~300 lines of dead code
- Reduces confusion about tournament training capability
- Cleaner codebase

---

## Phase 3: API Endpoint Consistency

### 3.1 Prefix Standardization

**Issue:** Tournament has two endpoints without `/tournament/` prefix

**Changes Required:**

1. **`/start-tournament` → `/tournament/start`**
   - Update endpoint: `BackEnd/api/tournament_routes.py` line ~126
   - Update frontend calls:
     - `FrontEnd/static/tournament-select.js` (if exists)
     - `FrontEnd/static/mode-select.js` (if calls this)
   - **Backward Compatibility**: Add redirect or keep old endpoint temporarily

2. **`/simulate-tournament-round` → `/tournament/simulate-round`**
   - Update endpoint: `BackEnd/api/tournament_routes.py` line ~159
   - Update frontend calls:
     - `FrontEnd/static/tournament.js`
   - **Backward Compatibility**: Add redirect or keep old endpoint temporarily

**Impact:**
- Consistent API naming pattern
- Easier to understand and maintain
- Better developer experience

### 3.2 Missing Endpoint Equivalents (Analysis)

**Intentional Differences (No Action Needed):**
- `/franchise/standings` vs Tournament bracket (different data structure)
- `/franchise/schedule` vs Tournament bracket (different data structure)
- `/franchise/recruits` (Franchise-only feature)
- `/franchise/complete-week` vs `/tournament/save-result` (different progression models)

**Potential Gaps (Investigate):**
- `/franchise/team-player-stats/{team_id}` - Tournament equivalent may be needed
- `/franchise/team-player-stats` - Tournament equivalent may be needed
- `/franchise/latest-training` - Tournament equivalent not needed (training disabled)
- `/franchise/training-points` - Tournament equivalent not needed (training disabled)
- `/franchise/scouting-report` - Verify if Tournament needs this

**Action Items:**
- Review if Tournament mode needs team-player-stats endpoints
- Verify scouting-report usage in Tournament mode

---

## Phase 4: Frontend Code Unification

### 4.1 Roster Loading & Stats Merging

**Current State:**
- Franchise: `franchise-command-center.js` - `init()` function loads roster, merges stats
- Tournament: `tournament.js` - `loadRoster()` function loads roster, merges stats

**Unification Opportunity:**
- Extract shared function: `loadRosterWithStats(mode, docId, teamName)`
- Returns: `{ players: [...], stats: {...} }`
- Both modes call this function with different parameters

**Files to Create:**
- `FrontEnd/static/js/shared/rosterLoader.js` - Shared roster loading logic

**Files to Update:**
- `FrontEnd/static/franchise-command-center.js` - Use shared function
- `FrontEnd/static/tournament.js` - Use shared function

### 4.2 Roster Stats Rendering

**Current State:**
- Both modes have `renderRosterStats()` and `renderRosterStatsTable()` functions
- Tournament copied from Franchise, but may have diverged

**Unification Opportunity:**
- Extract to shared module: `FrontEnd/static/js/shared/rosterStatsRenderer.js`
- Both modes import and use same functions

**Files to Create:**
- `FrontEnd/static/js/shared/rosterStatsRenderer.js`

**Files to Update:**
- `FrontEnd/static/franchise-command-center.js` - Import shared functions
- `FrontEnd/static/tournament.js` - Import shared functions

### 4.3 Team Stats Rendering

**Current State:**
- Already unified via `TeamStatsTable` module ✅
- Both modes use `TeamStatsTable.renderTeamStatsTable()`

**Status:** ✅ Already unified

### 4.4 Command Center Structure

**Current State:**
- Both have similar tab structures (Roster, Team, Stats, Schedule)
- Similar initialization patterns

**Unification Opportunity:**
- Extract shared tab management
- Extract shared initialization patterns
- Keep mode-specific content (bracket vs schedule, recruits tab)

**Files to Create:**
- `FrontEnd/static/js/shared/commandCenterTabs.js` - Shared tab management

**Files to Update:**
- `FrontEnd/static/franchise-command-center.js` - Use shared tab management
- `FrontEnd/static/tournament.js` - Use shared tab management

---

## Phase 5: Backend Code Unification

### 5.1 Team Stats Aggregation

**Status:** ✅ Already unified via `team_stats_aggregator.py`

### 5.2 Roster Endpoints

**Current State:**
- `/franchise/roster` - Returns roster with merged stats
- `/tournament/roster` - Returns roster with merged stats

**Unification Opportunity:**
- Extract shared roster building logic
- Both endpoints call shared function with mode-specific parameters

**Files to Create:**
- `BackEnd/utils/roster_builder.py` - Shared roster building logic

**Files to Update:**
- `BackEnd/api/franchise_routes.py` - Use shared function
- `BackEnd/api/tournament_routes.py` - Use shared function

### 5.3 Command Center Data Endpoints

**Current State:**
- `/franchise/command-center/data` - Returns structured command center data
- `/tournament/command-center/data` - Returns structured command center data

**Unification Opportunity:**
- Extract shared data building logic
- Both endpoints call shared function with mode-specific parameters

**Files to Create:**
- `BackEnd/utils/command_center_data.py` - Shared command center data builder

**Files to Update:**
- `BackEnd/api/franchise_routes.py` - Use shared function
- `BackEnd/api/tournament_routes.py` - Use shared function

---

## Implementation Priority

### High Priority (Core Unification):
1. **Phase 1: Field Name Standardization** - Eliminates most mode-specific branching
2. **Phase 3.1: API Prefix Consistency** - Improves API consistency
3. **Phase 4.2: Roster Stats Rendering** - Already similar, easy win

### Medium Priority (Code Quality):
4. **Phase 2: Tournament Training Removal** - Cleanup dead code
5. **Phase 4.1: Roster Loading Unification** - Reduces duplication
6. **Phase 5.2: Roster Endpoints Unification** - Backend consistency

### Low Priority (Nice to Have):
7. **Phase 4.4: Command Center Structure** - More complex, lower impact
8. **Phase 5.3: Command Center Data** - More complex, lower impact

---

## Testing Strategy

### For Each Phase:
1. **Local Testing**: Verify both modes work correctly
2. **Staging Testing**: Deploy to staging, test full flows
3. **Backward Compatibility**: Verify old endpoints/data structures still work (if applicable)
4. **Regression Testing**: Ensure no existing functionality breaks

### Specific Test Cases:
- Franchise mode: Full season flow, training, recruits, career stats
- Tournament mode: Full tournament flow, bracket progression
- Shared features: Game Plan, Playbooks, Roster, Stats tabs
- Navigation: All mode transitions

---

## Rollout Plan

### Step 1: Field Name Standardization (Phase 1)
- Add backward compatibility layer
- Update all references
- Test thoroughly
- Deploy to staging
- Monitor for issues
- Deploy to production

### Step 2: API Consistency (Phase 3.1)
- Add new endpoints with correct prefixes
- Keep old endpoints temporarily (redirect or alias)
- Update frontend to use new endpoints
- Test thoroughly
- Remove old endpoints after frontend update

### Step 3: Code Unification (Phases 4 & 5)
- Extract shared functions
- Update both modes to use shared code
- Test thoroughly
- Deploy incrementally

### Step 4: Cleanup (Phase 2)
- Remove tournament training code
- Update documentation
- Final cleanup pass

---

## Success Criteria

✅ **Field Name Standardization:**
- All code uses `teams` instead of `franchise_teams`
- No mode-specific branching for team data access
- Backward compatibility maintained

✅ **API Consistency:**
- All Tournament endpoints use `/tournament/` prefix
- Consistent naming patterns across both modes
- No breaking changes for existing clients

✅ **Code Unification:**
- Shared functions for roster loading, stats rendering
- Reduced code duplication
- Easier maintenance

✅ **Training Code Removal:**
- Tournament training code removed
- Documentation updated
- No dead code remaining

---

## Notes

- **Backward Compatibility**: Critical for existing tournaments/franchises in production
- **Incremental Rollout**: Deploy phases separately to minimize risk
- **Testing**: Extensive testing required before production deployment
- **Documentation**: Update all relevant documentation as changes are made

---

## Open Questions

1. **Team-Player-Stats Endpoints**: Do we need Tournament equivalents of `/franchise/team-player-stats`?
2. **Scouting Report**: Is scouting report needed in Tournament mode?
3. **Migration Script**: Do we need a script to migrate `franchise_teams` → `teams` in existing documents?
4. **API Versioning**: Should we version APIs to handle breaking changes more gracefully?

---

**Last Updated:** January 2025  
**Next Review:** After Phase 1 completion

