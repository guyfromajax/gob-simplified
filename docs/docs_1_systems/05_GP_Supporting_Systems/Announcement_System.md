## Announcement System ✅ **SS&S** (January 2025)

**Base Constants**

1. **Timing Types**:
   - `timing='start'` - Context announcements (situation being entered)
   - `timing='end'` - Result announcements (outcome of turn)

2. **Visual Styling**:
   - **Foul Announcements:** Dark yellow text (`#b8860b`) with silver border (`#c0c0c0`)
   - **All Other Announcements:** Dark silver text (`#a8a8a8`) with black border (`#000000`)
   - **Special Cases:** "DOUBLE TEAM!" uses red text (`#ff0000`)

3. **Idempotent Flags**:
   - `turn._contextAnnouncementsShown` - Prevents duplicate start announcements

**Announcement System Flow (2 Phases)**

1. **Start Announcements** (`timing='start'`)
   - **"Press!"** - FCP pressure applied (BASELINE_INBOUND with `next_defensive_setup='FCP'`)
   - **"Trap!"** - HCT pressure applied (BASELINE_INBOUND with `next_defensive_setup='HCT'`)
   - **"Fast Break!"** - Fast break initiated (only if not following a steal)
     - Suppressed if `turn.roles?.is_steal_entry` is true (steal announcement takes priority)

2. **End Announcements** (`timing='end'`)
   - **"It's Good!"** - Made shot (ballManager.js, when ball reaches rim)
   - **"It's Good! And 1!"** - Made shot with shooting foul (two-row announcement with shooter and fouler headshots)
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
- **"It's Good!"** - Handled in `ballManager.js` when ball reaches rim (line 542)
- **"It's Good! And 1!"** - Detected when text includes "AND-1" OR (`foul_player_id` exists + `result === "MAKE"` + `foul_team === "DEFENSE"`)
  - Uses `showAndOneAnnouncement()` for two-row announcement with shooter and fouler headshots
  - Fallback: Single-row announcement if player data missing
- **"Shooting Foul!"** - Detected when `foul_player_id` exists, `foul_team === "DEFENSE"`, and `result === "MISS"`
  - Always displays announcement even if player sprite/info is missing (fallback pattern)
  - Dark yellow text with silver border

**Steal Announcements:**
- **"STEAL!"** - Triggered when `result_type === 'STEAL'` or (`result_type === 'TURNOVER'` and text includes "steal")
- Takes priority over Fast Break announcement (suppresses Fast Break if steal-initiated)
- Shows stealer's headshot in defense team color

**Turnover Announcements:**
- **Dead Ball Turnovers:** Randomly displays "Travel!" or "Double Dribble!" (50/50 chance)
  - Triggered when `result_type === 'DEAD BALL'` or (`result_type === 'TURNOVER'` without steal indicators)
- **Other Turnovers:** Parsed from `turnover_type` field or text:
  - "OUT OF BOUNDS!", "BAD PASS!", "PALMING!", "ILLEGAL DRIBBLE!", "SHOT CLOCK VIOLATION!", "BACKCOURT VIOLATION!"
- Shows victim's headshot in offense team color

**Foul Announcements:**
- **"Charge!"** - Triggered when `result_type === 'CHARGE'` (offensive foul on drive). Routed via gameAnnouncements.js; AnimationEngine routes CHARGE to handleDefault (skeleton animation, then announcement).
- **"BLOCKING FOUL!"** - Triggered when `result_type === 'FOUL'`, `foul_team === 'DEFENSE'`, and text contains "blocking foul" (non-shooting defensive foul on drive).
- **"OFFENSIVE FOUL!"** / **"DEFENSIVE FOUL!"** - Other non-shooting fouls (foul_team OFFENSE or DEFENSE, not blocking).
- Shows fouling player's headshot. Skips if shooting foul (already handled in shot result announcements).

**Block Announcements:**
- **"BLOCK!"** - Announced in `ShotAnimationSystem.handleMissedShot` when `result_type === 'BLOCK'` (when ball has reached block spot), **before** the rebound is announced, so order is always Block → Rebound. Shows blocker's headshot. Routed via `announceGameEvent('BLOCK', ...)` in `gameAnnouncements.js`. Fallback: `finalizeTurnAfterAnimation` announces BLOCK only if `!turn._blockAnnounced`.

**Rebound Announcements:**
- **"Rebound!"** - Handled in `ballManager.js` / `ShotAnimationSystem.handleEmbeddedRebound` when ball reaches rebounder
- Shows rebounder's headshot in rebounder's team color

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

### Visual Styling

**Foul Announcements:**
- Text color: Dark yellow (`#b8860b`)
- Border color: Silver (`#c0c0c0`)
- Applied to: Shooting fouls, offensive fouls, defensive fouls

**All Other Announcements:**
- Text color: Dark silver (`#a8a8a8`)
- Border color: Black (`#000000`)
- Applied to: Shot results, steals, turnovers, rebounds, pressure announcements

**Special Cases:**
- "DOUBLE TEAM!" uses red text (`#ff0000`)

**Player Headshots:**
- Displayed for: Steals, turnovers, fouls, AND-1 situations
- Fallback: Announcement still displays even if player data is missing (matches AND-1 pattern for consistency)

### Key Files

**Frontend:**
- `FrontEnd/static/js/phaser/animation/turnPreparation.js`
  - `prepareTurnForAnimation()` - Start announcements (lines 89-112)
  - `finalizeTurnAfterAnimation()` - End announcements (if needed)
- `FrontEnd/static/js/phaser/utils/announcements.js`
  - `announceFromTurnData()` - Main announcement dispatcher (lines 290-493)
  - `showAnnouncement()` - Visual announcement display (lines 169-281)
  - `showAndOneAnnouncement()` - Special AND-1 two-row announcement
- `FrontEnd/static/js/phaser/utils/gameAnnouncements.js`
  - `announceGameEvent()` - Event-based announcement router (lines 24-125)
  - Handlers for specific event types (shot makes, fouls, steals, turnovers)
- `FrontEnd/static/js/phaser/animation/ballManager.js`
  - Shot result announcements when ball reaches rim (lines 476-598)
  - Rebound announcements when ball reaches rebounder (lines 822-839)
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`
  - BLOCK announcement at start of `handleMissedShot` when `result_type === 'BLOCK'` (before bounce/rebound)
  - Rebound announcement in `handleEmbeddedRebound` (e.g. before outlet setup)

**Backend:**
- `BackEnd/engine/phase_resolution.py` - Sets `is_steal_entry` flag for steal-initiated Fast Breaks
- `BackEnd/models/turn_manager.py` - Populates turn data with announcement triggers

