# Fast Break Outlet Pass Ball Detachment Bug

## Problem Description

In Fast Break sequences, when the outlet passer receives the pass, the ball detaches from the ball handler for the next animation. The ball incorrectly stays where the outlet receiver received the pass while all players correctly animate to their spots on the next step (whether it's a shot attempt or defensive stop).

## Current Flow

### 1. Outlet Phase (`animateOutletPhase` in `fastBreak.js`)

- **Line 129**: Ball attached to passer (outlet_passer)
- **Lines 178-183**: Outlet receiver moves to neutral outlet spot
- **Lines 262-267**: `runPass()` executes the outlet pass
- **Line 618 in `ballTween.js`**: `runPass` attaches ball to receiver when pass completes

### 2. After Outlet Phase

- **Lines 71-73**: Transition to FastBreak state
- **Lines 96-104**: Routes to either:
  - `animateFastBreakShot()` (line 99) - for shot attempts
  - `animateDefensiveStop()` (line 103) - for defensive stops

### 3. The Issue

- In `animateFastBreakShot()` (line 302): `attachBallToPlayer(scene, ballSprite, shooterSprite)` - attaches to shooter
- In `animateDefensiveStop()` (line 582 or 712): `attachBallToPlayer(scene, ballSprite, ballHandlerSprite)` - attaches to ball handler
- **Problem**: Between the outlet pass completing and these functions running, the ball may be getting detached or not properly following the receiver if they move.

## Root Cause Hypotheses

1. **Timing Issue**: The ball may be getting detached between when `runPass` completes and when the next phase starts.

2. **Ball Following System**: The ball following system may be stopping when the receiver moves, or the receiver's movement may not be triggering ball following.

3. **State Transition**: The FastBreak state transition (line 71-73) might be clearing ball attachment state.

4. **Missing Attachment**: The outlet receiver may not be the shooter/ball handler, so the ball isn't being reattached to the correct player.

## Key Questions to Investigate

1. Is the outlet receiver always the shooter/ball handler in the next phase?
2. Does the ball following system continue after the outlet pass completes?
3. Is there any code that detaches the ball between the outlet phase and the next phase?

## Likely Fix Location

The fix should ensure that:
1. After `runPass` completes in `animateOutletPhase` (line 267), the ball remains attached to the receiver and follows them.
2. OR, in `animateFastBreakShot`/`animateDefensiveStop`, ensure the ball is attached to the correct player (outlet receiver if they're the shooter/ball handler) before any movement.

## Files Involved

- `FrontEnd/static/js/phaser/animation/fastBreak.js` - Main Fast Break animation logic
- `FrontEnd/static/js/phaser/animation/ballTween.js` - Pass animation and ball attachment (`runPass` function)
- `FrontEnd/static/js/phaser/animation/BallControllerAdapter.js` - Ball attachment utilities (`attachBallToPlayer`)

## Status

**Status**: Documented - Awaiting fix implementation

**Priority**: Medium (affects Fast Break animations but doesn't break gameplay)

