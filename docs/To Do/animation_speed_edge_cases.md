# Animation Speed Edge Cases

> **Created**: January 2025  
> **Status**: Pending  
> **Related**: Bug 3 (Slow Animation Speed) - Main issue fixed, these are edge cases

## Overview

After fixing Bug 3 (replacing timestamp-based duration with distance-based calculations), the main animation speeds are now consistent. However, there are several edge cases where animations are still too fast and not using the distance-based speed system.

## Edge Cases to Fix

### 1. Rebound Positioning - Players Moving Too Fast

**Symptom**: Players moving into rebound position "jet very fast" instead of using distance-based speed.

**Location**: Likely in rebound animation logic (ShotAnimationSystem or ballManager.js)

**Investigation Needed**:
- Find where rebound positioning animations are triggered
- Check if they're using hardcoded durations or timestamp-based calculations
- Replace with `getPlayerDuration()` for distance-based calculation

**Files to Check**:
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js` (rebound handling)
- `FrontEnd/static/js/phaser/animation/ballManager.js` (rebound animations)
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` (rebound setup)

---

### 2. Get-Back Players on Shot Animations - Moving Too Fast

**Symptom**: Players getting back on defense (both teams) during shot animations are moving too fast.

**Location**: Likely in ShotAnimationSystem when animating players during ball flight

**Investigation Needed**:
- Find where get-back player animations are triggered during shots
- Check if they're using hardcoded durations or different speed calculations
- Replace with `getPlayerDuration()` for distance-based calculation

**Files to Check**:
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js` (player animations during shot)
- Look for code that animates non-shooter players during ball flight

---

### 3. IP→HCO Transition Step - Players Moving Faster Than HCO

**Symptom**: The step between Inbound Pass (IP) and HCO - players are moving faster than HCO instances, likely because they're covering longer distances (more x grid spots).

**Location**: Likely in transition logic between inbound and HCO

**Investigation Needed**:
- Find where IP→HCO transition animations are handled
- Check if they're using `isTransition = true` flag with `MAX_TRANSITION_DURATION` (3000ms cap)
- May need to adjust transition duration calculation or remove the cap for very long distances
- Ensure transition animations still feel smooth but match HCO speeds

**Files to Check**:
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` (transition logic)
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js` (HCO entry)
- Look for `getPlayerDuration(sprite, targetX, targetY, isTransition = true)` calls

**Note**: This might be intentional (transitions can be longer), but should still use distance-based calculation and respect game speed settings.

---

## Common Fix Pattern

All three edge cases should follow the same pattern:

**Before (likely):**
```javascript
// Hardcoded duration or timestamp-based
const duration = 500; // or (timestampDiff * 3)
```

**After:**
```javascript
import { getPlayerDuration } from './turnAnimation.js';

// Distance-based calculation
const { x: targetX, y: targetY } = gridToPixels(
  targetCoords.x,
  targetCoords.y,
  scene.game.config.width,
  scene.game.config.height
);
const duration = getPlayerDuration(sprite, targetX, targetY, isTransition);
```

---

## Priority

**Medium Priority** - These are edge cases that don't affect the core gameplay experience, but should be fixed for consistency and polish.

**Dependencies**:
- ✅ Bug 3 (main animation speed) - Fixed
- ⏳ Bug 4 (skipped passes) - Should verify first

---

## Testing Checklist

After fixing each edge case:
- [ ] Rebound positioning animations use distance-based speed
- [ ] Get-back players during shots use distance-based speed
- [ ] IP→HCO transitions use distance-based speed (may still be faster due to longer distances, but should respect game speed)
- [ ] All animations respect game speed buttons (Slow/Normal/Fast)
- [ ] Animations feel consistent across all scenarios

---

## Related Documents

- `docs/PHASE_2.5_BUG_LIST.md` - Main bug list
- `docs/animation_system.md` - Animation system documentation (includes distance-based speed system)

