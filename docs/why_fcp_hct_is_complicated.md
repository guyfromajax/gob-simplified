# Why FCP/HCT is Complicated 🏀

## The Simple Answer

FCP/HCT is complicated because it needs to do **TWO things in sequence**:
1. **Animate a skeleton** (press break/trap break sequence with multiple steps)
2. **Then animate a shot**

HCO shots only need to do **ONE thing**:
1. **Animate a shot** (simple player movement + shot)

---

## The Detailed Answer

### 1. Multi-Phase Sequences

**FCP/HCT has multiple phases:**

```
Phase 1: Setup
→ Players position for press/trap defense
→ Turn type: BASELINE_INBOUND with next_defensive_setup = "FCP" or "HCT"

Phase 2: Press Break / Trap Break (THE SKELETON)
→ Offense tries to break the pressure
→ Multiple steps: players move, passes happen, ball moves around
→ This is a "skeleton animation" - a sequence of steps

Phase 3: Shot Attempt (if they break the press)
→ Player shoots the ball
→ Turn type: MAKE or MISS with fcp_shot = true or hct_shot = true
```

**HCO shots are simpler:**

```
Phase 1: Shot
→ Players move to positions
→ Player shoots the ball
→ Done!
```

### 2. Skeleton Animations

**What is a skeleton?**
- A skeleton is a **multi-step animation sequence**
- Each step has players moving to different positions
- Passes happen between steps
- The ball moves from player to player
- It's like a choreographed dance with multiple moves

**FCP/HCT needs skeletons:**
- The press break sequence IS a skeleton
- Example: Player 1 passes to Player 2, Player 2 moves up court, Player 2 passes to Player 3, Player 3 shoots
- This is 3-4 steps of animation BEFORE the shot

**HCO shots don't have skeletons:**
- HCO shots are simple: players move to positions, then shoot
- No complex multi-step sequence
- Just basic player movement + shot

### 3. State Persistence

**FCP/HCT state needs to persist across turns:**

```
Turn 1: BASELINE_INBOUND
→ next_defensive_setup = "FCP"
→ System remembers: "We're in FCP mode now!"

Turn 2: MAKE or MISS
→ fcp_shot = true
→ System still remembers: "We're in FCP mode!"
→ System knows: "This is an FCP shot attempt, animate the skeleton first!"

Turn 3: (After shot)
→ System clears: "FCP mode is done!"
```

**HCO shots don't need state persistence:**
- Each HCO shot is independent
- No need to remember previous turns
- Just: "Here's a shot, animate it!"

### 4. Why ShotAnimationSystem CAN Handle It (Updated!)

**UPDATE (January 2025):** FCP/HCT shots are now routed through `ShotAnimationSystem` because they're structured identically to HCO shots!

**ShotAnimationSystem handles skeleton animations:**

```javascript
// ShotAnimationSystem does:
1. Get maxSteps from turnData.animations
2. Loop through skeleton steps (for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++))
   - Move players for each step
   - Handle passes between steps (via passDetection.js)
   - Track ball ownership
3. When skeleton is done, handle shot
   - Call handleShotAtStep() → shootBall()
   - Handle rebound
4. Done!
```

**playTurnAnimation() does the same thing:**

```javascript
// playTurnAnimation() does:
1. Get maxSteps from turnData.animations
2. Loop through skeleton steps (for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++))
   - Move players for each step
   - Handle passes between steps (via passDetection.js)
   - Track ball ownership
3. When skeleton is done, handle shot
   - Call shootBall()
   - Handle rebound
4. Done!
```

**They're identical!** Both use skeleton animations from `turnData.animations` array.

### 5. The Technical Difference

**HCO Shot Flow:**
```
AnimationRouter → AnimationEngine → ShotAnimationSystem
→ Move players (skeleton steps if present)
→ Shoot ball
→ Handle rebound
→ Done!
```

**FCP/HCT Shot Flow (Updated January 2025):**
```
AnimationRouter → AnimationEngine → ShotAnimationSystem
→ Loop through skeleton steps (3-4 steps)
  → Step 1: Move players, pass ball
  → Step 2: Move players, pass ball
  → Step 3: Move players, pass ball
→ Step 4: Shoot ball (via shootBall())
→ Handle rebound
→ Done!
```

**FCP/HCT Setup Flow (Non-Shot Outcomes):**
```
Direct call to playTurnAnimation()
→ Loop through skeleton steps
→ Handle outcome (FOUL, TURNOVER, HCO transition)
→ Done!
```

**Note:** FCP/HCT shot attempts now use the same routing as HCO shots (AnimationRouter → ShotAnimationSystem) because they have identical structure. Only non-shot outcomes (fouls, turnovers, HCO transitions) use `playTurnAnimation()` directly.

---

## Visual Comparison

### HCO Shot (Simple)
```
[Player Movement] → [Shot] → [Rebound] → Done!
```

### FCP/HCT Shot (Complicated)
```
[Setup Phase] → [Skeleton Step 1] → [Skeleton Step 2] → [Skeleton Step 3] → [Shot] → [Rebound] → Done!
```

---

## Current Routing (Updated January 2025)

**FCP/HCT Shot Attempts:**
- Route through `AnimationRouter → ShotAnimationSystem` (same as HCO shots)
- `ShotAnimationSystem` handles skeleton animations + shot
- Unified code path for all shot attempts

**FCP/HCT Setup Turns (Non-Shot Outcomes):**
- Route through `playTurnAnimation()` directly
- Handles skeleton animations + outcome (FOUL, TURNOVER, HCO transition)
- No shot involved, so doesn't use `ShotAnimationSystem`

**Why This Works:**
- `ShotAnimationSystem` can handle skeleton animations (it loops through `turnData.animations` just like `playTurnAnimation()`)
- FCP/HCT shots have identical structure to HCO shots: skeleton → shot
- Unified routing simplifies the codebase and ensures consistent behavior

---

## Summary

**FCP/HCT is complicated because:**

1. ✅ **Multi-phase sequences** - Setup → Skeleton → Shot/Outcome
2. ✅ **Skeleton animations** - Multi-step press break sequences
3. ✅ **State persistence** - Needs to remember "we're in FCP mode" across turns
4. ✅ **Dual routing** - Shot attempts use `ShotAnimationSystem`, setup turns use `playTurnAnimation()`
5. ✅ **Multiple outcomes** - Can result in shot, turnover, foul, or transition to HCO

**HCO shots are simple because:**

1. ✅ **Single phase** - Just shoot!
2. ✅ **No skeleton** - Just basic player movement
3. ✅ **No state tracking** - Each shot is independent
4. ✅ **Simple routing** - Can use ShotAnimationSystem
5. ✅ **One outcome** - Make or miss (then rebound)

---

## Current Status (January 2025)

✅ **FCP/HCT shot attempts** now route through `AnimationRouter → ShotAnimationSystem` (unified with HCO shots)
✅ **FCP/HCT setup turns** route through `playTurnAnimation()` (for non-shot outcomes)
✅ **State tracking** implemented on scene level (`scene.currentPressureType`, `scene.pressureSequenceActive`)
✅ **Backend** generates correct turn sequence (BASELINE_INBOUND → FCP/HCT setup turn)

The system is now streamlined and working correctly!

