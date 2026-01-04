# HCO Animation Sync Bug

## Bug Description

In HCO skeleton step animations, there are instances where ball pass animation and defensive player movement are not synchronized. The issue manifests as defensive players moving **before** the pass animation, when they should move **simultaneously** with the pass.

**Note:** This is the **same bug** documented in `docs/master_game_doc.md` (lines 2790-2932) as "Defensive Player + Pass Animation Synchronization Fix". The `offenseTeamId` resolver fix was implemented in January 2025, but it only partially addressed the issue. The bug still exists specifically in HCO Shot Miss => DREB scenarios, where a conflict between skeleton defensive tweens and collapse animations causes the synchronization issue. The `offenseTeamId` fix may have helped in other scenarios, but did not resolve this specific case.

## Specific Flow with Bug

**HCO Shot Miss, No Shooting Foul => DREB**

This bug occurs **100% of the time** when the following criteria are met:
- HCO skeleton step with a pass
- HCO result is a missed shot attempt with a DREB

**Impact:** This disrupts **all step animations in the turn with a pass**, indicating it is a bug that throws off the entire skeleton animation sequence.

## Working Scenarios

All other HCO results animate correctly:

1. ✅ **HCO Shot Make - No Shooting Foul**
2. ✅ **HCO Shot Make + Shooting Foul**
3. ✅ **HCO Shot Miss + Shooting Foul**
4. ✅ **HCO Shot Miss => OREB**
   - Note: In OREB instances, all possible scenarios following this animate correctly:
     - Kickout Pass
     - Putback Attempt Make
     - Putback Attempt Miss => OREB
     - Putback Attempt Miss => DREB

## Key Insight

The DREB is only involved in the bug when it's **paired with the missed shot in the HCO turn**. When DREB is paired with a missed shot in an OREB turn, the turn animates properly.

## Investigation History

### Attempted Fixes (All Reverted)

1. **Defensive Tween Timing Fix (Reverted)**
   - Attempted to defer defensive tween creation until Phase 2 (when pass starts)
   - This broke HCO step animations entirely (steps were skipped except entry and shot attempt)
   - Reverted: `ef217cdf`

2. **Standalone DREB Setup (Reverted)**
   - Attempted to make DREB a standalone setup step (similar to OREB Putback Miss => DREB)
   - Skipped embedded DREB handling in shot turn, moved to next HCO turn's setup phase
   - This caused outlet pass to be skipped in HCO => DREB => HCO transitions
   - Reverted: `654f6c34`

3. **Kill Skeleton Defensive Tweens Before animatePlayerCollapse() (Current)**
   - Added fix to kill skeleton defensive tweens before `animatePlayerCollapse()` runs
   - Also kills `collapseTweens` before `handleDefensiveRebound()` / outlet pass starts
   - Status: Implemented but not yet verified if it resolves the issue
   - Commit: `6101a653`
   - Marked with `✅ TEMP FIX` comments for easy reversion

### Root Cause Hypothesis

The issue appears to be a **conflict between multiple animation systems**:

1. **Skeleton defensive tweens** are still running from HCO skeleton steps
2. **`animatePlayerCollapse()`** starts new tweens on the same defenders (moving them toward ball bounce spot)
3. **Outlet pass animation** (in `runDefensiveReboundSetup()`) starts while collapse tweens may still be active

This creates a visual conflict where defenders appear to move before passes because:
- Skeleton defensive tweens start during the loop (Phase 1)
- `animatePlayerCollapse()` starts new tweens on the same players
- These tweens conflict, causing defenders to move incorrectly

### Why Other Scenarios Work

- **HCO Shot Make**: No `animatePlayerCollapse()` is called, so no conflict
- **HCO Shot Miss + Shooting Foul**: Goes to FREE_THROW, no rebound handling
- **HCO Shot Miss => OREB**: `animatePlayerCollapse()` runs, but no outlet pass (OREB handles differently)
- **OREB Putback Miss => DREB**: DREB is handled as a **separate turn**, not embedded in the shot turn, so no conflict

## Code Locations

### Key Files

- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`
  - `animatePlayerMovement()`: Creates skeleton defensive tweens
  - `handleMissedShot()`: Calls `handleEmbeddedRebound()`
  - `handleEmbeddedRebound()`: Calls `animatePlayerCollapse()` and `handleDefensiveRebound()`
  - `animatePlayerCollapse()`: Starts new tweens on non-rebounders (including defenders)
  - `handleDefensiveRebound()`: Calls `runDefensiveReboundSetup()` for outlet pass

- `FrontEnd/static/js/phaser/animation/turnAnimation.js`
  - `runDefensiveReboundSetup()`: Handles outlet pass for DREB => HCO transitions

### Current Fix Location

- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`
  - Lines ~370-387: Tracks defensive player IDs during skeleton animation
  - Lines ~1155-1175: Kills skeleton defensive tweens before `animatePlayerCollapse()`
  - Lines ~1230-1245: Kills `collapseTweens` before `handleDefensiveRebound()`

## Next Steps for Future Investigation

1. **Verify if current fix works**: Test if killing skeleton defensive tweens before `animatePlayerCollapse()` resolves the sync issue

2. **If fix doesn't work, investigate**:
   - Timing of when `animatePlayerCollapse()` tweens are killed vs when outlet pass starts
   - Whether outlet pass should wait for `collapseTweens` to fully complete
   - Whether `animatePlayerCollapse()` should exclude defenders entirely (only animate offensive rebounders)

3. **Alternative approaches**:
   - Delay outlet pass until all collapse animations complete
   - Exclude defenders from `animatePlayerCollapse()` (they shouldn't collapse for DREB anyway)
   - Handle DREB as a separate turn (like OREB Putback Miss => DREB), but ensure outlet pass executes correctly

## Related Commits

- `6101a653`: TEMP FIX: Kill skeleton defensive tweens before animatePlayerCollapse()
- `654f6c34`: Revert to embedded DREB handling in HCO shot turns
- `ef217cdf`: Revert "Fix defensive tween timing: defer creation until Phase 2"

## Notes

- The bug is **turn-wide**: If one pass step has the issue, all pass steps in that turn have it
- The bug is **100% reproducible** for HCO Shot Miss => DREB (no shooting foul)
- All other HCO result types animate correctly
- OREB scenarios work correctly even when they lead to DREB

