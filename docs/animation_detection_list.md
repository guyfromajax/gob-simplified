# Animation Detection List (Step 1)

> **Last Updated:** January 2025  
> **Purpose:** Comprehensive list of all turn detection points in `animateGameTurns.js` (Step 1 of the predictable architecture)

This document catalogs every detection point that initiates routing through `AnimationRouter` in the animation system.

---

## Detection Architecture

**Flow:**
```
animateGameTurns.js (detection)  ← STEP 1
    ↓
AnimationRouter (single entry point)
    ↓
AnimationEngine (routing logic)
    ↓
Specialized Handlers (execution)
```

**Detection Pattern:**
All detections follow this pattern:
1. Check turn properties (`result_type`, flags, state)
2. Set `turn.index = i`
3. Call `await animationRouter.processTurn(turn)`
4. `continue` to next turn

---

## Detection Points (In Order of Execution)

### 1. FREE_THROW
**Detection:** `turn.result_type === "FREE_THROW"`  
**Location:** Line 560  
**Routes to:** `AnimationRouter` → `handleFreeThrow()`  
**Notes:** Active player display, free throw sequence, and text scroll handled by handler

---

### 2. FOUL (FCP/HCT with animations)
**Detection:** `turn.result_type === "FOUL" && (turn.fcp_foul === true || turn.hct_foul === true) && turn.animations && turn.animations.length > 0`  
**Location:** Line 571-573  
**Routes to:** `AnimationRouter` → `handleDefault()` → `playTurnAnimation()`  
**Notes:** 
- Only FCP/HCT fouls with animations route through AnimationRouter
- Non-animated fouls just do announcements/updates (no routing)

---

### 3. DEAD BALL
**Detection:** `turn.result_type === "DEAD BALL"`  
**Location:** Line 596  
**Routes to:** Direct announcements (no AnimationRouter)  
**Notes:** No animation, just announcements and score updates

---

### 4. SIDE_INBOUND
**Detection:** `turn.result_type === "SIDE_INBOUND" && !scene.stateMachine?.is(States.FastBreak)`  
**Location:** Line 611  
**Routes to:** `AnimationRouter` → `handleSideInbound()`  
**Notes:** 
- Skips animation if in FastBreak state
- Still does announcements/updates even if skipped

---

### 5. BASELINE_INBOUND
**Detection:** `turn.result_type === "BASELINE_INBOUND"`  
**Location:** Line 633  
**Routes to:** `AnimationRouter` → `handleBaselineInbound()`  
**Notes:** 
- FCP/HCT state tracking handled by handler
- Player animations and state transitions handled by handler

---

### 6. DEFENSIVE_STOP
**Detection:** `turn.result_type === "DEFENSIVE_STOP"`  
**Location:** Line 644  
**Routes to:** `AnimationRouter` → `handleDefensiveStop()`  
**Notes:** 
- Fast Break defensive stops route to `handleFastBreak()`
- Non-Fast Break uses `handleDefensiveStop()`

---

### 7. PUTBACK_MAKE / PUTBACK_MISS / OREB_KICKOUT
**Detection:** `turn.result_type === "PUTBACK_MAKE" || turn.result_type === "PUTBACK_MISS" || turn.result_type === "OREB_KICKOUT"`  
**Location:** Line 655  
**Routes to:** `AnimationRouter` → `handlePutback()`  
**Notes:** 
- Includes debug logging for putback/OREB path tracking
- All three result types use the same handler

---

### 8. FCP/HCT Detection (Complex)
**Detection:** Multi-part detection logic (lines 707-737)  
**Location:** Line 707-1055  
**Routes to:** `playTurnAnimation()` directly (not through AnimationRouter)  
**Detection Logic:**
```javascript
// Part 1: Explicit flags
const hasExplicitFCPHCTFlags = 
  turn.fcp_shot === true || turn.hct_shot === true ||
  turn.fcp_foul === true || turn.hct_foul === true ||
  (isBaselineInbound && (turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT"));

// Part 2: Press break outcomes
const isPressBreakOutcome = 
  (turn.result_type === "HCO" || turn.result_type === "TURNOVER") && 
  scene.pressureSequenceActive;

// Part 3: Press break shot attempts
const isPressBreakShotAttempt = 
  scene.pressureSequenceActive && 
  (turn.result_type === "MAKE" || turn.result_type === "MISS") &&
  (turn.fcp_shot === true || turn.hct_shot === true);

const isFCPHCT = hasExplicitFCPHCTFlags || isPressBreakOutcome || isPressBreakShotAttempt;
```

**Sub-detections:**
- **FCP/HCT Shot Attempt:** `isFCPHCTShotAttempt = (turn.result_type === "MAKE" || turn.result_type === "MISS") && (turn.fcp_shot === true || turn.hct_shot === true)`
- **FCP/HCT Setup Turn:** `isFCPHCT && !isFCPHCTShotAttempt`

**Notes:**
- Uses scene-level state (`scene.pressureSequenceActive`, `scene.currentPressureType`)
- Routes directly to `playTurnAnimation()` (not through AnimationRouter)
- Handles both setup turns and shot attempts

---

### 9. TURNOVER
**Detection:** `turn.result_type === "TURNOVER"`  
**Location:** Line 1057  
**Routes to:** `AnimationRouter` → `handleTurnover()`  
**Notes:** 
- Only detected if not already caught by FCP/HCT detection above
- Includes debug logging to verify it's not catching FCP/HCT turns

---

### 10. OPENING_TIP
**Detection:** `turn.result_type === "OPENING_TIP"`  
**Location:** Line 1078  
**Routes to:** `AnimationRouter` → `handleOpeningTip()`  
**Notes:** 
- Handler validates timing (Q1 start or OT start)
- State transition to HalfCourt handled by handler

---

### 11. FAST_BREAK (Legacy Detection)
**Detection:** `turn.fast_break === true || turn.result_type === "FAST_BREAK"`  
**Location:** Line 1104  
**Routes to:** Direct call to `runFastBreakSequence()` (legacy path)  
**Notes:** 
- This is a legacy detection that still uses direct calls
- Should be removed in favor of detection at line 1141

---

### 12. FAST_BREAK (New Detection)
**Detection:** `turn.result_type === "FAST_BREAK" || ((turn.result_type === "MAKE" || turn.result_type === "MISS") && turn.fast_break === true)`  
**Location:** Line 1141  
**Routes to:** `AnimationRouter` → `handleFastBreak()`  
**Notes:** 
- Handles both explicit FAST_BREAK turns and MAKE/MISS with fast_break flag
- AnimationEngine.determineHandler() also checks fast_break flag

---

### 13. HCO Setup Turns
**Detection:** `turn.result_type === "HCO" && !(turn.result_type === "MAKE" || turn.result_type === "MISS") && !isFCPHCTTurnForHCO`  
**Location:** Line 1156-1166  
**Routes to:** `AnimationRouter` → `handleDefault()` → `playTurnAnimation()`  
**Notes:** 
- Excludes FCP/HCT turns (handled above)
- Excludes shot attempts (MAKE/MISS) - handled below
- Only detects pure HCO setup turns

---

### 14. HCO Shots (MAKE/MISS)
**Detection:** `!turn.fast_break && !isFCPHCTTurn && (turn.result_type === "MAKE" || turn.result_type === "MISS")`  
**Location:** Line 1192-1284  
**Routes to:** `AnimationRouter` → `handleShotAttempt()` → `ShotAnimationSystem`  
**Notes:** 
- Excludes fast breaks (handled above)
- Excludes FCP/HCT turns (handled above)
- Standard half-court offense shots

---

### 15. STEAL (Standalone Turn)
**Detection:** `!scene.stateMachine?.is(States.FastBreak) && turn.result_type === "STEAL"`  
**Location:** Line 1290  
**Routes to:** `AnimationRouter` → `handleSteal()`  
**Notes:** 
- Only routes standalone STEAL turns
- STEAL events within other turns are handled inline (line 1296)

---

### 16. STEAL (Event Within Turn)
**Detection:** `!scene.stateMachine?.is(States.FastBreak) && stealEvent` (where `stealEvent = turn.events?.find(e => e.event_type === "STEAL")`)  
**Location:** Line 1296  
**Routes to:** Direct call to `runPass()` (inline, not through AnimationRouter)  
**Notes:** 
- Not a standalone turn, so doesn't route through AnimationRouter
- Handled inline with pass animation

---

## Detection Summary by Result Type

| Result Type | Detection Line | Routes Through AnimationRouter? | Handler |
|------------|---------------|--------------------------------|---------|
| `FREE_THROW` | 560 | ✅ Yes | `handleFreeThrow()` |
| `FOUL` (FCP/HCT with animations) | 571 | ✅ Yes | `handleDefault()` → `playTurnAnimation()` |
| `FOUL` (non-animated) | 571 | ❌ No | Direct announcements |
| `DEAD BALL` | 596 | ❌ No | Direct announcements |
| `SIDE_INBOUND` | 611 | ✅ Yes | `handleSideInbound()` |
| `BASELINE_INBOUND` | 633 | ✅ Yes | `handleBaselineInbound()` |
| `DEFENSIVE_STOP` | 644 | ✅ Yes | `handleDefensiveStop()` |
| `PUTBACK_MAKE` | 655 | ✅ Yes | `handlePutback()` |
| `PUTBACK_MISS` | 655 | ✅ Yes | `handlePutback()` |
| `OREB_KICKOUT` | 655 | ✅ Yes | `handlePutback()` |
| FCP/HCT (any type) | 707-1055 | ❌ No | Direct to `playTurnAnimation()` |
| `TURNOVER` | 1057 | ✅ Yes | `handleTurnover()` |
| `OPENING_TIP` | 1078 | ✅ Yes | `handleOpeningTip()` |
| `FAST_BREAK` (explicit) | 1141 | ✅ Yes | `handleFastBreak()` |
| `MAKE`/`MISS` (fast_break) | 1141 | ✅ Yes | `handleFastBreak()` |
| `HCO` (setup turn) | 1156 | ✅ Yes | `handleDefault()` → `playTurnAnimation()` |
| `MAKE`/`MISS` (HCO shot) | 1192 | ✅ Yes | `handleShotAttempt()` → `ShotAnimationSystem` |
| `STEAL` (standalone) | 1290 | ✅ Yes | `handleSteal()` |
| `STEAL` (event) | 1296 | ❌ No | Direct to `runPass()` |

---

## Detection by Flag/Property

### By `result_type`:
- `FREE_THROW` → Line 560
- `FOUL` → Line 571
- `DEAD BALL` → Line 596
- `SIDE_INBOUND` → Line 611
- `BASELINE_INBOUND` → Line 633
- `DEFENSIVE_STOP` → Line 644
- `PUTBACK_MAKE` → Line 655
- `PUTBACK_MISS` → Line 655
- `OREB_KICKOUT` → Line 655
- `TURNOVER` → Line 1057
- `OPENING_TIP` → Line 1078
- `FAST_BREAK` → Line 1141
- `HCO` → Line 1156 (setup turns only)
- `MAKE` → Line 1141 (fast break) or 1192 (HCO) or 707 (FCP/HCT)
- `MISS` → Line 1141 (fast break) or 1192 (HCO) or 707 (FCP/HCT)
- `STEAL` → Line 1290

### By Flag:
- `turn.fast_break === true` → Line 1104 (legacy) or 1141 (new)
- `turn.fcp_foul === true` → Line 571 (FOUL) or 707 (FCP/HCT detection)
- `turn.hct_foul === true` → Line 571 (FOUL) or 707 (FCP/HCT detection)
- `turn.fcp_shot === true` → Line 707 (FCP/HCT detection)
- `turn.hct_shot === true` → Line 707 (FCP/HCT detection)
- `turn.next_defensive_setup === "FCP"` → Line 707 (FCP/HCT detection)
- `turn.next_defensive_setup === "HCT"` → Line 707 (FCP/HCT detection)

### By State:
- `scene.pressureSequenceActive === true` → Line 707 (FCP/HCT detection)
- `scene.stateMachine?.is(States.FastBreak)` → Line 611 (SIDE_INBOUND skip), 1290 (STEAL skip)

### By Event:
- `turn.events?.find(e => e.event_type === "STEAL")` → Line 1296 (inline STEAL event)

---

## Special Cases

### 1. FCP/HCT Detection (Not Through AnimationRouter)
**Why:** FCP/HCT turns route directly to `playTurnAnimation()` instead of through `AnimationRouter`.  
**Reason:** Historical implementation - could be migrated in future phase.

### 2. STEAL Events (Not Through AnimationRouter)
**Why:** STEAL events within other turns are not standalone turns, so they don't need routing.  
**Reason:** Events are handled inline as part of the parent turn's animation.

### 3. Legacy FAST_BREAK Detection
**Why:** Two detection points for fast breaks (line 1104 and 1141).  
**Reason:** Line 1104 is legacy code that should be removed.

---

## Detection Order Matters

The order of detections is **critical** because:
1. **Early exits:** Once a detection matches, the turn is processed and the loop `continue`s
2. **Exclusion logic:** Later detections exclude turns already handled (e.g., HCO detection excludes FCP/HCT)
3. **State dependencies:** Some detections depend on state set by previous detections (e.g., FCP/HCT uses `scene.pressureSequenceActive`)

**Current Order (as executed):**
1. FREE_THROW
2. FOUL
3. DEAD BALL
4. SIDE_INBOUND
5. BASELINE_INBOUND
6. DEFENSIVE_STOP
7. PUTBACK_MAKE/MISS/OREB_KICKOUT
8. FCP/HCT (complex detection)
9. TURNOVER
10. OPENING_TIP
11. FAST_BREAK (legacy - should be removed)
12. FAST_BREAK (new)
13. HCO setup turns
14. HCO shots (MAKE/MISS)
15. STEAL (standalone)
16. STEAL (event)

---

## Future Improvements

1. **Migrate FCP/HCT to AnimationRouter:** Currently routes directly to `playTurnAnimation()`
2. **Remove legacy FAST_BREAK detection:** Line 1104 should be removed
3. **Consolidate STEAL handling:** Consider routing STEAL events through AnimationRouter
4. **Document detection order:** Add comments explaining why order matters

---

## Key Files

- `FrontEnd/static/js/phaser/animation/animateGameTurns.js` - All detection logic
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js` - Single entry point
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - Routing logic

---

## Related Documentation

- `docs/animation_system.md` - Overall animation system architecture
- `docs/PHASE_2.6_MIGRATION_PLAN_REVISED.md` - Migration plan and status

