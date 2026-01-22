# Phase 5.7: Game-Scoped Settings Bug - Settings Persisting to Master Doc

**Status:** 🔴 Bug - Settings changes during gameplay saving to master doc instead of game doc

**Date:** 2024-12-XX

**Issue:**
Settings changes made during active gameplay in franchise/tournament mode are persisting back to the FCC (master settings) instead of being scoped to the game document only.

**Expected Behavior:**
- Settings changed during active gameplay (quarter > 0) should save to game doc only
- Master settings in franchise/tournament doc should remain unchanged
- When visiting FCC after game, should load original master settings (not game-scoped changes)

**Actual Behavior:**
- Settings changed during gameplay are persisting to master doc
- When visiting FCC after game, settings reflect the end-of-game values instead of original master values

**Root Cause Analysis:**
Based on Railway logs, the conditional save logic (`[PHASE 5.7] Saving playbooks/gameplan to game doc`) is not being triggered. This suggests:

1. **Most Likely:** `game_id` is not being passed in the save request from frontend
   - The conditional logic requires: `if game_id provided AND game exists AND game is active (quarter > 0)`
   - If `game_id` is missing, logic defaults to saving to master doc
   - Need to verify frontend includes `game_id` in save requests during gameplay

2. **Possible:** Game state detection failing
   - Quarter check might be failing (game not detected as active)
   - Game document lookup might be failing

3. **Possible:** Different code path for Sim Quarter vs Play Quarter
   - User used "Sim Quarter" for Q1-Q3 and "Play Quarter" for Q4
   - Different contexts might have different `game_id` availability

**Evidence from Logs:**
- ✅ Load logic working correctly: `[PHASE 5.7] Loading playbooks from master doc` when visiting FCC
- ❌ No save logs: Missing `[PHASE 5.7] Saving playbooks/gameplan to game doc` messages
- ❌ Settings persisted: Master doc has end-of-game values instead of original values

**Investigation Needed:**
1. Check frontend code that calls `/api/playbooks` and `/api/gameplan` during gameplay
   - Does it extract `game_id` from URL?
   - Does it include `game_id` in request body?
   - Check both Sim Quarter and Play Quarter contexts

2. Check browser network tab when saving settings during gameplay
   - Verify request body includes `game_id` parameter
   - Verify `game_id` value is correct

3. Add more logging to save functions
   - Log when `game_id` is missing
   - Log when game is not detected as active
   - Log the decision path (game doc vs master doc)

**Files to Check:**
- `FrontEnd/static/playbooks.js` - Save function during gameplay
- `FrontEnd/static/game-plan.js` - Save function during gameplay
- `BackEnd/api/gameplan_routes.py` - `save_playbooks()` and `update_gameplan()` functions
- `BackEnd/api/gameplan_routes.py` - `get_save_location_for_franchise_tournament()` helper

**Fix Priority:** Medium (not blocking, but breaks expected behavior)

**Related:** Phase 5.7 implementation (Tasks 1-4 complete, Tasks 5-6 pending)

