# Animation System Future Improvements

This document tracks remaining improvements for the animation system that are not yet complete.

## Status Overview

- ✅ **Item 1: Complete Specialized Systems** - DONE
  - `ReboundAnimationSystem` and `PassAnimationSystem` are fully implemented and operational

- ✅ **Item 2: Migrate FCP/HCT to Handlers** - DONE
  - FCP/HCT now routes through `AnimationRouter` (same as HCO)
  - Routes to `SHOT_ATTEMPT` handler or respective handlers (FOUL, TURNOVER, etc.)
  - **Note:** Large commented-out block of old FCP/HCT routing code (lines 810-992 in `animateGameTurns.js`) could be cleaned up

- ⚠️ **Item 3: Consolidate Text Scroll** - PARTIALLY DONE
  - Text scroll is still being appended in 3 handlers in `AnimationEngine.js`:
    - `handleFreeThrow()` (line 265) - `appendToTextScroll()`
    - `handleTimeout()` (line 488) - `emit('textScroll')`
    - `handleDefensiveStop()` (line 615) - `appendToTextScroll()`
  - Comments say "Note: Announcements and score updates are handled by AnimationRouter" but text scroll is still in handlers
  - **Action Needed:** Move all text scroll appends to `AnimationRouter` for consistency

- ⚠️ **Item 4: Handler Documentation** - PARTIALLY DONE
  - Some JSDoc exists (class and some methods), but not all handlers have complete JSDoc
  - **Action Needed:** Add complete JSDoc comments to all handlers in `AnimationEngine.js`

## Remaining Tasks

### 1. Consolidate Text Scroll

**Goal:** Move all text scroll appends to `AnimationRouter` for consistency

**Current State:**
- Text scroll is appended in 3 handlers:
  - `handleFreeThrow()` - line 265
  - `handleTimeout()` - line 488
  - `handleDefensiveStop()` - line 615

**Action:**
1. Move text scroll logic to `AnimationRouter.finalizeTurnAfterAnimation()`
2. Remove text scroll appends from individual handlers
3. Ensure all turn types that need text scroll are handled consistently

**Files to Update:**
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js`
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js`

### 2. Handler Documentation

**Goal:** Add complete JSDoc comments to all handlers

**Current State:**
- Some JSDoc exists (class and some methods)
- Not all handlers have complete JSDoc documentation

**Action:**
1. Add JSDoc comments to all handler methods in `AnimationEngine.js`
2. Document parameters, return values, and behavior
3. Include examples where helpful

**Files to Update:**
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js`

### 3. Clean Up Legacy FCP/HCT Code (Optional)

**Goal:** Remove large commented-out block of old FCP/HCT routing code

**Current State:**
- Large commented-out block (lines 810-992) in `animateGameTurns.js`
- Code is no longer used since FCP/HCT routes through `AnimationRouter`

**Action:**
1. Review commented code to ensure nothing important is lost
2. Remove commented block if confirmed safe
3. Update any related documentation

**Files to Update:**
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js`

