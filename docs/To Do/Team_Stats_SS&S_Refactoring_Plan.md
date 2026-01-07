# Team Stats SS&S Refactoring Plan

**Status:** 📋 **PLANNED**  
**Priority:** High (removes ~240 lines of duplicate code, prevents future bugs)  
**Estimated Effort:** 2-3 hours

## Overview

Refactor team stats rendering and aggregation to use shared code between Tournament and Franchise modes, eliminating code duplication and ensuring consistent behavior.

## Current State Analysis

### Frontend Duplication
- **`renderTeamStatsTable()`**: ~120 lines duplicated between `tournament.js` and `franchise-command-center.js`
- **`sortTeamStats()`**: ~40 lines duplicated between `tournament.js` and `franchise-command-center.js`
- **`renderTeamStats()`**: Similar wrapper functions with minor differences
- **Total Duplication**: ~160 lines of frontend code

### Backend Duplication
- **Team stats aggregation**: ~130 lines duplicated between `tournament_routes.py` and `franchise_routes.py`
- **Team name resolution**: Similar logic with minor differences
- **Total Duplication**: ~130 lines of backend code

### Unnecessary Code from Siloed Fix
- **Tournament `refreshTeamStats()` (line 763)**: Added roster refresh logic that's redundant (already handled by `handleTournamentUpdate()`)
- **Tournament `refreshTeamStats()` (line 1658)**: Duplicate function with different purpose (should be consolidated)
- **Tournament `renderTeamStats()` wrapper**: Minimal logic, could be inlined or simplified

## Refactoring Plan

### Phase 1: Frontend Shared Module

#### Step 1.1: Create Shared Team Stats Table Module
**File:** `FrontEnd/static/js/shared/teamStatsTable.js`

**Exports:**
```javascript
/**
 * Renders team stats table with totals row
 * @param {Array} teams - Array of {team: string, stats: {...}} objects
 * @param {string} tbodyId - ID of tbody element to render into
 */
export function renderTeamStatsTable(teams, tbodyId = 'teamstats-body')

/**
 * Sorts team stats data and re-renders table
 * @param {string} statKey - Stat key to sort by
 * @param {Array} teamsData - Teams data array (will be sorted in place)
 * @param {string} tbodyId - ID of tbody element to render into
 */
export function sortTeamStats(statKey, teamsData, tbodyId = 'teamstats-body')
```

**Implementation:**
- Extract `renderTeamStatsTable()` logic from both files
- Extract `sortTeamStats()` logic from both files
- Use `tbodyId` parameter instead of hardcoded `'teamstats-body'`
- Ensure W/L totals initialization is included (fixes the bug permanently)

#### Step 1.2: Update Tournament Mode
**File:** `FrontEnd/static/tournament.js`

**Changes:**
1. Import shared module: `import { renderTeamStatsTable, sortTeamStats } from './js/shared/teamStatsTable.js';`
2. Replace `renderTeamStatsTable()` function (lines 799-919) with shared import
3. Replace `sortTeamStats()` function (lines 921-960) with shared import
4. Simplify `renderTeamStats()` wrapper (lines 774-781):
   - Keep data transformation logic (if any)
   - Call shared `renderTeamStatsTable()` instead of local function
   - Keep sortable header setup (or move to shared module)
5. **Remove unnecessary code:**
   - Remove duplicate `refreshTeamStats()` at line 763 (keep the one at line 1658, but rename/consolidate)
   - Remove roster refresh logic from `refreshTeamStats()` (lines 769-772) - this is redundant with `handleTournamentUpdate()`
   - Simplify `refreshTeamStats()` to only fetch and render team stats (not roster)

#### Step 1.3: Update Franchise Mode
**File:** `FrontEnd/static/franchise-command-center.js`

**Changes:**
1. Import shared module: `import { renderTeamStatsTable, sortTeamStats } from './js/shared/teamStatsTable.js';`
2. Replace `renderTeamStatsTable()` function (lines 219-339) with shared import
3. Replace `sortTeamStats()` function (lines 341-380) with shared import
4. Simplify `renderTeamStats()` wrapper (lines 198-217):
   - Keep data transformation logic (if any)
   - Call shared `renderTeamStatsTable()` instead of local function
   - Keep sortable header setup (or move to shared module)

#### Step 1.4: Consolidate Sortable Header Setup
**Decision Point:** Should sortable header setup be in shared module or mode-specific?

**Option A (Recommended):** Move to shared module
- Create `setupTeamStatsSorting(tbodyId, teamsData)` function
- Handles all click listeners and header styling
- Both modes call it after initial render

**Option B:** Keep mode-specific
- Each mode sets up its own sortable headers
- Shared module just provides rendering/sorting functions

### Phase 2: Backend Shared Utility

#### Step 2.1: Create Shared Team Stats Aggregator
**File:** `BackEnd/utils/team_stats_aggregator.py`

**Function:**
```python
def aggregate_team_stats(
    players_dict: Dict[str, Dict],
    teams_dict: Dict[str, Any],
    collection_type: str = 'tournament'  # 'tournament' or 'franchise'
) -> List[Dict[str, Any]]:
    """
    Aggregates player stats into team stats.
    
    Args:
        players_dict: Dictionary of {player_id: {meta: {...}, season: {...}}}
        teams_dict: Dictionary of team objects (tournament.teams or franchise.franchise_teams)
        collection_type: 'tournament' or 'franchise' (for logging/debugging)
    
    Returns:
        List of {team: str, stats: {...}} dictionaries
    """
```

**Implementation:**
- Extract common aggregation logic from both endpoints
- Handle team_id normalization (string conversion)
- Map 3PTM/3PTA to TPM/TPA for output
- Return standardized format: `[{"team": "Team Name", "stats": {...}}, ...]`

#### Step 2.2: Create Shared Team Name Resolver
**File:** `BackEnd/utils/team_stats_aggregator.py`

**Function:**
```python
def resolve_team_names_and_standings(
    team_stats_map: Dict[str, Dict[str, int]],
    teams_collection: Collection
) -> Tuple[Dict[str, Dict], Dict[str, str]]:
    """
    Resolves team IDs to team names and fetches standings (W/L, PF/PA).
    
    Returns:
        Tuple of (standings_data, team_id_to_name_map)
    """
```

#### Step 2.3: Update Tournament Endpoint
**File:** `BackEnd/api/tournament_routes.py`

**Changes:**
1. Import shared utility: `from BackEnd.utils.team_stats_aggregator import aggregate_team_stats, resolve_team_names_and_standings`
2. Replace aggregation logic (lines 88-152) with:
   ```python
   team_stats_map = aggregate_team_stats(
       players,
       tournament_teams,
       collection_type='tournament'
   )
   ```
3. Replace team name resolution (lines 153-215) with shared function
4. Keep Tournament-specific deduplication logic (if needed) or move to shared utility

#### Step 2.4: Update Franchise Endpoint
**File:** `BackEnd/api/franchise_routes.py`

**Changes:**
1. Import shared utility: `from BackEnd.utils.team_stats_aggregator import aggregate_team_stats, resolve_team_names_and_standings`
2. Replace aggregation logic (lines 1316-1354) with shared function
3. Replace team name resolution (lines 1358-1392) with shared function
4. Keep Franchise-specific logic (if any) or move to shared utility

### Phase 3: Cleanup and Testing

#### Step 3.1: Remove Unnecessary Code
**Tournament Mode (`tournament.js`):**
- ✅ Remove duplicate `refreshTeamStats()` at line 763 (keep consolidated version)
- ✅ Remove roster refresh logic from `refreshTeamStats()` (lines 769-772)
- ✅ Simplify `refreshTeamStats()` to only handle team stats (not roster)
- ✅ Remove local `renderTeamStatsTable()` function (lines 799-919)
- ✅ Remove local `sortTeamStats()` function (lines 921-960)

**Franchise Mode (`franchise-command-center.js`):**
- ✅ Remove local `renderTeamStatsTable()` function (lines 219-339)
- ✅ Remove local `sortTeamStats()` function (lines 341-380)

**Backend:**
- ✅ Remove duplicate aggregation logic from `tournament_routes.py` (lines 88-215)
- ✅ Remove duplicate aggregation logic from `franchise_routes.py` (lines 1316-1398)

#### Step 3.2: Testing Checklist
- [ ] Tournament mode: Team stats table renders correctly
- [ ] Tournament mode: Totals row shows correct W/L (not undefined)
- [ ] Tournament mode: Sorting works for all columns
- [ ] Franchise mode: Team stats table renders correctly
- [ ] Franchise mode: Totals row shows correct W/L
- [ ] Franchise mode: Sorting works for all columns
- [ ] Both modes: All columns visible without horizontal scroll
- [ ] Both modes: Data refreshes correctly after game completion
- [ ] Backend: Tournament team stats endpoint returns correct format
- [ ] Backend: Franchise team stats endpoint returns correct format

## Code Reduction Summary

**Frontend:**
- Remove: ~160 lines of duplicate code
- Add: ~120 lines of shared module
- Net Reduction: ~40 lines + shared maintenance benefits

**Backend:**
- Remove: ~130 lines of duplicate code
- Add: ~100 lines of shared utility
- Net Reduction: ~30 lines + shared maintenance benefits

**Total:**
- Remove: ~290 lines of duplicate code
- Add: ~220 lines of shared code
- Net Reduction: ~70 lines + significant maintenance benefits

## Benefits

1. **Single Source of Truth**: One fix applies to both modes
2. **Bug Prevention**: W/L totals bug can't happen again (shared code)
3. **Consistency**: Both modes behave identically
4. **Maintainability**: Update once, both modes benefit
5. **Testability**: Shared code can be unit tested once
6. **Code Quality**: Follows DRY (Don't Repeat Yourself) principle

## Migration Strategy

1. **Create shared modules first** (non-breaking)
2. **Update Tournament mode** (test thoroughly)
3. **Update Franchise mode** (test thoroughly)
4. **Remove old code** (cleanup)
5. **Verify both modes work** (end-to-end testing)

## Risk Assessment

**Low Risk:**
- Shared frontend module is pure presentation logic
- Shared backend utility is pure data transformation
- Both modes already use identical data structures
- Can be done incrementally (create shared, then migrate one mode at a time)

**Mitigation:**
- Keep old code until new code is verified working
- Test both modes after each step
- Can rollback easily if issues arise

## Notes

- The W/L totals bug is a perfect example of why this refactoring is needed
- Tournament had the bug, Franchise didn't - because they were maintained separately
- With shared code, this bug would have been fixed once for both modes
- Future enhancements (new stats, formatting changes) only need to be done once

