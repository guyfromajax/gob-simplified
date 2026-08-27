# Animation Cleanup — Trace Findings

**Status:** Assessment complete 2026-08-27. Companion to `animation_cleanup_brief.md` (symptoms/references).
**Verdict:** No overhaul needed. The missing 30% concentrates in **3 root causes**, not 30 bugs.

---

## 1. Verdict — keep the baby

The good 70% and the bad 30% share the same renderer. Everything the brief calls out as
*feeling good* (rim variability, FT, FLSS, shot-motion variety, the FB jiggle) is
schema-rendered through `animationPlayback.playTurn()`. So the playback engine, the
`AnimationStep` schema, and the UESS contract are **not** the problem — they are the
reason the good parts are good.

The clumsiness is in **what the emitters author into the steps**, not in how the frontend
renders them. That localizes the work to backend step authoring and keeps overhaul risk low.

| Layer | State | Action |
|---|---|---|
| `AnimationStep` schema + UESS contract | Sound | Keep |
| FE `animationPlayback.playTurn()` | Sound | Keep |
| Backend step **authoring** (what's in each step) | Root of all 8 symptoms | Fix |
| FE legacy orchestrators (`turnAnimation`, `fastBreak`) | 10k lines, shrinking | Retire per UESS backlog 14–15 |

---

## 2. Root cause #1 — freeze-by-default (explains 4 of 8 symptoms)

`transition_bridge.build_pass_step()` takes `continuing_targets: Optional[...] = None`.
Its own docstring states the default:

> "Pass over `continuing_targets=None` to freeze everyone except passer/receiver."

**The default parameter value is the bug.** Every step builder must *opt in* to organic
movement; most don't. Frozen players get `action="stationary"`, `destination = start`,
`end_coords = start` — an explicit instruction to stand still.

| Symptom (brief) | Site | Detail |
|---|---|---|
| FB outlet denial: everyone holds, denier moves | `rim_runner_step_emitter._build_outlet_denied_defender_step` | No continuing loop at all. All 9 non-defenders explicitly written stationary. |
| Bat OOB in HCO: only batter moves | `dynamic_hct_step_emitter._build_bat_oob_steps` | Supports `continuing_targets`; HCT dish path passes `None` (`dynamic_hct_step_emitter.py:1516`) |
| Pauses in HCO turns / inbound | `transition_bridge.py:1428` | Comment: "No continuing_targets → other 8 stationary at their step 2 end coords." |
| **FB defenders freeze while offense finishes the turn** | Same mechanism | Defense omitted from continuing targets → offense tweens, defense holds |

### Why the FB freeze has survived 5–6 fixes

Each past fix populated `continuing_targets` at *one call site*. The default stayed
`None`, so every newly-added step builder reintroduces the freeze. It is not a recurring
bug — it is the same bug re-manifesting at new call sites.

### The correct primitive already exists

`rim_runner_step_emitter._initialize_continuing_movement()` (~50 lines) carries unfinished
movement intent from the previous step's `start.destination`, continues only players with
meaningful remaining distance, and clamps via `_interrupted_coord(rate × T)`. It is
correct — and **local to one emitter**.

**Highest-leverage change in this project: invert the default.** Promote
`_initialize_continuing_movement` to a shared builder base; movement continues unless a
builder explicitly freezes someone. Turns a per-call-site discipline problem into a
structural guarantee.

---

## 3. Root cause #2 — geometry-free actor selection (distant steals/fouls)

Not an animation bug. Resolution-layer.

| Function | Defect |
|---|---|
| `phase_resolution.select_foul_player()` :520 | Defensive foul = 60% positionally-matched defender, **10% each to the other four with no proximity term**. ~40% of defensive fouls can be committed by a player anywhere on the court. Matches "some but not all." |
| `phase_resolution.get_stealer_position_from_skeleton_step()` :459 | Takes a `defender` arg and **never reads it**. Reads the *ball handler's* skeleton location string → static `HCO_STRING_SPOTS` table → derives a synthetic on-ball-defender coord. Animates the steal at an idealized defender position regardless of who stole it. |

**Answer to the brief's open question:** it is *both* — wrong assignment (no geometry in
selection) *and* wrong animation (synthetic coords instead of the actor's emitted coords).

Both are the `apply_coords` antipattern: reading a parallel positioning source instead of
emitted step coords. `UESS_System.md` §1 already names this a violation under remediation —
here the doc is right and the code is wrong. No doc update needed; code must conform.

---

## 4. Root cause #3 — no shot-release timing model

There is no "when does he shoot" control to tune. Shot timing is a **byproduct**:

1. `motion_step_decision` returns `SHOOT` at some skeleton step.
2. Step T = traversal time to the shot spot.
3. Floored at `HCO_STEP_T_FLOOR_GAME_SECONDS = 0.5` game-sec (175ms wall).

Nothing anywhere expresses *catch-and-shoot* vs *hold two beats, then rise*.

The FE hook already exists — `releaseShotOnShooterSettle` fires the ball the instant the
shooter's tween settles (`animationPlayback.js:1283`). Missing piece is **backend intent**:
a shot-release mode on the shot step. Additive, not a refactor.

---

## 5. Hard-coded pause inventory (for review)

1 game-second = **350ms** wall clock (`clockSecondMs`). Backend constants written `X / 350.0`
mean *X ms of wall clock*.

### 5a. DEAD — knobs that control nothing

| Knob | Value | Why dead |
|---|---|---|
| `FAST_BREAK_END_PAUSE_MS` | 3000 | Exported, **zero importers repo-wide** |
| `possession.targetFrameMs / minFrameMs / maxFrameMs / minDurationScale / maxDurationScale / maxPassDurationMs` | 320/120/900/0.35/6/750 | Sole reader is `PossessionRunner`, which is hardcoded off (`debugFlags.js:57`). Also shadowed by a **duplicate `possession` key** in `animation_config.js` (lines 11 & 145, 122 & 205) — last-wins, so these are `undefined` even if revived |
| `outletSetup.playerMoveMs`, `freeThrow.lineupMoveMs`, `fastBreak.sprintSpeed` | 800/800/1.5 | Zero consumers |

### 5b. LIVE — frontend (`animation_config.js`)

| Knob | ms | Notes |
|---|---|---|
| `shot.rimHoldMs` | 1000 | Ball sits at rim after make/miss (HCO) |
| `fastBreak.rimHoldMs` | 1000 | Same, FB |
| `offensiveRebound.pauseMs` | 1000 | `turnAnimation.js:5442` |
| `finalTurn.holdFinalShotMs` | 2000 | Quarter-end hold |
| `finalTurn.holdClockOutMs` | 1800 | |
| `freeThrow.resultAnnouncementHoldMs` / `makeRimHoldMs` / `missAnnouncementHoldMs` | 600 each | 2× standard freeze, intentional |
| `fastBreak.agDriftSharedPhaseMinMs` | 520 | Anti-warp floor |
| `rebound.attachDelayMs` | 500 | Possession-secured delay |
| `fastBreak.defensiveStopHoldMs` | 500 | |
| `freeThrow.shotMs` | 500 | |
| `freeThrow.shooterPrepMs` | 400 | |
| `ANNOUNCEMENT_FREEZE_HOLD_MS` | 300 | Mirrored backend + frontend |
| `rebound.playerMoveMs`, `kickout.duration`, `outletSetup.passMs`, `freeThrow.rimHoldMs` | 300 | |
| `fastBreak.passMs` / `outletMoveMs` | 250 / 300 | |
| `inbound.holdAfterPlaceMs` | 200 | SIP only; BIP dropped May 2026 |
| `pass.duration`, `steal.duration` | 150 | |

### 5c. LIVE — frontend raw timers (not in config)

| Site | ms |
|---|---|
| `fastBreak.js:1792` | 650 |
| `openingTip.js:283` | 300 |
| `ballManager.js:608,660` | 200 |
| `batOobAnimation.js:149,151` | 130 |
| `animateStep.js:530` | 100 (`delay:`) |
| `openingTip.js:196` | 100 |
| `fastBreak.js` ×6, `ballManager.js` ×2 | 45–50 (frame-yield, benign) |

### 5d. LIVE — backend holds

| Constant / site | Wall ms |
|---|---|
| `ft_step_emitter._BOUNCE_HOLD_GAME_SECONDS` | 1000 |
| `dreb_step_emitter.py:240` `hold_ms` | 700 |
| `oreb_step_emitter.py:359` `hold_ms` | 700 |
| `FUMBLE_WALL_CLOCK_MS` | 660 |
| `QUICK_FOUL_REACHIN_GAME_SECONDS` | 450 |
| `AIRBALL_OOB_GAME_SECONDS` | 400 |
| `ANNOUNCEMENT_FREEZE_HOLD_MS` (many emitter sites) | 300 |
| `BOUNCE_STEP_GAME_SECONDS` | 300 |
| `BANK_MAKE_SETTLE_GAME_SECONDS` | 250 |
| `BANK_MISS_GRAZE_GAME_SECONDS` | 200 |
| `RATTLE_MAKE_SETTLE_GAME_SECONDS` | 150 |
| `BOR_MAKE_FOLLOWUP_SWISH_DELAY_MS` | 150 |
| `BANK_MAKE_FOLLOWUP_SWISH_DELAY_MS` | 100 |
| `RATTLE_HOP_GAME_SECONDS` | 40 |
| `HCO_STEP_T_FLOOR_GAME_SECONDS` | 175 **per skeleton step** (floor) |
| `FB_PASS_MIN_GAME_SECONDS` | 175 **per FB pass step** (floor) |

---

## 6. "Pauses between turns" — hypothesis, not yet confirmed

The turn loop (`animateGameTurns.js:713`) is a bare sequential `await
animationRouter.processTurn(turn)`. **There is no inter-turn sleep.** So the seam pause is
almost certainly root cause #1 stacking: turn N ends on a hold/announcement step (everyone
frozen, 300–1000ms) and turn N+1 opens on a frozen alignment/handoff step. Two frozen steps
back-to-back read as one dead stop.

**Not measured.** Confirm before tuning — see §7.

---

## 7. Measurement before tuning

`UESS_TRACE_PLAYBACK` already emits `step:movers` per step with each mover's duration and
distance (`animationPlayback.js`). Extend it to a **dead-air ledger**: log every step where
zero players move, plus its wall duration and the turn seam it sits on. One real game then
yields an exact ranked list of dead air instead of guesses.

Do this first. It converts §5 and §6 from an inventory into a priority order.

---

## 8. The 350ms contract is being diluted, not threatened

Requirement 3 ("executed a bit sloppily") is real and it is the most useful finding of the
requirements pass. The system runs **two conflicting time idioms**:

| | Scaled time (correct) | Unscaled time (violation) |
|---|---|---|
| Mechanism | step `T_game_seconds` x 350 = wall ms | raw wall-clock hold |
| Game clock | **burns** | **explicitly paused** |
| Stat impact | realistic | invisible to the box score |
| Backend idiom | `X / 350.0` (wall ms in scaled units) | `hold_ms`, `wall_clock_hold_ms` |

Unscaled sources, confirmed:

- **Blocking announcements.** `runStepAnnouncement()` calls `gameClock.pause()` +
  `shotClock.pause()`, waits `hold_ms`, resumes. **44 of 54 announcement literals are
  blocking** (only 10 carry `non_blocking: True`). 300ms each; FT ones 600ms.
- `wall_clock_hold_ms` on advance-trigger metadata — shot micro-movements, fumble (660ms), dunk.
- FE config holds on the legacy `turnAnimation` path — `shot.rimHoldMs` 1000,
  `offensiveRebound.pauseMs` 1000, `finalTurn` 1800/2000.
- Explicitly documented: `turn_manager.py:134` "500ms real, 0 game time";
  `animation_config.js:84` "0 game time"; `constants/__init__.py:274` "wall only; clock pinned".

### Why this matters

**Every unscaled hold is simultaneously the dead air and the scale violation.** They are one
defect, not two. This means:

- The feel goal and the timing-contract goal are **the same goal**, not competing ones.
  Removing dead air *tightens* the 350ms scale.
- The scale is not at risk from this project. It is **currently being diluted** by holds
  that buy wall time and zero game time.
- It explains why the game *feels* slow while the stats look fine: the slowness is
  invisible to the stat model by construction.

### The escape hatch already exists

`non_blocking: True` shows the callout while play continues underneath — already used on 10
announcements (FB lane pass, outlet denied, no fast break). The pattern is proven; it just
has not been applied broadly. Converting blocking -> non-blocking where the callout should
ride alongside motion is a per-announcement judgment call, and a natural review artifact
for the user (44 items, each a yes/no).

---

## 8a. Requirements check

| Requirement | Verdict | Detail |
|---|---|---|
| **Sim Perf Capstone** — no slowdown | **Helps** | All 3 root causes are authoring changes; no added per-step FE work. Clock-pinned holds are pure wall cost with zero sim value, so removing them speeds live play without touching sim math. Full-game sim path is untouched. |
| **UESS compliance** — logic backend, FE pure render | **Increases conformance** | RC#2's fix removes a parallel coord source (`HCO_STRING_SPOTS` re-derivation), which UESS §1 already names a violation. RC#1 and RC#3 are backend-side authoring. Nothing moves to the FE. **No doc change needed** — code must conform to the doc as written. |
| **350ms = 1 game second** | **Tightens it** | See §8 above. The contract is currently diluted by 44 blocking announcements + wall-clock holds. This work restores it rather than risking it. |

Deletion-as-completion-gate (from the prior thread) still applies: legacy FE orchestrators
(`turnAnimation` 5,809 + `fastBreak` 4,269) and the dead knobs in §5a must be removed by the
phase that obsoletes them, not deferred to a later one.

## 9. Tunable Constants

| Constant | File | Value | Effect |
|---|---|---|---|
| `ANNOUNCEMENT_FREEZE_HOLD_MS` | `constants/announcement_constants.py` | 300 | Court freeze on every blocking announcement; mirrored FE |
| `HCO_STEP_T_FLOOR_GAME_SECONDS` | `constants/__init__.py` | 0.5 (175ms) | Min duration of any HCO skeleton step |
| `FB_PASS_MIN_GAME_SECONDS` | `constants/__init__.py` | 0.5 (175ms) | Min duration of any FB pass step |
| `PASS_GRID_SPOTS_PER_GAME_SECOND` | `constants/__init__.py` | 24 | HCO pass speed |
| `FB_PASS_GRID_SPOTS_PER_GAME_SECOND` | `constants/__init__.py` | 40 / 30 sloppy | FB pass speed; sloppy hangs longer by design |
| `clockSecondMs` | `gameClock` state | 350 | Master game-sec → wall-clock scale. **Global pacing dial.** |

---

## 10. Implemented — measurement pass (2026-08-27)

Landed as one unit. Uncommitted on `develop`.

| # | Change | Files |
|---|---|---|
| 1 | **Make-hold de-load-beared.** Dwell moved from the announcement's `hold_ms` to the step's own `advance_trigger.metadata.wall_clock_hold_ms`. The beat now survives a non-blocking announcement. | `engine/skeleton_step_emitter.py` |
| 2 | **Announcement blocking default inverted.** Schema contract: non-blocking unless `blocking: True`. All 44 previously-freezing announcements now ride alongside motion. `non_blocking` kept as deprecated pass-through. | `utils/animation_step_schema.py`, `animationPlayback.js` |
| 3 | **Dead-air ledger.** Records frozen steps (zero movers) and announcement freezes, separating legitimate ball-motion beats. | `animation/deadAirLedger.js` (new), `animationPlayback.js` |
| 4 | **Foul language → backend, role-aware.** Canonical table with an on-ball/off-ball axis; FE table demoted to deprecated fallback. | `engine/foul_announcement_language.py` (new), `fb_terminal_announce.py`, `phase_resolution.py`, `foulAnnouncementLanguage.js` |
| 5 | **Presentation RNG stream.** `announcement_rng`, isolated from `sim_rng`. | `utils/sim_random.py` |

### How to run the measurement

```
play a quarter  →  dumpDeadAir()      # console: ranked dead-air ledger
                   resetDeadAir()     # clear between quarters
```

A/B the announcement change without a rebuild:

```
window.FORCE_ANNOUNCEMENT_BLOCKING = true   # restore old freeze-everything feel
window.DEAD_AIR_LEDGER = false              # silence ledger logging
```

### Foul language pools

| Text | non-lane | lane | Role |
|---|---|---|---|
| Blocking Foul! | 25 | 5 | on-ball |
| Hand-Checking! | 25 | 0 | on-ball |
| Illegal Contact! | 10 | 10 | either |
| Holding! | 15 | 20 | either |
| Arm Bar! | 15 | 10 | either |
| Pushing! | 10 | 30 | either |
| Illegal Post Defense! | 0 | 25 | off-ball, **or** on-ball when the BH is at lowPost / midPost |

Flag-driven overrides bypass the table: `otb_foul` → "Over The Back!" (off-ball),
`quick_foul` → "Quick Foul!", `reach_in_foul` → "Reaching In!" (both on-ball).

Selection distribution is **unchanged** — `select_foul_player` still spreads 40%
of defensive fouls to off-ball defenders. Only the copy changed.

### Why announcement copy needed its own RNG stream

Stamping foul text backend-side added draws to `sim_rng`, which shifted every
downstream basketball outcome — a presentation change silently altering
gameplay. `announcement_rng` (seeded at `seed + 1_000_003`) makes copy changes
provably outcome-neutral while keeping seeded replays byte-identical. Verified:
50 announcement draws leave the gameplay stream bit-identical.

### Test status

Targeted suite (49 files, 343 tests): **no regressions**. The suite carries
~9–11 pre-existing order-dependent failures whose membership changes between
identical runs; every test flagged in a diff was confirmed to fail (or pass)
the same way on a stashed baseline when run in isolation.

### Still open (next pass)

- **Root cause #1 not yet fixed** — `continuing_targets` still defaults to freeze.
  This is the big one; the ledger exists to size it.
- §6 turn-seam hypothesis still unmeasured.
- Root cause #3 (shot-release intent) not started.
- FE `foulAnnouncementLanguage.js` fallback table can be deleted once every foul
  path is confirmed to stamp `foul_announcement_text`.
