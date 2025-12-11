# HCO Shot Animation: MAKE vs MISS Comparison

## Code Flow Comparison

### Common Flow (Both MAKE and MISS)

1. **Step Loop** (lines 359-566 in `ShotAnimationSystem.js`):
   - For each step:
     - Detect pass at step (line 412)
     - Loop through all animations:
       - **Offensive players**: Call `animateStep()` immediately → promise stored in `offensivePromises` → tween starts immediately
       - **Defensive players**: Call `animateStep()` immediately → promise stored in `defensivePromises` → tween starts immediately
     - **Phase 1**: Wait for passer to complete (if pass exists)
     - **Phase 2**: `await Promise.all(passAndDefensePromises)` - waits for pass + defensive animations
     - If `shotInfo` exists: Call `handleShotAtStep()`

2. **handleShotAtStep()** (line 590):
   - Calls `animateBallFlight()` (line 617)
   - After ball flight: Calls `handleMadeShot()` OR `handleMissedShot()` based on `result_type`

### MAKE Shot Flow (Working Correctly)

**After Phase 2 completes:**
1. `handleShotAtStep()` → `animateBallFlight()` → `handleMadeShot()` (line 765)
2. `handleMadeShot()`:
   - Holds ball at rim (1 second delay, line 789-795)
   - **Stops get-back player animations** (lines 799-806) - kills `_getBackTweens`
   - Shows announcement
   - Transitions to IDLE state
   - **No new player animations created**

**Key Point**: After Phase 2, no new tweens are created on defensive player sprites. Defensive animations from Phase 2 complete naturally.

### MISS Shot Flow (Animating Incorrectly)

**After Phase 2 completes:**
1. `handleShotAtStep()` → `animateBallFlight()` → `handleMissedShot()` (line 905)
2. `handleMissedShot()`:
   - Animates ball bounce (line 909)
   - Calls `handleEmbeddedRebound()` (line 930)
3. `handleEmbeddedRebound()` (line 953):
   - Calls `animatePlayerCollapse()` (line 990)
   - Creates rebounder tween (lines 992-1027)
4. `animatePlayerCollapse()` (line 1078):
   - **Creates NEW tweens on ALL rebounders** (including defenders) to move them toward rebound spot (lines 1129-1140)
   - These tweens are created on the SAME sprites that just finished Phase 2 defensive animations

**Key Point**: After Phase 2, `animatePlayerCollapse()` creates NEW tweens on defensive player sprites. If Phase 2 defensive tweens are still active, Phaser will kill them and start the new collapse tweens, making defenders appear to "jump" from guard positions to rebound spot.

## The Problem

### Hypothesis 1: Tween Interruption
When `animatePlayerCollapse()` creates new tweens on defender sprites (line 1129), those sprites might still have active tweens from Phase 2. Phaser kills the old tweens and starts new ones, causing visual "jump".

**But**: This would only affect the END of the turn (after shot), not every step with a pass.

### Hypothesis 2: Defensive Tweens Start Too Early
Defensive promises are created during the loop (line 459) and `animateStep()` starts tweens immediately (line 463 in `animateStep.js`). By the time Phase 2's `Promise.all()` starts waiting, defensive tweens might already be partially complete, making them appear to start before the pass.

**But**: This should affect both MAKE and MISS equally.

### Hypothesis 3: Timing Difference
For MISS shots, something causes defensive tweens to complete faster or pass animation to start later, making the timing mismatch more visible.

**But**: The logs show pass detection and Phase 2 timing are the same for both.

### Hypothesis 4: Rebound Animation Interference
The rebound animation (`animatePlayerCollapse`) might be starting DURING the step loop (not just at the end), interfering with defensive animations in earlier steps.

**But**: `animatePlayerCollapse()` is only called after `handleShotAtStep()`, which is only called after Phase 2 completes for the shot step.

## Key Differences

| Aspect | MAKE | MISS |
|--------|------|------|
| After Phase 2 | No new player animations | `animatePlayerCollapse()` creates new tweens on defenders |
| Defensive tweens | Complete naturally | May be interrupted by collapse tweens |
| Ball animation | Held at rim, then hidden | Bounced, then rebound animation |
| Player animations after shot | Only get-back animations (stopped early) | Collapse animations (new tweens on same sprites) |

## Questions to Investigate

1. **When do defensive tweens actually start?** 
   - Are they starting immediately when `animateStep()` is called (during loop)?
   - Or only when `Promise.all()` begins waiting?

2. **Are defensive tweens still active when `animatePlayerCollapse()` is called?**
   - If yes, Phaser will kill them and start new tweens
   - This would cause visual "jump" but only at the end

3. **Is there a timing difference in Phase 2 execution between MAKE and MISS?**
   - Maybe Phase 2 completes faster for MISS, making defensive tweens appear to start earlier?

4. **Does `animatePlayerCollapse()` affect earlier steps?**
   - It's only called after the shot step, so it shouldn't affect earlier pass steps
   - But maybe there's some state that's set earlier?

## Next Steps

1. Add timing logs to see exactly when defensive tweens start vs when Phase 2 begins
2. Check if defensive tweens are still active when `animatePlayerCollapse()` is called
3. Verify that `animatePlayerCollapse()` is only called after the shot step, not during earlier steps

