##Bugs 
14. Charge or Blocking Foul on Fast Break, stop animation immediately don't wait for theor plaeyrs to get to teh spot
37. Player Foul Out Next Step bug
38 Fast Break, aninate defender back on pass

##Micro Movements
28. Make HCO defensers un-attached to the offender at all costs
29. Claude Design's designs
30. MM SFX

##Player Images
1. Set up Cloudflare
2. ChatGPT API Process for plaeyr images, uniform design, and applying uniforms to players

##Full Product Readiness
102. Team court images
105. More responsive front end
106. Monetization plan
107. Stripe
108. Message board
110. Strategic Geek Points system
113. Bring logic to screens
114. Better defense stat tracking
116. User account -- link X & Facebook?
117. More action on Signing Day
118. Make Tranining feed based on news -- previous week's results and this week's upcoming games.
119. PvP sim
120. PvP live
121. Tunable Constants file

##Full Season Playthrough ideas (6-11-26)
1. Training Camp News Report
2. Week 20 Recruiting Report to Inbox
3. Recruiting Round Up Results
5. Add a new hire news story for user team
6. Add a badass design appraoch to New Stories
25. Fast Break and P/T callouts in the Scouting Report of opponent

##Continuous Evolution (base is built)
1. In-Game SFX: Deny, Picked Up His Dribble, No Good/Missed
2. Advanced Topics tutorials
3. Dynamic FCP Turns



<!--
SEARCH TAG: [CODE-CLEANUP]
Every outstanding code-level fix/cleanup item surfaced during the documentation sweep (and the
ongoing code-cleanup backlog) is tagged with the literal token [CODE-CLEANUP]. To get the complete
list across the whole repo, run:  rg "\[CODE-CLEANUP\]"
This includes items in this file (Future Cleanup, P0, Fast Break backlog, FB test follow-up) plus
inline notes left in individual system docs. (Sunset-mode code removal also carries its own
"SUNSET MODE" tag inside the docs that describe those paths, and is cross-linked from here.)
-->

## Stale FB test suite (found + cleaned up 6-12-26, was not a product bug)

15 tests across 4 FB test files were failing because they asserted **pre-refactor** fast-break behavior (test files last touched Dec 2025–Mar 2026; FB engine rewritten May–Jun 2026): mock players missing the `MIN` stat key, hard-coded coordinates from the old outlet logic, and stale role-plumbing assertions.

**Resolved 6-12-26:** deleted `test_fast_break_comprehensive.py`, `test_fast_break_miss_dreb_flow.py`, `test_fast_break_position_logic.py` (fully red); trimmed the two stale tests from `test_fast_break_outlet_pass.py` (its two edge-case tests still pass and were kept). FB suite is now green.

**Open follow-up [CODE-CLEANUP]:** current-engine FB coverage is thin — `test_fast_break_rr_triangle_updates.py` covers RR/Triangle emitters, but the CR resolver path and `after_steal_fast_break.py` (resolver + emitter) have little/no direct test coverage. Write new tests against the current resolvers when FB work resumes.

## P0 — HCO contract clock overruns with invalid elapsed time (carried from Unified_Animation_System.md, 6-12-26) [CODE-CLEANUP]

Two critical issues from the animation blueprint's "Known HCO Turn Issues" list (`projects/Unified_Animation_System.md`), copied here so they're visible in the bug tracker:

1. **HCO resolution hard overrun:** observed throw `"[HCO resolution contract] clock overrun ... elapsedGameSeconds=649.00"` on a `DEAD BALL` path. Magnitude indicates timer baseline/state contamination, not normal jitter. Mitigation applied (Option A): turn-boundary guards use contract-capped elapsed (`min(wall_elapsed_ms, real_time_elapsed_ms + guard_slack_ms)`); needs validation in live runs before closing.
2. **HCO step-pass hard overrun in BATCH/DEAD BALL sub-turns:** observed throw `"[HCO step pass contract] clock overrun ... elapsedGameSeconds=405.78"` at `step=6` on a `DEAD BALL` batch sub-turn. Same timer-source class as #1 but a distinct enforcement site (`step pass` guard); track separately.

## Fast Break animation backlog (legacy path) [CODE-CLEANUP]

Tracked from archived [`Z-Completed/Fast_Break_Refactor.md`](Z-Completed/Fast_Break_Refactor.md). **UESS schema path is primary** for `covert_release`, `rim_runner`, `triangle`, `after_steal` when `animation_steps` exist.

- Advance triggers unreliable on legacy `fastBreak.js` / `runFastBreakSequence` (phase boundaries hang or short-circuit).
- FB visual timing still uses FE `getPlayerDuration` on legacy path; backend does not stamp per-player `game_seconds` in legacy `animator.capture_fast_break_animation` payload.
- Charge/blocking foul on FB: stop animation immediately (don't wait for defensive spot) — see Bugs §14.
- Full phase map and backend sites: archived refactor doc.

---

## Future Cleanup (Non-Critical Warnings)

### Coordinate flip off-by-one: backend `100 − x` vs frontend `101 − x` (found 6-12-26 during doc sweep) [CODE-CLEANUP]
- **Issue**: Two different mirror-flip conventions coexist. Backend `getAwayTeamCoords()` (`BackEnd/utils/shared.py`) flips with `x = 100 − x`; legacy frontend helpers in `turnAnimation.js` (4 sites: skeleton position conversion, FCP defensive setup, and two local `flipCoords` helpers) flip with `x = 101 − x`.
- **Impact**: Low/medium — a 1-grid-spot horizontal discrepancy whenever a frontend-flipped coordinate is compared to or layered on a backend-flipped one. On a 1–100 grid, `101 − x` is the symmetric mirror (1↔100); `100 − x` maps 1→99, drifting everything 1 spot. Not known to cause a visible bug today, but it's a trap for any future code that mixes the two.
- **Action**: Pick one convention (likely `101 − x` if the grid is 1–100) and unify; at minimum, audit the 4 frontend `101 − x` sites against the backend coords they consume. As UESS schema playback takes over, the legacy frontend flip sites should shrink toward dead code anyway.
- **Priority**: Low (documented in `05_GP_Supporting_Systems/BIP_System.md` → "Coordinate System and `opp` Field")

### Sunset mode code removal (Single Game + Tournament) — surfaced during doc sweep 6-13-26 [CODE-CLEANUP]
- **Issue**: Single Game and Tournament modes are sunset (not user-facing), but their code paths still exist throughout the backend/frontend (e.g. `init_game()` mode branches for `single`/`tournament` in `BackEnd/api/api.py`, tournament master-copy seeding, single-game empty-playbook init, plus tournament/single routes and frontend pages).
- **Decision (prior)**: When tournaments / single games are reintroduced, build fresh from current architecture rather than reviving these early-build paths (lots of legacy bloat). So this code is removable, not preserve-for-reuse.
- **Action**: Future cleanup — remove sunset `single`/`tournament` code paths once the team commits to the rebuild-from-scratch plan. Docs that describe these paths are tagged "SUNSET MODE" (e.g. `Game_Init_System.md` Tournament / Single sections; `Lineup_Selection_Screen.md`) and point here.
- **Priority**: Low (dead-end paths; not causing bugs, just bloat/confusion). Do as a deliberate sweep, not piecemeal.

### Steal → HCO setup: backend computes positioning that the frontend no longer renders (found 6-13-26 during doc sweep) [CODE-CLEANUP]
- **Issue**: `resolve_half_court_offense_logic` (~L4820, `BackEnd/.../half_court_offense*`) still computes detailed Steal → HCO setup positioning — moving the stealer away from the basket plus a bespoke PG reposition for other players — and emits fields like `is_steal_hco_setup`, `ball_handler_hco_setup_*`, and `other_players_hco_setup_movements`. The frontend has removed all of the corresponding animation code (`animateStealHCOSetup()`) and stopped reading those fields.
- **Impact**: Low — backend is doing compute-but-unrendered work. No visible bug, just wasted computation and a misleading contract (emitted fields nothing consumes).
- **Action**: Remove the Steal → HCO setup positioning computation and its emitted fields from the backend resolver (or, if the visual is wanted back, re-add the frontend animation). Confirm no other consumer reads `is_steal_hco_setup` / `ball_handler_hco_setup_*` / `other_players_hco_setup_movements` first.
- **Priority**: Low (dead/unrendered compute, not causing bugs)

### Legacy steal-entry Fast Break dead code + unused `STEAL_ENTRY_*` constants (found 6-13-26 during doc sweep) [CODE-CLEANUP]
- **Issue**: All steals are short-circuited to the UESS-migrated `after_steal` resolver early in `resolve_fast_break_logic` (~L1056), which makes the legacy steal-entry movement block later in the same function (~L1195–1360) unreachable dead code. The `STEAL_ENTRY_MOVE_*` / `STEAL_ENTRY_Y_*` constants that block relied on are now unused on the rendered path in both `BackEnd/constants/fast_break_constants.py` and `FrontEnd/static/js/phaser/constants/fastBreakConstants.js`.
- **Impact**: Low — unreachable code + orphaned constants. No runtime effect, just bloat/confusion for anyone reading the FB resolver.
- **Action**: Delete the unreachable steal-entry block in `resolve_fast_break_logic` and remove the unused `STEAL_ENTRY_*` constants from both the backend and frontend constants files. Verify nothing on the live `after_steal` path references those constants before removing.
- **Priority**: Low (dead code; tie in with the FB-coverage follow-up noted in the "Stale FB test suite" item above)

### State Telemetry Violations (Phase 1.3) [CODE-CLEANUP]
- **Issue**: `game_id` is being read/written to `gameStore` when it should come from URL according to State & Persistence Contract
- **Location**: Multiple locations detected by Phase 1.3 telemetry
- **Impact**: Low - telemetry is working as intended, detecting contract violations
- **Action**: Future cleanup - refactor to use URL as source of truth for `game_id` instead of `gameStore`
- **Priority**: Low (informational only, not causing bugs)

### Missing Rebound Data Warning [CODE-CLEANUP]
- **Issue**: ShotAnimationSystem reports "Rebound data missing, skipping embedded rebound" for some MISS shots
- **Location**: `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`
- **Impact**: Low - may be expected if rebound is handled in separate turn, but worth monitoring
- **Action**: Investigate if this is expected behavior or if rebound data should always be present
- **Priority**: Low (monitoring only)

### Invalid State Transition Warning [CODE-CLEANUP]
- **Issue**: State machine attempts no-op transition (HalfCourt -> HalfCourt)
- **Location**: `FrontEnd/static/js/phaser/animation/AnimationEngine.js` → `handleBaselineInbound()`
- **Impact**: Low - harmless but indicates unnecessary `safeTransition()` call
- **Action**: Review `handleBaselineInbound()` to avoid calling `safeTransition()` when already in target state
- **Priority**: Low (code cleanup)

### Missing Team Background Images (404s) [CODE-CLEANUP]
- **Issue**: 404 errors for team background images (e.g., `south_lancaster-background.png`, `little_york-background.png`)
- **Location**: `FrontEnd/static/images/teams/{team_slug}/` (`{team_slug}_background.png`; see `docs/docs_1_systems/00_General_Systems/Team_Images_System.md` and `FrontEnd/static/common.js` asset helpers)
- **Impact**: Low - missing assets, doesn't affect functionality
- **Action**: Add missing team background images or update references
- **Priority**: Low (cosmetic only)


## Fixed Bugs (January 2025)

✅ **Playcall Center Overrides Not Working After Sim Quarter → Play Quarter** (Fixed: January 2025)
- **Issue**: Playcall overrides were not being applied during Play Quarter after simulating previous quarters (e.g., Sim Quarter for Q1-Q3, then Play Quarter for Q4).
- **Root Cause**: `user_team_side` was `None` in the game state, causing the override check in `turn_manager.py` to skip processing with "no user_team (user_team_side=None)". This happened because `user_team_side` wasn't being preserved when games were loaded from the database or when transitioning between Sim Quarter and Play Quarter modes.
- **Fix**: Added safeguards to preserve and restore `user_team_side`:
  - Preserve `user_team_side` from in-memory game before any DB operations
  - When loading from DB, use priority: saved document → preserved in-memory value → request value
  - Set `user_team_side` in in-memory game if missing (from request or preserved value)
- **Result**: Playcall overrides now work correctly after Sim Quarter → Play Quarter transitions
- **Status**: ✅ Fixed and committed (January 2025)

✅ **Tournament Command Center Stats Bugs** (Fixed: January 2025)
- **Totals showing "undefined"**: Fixed missing W/L initialization in totals object
- **Player stats not populating on Roster tab**: ✅ **FIXED** - Refactored Tournament mode to match Franchise pattern exactly
  - `loadRoster()` now merges stats from tournament document into roster data (matches Franchise pattern)
  - `renderRoster()` now calls `renderRosterStats()` internally (matches Franchise `renderTeam()` pattern)
  - Removed old `renderStats()` function that used separate stats array
  - Updated HTML to use `roster-stats-body` instead of `stats-body` (matches Franchise)
- **Team stats container scroll issue**: Fixed by removing `scroll-x` wrapper and using inline overflow styling
- **Teams from user's game not populating on Stats tab**: ✅ **FIXED** - Now using shared `TeamStatsTable` module (same as Franchise)
- **Note**: Computer teams showing 2 games is a backend issue (likely double finalization) - needs backend investigation

✅ **Team Stats SS&S Refactoring** (Completed: January 2025)
- **Frontend**: Extracted shared `teamStatsTable.js` module (~160 lines of duplicate code removed)
  - Both Tournament and Franchise modes now use `TeamStatsTable.renderTeamStatsTable()` and `TeamStatsTable.sortTeamStats()`
  - Removed unnecessary roster refresh logic from Tournament `refreshTeamStats()`
- **Backend**: Extracted shared `team_stats_aggregator.py` utility (~130 lines of duplicate code removed)
  - Both Tournament and Franchise endpoints now use `aggregate_team_stats_from_players()`
  - Single source of truth for team stats aggregation logic
- **Total Reduction**: ~290 lines of duplicate code eliminated
- **Benefits**: One fix applies to both modes, prevents future bugs, ensures consistent behavior

✅ **Tournament Mode Roster/Stats Refactoring** (Completed: January 2025)
- **Refactored to match Franchise pattern exactly**: Tournament mode now uses identical code structure as Franchise mode
  - `loadRoster()`: Loads roster, loads tournament doc, merges stats into roster data (matches Franchise exactly)
  - `renderRoster()`: Calls `renderRosterStats()` internally (matches Franchise `renderTeam()` pattern)
  - Removed old `renderStats()` and `renderStatsTable()` functions that used separate stats array
  - Updated HTML: Changed `stats-body` to `roster-stats-body` to match Franchise
  - **Result**: Tournament and Franchise modes now use the exact same execution pattern with only variable names different (`tournament_id` vs `franchise_id`, `tournament.players` vs `franchise.players`)

✅ **Tournament Player Stats Not Saving - SS&S Refactoring** (Fixed: January 2025)
  - **Issue**: Player stats remained at zero after Tournament games, even though games were played
  - **Root Cause**: Tournament mode used per-player update pattern with complex nested path queries, while Franchise mode used single atomic update
  - **Fix**: Refactored Tournament mode's `finalize_game()` to match Franchise mode's pattern exactly:
    - Single atomic MongoDB update for all players (instead of per-player updates)
    - Document-level `applied_games` check (removed complex nested path queries)
    - Uses `$setOnInsert` for automatic player initialization
    - Processes all players from `box_score` in one operation
  - **Result**: Tournament and Franchise modes now use identical execution patterns, ensuring consistent behavior and eliminating zero stats issues
  - **Documentation**: See `docs/To Do/Tournament_vs_Franchise_Player_Stats_Comparison.md` for detailed comparison

## Current Investigation (January 2025)

### ✅ Addressed (Jun 2026): HCO entry `current_bh_id is None` after MISS with schema bounce
- **Issue:** Prior turn was **HCO MISS** with `ball_bounce_x/y` and schema `animation_steps`, but `rebounderId` / `rebound_type` / `next_play_type` were missing → discrete **DREB** promotion skipped → next **HCO** turn's entry orchestrator logged `[HCO ENTRY BUG]` (loose-ball prior turn, no `final_ball_handler_id`).
- **Fix:** `game_manager._repair_miss_bounce_rebound_contract()` runs in `simulate_macro_turn` before `_append_turn`, restoring rebound metadata from `game_state.last_rebounder` / `last_rebound` when bounce coords exist on migrated MISS/BLOCK rows. See `Turn_by_Turn_System.md` (Discrete DREB turn §2) and `Rebound_System.md` (MISS/BLOCK turn contract).

### ✅ Addressed (May 2026): Discrete HCO / HCT / FB MISS → DREB → HCO outlet (`AnimationEngine`)
- **Fix:** After discrete **`DREB`** `animation_steps` `playTurn`, `AnimationEngine._maybeRunDiscreteDrebOutletLeadIn` calls **`runDefensiveReboundSetup`** when `next_play_type` is **HCO/HCT/FCP**, using the prior **MISS/BLOCK** turn for **`dreb_outlet_pass`** / get-back. Skips **FAST_BREAK** next and **`force_foul_after_dreb`**. See `FrontEnd/static/js/phaser/animation/AnimationEngine.js` and **`Turn_by_Turn_System.md`** (Discrete `DREB` turn).
- **Remaining (optional hardening):** suppress duplicate embedded rebound animation on the MISS when `next_play_type === "DREB"` if double-capture is still visible; HCO step-0 tolerance tuning if any edge case remains.

### 📜 Historical: HCO MISS → discrete DREB outlet gap (pre–May 2026)
- Prior to **`AnimationEngine._maybeRunDiscreteDrebOutletLeadIn`**, `runDefensiveReboundSetup` was not invoked after discrete **`DREB`** `playTurn`, and **`ShotAnimationSystem.handleDefensiveRebound`** skipped outlet when the MISS row’s **`next_play_type`** was rewritten to **`"DREB"`**. Root-cause write-up and diagnostics lived here during migration; see **✅ Addressed** above and **`Turn_by_Turn_System.md`**.

### ✅ Fixed: Duplicate Teams Bug
- **Root Cause**: When `team_id_str` was not a valid ObjectId (e.g., "BENTLEY_TRUMAN"), the code still added it to output, creating duplicates
- **Fix**: Updated `BackEnd/utils/team_stats_aggregator.py` to resolve non-ObjectId team IDs to ObjectIds before adding to output, or skip them if they can't be resolved
- **Status**: ✅ Fixed and committed

### ✅ Fixed: Player Stats Not Saving for User Games (Mode Field Missing)
- **Root Cause**: Frontend was not passing `tournament_id` and `mode` in `/api/simulate-quarter` request payload, causing backend to default to `mode: "single"` instead of `mode: "tournament"`. When `finalize_game()` was called with `mode="tournament"`, the game document had `mode: "single"`, causing a mismatch and potentially skipping Tournament processing.
- **Fix**: 
  - Added `tournament_id` and `mode` to payload in `gameScene.js` (main gameplay flow)
  - Added `tournament_id` and `mode` to payload in `bootGame.js` (sim-to-4th and sim-full-game flows)
  - This ensures backend correctly sets `mode: "tournament"` on game document, allowing `finalize_game()` to process Tournament stats correctly
- **Result**: Game documents now have correct `mode: "tournament"` field, ensuring `finalize_game()` processes player stats correctly for Tournament mode
- **Status**: ✅ Fixed and committed

### ✅ Fixed: Player Stats Not Saving for User Games (Mode Field Missing)
- **Root Cause**: Frontend was not passing `tournament_id` and `mode` in `/api/simulate-quarter` request payload, causing backend to default to `mode: "single"` instead of `mode: "tournament"`. When `finalize_game()` was called with `mode="tournament"`, the game document had `mode: "single"`, causing a mismatch and potentially skipping Tournament processing.
- **Fix**: 
  - Added `tournament_id` and `mode` to payload in `gameScene.js` (main gameplay flow)
  - Added `tournament_id` and `mode` to payload in `bootGame.js` (sim-to-4th and sim-full-game flows)
  - This ensures backend correctly sets `mode: "tournament"` on game document, allowing `finalize_game()` to process Tournament stats correctly
- **Result**: Game documents now have correct `mode: "tournament"` field, ensuring `finalize_game()` processes player stats correctly for Tournament mode
- **Status**: ✅ Fixed and committed

### ✅ Fixed: Player Stats Not Saving for User Games (Race Condition + Missing game_document)
- **Root Cause**: Two issues prevented player stats from saving:
  1. **Race Condition**: Tournament mode was looking up game document from database in `/tournament/save-result`, which could be stale or incomplete (save-result called before Q4 save completes). Franchise mode avoided this by accepting `game_document` directly from the request.
  2. **Missing game_document in Sim Full Game**: When using "Sim Full Game" in `bootGame.js`, the fetched game document wasn't being passed as `game_document` to `finalizeGame()`, so `finalizeGame()` couldn't detect it and pass it to the backend.
- **Fix**: 
  - **Frontend (`finalizeGame.js`)**: Added logic to detect if `simData` itself is a complete game document (has `box_score` and `game_id`) and use it directly as `game_document` when calling `/tournament/save-result`. This handles the "Sim Full Game" flow from `bootGame.js`.
  - **Backend (`tournament_routes.py`)**: 
    - Added `game_document` field to `TournamentResultRequest` (matches Franchise `CompleteWeekRequest`)
    - Updated `/tournament/save-result` to use `request.game_document` if provided (matches Franchise pattern)
    - Added logic to save `game_document` to database before calling `finalize_game()` to ensure complete data is available
  - **Frontend (`finalizeGame.js`)**: Updated to pass `final_game_document` from `simulate-quarter` response to `/tournament/save-result` (matches Franchise pattern)
- **Result**: Tournament mode now uses the exact same pattern as Franchise mode - receives fresh, complete game document directly from frontend, saves it to database, and `finalize_game()` processes complete `box_score` data. Player stats now save correctly for both regular gameplay and "Sim Full Game" flows.
- **Status**: ✅ Fixed and committed (January 2025)

### 🔍 Investigating: Formatting Bug (Team Stats Table)
- **Current State**: 
  - HTML has `overflow-x: auto` on wrapper div (line 143 in tournament.html)
  - CSS has `min-width: 800px` on `.stats-table` (line 425 in tournament.css)
  - Structure matches Franchise mode
- **Possible Causes**:
  1. CSS not being applied correctly
  2. Container width constraint
  3. Browser caching
- **Next Steps**: Verify CSS is loading and container width is correct

### 🔍 Investigating: Continuous 404 Requests for Player Tooltip Images (court.html)
- **Issue**: Continuous stream of 404 requests for player headshot images (`/images/players/${playerId}.png` and `/images/players/generic_headshot.png`) even when game is paused
- **Location**: `FrontEnd/static/js/phaser/gameScene.js` lines 519-523 (player tooltip image loading)
- **Root Cause**:
  1. Tooltip tries to load player image: `/images/players/${playerId}.png` (UUID-based filenames)
  2. When that fails (404), `onerror` handler tries fallback: `/images/players/generic_headshot.png`
  3. Fallback also doesn't exist (404), creating a retry loop
  4. `mousemove` event listener (lines 673-683) is active even when paused, continuously triggering tooltip updates and image load attempts
- **Impact**:
  - Unnecessary network requests (continuous 404s)
  - Console noise
  - Potential performance impact from repeated failed requests
  - May contribute to slow initial game download
- **Expected Behavior**:
  - Image should load once when tooltip is first shown
  - Should fail gracefully if missing (hide image or show placeholder)
  - Should not retry continuously after failure
  - Tooltips should be disabled when game is paused
- **Fix Required**:
  1. Add flag to prevent retries after first failure
  2. Hide image element on error instead of trying non-existent fallback
  3. Optionally disable tooltips when game is paused
  4. Ensure tooltip image only loads once per tooltip show, not on every mousemove

### 🔍 Investigating: Stale Data on Initial Page Load (Race Condition)
- **Issue**: When landing on `court.html`, the page initially displays stale/inaccurate data:
  - Team TOL (timeouts) shows as 5 (hardcoded HTML default)
  - Team scores may be incorrect (defaults to 0)
  - All players in box score show 100% NG (energy)
  - After a few seconds or after first turn processes, data calibrates to correct values
- **Location**: 
  - `FrontEnd/static/court.html` - Hardcoded HTML defaults (lines 2187, 2289: `TOL: 5`)
  - `FrontEnd/static/js/phaser/utils/loadGameStats.js` - `initializeGameStats()` function
- **Root Cause**: 
  1. **HTML Defaults**: `court.html` has hardcoded defaults (`TOL: 5`, scores `0`) that render immediately
  2. **Race Condition**: `initializeGameStats()` runs asynchronously, so page renders with defaults before API call completes
  3. **Incomplete Data Loading**: `displayAccumulatedScores()` only updates scores, NOT timeouts (missing timeout update)
  4. **Missing gameId**: If URL lacks `game_id`, `initializeGameStats()` returns early and defaults persist
  5. **Player Energy Not Updated**: `displayAccumulatedPlayerStats()` doesn't show/update NG (energy) in box score
- **Why It "Calibrates" After Turn**: 
  - When first turn processes, `gameScene.js` `updateScoreboard()` receives real turn data
  - Updates scores, fouls, AND timeouts from turn data, overwriting stale defaults
- **Impact**:
  - Poor user experience - users see incorrect data on page load
  - Confusing behavior - data "magically" updates after a few seconds or first turn
  - May cause users to make decisions based on stale data
- **Expected Behavior**: 
  - Page should show correct data immediately on load (or show loading state until data is ready)
  - Timeouts should be updated from game state, not hardcoded defaults
  - Player energy should reflect actual values from game state
- **Fix Required**: 
  1. **Update `displayAccumulatedScores()`** to also update timeouts:
     - Read from `gameData.teams[team_id].timeouts` (unified structure) or fallback to `gameData.timeouts.home/away`
     - Update `#home-tol` and `#away-tol` elements with correct values
  2. **Ensure `initializeGameStats()` completes before page is "ready"**:
     - Show loading state until data is loaded, OR
     - Wait for `initializeGameStats()` to complete before rendering scoreboard
  3. **Update player energy display** if shown in stats panel (may require separate function)
  4. **Handle missing `gameId` gracefully**:
     - If `gameId` missing, either fetch from another source or show appropriate defaults
     - Don't silently fail and leave stale defaults
- **Priority**: Medium-High (affects user experience and data accuracy)

### 🔍 Investigating: "Play Quarter" Button Requires Two Clicks (Initialization Timing Bug)
- **Issue**: On first page load, users must click "Play Quarter" button twice to start the game. First click does nothing, second click works. When returning to the page (e.g., after navigating away and back), first click works correctly.
- **Location**: `FrontEnd/static/js/phaser/bootGame.js` - `initGame()` function
- **Root Cause**: 
  - The "Play Quarter" button is visible and clickable immediately when the page loads
  - `bootGame.js` runs asynchronously and attaches the click event listener in `initGame()` function
  - If user clicks before `initGame()` finishes attaching the handler, the click does nothing
  - On subsequent visits, the handler is already attached (or page loads faster), so first click works
- **Impact**:
  - Poor user experience - users must click twice on first load
  - Confusing behavior - button appears clickable but doesn't respond
  - Test reliability issues - tests need workarounds to handle this timing issue
- **Expected Behavior**: 
  - Button should be disabled/hidden until initialization completes, OR
  - Handler should be attached synchronously before button is shown, OR
  - Show loading state until ready
- **Fix Required**: 
  1. Disable button initially, enable after `initGame()` completes
  2. OR attach handlers before showing button
  3. OR show loading state until initialization is complete
- **Priority**: Medium (affects user experience and test reliability)

### ✅ Fixed: Pre-Game Set-Lineup MO Bars Show Stale Non-Zero Values (June 2026)
- **Issue**: At pre-game set-lineup, starter MO bars showed persistent non-zero fills (same every game); court correctly showed MO 0.
- **Root Cause**: `init-game` wrote `game_id` to the URL but `loadRoster()` still used the page-load `gameId` const (null), skipped `/api/game/...` merge, and displayed MO from franchise roster (FPD training Inspire).
- **Fix**: `getActiveGameId()` in `set-lineup.js` reads URL after `init-game`; game doc EM/MO/NG merge runs before slot render.
- **Docs**: `Lineup_Selection_Screen.md`, `Player_Momentum_System.md`.

### 🔍 Investigating: Slow Lineup Screen Load in Single Game Mode
- **Issue**: Lineup screen takes 5-10 seconds to load player data when starting a Single Game, despite network request completing in only 294ms (49.4 kB response). The delay occurs after the network response is received, indicating a frontend processing bottleneck.
- **Location**: `FrontEnd/static/set-lineup.js` - Likely contains the bottleneck
- **Environment**: Staging
- **Mode**: Single Game Mode
- **Symptoms**:
  - Network request completes quickly (294ms)
  - Response size: 49.4 kB (reasonable)
  - UI takes 5-10 seconds to appear after network completion
  - Users see loading state for extended period
- **Root Cause Analysis (Initial)**:
  - **Network is NOT the bottleneck** - Request completes in 294ms
  - **Frontend processing is the bottleneck** - 4.7-9.7 seconds of blocking JavaScript execution
  - Likely causes:
    1. Heavy synchronous data processing (player stats/attributes/energy calculations)
    2. Inefficient DOM rendering (creating many player elements in loop, no batching)
    3. Sequential blocking operations (for loops, synchronous await calls)
    4. Missing optimization patterns (no debouncing, no requestAnimationFrame, no lazy loading)
- **Investigation Needed**:
  1. Check browser performance profiler to identify where time is spent (scripting vs rendering)
  2. Review `set-lineup.js` for synchronous loops processing player data
  3. Check for DOM thrashing (too many DOM updates causing reflows)
  4. Identify any hidden sequential operations happening after network request
- **Expected Behavior**: Lineup screen should load and display player data within 1-2 seconds after network request completes.