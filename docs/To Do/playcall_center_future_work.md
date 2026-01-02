# Playcall Center Future Work

This document tracks outstanding items and future enhancements for the Playcall Center system.

## Priority Items

### 1. Full Scenario Testing

**Status:** Test Documentation Created, Not Executed  
**Issue:** Comprehensive test scenarios have been documented but not yet executed.

**What Needs to Be Done:**
- Execute all 5 test scenarios with 3 configurations each (15 total tests)
- Document results in test tracking system
- Fix any issues discovered during testing

**Test Scenarios:**
1. BIP → HCT (trap break) → HCO (offense) → SIP → HCO (defense)
2. BIP → HCT (dead ball turnover) → SIP → HCO (defense) → Fast Break → HCO (offense)
3. BIP → HCO (offense) → Free Throw → BIP → HCT → HCO (defense)
4. HCT (user has ball) → HCO (offense) → HCO (defense)
5. HCO → Fast Break → BIP → FCP → SIP → HCO (offense) → HCO (defense)

**Note:** Test documentation files have been removed. Test scenarios can be recreated if needed.

---

## Enhancement Items

### 2. Zone Defense Granular Selection

**Status:** Not Implemented  
**Issue:** Users can only select "Zone" or "Man" for defense. The backend randomly converts "Zone" to a specific zone type (2-3 Zone, 3-2 Zone, or 1-3-1 Zone). Users cannot choose the specific zone type.

**Current Behavior:**
- User selects "Zone" in Playcall Center
- Backend converts to random specific zone type at runtime
- User has no control over which specific zone is used

**Future Enhancement:**
- Add UI buttons for specific zone types (2-3 Zone, 3-2 Zone, 1-3-1 Zone)
- Allow users to select specific zone types directly
- Update backend to accept and use specific zone types without conversion

**Related Files:**
- `FrontEnd/static/court.html` - Playcall Center UI
- `BackEnd/models/turn_manager.py` - Zone conversion logic (lines 849, 884, 961)

---

### 3. Button Highlighting Edge Cases

**Status:** Partially Addressed  
**Issue:** Button highlighting may not always clear correctly when overrides are used. The match logic in `updatePlaycallCenter()` may not find matches in some edge cases.

**Current Behavior:**
- Most of the time, highlights clear correctly
- `offense_override_cleared` flag exists and is checked to clear offense highlights (`FrontEnd/static/js/phaser/ui/playcallCenter.js:42`)
- Defense and aggression buttons remain highlighted until manually cleared by user (line 53)
- Occasionally, buttons may remain highlighted after override is used
- Likely due to matching logic not finding exact match between turn data and button attributes

**What Needs to Be Done:**
- Review and improve matching logic in `updatePlaycallCenter()`
- Add more robust matching (case-insensitive, whitespace handling, etc.)
- Add fallback clearing mechanism if match isn't found

**Related Files:**
- `FrontEnd/static/js/phaser/ui/playcallCenter.js` - Button highlighting logic (lines 12-53)

---


---

## Completed Items ✅

### ✅ Database Persistence of `strategy_calls`
- **Fixed:** `strategy_calls` (including `offense_call`, `defense_call`, `aggression_override`, `tempo_override`) are now persisted to the database and restored when loading games
- **Date:** February 2025
- **Implementation:**
  - `summarize_game_state()` saves `strategy_calls` to database (`BackEnd/utils/shared.py:788, 796`)
  - `strategy_calls` are loaded when resuming games (`BackEnd/api/api.py:1036-1037, 1106-1107`)
  - `strategy_calls` are passed to `GameManager` constructor and initialized in `TeamManager`
- **Files:**
  - `BackEnd/utils/shared.py` - `summarize_game_state()` (lines 788, 796)
  - `BackEnd/api/api.py` - Game loading logic (lines 1036-1037, 1106-1107)
  - `BackEnd/models/team_manager.py` - Team initialization (lines 53-73)

### ✅ Aggression and Tempo Overrides Integration
- **Fixed:** Aggression and tempo overrides are fully integrated into the game engine logic
- **Date:** February 2025
- **Implementation:**
  - Overrides stored in `team.strategy_calls["aggression_override"]` and `team.strategy_calls["tempo_override"]`
  - Overrides used in game logic (`BackEnd/models/turn_manager.py:1420-1426, 1445-1449`)
  - Aggression override persists until manually cleared
  - Tempo override clears after use
- **Files:**
  - `BackEnd/api/api.py` - `set_playcall_override_endpoint()` (lines 2291-2308)
  - `BackEnd/models/turn_manager.py` - Override usage (lines 1420-1426, 1445-1449)
  - `BackEnd/models/team_manager.py` - Override initialization (lines 58-59, 69-70)

### ✅ Offense Override Stat Tracking
- **Fixed:** Added offensive playcall stat tracking before early return in `set_playcalls()`
- **Date:** January 2025
- **Files:** `BackEnd/models/turn_manager.py` (lines 861-911)

### ✅ Defense Override Stat Tracking (Zone)
- **Fixed:** Added zone conversion in defense-only override path
- **Date:** January 2025
- **Files:** `BackEnd/models/turn_manager.py` (lines 881-885)

### ✅ Defense Override Detection When User on Offense
- **Fixed:** Modified `set_playcalls()` to check user team's `strategy_calls` regardless of current offense/defense position
- **Date:** January 2025
- **Files:** `BackEnd/models/turn_manager.py` (lines 779-790)

---

## Notes

- All overrides are stored in `team.strategy_calls` dictionary
- Overrides persist until used, then are automatically cleared
- `set_playcalls()` is called during HCO turns to determine playcalls
- Overrides are checked from the user team's `strategy_calls` regardless of current offense/defense position

