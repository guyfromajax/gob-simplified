##Bugs
1. Getting some double rebounds (SFX, maybe animaiton, not sure about logic)
2. Screenshot Capture Tool is still not working
3. Remove BT background from recruit images


##Full Product Readiness
1. Downloadable game vs Live game dynamics
2. College and Pro setup
3. ~~Assign images and jersey numbers to walk ons who make the roster -- and paint their jersey~~ **DONE** (camp-cut assign + walk_on_portraits pool; publish kits to R2 via `scripts/recruit_sets/publish_walk_on_portraits.py`)

##Playtest Launch / In Progress
1. Steam
2. Stripe
3. Balance Team attributes
-----
4. PvP sim -- playtest post-launch / immediate parallel task


##Full Product Perfection
1. Training Camp News Report
2. Week 20 Recruiting Report to Inbox
3. Recruiting Round Up Results
4. Comprehensive Blowout Governor
6. Add a new hire news story for user team
102. Team court images
108. Message board
113. Bring logic to screens
114. Better individual player defense stat tracking
116. User account -- link X & Facebook?
117. More action on Signing Day
125. MM: Micro Movement SFX
127. Get Aggressive / Get Conservative settings and Playcall Center buttons
128. Add a badass design appraoch to New Stories
129: Loose Balls!
131. Centralized Turn Transition Helper / System
137. Watermark free version of player headshots
138. College & Pro game system
139. Mod system for uploading custom teams

199. Mobile
200. PvP live

##Continuous Evolution (base is built)
1. In-Game SFX: Deny, Picked Up His Dribble, No Good/Missed
2. Advanced Topics tutorials
3. Steam Strategy
4. Monetization plan
5. Players as Characters

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

## Two test modules fail to import — invisible coverage debt (found 2026-08-04) [CODE-CLEANUP]

`test_eoq_clock_progression.py` and `test_final_turn_entry_pass_chain.py` raise `ImportError` at collection — they import symbols that no longer exist (`roll_anchor_clock` from `eoq_clock_progression`, `_append_final_turn_entry_pass_if_needed` from `skeleton_step_emitter`). A module that can't import is **invisible debt**: it reads as passing coverage while testing nothing, and the exclusion (`--ignore` in any full-suite run) becomes permanent by default. Either repoint each test at the current API (the behaviour it covers — EOQ clock progression, final-turn entry-pass chaining — likely still exists under a renamed function) or delete it if the behaviour is gone. Do not leave them uncollectable.

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

### DEFERRED: M0 throwaway DB for DB-dependent tests — restore runbook (August 2026)

Deferred, not cancelled. Needed when identity wiring starts and DB-dependent tests matter.
Context: `tests/conftest.py` block-lists `gob` and `gob-staging`, so the 217 DB-touching tests
(45 files, 42 of which contain `delete_many({})`) cannot run without a throwaway.

- **Size constraint:** staging is **498.84 MB storage against the 512 MB M0 cap**. A full clone
  does not fit. **Restore a subset**, not everything — `plays`, `teams`, `defenses`, and a small
  slice of `players` cover most fixture needs; skip `games`, `franchise_players_data`,
  `franchise_team_data` and the `players_backup_*` collections, which are the bulk.
- **Namespace rename is required** (source db `gob-staging` → target `gob-test`):
  ```
  mongodump   --uri "<staging-uri>" --db gob-staging \
              --collection plays --collection teams --collection defenses \
              --out /tmp/gobdump
  mongorestore --uri "<m0-uri>" \
              --nsFrom 'gob-staging.*' --nsTo 'gob-test.*' \
              /tmp/gobdump
  ```
  Without `--nsFrom/--nsTo` the restore recreates the database under its original name, which
  the conftest guard then blocks — the rename is what makes the throwaway usable.
- **Then:** point `.env.local` at the M0 with db name `gob-test` (any name not in
  `_BLOCKED_DB_NAMES`) and the guard passes legitimately rather than being worked around.
- **Prefer a separate M0 cluster over a `gob-test` database on the production cluster** — the guard
  block-lists by database *name*, so a same-cluster scratch db is one connection-string typo away
  from the real thing.

### Test suite cannot run end to end — four independent causes (August 2026)

**Impact:** nobody can complete a full run, which is why **19 deterministic failures accumulated
invisibly** in the motion/shot area alone. This blocks regression coverage for the CPU identity
wiring and rotation work that comes next. It is a workstream, not a pre-commit step.

**1. Three files do not import.** `pytest --collect-only` → **2,274 collected, 3 errors**:
`tests/test_final_turn_entry_pass_chain.py`, `BackEnd/tests/test_mask_validation.py`,
`tests/test_shared_defense.py`. Example: `ImportError: cannot import name
'_append_final_turn_entry_pass_if_needed' from 'BackEnd.engine.skeleton_step_emitter'` — the
emitter's private API moved and these were not updated. Their tests never run and never report
as failures. Same failure mode as the orphaned-function sweep: code moved, the referencing thing
did not.

**2. Ten tests vary run to run, from TWO independent sources.** Measured over 5 identical runs per
arm: **22, 23, 23, 23, 20** vs **26, 21, 23, 22, 22** — same code both times. Flaky:
`test_motion_moment.py` (6), `test_motion_dynamic_resolver.py` (3), `test_motion_pass_lane.py` (1).
  - `BackEnd/utils/sim_random.sim_rng` seeds from OS entropy when unseeded (by design). Tests that
    exercise the walk without seeding get a different stream each run.
  - The **stdlib** `random` module is used directly in `BackEnd/api/gameplan_routes.py`
    (`populate_team_plays`, `populate_scouting_data`) — those draws are NOT on the isolated sim
    stream, so seeding `sim_rng` alone is insufficient.
  - A third factor, `PYTHONHASHSEED`, is filed separately below — it is not only a test problem.

**3. At least one test hangs forever.** `tests/test_defensive_pressure_all_scenarios.py` stalls
after 2 failures and produces no further output — observed 37 minutes with zero progress, at 19%
of the run. Confirmed **pre-existing** (HEAD hangs at the identical point, not caused by the
focus-emphasis change). `pytest-timeout` is **not installed**, so a hang is a wall rather than a
reported failure.
  - ⚠️ **The hang inventory is UNKNOWN.** We only know of this one because we never got past it.
    There may be more beyond 19%.

**4. `pytest.ini` sets `addopts = --maxfail=2`,** so a default invocation aborts after the second
failure — which, given 19 deterministic failures, means a default run shows almost nothing. Needs
`--maxfail=999 --continue-on-collection-errors` to see the real picture.

**Suggested order (when authorized):** install `pytest-timeout` and run with `--timeout=60
--timeout-method=thread` to convert hangs into failures and produce the hang inventory in one pass;
then fix the 3 imports; then seed both RNG streams via an autouse conftest fixture; then revisit
`--maxfail`. Only after that is the 19-failure backlog worth triaging.

### `PYTHONHASHSEED` reaches simulation behaviour — game results depend on an unrecorded value (August 2026)

- **Finding:** with `sim_rng` AND the stdlib `random` both explicitly seeded per quarter, repeated
  runs of the same sim still produced different results — until `PYTHONHASHSEED=0` was set, after
  which two runs were **bit-identical** (results and RNG draw counts alike).
- **Implication:** something on the sim path iterates a `set` or `dict` of strings in an order that
  reaches behaviour. Python randomises string hashing per process by default, so **live game results
  depend on a per-process value that nobody sets, controls, or records.**
- **Why this is not just a test problem:** it means a production game is not reproducible even given
  the same seed, and any seeded investigation is only valid within a single process. It undermines
  SS&S reproducibility guarantees generally.
- **Same class as the pymongo global-stream finding** documented in `BackEnd/utils/sim_random.py`:
  an invisible external input perturbing the simulation. That one was fixed by isolating the RNG;
  this one is still open.
- **Likely fix (when authorized):** find the offending iteration (candidates: any `set` of position
  or player-id strings feeding ordered logic, `_step_locations`, read-map construction, defender
  grids) and impose a deterministic order — `sorted()` at the point of use. Pinning
  `PYTHONHASHSEED` in the runtime would mask it, not fix it, and would not help anyone reading a
  historical game.

### `OUTSIDE_SHOT_SELECTION_MULTIPLIER = 0.55` is the real driver of attack dominance (August 2026)

- **Symptom:** Motion shot types run **~77% attack at NEUTRAL sliders** (2/2/2), and ~90% at
  `attack=4/outside=0`. Measured over 5 matched seed sets, 15 quarters/config.
- **Not the sliders.** Removing team emphasis from the `_weighted_attack_or_outside` type roll
  (so the sliders act only through `_focus_emphasis`) moved the neutral mix by **0.1 points**
  (77.02% → 77.11%) and the 4/0 extreme by only 3 points (92.7% → 89.7%). The sliders were
  symmetric noise on top of an already-lopsided base.
- **Root cause** — `BackEnd/engine/motion_step_decision.py`:
  ```
  attack_score  = (AG + SC)/2                              ~55 for a typical starter
  outside_score = SH * OUTSIDE_SHOT_SELECTION_MULTIPLIER    ~30  (SH ~55, discounted 45%)
  -> attack wins ~65% of type rolls before any emphasis
  ```
  The constant's own comment says it exists to "steer eligible outside players toward drives".
  At 0.55 that thumb is heavy. Raising it toward **~0.8** is the actual lever; it would pull
  neutral attack from ~77% to roughly the mid-60s and bring the 4/0 extreme down with it.
- **⚠️ NOT just a shot-mix dial.** Attack decisions are what generate contact: they route through
  `_create_attack_drive_shoot_steps`, whose drives can end in foul / charge / dead-ball turnover.
  Roughly **two-thirds of attack decisions never become shots** (decision-level attack ~80% vs
  final-shot attack ~25%). So changing this constant moves **foul rate, free-throw rate and
  turnover rate**, not only the inside/attack/outside split.
- **Owner:** belongs with the shot-tuning pass (see `project_shot_system_tuning`), NOT with the
  focus-slider work. Needs its own before/after across those four rates, and it will interact
  with the 3PT-rate calibration.

### MEASURED AND REJECTED: NG pull/return hysteresis pair (August 2026)

Implemented, swept, head-to-head'd, then **stripped** rather than left as inert plumbing —
this project has surfaced four orphaned mechanisms already, and shipping the scaffolding for
a rejected one is the same pattern. Recording the results so the work isn't lost.

**What it was:** replace the single `NG >= 0.80` eligibility gate with a pair — a player ON
THE FLOOR stays eligible until NG < PULL, and once benched cannot return until NG >= RETURN.
The late-game relaxation (0.64 in the final 4:00 of Q4/OT) composed multiplicatively
(factor 0.64/0.80) against BOTH ends, so `(0.80, 0.80)` reproduced the old behaviour exactly.

**Sweep (16 games per pair, w = 1.0 so only the gate moved):**

| pull/return | star min% | stint mean | subs/rebuild | floor NG mean | floor NG min |
|---|---|---|---|---|---|
| 0.80/0.80 (control) | 40.5%* | 1.21 | 4.01 | 0.879 | 0.600 |
| 0.75/0.85 | 40.5%* | 1.41 | 3.37 | 0.852 | 0.520 |
| 0.70/0.90 | 40.5%* | 1.46 | 3.21 | 0.842 | 0.510 |
| 0.65/0.90 | 41.4%* | 1.58 | 2.94 | 0.824 | 0.450 |
| 0.60/0.95 | 41.0%* | 1.71 | 2.68 | 0.805 | 0.420 |

\* these star-minutes figures are VOID — see the metric warning in
`06_Gameplay_Systems/CPU_Team_Rotation_System.md`. The *relative* flatness across pairs is
still informative (the defect was constant across arms); the absolute level is not.

**Head-to-head vs (0.80, 0.80), 32 games each, both directions:**

| pair | record | win% | SE | mean margin |
|---|---|---|---|---|
| 0.75/0.85 | 14-18 | 43.8% | +/-8.8 | **-1.81** |
| 0.70/0.90 | 15-17 | 46.9% | +/-8.8 | **-1.66** |
| 0.65/0.90 | 16-16 | 50.0% | +/-8.8 | -0.56 |

**Verdict — rejected.** Three findings:
1. **Churn improves genuinely** — substitutions per rebuild fall 20-33%, mean stint length
   rises 41%. This is the only real benefit, and it is cosmetic.
2. **It costs about a point a game.** No pair beat the control; all three margins are
   negative. Mechanically unsurprising: holding a tired player past PULL is by construction
   fielding someone worse than the best available alternative.
3. **It does not move star minutes at all** (flat across every pair). Star minutes are an
   equilibrium of the fatigue economy — on-floor decay ~0.015/possession
   (`_ND_DECAY_TIERS`) against bench recovery ~0.009/possession
   (`phase_resolution.py` bench recharge) — not a property of the thresholds. Widening
   hysteresis buys a longer stint and pays for it with a proportionally longer rest.

**When to revisit:** only if the FATIGUE ECONOMY changes. In a slower-decay world long
stints may arise without paying a point a game for them, at which point hysteresis might be
unnecessary rather than merely unprofitable. **Do not revisit by searching for a better
threshold pair** — the sweep covered 0.60-0.80 pull against 0.80-0.95 return and the shape
was monotonic throughout: more hysteresis, less churn, more exhaustion, same minutes.
