# Animation Detection Reference

**Status:** ✅ Architecture stable as of May 2026.

This document catalogs every detection point that initiates routing through `AnimationRouter` in the animation system.

> **Note on line numbers:** the line references below were captured against an earlier snapshot of `animateGameTurns.js` and may have drifted as the file evolved. The detection patterns (`turn.result_type === ...`, `scene.pressureSequenceActive`, etc.) are the durable contract — search for those if a referenced line number doesn't land on the expected code.

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

## Detection Pattern

All detections follow this pattern:
1. Check turn properties (`result_type`, flags, state)
2. Set `turn.index = i`
3. Call `await animationRouter.processTurn(turn)`
4. `continue` to next turn

## Detection Points (In Order of Execution)

### 1. FREE_THROW (Line 560)
- **Detection:** `turn.result_type === "FREE_THROW"`
- **Routes to:** `AnimationRouter` → `handleFreeThrow()`
- **Notes:** Active player display, free throw sequence, and text scroll handled by handler

### 2. FOUL (FCP/HCT with animations) (Line 571-573)
- **Detection:** `turn.result_type === "FOUL" && (turn.fcp_foul === true || turn.hct_foul === true) && turn.animations && turn.animations.length > 0`
- **Routes to:** `AnimationRouter` → `handleDefault()` → `playTurnAnimation()`
- **Notes:** Only FCP/HCT fouls with animations route through AnimationRouter; non-animated fouls just do announcements

### 3. DEAD BALL (Line 596)
- **Detection:** `turn.result_type === "DEAD BALL"`
- **Routes to:** Direct announcements (no AnimationRouter)
- **Notes:** No animation, just announcements and score updates

### 4. SIDE_INBOUND (Line 611)
- **Detection:** `turn.result_type === "SIDE_INBOUND" && !scene.stateMachine?.is(States.FastBreak)`
- **Routes to:** `AnimationRouter` → `handleSideInbound()`
- **Notes:** Skips animation if in FastBreak state; still does announcements/updates

### 5. BASELINE_INBOUND (Line 633)
- **Detection:** `turn.result_type === "BASELINE_INBOUND"`
- **Routes to:** `AnimationRouter` → `handleBaselineInbound()`
- **Notes:** FCP/HCT state tracking, player animations, and state transitions handled by handler

### 6. DEFENSIVE_STOP (Line 644)
- **Detection:** `turn.result_type === "DEFENSIVE_STOP"`
- **Routes to:** `AnimationRouter` → `handleDefensiveStop()`
- **Notes:** Fast Break defensive stops route to `handleFastBreak()`; non-Fast Break uses `handleDefensiveStop()`

### 7. PUTBACK_MAKE / PUTBACK_MISS / OREB_KICKOUT (Line 655)
- **Detection:** `turn.result_type === "PUTBACK_MAKE" || turn.result_type === "PUTBACK_MISS" || turn.result_type === "OREB_KICKOUT"`
- **Routes to:** `AnimationRouter` → `handlePutback()`
- **Notes:** All three result types use the same handler

### 8. FCP/HCT Detection (Complex) (Line 707-1055)
- **Detection:** Multi-part detection logic
- **Routes to:** `playTurnAnimation()` directly (not through AnimationRouter)
- **Detection Logic:**
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
- **Notes:** Uses scene-level state; routes directly to `playTurnAnimation()` (not through AnimationRouter); handles both setup turns and shot attempts

### 9. TURNOVER (Line 1057)
- **Detection:** `turn.result_type === "TURNOVER"`
- **Routes to:** `AnimationRouter` → `handleTurnover()`
- **Notes:** Only detected if not already caught by FCP/HCT detection above

### 10. OPENING_TIP (Line 1078)
- **Detection:** `turn.result_type === "OPENING_TIP"`
- **Routes to:** `AnimationRouter` → `handleOpeningTip()`
- **Notes:** Handler validates timing (Q1 start or OT start); state transition to HalfCourt handled by handler

### 11. FAST_BREAK (Legacy Detection) (Line 1104)
- **Detection:** `turn.fast_break === true || turn.result_type === "FAST_BREAK"`
- **Routes to:** Direct call to `runFastBreakSequence()` (legacy path)
- **Notes:** Legacy code that should be removed in favor of detection at line 1141

### 12. FAST_BREAK (New Detection) (Line 1141)
- **Detection:** `turn.result_type === "FAST_BREAK" || ((turn.result_type === "MAKE" || turn.result_type === "MISS") && turn.fast_break === true)`
- **Routes to:** `AnimationRouter` → `handleFastBreak()`
- **Notes:** Handles both explicit FAST_BREAK turns and MAKE/MISS with fast_break flag

### 13. HCO Setup Turns (Line 1156-1166)
- **Detection:** `turn.result_type === "HCO" && !(turn.result_type === "MAKE" || turn.result_type === "MISS") && !isFCPHCTTurnForHCO`
- **Routes to:** `AnimationRouter` → `handleDefault()` → `playTurnAnimation()`
- **Notes:** Excludes FCP/HCT turns and shot attempts; only detects pure HCO setup turns

### 14. HCO Shots (MAKE/MISS) (Line 1068-1153)
- **Detection:** `const isHCO = !isFastBreak && (turn.result_type === "MAKE" || turn.result_type === "MISS")`
- **Routes to:** `AnimationRouter` → `AnimationEngine` → `handleShotAttempt()` → `ShotAnimationSystem`
- **Notes:** Uses `result_type` check directly (not `current_turn === "HCO"`). Excludes fast breaks and FCP/HCT turns. Standard half-court offense shots.

### 15. STEAL (Standalone Turn) (Line 1290)
- **Detection:** `!scene.stateMachine?.is(States.FastBreak) && turn.result_type === "STEAL"`
- **Routes to:** `AnimationRouter` → `handleSteal()`
- **Notes:** Only routes standalone STEAL turns; STEAL events within other turns are handled inline

### 16. STEAL (Event Within Turn) (Line 1296)
- **Detection:** `!scene.stateMachine?.is(States.FastBreak) && stealEvent` (where `stealEvent = turn.events?.find(e => e.event_type === "STEAL")`)
- **Routes to:** Direct call to `runPass()` (inline, not through AnimationRouter)
- **Notes:** Not a standalone turn, so doesn't route through AnimationRouter; handled inline with pass animation

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
| `MAKE`/`MISS` (HCO shot) | 1069 | ✅ Yes | `handleShotAttempt()` → `ShotAnimationSystem` |
| `STEAL` (standalone) | 1290 | ✅ Yes | `handleSteal()` |
| `STEAL` (event) | 1296 | ❌ No | Direct to `runPass()` |

## Detection Order Matters

The order of detections is **critical** because:
1. **Early exits:** Once a detection matches, the turn is processed and the loop `continue`s
2. **Exclusion logic:** Later detections exclude turns already handled (e.g., HCO detection excludes FCP/HCT)
3. **State dependencies:** Some detections depend on state set by previous detections (e.g., FCP/HCT uses `scene.pressureSequenceActive`)

## Important Notes

1. **HCO Routing:** Uses `result_type === "MAKE" || result_type === "MISS"` check (not `current_turn === "HCO"`). This is more permissive and catches all HCO shots, including those where `current_turn` might not be set correctly.

2. **FCP/HCT Routing:** Currently routes directly to `playTurnAnimation()` (not through AnimationRouter). This is historical implementation - could be migrated in future phase.

3. **Detection Order Matters:** Early exits prevent double processing. Later detections exclude turns already handled (e.g., HCO detection excludes FCP/HCT).

