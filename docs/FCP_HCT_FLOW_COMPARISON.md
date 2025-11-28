# FCP/HCT Flow Comparison: Made Shot → FCP/HCT Transition

## Comparison Grid

| Flow | Handler Function | Calls `runInboundSetup()` | After `runInboundSetup()` | Next Turn Routing | Cleanup Present? |
|------|------------------|---------------------------|---------------------------|-------------------|------------------|
| **Made OREB Putback** | `handleOrebTurn()` | ✅ Yes (with 50ms delay) | `announceFromTurnData()`<br>`onUpdate()`<br>`updateDebugScore()` | `playTurnAnimation` (setup)<br>OR<br>`ShotAnimationSystem` (shot attempt) | ✅ Yes (both paths) |
| **Made HCO Shot** | `ShotAnimationSystem.handleMadeShot()` | ✅ Yes (with 50ms delay) | Returns immediately | `playTurnAnimation` (setup)<br>OR<br>`ShotAnimationSystem` (shot attempt) | ✅ Yes (both paths) |
| **Made Free Throw** | `runFreeThrowSequence()` | ✅ Yes (via `inboundSetup()` alias, with 50ms delay) | `scene.events?.emit?.("possessionChange")`<br>`nextStateResolved = States.Inbound`<br>`scene.events?.emit("ft:repeatOrExit")`<br>`scene.events?.emit("ft:end")` | `playTurnAnimation` (setup)<br>OR<br>`ShotAnimationSystem` (shot attempt) | ✅ Yes (both paths) |
| **Made Fast Break Shot** | `animateFastBreakShot()` (called from `runFastBreakSequence()`) | ✅ Yes (with 50ms delay) | Returns to `runFastBreakSequence()`<br>Then: `announceFromTurnData()`<br>`onUpdate()`<br>`updateDebugScore()` | `playTurnAnimation` (setup)<br>OR<br>`ShotAnimationSystem` (shot attempt) | ✅ Yes (both paths) |

## Key Observations

### 1. **All flows call `runInboundSetup()` with built-in 50ms delay**
   - The delay is implemented inside `runInboundSetup()` itself (lines 1391-1419 in `turnAnimation.js`)
   - This ensures consistent behavior across all flows

### 2. **Post-`runInboundSetup()` processing varies:**
   - **OREB Putback**: Has additional processing (`announceFromTurnData`, `onUpdate`, `updateDebugScore`) before next turn
   - **HCO Shot**: Returns immediately, next turn starts right away ⚠️
   - **Free Throw**: Has extensive event emissions and state transitions before next turn
   - **Fast Break**: Has additional processing (`announceFromTurnData`, `onUpdate`, `updateDebugScore`) before next turn

### 3. **Next turn routing is identical for all flows:**
   - Routes to `playTurnAnimation` for setup turns (FOUL, HCO transition, etc.)
   - Routes to `ShotAnimationSystem` for shot attempts (press break shots)

### 4. **Cleanup status:**
   - ✅ `playTurnAnimation` has player tween cleanup (lines 1716-1843 in `turnAnimation.js`)
   - ✅ `ShotAnimationSystem` now has player tween cleanup (just added in `animatePlayerMovement()`)

## Why HCO Shots Were Failing (Before Fix)

**HCO Shot flow was unique:**
- After `runInboundSetup()` completes, it returns immediately
- Next turn starts right away (no additional processing delay)
- If next turn routes to `ShotAnimationSystem`, it didn't have player tween cleanup
- Lingering player tweens from `runInboundSetup()` blocked new tweens from starting

**Other flows worked because:**
- **OREB Putback**: Additional processing (`announceFromTurnData`, `onUpdate`, `updateDebugScore`) naturally delays next turn
- **Free Throw**: Extensive event emissions and state transitions naturally delay next turn
- **Fast Break**: Additional processing (`announceFromTurnData`, `onUpdate`, `updateDebugScore`) naturally delays next turn

## The Fix

Added player tween cleanup to `ShotAnimationSystem.animatePlayerMovement()`:
1. Kill all player sprite tweens before step loop
2. 50ms delay to let tween manager settle
3. Matches `playTurnAnimation`'s approach exactly

This ensures consistent behavior across all flows, regardless of post-`runInboundSetup()` processing.

