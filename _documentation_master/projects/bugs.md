##Bugs
1. Getting some double rebounds (SFX, maybe animaiton, not sure about logic)
2. Improve FB Outlet Pass denied animation
3. Latest Sentry bug report
4. Week 1 upcoming games card during training

##Playtest Launch / In Progress
1. Steam Video
-----
2. PvP sim -- playtest post-launch / immediate parallel task
3. Downloadable game vs Live game dynamics
4. College and Pro setup
5. UX upgrade -- particularly around tabs and scrolling and back buttons (relative to browser back button), load screens
6. UI Design upgrade, what is this game's personality?
7. Wire Stripe into site
8. Evolve animation from annoying to rewarding


##Full Product Perfection
1. Training Camp News Report
102. Team court images
108. Message board
113. Bring logic to screens
114. Better individual player defense stat tracking
116. User account -- link X & Facebook?
127. Get Aggressive / Get Conservative settings and Playcall Center buttons
128. Add a badass design appraoch to New Stories
129: Loose Balls!
131. Centralized Turn Transition Helper / System
137. Watermark free version of player headshots
139. Mod system for uploading custom leagues
140. Better logic and impact to player EM
142. Logic and impact for play scores
143. Nail player plumbing for Mod Teams
144. Nail mod team balance, league-wide

199. Mobile
200. PvP live

##Continuous Evolution (base is built)
1. In-Game SFX: Deny, Picked Up His Dribble, No Good/Missed
2. Advanced Topics tutorials
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

## Resolved — stale Final Turn test import (found 2026-08-04, fixed 2026-08-11)

`test_final_turn_entry_pass_chain.py` was repointed from the retired
`_append_final_turn_entry_pass_if_needed` helper to the current
`_prepend_final_turn_handoff_if_needed` path. Its monotonic/no-self-loop contract remains
covered. The separate `roll_anchor_clock` debt was resolved earlier.

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

**1. Resolved 2026-08-11 — stale imports no longer block collection.** Final Turn
coverage now targets the current handoff helper, and shared-defense symmetry coverage now
targets the unified `get_defender_coords` API instead of the two deliberately retired
assignment helpers. Full local collection reaches 2,337 tests with the image-mask test
excluded only because the local virtualenv predates the already-declared NumPy/SciPy
requirements; hosted CI installs both from `requirements.txt`.

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

#### PARTIAL FIX + method to finish it (August 2026)

**12 genuine hash-order dependencies found and fixed.** Each was a raw `set` iteration whose
order reached RNG draw ORDER, so every subsequent draw in the game shifted:

| file | what |
|---|---|
| `engine/attack_drive_clearance.py:1012` | `for off_pos in perimeter_moved` — set from `_apply_perimeter_relocations`; loop consumes `player_read` + `get_defender_coords` draws per element. **The primary site.** |
| `models/animator.py:1294` | `for position in all_positions` — set; sets `offensive_animations` insertion order, which flows into zone overlap resolution |
| `engine/dynamic_hct.py:1162` | `backcourt` was a set literal → now a tuple |
| `engine/dynamic_hct_step_emitter.py:273`, `utils/shared.py:2543`, `utils/transition_bridge.py:312`, `utils/stat_updater.py` ×4, `utils/playbook_weights_utils.py:245`, `models/training_execution_v2.py:268` | raw set iteration, now `sorted(..., key=str)` |

**Causally confirmed**: the first divergence between hash worlds moved 9,051 → 23,677 →
31,023 draws as sites were fixed, and `PYTHONHASHSEED` 0 and 7 now produce **identical** games
(they did not before).

**STILL NOT FIXED.** Seeds 1 and 2 still diverge. On the identity-ON arm, 96 team-games, the
between-seed spread is **points/tg 69.22–70.58 and FCP foul-outs/tg 1.04–1.35** — comparable
to the effects being measured. **The instrument is still not trustworthy for effects of this
size.** Until it is, pin `PYTHONHASHSEED` for every arm of every comparison.

**Next site**: the OREB rebounder selection. Trace shows identical RNG state through draw
31,022, then `mo_shot_roll` takes a different branch (`player_momentum.py:54` vs `:57`) via
`shot_manager.calculate_shot_score` ← `shared.resolve_offensive_rebound` ← 
`turn_manager.resolve_offensive_rebound_turn:5252`. Same draws, different rebounder — so the
selection is order-dependent, most likely a `max()`/`min()` tie broken by iteration order
rather than a raw set iteration (the static scan for those is now clean).

**Method to continue** (`scratchpad/hashfind.py` + `nextdiv.sh`): wrap every `sim_rng` method
to record the caller's `file:line` per draw; run one game under two hash seeds; diff the
call-site sequences to find the first differing draw index; re-run with deep stacks in a
±2 window around it. That names the function in two passes.

#### RESOLUTION: pinned structurally, remaining hunt PARKED (August 2026)

**Decision: stop chasing sites; fix the failure mode instead.** Twelve fixes with causal
confirmation did not shrink the between-seed spread, and the static scan for raw set iteration
is now clean while divergence persists — so the remaining sites are subtler and possibly
numerous. Pinning, meanwhile, works perfectly. Every false conclusion came from an UNPINNED
run, so the defect to fix is **"requires remembering."**

| where | how |
|---|---|
| measurement harnesses | `BackEnd/utils/repro.pin_hash_seed()` as the first statement. `PYTHONHASHSEED` is read at interpreter startup, so it cannot be set from inside a running process — the helper **re-executes** the interpreter with it set. A harness that cannot be run unpinned cannot produce another false result. |
| production | `export PYTHONHASHSEED=0` in `start.sh`. Does not help with games already played, but from now on a reported game can be replayed. |

An explicit `PYTHONHASHSEED` in the environment is **respected, not overridden** — deliberately
varying it is how you measure between-world spread. Only the unset (and `"random"`) case is
pinned. If the re-exec fails to take, `pin_hash_seed` **raises** rather than continuing
unpinned.

`repro.py` is loaded BY PATH in the harness preamble, not imported as `BackEnd.utils.repro`,
because `BackEnd/utils/__init__.py` pulls in `stat_updater -> db` and the re-exec would
otherwise open a Mongo connection twice. Pinned harnesses: `perf_sim_baseline.py`,
`eog_measurement_season.py`, `simulate_100_quarters.py`, `s11_framework_baseline_measure.py`,
`eog_db_sweep.py`.

**When to un-park:** only if something specifically needs true hash-independence — e.g. running
measurement arms across multiple workers/processes where a shared pin is not achievable, or a
production incident that turns out to depend on hash order rather than seed. The next site and
the two-pass tracing method are recorded above and remain valid.

### Production games are NOT replayable — the per-game seed is never created or persisted (August 2026)

**TICKET, not fixed.** Pinning `PYTHONHASHSEED` (done, `start.sh`) makes hash ORDER
deterministic. It is **necessary but not sufficient**. A user reporting a strange game still
cannot have it reproduced, and it would be easy to believe otherwise.

**Why.** `cpu_week_pool` derives `seed = None if seed_base is None else seed_base + idx`
(`utils/cpu_week_pool.py:85`, `:127`), and **production passes `seed_base=None`**. In
`_run_franchise_cpu_full_simulation_core` (`api/franchise_routes.py:5205`) the seeding call is
guarded by `if seed is not None:` — so in production `sim_rng` is **never seeded**. It
self-seeds once from OS entropy at import and then runs as one continuous stream across every
game in the process.

So there is no per-game seed to record. The fix is not "log the seed we used" — it is
**generate one per game, seed with it, then persist it.**

**What the fix needs:**

1. Generate a per-game seed in the production path (e.g. `secrets.randbits(63)`), pass it
   where `seed_base + idx` goes today, so each game seeds independently of how many ran before
   it. This also removes the current cross-game coupling inside a worker process.
2. Persist it on the game document alongside the other provenance fields — `sim_seed`, plus
   `training_seed` now that training has its own stream (`utils/training_random.py`), plus the
   `PYTHONHASHSEED` in force and the git SHA (`_eog_band_git_sha()` already computes one from
   `RAILWAY_GIT_COMMIT_SHA`).
3. Add a replay entry point that takes a game document and re-runs it from those values.

**Caveats the fix must respect:**

- `sim_rng` is a plain instance shared across threads (deliberately — a thread-local proxy
  measured +30% per draw, and the engine makes ~82k draws/game). **Replay therefore requires
  single-threaded execution**, as `perf_sim_baseline.py --workers 1` already does. Per-game
  seeding makes multi-process pools reproducible, but not multi-threaded ones.
- Hash-order determinism is only partial — twelve sites fixed, divergence still present, hunt
  parked. Replay depends on the pin staying in place, so `PYTHONHASHSEED` must be recorded per
  game rather than assumed to be 0 forever.
- Games played BEFORE this ships are unrecoverable. No amount of later work reconstructs them.

**Value:** this is the difference between "we pinned the hash seed" and "a user can send us a
game ID and we can watch exactly what they watched." Small change, and the second thing is the
one people will actually ask for.

#### AUDIT — which earlier results were affected

The rule: **arms compared WITHIN one process share that process's hash seed and are valid;
arms run as separate invocations are not.**

| harness | structure | verdict |
|---|---|---|
| `w_sweep.py` | `for w in WS` inside one process | **valid** |
| `read_test.py` | `CONFIGS` looped in-process | **valid** |
| `lineup_analyze.py`, `gates.py` | no per-arm invocation | **valid** |
| `head2head.py`, `lineup_diag.py` | `argv[1]` is games count, single config | **valid** (absolute values are one hash world) |
| `slider_ab.py` | `ARM = sys.argv[1]` — one arm per process | **INVALID across arms** |
| `difficulty.py` | `TAG = sys.argv[1]` — one arm per process | **INVALID across arms** |
| `foul_levers.py` | one arm per process | **INVALID** as originally run; later re-run pinned |

No harness set `PYTHONHASHSEED` internally. The lineup diagnostics and gate sweep are
structurally fine; the slider A/B and difficulty comparisons should be re-run pinned before
being quoted again.

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

### MEASURED, NO EFFECT FOUND: archetype-varying objective weight `w` (2026-08-12)

**The second attempt at archetype-driven substitution, and the second one that does not pay.**

After the hysteresis pair below was rejected, `cpu_identity_design.md` §B3's archetype idea
was redirected from the NG gate to the selector objective weight `w`
(`score = w·static + (1−w)·effective`), which `db_utils.py:176` already names as *"the
intended home for archetype influence (via starter_bench_gap)"*. That redirect was right in
principle — `w` changes who the selector considers better rather than holding anyone past a
gate — but the effect is not there.

**The hypothesis, stated precisely.** `c2570c5aa` swept `w` LEAGUE-WIDE and found lower is
better (every value beat `w=1.0`; >10 effective-talent gap 20.8% → 0.7% going 1.0 → 0.25).
The spec wants `w` to go UP for top-heavy rosters. That is only defensible if the optimum
DIFFERS BY ROSTER SHAPE and the league-wide sweep averaged the difference away. So the test
is not "is high `w` good" — it is **"does the optimum differ by band."**

**Method** (`scripts/lineup_w_conditional_sweep.py`, read-only): within-game pairing — one
team gets `w=0.60`, its opponent `w=0.05`, same seed/venue/opponent, with the high arm
alternating home/away. One observation per GAME (the design is zero-sum, so per-team-game
arms are perfect negatives and a two-sample SE over them is meaningless). Matchups restricted
to a single `starter_bench_gap` band, because the bands are 96/23/9 teams and random pairing
spends ~93% of games where the answer is already known.

| gap band | games | high-`w` margin | SE | \|t\| |
|---|---|---|---|---|
| top-heavy (>19) | 32 | **−1.56** | 2.70 | 0.6 |
| shallow (<13) | 32 | **−1.22** | 2.50 | 0.5 |

**Verdict — no conditional effect.** The spec predicts these bands should have OPPOSITE
signs. They have the same sign, similar magnitude, and differ by **0.34 points — about
one-eighth of a single SE**. Both are consistent with the league-wide result that lower `w`
is better; neither supports varying it by roster shape.

**Honest limits.** 32 games/band cannot resolve a ~1.5-point effect on its own (|t| ≈ 0.5–0.6),
so this does not *prove* no effect. What it does is bound the conditional effect as small and
provide zero support for its existence, against a prior that already measured higher `w` as
worse. Single franchise, week-2 rosters, two `w` arms rather than a full sweep.

**Where `starter_bench_gap` came from.** It is not defined anywhere in the codebase — only
named in the `db_utils` comment. The sweep defines it as the mean over the five lineup slots
of (best static slot rating − second best). Static not effective (it is a roster property,
not a fatigue state); second-best per slot not "the bench" (that is who actually replaces the
starter); mean not max (one thin position should not read as top-heavy). Observed on the
identity league: min 2.0, max 29.2, mean 11.1 — so the spec's 13/19 band edges put **75% of
the league in one bucket** and were evidently cut against a different population, the same
failure as the `RT ≥ 50` bar and the frozen `SIGNAL_SCALE` constants.

**When to revisit:** a different `w` grid is not the answer — the league-wide sweep already
mapped that curve and it is monotonic. Like hysteresis, the case for reopening is a change to
the **fatigue economy**, not a better parameter.

---

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

## Database-safety incident + systemic holes (August 2026)

### `_update_position_ratings` writes a derived cache on every GameManager construction — TICKET, not fixed

- **Finding:** `GameManager.__init__` calls `_update_position_ratings()`, which recomputes
  `position_ratings` from each player's attributes/height/name and **`bulk_write`s them to
  `players`** for every non-franchise, non-synthetic player on both teams
  (`BackEnd/models/game_manager.py:113-121`). **Constructing a GameManager is a database write.**
- **Why it matters:** this made "read-only investigation" false for the entire CPU identity /
  rotation / lineup / motion project. Every sim harness was writing `position_ratings` on each
  game it constructed. On staging that is self-consistent, so it went unnoticed for weeks.
- **The design question (not tonight's work):**
  1. compute in memory, persist **only on change** — would not have helped here, the formula
     genuinely differed;
  2. compute in memory, persist **never**, with an explicit migration owning the stored field;
  3. keep writing, but behind an explicit **read-only / no-persist mode** harnesses opt into.
  Option 2 is cleanest — a cache that self-heals is exactly what makes its staleness invisible.
  Option 3 is the smallest change and would immediately make sim harnesses honest.
- **Supporting evidence:** prod `position_ratings` carries at least three formula generations
  (53.6% match `93737625c`, 39.4% match `a88aa8fcc`, remainder older). Teams hold whatever was
  deployed the last time they played, so the field is unreliable for league-wide analysis.

### `.env.local` resolved against CWD, silently retargeting production — FIXED

- **Was:** `BackEnd/db.py` chose its env file with `os.path.exists(".env.local")`, relative to the
  **working directory**. Any script run from a subdirectory failed to find it, fell through to
  `.env`, and connected to prod. One instance of a class, not a one-off.
- **Incident:** a sim harness run from a scratch directory rewrote `position_ratings` on **192
  prod player documents across 16 teams** with the recalibrated formula, while prod runs a
  pre-recal formula. Deltas up to 38 rating points. Only that field changed — `attributes`,
  `height` and `name` verified untouched.
- **Now:** resolved against the repo root (`Path(__file__).resolve().parent.parent`).
- **Plus a production access guard** in the same file: reaching `gob` requires an explicit
  per-invocation opt-in, `GOB_DB_ACCESS=read` or `=write`, read from the **real process
  environment snapshotted before dotenv load** — so it cannot be armed from a committed `.env`.
  The deployed app is recognised by any `RAILWAY_*` variable. Unrecognised process → refuse at
  import. `aggregate()` is deliberately not blocked in read mode, so `$out`/`$merge` can still
  write; tighten if that becomes a real path.

## EOG leveling pass (August 2026) — follow-ups

### RESOLVED + ESCALATED: the fight / discipline drift owner (August 2026)

**Diagnosed. Two of the three candidates are closed; a bigger one opened.**

**(b) reset/rollover artifact — RULED OUT.** The per-week training delta is SPREAD EVENLY
across all 26 weeks, not spiked. `fight` runs +0.4..+2.0 every week, `discipline` -0.4..-3.6;
the top three weeks hold only 20% and 29% of total movement. Controls
(`offensive_efficiency`, `fb_efficiency`, `shot_threshold`, `team_chemistry`) are equally
smooth, top-3 concentration 15-16% — so §2b is NOT absorbing large one-off EOS/camp writes
into the training column for any attribute.

**Persona coupling — RULED OUT TWICE OVER.** The nudges are equal in magnitude (±1.5 mean) and
fire at 4-of-5 sub-options each way, so they cancel at uniform selection. And they never fire
at all for CPU teams: `auto_train_one_cpu_team` pins `coaching_focus = "player-maximizer-custom"`,
so the archetype is ALWAYS `player-maximizer`. The culture-builder / authoritarian branches are
dead code on the CPU path, and 127 of 128 teams are CPU.

**(a) the CPU reference plan — CONFIRMED OWNER for fight/discipline.** Measured directly via
`auto_train_one_cpu_team(..., dry_run=True)` over 40 teams (all pymongo writes blocked; zero
write attempts):

| attribute | reference plan | §2b inferred | verdict |
|---|---|---|---|
| team_chemistry | -11.7 | -10.2 | ✅ fully explained |
| offensive_efficiency | +7.2 | +7.5 | ✅ fully explained |
| fight | **+16.2** | +27 .. +32 | direction right, ~60% of magnitude |
| discipline | **-24.1** | -35 .. -48 | direction right, ~60% of magnitude |
| **shot_threshold** | **+1.3** | **+51.4** | ❌ **40x GAP — NOT TRAINING** |

The fight/discipline residual is plausibly estimator bias: §2b conditions on BOTH endpoints
unclamped, which progressively drops teams that have drifted to the clamp and leaves only
small-delta survivors (visible as `discipline` decaying -3.55 at wk2 to -0.44 at wk14). That
biases the estimate DOWNWARD, so the true drift is probably larger than either figure.

**Action for fight/discipline:** the owner is the reference plan's drill->team-attr mapping
(`training_execution_v2.py:607-617` — discipline draws 0.25x from four categories, fight 0.5x
from two). Retune there, not in the EOG bands.

### ⚠️ RETRACTED: "shot_threshold has an unidentified writer" — it was a measurement error

**There is no mystery writer.** The claim came from a dry-run measurement taken against
END-OF-SEASON state where **123 of 128 teams sat at the 200 ceiling**, so every training gain
was clamped to zero and the plan appeared to produce +1.3/season. Re-measured with attributes
reset to mid-range, the SAME reference plan produces **+60.5/season** against §2b's +51.4 —
fully explained by training. Only three writers touch team attributes (EOG apply, CPU
auto-train, user training) and that is correct.

Also note: the "nothing in week 1" signal that motivated the hunt is an artifact. The training
delta is computed as `pre[w] - post[w-1]`, so week 1 has no value BY CONSTRUCTION. It is not
evidence of a state-dependent writer.

### ⚠️ THE REAL FINDING: §2b systematically UNDERSTATES training for clamped attributes

Reference plan measured two ways over 40 teams (`dry_run=True`, writes blocked, zero attempts):

| attribute | from LIVE (railed) state | from UNCLAMPED state | §2b inferred | ratio |
|---|---|---|---|---|
| **team_chemistry** | -11.0 | **-93.6** | -10.2 | **9.2x** |
| **discipline** | -17.6 | **-91.6** | -48.1 | **1.9x** |
| **shot_threshold** | +5.9 | **+60.5** | +51.4 | 1.2x |
| fight | +26.0 | +37.1 | +32.0 | 1.2x |
| pt_efficiency | +6.5 | +9.1 | +7.3 | 1.2x |
| offensive_efficiency | +7.2 | +7.8 | +7.5 | 1.0x |
| defensive_efficiency | +11.0 | +7.8 | +7.6 | 1.0x |
| fb_efficiency | +7.8 | +6.5 | +7.4 | 0.9x |
| rebound_modifier | +0.5 | +0.2 | +0.2 | 1.0x |

§2b conditions on BOTH endpoints unclamped, so for an attribute whose population is pressed
against a clamp it measures only the survivors — the teams that have not yet railed, which are
precisely the ones with small deltas. **The unconstrained attributes agree within 10%; the
railing ones are understated by up to 9x.**

**This invalidates part of the leveling pass.** EOG was tuned against the inferred column, so
for the four clamped attributes the resulting combined drift is much worse than the tuner
reported:

| attribute | tuner said | with TRUE training pressure |
|---|---|---|
| team_chemistry | +0.8 | **≈ -83** |
| discipline | -34.2 | **≈ -78** |
| shot_threshold | +48.3 | **≈ +57** |
| fight | +32.0 | **≈ +37** |

The seven unconstrained attributes are unaffected and their tuning stands.

**Which number is the right target?** Neither alone. The unclamped figure is the training
PRESSURE; the inferred figure is the movement REALISED among teams that have not railed. EOG
should be tuned against the pressure — if it is not, the attribute rails, and a railed attribute
carries no information regardless of what the realised drift looks like. Update
`TRAINING_PER_SEASON` in `scripts/eog_band_tuner.py` to the unclamped column and re-tune those
four.

**But the pressure is too large to absorb in EOG alone.** team_chemistry at -93.6/season on an
18-point range cannot be offset by any sane band — EOG would need +3.6/game. The training side
has to come down for team_chemistry and discipline; only then is EOG re-tuning meaningful.

### (superseded by the entry above) Original fight/discipline ticket

**Measured on the identity season:** `fight` **+32.0**/season and `discipline` **−48.1**/season
from TRAINING, against EOG contributions of **+0.6** and **+14.0**. Training dominates both, so
their EOG bands were left DELIBERATELY UNTUNED in the leveling pass — compensating via EOG would
require perverse bands (see below). Revisit the bands only after this is settled.

**The persona coupling is NOT the cause — this was checked and ruled out.**
`_apply_player_training_points` (`training_execution_v2.py:745-767`) looks asymmetric but is not:

| nudge | fires when | sub-options hit |
|---|---|---|
| `fight` +1..+2 | culture-builder, sub != `culture-builder-teamwork` | 4 of 5 |
| `discipline` −2..−1 | culture-builder, sub != `culture-builder-confidence` | 4 of 5 |
| `discipline` +1..+2 | authoritarian, sub != `authoritarian-teamwork` | 4 of 5 |
| `fight` −2..−1 | authoritarian, sub != `authoritarian-rebounding` | 4 of 5 |

Equal magnitudes (±1.5 mean), equal firing rates, and `generate_random_coaching_focus` picks
uniformly from 19 options. Expected net contribution to both attributes is **zero**. The
drill mapping is symmetric too — `discipline` draws 0.25x from four categories, `fight` 0.5x
from two; both total 1.0x.

**Direct measurement contradicts the season figures.** Running `execute_training` 200x with
`generate_random_training_allocations(24)`:

| focus | Δfight/season | Δdiscipline/season |
|---|---|---|
| none | −4.5 | +4.9 |
| random | −10.8 | +3.9 |

**Opposite sign and an order of magnitude smaller** than the season's +32 / −48.

**Two candidates remain, neither yet confirmed:**
1. **CPU auto-train does not use random allocation.** `auto_train_one_cpu_team` trains a
   "coaching-quality REFERENCE" plan (see the comment above `_AUTOTRAIN_PLAYER_ATTRS` in
   `franchise_routes.py`). 127 of 128 teams in the season are CPU, so the measured drift
   reflects that reference plan, not the random path measured above. **Measure the reference
   plan's per-attribute effect first — this is the most likely owner.**
2. **The "training" figure is INFERRED, not measured.** Report §2b derives it from
   unclamped week-to-week `pre`->`post` gaps in the band log, so it attributes EVERY
   non-EOG change to training — including anything else that writes team attributes between
   games (EOS, training camp, rollover). Verify the attribution before trusting the number.

**Why not just tune EOG around it:** `fight` EOG is structurally zero (every game has exactly
one winner, so win +1 / loss −1 nets to 0 league-wide); offsetting +32 would require losses to
hurt far more than wins help, i.e. every team drifts down over a season. `discipline` would need
EOG ≈ +2.04/game, which on a ±20 range rails the ceiling in about six games.

### The two INTERIM constants

`FG_PCT_MID/HIGH` and `OFF_CONC_REWARD/MIDDLE` are cut against inputs already scheduled to
change (shot calibration; the playbook generator's 20% concentration cap for 4+ set plays).
The dependency is recorded beside each constant in `constants/eog_attr_bands.py` — what it was
cut against, its measured value at cut time, and that a material shift requires re-running
`scripts/eog_band_tuner.py`. When either input moves, these cuts invert the problem.

### `rebound_modifier` init 0.2 -> 0.5 — NOT DONE

Not a band, so outside the tuner's model. With the new ladder, rebound drift is +0.1/season on
a 0.0-1.0 range, so 0.5 gives symmetric headroom and should stop the week-3 flooring (93 teams).
Confirm against a short run rather than assuming.

## ⚠️ MEASUREMENT FRANCHISES ARE SEEDED BY PROD CODE, MEASURED BY LOCAL CODE (August 2026)

**The structural hazard behind several hours of confusion, stated once so it is not
rediscovered.** A measurement franchise is created through the UI, which talks to the
**deployed Railway backend running `main`**. The season is then driven **in-process by local
`develop` code**. So every value seeded at creation comes from prod, and everything computed
during the run comes from local. Anything changed since the last deploy **seeds wrong,
silently, and looks like data rather than an error.**

`main` is currently **158 commits behind `develop`**.

### Audit: what differs (prod `main` -> local `develop`)

| surface | prod (main) | local (develop) | consequence for a measurement franchise |
|---|---|---|---|
| **`position_ratings.py` RT model** | pre-recalibration | recalibrated | **100% of FPD players carry old-formula `position_ratings`, median delta 24, max 55.** Baked in at creation and NOT recomputed for franchise mode (`_update_position_ratings` skips `is_franchise`). Feeds `projected_starting_five` -> identity signals -> starter strength, and every lineup decision. |
| **`player_generator.py`, `recruit_generator.py`** | ABSENT | present | prod builds rosters by a different path; the player population itself may differ |
| **`TEAM_ATTR_CLAMPS` core-8** | ±10 | ±20 | prod-written attributes live in HALF the range local code assumes |
| `team_chemistry` init (franchise) | `randint(7, 10)` | `randint(8, 11)` | 21% of the league born on the 7 floor |
| `rebound_modifier` init (franchise) | 0.2 | 0.5 | floors 93/128 teams by week 3 |
| `eog_attr_bands.py` | ABSENT | present | prod has no band configuration at all |
| `team_identity.py`, `franchise_identity.py` | ABSENT | present | prod has no CPU identity |
| `TEAM_ATTR_RANGES["rebound_modifier"]` | (0.0, 0.4) | (0.0, 1.0) | no practical difference — franchise init sets the value explicitly |
| `init_team_attributes` single-mode rebound | `TEAM_ATTR_RANGES` (= 0.0-0.4) | literal 0.0-0.4 | identical behaviour |

### Before the next measurement season, do ONE of

1. **Deploy `develop` first**, so seeded and measured code agree. Cleanest.
2. **Normalise after creation** — a setup script that overwrites every seeded value local code
   would produce differently, run before week 1. This is what was done ad hoc for
   `rebound_modifier` on the verification franchise (all 128 FTDs set to 0.5). It must also
   recompute FPD `position_ratings` with the local formula, which was NOT done.
3. **Provision locally** rather than through the UI.

### Standing caveat for the identity and verification seasons

Both were UI-created, so BOTH carry prod-formula `position_ratings`. They are therefore
consistent WITH EACH OTHER — the band thresholds cut against the identity season apply to the
verification season — but neither matches what local code would generate, and neither will
match production once the recalibration deploys. **The thresholds will need re-cutting after
that deploy.** Re-running `scripts/eog_band_tuner.py` against a post-deploy season is seconds;
the trap is not noticing it is needed.

## DEPLOY CHECKLIST — develop -> main (prepared 2026-08-11)

`main` is 158 commits behind. Testers are on ±10 clamps, no CPU identity, and
pre-recalibration attributes. No migration path is needed: users are told to abandon
existing franchises and start new ones.

| # | step | notes |
|---|---|---|
| 1 | **Back up prod collections** | DONE — `~/gob-measurement-archive/db_backups_predeploy/`, checksummed, reload-verified. `gob.players_backup` is NOT a usable rollback (stale; attributes differ on 1440/1536). |
| 2 | **Merge develop -> main** | code half |
| 3 | **Copy `players` + `recruit_sets`** staging -> prod | data half. NOT the skeletons — see below. |
| 4 | `GOB_DB_ACCESS=write` in Railway | redundant signal for the prod guard; `RAILWAY_*` alone also satisfies it |
| 5 | CSP: allow `fonts.googleapis.com`, `www.googletagmanager.com` | new external hosts |
| 6 | Site callout: abandon current franchises | |
| 7 | **`scripts/verify_deploy.py`** | proves the deploy took — see below |

**ORDERING IS BACKUP -> MERGE -> COPY, not copy -> merge.** New code reading old data is a
known-good combination — both measurement seasons ran 26 weeks on exactly that (local code
against prod-formula ratings). OLD code reading NEW data is untested: prod's current build
would be handling a `recruit_sets` 50% larger than it expects.

### Do NOT copy the skeletons

`fcp_skeletons` / `hct_skeletons` hash differently across databases but are **identical except
for `_id`** — every coordinate matches. Copying would churn prod for no benefit. **Heuristic
worth keeping: same byte size + different hash usually means metadata; a real content change
moves the size.** `recruit_sets` moved 146 KB -> 356 KB, and that one is real.

### `recruit_sets` 300 -> 450 is INTENTIONAL

Deliberate regeneration (`1277580c6`, 2026-08-08): 150 added recruits plus the `entry_tier` /
`position_intent` / `potential_factor` / `has_portrait` fields. It is a balance change riding
along with the attributes deploy — 50% more recruits available — and should be stated in the
callout, not discovered.

⚠️ **Prod's document claims `version=2` but holds the 300-recruit content with none of the
regen fields.** A version check would pass on stale data; only a content checksum catches it.

### Post-deploy verification — `scripts/verify_deploy.py`

Nothing else on the list confirms the deploy took, and silent divergence is the failure being
closed. `/health` now reports `commit`, `hash_seed` and `db_access` so the running build is
answerable from outside.

    scripts/verify_deploy.py --health-url https://<prod>/health   # A: build
    GOB_DB_ACCESS=read scripts/verify_deploy.py --data            # B: data (prod URI)
    scripts/verify_deploy.py --franchise-id <id> --delete         # C: seeding

C needs a throwaway franchise created in the UI (creation requires an authenticated session,
which the script deliberately does not embed) at **week 1, unplayed** — training moves the
seeded values immediately. It checks identity persisted, sliders varying, `rebound_modifier`
0.5, `team_chemistry` 8-11, `shot_threshold` 80-90, core-8 clamps ±20, then deletes the
franchise and its FTD/FPD/FRD rows.

The data check was negative-controlled against prod BEFORE the deploy and correctly FAILED on
both collections — it detects a stale copy rather than merely returning green.


## EOG band logging in PRODUCTION (August 2026)

Enabled so tester franchises produce the re-fit basis for `shot_threshold`. Those seasons are
the first ever run under the new bands, and they generate data in the region the model cannot
see — the fit behind the current calibration has n=256 at S=100-119 against n=1008 at 80-99.

### Why Mongo, not the file sink

`GOB_EOG_BAND_LOG=1` writes JSONL to a local path. **In production that produces nothing
retrievable**: Railway's container filesystem is ephemeral and `railway.json` declares no
volume, so the file dies on the next redeploy, each replica writes its own partial, and no
endpoint serves it. The default path is relative, inheriting the same CWD-relative hazard that
sent a sim harness at production.

    GOB_EOG_BAND_LOG=mongo            # off | file (local harnesses) | mongo (production)
    GOB_EOG_BAND_FRANCHISES=a,b       # OPTIONAL RESTRICTION — unset/empty logs EVERY franchise
    GOB_EOG_BAND_TTL_DAYS=90          # retention

Logging every franchise by default is deliberate: tester franchises are created whenever, so
naming ids in advance would mean discovering which to log only after the season is half gone.

### Cost — measured, not estimated

| | |
|---|---|
| row size | 379 bytes JSONL / **258 bytes BSON** |
| franchise-season | 36,608 rows = **9.0 MiB** in Mongo |
| extra input computation | 0.026 ms/game — **0.001%** of a CPU week |
| Mongo writes, batch 500 | **3.96 ms/game** = 0.25 s on a ~160 s week (**0.16%**) |

Batch is 500, not 50: each `insert_many` is an Atlas round-trip (~45 ms), so batch 50 cost
~20 ms/game. `complete_week` flushes at week end and an `atexit` hook flushes on shutdown, so
a hard crash loses at most the current week's tail.

### Extraction

    GOB_DB_ACCESS=read scripts/eog_band_export.py --list
    GOB_DB_ACCESS=read scripts/eog_band_export.py --franchise-id <id> -o out.jsonl
    scripts/eog_band_tuner.py out.jsonl --validate --live

`--list` shows rows, weeks and whether a season is complete (26 weeks / 36,608 rows). Verified
round-trip: 1,408 rows through Mongo and back came out **byte-identical**.

⚠️ **`--validate` must use the config that PRODUCED the log.** There are now three generations
(pre-leveling, post-leveling, post-shot-retune) and validating against the wrong one reports
mass "drift" that is really a config mismatch — the verification log scored 8 of 11 attributes
as mismatched against `AS_LOGGED`, and 11 of 11 clean against its own config. `--validate` now
honours `--config` and `--live`.

### What tester data can and cannot answer

~99% of rows still come from uniform-reference-plan CPU teams — only 1 of 128 teams in a
franchise is the user's — so the sample is not meaningfully contaminated by deliberate human
training. The real distinction is which QUESTION the data answers:

* **The FG%-vs-shot_threshold slope fit is VALID regardless of training.** It is a property of
  the engine and rosters — what FG% a team produces at a given threshold — and training does
  not enter it. This is exactly the re-fit the `shot_threshold` calibration needs.
* **The band-POSITION calibration is NOT valid**, because it depends on the training drift the
  neutral band must offset (+56.4/season measured on the uniform plan). A league with human
  training has a different balance point.

So tester seasons answer the question we need and not the other one. Re-derive the slope from
them; do not re-derive the training constants from them.

### CPU strategy still derives from a THIRD starting-five picker (August 2026) [CODE-CLEANUP]

The display surfaces were synced to the game's selector in August 2026 — FCC Scouting Report
tab, team roster pages, training report, practice-squad team and tournament scouting all now
run `db_utils.projected_starting_five_from_payload`, the exact max-weight assignment autoset
uses at tip (`06_Gameplay_Systems/CPU_Team_Rotation_System.md` §6).

**`team_identity.projected_starting_five` was deliberately NOT re-pointed.** It is a separate
**greedy** fill on raw `position_ratings`, and it feeds eight signals → vision pair → strategy
sliders → `ftd.identity`. So every CPU team's game plan is still derived from a five that is
not the five it fields.

**Why it was left alone — this is the whole ticket.** `SIGNAL_SCALE`,
`RESIDUAL_SLOPE_VS_STRENGTH` and `STARTER_STRENGTH_MEAN` in `team_identity.py` are FROZEN
constants calibrated once against 128 measured teams **using the greedy five**. Swapping the
picker changes `starter_strength` and shifts every residualised signal off its calibrated
mean. Vision assignment across the league would drift by an unmeasured amount, silently,
because the scale would no longer mean what it was calibrated to mean.

**To finish it:**

1. Re-point `team_identity.projected_starting_five` at `solve_best_assignment`
   (`tie_break="stable"` — identity assignment must not consume sim RNG either).
2. Re-derive the frozen constants against a fresh 128-team pool under the new picker.
3. Bump `CONSTANTS_VERSION` so `ensure_franchise_identities` reassigns existing franchises
   rather than reusing pairs derived under the old scale.
4. Re-run the week-1 measurement gate (`franchise_identity_summary`) — vision distribution
   and slider variance. Zero variance means the treatment is not active.

**Not a perf item.** 128 teams × a 32-state DP once per season is nothing. The cost is the
measurement pass, not the compute.

**Trigger to do it:** the next time the identity constants are being re-derived anyway. Doing
it standalone means paying for a full recalibration to fix a consistency defect no user sees
directly.

## Sunset: `/team-roster/{team}` (removed 2026-08-17)

Removed the route, its 8 Jinja templates, the 8 "In Development" sibling pages, the
dev-only `/team-roster/` static-redirect entry, and `tests/test_team_roster_page.py`.

Why it went rather than being brought in line with the attribute-tile work:

- **Zero inbound links** anywhere in the repo — reachable only by typing the URL.
- **Wrong data source.** It read `players_collection` (the universal player pool), not
  franchise player data, so the same team showed *different numbers* than
  `team-roster-view.html`.
- **Already dead in development.** The dev middleware redirects any `/team-roster/*`
  path to `/static/...` before routing (`api.py`, static_dirs), so the page only ever
  rendered in production. That is likely why its data source drifted unnoticed.
- **No auth.** The route took no `Depends(get_current_user)` while every other roster
  surface is behind auth.

Residual risk accepted: an external bookmark or link would now 404. If that surfaces,
the fix is a 301 to `/team-roster-view.html` rather than restoring the page.
