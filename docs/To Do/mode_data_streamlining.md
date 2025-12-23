# Mode Data Streamlining - To Do List

**Date:** January 2025  
**Purpose:** Align Franchise and Tournament mode data structures for consistency and maintainability

**Reference:** `docs/FRANCHISE_VS_TOURNAMENT_DATA_COMPARISON.md` for detailed comparison

---

## Phase 1: Critical Alignments (Must Do)

### 1.1 Tournament Mode: Initialize All Teams Upfront
**Status:** ⏳ Pending  
**Priority:** 🔴 Critical

**Current State:**
- Tournament mode uses lazy initialization (only creates team objects when first accessed)
- Franchise mode initializes all 8 teams upfront

**Changes Required:**
- [ ] Update `TournamentManager.create_tournament()` to initialize team objects for all 8 teams
- [ ] Use same pattern as `FranchiseManager.initialize_season()` (loop through all teams)
- [ ] Update `ensure_team_objects_exist()` to handle tournament mode upfront initialization
- [ ] Test that all teams are initialized when tournament is created

**Files to Modify:**
- `BackEnd/tournament/tournament_manager.py` - `create_tournament()` method
- `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` function

**Reference:** `docs/FRANCHISE_VS_TOURNAMENT_DATA_COMPARISON.md` Section: Team Objects Initialization

---

### 1.2 Franchise Mode: Add `user_team_id` and `user_team_object_id` to Document
**Status:** ⏳ Pending  
**Priority:** 🔴 Critical

**Current State:**
- Franchise mode uses separate `franchise_state_collection` to store user team
- Tournament mode stores `user_team_id` and `user_team_object_id` directly in tournament document

**Changes Required:**
- [ ] Update `FranchiseManager.initialize_season()` to accept `user_team_id` and `user_team_object_id` parameters
- [ ] Store both fields in franchise document during initialization
- [ ] Update `select_team()` endpoint to resolve team name to ObjectId and pass to `initialize_season()`
- [ ] Update all 8 endpoints that use `franchise_state_collection` to read from franchise document instead
- [ ] Add backward compatibility (check franchise doc first, fallback to state collection for old franchises)
- [ ] Update `command_center_data()` endpoint (line 370)
- [ ] Update `season_schedule()` endpoint (line 472)
- [ ] Update `user_team_player_stats_endpoint()` endpoint (line 738)
- [ ] Update `get_franchise_team_data()` endpoint (line 865)
- [ ] Update `get_training_report()` endpoint (line 937)
- [ ] Update `run_franchise_training()` endpoint (line 1046)
- [ ] Find and update any other endpoints using `franchise_state_collection`

**Files to Modify:**
- `BackEnd/models/franchise_manager.py` - `initialize_season()` method
- `BackEnd/api/franchise_routes.py` - Multiple endpoints (8+ locations)
- `BackEnd/api/franchise_routes.py` - `select_team()` endpoint

**Reference:** `docs/FRANCHISE_VS_TOURNAMENT_DATA_COMPARISON.md` Section: Document-Level Fields

---

### 1.3 Tournament Mode: Add `position_ratings` to Player Objects
**Status:** ⏳ Pending  
**Priority:** 🔴 Critical

**Current State:**
- Franchise mode stores `position_ratings` in player objects
- Tournament mode does not store `position_ratings`
- Training system needs `position_ratings` to work correctly

**Changes Required:**
- [ ] Update `TournamentManager.create_tournament()` to include `position_ratings` when creating player_stats
- [ ] Load `position_ratings` from universal players collection
- [ ] Store in `tournament.player_stats.{player_id}.position_ratings`
- [ ] Update training system to save `position_ratings` updates to tournament document
- [ ] Test that position ratings are available for training

**Files to Modify:**
- `BackEnd/tournament/tournament_manager.py` - `create_tournament()` method
- `BackEnd/api/tournament_routes.py` - `run_tournament_training()` method (if needed)

**Reference:** `docs/FRANCHISE_VS_TOURNAMENT_DATA_COMPARISON.md` Section: Player Objects Structure

---

### 1.4 Tournament Mode: Use `meta` Wrapper for Player Metadata
**Status:** ⏳ Pending  
**Priority:** 🔴 Critical

**Current State:**
- Franchise mode: `players.{player_id}.meta: {first_name, last_name, team, team_id}`
- Tournament mode: `player_stats.{player_id}: {first_name, last_name, team}` (at root level)

**Changes Required:**
- [ ] Update `TournamentManager.create_tournament()` to wrap player metadata in `meta` object
- [ ] Structure: `player_stats.{player_id}.meta: {first_name, last_name, team, team_id}`
- [ ] Add `team_id` to metadata (currently missing in tournament mode)
- [ ] Update all code that reads player metadata to use `meta` wrapper
- [ ] Update training system to use `meta` structure
- [ ] Update frontend code that reads player metadata (if any)

**Files to Modify:**
- `BackEnd/tournament/tournament_manager.py` - `create_tournament()` method
- `BackEnd/api/tournament_routes.py` - Any code reading player metadata
- `BackEnd/api/franchise_routes.py` - `get_training_report()` (tournament mode section)
- Frontend files that read tournament player data (if any)

**Reference:** `docs/FRANCHISE_VS_TOURNAMENT_DATA_COMPARISON.md` Section: Player Objects Structure

---

## Phase 2: Important Alignments (Should Do)

### 2.1 Franchise Mode: Add Missing Document-Level Fields
**Status:** ⏳ Pending  
**Priority:** 🟡 Important

**Current State:**
- Tournament mode has: `created_at`, `stats`/`leaderboards`, `completed`
- Franchise mode missing: `created_at`, `stats`/`leaderboards`, `current_season`

**Note:** Franchise mode does NOT need `completed` because franchises are ongoing across multiple seasons. Tournament mode uses `completed` because tournaments end after the final round.

**Changes Required:**
- [ ] Add `created_at` field to franchise document during initialization
- [ ] Add `stats`/`leaderboards` structure to franchise document (same as tournament)
- [ ] Add `current_season` number field to franchise document (starts at 1, increments each season)
- [ ] Update `FranchiseManager.initialize_season()` to include these fields
- [ ] Initialize `current_season = 1` when creating a new franchise

**Files to Modify:**
- `BackEnd/models/franchise_manager.py` - `initialize_season()` method
- `BackEnd/api/franchise_routes.py` - Any completion checking logic

**Reference:** `docs/FRANCHISE_VS_TOURNAMENT_DATA_COMPARISON.md` Section: Document-Level Fields

---

### 2.2 Standardize Training Status Field Names
**Status:** ⏳ Pending  
**Priority:** 🟡 Important

**Current State:**
- Franchise: `{current_week, training_completed, session_type}`
- Tournament: `{training_completed, round, last_training_date}`

**Changes Required:**
- [ ] Align field names:
  - Use `current_week`/`current_round` consistently (keep mode-specific names)
  - Use `session_type` in both modes
  - Use `last_training_date` in both modes
- [ ] Update Tournament mode to include `session_type` field
- [ ] Update Franchise mode to include `last_training_date` field
- [ ] Update all code that reads/writes training status

**Files to Modify:**
- `BackEnd/api/tournament_routes.py` - `run_tournament_training()` method
- `BackEnd/api/franchise_routes.py` - `run_franchise_training()` method
- `BackEnd/models/franchise_manager.py` - `initialize_season()` method

**Reference:** `docs/FRANCHISE_VS_TOURNAMENT_DATA_COMPARISON.md` Section: Document-Level Fields

---

### 2.3 Standardize Latest Training Field Names
**Status:** ⏳ Pending  
**Priority:** 🟡 Important

**Current State:**
- Franchise: `{player_logs, team_log, session_type, week}`
- Tournament: `{player_changes, team_changes, round, ...}`

**Changes Required:**
- [ ] Align field names:
  - Use `player_logs` (not `player_changes`) in both modes
  - Use `team_log` (not `team_changes`) in both modes
  - Use `week`/`round` consistently (keep mode-specific names)
  - Use `session_type` in both modes
- [ ] Update Tournament mode to use `player_logs` and `team_log`
- [ ] Update Franchise mode to ensure consistency
- [ ] Update all code that reads/writes latest training data

**Files to Modify:**
- `BackEnd/api/tournament_routes.py` - `run_tournament_training()` method
- `BackEnd/api/franchise_routes.py` - `run_franchise_training()` method
- `BackEnd/api/franchise_routes.py` - `get_training_report()` method

**Reference:** `docs/FRANCHISE_VS_TOURNAMENT_DATA_COMPARISON.md` Section: Document-Level Fields

---

### 2.4 Training Reports Storage - Already Consistent ✅
**Status:** ✅ Already Implemented  
**Priority:** 🟡 Important

**Current State:**
- Tournament mode stores training reports in `teams.{user_team_id}.training_reports.{round}`
- Franchise mode stores training reports in `franchise_teams.{user_team_id}.training_reports.{week}`
- Both modes only store training reports for the user team (not computer teams)
- Both modes also store in `latest_training` at document level for quick access

**Consistency Status:**
- ✅ Both only store for user team
- ✅ Both use same pattern: `{teams_path}.{user_team_id}.training_reports.{time_period}`
- ✅ Different path names (`teams` vs `franchise_teams`) are intentional and acceptable

**No Changes Required:**
- Training reports storage is already consistent across modes
- Both modes follow the same pattern (user team only, per-time-period storage)

**Reference:** `docs/FRANCHISE_VS_TOURNAMENT_DATA_COMPARISON.md` Section: Team Objects Structure

---

## Phase 3: Nice to Have (Optional)

### 3.1 Add `created_at` to Franchise Document
**Status:** ⏳ Pending  
**Priority:** 🟢 Nice to Have

**Note:** This is also covered in Phase 2.1, but listed separately for tracking.

---

### 3.2 Add `stats`/`leaderboards` to Franchise Document
**Status:** ⏳ Pending  
**Priority:** 🟢 Nice to Have

**Note:** This is also covered in Phase 2.1, but listed separately for tracking.

---

### 3.3 Add `current_season` Number to Franchise Document
**Status:** ⏳ Pending  
**Priority:** 🟢 Nice to Have

**Note:** This is also covered in Phase 2.1, but listed separately for tracking. Franchise mode uses `current_season` (number) instead of `completed` (boolean) because franchises are ongoing across multiple seasons.

---

## Implementation Notes

### Backward Compatibility Strategy

For all changes, maintain backward compatibility:
1. **Check new structure first** (franchise/tournament document)
2. **Fallback to old structure** (state collection, old field names, etc.)
3. **Log warnings** when fallback is used (for migration tracking)
4. **Update old data** when accessed (lazy migration)

### Testing Checklist

After each phase:
- [ ] Test new franchise creation
- [ ] Test new tournament creation
- [ ] Test loading existing franchises (backward compatibility)
- [ ] Test loading existing tournaments (backward compatibility)
- [ ] Test all navigation flows (Command Center → Game Plan → Playbooks → Training)
- [ ] Test training system works with new structures
- [ ] Test training reports load correctly
- [ ] Verify all teams initialized in tournament mode
- [ ] Verify user team identification works in franchise mode

### Documentation Updates Required

After implementation:
- [ ] Update `docs/franchise_mode_architecture.md` with new structure
- [ ] Update `docs/master_game_doc.md` Data Persistence section
- [ ] Update `docs/FRANCHISE_VS_TOURNAMENT_DATA_COMPARISON.md` to reflect completed alignments
- [ ] Update `docs/COMMON_DATA_SET.md` if structure changes affect common data

---

## Summary

**Total Tasks:** 11 items across 3 phases

**Phase 1 (Critical):** 4 items
- Tournament: Initialize all teams upfront
- Franchise: Add user_team_id and user_team_object_id
- Tournament: Add position_ratings
- Tournament: Use meta wrapper for player metadata

**Phase 2 (Important):** 4 items
- Franchise: Add missing document-level fields (`created_at`, `stats`/`leaderboards`, `current_season`)
- Standardize training status field names
- Standardize latest training field names
- Franchise: Add per-week training reports storage

**Phase 3 (Nice to Have):** 3 items (duplicates of Phase 2.1)

**Estimated Impact:**
- ~15-20 files to modify
- ~8-10 endpoints to update
- Significant improvement in consistency and maintainability
- Better support for multiple franchises per user
- Elimination of legacy state collection pattern

