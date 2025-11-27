# Fast Break Landing Spot Fix

## Problem
Made fast break shots were landing at a different position than made free throws, HCO shots, and OREB putbacks.

## Root Cause

**Why this was thrown off:**

1. **Migration to `animateShotToRim()`**: Fast break shots were migrated from using `shootBall()` to using `animateShotToRim()` helper (see comment "✅ STEP 3 MIGRATION" on line 461).

2. **Missing adjustment logic**: When migrating, the made-shot landing adjustment wasn't copied over. The old `shootBall()` function had this adjustment (line 311-313 in `ballManager.js`), but it wasn't included in the fast break migration.

3. **Incorrect comment**: The comment on line 452-453 said:
   ```javascript
   // ✅ FIX: Use exact rim coordinates for all shots (matches putbacks and free throws)
   // No adjustment needed - ball should land at exact rim position
   ```
   This was **incorrect** - putbacks and free throws DO adjust for made shots, and the comment incorrectly claimed fast breaks matched them.

4. **Inconsistent with other shot types**: All other shot types adjust landing position for made shots:
   - `ballManager.js` (line 311-313): Adjusts for made shots
   - `ShotAnimationSystem.js` (line 1335-1345): Adjusts for made shots
   - `fastBreak.js` (line 452-454): Was NOT adjusting ❌

## The Fix

**Added made-shot landing adjustment to match other shot types:**

```javascript
// ✅ FIX: Adjust rim position for made shots (1 grid unit closer to shooter)
// This matches the adjustment in ballManager.js and ShotAnimationSystem.js
// Home team (shoots at x=91): reduce by 1 → 90
// Away team (shoots at x=9): increase by 1 → 10
const adjustedBasket = { ...basket };
if (turnData.result_type === "MAKE") {
  adjustedBasket.x = isHomeOffense ? basket.x - 1 : basket.x + 1;
}
const rimPx = gridToPixels(adjustedBasket.x, adjustedBasket.y, width, height);
```

## Why This Happened

**The migration process:**
1. Fast break shots were refactored to use `animateShotToRim()` helper
2. The helper was designed to be a simple "animate ball to rim" function
3. The made-shot adjustment logic was left in the caller (`fastBreak.js`)
4. But it wasn't copied over during migration
5. The comment incorrectly assumed no adjustment was needed

**The lesson:**
- When migrating code, ensure all logic is preserved
- Comments should be verified against actual behavior
- Consistency checks should be done across similar functions

## Result

Now all made shots land consistently:
- ✅ Fast break shots: 1 unit closer to shooter
- ✅ HCO shots: 1 unit closer to shooter
- ✅ Free throws: 1 unit closer to shooter
- ✅ OREB putbacks: 1 unit closer to shooter

