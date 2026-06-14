## Possession Management System ✅ **SS&S** (January 2025)

**Base Constants**

1. **Single Source of Truth**: Each turn's `offense_team_id` field
2. **Internal Flag**: `possession_flips` - Boolean flag telling backend when to call `switch_possession()`
3. **Possession Flip Locations** (`simulate_macro_turn()`; line numbers approximate, verified 2026-06-13):
   - **SIP Transitions**: flips BEFORE `setup_side_inbound()` (line ~1338)
   - **DREB → HCO**: Flips before HCO turn creation (line ~1199)
   - **DREB → Fast Break**: Flips before Fast Break turn creation (line ~1213)
   - **OREB Transitions**: Flips after OREB turn creation (line ~1014)
   - **Made Shot → BIP**: Flips before BASELINE_INBOUND turn creation (line ~1454)
4. **Key Files**:
   - `BackEnd/models/game_manager.py` - Backend possession management and flip logic
   - `BackEnd/models/turn_manager.py` - Sets `offense_team_id` in turn results
   - `FrontEnd/static/js/phaser/animation/turnPreparation.js` - Frontend possession handling (`handleTurnTransition()`)
   - `FrontEnd/static/js/phaser/utils/possessionManager.js` - Possession change event handling

**Possession Management System Flow (Backend - 4 Steps)**

1. **Turn Resolution**: Backend resolves turn and sets `result["offense_team_id"] = game.offense_team.team_id` (team on offense DURING this turn)
2. **Possession Flip Check**: Backend checks `result.get("possession_flips")` flag to determine if possession should change
3. **Possession Flip Execution**: If `possession_flips=True`, backend calls `game.switch_possession()` at appropriate location (depends on transition type)
4. **Turn Result Update**: Backend updates `result["offense_team_id"]` to NEW offense team (after flip) and sets `possession_flips=False` to prevent double flip

**Possession Management System Flow (Frontend - 3 Steps)**

1. **Read Turn Data**: Frontend reads `turnData.offense_team_id` from each turn
2. **Update Scene State**: Frontend sets `scene.offenseTeamId = turnData.offense_team_id` (simple assignment, no flip logic)
3. **Emit Event**: Frontend emits `possessionChange` event if value changes from previous turn

**Long Form Documentation**

### Overview

The Possession Management System uses a **Single Source of Truth (SS&S)** architecture where each turn's `offense_team_id` field is the authoritative source for which team has possession. The backend handles all possession flips internally using the `possession_flips` flag, while the frontend simply reads and displays the `offense_team_id` value.

**Status:** ✅ Fully implemented with SS&S pattern

### Single Source of Truth

**Each turn's `offense_team_id` field** is the single source of truth for possession. This field:
- Is set by the backend during turn resolution
- Represents the team on offense **DURING** that specific turn
- Is read by the frontend to determine which team to display as offense
- Works for ALL turn types (HCO, FCP, HCT, FREE_THROW, BASELINE_INBOUND, SIDE_INBOUND, FAST_BREAK, etc.)

### Backend Responsibility

**Sets `offense_team_id`:**
- Backend sets `result["offense_team_id"] = game.offense_team.team_id` during turn resolution
- This represents the team on offense **DURING** the turn being resolved
- Location: `BackEnd/models/turn_manager.py` - Various turn resolution functions

**Uses `possession_flips` as INTERNAL flag:**
- `possession_flips` is a boolean flag that tells the backend when to call `switch_possession()`
- It is **NOT** sent to frontend (prevents frontend from doing its own flip logic)
- Flag is cleared after flipping to prevent double flips

**Possession Flip Locations:**

1. **SIP Transitions** (`game_manager.py` `simulate_macro_turn()` line ~1338):
   - Flips BEFORE `setup_side_inbound()` is called
   - Handles offensive fouls and dead ball turnovers
   - Checks `result.get("possession_flips")` and flips if True
   - Clears flag after flipping to prevent frontend double flip
   - **Important:** 
     - The HCO turn result has `offense_team_id` set to the team that was on offense **DURING** that turn (before flip)
     - The SIP turn result has `offense_team_id` set to the **NEW** offense team (after flip)

2. **DREB → HCO** (`game_manager.py` `simulate_macro_turn()` line ~1199):
   - Flips before HCO turn creation
   - Handles: MISS with DREB → HCO, STEAL → HCO (direct, not via Fast Break)
   - **SS&S FIX:** Only flips if `possession_flips is True` (prevents double flip for Fast Break → HCO)
   - **ANIMATION FIX (current behavior):** Does **NOT** mutate `result["offense_team_id"]` here. The result (DREB) turn deliberately **keeps `offense_team_id` = old team** so the frontend classifies offense/defense correctly for that turn's step animation (e.g. pass steps animate in sync). The new offense team is reflected by the updated `game.offense_team` state on the **next** (HCO) turn, not by rewriting this turn's id.

3. **DREB → Fast Break** (`game_manager.py` `simulate_macro_turn()` line ~1213):
   - Flips before Fast Break turn creation
   - Handles: MISS with DREB → Fast Break, STEAL → Fast Break
   - **ANIMATION FIX (current behavior):** Same as DREB → HCO — does **NOT** mutate `result["offense_team_id"]`; the result turn keeps `offense_team_id` = old team for animation sync, and the new offense team appears on the next (Fast Break) turn via `game.offense_team` state.

4. **OREB Transitions** (`game_manager.py` `simulate_macro_turn()` line ~1014):
   - Flips after OREB turn creation
   - Handles offensive rebound putback scenarios
   - Clears flag after flipping

5. **Made Shot → BIP** (`game_manager.py` `simulate_macro_turn()` line ~1454):
   - Flips before BASELINE_INBOUND turn creation
   - Handles made shot transitions
   - Clears flag after flipping

**After turn completes:**
- Backend calls `game.switch_possession()` if `possession_flips=True` (location depends on transition type)
- Next turn automatically has correct `game.offense_team` (updated state)
- `offense_team_id` in next turn reflects the new offense team

### Frontend Responsibility

**Reads `offense_team_id`:**
- Frontend reads `turnData.offense_team_id` from each turn
- Location: `FrontEnd/static/js/phaser/animation/turnPreparation.js` - `handleTurnTransition()` function

**Sets scene state:**
- Frontend sets `scene.offenseTeamId = turnData.offense_team_id` (simple assignment, no flip logic)
- This is a direct assignment - frontend does NOT perform any flip calculations

**Emits possession change event:**
- Frontend emits `possessionChange` event if `offense_team_id` value changes from previous turn
- Event payload: `{ offenseTeamId: newOffenseTeamId }`
- Location: `FrontEnd/static/js/phaser/animation/turnPreparation.js` (`handleTurnTransition` ~line 229; emit ~line 242)

**Key Principle:**
- Frontend **never** performs possession flips
- Frontend **only** reads and displays the `offense_team_id` value provided by backend
- This ensures single source of truth and prevents double-flip bugs

### Benefits

- ✅ **No double flips**: Backend flips once, frontend just displays
- ✅ **No confusion**: One value, one source (`offense_team_id`)
- ✅ **Works for ALL turn types**: HCO, FCP, HCT, FREE_THROW, BASELINE_INBOUND, SIDE_INBOUND, FAST_BREAK, etc.
- ✅ **Consistent behavior**: Same pattern across all transition types
- ✅ **Easier debugging**: Single source of truth makes it clear which team has possession

### Critical Fixes

**Fix 1: SIP Transition Possession Flip (January 2025)**
- **Issue:** Possession flip was happening in wrong location, causing timing issues
- **Solution:** Moved flip to BEFORE `setup_side_inbound()` call
- **Result:** SIP turn now correctly has `offense_team_id` set to new offense team

**Fix 2: DREB → HCO Possession Flip (January 2025) — superseded by Animation Fix below**
- **Issue:** `offense_team_id` was set before flip, causing incorrect value
- **Original solution:** Flip possession first, then update `offense_team_id` AFTER flip
- **Superseded:** A later **Animation Fix** reversed the `offense_team_id` rewrite. The DREB result turn now **keeps `offense_team_id` = old team** (for step-animation classification); the new offense team is reflected on the next (HCO) turn via `game.offense_team` state. See the DREB → HCO flip location above.

**Fix 3: DREB → Fast Break Possession Flip (January 2025) — superseded by Animation Fix below**
- **Issue:** Same as Fix 2 - `offense_team_id` set before flip
- **Original solution:** Flip possession first, then update `offense_team_id` AFTER flip
- **Superseded:** Same Animation Fix as DREB → HCO — the Fast Break result turn keeps `offense_team_id` = old team for animation sync; new offense team appears on the next turn.

**Fix 4: Fast Break → HCO Double Flip Prevention (January 2025)**
- **Issue:** Fast Break defensive stop was causing double flip (Fast Break sets `possession_flips=False`, but DREB → HCO path was still flipping)
- **Solution:** Added check `if result.get("possession_flips") is True` before flipping in DREB → HCO path
- **Result:** Fast Break defensive stops no longer cause double flips

### Key Files

**Backend:**
- `BackEnd/models/game_manager.py` - Possession management and flip logic (line numbers approximate, verified 2026-06-13)
  - `simulate_macro_turn()` (~line 949) - Main turn simulation, handles possession flips
  - `switch_possession()` (~line 1742) - Swaps offense and defense teams
- `BackEnd/models/turn_manager.py` - Sets `offense_team_id` in turn results
  - Various turn resolution functions set `result["offense_team_id"] = game.offense_team.team_id`

**Frontend:**
- `FrontEnd/static/js/phaser/animation/turnPreparation.js` - Frontend possession handling
  - `handleTurnTransition()` (~line 229) - Reads `offense_team_id` and updates scene state (emits `possessionChange` ~line 242)
- `FrontEnd/static/js/phaser/utils/possessionManager.js` - Possession change event handling
  - `handlePossessionChange()` - Processes possession change events
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js` - Possession change event listener
  - `handlePossessionFlip()` - Handles possession change events during animation

### Turn Type Coverage

The possession management system works for all turn types:
- **HCO** (Half Court Offense)
- **FCP** (Full Court Press)
- **HCT** (Half Court Trap)
- **FREE_THROW**
- **BASELINE_INBOUND** (BIP)
- **SIDE_INBOUND** (SIP)
- **FAST_BREAK**
- **OREB** (Offensive Rebound)
- **DREB** (Defensive Rebound)
- **STEAL**
- **TIMEOUT**

Each turn type has `offense_team_id` set correctly, and possession flips happen at the appropriate transition points.

