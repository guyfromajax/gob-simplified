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

---

## 11. First measurement result (2026-08-27)

Sample: turns 64–80 of a live quarter.

**Announcement flip validated.** Zero `announce-freeze` entries — all 44 now ride
alongside motion, and no beat collapsed (`make_hold` logged at its full 300ms,
confirming the step-ownership fix). User feel report: *"much better, the pace of
the game with those pauses removed feels very nice."*

**Dead air is NOT the dominant defect.** 3,396ms across ~17 turns ≈ 108ms/turn,
and ~46% of it is presentation the user explicitly likes:

| Kind | Total | Verdict |
|---|---|---|
| `make_hold` x2 | 600ms | Keep — made-shot beat |
| `ft_stationary` x3 | 366ms | Keep |
| `bounce` | 300ms | Keep — rim action |
| `rattle_settle` x2 | 300ms | Keep — rim action |
| `player_reaches_position` x3 | 911ms | **Defect** — gated on arrival, nobody moves |
| `bip_passer_hold` + `bip_fcp_passer_hold` | 700ms | **Defect** — RC#1 |
| `bip_inbound_pass` | 219ms | **Defect** — 10 players frozen during inbound |

### The instrument was measuring the wrong thing

Frozen steps require **zero** movers. RC#1's actual signature — outlet denial,
bat-OOB, frozen FB defenders — is **one mover and nine posed**, which has
`movers > 0` and never appeared. 108ms/turn of true dead air cannot explain the
felt clumsiness; the stiffness is in steps that technically have motion.

**Fix:** `recordStillness` now runs on every step and reports *player-seconds of
stillness* = (players that never moved) x duration. A 368ms step with 1 of 10
moving costs 3.3 p-s; the same step with all 10 moving costs 0. Ranking by this
surfaces the posed-court family directly.

### Observer effect — instrument made silent

Per-event `console.log` was measurably destructive. A `HEAVY_RATTLE` is **8
consecutive ~50ms steps** (`RATTLE_HOP_GAME_SECONDS`, floored to 50ms by the FE's
`Math.max(50, ...)`); synchronous console writes with DevTools open added enough
per-step latency to make rim action visibly stutter — reported as "slower and
jerkier" rattles. The ledger is now buffer-only; nothing prints until
`dumpDeadAir()`.

The rattle path was verified clean of all code changes: hops carry **no
announcement** (arrival SFX only, so the blocking flip cannot touch them),
`ball_motion_style` is `None` (so no 400ms `SHOT_BALL_MIN_WALL_CLOCK_MS` floor),
and `make_hold` runs *after* the rattle. Not a regression.

**Minor pre-existing note:** hops are authored at 40ms but the FE floors every
step at 50ms, so rattles run ~25% slower than authored. Candidate for later
tuning, not a regression.

---

## 12. Implemented — freeze-by-default pass (2026-08-27)

Scope agreed with user: **HCO stationary players left as-is** (idle motion descoped),
SIP/BIP passer holds left as-is. Work limited to the FB/transition family, where
players demonstrably had unfinished authored movement that was being dropped.

### 12a. Archetype rate consolidated

`_ag_grid_per_game_sec` existed in three places. `rim_runner_step_emitter` and
`covert_release_step_emitter` each kept a private copy **missing the `drift`
branch**, so drift silently resolved to `standard` — 14 instead of 8, a 75%
overspeed. Their docstrings were also stale (claimed an AG=50 anchor of 12 after
`STANDARD_GRID_PER_GAME_SEC` moved to 14).

Both copies now alias the canonical `animation_step_helpers.ag_grid_per_game_sec`.

**Behaviorally a no-op today:** neither emitter ever assigns `drift`, and
`fb_drive_resolution` already imported the canonical version. This removes a trap
rather than changing output — verified identical rates across all seven archetypes.

### 12b. Continuing movement — three FB builders

Replaced the freeze-everyone block with `_initialize_continuing_movement`, which
reuses each player's **existing** destination from the prior step. No invented
movement; gate timing (`T_game_seconds`) unchanged in all three.

| Builder | Before | After |
|---|---|---|
| `_build_outlet_denied_defender_step` | 1/10 movers | **9/10** |
| `_build_lane_pass_intercepted_step` | 2/10 (defenders 1/5) | **9/10 (defenders 5/5)** |
| `_build_lane_pass_batted_step` | 2/10 (defenders 1/5) | **9/10 (defenders 5/5)** |

The two lane-pass terminals run ~2.14s each, so each occurrence was carrying
~17 player-seconds of stillness. Ball holder / passer correctly still holds his
release position; ball ownership and clock unchanged.

`_build_lane_pass_step` was deliberately **not** converted — it already commits
every player via `_commit_lane_pass_sprint_mover`. An over-broad match caught it
and the assertion stopped the edit.

### 12c. Not done (and why)

- **HCO `player_reaches_position`** (276 p-s, 43% of stillness) — untouched by user
  decision. Root cause is play-design: skeletons author only **1.27 of 5** offensive
  movers per step (measured across all 7 skeletons, 44 transitions), and defenders
  track their man, so ~2.5/10 is the authored ceiling. Fixing it means richer
  skeletons or Dynamic MM off-ball logic, not animation plumbing.
- **SIP/BIP passer holds** (~45 p-s) — after `sip_setup_walkin` players have genuinely
  arrived, so there is no intent to carry forward; only idle motion would help, and
  idle motion is descoped.
- **HCO bat-OOB** — not a step-based path at all. The FE flies the ball imperatively
  from `turn_result.bat_oob_*` (`_finalize_hco_pass_bat_oob` +
  `AnimationEngine._runHctBatOobBallSend`); the emitter path was removed 2026-07-13.
  HCT bat-OOB already passes `continuing_targets`.

### Test status

Targeted suite (49 files): **no regressions.** The one test flagged in a sweep diff
(`test_outlet_pass_roles_not_set_when_rebounder_is_ball_handler`) passes in isolation
on both baseline and changed trees, and also fails in baseline sweeps — pre-existing
order-dependence, same class as the other ~9.

### Next measurement

Re-run `dumpDeadAir()` on a quarter with fast breaks. Expect the FB rows
(`outlet_denied`, lane-pass terminals) to drop toward 0 p-s. HCO rows should be
unchanged — that is the control.

---

## 13. Second measurement + the arrival-tail blind spot (2026-08-27)

### Fast breaks are clean by the stillness metric

Summing every `FAST_BREAK` row: **~10.0 p-s of 447.8 total (2%)**. Largest is
`make_hold` at 0.0/10 movers, which is correct (the made-shot beat). Three rows
score a perfect 10/10 (`rim_runner_meet`, `triangle::rim_runner_drive`,
`rim_runner_fixed_burst_advance`).

**Caveat:** none of the three converted branches (`outlet_denied`,
`lane_pass_intercepted`, `lane_pass_batted`) appeared in either sample — those
outcomes did not occur. The §12b fixes remain verified only on synthetic
fixtures, not in live play.

### But the user still sees frozen defenders — the metric has a blind spot

`countStepMovers` asks only whether `start != end`. It cannot see **when** in the
step a player moved. `stamp_tween_durations` sets each tween to
`min(distance / rate, step_t)` and its docstring states the consequence plainly:
*"each player tweens for their natural duration then idles at their end coord
until step T elapses."*

So `FAST_BREAK/triangle :: rim_runner_drive` — 1445ms, 10/10 movers — scores
**0.0 p-s** while every player may stand for most of a second. Long steps that
end FB possessions are exactly where this is most visible, which matches the
report of "defenders not animating during the final steps of the turn."

This is the documented natural-speed-then-idle design (§ "lazy drift"), not a
regression.

### Category 4 added: arrival tails

`recordArrivalTails` computes, per mover, `stepWaitMs - (tween_duration x
clockSecondMs)` and reports player-seconds spent standing at the destination.
`dumpDeadAir()` now prints an ARRIVAL TAILS table plus a COMBINED STATIC TIME
total.

Verified on a synthetic reproduction of `rim_runner_drive`: 0.0 p-s stillness,
**12.7 p-s arrival tails**; a healthy step where movers use the full duration
scores 0.0 on both.

### Why this matters for the plan

`PLAYER STILLNESS` alone under-reports static time. The two categories have
different fixes:

| | Cause | Fix |
|---|---|---|
| Stillness | player has no destination | continuing movement / play design |
| Arrival tail | player has a destination but reaches it early | bounded pace-to-arrive, or idle motion |

Both remedies for arrival tails were previously discussed and set aside — stretch
was rejected long ago as "lazy drift", and idle motion is descoped. Re-open only
with a measured tail number in hand.

---

## 14. Team split added to hunt the FB defect (2026-08-27)

Three quarters of measurement never triggered `outlet_denied`,
`lane_pass_intercepted`, or `lane_pass_batted`, so the §12b fixes remain
verified only on synthetic fixtures. Meanwhile the reported defect — "the whole
defensive team stops animating while the offense plays out the turn" — was
invisible to the summary, because a combined movers count cannot distinguish
5-offense/0-defense from a balanced 2/3 split.

`splitMoversByTeam` now records offense/defense movers per step (via
`sprite.team_id` vs `scene.offenseTeamId`; returns null rather than guessing
when team identity is unresolvable). The stillness table prints
`off M/N  def M/N` per row and appends **`<== DEFENSE FROZEN`** when offense is
at least half in motion while defense is at most 10% — the exact signature.

Verified: flags off 5/5 + def 0/5; does not flag a balanced 2/5 + 2/5, nor a
healthy 5/5 + 5/5.

### HCO stationary players — closed

User confirmed after the pause removal: *"I'm actually not really bothered by
stationary players during HCO turns now that things are moving faster without
the pauses. It feels like real basketball. Often times in HCO sets players do
remain stationary for moments of time."*

Both HCO halves (stillness 262 p-s, arrival tails 160 p-s) are therefore
**accepted behavior, not defects**. Do not reopen without a new request.

### Next topics (user-selected, after the FB defect)

1. Shot timing dynamics (root cause #3 — no catch-and-shoot vs hold-then-rise intent)
2. 2D geography + player collisions (sprite stacking)

---

## 15. THE FB defect — found and fixed (2026-08-27)

### Root cause

Not in the FB emitters at all. `BackEnd/utils/transition_shot_board_crash.py`
already implements board-crash destinations for transition shots — the system
that makes players crash the glass on a shot attempt. Its assignment loop had:

```python
elif _euclid(start_coord, basket) <= radius:
    continue          # radius = CONTEST_EUCLIDEAN_RADIUS = 11
```

Any player already within 11 grid of the basket got **no destination at all**.
On a fast break that ends at the rim virtually everyone is inside that radius, so
the entire non-shooter cast was skipped and stood still for the whole shot step.

**The board-crash system silently no-opped in exactly the situation it was built
for.** This is why the defect survived repeated fixes: the fix existed, and an
early-out was hiding it.

### Scope

`_BOARD_CRASH_TURNS = {FAST_BREAK, HCT, FCP}` — shared helper, so the defect was
never RR-specific. Ledger data confirmed both FB variants:
`rim_runner :: shot_resolved` 8/10 arriving early, `triangle :: shot_resolved` 9/10.

### Fix

Replaced the `continue` with a sampled crash target, **scoped to FAST_BREAK**
(HCT/FCP keep old behavior pending review). Added `_sample_crash_target`, which
retries the disk sample until the point is at least `_MIN_CRASH_MOVE_GRID` (4.0)
from the player's start, falling back to stepping 4 grid toward the basket when
the player is already at the rim — otherwise a near-rim player gets a sampled
spot ~0 grid away and still renders frozen.

Deliberately **not** "everyone targets the basket coord": eight sprites converging
on one point is the stacking problem, and the existing radius sampling exists to
avoid it.

Verified on a rim-clustered fixture: FAST_BREAK assigns 8/10 (shooter + shot
defender correctly held), displacement 4.7–13.9 grid, all inside the rim radius;
HCT assigns 0/10 (scoping holds).

### Gameplay consequence — accepted, needs measuring

`select_rebounder_by_score` weights by `1 / (1 + distance / REBOUND_DISTANCE_SCALE)`
and can filter on `max_distance_from_bounce`. The overlay maps written here feed
`sync_lineup_coords_from_turn`, which seeds the DREB/OREB turn. **Fast-break
rebound outcomes will shift** — crashers get closer to the bounce spot and score
higher. Arguably a correction, but it is a real gameplay change, accepted by the
user with the understanding that FB OREB/DREB splits should be measured
before/after.

Also shifts the `sim_rng` stream (extra `rng.uniform` draws for previously-skipped
players), so seeded replays will not match pre-change runs. Correct here — unlike
announcement copy, these draws produce positions that are genuinely gameplay.

### Tests

No regressions. Two tests appeared in a sweep diff; both pass in isolation with
the change, and one fails in isolation on baseline — the known order-flake set.

### Note for the collision work

Closest sampled destination pair on the fixture was 1.7 grid apart. Destinations
are clamped by `rate x t` so players rarely reach them, but this is the kind of
convergence the future sprite-collision work will need to handle.

---

## 16. HCO cold-start after Triangle FB (2026-08-27) — partially resolved

### Symptom
Post-FB HCO turns skip the Handoff + dribble-up and cold-start (= teleport).

### Confirmed chain (from production logs)
`❌❌❌ [HCO ENTRY BUG]` fired 3x, every one `fast_break_play=triangle` +
`result_type=DEFENSIVE_STOP` + `has_animation_steps=False`:

no `animation_steps` → no `last_step.end.ball.owner_player_id` →
`final_ball_handler_id=None` → `current_bh_id=None` → `has_entry_inputs` fails →
orchestrator skips Handoff/Walk-Up → HCO cold-starts.

Every rim_runner turn in the same log fired `HANDOFF FIRED` + `WALKUP FIRED`
correctly. One branch, not a general breakage.

### Fixed

**1. `build_final_ball_handler_id` could not read a dict-shaped role.**
```python
pid = getattr(bh, "player_id", None) if not isinstance(bh, (str, int)) else bh
```
`roles.ball_handler` appears as a bare id, a Player object, **or a serialized
dict** `{player_id, name, team}`. The dict case fell through `getattr` → None.
The production log printed the dict right there in the error — the handle existed
and the resolver couldn't see it. Now handles all three shapes; priority order
(animation_steps → ball_handler_id → roles) unchanged and tested.

This is a **general safety net**: any emitter gap now degrades to a correct
handoff instead of a teleport.

**2. Triangle's null-consequence log was `logging.debug`** while Rim Runner's
identical branch was `logging.warning` — so Triangle emitter failures were
invisible at normal log level. Promoted to `warning`.

**3. Triangle's `_is_full_simulation` early return was the emitter's only
unmarked exit** (RR and Covert Release have no such guard at all). It now stamps
`fb_emitter_fallback_reason = "triangle:full_simulation_skip"` without logging —
a real full sim would emit one per fast break.

**4. The HCO entry error now prints `prior_turn.fb_emitter_fallback_reason`**, so
the next occurrence names the exact guard that fired.

### NOT yet resolved — why Triangle returned None

`FB_EMITTER_FALLBACK` produced **zero** log hits, so no marked guard fired. Two
candidates remain:

- `_is_full_simulation` was set on a live turn (now distinguishable via the
  stamped reason)
- an exception inside `_finalize_rr_steps` → `🚨 [TRIANGLE EMITTER EXCEPTION]`
  (ERROR level; not covered by the original grep)

**Next occurrence is self-diagnosing** via fix 4. Also worth grepping
`TRIANGLE EMITTER` (covers both NULL CONSEQUENCE and EXCEPTION).

### Correction to an earlier hypothesis
I proposed that non-rebound RR/Triangle fast breaks fall through the dispatch
gate and added a branch for it. That is **impossible**:
`play_key_for_fast_break_entry(is_dreb_outlet=False)` always returns
`AFTER_STEAL`, so `fb_play_key == TRIANGLE` implies `rebound == True`. The branch
was unreachable dead code and was removed.

### Test note
`test_outlet_pass_roles_not_set_when_rebounder_is_ball_handler` and
`test_deep_key_anchor_backcourt_side` fail intermittently (~1 in 5) on **both**
baseline and changed trees — genuinely nondeterministic, not regressions.
