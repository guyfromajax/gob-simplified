# Transition System Review Against game_flows.md

## Review Date: 2025-01-XX

This document reviews the transition system implementation against the specifications in `game_flows.md`.

---

## 1. Opening Tip → Master HCO Flow

**Expected:** Opening Tip -> Master HCO Flow

**Implementation Check:**
- `BackEnd/utils/opening_tip.py` line 83: Sets `offensive_state = "HCO"` ✓

**Status:** ✅ CORRECT

---

## 2. Master HCO Flow

**Expected transitions:**
1. Master Shot Attempt Flow
2. Master Turnover Flow (possession change)
3. Non-Shooting Foul
   - Offensive Foul (possession change) -> Side Inbound Pass -> HCO
   - Defensive Foul
     - In Bonus? Yes -> Master Free Throw Flow
     - No -> Side Inbound Pass -> HCO

**Implementation Check:**
- HCO routes to `resolve_half_court_offense()` in `turn_manager.py` line 358
- This calls `shot_manager.resolve_shot()` for shot attempts ✓
- Turnovers handled by `resolve_turnover_logic()` ✓
- Non-shooting fouls handled by `resolve_non_shooting_foul()` in `phase_resolution.py` ✓

**Status:** ✅ CORRECT

---

## 3. Master Turnover Flow

**Expected transitions:**
1. Dead Ball Turnover -> Side Inbound Pass -> HCO
2. Steal -> HCO or Master Fast Break Flow

**Implementation Check:**
- `resolve_turnover_logic()` in `phase_resolution.py` line 683:
  - Line 689: Randomly chooses "STEAL" or "DEAD BALL" ⚠️ **ISSUE FOUND**
  - Line 699-707: STEAL -> FAST_BREAK or HCO ✓
  - Line 718-719: DEAD BALL -> HCO ✓

**Issue:** The code randomly chooses between STEAL and DEAD BALL, but according to game_flows.md, these should be separate outcomes based on the actual turnover type. The turnover_type parameter is passed but then overridden.

**Status:** ⚠️ **ISSUE FOUND** - Line 689 overrides turnover_type parameter

---

## 4. Master Fast Break Flow

**Expected transitions:**
1. Defensive Stop -> HCO
2. Master Shot Attempt Flow

**Implementation Check:**
- `resolve_fast_break_logic()` in `phase_resolution.py` line 224
- Need to check if defensive stop transitions to HCO correctly
- Need to check if shot attempts are handled correctly

**Status:** 🔍 NEEDS VERIFICATION

---

## 5. Master Shot Attempt Flow

**Expected transitions:**
1. Make
   - Foul -> Master Free Throw Flow
   - No Foul (possession change) -> Master Inbound Pass Flow
2. Miss
   - Foul -> Master Free Throw Flow
   - No Foul -> Master Rebound Flow

**Implementation Check:**
- `shot_manager.resolve_shot()` in `shot_manager.py`:
  - Line 341-358: Make with foul -> FREE_THROW ✓
  - Line 370-379: Make without foul -> Sets pressure_type (FCP/HCT/HCO) ✓
  - Line 396-422: Miss with foul -> FREE_THROW ✓
  - Line 430-620: Miss without foul -> Rebound logic ✓

**Status:** ✅ CORRECT

---

## 6. Master Free Throw Flow

**Expected transitions:**
- Final Free Throw?
  - No -> Shoot next free throw
  - Yes:
    - Make (possession change) -> Master Inbound Pass Flow
    - Miss -> Master Rebound Flow

**Implementation Check:**
- `resolve_free_throw_logic()` in `phase_resolution.py` line 518:
  - Line 584-592: Final FT logic:
    - Line 586-589: If made -> Sets pressure_type (FCP/HCT/HCO) ✓
    - Line 591-592: If missed -> Sets HCO, then rebound logic ✓
  - Line 594-640: Rebound logic for missed FT:
    - Line 630-634: DREB -> FAST_BREAK or HCO ✓
    - Line 635-641: OREB -> Stored for separate turn ✓

**Status:** ✅ CORRECT

---

## 7. Master Rebound Flow

**Expected transitions:**
1. Offensive Rebound
   - Kickout -> HCO
   - Putback Attempt -> Master Shot Attempt Flow
2. Defensive Rebound (possession change)
   - Master HCO Flow
   - Master Fast Break Flow

**Implementation Check:**
- Missed shot rebound in `shot_manager.py` line 575-620:
  - Line 575-583: OREB -> Stored in `pending_oreb` ✓
  - Line 584-620: DREB -> FAST_BREAK or HCO ✓
- OREB processing in `turn_manager.py`:
  - Need to check if kickout vs putback is handled correctly

**Status:** 🔍 NEEDS VERIFICATION for OREB kickout vs putback

---

## 8. Master Inbound Pass Flow

**Expected transitions:**
1. FCP
   - Foul (Offensive/Defensive) -> Side Inbound Pass -> HCO or Master Free Throw Flow
   - Master Turnover Flow (possession change)
   - Press Break -> Master Shot Attempt Flow or Master HCO Flow
2. HCT
   - Foul (Offensive/Defensive) -> Side Inbound Pass -> HCO or Master Free Throw Flow
   - Master Turnover Flow (possession change)
   - Trap Break -> Master Shot Attempt Flow or Master HCO Flow
3. Master HCO Flow

**Implementation Check:**
- `resolve_full_court_press_logic()` in `phase_resolution.py` line 1260:
  - Line 1399-1409: Offensive foul -> FOUL, possession_flips = True ✓
  - Line 1410-1416: Dead ball turnover -> DEAD BALL, possession_flips = True ✓
  - Line 1417-1424: Steal -> STEAL, possession_flips = True ✓
  - Line 1448-1454: STEAL -> FAST_BREAK or HCO ✓
  - Line 1455-1457: HCO (press break) -> HCO ✓
  - ⚠️ **ISSUE:** Defensive foul in FCP not explicitly handled - should check bonus and route to FREE_THROW or HCO

- `resolve_half_court_trap_logic()` in `phase_resolution.py` line 1839:
  - Similar structure to FCP
  - ⚠️ **ISSUE:** Defensive foul in HCT not explicitly handled - should check bonus and route to FREE_THROW or HCO

**Status:** ⚠️ **ISSUES FOUND** - Defensive fouls in FCP/HCT not checking bonus

---

## Summary of Issues Found and Fixed

1. **✅ FIXED: Turnover Logic Issue** (`phase_resolution.py` line 689):
   - **Issue:** The `turnover_type` parameter was passed but then randomly overridden
   - **Fix:** Now respects the actual turnover type, only uses random choice when both STEAL and DEAD BALL are possible (defender present)
   - **Status:** ✅ FIXED

2. **✅ FIXED: FCP Defensive Foul Issue** (`phase_resolution.py` lines 1402-1425):
   - **Issue:** Defensive fouls in FCP should check bonus status and route to FREE_THROW if in bonus, otherwise HCO
   - **Fix:** Added bonus checking logic (same as `resolve_non_shooting_foul`) to route correctly
   - **Status:** ✅ FIXED

3. **✅ FIXED: HCT Defensive Foul Issue** (`phase_resolution.py` lines 1973-1995):
   - **Issue:** Defensive fouls in HCT should check bonus status and route to FREE_THROW if in bonus, otherwise HCO
   - **Fix:** Added bonus checking logic (same as `resolve_non_shooting_foul`) to route correctly
   - **Status:** ✅ FIXED

4. **✅ VERIFIED: Fast Break Defensive Stop** (`phase_resolution.py` line 395):
   - Correctly sets `offensive_state = "HCO"` when defensive stop occurs
   - **Status:** ✅ CORRECT

5. **✅ VERIFIED: OREB Kickout vs Putback** (`turn_manager.py` line 1500):
   - OREB kickout correctly sets `offensive_state = "HCO"`
   - OREB putback correctly routes to shot attempt
   - **Status:** ✅ CORRECT

