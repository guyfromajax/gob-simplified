# Detailed Comparison: HCO Shots vs FCP/HCT Shots

## Execution Path Comparison

### Step 1: Detection in animateGameTurns.js

**HCO Shot:**
```javascript
// Line 1222
const isHCO = !turn.fast_break && !isFCPHCTTurn && (turn.result_type === "MAKE" || turn.result_type === "MISS");
// Line 1287
await animationRouter.processTurn(turn);
```

**FCP/HCT Shot:**
```javascript
// Line 882
const isFCPHCTShotAttempt = scene.pressureSequenceActive && 
                             (turn.result_type === "MAKE" || turn.result_type === "MISS") &&
                             (turn.fcp_shot === true || turn.hct_shot === true ||
                              scene.currentPressureType === "FCP" || scene.currentPressureType === "HCT");
// Line 932
await animationRouter.processTurn(turn);
```

**Difference:** FCP/HCT requires `scene.pressureSequenceActive === true` (set by previous BASELINE_INBOUND turn)

---

### Step 2: AnimationRouter.processTurn()

**Both paths are IDENTICAL:**
- Calls `prepareTurnForAnimation()` (line 107)
- Calls `animationEngine.processTurn()` (line 158)
- Calls `finalizeTurnAfterAnimation()` in finally block (line 187)

**No differences here.**

---

### Step 3: AnimationEngine.determineHandler()

**Both paths are IDENTICAL:**
- Checks `isShotAttempt()` (line 175)
- Routes to `SHOT_ATTEMPT` handler (line 179)
- Calls `handleShotAttempt()` (line 323)

**No differences here.**

---

### Step 4: ShotAnimationSystem.processShot()

**Both paths are IDENTICAL:**
- Validates shot data (line 87)
- Calls `executeCompleteShotSequence()` (line 100)

**No differences here.**

---

### Step 5: ShotAnimationSystem.executeCompleteShotSequence()

**Both paths are IDENTICAL:**
- Initializes ball holder state (line 122)
- Resets scene flags (line 127-128)
- Clears ball state (line 131-134)
- Calculates maxSteps (line 142-148)
- Calls `runSetupTween()` (line 151)
- Calls `updateBallOwnership()` at step 0 (line 155-163)
- Attaches ball at step 0 (line 174-177)
- Calls `animatePlayerMovement()` (line 180)

**No differences here.**

---

## Critical Differences Found

### 1. Scene State Before Turn

**HCO Shot:**
- Previous turn: Could be DREB, HCO setup, or other non-shot turn
- `scene._previousTurnWasShot`: Usually `false` (unless previous was a shot)
- `scene._previousTurnWasInbound`: Usually `false`
- `scene.pressureSequenceActive`: `false`
- Players: Already positioned from previous HCO play

**FCP/HCT Shot:**
- Previous turn: **BASELINE_INBOUND** with `next_defensive_setup === "FCP"` or `"HCT"`
- `scene._previousTurnWasShot`: Could be `true` (if previous was a made shot)
- `scene._previousTurnWasInbound`: **`true`** (set by BASELINE_INBOUND turn)
- `scene.pressureSequenceActive`: **`true`** (set by BASELINE_INBOUND turn)
- Players: Just positioned by `runInboundSetup()` with FCP/HCT defensive setup

**KEY DIFFERENCE:** FCP/HCT shots come AFTER an inbound setup, which means:
- `scene._previousTurnWasInbound === true`
- Players were just moved to inbound positions
- Ball might already be attached to inbound receiver

---

### 2. Ball State Before Turn

**HCO Shot:**
- Ball state: Usually attached to a player from previous play
- `scene.passInFlight`: Usually `false`
- Ball position: At player position

**FCP/HCT Shot:**
- Ball state: **Might be attached from inbound pass** (if inbound pass completed)
- `scene.passInFlight`: Could be `true` if inbound pass just completed
- Ball position: At inbound receiver position

**KEY DIFFERENCE:** FCP/HCT shots might have ball already attached from inbound, which could conflict with `ShotAnimationSystem`'s step 0 ball attachment logic.

---

### 3. Player Positions Before Turn

**HCO Shot:**
- Players: Positioned from previous HCO play
- Positions: Half-court offense positions
- Movement: Small adjustments to shooting positions

**FCP/HCT Shot:**
- Players: **Just positioned by `runInboundSetup()`**
- Positions: Inbound positions (offense near baseline, defense in FCP/HCT press positions)
- Movement: **Large movement from inbound positions to press break positions**

**KEY DIFFERENCE:** FCP/HCT shots require players to move from inbound positions (baseline) to press break positions (up court), which is a much larger movement than HCO shots.

---

### 4. Missing Logic in ShotAnimationSystem

**playTurnAnimation has this check:**
```javascript
// Line 1546-1550
const previousTurnWasShot = scene._previousTurnWasShot === true;
if (previousTurnWasShot) {
  console.log('🏀 playTurnAnimation: Skipping step 0 ball attachment - previous turn was a shot');
  scene._previousTurnWasShot = false; // Clear the flag
}

// Line 1555
if (!previousTurnWasShot && !fromInbound && !fromOpeningTip) {
  // Attach ball at step 0
}
```

**ShotAnimationSystem does NOT have this check:**
- It always tries to attach ball at step 0 (line 174-177)
- It doesn't check `_previousTurnWasShot`
- It doesn't check `fromInbound`
- It doesn't skip ball attachment if coming from inbound

**KEY DIFFERENCE:** `ShotAnimationSystem` doesn't handle the case where:
- Previous turn was an inbound (`fromInbound === true`)
- Ball is already attached to inbound receiver
- Trying to attach again at step 0 causes conflicts

---

### 5. Missing Logic: Skip Step 0 Ball Attachment

**playTurnAnimation:**
```javascript
// Line 1553-1555
// If we are coming directly from an inbound or opening tip, the ball should already be attached
// to the inbound receiver or tip winner, so we don't re-derive or re-attach at step 0.
if (!previousTurnWasShot && !fromInbound && !fromOpeningTip) {
  // Only attach ball if NOT from inbound/tip
}
```

**ShotAnimationSystem:**
```javascript
// Line 174-177
// Always tries to attach ball, regardless of fromInbound
if (step0OwnerSprite) {
  this.ballController.attachToPlayer(step0OwnerSprite);
  currentBallOwnerRef.value = step0OwnerSprite;
}
```

**KEY DIFFERENCE:** `ShotAnimationSystem` doesn't skip ball attachment when coming from inbound, which could cause:
- Ball attachment conflicts
- Ball teleporting
- Animation skipping

---

## Root Cause Hypothesis

**The problem:** FCP/HCT shots come AFTER a BASELINE_INBOUND turn, which means:
1. `scene._previousTurnWasInbound === true`
2. Ball is already attached to inbound receiver
3. Players are already at inbound positions
4. `ShotAnimationSystem` tries to re-attach ball at step 0, causing conflicts
5. Animation gets stuck or skips because of ball state conflicts

**HCO shots work because:**
- They don't come after inbound turns
- `fromInbound === false`
- Ball attachment at step 0 works normally
- No conflicts

---

## Solution

Add the same logic to `ShotAnimationSystem` that `playTurnAnimation` has:

```javascript
// Check if coming from inbound/tip
const fromInbound = this.scene._previousTurnWasInbound === true;
const fromOpeningTip = this.scene._previousTurnWasOpeningTip === true;
const previousTurnWasShot = this.scene._previousTurnWasShot === true;

// Skip ball attachment if coming from inbound/tip or previous was shot
if (!previousTurnWasShot && !fromInbound && !fromOpeningTip) {
  // Attach ball at step 0
  if (step0OwnerSprite) {
    this.ballController.attachToPlayer(step0OwnerSprite);
    currentBallOwnerRef.value = step0OwnerSprite;
  }
}
```

This would match `playTurnAnimation`'s logic exactly and prevent ball attachment conflicts.

