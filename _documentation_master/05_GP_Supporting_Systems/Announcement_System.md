## Announcement System ✅ **SS&S** (January 2025)

**Base Constants**

1. **Timing Types**:
   - `timing='start'` - Context announcements (situation being entered)
   - `timing='end'` - Result announcements (outcome of turn)

2. **Display Layer — two tiers**

   The system has **two independent display tiers** that may be on screen at the same time. Callers select the tier via the payload field `tier: 'primary' | 'secondary'`. Default is `primary`.

   **Primary — Center-Court Overlay** (`#announcement-overlay`):
   - **Location:** `#announcement-overlay` inside `#phaser-container` (position: absolute, centered). HTML, CSS, and controller live in `FrontEnd/static/court.html`.
   - **Variants:**
     - **Standard** — Single player portrait (left), caption bar (#jersey lastName + position), and event text (right). Used for all single-player result events (made shot, rebound, block, steal, fouls, turnovers, etc.).
     - **Foul (AND-1)** — Shooter portrait (left), center panel ("It's Good!" + "+ Free Throw" + "And one"), fouler portrait (right). Used only for made shot with shooting foul.
   - **No-player announcements:** When the payload has no `photoUrl` and no `lastName`, the portrait zone is hidden and the event text is centered. This applies to: **DOUBLE TEAM!**, **Batted Ball Out Of Bounds!**, and other rare neutral cases. (Press/Trap/Fast Break/Slow It Down/Quick Shot/Final Shot now route to the secondary tier — see below.)
   - **Data shapes:** Standard `{ type: 'standard', eventText, photoUrl, jersey, lastName, position }`. Foul `{ type: 'foul', foulEventText, shooterPhotoUrl, shooterJersey, shooterLastName, foulerPhotoUrl, foulerJersey, foulerLastName }`.

   **Secondary — Top-Edge Ribbon** (`#announcement-overlay-secondary`):
   - **Purpose:** Non-critical context announcements that should not block sprite action in the center of the court.
   - **Location:** `#announcement-overlay-secondary`, sibling of `#announcement-overlay` inside `#phaser-container`. Mounted at the top edge of the court canvas (`top: 4px; left: 16px; right: 16px; height: 64px`).
   - **z-index:** `940` (primary is `950`); always sits above court sprites and below the foul card / modals.
   - **Variants:**
     - **With player** — 48×48 headshot + chip (#jersey above last name), italic headline centered, optional Good/Bad Read pill in the lower-right corner.
     - **No player** — Headline only, centered horizontally and vertically.
   - **Team color:** The left-edge stripe (6px) and the surface gradient resolve from the **initiating team's `primary_color`** via `gameStore.getColors()`. Defense-initiated events (Press, Trap, Great Stop!, FB Outlet Pass Denied) use the defense side; offense-initiated events use the offense side.
   - **Data shape:** `{ tier: 'secondary', type: 'standard', eventText, photoUrl, jersey, lastName, teamColor, decisionPillText, decisionPillTone }`.
   - **Motion:** Entry slides DOWN from `translateY(-110%)` to `0` with fade-in (`260ms cubic-bezier(.22,1,.36,1)` transform, `220ms ease` opacity). Exit reverses. Headline plays a `secPulse` (scale 0.96 → 1.02 → 1.00) at 60 ms delay. Reduced-motion: fade only, no transforms.
   - **SFX:** **No SFX** for any secondary announcement in v1. Whistles remain primary-only.

   **Routing API:** All display is routed through `window.showAnnouncementOverlay(data)`. The function dispatches on `data.tier` — `secondary` → `window.showSecondaryAnnouncementOverlay(data)`, otherwise the primary path. The JS helpers in `announcements.js` (`showAnnouncement`, `showAndOneAnnouncement`, **`showSecondaryAnnouncement`**) build the payload and call the dispatcher.

   **Duration:** Each tier overlay is shown for **2200 ms** then hidden. Each tier owns an independent timer — there is **no cross-tier queueing**; primary and secondary can coexist on screen. Within a single tier, a new announcement preempts the prior one (the existing single-overlay-per-tier behavior).

   **Typography:** Both primary and secondary announcement **headlines** use **Bebas Neue** (Google Fonts, already loaded). Smaller text (jersey caption, position, foul subtext, decision pill) continues to use Barlow Condensed.

3. **Idempotent Flags**:
   - `turn._contextAnnouncementsShown` - Prevents duplicate start announcements
   - `turn._reboundHeadlineShown` - Set by `announceReboundHeadlineIfNeeded()` after showing **Rebound!** so the same MISS/BLOCK (or rebound) turn cannot trigger duplicate headlines from `ballManager`, embedded shot rebounds, FT rebound, or `announceGameEvent('REBOUND', ...)`.

4. **Announcement hold time**:
   - **1000 ms** — Uniform delay for result announcements before the next animation. In **ShotAnimationSystem** (HCO/regular makes), the rim hold and "It's Good!" / AND-1 run **in unison**: one 1000 ms period with ball at rim and announcement both visible. Other paths (ballManager made shot, FT make, FB make, "Great Stop!") use a 1000 ms hold after the announcement. Do not reduce when tuning other animation delays; see "Hold time after result announcements" below.

5. **Tier routing (canonical list)**

   The following announcements route to the **secondary** tier (top-edge ribbon):

   | Announcement | Initiating team | Player headshot? | Where it fires |
   |---|---|---|---|
   | **Press!** | defense | no | `gameAnnouncements.js` → `PRESSURE_FCP` |
   | **Trap!** | defense | no | `gameAnnouncements.js` → `PRESSURE_HCT` |
   | **Fast Break!** (start) | offense | no (dispatcher) / yes (RR lane-pass with passer) | `gameAnnouncements.js` → `FAST_BREAK`; `fastBreak.js` `animateRimRunnerLanePass` |
   | **No Fast Break** (RR decision) | offense | yes (ball handler) | `fastBreak.js` `animateRimRunnerHoldUpLeadIn` |
   | **FB Outlet Pass Denied!** | defense | yes (stopper) when available | `fastBreak.js` `animateRimRunnerOutletDeniedBeat` |
   | **Great Stop!** (FB defensive stop) | defense | yes (stopper) | `fastBreak.js` defensive-stop block; `gameAnnouncements.js` → `DEFENSIVE_STOP` |
   | **Slow It Down** | offense | no | `gameAnnouncements.js` → `SLOW_IT_DOWN` |
   | **Quick Shot** | offense | no | `gameAnnouncements.js` → `QUICK_SHOT` |
   | **Final Shot** | offense | no | `gameAnnouncements.js` → `FINAL_SHOT` |

   Everything else stays on the **primary** center-court overlay. **AND-1 and the foul card stay primary.**

   The Good Read / Bad Read decision pill (gold/red) ships on the secondary tier for the Fast Break! / No Fast Break RR decision. It uses the same visual vocabulary as the existing primary `.ann-decision-pill` and is anchored to the lower-right corner of the secondary ribbon.

**Announcement System Flow (2 Phases)**

1. **Start Announcements** (`timing='start'`) — route to **secondary** tier (top-edge ribbon)
   - **"Press!"** - FCP pressure applied (BASELINE_INBOUND with `next_defensive_setup='FCP'`)
   - **"Trap!"** - HCT pressure applied (BASELINE_INBOUND with `next_defensive_setup='HCT'`)
   - **"Fast Break!"** - Fast break initiated (only if not following a steal)
     - Suppressed if `turn.roles?.is_steal_entry` is true (steal announcement takes priority)
   - **"Slow It Down"** - Q4/OT HCO turns when `turn.slow_it_down` is true
   - **"Quick Shot"** - Q4/OT HCO turns when `turn.quick_shot` is true
   - **"Final Shot"** - Final-turn shot attempts when `turn.final_turn` is true and `result_type !== 'FINAL_HOLD'`

2. **End Announcements** (`timing='end'`) — route to **primary** tier (center-court overlay)
    - **"It's Good!"** - Made shot (ballManager.js, when ball reaches rim)
    - **"It's Good! And 1!"** - Made shot with shooting foul (overlay foul card: shooter portrait, center "It's Good!" + Free Throw, fouler portrait)
    - **"Shooting Foul!"** - Defensive shooting foul on miss (with fouling player headshot)
   - **"STEAL!"** - Steal occurred (takes priority over Fast Break announcement)
   - **"Travel!" / "Double Dribble!"** - Dead ball turnovers (randomly chosen 50/50)
   - **"OUT OF BOUNDS!" / "BAD PASS!"** - Other turnover types
   - **"Charge!"** - Offensive foul on drive (result_type === 'CHARGE')
   - **"BLOCKING FOUL!"** - Defensive blocking foul on drive (result_type === 'FOUL', foul_team DEFENSE, text contains "blocking foul")
   - **"OFFENSIVE FOUL!" / "DEFENSIVE FOUL!"** - Other non-shooting fouls (with fouling player headshot)
   - **"BLOCK!"** - Block on shot attempt (ShotAnimationSystem when ball reaches block spot, before rebound; blocker's image)
   - **"Rebound!"** - Rebound secured (DREB and OREB): `announceReboundHeadlineIfNeeded()` in `announcements.js`; see **Rebound announcements** below. **Discrete `DREB` turn** (separate row after some MISS/BLOCK): outlet choreography is **`AnimationEngine._maybeRunDiscreteDrebOutletLeadIn`** → `runDefensiveReboundSetup` after DREB `playTurn` (see `Turn_by_Turn_System.md`); **Rebound!** usually still fires on the **embedded** MISS/BLOCK path via `ShotAnimationSystem.handleEmbeddedRebound`, not on the DREB `animation_steps` row alone.

**Long Form Documentation**

### Overview

The Announcement System provides visual feedback for game events using timing-based separation. Context announcements (situation being entered) appear at turn start, while result announcements (outcome of turn) appear at turn end. The system uses idempotent flags to prevent duplicate announcements when functions are called multiple times.

### Start Announcements (Context)

**Tier:** **Secondary** (top-edge ribbon).

**Location:** `FrontEnd/static/js/phaser/animation/turnPreparation.js` → `prepareTurnForAnimation()` (the `if (!turn._contextAnnouncementsShown)` block).

**Announcements:**
- **"Press!"** - Triggered when `result_type === 'BASELINE_INBOUND'` and `next_defensive_setup === 'FCP'`. Stripe = defense team primary color.
- **"Trap!"** - Triggered when `result_type === 'BASELINE_INBOUND'` and `next_defensive_setup === 'HCT'`. Stripe = defense team primary color.
- **"Fast Break!"** - Triggered when `turn.fast_break === true`, `turn.current_turn === 'FAST_BREAK'`, or `turn.roles?.rim_runner_sequence === true`, but suppressed if:
  - `result_type === 'STEAL'`
  - Text includes "steal"
  - `turn.roles?.is_steal_entry` is true (steal-initiated Fast Break)
- **"Slow It Down"** - HCO turns (`current_turn === 'HCO'` or `play_type === 'HCO'`) when `turn.slow_it_down` is true (Q4/OT pacing).
- **"Quick Shot"** - HCO turns when `turn.quick_shot` is true (Q4/OT pacing). `slow_it_down` takes precedence if both are set.
- **"Final Shot"** - When `turn.final_turn` is true and `result_type !== 'FINAL_HOLD'`.

**Pressure dispatch from Free Throws:** `FreeThrowAnimationSystem.js` also dispatches `PRESSURE_FCP` / `PRESSURE_HCT` when `next_defensive_setup` indicates pressure after a final FT.

**Implementation:** Uses `announceGameEvent()` dispatcher from `gameAnnouncements.js`, which routes the events listed above through `showSecondaryAnnouncement()` in `announcements.js`.

### End Announcements (Results)

**Tier:** **Primary** (center-court overlay).

**Locations:**
- Per-animation result announcements fire directly from the animation modules when the ball reaches the relevant beat (rim, rebounder, block spot). See `ballManager.js`, `ShotAnimationSystem.js`, **`AnimationEngine.js`** (discrete **DREB** outlet is movement here, not a headline), `fastBreak.js`, `FreeThrowAnimationSystem.js`. Turn-type and discrete-**DREB** routing: `_documentation_master/05_GP_Supporting_Systems/Turn_by_Turn_System.md`.
- Fallback/result text is also handled in `announcements.js` → `announceFromTurnData(turn, 'end', ...)`, invoked from `animateGameTurns.js` for turns whose result wasn't already announced inline.

**Shot Results:**
- **"It's Good!"** - Handled in `ballManager.js` when ball reaches rim; in `ShotAnimationSystem.js` (HCO makes) in unison with the rim hold. **Fast Break** shots use `fastBreak.js` (see below).
- **"It's Good! And 1!"** - Detected when text includes "AND-1" OR (`foul_player_id` exists + `result === "MAKE"` + `foul_team === "DEFENSE"`).
  - Uses `showAndOneAnnouncement()` for the two-portrait foul card with shooter and fouler headshots.
  - Both player images display `#jersey lastName` directly beneath the headshot when that data is available.
  - Fallback: single-row standard announcement (`"It's Good! And 1!"`) if either player's data is missing.
- **"Shooting Foul!"** - Detected on shot-result turns (`result_type === "MISS"` with shooting-foul context from the shot pipeline).
  - Always displays announcement even if player sprite/info is missing (fallback pattern).
  - Routed via `announceGameEvent('FOUL_SHOOTING', ...)` from `ShotAnimationSystem.handleMissedShot()`.

**Fast Break shot path:** Fast Break shots are animated only in `fastBreak.js` (`animateFastBreakShot`, `animateFastBreakShotWithStopper`). They use `animateShotToRim()` and do **not** go through `ballManager.shootBall()` or ShotAnimationSystem. Therefore **AND-1** and **"Shooting Foul!"** (on miss) must be detected and announced inside `fastBreak.js` using the same logic as in `ballManager.js` (same `turnData` fields and `showAnnouncement` / `showAndOneAnnouncement` / `triggerFoulEffect`). **Note:** the `after_steal` FB play-key is the exception — it migrated to the UESS schema (see "After-Steal Fast Break shot path" below). The legacy path here still applies to DREB-triggered RR / CR / Triangle FBs (their schema migration covers shot result via `_build_post_shot_sub_steps` but in-progress legacy code still handles some choreography).

**After-Steal Fast Break shot path:** Steal-initiated FB shots (`current_turn === "FAST_BREAK"` AND `fast_break_play === "after_steal"`) animate through the UESS step schema emitted by `BackEnd/engine/after_steal_fast_break_step_emitter.py::build_after_steal_fast_break_animation_steps`. Announcements, SFX, and choreography are **backend-emitted** into the step payload — the frontend is a pure renderer. Per-play details:

| Steal-FB case | Step that carries the announcement | How it's stamped |
|---|---|---|
| Burst phase | step 0 `start.announcement` | "Fast Break!" secondary headline (suppresses the FE's `prepareTurnForAnimation` dispatch via `turn._contextAnnouncementsShown`) |
| `MAKE` (with or without and-1) | make-hold step `start.announcement` | `_build_make_hold_sub_step` (from skeleton); text overridden in-place by emitter from "It's Good!" to **"Fast Break Score!"** (or "Fast Break Score! And 1!" for and-1) |
| `MISS` with defensive shooting foul (bounce branch) | bounce step `end.announcement` | `_stamp_shooting_foul_on_miss_end(bounce_step, turn_result)` (shared with skeleton) |
| `MISS` with defensive shooting foul (no-bounce branch) | terminal flight step `end.announcement` | Same helper as above on the terminal step |
| `BLOCK` | ball-flight step `end.announcement` | `BLOCK!` headline (shared post-shot path stamps it) |
| `DEFENSIVE_STOP` | step-back step `end.announcement` | "Great Stop!" secondary headline with stopper headshot |

**Variant rim SFX (RATTLE, BANK, AIRBALL, etc.)** are emitted as per-hop / per-sub-step `sfx_on_ball_arrival` cues by skeleton's `_build_post_shot_sub_steps` (shared helper). This fixes the legacy bug where `playShotResultSfx` early-returned for RATTLE variants on FB shots (no per-hop sub-steps existed in the legacy single-tween path).

**Step-back coord-capture invariant:** the defensive-stop step-back step's `end.coords` IS the authoritative coord snapshot. The next HCO turn's first step (handoff) consumes those as its start coords so the ball handler and stopper don't teleport. This pattern is the canonical fix shape if you tackle the related HCO-steal teleport bug — the step-back step's `end.coords` is the source of truth, never the pre-step-back snapshot.

**OREB Putback shot path:** Putback shots (`PUTBACK_MAKE` / `PUTBACK_MISS`) animate through the UESS step schema emitted by `BackEnd/engine/oreb_step_emitter.py::build_oreb_animation_steps`. Announcements are **backend-emitted** into the step payload — the frontend just plays them via `runStepAnnouncement`. Same pattern as HCO skeleton shots:

| Putback case | Step that carries the announcement | How it's stamped |
|---|---|---|
| `PUTBACK_MAKE` (with or without and-1) | make-hold step (`start.announcement`) | `_build_make_hold_sub_step` (imported from `skeleton_step_emitter`); derives `is_and_one` from `turn_result.next_play_type == "FREE_THROW"` + `foul_player_id` |
| `PUTBACK_MISS` with defensive shooting foul (bounce branch) | bounce step (`end.announcement`) | `_stamp_shooting_foul_on_miss_end(bounce_step, turn_result)` |
| `PUTBACK_MISS` with defensive shooting foul (no-bounce branch) | flight step (`end.announcement`) | `_stamp_shooting_foul_on_miss_end(flight_step, turn_result)` |

`_stamp_shooting_foul_on_miss_end` is the same helper used by `skeleton_step_emitter` on HCO miss + foul. It no-ops when `result_type != "MISS"`, when there are no free throws to come, or when no `foul_player_id` is set. The frontend detection in `ballManager.shootBall` (used by the legacy `handleOrebTurn` path) remains as defense-in-depth and will be redundant once all putback playback routes through the schema.

**Steal Announcements:**
- **"STEAL!"** - Triggered when `result_type === 'STEAL'` or (`result_type === 'TURNOVER'` and text includes "steal")
- Takes priority over Fast Break announcement (suppresses Fast Break if steal-initiated)
- Shows stealer's headshot; initials use the stealer's actual team colors (defense side on the turn, resolved per-player — not inferred from the `defenseTeam` context arg alone)

**Turnover Announcements:**
- **Two pipelines:** the SS&S dispatcher `handleTurnoverAnnouncement()` in `gameAnnouncements.js` (called via `announceGameEvent('TURNOVER', ...)` from `finalizeTurnAfterAnimation()`), and the legacy `announceFromTurnData(turn, 'end', ...)` fallback in `announcements.js`. The legacy path is still invoked from several call sites in `animateGameTurns.js` for turns that haven't been announced inline.
- **Dead-ball turnovers (no explicit type):** Randomly displays `"Travel!"` or `"Double Dribble!"` (50/50). Triggered when `result_type === 'DEAD BALL'` or (`result_type === 'TURNOVER'` without steal indicators).
- **Typed turnovers** (mapped from `turnover_type`):
  - `gameAnnouncements.js` typeMap: `TRAVEL → "Travel!"`, `DOUBLE_DRIBBLE → "Double Dribble!"`, `OUT_OF_BOUNDS → "OUT OF BOUNDS!"`, `BAD_PASS → "BAD PASS!"`, `SHOT_CLOCK → "Shot Clock Violation!"`.
  - Legacy `announceFromTurnData` typeMap additionally recognizes: `PALMING → "PALMING!"`, `ILLEGAL_DRIBBLE → "ILLEGAL DRIBBLE!"`, `BACKCOURT → "BACKCOURT VIOLATION!"`.
- **Shot Clock Violation:** Uses `whistle-3.mp3` (vs `whistle-1-lowervol.wav` for other turnovers). See Sounds below.
- Shows victim's headshot; initials use the victim's actual team colors (offense side on the turn, resolved per-player).

**Foul Announcements:**
- **"Charge!"** - Triggered when `result_type === 'CHARGE'` (offensive foul on drive). Routed via gameAnnouncements.js; AnimationEngine routes CHARGE to handleDefault (skeleton animation, then announcement).
- **"BLOCKING FOUL!"** - Triggered when `result_type === 'FOUL'`, `foul_team === 'DEFENSE'`, and text contains "blocking foul" (non-shooting defensive foul on drive).
- **Offensive non-charge fouls:** Announcement text is now a specific foul call (for example, "Push Off!", "Illegal Screen!", "Elbowing!") selected by weighted language tables.
- **Defensive non-shooting fouls (non-blocking):** Announcement text is now a specific foul call (for example, "Hand-Checking!", "Holding!", "Pushing!", "Illegal Post Defense!") selected by weighted language tables.
- **Lane weighting rule:** Offensive/defensive foul language selection uses separate weighted pools for non-lane vs lane locations (lane: `lower/upper lowPost`, `midPost`, `highPost`, `basketSpot`, `midLane`, `topLane`).
- Shows fouling player's headshot. Skips if shooting foul (already handled in shot result announcements).
- **Important distinction:** `result_type === 'FOUL'` that routes to `next_play_type === 'FREE_THROW'` (bonus) is still announced as FOUL. True shooting fouls are announced in shot-result handlers (`MAKE/MISS` paths such as `ballManager.js`, `ShotAnimationSystem.js`, `fastBreak.js`).

**Block Announcements:**
- **"BLOCK!"** - Announced in `ShotAnimationSystem.handleMissedShot` when `result_type === 'BLOCK'` (when ball has reached block spot), **before** the rebound is announced, so order is always Block → Rebound. Shows blocker's headshot. Routed via `announceGameEvent('BLOCK', ...)` in `gameAnnouncements.js`. Fallback: `finalizeTurnAfterAnimation` announces BLOCK only if `!turn._blockAnnounced`.

**Rebound Announcements:**
- **"Rebound!"** - `announceReboundHeadlineIfNeeded(scene, turnData, rebounderSprite, rebounderId)` in `announcements.js`. Fires when the rebounder secures the ball (embedded path: rebounder tween `onComplete` after attach + rebound SFX; `ballManager.animateRebound`: rebounder tween `onComplete`). **DREB and OREB** on embedded misses both use the same hook so FAST_BREAK / `force_foul_after_dreb` / odd `next_play_type` branches still get the headline when the rebound animates. Idempotent via `turnData._reboundHeadlineShown` when `turnData` is passed (always pass the authoritative MISS/BLOCK or rebound turn from callers). Primary card uses the same portrait styling as other results (`teamName` from `scene.simData` home/away names; `secondaryColor` from `gameStore.getColors()`).
- **Discrete `DREB` row (migration):** Backend may append a separate **`DREB`** turn whose `animation_steps` only capture the ball. **Rebound!** idempotency should continue to use the **MISS/BLOCK** turn object when that turn still runs **`ShotAnimationSystem`** embedded rebound; the DREB row does not replace the headline hook by itself. **Outlet** (pass / bring-up) is **`runDefensiveReboundSetup`** after DREB `playTurn` — see **`Rebound_System.md`** (DREB vs outlet) and **`Turn_by_Turn_System.md`** (Discrete `DREB` turn).

### Sounds (SFX) — payload-carries-SFX architecture

**Single source of truth for announcement-tied SFX:** the announcement payload carries a `sfx` field (filename string or filename array), and `court.html`'s overlay mount functions (`window.showAnnouncementOverlay` for primary, `window.showSecondaryAnnouncementOverlay` for secondary) play it via `window.playGameSfx(filename)` at the moment the DOM mounts. Audio is synced to the visual entry (Sound_Design_Update.md "Trigger: immediately when the announce appears"). Both tiers go through exactly one dispatch point.

**Caller flow:**
1. Caller invokes `showAnnouncement` / `showAndOneAnnouncement` / `showSecondaryAnnouncement` with `meta.sfx = '<filename>'` (or array, or legacy kind — `'foul'` / `'shot_clock_violation'` / `'fb_outlet_denied_court'` / etc.).
2. The helper normalizes the value to a filename via `resolvePrimarySfxFromMeta` (in `announcements.js`) or the equivalent resolver chain in `showSecondaryAnnouncement`:
   - Filename (`.wav` / `.mp3`) → as-is.
   - Filename array → mapped to filename array.
   - Legacy kind → resolved via `resolveAnnounceMetaCourtSfxFile` (`gameSfx.js`).
   - Secondary-tier headline with no `meta.sfx` → resolved via `resolveSecondaryAnnounceCourtSfxFile`, which also applies once-per-turn dedupe for `Press!` / `Trap!` / `Fast Break!`.
3. The resolved filename lands on `data.sfx`; `court.html` plays it at mount.

**No direct `playXxxCourtSfx(scene)` calls** remain outside `gameSfx.js`. The legacy `playAnnouncementSfx(kind)` function in `announcements.js` is kept exported for back-compat but is no longer called from any internal path.

| Announcement | Sound file | Caller |
|---|---|---|
| **Shot Clock Violation!** | `whistle-3.mp3` | `gameAnnouncements.js::handleTurnoverAnnouncement` + `announcements.js::announceFromTurnData` (turnover branch) |
| Dead-ball turnovers (Travel!, Double Dribble!, OUT OF BOUNDS!, BAD PASS!, …) | `whistle-1-lowervol.wav` | same callers as Shot Clock Violation |
| Shooting Foul!, Offensive/Defensive Foul, Blocking Foul | `whistle-1-lowervol.wav` | `gameAnnouncements.js` foul handlers + `announceFromTurnData` foul branches |
| **CHARGE!** | `['whistle-1-lowervol.wav', 'duke-charging.wav']` | `gameAnnouncements.js::handleChargeAnnouncement` |
| AND-1 (shooting foul on make) | `whistle-1-lowervol.wav` (default, overridable) | `announcements.js::showAndOneAnnouncement` |
| **BLOCK!** | `duke-its-blocked.wav` | `gameAnnouncements.js::handleBlockAnnouncement` |
| **STEAL!** / **Interception!** | 33/33/34 random — `sammy-steal.wav` / `braddock-steal.wav` / `butler-steal.wav` (via `resolveStealSfxFile()`) | `handleStealAnnouncement`, `announceFromTurnData` STEAL branch, `fastBreak.js::animateRimRunnerInterception` |
| Press! | random — `sammy-press.mp3` / `press-braddock.mp3` (once per turn) | secondary headline resolver |
| Trap! | `trap-braddock.mp3` (once per turn) | secondary headline resolver |
| Fast Break! | `fast-break-braddock.mp3` (once per turn) | secondary headline resolver |
| Quick Shot | `quick-shot-braddock.mp3` | secondary headline resolver |
| Slow It Down | `slow-it-down-braddock.mp3` | secondary headline resolver |
| Final Shot | random — `sammy-final-shot.mp3` / `final-shot-braddock.mp3` | secondary headline resolver |
| No Fast Break | `duke-hold-up.wav` | secondary headline resolver + backend `meta.sfx: "no_fast_break"` |
| Great Stop! (FB defensive stop) | `duke-great-stop.wav` | `fastBreak.js::animateDefensiveStop` (legacy path); schema path via `covert_release_step_emitter.py` stamping `meta.sfx: "fb_defensive_stop"` |
| FB Outlet Pass Denied! | `duke-denied.wav` | `fastBreak.js::animateRimRunnerOutletDeniedBeat` + backend `meta.sfx: "fb_outlet_denied_court"` |

### Hold time after result announcements (1000 ms)

**Rule:** All result announcements use a **uniform 1000 ms** period on screen before the next animation. In **ShotAnimationSystem** (HCO made shots), the rim hold and "It's Good!" / AND-1 run **in unison**: the announcement is shown immediately and the ball stays at the rim for the same 1000 ms, so there is a single 1000 ms period (not rim hold then announcement). Other paths use a 1000 ms hold after the announcement. Do not reduce below 1000 ms when tuning animation delays.

**Where the 1000 ms hold is used:**

| Announcement / context | Location | Note |
|------------------------|----------|------|
| Shot make — "It's Good!" / AND-1 | `ShotAnimationSystem.js` | **In unison** with rim hold: one 1000 ms period (ball at rim + announcement together) |
| Made shot rim hold (ballManager path) | `ballManager.js` | Holds after ball at rim; allows announcement to display |
| Free throw make — rim hold | `FreeThrowAnimationSystem.js` | Non-final FT; ball at rim then next attempt or transition |
| Fast break make — "It's Good!" | `fastBreak.js` | After FB make announcement |
| Fast break defensive stop — "Great Stop!" | `fastBreak.js` | After "Great Stop!" before transition to HalfCourt |

**Do not reduce** these holds below 1000 ms when tuning animation delays; see `docs/To Do/SEAMLESS_DELAY_TUNING_AND_NEXT_STEPS.md` for which delays are safe to shorten (e.g. shot rim hold, rebound attach, OREB pause) vs announcement holds.

### Idempotent Design

**Problem:** `prepareTurnForAnimation()`, `announceFromTurnData()`, and animation-module result announcements may all run for the same turn (the turn flows through `animateGameTurns`, `AnimationEngine`/`AnimationRouter`, and the per-animation modules). Without guards, the same context or result could be announced more than once.

**Solution — per-turn flags set on `turnData`:**
- `turn._contextAnnouncementsShown` — Set inside the start-announcement block of `prepareTurnForAnimation()` after Press / Trap / Fast Break / Slow It Down / Quick Shot / Final Shot have been dispatched.
- `turn._blockAnnounced` — Set by `ShotAnimationSystem.handleMissedShot()` after a `BLOCK` is announced; `finalizeTurnAfterAnimation()` only announces BLOCK as a fallback when this flag is missing.
- `turn._reboundHeadlineShown` — Set by `announceReboundHeadlineIfNeeded()` after **Rebound!** is shown so animation paths and the `REBOUND` dispatcher cannot double-announce the same turn.

**Benefits:**
- No duplicate announcements across the prep / animate / finalize path.
- Safe to call the dispatchers multiple times for the same turn.
- Works across all turn types (HCO, FB, FT, BASELINE_INBOUND, DEFENSIVE_STOP, etc.).

### Steal → Fast Break Flow

When a steal leads to a fast break:
1. Backend sets `turn.roles?.is_steal_entry = true` on Fast Break turn
2. Frontend checks this flag in `prepareTurnForAnimation()`
3. If `is_steal_entry` is true, Fast Break announcement is suppressed
4. Only "STEAL!" announcement is shown (takes priority)

**Implementation:** `FrontEnd/static/js/phaser/animation/turnPreparation.js` → `prepareTurnForAnimation()` start-announcement block.

### Visual Styling

#### Primary — Center-Court Overlay

**Overlay card:**
- Dark semi-opaque background (`rgba(7, 8, 14, 0.90)`), 5px left accent bar with event-type tone (`#F79420` orange default, `#34EC27` green for makes, `#ff4444` red for fouls, `#4a90d9` blue for defense / steal / block, `#F79420` for turnovers / neutral). Subtle shadow and entry scale animation (`annCardIn`).
- **Headlines** (`.ann-event-text`, `.ann-foul-primary`) use **Bebas Neue** (Google Fonts) italic. Smaller chrome (jersey caption, position label, decision pill, foul subtext) stays on **Barlow Condensed**.
- **Standard card:** Portrait zone **110×144px** with a skewed dark cutaway on the right edge; caption bar at the bottom of the portrait with `#jersey lastName` and position label (orange). Event text large italic, white, with an orange accent on the trailing "!".
- **Foul card (AND-1):** Shooter portrait (left, same dimensions), center panel with foul event text + `+ Free Throw` + `And one`, fouler portrait (right, **100×130px** with red border). Caption bars show jersey + last name; fouler caption uses red tint.

**No-player announcements (primary):**
- When `photoUrl` and `lastName` are both empty, the portrait zone is hidden (`.ann-card.standard-card.no-player .ann-portrait-zone { display: none }`) and the event text is centered. After the secondary-tier migration, this state is reached only for rare neutral / team-level events such as `DOUBLE TEAM!` and `Batted Ball Out Of Bounds!`. Press/Trap/Fast Break/Slow It Down/Quick Shot/Final Shot now render in the secondary tier instead.

#### Secondary — Top-Edge Ribbon

**Ribbon:**
- 64px tall, full width of `#phaser-container` with 16px gutters, anchored `top: 4px` (just under the scoreboard). z-index `940` (below primary's `950`).
- Left edge: 6px solid stripe in the **initiating team's `primary_color`** with a colored glow. Surface uses a dark `rgba(10,10,10,0.92)` gradient with the team color mixed in at both edges (`color-mix(in oklab, var(--sec-team), #000 70%)`).
- **Headline** (`.sec-headline`) uses **Bebas Neue** italic, 36px (40px in no-player state), uppercase, with the orange `!` accent shared with primary.
- **With player:** 48×48 rounded headshot block (team-color background, white-alpha border) + chip (`#jersey` in team color above last name in white, both Bebas Neue).
- **No-player state:** headshot/chip column is hidden and the headline takes the full surface (`grid-template-columns: 1fr`).
- **Decision pill** (`.sec-decision-pill`) — same gold-gradient (good) / red (bad) vocabulary as the primary `.ann-decision-pill`, anchored to the lower-right corner of the ribbon. Hidden unless both `decisionPillText` and a valid `decisionPillTone` (`'good'` | `'bad'`) are provided.
- **Motion:** entry slides from `translateY(-110%)` to `0` with fade-in (`260ms cubic-bezier(.22,1,.36,1)` transform, `220ms ease` opacity); exit reverses. `secPulse` keyframe (`scale 0.96 → 1.02 → 1.00`) on the headline at 60ms delay. `@media (prefers-reduced-motion: reduce)` drops all transforms and the headline animation, keeping only the opacity fade.

#### Player images and labels (both tiers)

- Callers pass `playerData` with `playerId` (string) and optional `photo`. In `announcements.js`, `getPlayerImageUrl(photo, playerId)` resolves the portrait URL in this priority order:
  1. Explicit `photo` path on the caller's `playerData` (if provided).
  2. `/images/players/{playerId}.png` (resolved via `API_CONFIG.buildStaticPath` so localhost/production paths both work) when a `playerId` is available.
  3. `generic_headshot.png` when no `playerId` is supplied.
- **Fallback when the per-player photo fails to load:** The image element in `court.html` (both primary and secondary tiers) applies an `onerror` handler via `applyHeadshotFallback(imgEl, src, initialsInfo)`. When `initialsInfo` is supplied (the standard case for any announcement built by `showAnnouncement`, `showSecondaryAnnouncement`, or `showAndOneAnnouncement`), the failed `<img>` is hidden and replaced with a sibling `<div class="ann-headshot-initials">` showing the player's initials. The same fallback function is also used by the Playcall Center (play-option, reveal HUD, hover tooltip — see `Player_Sprite_System.md` for the full list of surfaces).
- **Initials tile colors** — shared rule across sprites, announcements, and Playcall Center:
  - **Home** player → tile fill = team **primary**, text = team **secondary**
  - **Away** player → tile fill = **white** (`#ffffff`), text = team **primary**
- Each headshot resolves its own team independently — important in the foul card where shooter and fouler are on opposite teams; each side gets its own initials-tile color rule.
- **Team param vs initials (important):** The `team` argument on `showAnnouncement()` / `showSecondaryAnnouncement()` / `showAndOneAnnouncement()` describes **announcement context** (offense side, defense side, beneficiary team for ribbon/stripe styling). It must **not** be used to infer which colors a featured player's initials tile wears. When `playerData.playerId` is present, initials colors are resolved per-player by `resolvePlayerTeamSide()` → `buildHeadshotInitialsForPlayer()` in `announcements.js`, in this order:
  1. On-court sprite `team` (`'home'` | `'away'`) from `scene.playerSprites`
  2. Sprite / playerData `team_id` compared to `scene.simData.home_team_id`
  3. Roster membership (`gameStore.getRosters()` home vs away lists)
  4. Fallback to the caller's `team` arg only when membership cannot be determined
- Scene lookup uses `meta.scene` when provided, otherwise `window.currentGameScene` (set in `gameScene.js`). Callers that run outside the live Phaser scene should pass `{ scene }` in `meta`.
- Foul announcements historically passed the **beneficiary** side as `team` (e.g. defensive foul card used `offenseTeam` because offense "benefited"). That was correct for ribbon context but caused swapped initials before the per-player resolver above. No caller changes are required — initials now ignore that context when sprite/roster data is available.
- The `initialsInfo` descriptor (`{isHome, primaryColor, secondaryColor, name}`) is built per-headshot by `buildHeadshotInitialsForPlayer()` and attached to the overlay payload as `headshotInitials` (primary/secondary single-player) or `shooterHeadshotInitials` / `foulerHeadshotInitials` (foul card). The Playcall Center has its own resolver, `buildPlaycallInitialsInfo(playerId)` in `court.html`, which sources the same data (`window.currentGameScene.playerInfo` + `window.gameStore.getColors()`) for user-team players.
- If `initialsInfo` is unresolvable (no team colors in `gameStore`, or `applyHeadshotFallback` called without it), the legacy generic-headshot fallback still runs — no broken-image icon either way.
- Jersey and last name are resolved by `getPlayerJerseyValue()` / `getPlayerLastName()` from `gameStore` rosters or the passed `playerData`. The primary overlay displays `#jersey lastName` in the portrait caption; the secondary ribbon shows them stacked in the chip (`#jersey` above last name).
- If no player data is provided (no `photoUrl` and no `lastName` in the payload), both tiers collapse their player column and center the headline (`.no-player` state).

### Key Files

**Frontend:**
- `FrontEnd/static/court.html`
  - `#announcement-overlay` — HTML for standard and foul **primary** overlay cards (inside `#phaser-container`).
  - `#announcement-overlay-secondary` — HTML for the **secondary** top-edge ribbon (sibling of `#announcement-overlay`).
  - CSS for `.ann-card`, `.ann-portrait-zone`, `.ann-event-zone`, `.ann-foul-event-zone`, `.ann-decision-pill`, `.no-player` state, plus the secondary `.sec-*` classes (`.sec-stripe`, `.sec-surface`, `.sec-player`, `.sec-headshot`, `.sec-chip`, `.sec-headline`, `.sec-decision-pill`).
  - `window.showAnnouncementOverlay(data)` — Inline IIFE; dispatches on `data.tier` to `window.showSecondaryAnnouncementOverlay(data)` (secondary) or the primary path (default). Each tier owns an independent timer; 2200 ms display.
- `FrontEnd/static/js/phaser/animation/turnPreparation.js`
  - `prepareTurnForAnimation()` — Dispatches start announcements via `announceGameEvent()` (Fast Break, Press, Trap, Slow It Down, Quick Shot, Final Shot, Batted Ball OOB) gated by `turn._contextAnnouncementsShown`.
  - `finalizeTurnAfterAnimation()` — Result-side fallbacks (e.g. BLOCK when `!turn._blockAnnounced`, STEAL, TURNOVER).
- `FrontEnd/static/js/phaser/utils/announcements.js`
  - `announceFromTurnData(turnData, timing, homeTeamId, scene)` — Legacy end-of-turn dispatcher; still called with `timing: 'end'` from `animateGameTurns.js`. Uses `offense_team_id` (SS&S canonical) with `possession_team_id` fallback. Passes `{ scene }` in meta when resolving player initials. The `timing: 'start'` branch is currently unreachable but is routed to secondary if revived.
  - `announceReboundHeadlineIfNeeded(scene, turnData, rebounderSprite, rebounderId)` — Single entry point for primary **Rebound!**; sets `turnData._reboundHeadlineShown` when `turnData` is provided.
  - `showAnnouncement(text, team, playerData, meta)` — Builds **primary** standard payload and calls `window.showAnnouncementOverlay(data)`.
  - `showSecondaryAnnouncement(text, team, playerData, meta)` — Builds **secondary** payload (`tier: 'secondary'`), resolves the team primary color via `gameStore.getColors()` (`resolveSecondaryStripeColor`), and calls `window.showAnnouncementOverlay(data)`.
  - `showAndOneAnnouncement(team, shooterData, foulPlayerData, meta)` — Builds primary foul-card payload.
  - `getPlayerImageUrl(photo, playerId)` — Uses explicit portrait paths when provided; otherwise falls back to `generic_headshot.png`. When the resolved URL fails to load, `court.html`'s `applyHeadshotFallback` swaps in the team-aware initials tile (see "Player images and labels" above).
  - `resolvePlayerTeamSide(scene, playerId, playerData, fallbackTeamSide)` — Resolves `'home'` | `'away'` from sprite, team_id, or roster; used exclusively for initials-tile colors.
  - `buildHeadshotInitialsForPlayer(scene, player, playerId, fallbackTeamSide)` — Wraps `buildHeadshotInitialsInfo()` with per-player team resolution. Used by all three `show*Announcement` builders.
  - `buildHeadshotInitialsInfo(player, teamSide)` — Low-level color/name descriptor from an already-resolved side + `gameStore.getColors()`.
  - `playAnnouncementSfx(kind)` — Plays `whistle-3.mp3` for `'shot_clock_violation'`, otherwise `whistle-1-lowervol.wav` at volume 0.7.
- `FrontEnd/static/js/phaser/utils/gameAnnouncements.js`
  - `announceGameEvent(eventType, turnData, scene, context)` — Central event router. Cases: `SHOT_MAKE`, `SHOT_MAKE_AND_ONE`, `FT_MAKE`, `FT_MISS`, `REBOUND` (delegates to `announceReboundHeadlineIfNeeded`, respects `_reboundHeadlineShown`), `FOUL_SHOOTING`, `FOUL_OFFENSIVE`, `FOUL_DEFENSIVE`, `CHARGE`, `BLOCKING_FOUL`, `BLOCK`, `STEAL`, `TURNOVER`, `PRESSURE_FCP`, `PRESSURE_HCT`, `FAST_BREAK`, `RIM_RUNNER_BATTED_OOB`, `SLOW_IT_DOWN`, `QUICK_SHOT`, `FINAL_SHOT`, `DEFENSIVE_STOP`, `DOUBLE_TEAM`.
  - Secondary-tier cases (`PRESSURE_FCP`, `PRESSURE_HCT`, `FAST_BREAK`, `SLOW_IT_DOWN`, `QUICK_SHOT`, `FINAL_SHOT`, `DEFENSIVE_STOP`) call `showSecondaryAnnouncement()`; everything else calls `showAnnouncement()` / `showAndOneAnnouncement()`.
- `FrontEnd/static/js/phaser/animation/ballManager.js`
  - Shot make announcements (`"It's Good!"`, `"It's Good! And 1!"`) emitted when the ball reaches the rim.
  - `animateRebound` — calls `announceReboundHeadlineIfNeeded` when the rebounder tween completes (pass `turnData` from the MISS/BLOCK/rebound turn for idempotency).
- `FrontEnd/static/js/phaser/animation/fastBreak.js`
  - Fast-break secondary announcements: `animateRimRunnerLanePass()` (`"Fast Break!"` with RR decision pill), `animateRimRunnerHoldUpLeadIn()` (`"No Fast Break"` with decision pill), `animateRimRunnerOutletDeniedBeat()` (`"FB Outlet Pass Denied!"`), and the FB defensive stop block (`"Great Stop!"`).
  - Fast-break shot results: `animateFastBreakShot()` and `animateFastBreakShotWithStopper()` emit `"Fast Break Score!"`, AND-1, and `"Shooting Foul!"` (on miss) directly — separate path from `ballManager` / `ShotAnimationSystem`.
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`
  - `handleMissedShot()` — emits `BLOCK` via `announceGameEvent('BLOCK', ...)` when `result_type === 'BLOCK'`, before the rebound; sets `turnData._blockAnnounced = true`. Also emits `FOUL_SHOOTING` when a shooting foul is detected on the miss.
  - `handleEmbeddedRebound()` — calls `announceReboundHeadlineIfNeeded` in the rebounder tween `onComplete` (after attach + rebound SFX) for both DREB and OREB; `handleDefensiveRebound` no longer duplicates the headline before outlet setup.
  - HCO make path emits `"It's Good!"` / AND-1 in unison with the rim hold (single 1000ms period).
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js`
  - Discrete **`DREB`** + `animation_steps`: after **`playTurn`**, **`_maybeRunDiscreteDrebOutletLeadIn`** runs **`runDefensiveReboundSetup`** when next is **HCO/HCT/FCP** (outlet / bring-up — not an announcement). Cross-ref: `Turn_by_Turn_System.md`, `Rebound_System.md`.
- `FrontEnd/static/js/phaser/animation/FreeThrowAnimationSystem.js`
  - Free-throw make announcements; also dispatches `PRESSURE_FCP` / `PRESSURE_HCT` (secondary) when the next defensive setup applies pressure after a final FT.
  - Final FT miss → `animateRebound` passes `turnData` so **Rebound!** uses the same idempotent flag as other paths.
- `FrontEnd/static/js/phaser/animation/ReboundAnimationSystem.js`
  - Standalone `REBOUND` turns: after ball attach + rebound SFX, calls `announceReboundHeadlineIfNeeded` (DREB and OREB sequences).
- `FrontEnd/static/js/phaser/utils/foulAnnouncementLanguage.js`
  - Weighted language tables for offensive / defensive non-shooting fouls; `isLaneFoulContext(turnData)` selects between non-lane and lane pools.

**Backend:**
- `BackEnd/engine/phase_resolution.py`, `BackEnd/models/shot_manager.py`, `BackEnd/engine/rim_runner_fast_break.py` — Set the `is_steal_entry` flag on Fast Break turns originating from a steal.
- `BackEnd/models/turn_manager.py` — Populates turn data with announcement triggers.

### Foul Taxonomy (Future Event Mapping)

Use this list as the canonical taxonomy for future event-specific micro-animations paired with announcements.

**Offensive Fouls**
Language Guidance For Offensive Fouls in Announcement System (non lane players / lane location)
- Push Off (30 / 10)
- Illegal Screen (20 / 10) (ball handler excluded)
- Arm Extension (15 /10)
- Hooking (5 / 5)
- Illegal Use Of Hands (10 / 5)
- Elbowing (20 / 20)
- Illegal Post Up (0 / 40)

**Defensive Non-Shooting Fouls**
- Blocking Foul (25 / 5)
- Hand-Checking (25 / 0)
- Illegal Contact (10 / 10)
- Holding (15 / 20)
- Arm Bar (15 / 10)
- Pushing (10 / 30)
- Illegal Post Defense (0 / 25)

Lane locations = lower and upper lowPost, midPost, highPost, basketSpot, midLane, topLane

All Force Fouls announce "Quick Foul!"
