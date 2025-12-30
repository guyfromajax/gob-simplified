# Tournament Mode Migration Plan

> **Date:** February 2025  
> **Purpose:** Comprehensive work plan to migrate Tournament Mode to use Franchise Mode structure and data/settings persistence system  
> **Status:** Planning Phase

---

## Overview

Migrate Tournament Mode to align with Franchise Mode's SS&S (Simple, Stable, Scalable) architecture, ensuring consistent data persistence, navigation patterns, and API structure across both modes.

---

## Key Differences to Address

### Current State (Tournament Mode)
- Player storage: `player_stats.{player_id}` (inconsistent with Franchise)
- Team storage: `teams.{team_id}` (consistent, but different key name from Franchise)
- Settings persistence: May use localStorage in some places (needs verification)
- Navigation: Uses `user_team_object_id` but may not be consistently authoritative
- Training reports: `training_reports.{round}` (correct for tournament)
- Stats rollup: Uses `rollup_game_to_tournament()` (may need alignment)

### Target State (Aligned with Franchise)
- Player storage: `players.{player_id}` (consistent with Franchise)
- Team storage: `teams.{team_id}` (keep different key name - intentional)
- Settings persistence: Database-only (no localStorage for persistent data)
- Navigation: `user_team_object_id` as authoritative source of truth
- Training reports: `training_reports.{round}` (keep - correct for tournament)
- Stats rollup: Same patterns as Franchise (single source of truth)

---

## Migration Tasks

### Phase 1: Data Structure Alignment

#### Task 1.1: Player Object Storage Migration
**Priority:** Critical  
**Status:** Pending

**Current State:**
- Tournament uses `player_stats.{player_id}` in some places
- Franchise uses `players.{player_id}` consistently

**Changes Required:**
1. **Backend:**
   - Update `TournamentManager.create_tournament()` to use `players` instead of `player_stats`
   - Update all tournament routes that read/write player data:
     - `GET /api/tournament/state` - Change `player_stats` to `players`
     - `GET /api/tournament/roster` - Change `player_stats` to `players`
     - `POST /api/tournament/training` - Change `player_stats` to `players`
     - `GET /api/training-report` - Change `player_stats` to `players`
     - `GET /api/tournament/team-stats` - Already uses `players` ✅
   - Update `rollup_game_to_tournament()` to write to `players.{pid}` instead of `player_stats.{pid}`
   - Update training execution to write to `players.{pid}.attributes` instead of `player_stats.{pid}.attributes`

2. **Frontend:**
   - Update `tournament.js` to read from `tournament.players` instead of `tournament.player_stats`
   - Update any other frontend files that reference `player_stats` for tournament mode

3. **Database Migration:**
   - Create migration script to rename `player_stats` → `players` in existing tournament documents
   - Test migration on sample tournament documents

**Files to Modify:**
- `BackEnd/tournament/tournament_manager.py` - `create_tournament()` method
- `BackEnd/api/tournament_routes.py` - All endpoints that access player data
- `BackEnd/utils/stat_updater.py` - `rollup_game_to_tournament()` function
- `BackEnd/models/training_execution_v2.py` - Tournament training logic
- `FrontEnd/static/tournament.js` - Player data access
- `scripts/migrate_tournament_player_stats_to_players.py` (new migration script)

**Validation:**
- All tournament documents use `players` key
- All API endpoints return/accept `players` structure
- Training system writes to `players.{pid}.attributes`
- Stats rollup writes to `players.{pid}.season`

---

#### Task 1.2: Team Object Initialization Alignment
**Priority:** Critical  
**Status:** Pending

**Current State:**
- Tournament initializes all 8 teams upfront (✅ already aligned)
- But may not use same initialization pattern as Franchise

**Changes Required:**
1. **Backend:**
   - Ensure `TournamentManager.create_tournament()` uses same initialization pattern as `FranchiseManager.initialize_season()`
   - Use `ensure_team_objects_exist()` pattern for lazy initialization if needed
   - Ensure all team objects include:
     - Team attributes (via `TeamManager.init_team_attributes(mode="tournament")`)
     - `strategy_settings` (defaults: all = 2)
     - `plays` (via `populate_team_plays(mode="tournament")`)
     - `scouting_data` (via `populate_scouting_data(mode="tournament")`)
     - `playbook_settings` (defaults: first play = 100% per section)

2. **Verification:**
   - Compare team object structure between Tournament and Franchise
   - Ensure all required fields are present

**Files to Modify:**
- `BackEnd/tournament/tournament_manager.py` - `create_tournament()` method
- `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (verify tournament support)

**Validation:**
- All 8 teams initialized with complete team objects
- Team objects match Franchise structure (except storage key name)

---

#### Task 1.3: Player Metadata Structure Alignment
**Priority:** Important  
**Status:** Pending

**Current State:**
- Tournament may use `meta` wrapper (needs verification)
- Franchise uses `meta` wrapper consistently

**Changes Required:**
1. **Backend:**
   - Ensure `TournamentManager.create_tournament()` wraps player metadata in `meta` object:
     ```javascript
     {
       "meta": {
         "first_name": "...",
         "last_name": "...",
         "team": "...",
         "team_id": "..."
       },
       "attributes": {...},
       "position_ratings": {...},
       "season": {...}
     }
     ```
   - Update any code that reads player metadata to use `meta` wrapper

2. **Frontend:**
   - Update `tournament.js` to read from `player.meta` instead of direct fields
   - Ensure backward compatibility during migration

**Files to Modify:**
- `BackEnd/tournament/tournament_manager.py` - `create_tournament()` method
- `BackEnd/api/tournament_routes.py` - Player data access
- `FrontEnd/static/tournament.js` - Player metadata access

**Validation:**
- All player objects use `meta` wrapper
- Frontend correctly reads from `meta` structure

---

#### Task 1.4: Position Ratings Addition
**Priority:** Important  
**Status:** Pending

**Current State:**
- Tournament may not include `position_ratings` in player objects
- Franchise includes `position_ratings` (needed for training)

**Changes Required:**
1. **Backend:**
   - Ensure `TournamentManager.create_tournament()` includes `position_ratings` in player objects
   - Load `position_ratings` from universal players collection
   - Include in player object structure:
     ```javascript
     {
       "position_ratings": {
         "PG": 70,
         "SG": 85,
         "SF": 92,
         "PF": 72,
         "C": 55
       }
     }
     ```

2. **Training System:**
   - Verify training system can read `position_ratings` from tournament players
   - Ensure training updates `position_ratings` if needed

**Files to Modify:**
- `BackEnd/tournament/tournament_manager.py` - `create_tournament()` method
- `BackEnd/models/training_execution_v2.py` - Verify tournament training reads position_ratings

**Validation:**
- All tournament player objects include `position_ratings`
- Training system can access position_ratings for tournament mode

---

### Phase 2: Settings Persistence Migration

#### Task 2.1: Game Plan Settings Persistence
**Priority:** Critical  
**Status:** Pending

**Current State:**
- Tournament may use localStorage or inconsistent persistence
- Franchise uses database-only via `/api/gameplan` endpoints

**Changes Required:**
1. **Backend:**
   - Verify `/api/gameplan` endpoints work correctly for Tournament mode
   - Ensure `get_gameplan()` and `update_gameplan()` use `user_team_object_id` as authoritative source
   - Verify settings are stored in `tournaments.{tournament_id}.teams.{team_id}.strategy_settings`

2. **Frontend:**
   - Remove any localStorage usage for Game Plan settings in Tournament mode
   - Ensure `game-plan.js` loads from database for Tournament mode
   - Verify settings persist across navigation

**Files to Review/Modify:**
- `BackEnd/api/gameplan_routes.py` - Verify tournament mode support
- `FrontEnd/static/game-plan.js` - Remove localStorage, ensure database-only
- `FrontEnd/static/tournament.js` - Verify no localStorage for settings

**Validation:**
- Game Plan settings load from database
- Settings persist across all navigation
- No localStorage usage for Game Plan settings

---

#### Task 2.2: Playbooks Settings Persistence
**Priority:** Critical  
**Status:** Pending

**Current State:**
- Tournament may use localStorage or inconsistent persistence
- Franchise uses database-only via `/api/playbooks` endpoints

**Changes Required:**
1. **Backend:**
   - Verify `/api/playbooks` endpoints work correctly for Tournament mode
   - Ensure `get_playbooks()` and `save_playbooks()` use `user_team_object_id` as authoritative source
   - Verify settings are stored in `tournaments.{tournament_id}.teams.{team_id}.playbook_settings`

2. **Frontend:**
   - Remove any localStorage usage for Playbooks settings in Tournament mode (except UI state)
   - Ensure `playbooks.js` loads from database for Tournament mode
   - Keep localStorage only for UI preferences (position filters, toggle states)
   - Verify settings persist across navigation

**Files to Review/Modify:**
- `BackEnd/api/gameplan_routes.py` - Verify tournament mode support for playbooks
- `FrontEnd/static/playbooks.js` - Remove localStorage for persistent data, keep UI state only
- `FrontEnd/static/tournament.js` - Verify no localStorage for settings

**Validation:**
- Playbooks settings load from database
- Settings persist across all navigation
- Only UI preferences use localStorage (position filters, toggles)

---

### Phase 3: Navigation & Team ID Resolution

#### Task 3.1: Team ID Resolution Pattern
**Priority:** Critical  
**Status:** Pending

**Current State:**
- Tournament may not consistently use `user_team_object_id` as authoritative source
- Franchise uses `get_user_team_from_franchise()` pattern

**Changes Required:**
1. **Backend:**
   - Create `get_user_team_from_tournament()` function (mirror of `get_user_team_from_franchise()`)
   - Update all tournament endpoints to use `user_team_object_id` from tournament document as authoritative source
   - Ignore URL `team_id` parameter if it doesn't match tournament document
   - Endpoints to update:
     - `GET /api/tournament/state`
     - `GET /api/gameplan` (tournament mode)
     - `PUT /api/gameplan` (tournament mode)
     - `GET /api/playbooks` (tournament mode)
     - `POST /api/playbooks` (tournament mode)
     - `POST /api/tournament/training`
     - `GET /api/training-report` (tournament mode)

2. **Frontend:**
   - Update tournament command center to load authoritative `team_id` from API
   - Use API-provided `team_id` for all navigation and API calls

**Files to Modify:**
- `BackEnd/api/tournament_routes.py` - Add `get_user_team_from_tournament()` function
- `BackEnd/api/tournament_routes.py` - Update all endpoints to use authoritative team_id
- `BackEnd/api/gameplan_routes.py` - Verify tournament mode uses authoritative team_id
- `FrontEnd/static/tournament.js` - Use API-provided team_id

**Validation:**
- All tournament endpoints use `user_team_object_id` as authoritative source
- URL `team_id` parameter is ignored if it doesn't match tournament document
- Frontend uses API-provided team_id consistently

---

#### Task 3.2: Navigation Anchor Set Consistency
**Priority:** Important  
**Status:** Pending

**Current State:**
- Tournament uses `mode`, `tournament_id`, `team_id` (ObjectId)
- Franchise uses `mode`, `franchise_id`, `team_id` (ObjectId)
- Should be consistent pattern

**Changes Required:**
1. **Documentation:**
   - Verify navigation anchor set is documented consistently
   - Ensure all three parameters are required for seamless navigation

2. **Frontend:**
   - Verify all tournament navigation preserves anchor set
   - Ensure `team_id` is always ObjectId format (never team name)

3. **Backend:**
   - Verify all tournament endpoints validate navigation anchor set
   - Ensure consistent error handling for missing parameters

**Files to Review:**
- `docs/_Master_Documentation.md` - Verify Tournament Mode navigation documentation
- `FrontEnd/static/tournament.js` - Verify navigation anchor preservation
- `BackEnd/api/tournament_routes.py` - Verify parameter validation

**Validation:**
- Navigation anchor set preserved across all tournament screens
- Consistent error handling for missing parameters

---

### Phase 4: API Endpoint Alignment

#### Task 4.1: Command Center Data Endpoint
**Priority:** Important  
**Status:** Pending

**Current State:**
- Tournament uses `GET /api/tournament/state`
- Franchise uses `GET /franchise/command-center/data`
- Should have consistent structure

**Changes Required:**
1. **Backend:**
   - Review `GET /api/tournament/state` endpoint structure
   - Align response format with Franchise command center data
   - Ensure includes:
     - `team_id` (ObjectId, authoritative)
     - `training_completed`
     - `session_type`
     - Tournament-specific data (bracket, current_round, etc.)

2. **Frontend:**
   - Verify tournament command center uses consistent data structure
   - Ensure backward compatibility during migration

**Files to Review/Modify:**
- `BackEnd/api/tournament_routes.py` - `GET /api/tournament/state` endpoint
- `FrontEnd/static/tournament.js` - Command center data loading

**Validation:**
- Command center data structure matches Franchise pattern
- All required fields present in response

---

#### Task 4.2: Training Endpoint Alignment
**Priority:** Important  
**Status:** Pending

**Current State:**
- Tournament uses `POST /api/tournament/training`
- Franchise uses `POST /franchise/training`
- Should use same training execution logic

**Changes Required:**
1. **Backend:**
   - Verify both endpoints use same `training_execution_v2.py` logic
   - Ensure tournament training writes to `players.{pid}` (after Task 1.1)
   - Verify training reports stored in `teams.{team_id}.training_reports.{round}`

2. **Frontend:**
   - Verify training UI works consistently for both modes
   - Ensure training report navigation works correctly

**Files to Review:**
- `BackEnd/api/tournament_routes.py` - `POST /api/tournament/training` endpoint
- `BackEnd/api/franchise_routes.py` - `POST /franchise/training` endpoint
- `BackEnd/models/training_execution_v2.py` - Verify both modes use same logic

**Validation:**
- Training execution logic is identical for both modes
- Training reports stored correctly in tournament document

---

#### Task 4.3: Training Report Endpoint Alignment
**Priority:** Important  
**Status:** Pending

**Current State:**
- Both modes use `GET /api/training-report`
- Should return consistent structure

**Changes Required:**
1. **Backend:**
   - Verify `GET /api/training-report` handles Tournament mode correctly
   - Ensure uses `user_team_object_id` as authoritative source
   - Verify reads from `teams.{team_id}.training_reports.{round}`

2. **Frontend:**
   - Verify training report display works consistently
   - Ensure navigation from training report works correctly

**Files to Review:**
- `BackEnd/api/franchise_routes.py` - `GET /api/training-report` endpoint
- `FrontEnd/static/training-report.js` - Verify tournament mode support

**Validation:**
- Training report endpoint works correctly for Tournament mode
- Report data structure is consistent

---

### Phase 5: Stats Rollup Alignment

#### Task 5.1: Stats Rollup Pattern Alignment
**Priority:** Critical  
**Status:** Pending

**Current State:**
- Tournament uses `rollup_game_to_tournament()`
- Franchise uses `rollup_game_to_franchise()`
- Should use same patterns and write to `players.{pid}`

**Changes Required:**
1. **Backend:**
   - Update `rollup_game_to_tournament()` to write to `players.{pid}.season` (not `player_stats`)
   - Ensure uses same stat rollup patterns as Franchise
   - Verify `applied_games` array prevents double-counting
   - Ensure box score structure matches Franchise pattern

2. **Verification:**
   - Compare stat rollup logic between Tournament and Franchise
   - Ensure consistent stat field names and structures

**Files to Modify:**
- `BackEnd/utils/stat_updater.py` - `rollup_game_to_tournament()` function
- Verify stat field names match between modes

**Validation:**
- Stats rollup writes to `players.{pid}.season`
- Stat rollup patterns match Franchise
- No double-counting via `applied_games` array

---

### Phase 6: Frontend Alignment

#### Task 6.1: Tournament Command Center Structure
**Priority:** Important  
**Status:** Pending

**Current State:**
- Tournament command center may have different structure than Franchise
- Should align UI patterns where possible

**Changes Required:**
1. **Frontend:**
   - Review `tournament.js` structure
   - Align button states, tab structure, and data loading patterns with Franchise
   - Ensure consistent navigation patterns

2. **UI Components:**
   - Verify tabs, buttons, and data displays are consistent
   - Ensure training/play button logic matches Franchise pattern

**Files to Review:**
- `FrontEnd/static/tournament.js` - Command center structure
- `FrontEnd/static/tournament.html` - HTML structure
- Compare with `FrontEnd/static/franchise-command-center.js`

**Validation:**
- Command center structure is consistent between modes
- Navigation patterns match

---

#### Task 6.2: Settings Loading/Saving Patterns
**Priority:** Important  
**Status:** Pending

**Current State:**
- Tournament may use different loading/saving patterns
- Should match Franchise database-only pattern

**Changes Required:**
1. **Frontend:**
   - Verify `game-plan.js` loads from database for Tournament mode
   - Verify `playbooks.js` loads from database for Tournament mode
   - Remove any localStorage usage for persistent data
   - Keep localStorage only for UI preferences

2. **Navigation:**
   - Ensure settings persist across all navigation transitions
   - Verify settings load correctly on page refresh

**Files to Review:**
- `FrontEnd/static/game-plan.js` - Verify tournament mode support
- `FrontEnd/static/playbooks.js` - Verify tournament mode support
- `FrontEnd/static/tournament.js` - Verify no localStorage for settings

**Validation:**
- Settings load from database for Tournament mode
- Settings persist across navigation
- No localStorage for persistent data

---

### Phase 7: Documentation Updates

#### Task 7.1: Update Master Documentation
**Priority:** Important  
**Status:** Pending

**Changes Required:**
1. **Documentation:**
   - Update `docs/_Master_Documentation.md` Tournament Mode section to reflect migrated structure
   - Document `players` key (not `player_stats`)
   - Document authoritative `user_team_object_id` pattern
   - Document database-only settings persistence
   - Update API endpoint documentation
   - Update navigation patterns documentation

2. **Comparison Doc:**
   - Update `docs/FRANCHISE_VS_TOURNAMENT_DATA_COMPARISON.md` to reflect completed migration
   - Mark aligned items as complete

**Files to Modify:**
- `docs/_Master_Documentation.md` - Tournament Mode section
- `docs/FRANCHISE_VS_TOURNAMENT_DATA_COMPARISON.md` - Update comparison

**Validation:**
- Documentation accurately reflects migrated structure
- All key differences documented

---

### Phase 8: Testing & Validation

#### Task 8.1: Create Migration Test Plan
**Priority:** Critical  
**Status:** Pending

**Test Scenarios:**
1. **Tournament Creation:**
   - Create new tournament
   - Verify `players` key (not `player_stats`)
   - Verify all 8 teams initialized with complete team objects
   - Verify player objects include `meta` wrapper and `position_ratings`

2. **Settings Persistence:**
   - Configure Game Plan settings
   - Configure Playbooks settings
   - Navigate between screens
   - Verify settings persist
   - Verify no localStorage usage for persistent data

3. **Training:**
   - Run training session
   - Verify writes to `players.{pid}.attributes`
   - Verify training report displays correctly
   - Verify training reports stored in `teams.{team_id}.training_reports.{round}`

4. **Stats Rollup:**
   - Complete a tournament game
   - Verify stats rollup writes to `players.{pid}.season`
   - Verify no double-counting
   - Verify stat field names match Franchise

5. **Navigation:**
   - Navigate between all tournament screens
   - Verify navigation anchor set preserved
   - Verify `team_id` is always ObjectId format
   - Verify authoritative `user_team_object_id` pattern works

6. **Backward Compatibility:**
   - Test with existing tournament documents (if any)
   - Verify migration script works correctly
   - Verify old `player_stats` structure is handled gracefully

---

## Additional Documentation to Review

The following documentation files may contain relevant information:

1. **`docs/franchise_mode_architecture.md`** - Complete franchise mode data structure (already reviewed)
2. **`docs/COMMON_DATA_SET.md`** - Common data structure across all modes (already reviewed)
3. **`docs/FRANCHISE_VS_TOURNAMENT_DATA_COMPARISON.md`** - Side-by-side comparison (already reviewed)
4. **`docs/master_game_doc.md`** - Game system documentation (already reviewed)
5. **`docs/NAVIGATION_DATA_REQUIREMENTS.md`** - Navigation patterns (may have additional details)
6. **`docs/GAMEPLAY_DATA_PERSISTENCE_ANALYSIS.md`** - Gameplay persistence patterns (may have additional details)

**Recommendation:** Review `NAVIGATION_DATA_REQUIREMENTS.md` and `GAMEPLAY_DATA_PERSISTENCE_ANALYSIS.md` to ensure no navigation or persistence patterns are missed.

---

## Migration Priority Order

### Critical Path (Must Complete First):
1. Task 1.1: Player Object Storage Migration (`player_stats` → `players`)
2. Task 1.2: Team Object Initialization Alignment
3. Task 2.1: Game Plan Settings Persistence
4. Task 2.2: Playbooks Settings Persistence
5. Task 3.1: Team ID Resolution Pattern
6. Task 5.1: Stats Rollup Pattern Alignment

### Important (Complete After Critical):
7. Task 1.3: Player Metadata Structure Alignment
8. Task 1.4: Position Ratings Addition
9. Task 3.2: Navigation Anchor Set Consistency
10. Task 4.1: Command Center Data Endpoint
11. Task 4.2: Training Endpoint Alignment
12. Task 4.3: Training Report Endpoint Alignment
13. Task 6.1: Tournament Command Center Structure
14. Task 6.2: Settings Loading/Saving Patterns

### Documentation & Testing:
15. Task 7.1: Update Master Documentation
16. Task 8.1: Create Migration Test Plan

---

## Estimated Effort

- **Phase 1 (Data Structure):** ~8-10 hours
- **Phase 2 (Settings Persistence):** ~4-6 hours
- **Phase 3 (Navigation):** ~4-6 hours
- **Phase 4 (API Alignment):** ~4-6 hours
- **Phase 5 (Stats Rollup):** ~2-4 hours
- **Phase 6 (Frontend):** ~4-6 hours
- **Phase 7 (Documentation):** ~2-3 hours
- **Phase 8 (Testing):** ~4-6 hours

**Total Estimated Effort:** ~32-47 hours

---

## Risk Assessment

### High Risk:
- **Database Migration:** Renaming `player_stats` → `players` in existing tournaments
  - **Mitigation:** Create comprehensive migration script, test on sample data first

### Medium Risk:
- **Breaking Changes:** Existing tournament documents may have different structure
  - **Mitigation:** Add backward compatibility checks, graceful degradation

### Low Risk:
- **Settings Persistence:** Removing localStorage may break existing user sessions
  - **Mitigation:** Ensure database is always source of truth, localStorage is fallback only

---

## Success Criteria

✅ All tournament player data uses `players` key (not `player_stats`)  
✅ All team objects initialized with complete structure  
✅ Settings persist via database only (no localStorage for persistent data)  
✅ `user_team_object_id` is authoritative source for all tournament operations  
✅ Stats rollup writes to `players.{pid}.season`  
✅ Navigation patterns match Franchise mode  
✅ API endpoints use consistent patterns  
✅ Documentation updated to reflect migrated structure  
✅ All tests pass

---

## Notes

- **Team Storage Key:** Keep `teams.{team_id}` for Tournament (different from `franchise_teams.{team_id}`) - this is intentional
- **Player Storage Key:** Must change to `players.{player_id}` (align with Franchise)
- **Training Reports:** Keep `training_reports.{round}` for Tournament (correct for tournament structure)
- **Bracket Structure:** Keep tournament-specific bracket structure (different from Franchise schedule)

---

## Next Steps

1. Review this plan with team
2. Prioritize tasks based on dependencies
3. Begin with Phase 1, Task 1.1 (Player Object Storage Migration)
4. Create migration script for existing tournament documents
5. Test migration on sample data
6. Execute migration tasks in priority order
7. Update documentation as tasks complete

