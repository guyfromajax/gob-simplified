# Tournament & Franchise Mode Unification Plan

**Date:** January 2025  
**Status:** 📋 Planning (Phase 1 ✅, Phase 2 ✅, Phase 2.5 Frontend bracket ✅, Phase 3.1 ✅, Phase 3.2 ✅, Phase 4.1 ✅, Phase 4.2 ✅, Phase 4.4 ✅, Phase 5.2 ✅, Phase 5.3 ✅)  
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

### 3.2 Missing Endpoint Equivalents (Analysis) ✅

**Status:** Done (January 2025)

**Findings:**

- **Scouting report:** Tournament **already has** an equivalent. `BackEnd/api/tournament_routes.py` exposes `GET /tournament/scouting-report` (tournament_id, team_id/team_name). FCC calls `/franchise/scouting-report`; TCC calls `/tournament/scouting-report`. Both use shared `BackEnd/utils/scouting_utils.py::extract_plays_from_game_document()`. **No action needed.**

- **Team-player-stats:** Franchise exposes `/franchise/team-player-stats/{team_id}` and `/franchise/team-player-stats` (user team). Used only by `team-roster-view.js` in **franchise** mode to load one team’s player stats. In **tournament** mode, `team-roster-view.js` does **not** call these; it calls `/tournament/state?tournament_id=...` and merges `data.players` with the roster client-side (same pattern as TCC roster tab). So Tournament does not need `/tournament/team-player-stats` or `/tournament/team-player-stats/{team_id}` for current behavior. **No action needed.** (Optional future: add a Tournament team-player-stats endpoint to simplify team-roster-view.js to one stats URL per mode.)

- **Training endpoints:** `/franchise/latest-training`, `/franchise/training-points` — Tournament training is disabled; no Tournament equivalents needed. **No action needed.**

**Intentional differences (unchanged):**
- `/franchise/standings` vs Tournament bracket; `/franchise/schedule` vs bracket; `/franchise/recruits` (Franchise-only); `/franchise/complete-week` vs `/tournament/save-result`.

**Conclusion:** Phase 3.2 is analysis-only; no code changes required. All potential gaps are either already covered (scouting-report) or not required for current behavior (team-player-stats).

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

### 4.4 Command Center Structure ✅

**Status:** Done (January 2025)

**Completed:**
- **Shared module:** `FrontEnd/static/js/shared/commandCenterTabs.js` — `CommandCenterTabs.initCommandCenterTabs({ defaultTab, onTabShow })` handles: read tab from URL (fallback to defaultTab), set active on matching `.tab-buttons button` and `.tab-content`, add click listeners that switch active, update URL with pushState, and call `onTabShow(tabName)`. On init, calls `onTabShow(activeTab)` so the restored tab loads its data.
- **FCC:** Inline tab script removed from `franchise-command-center.html`. In `franchise-command-center.js` DOMContentLoaded, after `init()`, calls `CommandCenterTabs.initCommandCenterTabs({ defaultTab: 'standings-tab', onTabShow: (tabName) => { tournament-tab → renderTournamentBracket(); team-tab → loadTeamData() / renderTeamReport + renderPlaybookSummary(); } })`.
- **TCC:** Inline tab script removed from `tournament.html`. In `tournament.js` DOMContentLoaded, calls `CommandCenterTabs.initCommandCenterTabs({ defaultTab: 'bracket-tab', onTabShow: (tabName) => { bracket-tab → renderBracket(); roster-tab → loadRoster/renderRoster; team-tab → loadTeamData(); stats-tab → renderLeaderboards + refreshTeamStats; schedule-tab → renderSchedule(); } })`.
- **Script:** `commandCenterTabs.js` included in both HTML files before the main app script.

**Impact:** One code path for tab switch + URL; mode-specific “on tab show” logic stays in each app via callback. Initial tab from URL restores and loads data.

---

## Phase 5: Backend Code Unification

### 5.1 Team Stats Aggregation

**Status:** ✅ Already unified via `team_stats_aggregator.py`

### 5.2 Roster Endpoints ✅

**Status:** Done (January 2025)

**Completed:**
- **Shared module:** `BackEnd/utils/roster_builder.py` — `build_roster_players(team_player_ids, mode_overrides, core_players_dict, team_name)` builds the common player dict shape (`_id`, `first_name`, `last_name`, `name`, `team`, `attributes` with `anchor_*`, `position_ratings`, `height`, `weight`, `jersey`, `year`). No DB access; callers pass IDs, overrides, and core dict.
- **Franchise:** `get_franchise_roster` keeps FPD + core queries; builds `mode_overrides` from FPD (meta, attributes, position_ratings), filters to `pids_with_fpd`, calls `build_roster_players(pids_with_fpd, mode_overrides, core_players_dict, team_name)`, returns `{"players": players}`.
- **Tournament:** `get_tournament_roster` keeps tournament doc + core batch query; builds `mode_overrides` from tournament.players (merged attributes, position_ratings, name from meta/root/core), filters to `pids_with_core`, calls `build_roster_players(pids_with_core, mode_overrides, core_players_dict, team_name)`, returns `{"players": players}`.

**Impact:** Single place for roster player dict construction; both modes return the same shape; no duplicate merge/anchor logic.

### 5.3 Command Center Data Endpoints ✅

**Status:** Done (January 2025)

**Completed:**
- **Shared module:** `BackEnd/utils/command_center_data.py` — `build_command_center_base(team_name, team_id, team_attrs)` returns the common response keys: `team`, `team_id`, `team_chemistry`, `offense`, `defense`, `athleticism`, and optionally `intangibles`, `prestige`, `rank` when present in `team_attrs`. No DB access; callers pass resolved team name, team_id, and team attrs.
- **Franchise:** `command_center_data` keeps franchise_doc/FTD/state queries; builds `team_doc` (with team_chemistry from FTD); calls `build_command_center_base(team_name, team_id, team_doc)`; merges franchise-only keys (`username`, `seed`, `intangibles`, `prestige`, `rank`, `week`, `training_status`, `eos_tournament*`, `training_disabled_for_eos`, `user_eliminated`, `offer_sim_rest`); returns response.
- **Tournament:** `tournament_command_center_data` keeps tournament doc + team_doc resolution; calls `build_command_center_base(user_team_id_name, user_team_object_id, team_doc)`; merges tournament-only keys (`training_completed`, `session_type`, `current_round`, `completed`, `bracket`); returns response.

**Impact:** Single place for common command-center response keys; both modes return consistent team/chemistry/offense/defense/athleticism shape; mode-specific keys remain in routes.

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

### Final Smoke Test Checklist (Phases 4.1, 4.2, 4.4, 5.2, 5.3)

Run after unification work to confirm shared modules and endpoints behave correctly.

**Franchise Command Center (FCC)**

| Check | What to verify |
|-------|----------------|
| Load FCC | Open `franchise-command-center.html?franchise_id=<valid_id>`. Page loads; top bar shows team name, chemistry, grades (offense/defense/athleticism), week. |
| Command center data | Top bar and tabs reflect data from `/franchise/command-center/data` (team, chemistry, intangibles, prestige, rank, username, week, training status). |
| Tabs + URL | Click Standings → Roster → Team → Stats → Schedule → Tournament → Recruits → Team Traits. URL gets `?tab=...`; correct tab content shows. |
| Restore tab from URL | Reload with `?franchise_id=...&tab=team-tab`. Team tab is active and team report/playbook summary load. |
| Roster tab | Roster table and **Stats** sub-table (PTS, FGM, FG%, etc.) render. Click a stat header; rows re-sort. |
| Tournament tab (EOS) | If EOS tournament is active, Tournament tab shows bracket with team names (not IDs) and same layout as TCC. |
| Roster backend | `GET /franchise/roster?franchise_id=...&team_name=...` returns `{ players: [...] }` with attributes/position_ratings. |

**Tournament Command Center (TCC)**

| Check | What to verify |
|-------|----------------|
| Load TCC | Open `tournament.html?tournament_id=<valid_id>`. Page loads; top bar shows team, chemistry, grades. |
| Command center data | Top bar reflects `/tournament/command-center/data` (team, team_id, chemistry, offense/defense/athleticism, current_round, completed, bracket). |
| Tabs + URL | Click Bracket → Roster → Team → Stats → Schedule. URL gets `?tab=...`; correct tab content shows. |
| Restore tab from URL | Reload with `?tournament_id=...&tab=roster-tab`. Roster tab is active and roster + stats table load. |
| Bracket tab | Bracket renders with team names and scores; layout matches FCC Tournament tab. |
| Roster tab | Roster table and stats sub-table render; stat header click sorts. Player stats (season) show after games played. |
| Roster backend | `GET /tournament/roster?tournament_id=...&team_id=...` (or team_name) returns `{ players: [...] }` with merged attributes. |

**Shared / Deep links**

| Check | What to verify |
|-------|----------------|
| Team roster view (franchise) | From FCC Standings or Schedule, open another team’s roster (`team-roster-view.html?mode=franchise&franchise_id=...&team_id=...`). Roster and stats load (franchise path). |
| Team roster view (tournament) | From TCC Schedule, open another team’s roster (`team-roster-view.html?mode=tournament&tournament_id=...&team_id=...`). Roster and stats load (tournament state merge). |
| App-level roster | Game/box-score flows that use `/roster/<team>?franchise_id=...` or `?tournament_id=...` still load roster correctly. |

**Quick backend checks (optional)**

- `GET /franchise/command-center/data?franchise_id=...` → JSON with `team`, `team_id`, `team_chemistry`, `offense`, `defense`, `athleticism`, plus franchise-only keys.
- `GET /tournament/command-center/data?tournament_id=...` → JSON with same common keys plus `current_round`, `completed`, `bracket`.

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

1. ~~**Team-Player-Stats Endpoints**~~ **Answered (Phase 3.2):** No. Tournament uses `/tournament/state` + client-side merge in team-roster-view; no dedicated team-player-stats endpoint needed.
2. ~~**Scouting Report**~~ **Answered (Phase 3.2):** Tournament already has `/tournament/scouting-report`; no gap.
3. **Migration Script**: Do we need a script to migrate `franchise_teams` → `teams` in existing documents?
4. **API Versioning**: Should we version APIs to handle breaking changes more gracefully?

---

**Last Updated:** January 2025  
**Next Review:** After Phase 5.2 (Roster Endpoints Unification)

