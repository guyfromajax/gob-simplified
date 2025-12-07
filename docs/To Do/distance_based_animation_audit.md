# Distance-Based Animation Timing Audit

> **Created**: January 2025  
> **Status**: In Progress  
> **Purpose**: Comprehensive review of where distance-based animation timing is implemented and where it's missing

## Executive Summary

The codebase has distance-based animation timing **partially implemented**. Core step animations (HCO, FCP, HCT) use it correctly, but several edge cases and special animations still use hardcoded durations, causing inconsistent speeds.

**Key Functions:**
- `getPlayerDuration(sprite, targetX, targetY, isTransition)` - Player movement duration
- `getBallDuration(ballSprite, targetX, targetY)` - Ball movement duration
- `getDurationFromDistance(currentX, currentY, targetX, targetY, speed)` - Core calculation

**Formula:** `duration = (distance / speed) * 1000` (converts to milliseconds)

---

## ✅ Where Distance-Based Timing IS Used

### 1. Core Turn Animations (Skeleton Steps)

**Files:**
- `turnAnimation.js` (lines 1924-1928)
- `ShotAnimationSystem.js` (lines 405-413)

**Implementation:**
```javascript
const duration = getPlayerDuration(sprite, targetX, targetY);
```

**Coverage:**
- ✅ HCO turn step animations
- ✅ FCP/HCT turn step animations
- ✅ All skeleton-based movement steps

**Status:** ✅ **WORKING CORRECTLY**

---

### 2. Baseline Inbound (BIP) Player Positioning

**File:** `AnimationEngine.js` (lines 332-358)

**Implementation:**
```javascript
const duration = getPlayerDuration(sprite, endPixels.x, endPixels.y, false);
```

**Coverage:**
- ✅ BIP player positioning to skeleton step 0 positions
- ✅ Uses `isTransition = false` (regular speed, not transition speed)

**Status:** ✅ **WORKING CORRECTLY**

---

### 3. Inbound Setup (runInboundSetup)

**File:** `turnAnimation.js` (lines 1329-1441)

**Implementation:**
```javascript
const sfDuration = getPlayerDuration(sfSprite, sfDestPx.x, sfDestPx.y, false);
const pgDuration = getPlayerDuration(pgSprite, pgDestPx.x, pgDestPx.y, false);
// ... etc for all positions
```

**Coverage:**
- ✅ SF, PG, SG, PF, C positioning during inbound setup
- ✅ Uses `isTransition = false` (regular speed)

**Status:** ✅ **WORKING CORRECTLY**

---

### 4. Defensive Rebound (DREB) Outlet Step

**File:** `turnAnimation.js` (lines 554-692)

**Implementation:**
```javascript
// Outlet receiver movement
const outletDuration = getPlayerDuration(outletReceiverSprite, outletPx.x, outletPx.y, true);

// Other players moving toward new offense basket
const playerDuration = getPlayerDuration(sprite, targetPx.x, targetPx.y, true);
```

**Coverage:**
- ✅ Outlet receiver (PG) movement to rebounder
- ✅ All other players moving toward new offense basket
- ✅ Uses `isTransition = true` (allows longer durations for long movements)

**Status:** ✅ **WORKING CORRECTLY**

---

### 5. Opening Tip

**File:** `openingTip.js` (lines 100-101, 170-171)

**Implementation:**
```javascript
const jumpDuration = getPlayerDuration(playerSprite, jumpPixels.x, jumpPixels.y);
const convergeDuration = getPlayerDuration(playerSprite, pixelCoords.x, pixelCoords.y);
```

**Coverage:**
- ✅ Jump ball animations
- ✅ Player convergence after tip

**Status:** ✅ **WORKING CORRECTLY**

---

### 6. Free Throw

**File:** `freeThrow.js` (lines 101-102, 126-127)

**Implementation:**
```javascript
const duration = getPlayerDuration(sprite, px.x, px.y);
```

**Coverage:**
- ✅ Player positioning for free throws

**Status:** ✅ **WORKING CORRECTLY**

---

### 7. Fast Break

**File:** `fastBreak.js` (lines 403-404, 458-459, 1018-1019)

**Implementation:**
```javascript
const shooterDuration = getPlayerDuration(shooterSprite, shotPx.x, shotPx.y);
const defenderDuration = getPlayerDuration(defenderSprite, defenderPx.x, defenderPx.y);
const playerDuration = getPlayerDuration(sprite, targetPx.x, targetPx.y);
```

**Coverage:**
- ✅ Fast break player movements
- ✅ Shooter and defender positioning

**Status:** ✅ **WORKING CORRECTLY**

---

### 8. Ball Animations (Passes)

**Files:**
- `ballTween.js` (lines 56-91)
- `ballAnimationSimple.js` (lines 205-240)

**Implementation:**
```javascript
const duration = getBallDuration(ballSprite, targetX, targetY);
```

**Coverage:**
- ✅ Most pass animations
- ✅ Ball movement during plays

**Status:** ✅ **MOSTLY WORKING** (some edge cases may use hardcoded durations)

---

## ❌ Where Distance-Based Timing is NOT Used

### 1. Get-Back Players During Shot Attempts ⚠️ **CRITICAL**

**File:** `ShotAnimationSystem.js` (lines 606-627)

**Current Implementation:**
```javascript
// Offensive players getting back on defense
turnData.offense_getback.forEach(playerId => {
  const sprite = this.playerSprites[playerId];
  if (sprite) {
    const targetPixel = gridToPixels(targetX, targetY, ...);
    
    this.scene.tweens.add({
      targets: sprite,
      x: targetPixel.x,
      y: targetPixel.y,
      duration: this.shotConfig.flightDuration,  // ❌ HARDCODED: 800ms
      ease: 'Power1'
    });
  }
});
```

**Problem:**
- Uses `shotConfig.flightDuration` (800ms) regardless of distance
- Players moving short distances move too fast
- Players moving long distances move too slow
- Not consistent with other player movements

**Fix Required:**
```javascript
import { getPlayerDuration } from './turnAnimation.js';

const duration = getPlayerDuration(sprite, targetPixel.x, targetPixel.y);
```

**Also Affects:**
- Defensive players getting back (lines 590-604) - Same issue

**Status:** ❌ **NEEDS FIX**

---

### 2. Rebound Positioning Animations ⚠️ **CRITICAL**

**File:** `ShotAnimationSystem.js`

#### 2a. Rebounder to Ball Bounce (Line 871)

**Current Implementation:**
```javascript
this.scene.tweens.add({
  targets: rebounderSprite,
  x: ballBounceX,
  y: ballBounceY,
  duration: 400,  // ❌ HARDCODED
  ease: 'Power2',
  // ...
});
```

**Problem:**
- 400ms regardless of distance from rebounder to ball
- Can cause "jetting" if rebounder is far from ball
- Can cause slow movement if rebounder is close to ball

**Fix Required:**
```javascript
import { getPlayerDuration } from './turnAnimation.js';

const duration = getPlayerDuration(rebounderSprite, ballBounceX, ballBounceY);
```

**Status:** ❌ **NEEDS FIX**

---

#### 2b. Non-Rebounders Collapse (Line 986)

**Current Implementation:**
```javascript
this.scene.tweens.add({
  targets: playerSprite,
  x: targetPixel.x,
  y: targetPixel.y,
  duration: 400,  // ❌ HARDCODED
  ease: 'Power2',
  // ...
});
```

**Problem:**
- 400ms regardless of distance
- Players moving to rebound spot use fixed duration

**Fix Required:**
```javascript
import { getPlayerDuration } from './turnAnimation.js';

const duration = getPlayerDuration(playerSprite, targetPixel.x, targetPixel.y);
```

**Status:** ❌ **NEEDS FIX**

---

#### 2c. Player to Rebound Spot (Line 1037)

**Current Implementation:**
```javascript
this.scene.tweens.add({
  targets: playerSprite,
  x: clampedX,
  y: clampedY,
  duration: 500,  // ❌ HARDCODED
  ease: 'Power2',
  // ...
});
```

**Problem:**
- 500ms regardless of distance

**Fix Required:**
```javascript
import { getPlayerDuration } from './turnAnimation.js';

const duration = getPlayerDuration(playerSprite, clampedX, clampedY);
```

**Status:** ❌ **NEEDS FIX**

---

### 3. Initial Player Positioning in ShotAnimationSystem

**File:** `ShotAnimationSystem.js` (line 270)

**Current Implementation:**
```javascript
const tween = this.scene.tweens.add({
  targets: [sprite],
  x,
  y,
  duration: 1000,  // ❌ HARDCODED
  ease: "Linear",
  // ...
});
```

**Problem:**
- 1000ms regardless of distance
- Used for initial positioning before skeleton animation starts

**Fix Required:**
```javascript
import { getPlayerDuration } from './turnAnimation.js';

const duration = getPlayerDuration(sprite, x, y);
```

**Status:** ❌ **NEEDS FIX**

---

### 4. BIP to HCO Transition ⚠️ **USER REPORTED ISSUE**

**Problem Description:**
User reports that the transition from BASELINE_INBOUND to HCO is not adhering to distance-based timing. Players "jet down the court" during this transition.

**Investigation:**

**Current Flow:**
1. `handleBaselineInbound()` (AnimationEngine.js) - ✅ Uses distance-based timing for positioning
2. `executeInboundSequence()` (PassAnimationSystem) - Passes ball
3. Next turn (HCO) starts with `playTurnAnimation()` - ✅ Uses distance-based timing for steps

**Potential Issues:**
1. **Gap Between BIP and HCO:** If there's a gap between where players end after BIP and where HCO step 0 expects them, the first HCO step might cover a very long distance, causing fast movement.

2. **HCO Step 0 Positioning:** The first HCO step might not account for where players actually are after BIP completes.

3. **Transition State:** There might be a transition animation between BIP and HCO that's not using distance-based timing.

**Files to Check:**
- `AnimationEngine.js` - `handleBaselineInbound()` (lines 311-379)
- `PassAnimationSystem.js` - `executeInboundSequence()`
- `turnAnimation.js` - `playTurnAnimation()` (HCO entry)
- `turnPreparation.js` - Any transition logic

**Status:** ⚠️ **NEEDS INVESTIGATION**

**Next Steps:**
1. Check if there's a transition animation between BIP and HCO
2. Verify that HCO step 0 accounts for actual player positions after BIP
3. Check if `_previousTurnWasInbound` flag affects duration calculations

---

### 5. Ball Pass in runInboundSetup

**File:** `turnAnimation.js` (line 1516)

**Current Implementation:**
```javascript
await runPass(scene, {
  fromId: sfId,
  toId: pgId,
  duration: 500,  // ❌ HARDCODED
  easing: "Sine.easeInOut"
});
```

**Note:** This might be intentional - pass speeds may need to be different from player movement speeds. However, it should still use distance-based calculation for consistency.

**Status:** ⚠️ **REVIEW NEEDED** (May be intentional)

---

## Summary Table

| Animation Type | File | Line(s) | Status | Priority |
|---------------|------|---------|--------|----------|
| HCO step animations | `turnAnimation.js` | 1924-1928 | ✅ Working | - |
| FCP/HCT step animations | `ShotAnimationSystem.js` | 405-413 | ✅ Working | - |
| BIP player positioning | `AnimationEngine.js` | 332-358 | ✅ Working | - |
| Inbound setup | `turnAnimation.js` | 1329-1441 | ✅ Working | - |
| DREB outlet step | `turnAnimation.js` | 554-692 | ✅ Working | - |
| Opening tip | `openingTip.js` | 100-171 | ✅ Working | - |
| Free throw | `freeThrow.js` | 101-127 | ✅ Working | - |
| Fast break | `fastBreak.js` | 403-1019 | ✅ Working | - |
| **Get-back players (offense)** | `ShotAnimationSystem.js` | 606-627 | ❌ **FIX NEEDED** | **HIGH** |
| **Get-back players (defense)** | `ShotAnimationSystem.js` | 590-604 | ❌ **FIX NEEDED** | **HIGH** |
| **Rebounder to ball** | `ShotAnimationSystem.js` | 871 | ❌ **FIX NEEDED** | **HIGH** |
| **Non-rebounders collapse** | `ShotAnimationSystem.js` | 986 | ❌ **FIX NEEDED** | **HIGH** |
| **Player to rebound spot** | `ShotAnimationSystem.js` | 1037 | ❌ **FIX NEEDED** | **HIGH** |
| Initial positioning | `ShotAnimationSystem.js` | 270 | ❌ **FIX NEEDED** | **MEDIUM** |
| **BIP → HCO transition** | Multiple | - | ⚠️ **INVESTIGATE** | **HIGH** |
| Ball pass (inbound) | `turnAnimation.js` | 1516 | ⚠️ Review | **LOW** |

---

## Recommended Fix Priority

### Priority 1: Critical User-Reported Issues
1. **BIP → HCO Transition** - User specifically reported this
2. **Get-Back Players** - Very noticeable during shots
3. **Rebound Positioning** - Very noticeable during rebounds

### Priority 2: Other Hardcoded Durations
4. **Initial Positioning** - Less noticeable but should be fixed
5. **Ball Pass Duration** - Review if intentional

---

## Implementation Pattern

For all fixes, use this pattern:

```javascript
// Import at top of file
import { getPlayerDuration } from './turnAnimation.js';
// OR if in turnAnimation.js itself, use the function directly

// Replace hardcoded duration:
const duration = getPlayerDuration(sprite, targetX, targetY);

// For transitions (long movements), use:
const duration = getPlayerDuration(sprite, targetX, targetY, true); // isTransition = true
```

---

## Testing Checklist

After implementing fixes:
- [ ] Get-back players move at consistent speed during shots
- [ ] Rebound positioning animations use consistent speed
- [ ] BIP → HCO transition is smooth and consistent
- [ ] All animations respect game speed settings (Slow/Normal/Fast)
- [ ] No "jetting" or super-fast movements
- [ ] No super-slow movements for short distances
- [ ] Animations feel organic and human-like

---

## Related Documents

- `docs/To Do/animation_speed_edge_cases.md` - Previous edge cases document
- `docs/master_game_doc.md` - Distance-based speed system documentation (lines 2968-3045)
- `docs/animation_system.md` - Animation system documentation (lines 2398-2475)

