# Motion Offense System - Design Document

**Date:** January 2025  
**Status:** Design Complete - Awaiting Implementation

---

## Overview

Motion offenses differ fundamentally from Set Plays in execution. Rather than having a single ideal outcome with variant skeletons (successful/contested/broken), Motion offenses use **infinite circular loops** where players cycle through positions until a turn-ending event occurs (shot, foul, turnover, steal).

---

## Core Principles

### 1. Circular Loop Structure
- Motion plays are built as **base loops** (no variant system)
- Final step should match first step (or explicitly loop back to step 0/1)
- Engine continues looping until a turn-ending event occurs
- No skeleton variants needed - just one base loop per motion play

### 2. Location-Based Shot Type Determination
Shot type is determined **dynamically** based on player location, not hard-coded in skeleton:

**Inside Shots:**
- Automatic if player is at lane spots: `lower lowPost`, `lower midPost`, `upper lowPost`, `upper midPost`, `midLane`, `basketSpot`
- Receives pass → shoots from that spot → inside shot
- Uses `playcall = "Inside"` for shot score calculation

**Outside Shots:**
- Any other location → shoot from current spot → outside shot
- Uses `playcall = "Outside"` for shot score calculation

**Attack Shots:**
- Player on non-lane spot (e.g., `upper wing`) chooses to drive
- **Two-step process**: 
  1. Step 1: `action: "drive"` to destination lane spot
  2. Step 2: `action: "shoot"` at destination lane spot
- Shoots from that lane spot → attack shot
- Uses `playcall = "Attack"` for shot score calculation
- **Note**: Two-step approach ensures proper drive animation and accurate shot location detection

### 3. Focus as Influence, Not Constraint
- Focus (Inside/Attack/Outside) **influences probability** of actions, doesn't lock players in
- "Inside" focus → more likely to pass to lane spots
- "Attack" focus → more likely to drive from non-lane spots
- "Outside" focus → more likely to shoot from current spot
- **Player attributes matter**: High IQ players can recognize better opportunities even if they don't match focus

### 4. No Variant Modifier System
- Motion plays do **NOT** use variant modifiers (successful/contested/broken)
- Shot calculation uses base attributes + defense + location-based playcall
- No `_variant` field needed in skeleton for Motion plays
- Set Plays continue to use variant system as they do now

---

## Drive Destination Logic

### Starting Position → Valid Destinations

**Upper Half Starting Positions:**
- Examples: `upper wing`, `upper corner`, `upper midWing`, `upper midCorner`
- Can drive to: `upper lowPost`, `upper midPost`, `upper bird`, `midLane`, `basketSpot`
- Cannot drive to: lower-side spots (unrealistic path)

**Lower Half Starting Positions:**
- Examples: `lower wing`, `lower corner`, `lower midWing`, `lower midCorner`
- Can drive to: `lower lowPost`, `lower midPost`, `lower bird`, `midLane`, `basketSpot`
- Cannot drive to: upper-side spots (unrealistic path)

**Central Starting Positions:**
- Examples: `key`, `topLane`, `deep key`
- Can drive to: **All destinations** (both upper and lower)
- Makes sense since they're central and can go either direction

### Defensive Stops
- Players can be stopped short of ideal destination
- Results in intermediate spots (e.g., `upper midPost` instead of `basketSpot`)
- Penalty applies (see below)

---

## Attack Shot Penalty System

### No Penalty (Ideal Spots)
- `basketSpot` (x = 10 or 90 depending on basket)
- `upper lowPost`
- `lower lowPost`

### Penalty Applies (Stopped Short)
- `upper midPost`, `lower midPost`
- `upper bird`, `lower bird`
- `midLane`
- Any other intermediate spot

### Penalty Calculation
```python
penalty = abs(shot_location_x - basket_spot_x)
shot_score -= penalty
```

**Notes:**
- Basket spot X: Home team offense = x=10, Away team offense = x=90
- Penalty is raw X difference (not scaled)
- Applied before final shot threshold check

---

## Execution Flow

### Step-by-Step Process

1. **Start Motion Loop**
   - Begin at step 0 of base skeleton
   - Continue step by step through loop

2. **Evaluate Opportunities at Each Step**
   - Is ball handler at a lane spot? → Can shoot inside
   - Is ball handler at non-lane spot? → Can shoot outside OR drive (attack)
   - Are teammates at lane spots? → Can pass for inside shot

3. **Focus Influences Probability**
   - Focus modifies probability of each action type
   - Player attributes (IQ) can override focus if better opportunity exists

4. **Decision Point**
   - If shot taken → determine shot type by final location
   - If drive chosen → select destination based on starting position
   - If pass chosen → continue to next step

5. **Shot Execution**
   - Determine `playcall` based on shot type (Inside/Attack/Outside)
   - Pass to `calculate_shot_score()` with appropriate playcall
   - Apply attack penalty if applicable (stopped short)
   - Execute shot with base calculation (no variant modifier)

6. **Loop Continuation**
   - If no ending event → continue to next step
   - If reach final step → loop back to step 0/1
   - Continue until shot, foul, turnover, or steal

---

## Database Structure

### Motion Play Documents

**Structure:**
```json
{
  "name": "4-1 Motion",
  "play_type": "motion",
  "play_focus": null,  // No default focus - set at runtime
  "skeletons": {
    "base_loop": {  // Single loop, no variants
      "steps": [
        {
          "step": 0,
          "timestamp": 0,
          "pos_actions": {...}
        },
        // ... more steps
        {
          "step": N,
          "loop_back_to": 0,  // Explicit loop marker
          "is_final_step": true
        }
      ]
    }
  },
  "game_stats": {...},
  "season_stats": {...}
}
```

**Key Requirements:**
- Final step must match first step OR have explicit `loop_back_to` marker
- All steps should have consistent player positioning
- Loop should be cohesive (smooth transition from final → first step)

### Plays to Build

1. **4-1 Motion** (currently exists, needs loop structure)
2. **3-2 Motion** (currently exists, needs loop structure)
3. **5-0 Motion** (currently exists, needs loop structure)
4. **4-1 Flex Motion** (currently exists, needs loop structure)

---

## Integration with Existing Systems

### Harmony with Set Plays

**Set Plays (Unchanged):**
- Continue using variant system (successful/contested/broken)
- Variant determines both skeleton AND shot modifier
- Works exactly as it does now

**Motion Plays (New):**
- Use base loop only (no variants)
- Location determines shot type
- Focus influences decisions
- No variant modifier applied

**Shared Systems:**
- Both use `generate_logic()` for result determination (SHOT vs non-SHOT)
- Both use `calculate_shot_score()` with playcall parameter
- Both use same shot threshold system
- Both use same defensive calculation logic

### `generate_logic()` Usage

**For Motion:**
- Determines result type: "SHOT", "O_FOUL", "D_FOUL", "DEAD_BALL_TURNOVER", "STEAL"
- Returns `lean_score` (not used for variant selection, but could be used for future enhancements)
- If result != "SHOT" → apply stopper system (truncate skeleton)

**For Set Plays:**
- Determines result type AND lean_score
- Lean_score selects skeleton variant
- Variant affects shot modifier

---

## Implementation Checklist

### Phase 1: Database Setup
- [ ] Build 4 Motion plays with synced loop structures
- [ ] Ensure final step matches first step (or has loop_back_to marker)
- [ ] Verify loop cohesion (smooth transitions)

### Phase 2: Engine Logic
- [ ] Implement location-based shot type determination
- [ ] Implement drive destination logic (upper/lower/central mapping)
- [ ] Implement attack shot penalty system
- [ ] Implement focus-based probability weighting
- [ ] Implement player attribute (IQ) override logic
- [ ] Implement loop continuation logic

### Phase 3: Integration
- [ ] Update `resolve_half_court_offense_logic()` to detect Motion plays
- [ ] Route Motion plays through new execution flow
- [ ] Ensure Set Plays continue working unchanged
- [ ] Test with all 4 Motion plays

### Phase 4: Testing
- [ ] Test loop continuation (multiple cycles)
- [ ] Test location-based shot type determination
- [ ] Test drive destinations for all starting positions
- [ ] Test attack shot penalties
- [ ] Test focus influence on decisions
- [ ] Test player IQ override logic

---

## Key Files to Modify

**Backend:**
- `BackEnd/engine/phase_resolution.py` - Motion execution logic
- `BackEnd/models/shot_manager.py` - Attack penalty application
- `BackEnd/models/turn_manager.py` - Playcall selection (already handles Motion)

**Database:**
- `plays` collection - Build 4 Motion plays with loop structures

**Constants:**
- May need location-to-X-coordinate mapping
- May need drive destination mapping

---

## Open Questions

1. **Location X Coordinates**: Do we have a mapping of location names to X coordinates, or should we extract from skeleton step data?

2. **Penalty Application**: Should attack penalty be applied in `calculate_shot_score()` when `playcall == "Attack"`, or in motion-specific logic before calling it?

3. **Focus Probability Weights**: What should the probability distribution be? (e.g., Inside focus: 70% inside actions, 20% attack, 10% outside?)

4. **IQ Override Threshold**: At what IQ level should players be able to recognize non-focus opportunities? Should it be a percentage chance or absolute threshold?

5. **Loop Detection**: Should we use explicit `loop_back_to` marker, or detect when final step matches first step?

---

## Notes

- Motion plays are fundamentally different from Set Plays - embrace the difference
- Keep it simple: location determines shot type, focus influences decisions
- Player attributes matter - smart players make better reads
- No need for complex flag systems - location is the flag

