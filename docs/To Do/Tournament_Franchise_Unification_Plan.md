# Tournament & Franchise Mode Unification Plan

**Date:** January 2025  
**Status:** 📋 Planning (Phase 1 ✅, Phase 2 ✅, Phase 2.5 Frontend bracket ✅, Phase 3.1 ✅, Phase 4.1 ✅, Phase 4.2 ✅)  
**Goal:** Unify Tournament and Franchise modes to use identical code patterns, with only mode variable differences and intentional feature differences (training, recruits, career stats, bracket vs schedule)

---

## Summary of Prior Discussion Agreements

1. ✅ **Field Name Standardization**: `franchise_teams` → `teams` (standardize to `teams`)
2. ✅ **Training**: Leave Franchise as-is (working perfectly). If simple, sunset Tournament training code (already disabled).
3. ✅ **Frontend Roster/Stats Rendering**: Extract shared functions to unify code
4. ✅ **API Patterns**: Identify and fix inconsistencies

---

## Phase 1: Field Name Standardization ✅

### Status: Done (January 2025)

**Approach taken:** `franchise_teams` was **removed** from the franchise document entirely (not renamed to `teams` on the franchise doc). Franchise team-level data lives in **FTD** (franchise_team_data collection); game and tournament docs use **`teams`** for in-game team data. No `teams` field on the franchise document (that would duplicate FTD).

**Completed:**
- **Backend:** All reads/writes of `franchise_teams` removed or replaced with FTD / game doc `teams`: stat_updater (FTD-based mapping), franchise_manager (no init of franchise_teams), gameplan_routes (path and projections), eos_tournament (team_ids from FTD), franchise_routes (FTD/team-stats), turn_manager (game_doc.teams), team_settings_manager (teams for all modes), team_stats_aggregator and franchise_standings (comments/param rename to `team_ids_map`), team_id_resolver and play_routes (comments), api (comment).
- **Frontend:** FCC and TCC use `teams` / team-stats for bracket and display; no franchise_teams references.
- **Parameter/doc cleanup:** `calculate_franchise_standings` second parameter renamed `franchise_teams` → `team_ids_map`; eos_tournament passes `team_ids_map`; docstrings and comments updated to say FTD / game doc `teams` (no franchise_teams).
- **No backward-compatibility read fallback** (would re-introduce dependency on deprecated field). Optional DB `$unset` of franchise_teams from existing franchise docs can be run separately if desired.

**Impact:** Franchise team data has a single source of truth (FTD); game/tournament docs use `teams` consistently; no mode-specific branching on franchise_teams; codebase aligned with removal.

---

## Phase 2: Tournament Training Code Removal ✅

### Status: Done (January 2025)

**Completed:**
- **Backend:** Removed `TournamentTrainingRequest`; removed ~300 lines of dead code from `run_tournament_training()`. Kept minimal stub `POST /tournament/run-training` that raises 404 ("Training is not available in Tournament mode") for backward compatibility.
- **Frontend:** Verified `tournament.js` does not call the training endpoint; `training.js` still POSTs to `/tournament/run-training` in tournament mode and handles non-OK (404) via catch + alert.
- **Documentation:** Updated `Tournament_Mode_Systems.md` to state training is disabled, stub behavior, and removed lengthy training-flow description.

**Impact:** ~300 lines of dead code removed; clearer that Tournament mode has no training.

---

## Phase 2.5: Frontend Bracket Unification ✅

**Status:** Done (January 2025)

**Goal:** Same bracket UI and layout for FCC (Franchise EOS Tournament tab) and TCC (Tournament Bracket tab).

**Completed:**
- **Shared bracket renderer:** `FrontEnd/static/bracket.js` — `renderBracketShared(container, bracketData, teamIdToNameMap, options)`. Single DOM implementation (5-column grid, matchups, logos, seeds, scores).
- **FCC Tournament tab:** Uses shared renderer; team names from `/franchise/team-stats` (one request); container uses class `bracket` + `tournament.css` for same layout as TCC.
- **TCC Bracket tab:** Uses same shared renderer; `teamIdNameMap` from `/tournament/team-stats`; TCC-only logic (applyResults, localStorage, updateCTA) unchanged around the call.
- **Layout:** Both use `tournament.css` (`.bracket` grid, `.round`, etc.); FCC container gets same padding/min-height via `franchise-command-center.css`.

**Impact:** One code path for bracket display; FCC shows team names and correct layout; no duplicate bracket DOM logic.

**Related:** `tournament_eos_bracket_merge_plan.md` §9 (Frontend Bracket Unification).

---

## Phase 3: API Endpoint Consistency

### 3.1 Prefix Standardization ✅

**Status:** Done (January 2025)

**Completed:**
- **`/tournament/start`** — New primary route; **`/start-tournament`** kept as backward-compat alias (same handler). Backend: `BackEnd/api/tournament_routes.py` registers both paths for `start_tournament`.
- **`/tournament/simulate-round`** — New primary route; **`/simulate-tournament-round`** kept as backward-compat alias (same handler). Backend: both paths for `simulate_round`.
- **Frontend:** `tournament-select.js` uses `/tournament/start`; `tournament.js` uses `/tournament/simulate-round`.
- **Tests:** `tests/test_start_tournament_resets_stats.py`, `test_sim_to_4th_quarter.py`, `test_quarter_simulation_standardization.py`, `test_gameplan_simple.py`, `test_gameplan_scenarios.py`, `test_gameplan_functionality.py` updated to use new URLs.

**Impact:** Consistent `/tournament/` prefix for tournament endpoints; no breaking change (old URLs still work).

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

### 4.1 Roster Loading & Stats Merging ✅

**Status:** Done (January 2025)

**Completed:**
- **Shared module:** `FrontEnd/static/js/shared/rosterLoader.js` — `loadRosterWithStats(rosterUrl, stateUrl)` fetches roster + state and returns `{ players }` with merged `stats.season`; `mergeRosterWithStateDoc(rosterData, stateDoc)` for merge-only (used by TCC to avoid double-fetch).
- **FCC:** `init()` builds `rosterUrl` and `stateUrl`, calls `RosterLoader.loadRosterWithStats(rosterUrl, stateUrl)`, then `renderTeam({ players: result.players })`.
- **TCC:** `loadRoster()` keeps 404 retry and fetches; after having `data` and `tournamentDoc`, calls `RosterLoader.mergeRosterWithStateDoc(data, tournamentDoc)` and assigns `data.players = merged.players`.
- **Script:** `rosterLoader.js` included in both `franchise-command-center.html` and `tournament.html`.

**Impact:** Single place for roster+state fetch/merge (FCC) and merge logic (TCC); no duplicate merge code.

### 4.2 Roster Stats Rendering ✅

**Status:** Done (January 2025)

**Completed:**
- **Shared module:** `FrontEnd/static/js/shared/rosterStatsRenderer.js` — `RosterStatsRenderer.renderRosterStats(players)`, `renderRosterStatsTable(players)`, `sortRosterStats(statKey)`; uses `#roster-stats-body` and `#roster-tab .stats-table` with `.sortable`/`data-stat`.
- **FCC:** Removed local `renderRosterStats`, `renderRosterStatsTable`, `sortRosterStats`; `renderTeam()` calls `RosterStatsRenderer.renderRosterStats(data.players || [])`.
- **TCC:** Removed local roster-stats block; `renderRoster()` calls `RosterStatsRenderer.renderRosterStats(data.players || [])`.
- **Script:** `rosterStatsRenderer.js` included in both HTML files.

**Impact:** One code path for roster stats table and sorting; FCC and TCC behave the same.

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

