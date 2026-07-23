##Bugs
1. Teleported an HCO entry step, result was a DB turnover
2. Getting some double rebounds (SFX, maybe animaiton, not sure about logic)


##Full Product Readiness
2. Stripe
3. PvP sim
4. Tunable Constants file
5. Downloadable game vs Live game dynamics
7. Comprehensive Blowout Governor
8. HCO Roles Audit & Fixes
9. Better timing on shots, most should be more immediate, those that are not should have pre-shot movement


##Full Product Perfection
1. Training Camp News Report
2. Week 20 Recruiting Report to Inbox
3. Recruiting Round Up Results
6. Add a new hire news story for user team
25. Fast Break and P/T callouts in the Scouting Report of opponent
26. Add tournament design magic to the UX -- court screen, modals, FCC, etc
102. Team court images
108. Message board
110. Strategic Geek Points system
113. Bring logic to screens
114. Better individual player defense stat tracking
116. User account -- link X & Facebook?
117. More action on Signing Day
125. MM: Micro Movement SFX
127. Get Aggressive / Get Conservative settings and Playcall Center buttons
128. Add a badass design appraoch to New Stories
129: Loose Balls!
131. Centralized Turn Transition Helper / System
132. Players as Characters
135. Better simming of computer training
136. Need to better calibrate season to season player attribute progression
137. Watermark free version of player headshots

199. Mobile
200. PvP live

##Continuous Evolution (base is built)
1. In-Game SFX: Deny, Picked Up His Dribble, No Good/Missed
2. Advanced Topics tutorials
3. Steam Strategy
4. Monetization plan

##Player Images
1. AI player portrait production (confs 2–16) — see [`player_image_generator.md`](player_image_generator.md)



<!--
SEARCH TAG: [CODE-CLEANUP]
Every outstanding code-level fix/cleanup item surfaced during the documentation sweep (and the
ongoing code-cleanup backlog) is tagged with the literal token [CODE-CLEANUP]. To get the complete
list across the whole repo, run:  rg "\[CODE-CLEANUP\]"
This includes items in this file (Future Cleanup, P0, Fast Break backlog, FB test follow-up) plus
inline notes left in individual system docs. (Sunset-mode code removal also carries its own
"SUNSET MODE" tag inside the docs that describe those paths, and is cross-linked from here.)
-->

## Stale FB test suite — open follow-up [CODE-CLEANUP]

Stale pre-refactor FB tests were deleted 6-12-26; suite is green. **Still open:** current-engine FB coverage is thin — `test_fast_break_rr_triangle_updates.py` covers RR/Triangle emitters, but the CR resolver path and `after_steal_fast_break.py` (resolver + emitter) have little/no direct test coverage. Write new tests against the current resolvers when FB work resumes.

## P0 — HCO contract clock overruns (carried from Unified_Animation_System.md, 6-12-26) [CODE-CLEANUP]

Two critical issues from the animation blueprint's "Known HCO Turn Issues" list (`projects/Unified_Animation_System.md`):

1. **HCO resolution hard overrun:** observed throw `"[HCO resolution contract] clock overrun ... elapsedGameSeconds=649.00"` on a `DEAD BALL` path. **Partial mitigation (Option A):** turn-boundary guards in `turnAnimation.js` use contract-capped elapsed (`min(wall_elapsed_ms, real_time_elapsed_ms + guard_slack_ms)`). Throws still exist; needs live validation before closing.
2. **HCO step-pass hard overrun in BATCH/DEAD BALL sub-turns:** observed throw `"[HCO step pass contract] clock overrun ... elapsedGameSeconds=405.78"` at `step=6`. **Still uncapped** — step-pass guard uses raw `Date.now() - stepStartMs` (no Option A). Track separately from #1.

## Animation timing pauses

**Meta:** With dynamic HCO on, Motion/Set-Play render via backend `animation_steps[]` (`animationPlayback.js`). Pause durations are stamped in Python (`time_elapsed`, `hold_ms`); FE-only fixes miss the source. Design work applies only to optional idle-sprite drift (Bucket 1 secondary).

### Open — Bucket 1: Long pauses between HCO steps (Motion only)
- **Symptom:** All ten players frozen 700–1400ms on many Motion steps; Set Play unaffected.
- **Root cause:** Motion "subtle-movement" beats floor at **2–4 game-seconds** (`SUBTLE_STEP_ELAPSED_BY_TEMPO` in `motion_step_decision.py`; stamped via `skeleton_step_emitter.py`). Schema engine hard-waits full `time_elapsed` (`animationPlayback.js`). Set Play forces `offense_reads=False` → fewer subtle beats.
- **Fix:** Decouple sim clock from visual time — keep 2–4s on game ledger, stamp small visual `time_elapsed`. Optional: off-ball drift during BH hold so 9 players don't read as frozen.
- **Secondary:** Confirm BH hold doesn't block the other 9 from moving; consider idle organic sprite animation on truly stationary steps.

## Fast Break animation backlog (legacy path) [CODE-CLEANUP]

Tracked from archived [`Z-Completed/Fast_Break_Refactor.md`](Z-Completed/Fast_Break_Refactor.md). **UESS schema path is primary** for `covert_release`, `rim_runner`, `triangle`, `after_steal` when `animation_steps` exist; legacy `runFastBreakSequence` remains the fallback when steps are missing / variant unmigrated.

- Advance triggers unreliable on legacy `fastBreak.js` / `runFastBreakSequence` (phase boundaries hang or short-circuit).
- FB visual timing still uses FE `getPlayerDuration` on legacy path; backend does not stamp per-player `game_seconds` in legacy `animator.capture_fast_break_animation` payload.
- Charge/blocking foul on FB: stop animation immediately (don't wait for defensive spot) — see Bugs §14.
- Full phase map and backend sites: archived refactor doc.

---

## Future Cleanup (Non-Critical Warnings)

### Sunset mode code removal (Single Game + Tournament) — surfaced during doc sweep 6-13-26 [CODE-CLEANUP]
- **Issue**: Single Game and Tournament modes are sunset (not user-facing), but their code paths still exist throughout the backend/frontend (e.g. `init_game()` mode branches for `single`/`tournament` in `BackEnd/api/api.py`, tournament master-copy seeding, single-game empty-playbook init, plus tournament/single routes and frontend pages).
- **Decision (prior)**: When tournaments / single games are reintroduced, build fresh from current architecture rather than reviving these early-build paths (lots of legacy bloat). So this code is removable, not preserve-for-reuse.
- **Action**: Future cleanup — remove sunset `single`/`tournament` code paths once the team commits to the rebuild-from-scratch plan. Docs that describe these paths are tagged "SUNSET MODE" (e.g. `Game_Init_System.md` Tournament / Single sections; `Lineup_Selection_Screen.md`) and point here.
- **Priority**: Low (dead-end paths; not causing bugs, just bloat/confusion). Do as a deliberate sweep, not piecemeal.

### Steal → HCO setup: backend computes positioning that the frontend no longer renders (found 6-13-26 during doc sweep) [CODE-CLEANUP]
- **Issue**: `resolve_half_court_offense_logic` (`BackEnd/engine/phase_resolution.py`) still emits `is_steal_hco_setup`, `ball_handler_hco_setup_*`, and `other_players_hco_setup_movements`. The frontend has removed `animateStealHCOSetup()` and stopped reading those fields. UESS has a replacement (`_append_post_steal_hco_transition` in `skeleton_step_emitter.py`), but the old role-field contract is unused.
- **Impact**: Low — backend is doing compute-but-unrendered work. No visible bug, just wasted computation and a misleading contract.
- **Action**: Remove the Steal → HCO setup positioning computation and its emitted fields from the backend resolver. Confirm no other consumer reads those fields first.
- **Priority**: Low (dead/unrendered compute, not causing bugs)

### Legacy steal-entry Fast Break dead code + unused `STEAL_ENTRY_*` constants (found 6-13-26 during doc sweep) [CODE-CLEANUP]
- **Issue**: All steals are short-circuited to the UESS-migrated `after_steal` resolver early in `resolve_fast_break_logic` (~L1205), which makes the legacy steal-entry movement block later in the same function (~L1517–1541) unreachable dead code. The `STEAL_ENTRY_MOVE_*` / `STEAL_ENTRY_Y_*` constants that block relied on are now unused on the rendered path in both `BackEnd/constants/fast_break_constants.py` and `FrontEnd/static/js/phaser/constants/fastBreakConstants.js`.
- **Impact**: Low — unreachable code + orphaned constants. No runtime effect, just bloat/confusion for anyone reading the FB resolver.
- **Action**: Delete the unreachable steal-entry block in `resolve_fast_break_logic` and remove the unused `STEAL_ENTRY_*` constants from both the backend and frontend constants files. Verify nothing on the live `after_steal` path references those constants before removing.
- **Priority**: Low (dead code; tie in with the FB-coverage follow-up noted in the "Stale FB test suite" item above)

### State Telemetry Violations (Phase 1.3) [CODE-CLEANUP]
- **Issue**: `game_id` is being read/written to `gameStore` when it should come from URL according to State & Persistence Contract
- **Location**: `FrontEnd/static/js/state/gameStore.js` (`setGameId` / `getGameId` + telemetry)
- **Impact**: Low - telemetry is working as intended, detecting contract violations
- **Action**: Future cleanup - refactor to use URL as source of truth for `game_id` instead of `gameStore`
- **Priority**: Low (informational only, not causing bugs)

### Invalid State Transition Warning [CODE-CLEANUP]
- **Issue**: State machine attempts no-op transition (HalfCourt -> HalfCourt)
- **Location**: `FrontEnd/static/js/phaser/animation/AnimationEngine.js` → `handleBaselineInbound()` still calls `safeTransition` unconditionally (tip path has an `is(HalfCourt)` guard; BIP does not)
- **Impact**: Low - harmless but indicates unnecessary `safeTransition()` call
- **Action**: Review `handleBaselineInbound()` to avoid calling `safeTransition()` when already in target state
- **Priority**: Low (code cleanup)

---

## Open Investigations

### "Play Quarter" Button Requires Two Clicks (Initialization Timing Bug)
- **Issue**: On first page load, users must click "Play Quarter" twice to start the game. First click does nothing, second click works. When returning to the page (e.g., after navigating away and back), first click works correctly.
- **Location**: `FrontEnd/static/js/phaser/bootGame.js` - `initGame()` function
- **Root Cause**:
  - The "Play Quarter" button is visible and clickable immediately when the page loads (`court.html`)
  - `bootGame.js` runs asynchronously and attaches the click event listener late in `initGame()`
  - If user clicks before `initGame()` finishes attaching the handler, the click does nothing
- **Fix Required**:
  1. Disable button initially, enable after `initGame()` completes
  2. OR attach handlers before showing button
  3. OR show loading state until initialization is complete
- **Priority**: Medium (affects user experience and test reliability)

### Live Court Sidebar Shows All 12 Players Instead of Active 5 (July 2026)

- **Symptom:** During live `court.html` gameplay, both player box-score sidebars listed the full 12-man roster per team instead of the five active players. Court sprites still showed 5 per side. Observed after a **computer timeout** (no lineup changes); corrected after a later **user timeout + lineup change** return to court.
- **Fingerprint:** Bad rows used bare full names (`Yadiel Terra`), not Phaser’s `#jersey LastName` format — so the writer was not `gameScene.js` `initTeamTable`.
- **Clear cause (code-backed):**
  1. Backend `GameManager.get_box_score()` intentionally returns lineup **+** bench (~12).
  2. Phaser sidebar correctly builds only `PG/SG/SF/PF/C`.
  3. `displayAccumulatedPlayerStats()` in `FrontEnd/static/js/phaser/utils/loadGameStats.js` clears each tbody and dumps `Object.values(boxScore[teamName])` with **no** active-five filter; names are raw `playerStats.name`.
  4. That runs from `initializeGameStats()` on court load when game data resolves.
  5. Lookup is by URL team **names** (`?home=` / `?away=`). `/api/game/{id}/resume-state` aliases the full box under those names (dump succeeds → 12 rows). `/api/game/{id}` keys by **team_id** (name lookup usually fails → function no-ops → Phaser’s 5 rows remain).
- **Why “fixed” after user timeout + lineup change:** set-lineup Return forces `resume_from_timeout=true` → resume-state probe skipped → `/api/game` path → name lookup fails → dump does not run; Phaser remount rebuilds 5.
- **Not proven without URL/network capture:** exact entry params on the bad computer-timeout return (e.g. whether resume-state was probed because `resume_from_timeout` was missing/false). Mechanism that produces 12 rows is clear; that one trigger instance is the remaining link.
- **Likely fix (when authorized):** filter to `PG`–`C` (or current lineup IDs) in `displayAccumulatedPlayerStats`, and/or resolve box score by `team_id` consistently.
