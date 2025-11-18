# Fast Break Issue Analysis: Receiver Animates to Basket But Doesn't Shoot

## Problem
The outlet receiver receives the pass, animates toward the basket, but then transitions to HCO instead of shooting.

## All Identified Instances

### 1. **Outlet Receiver Moves Too Far Toward Basket in `animateOutletPhase`**
**Location**: `FrontEnd/static/js/phaser/animation/fastBreak.js` lines 141-163

**Issue**: The receiver moves 5-10 grid spots toward the basket BEFORE we know if it's a shot or defensive stop. If the receiver starts close to the basket (e.g., x=80 on home side), moving 5-10 more spots could put them at x=85-90, which is very close to the basket (x=90), making it look like they're going to shoot.

**Flow**:
1. Outlet pass animates
2. Receiver moves 5-10 spots toward basket (in `animateOutletPhase`)
3. Backend determines `result_type` (MAKE/MISS or DEFENSIVE_STOP)
4. If DEFENSIVE_STOP, `animateDefensiveStop` is called instead of `animateFastBreakShot`
5. Receiver already looks like they're going to basket, but no shot happens

**Code**:
```javascript
const outletTarget = {
  x: Phaser.Math.Clamp(
    receiverCurrentGrid.x + direction * Phaser.Math.Between(5, 10),  // Could move receiver too close to basket
    4,
    97
  ),
  ...
};
```

---

### 2. **Backend Determines DEFENSIVE_STOP After Outlet Pass Animation**
**Location**: `BackEnd/engine/phase_resolution.py` lines 328-336

**Issue**: The backend determines SHOT vs DEFENSIVE_STOP based on defender count AFTER the frontend has already animated the outlet pass. This means:
- If 1 defender: 75% SHOT, 25% DEFENSIVE_STOP
- If 2+ defenders: 10% SHOT, 90% DEFENSIVE_STOP

Even with an outlet pass, the backend can still determine DEFENSIVE_STOP, causing the receiver to animate toward basket but not shoot.

**Code**:
```python
if d_count == 0:
    event_type = "SHOT"
elif d_count == 1:
    event_type = random.choices(["SHOT", "DEFENSIVE_STOP"], weights=[0.75, 0.25])[0]
else:  # d_count >= 2
    event_type = random.choices(["SHOT", "DEFENSIVE_STOP"], weights=[0.10, 0.90])[0]
```

---

### 3. **Shooter ID Doesn't Match Outlet Receiver ID**
**Location**: `FrontEnd/static/js/phaser/animation/fastBreak.js` line 268

**Issue**: The shooter is determined from `turnData.roles?.shooter?.player_id || turnData.shooter_id || getCurrentOwner(scene)`. If the shooter ID doesn't match the outlet receiver ID, `animateFastBreakShot` would animate a different player, not the receiver.

**Backend Logic** (`BackEnd/engine/phase_resolution.py` lines 379-380):
```python
offense_in_play = [fb_roles["ball_handler"]] + fb_roles["offense"]
shooter = random.choice(offense_in_play)
```

When starting from a rebound, `offense` is empty (line 241), so the shooter should always be the `ball_handler`, which should be the outlet receiver. However, if there's an ID mismatch or the backend chooses a different player, the receiver wouldn't be animated as the shooter.

**Code**:
```javascript
const shooterId = turnData.roles?.shooter?.player_id || turnData.shooter_id || getCurrentOwner(scene);
const shooterSprite = playerSprites[shooterId];

if (!shooterSprite) return;  // Early return if shooter sprite not found
```

---

### 4. **Shooter Sprite Not Found (Early Return)**
**Location**: `FrontEnd/static/js/phaser/animation/fastBreak.js` line 271

**Issue**: If `shooterSprite` is not found, `animateFastBreakShot` returns early without animating anything. The receiver has already moved toward the basket in `animateOutletPhase`, but no shot animation happens.

**Code**:
```javascript
if (!shooterSprite) return;  // Returns early, no shot animation
```

---

### 5. **State Machine Issues Preventing Shot**
**Location**: `FrontEnd/static/js/phaser/animation/fastBreak.js` line 381

**Issue**: If `safeTransition(scene.stateMachine, States.ShotAttempt)` fails, the shot animation might not complete properly, causing the game to transition to HCO instead.

**Code**:
```javascript
// Shoot the ball
safeTransition(scene.stateMachine, States.ShotAttempt);

const rimPx = gridToPixels(adjustedBasket.x, adjustedBasket.y, width, height);
await tweenBallTo(scene, ballSprite, rimPx, {
  duration: 400,
  easing: "Sine.easeInOut",
  arc: { height: 50 }
});
```

---

### 6. **Next Turn Processed Before Fast Break Shot Completes**
**Location**: `FrontEnd/static/js/phaser/animation/animateGameTurns.js` lines 940-965

**Issue**: If the next turn is processed before the Fast Break shot completes, it might transition to HCO prematurely. The HCO turn detection logic might incorrectly process the next turn before the shot animation finishes.

**Code**:
```javascript
const wasDefensiveStop = previousTurn?.result_type === "DEFENSIVE_STOP" && previousTurn?.fast_break === true;
const isHCO = !turn.fast_break && (turn.result_type === "MAKE" || turn.result_type === "MISS");

// Enhanced debug for HCO detection after defensive stop
if (wasDefensiveStop) {
  // HCO turn processing might happen before Fast Break shot completes
}
```

---

## Summary

The main issues are:

1. **Receiver moves toward basket before knowing if it's a shot** - `animateOutletPhase` moves receiver 5-10 spots toward basket, which can make them appear too close to the basket if they start near it.

2. **Backend can determine DEFENSIVE_STOP after outlet pass** - Even with an outlet pass, the backend can still determine DEFENSIVE_STOP (25% chance with 1 defender, 90% with 2+ defenders), causing the receiver to animate toward basket but not shoot.

3. **Shooter ID mismatch or sprite not found** - If the shooter ID doesn't match the outlet receiver ID, or if the shooter sprite is not found, `animateFastBreakShot` won't animate the receiver, causing them to appear to go toward basket but not shoot.

4. **State machine or timing issues** - State transitions or timing issues might prevent the shot animation from completing properly.

---

## Recommended Fixes

1. **Reduce outlet receiver movement distance** - Move receiver only 2-5 spots toward basket (instead of 5-10) to avoid making them appear too close to the basket.

2. **Check for shooter ID match** - Ensure the shooter ID matches the outlet receiver ID before animating the shot. If they don't match, log a warning and fall back to the outlet receiver.

3. **Add defensive stop check before moving receiver** - Move the receiver to a truly neutral spot (not toward basket) until we know if it's a shot or defensive stop.

4. **Add debug logs** - Add comprehensive debug logs to track:
   - Outlet receiver ID vs shooter ID
   - Whether `animateFastBreakShot` is called
   - Whether shooter sprite is found
   - Whether shot animation completes
   - State machine transitions

