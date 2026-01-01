# Playcall Center Future Work

This document tracks outstanding items and future enhancements for the Playcall Center system.

## Priority Items

### 1. Database Persistence of `strategy_calls` ⚠️ HIGH PRIORITY

**Status:** Not Implemented  
**Issue:** The `strategy_calls` (including `offense_call` and `defense_call`) are not persisted to the database. If the server restarts or the game is reloaded, user playcall overrides are lost.

**Impact:**
- User sets an override during a timeout
- Server restarts or game is reloaded
- Override is lost, user's selection is not applied

**Previous Attempt:**
- Attempted to add database persistence in `api.py` and `turn_manager.py`
- Extracted `strategy_calls` from game document and passed to `GameManager` constructor
- Added `strategy_calls` parameter to `TeamManager.__init__()`
- **Result:** Broke things entirely, changes were reverted

**What Needs to Be Done:**
- Persist `strategy_calls` to the game document in the database
- Load `strategy_calls` when loading a game from the database
- Ensure `strategy_calls` are included in game state summaries
- Test thoroughly to avoid breaking existing functionality

**Related Files:**
- `BackEnd/api/api.py` - `simulate_quarter_endpoint()`, `set_playcall_override_endpoint()`
- `BackEnd/models/game_manager.py` - Game loading/saving
- `BackEnd/models/team_manager.py` - Team initialization
- `BackEnd/utils/shared.py` - `summarize_game_state()`

---

## Enhancement Items

### 2. Full Scenario Testing

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

### 3. Zone Defense Granular Selection

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

### 4. Button Highlighting Edge Cases

**Status:** Minor Issue  
**Issue:** Button highlighting may not always clear correctly when overrides are used. The match logic in `updatePlaycallCenter()` may not find matches in some edge cases.

**Current Behavior:**
- Most of the time, highlights clear correctly
- Occasionally, buttons remain highlighted after override is used
- Likely due to matching logic not finding exact match between turn data and button attributes

**What Needs to Be Done:**
- Review and improve matching logic in `updatePlaycallCenter()`
- Add more robust matching (case-insensitive, whitespace handling, etc.)
- Add fallback clearing mechanism if match isn't found

**Related Files:**
- `FrontEnd/static/js/phaser/ui/playcallCenter.js` - Lines 149-193 (defense matching), 67-147 (offense matching)

---

### 5. Aggression and Tempo Overrides Integration

**Status:** Partially Implemented  
**Issue:** Aggression and tempo overrides are stored in `strategy_calls` and can be set via the API, but may not be fully integrated into the game engine logic.

**Current Behavior:**
- Overrides can be set via `/api/set-playcall-override` endpoint
- Stored in `team.strategy_calls["aggression_override"]` and `team.strategy_calls["tempo_override"]`
- May not be consistently used throughout the game engine

**What Needs to Be Done:**
- Verify aggression and tempo overrides are used in all relevant game logic
- Ensure overrides are cleared after use (similar to offense/defense overrides)
- Test that overrides persist through turn transitions

**Related Files:**
- `BackEnd/api/api.py` - `set_playcall_override_endpoint()`
- `BackEnd/models/turn_manager.py` - `set_strategy_calls()`
- Game engine logic that uses aggression and tempo settings

---

## Completed Items ✅

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

