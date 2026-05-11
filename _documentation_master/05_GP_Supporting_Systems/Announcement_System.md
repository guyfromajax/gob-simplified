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

3. **Idempotent Flags**:
   - `turn._contextAnnouncementsShown` - Prevents duplicate start announcements

4. **Announcement hold time**:
   - **1000 ms** — Uniform delay for result announcements before the next animation. In **ShotAnimationSystem** (HCO/regular makes), the rim hold and "It's Good!" / AND-1 run **in unison**: one 1000 ms period with ball at rim and announcement both visible. Other paths (ballManager made shot, FT make, FB make, "Great Stop!") use a 1000 ms hold after the announcement. Do not reduce when tuning other animation delays; see "Hold time after result announcements" below.

**Announcement System Flow (2 Phases)**

1. **Start Announcements** (`timing='start'`)
   - **"Press!"** - FCP pressure applied (BASELINE_INBOUND with `next_defensive_setup='FCP'`)
   - **"Trap!"** - HCT pressure applied (BASELINE_INBOUND with `next_defensive_setup='HCT'`)
   - **"Fast Break!"** - Fast break initiated (only if not following a steal)
     - Suppressed if `turn.roles?.is_steal_entry` is true (steal announcement takes priority)

2. **End Announcements** (`timing='end'`)
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
   - **"Rebound!"** - Defensive rebound (ballManager.js / ShotAnimationSystem when ball reaches rebounder)

**Long Form Documentation**

### Overview

The Announcement System provides visual feedback for game events using timing-based separation. Context announcements (situation being entered) appear at turn start, while result announcements (outcome of turn) appear at turn end. The system uses idempotent flags to prevent duplicate announcements when functions are called multiple times.

### Start Announcements (Context)

**Location:** `FrontEnd/static/js/phaser/animation/turnPreparation.js` - `prepareTurnForAnimation()` (lines 89-112)

**Announcements:**
- **"Press!"** - Triggered when `result_type === 'BASELINE_INBOUND'` and `next_defensive_setup === 'FCP'`
- **"Trap!"** - Triggered when `result_type === 'BASELINE_INBOUND'` and `next_defensive_setup === 'HCT'`
- **"Fast Break!"** - Triggered when `turn.fast_break` is true, but suppressed if:
  - `result_type === 'STEAL'`
  - Text includes "steal"
  - `turn.roles?.is_steal_entry` is true (steal-initiated Fast Break)

**Implementation:** Uses `announceGameEvent()` dispatcher from `gameAnnouncements.js` to route to appropriate handlers.

### End Announcements (Results)

**Location:** `FrontEnd/static/js/phaser/utils/announcements.js` - `announceFromTurnData()` (lines 334-493)

**Shot Results:**
- **"It's Good!"** - Handled in `ballManager.js` when ball reaches rim (line 542); **Fast Break** shots use `fastBreak.js` (see below).
- **"It's Good! And 1!"** - Detected when text includes "AND-1" OR (`foul_player_id` exists + `result === "MAKE"` + `foul_team === "DEFENSE"`)
  - Uses `showAndOneAnnouncement()` for two-row announcement with shooter and fouler headshots
  - Both player images display `#jersey lastName` directly beneath the headshot when that data is available
  - Fallback: Single-row announcement if player data missing
- **"Shooting Foul!"** - Detected on shot-result turns (`result_type === "MISS"` with shooting-foul context from the shot pipeline)
  - Always displays announcement even if player sprite/info is missing (fallback pattern)
  - Dark yellow text with silver border

**Fast Break shot path:** Fast Break shots are animated only in `fastBreak.js` (`animateFastBreakShot`, `animateFastBreakShotWithStopper`). They use `animateShotToRim()` and do **not** go through `ballManager.shootBall()` or ShotAnimationSystem. Therefore **AND-1** and **"Shooting Foul!"** (on miss) must be detected and announced inside `fastBreak.js` using the same logic as in `ballManager.js` (same `turnData` fields and `showAnnouncement` / `showAndOneAnnouncement` / `triggerFoulEffect`).

**Steal Announcements:**
- **"STEAL!"** - Triggered when `result_type === 'STEAL'` or (`result_type === 'TURNOVER'` and text includes "steal")
- Takes priority over Fast Break announcement (suppresses Fast Break if steal-initiated)
- Shows stealer's headshot in defense team color

**Turnover Announcements:**
- **Dead Ball Turnovers:** Randomly displays "Travel!" or "Double Dribble!" (50/50 chance)
  - Triggered when `result_type === 'DEAD BALL'` or (`result_type === 'TURNOVER'` without steal indicators)
- **Other Turnovers:** Parsed from `turnover_type` field or text:
  - "OUT OF BOUNDS!", "BAD PASS!", "PALMING!", "ILLEGAL DRIBBLE!", "SHOT CLOCK VIOLATION!", "BACKCOURT VIOLATION!"
- **Shot Clock Violation:** Displays "Shot Clock Violation!" (when `turnover_type === 'SHOT_CLOCK'`). Uses **whistle-3.mp3** (see Sounds below).
- Shows victim's headshot in offense team color

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
- **"Rebound!"** - Handled in `ballManager.js` / `ShotAnimationSystem.handleEmbeddedRebound` when ball reaches rebounder
- Shows rebounder's headshot in rebounder's team color

### Sounds (SFX)

| Announcement | Sound file | Location |
|--------------|------------|----------|
| **Shot Clock Violation!** | `whistle-3.mp3` | `announcements.js` – `showAnnouncement()` when `text === 'Shot Clock Violation!'` |
| Dead ball turnovers (Travel!, Double Dribble!, etc.), foul announcements | `whistle-1.mp3` | `announcements.js` – `showAnnouncement()` for foul or dead-ball turnover text |
| AND-1 (shooting foul on make) | `whistle-1.mp3` | `announcements.js` – `showAndOneAnnouncement()` |

Sounds are played in sync with the on-screen announcement (volume 0.7). Path: `/sounds/` + filename.

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

**Problem:** `prepareTurnForAnimation()` and `announceFromTurnData()` may be called multiple times (from `animateGameTurns` and `AnimationRouter`).

**Solution:** Uses flags to prevent duplicate announcements:
- `turn._contextAnnouncementsShown` - Set after start announcements are shown

**Benefits:**
- ✅ No duplicate announcements
- ✅ Safe to call functions multiple times
- ✅ Works across all turn types

### Steal → Fast Break Flow

When a steal leads to a fast break:
1. Backend sets `turn.roles?.is_steal_entry = true` on Fast Break turn
2. Frontend checks this flag in `prepareTurnForAnimation()`
3. If `is_steal_entry` is true, Fast Break announcement is suppressed
4. Only "STEAL!" announcement is shown (takes priority)

**Implementation:** `FrontEnd/static/js/phaser/animation/turnPreparation.js` (lines 95-100)

### Visual Styling (Center-Court Overlay)

**Overlay card:**
- Dark semi-opaque background (`rgba(10,10,10,0.82)`), orange left accent bar (`#F79420`), subtle shadow. Barlow Condensed for all text.
- **Standard card:** Portrait zone (100×130px, diagonal cut on right), caption bar at bottom of portrait with `#jersey lastName` and position label (orange). Event text (large italic, white, optional orange accent on trailing "!").
- **Foul card:** Shooter portrait (left), center panel with foul event text and "+ Free Throw" / "And one", fouler portrait (right, red border). Caption bars show jersey + last name; fouler caption uses red tint.

**No-player announcements:**
- When `photoUrl` and `lastName` are both empty, the portrait zone is hidden (`.ann-card.standard-card.no-player .ann-portrait-zone { display: none }`) and the event text is centered. Used for: Trap!, Press!, Fast Break!, Slow It Down, Quick Shot, Final Shot, DOUBLE TEAM!

**Player images and labels:**
- Callers pass `playerData` with `playerId` (string) and optional `photo`. In `announcements.js`, `getPlayerImageUrl()` treats player portraits as **opt-in**:
  - if an explicit `photo` path is provided, use it
  - otherwise use `generic_headshot.png`
- The announcement system does **not** assume `/images/players/{playerId}.png` exists for every player.
- `court.html` also applies an image `onerror` fallback to `generic_headshot.png`, so bad or missing portrait paths degrade cleanly instead of rendering a broken-image icon.
- Jersey and last name are resolved from `gameStore` rosters or `playerData`. The overlay displays `#jersey lastName` in the portrait caption. If no player data is provided, the overlay hides the portrait zone (see above).

### Key Files

**Frontend:**
- `FrontEnd/static/court.html`
  - `#announcement-overlay` — HTML for standard and foul **primary** overlay cards (inside `#phaser-container`)
  - `#announcement-overlay-secondary` — HTML for the **secondary** top-edge ribbon (sibling of `#announcement-overlay`)
  - CSS for `.ann-card`, `.ann-portrait-zone`, `.ann-event-zone`, `.ann-foul-event-zone`, `.no-player` state, plus the secondary `.sec-*` classes (`.sec-stripe`, `.sec-surface`, `.sec-player`, `.sec-headshot`, `.sec-chip`, `.sec-headline`, `.sec-decision-pill`)
  - `window.showAnnouncementOverlay(data)` — Inline IIFE; dispatches on `data.tier` to `window.showSecondaryAnnouncementOverlay(data)` (secondary) or the primary path (default). Each tier owns an independent timer; 2200 ms display.
- `FrontEnd/static/js/phaser/animation/turnPreparation.js`
  - `prepareTurnForAnimation()` - Start announcements (lines 89-112)
  - `finalizeTurnAfterAnimation()` - End announcements (if needed)
- `FrontEnd/static/js/phaser/utils/announcements.js`
  - `announceFromTurnData()` - Main announcement dispatcher (lines 290-493)
  - `showAnnouncement(text, team, playerData, meta)` - Builds standard **primary** payload, calls `window.showAnnouncementOverlay(data)`
  - `showSecondaryAnnouncement(text, team, playerData, meta)` - Builds **secondary** payload with `tier: 'secondary'`, resolves the team primary color via `gameStore.getColors()`, calls `window.showAnnouncementOverlay(data)`
  - `showAndOneAnnouncement(team, shooterData, foulPlayerData)` - Builds foul (primary) payload, calls `window.showAnnouncementOverlay(data)`
  - `getPlayerImageUrl(photo, playerId)` - Uses explicit portrait paths when available; otherwise falls back to `generic_headshot.png`
- `FrontEnd/static/js/phaser/utils/gameAnnouncements.js`
  - `announceGameEvent()` - Event-based announcement router (lines 24-125)
  - Handlers for specific event types (shot makes, fouls, steals, turnovers)
- `FrontEnd/static/js/phaser/animation/ballManager.js`
  - Shot result announcements when ball reaches rim (lines 476-598)
  - Rebound announcements when ball reaches rebounder (lines 822-839)
- `FrontEnd/static/js/phaser/animation/fastBreak.js`
  - Fast Break shot result announcements (AND-1, "Shooting Foul!" on miss) in `animateFastBreakShot` and `animateFastBreakShotWithStopper` (separate path from ballManager)
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`
  - BLOCK announcement at start of `handleMissedShot` when `result_type === 'BLOCK'` (before bounce/rebound)
  - Rebound announcement in `handleEmbeddedRebound` (e.g. before outlet setup)

**Backend:**
- `BackEnd/engine/phase_resolution.py` - Sets `is_steal_entry` flag for steal-initiated Fast Breaks
- `BackEnd/models/turn_manager.py` - Populates turn data with announcement triggers

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
