# Stopper System - Future Enhancements

This document tracks future enhancements for the HCO Stopper System, which truncates skeleton animations and adds stopper steps for non-HCO results (fouls, turnovers, steals).

## Current Implementation

The stopper system is currently implemented in `BackEnd/engine/phase_resolution.py` (lines 1652-1738). It:
- Truncates HCO skeletons when the result is not "HCO"
- Adds a stopper step as the final step with the appropriate event type
- Handles ball handler position for the stopper step

## Future Enhancements

### 1. Strategic Step Selection for Turnovers/Steals

**Current State:**
- Turnovers (`DEAD_BALL_TURNOVER`) and steals (`STEAL`) currently use the middle step as a placeholder
- Fouls use random step selection (which is appropriate)

**Enhancement Needed:**
- Implement strategic step selection based on:
  - Player attributes (ball handler's `BH` vs defender's `ST`)
  - Player dynamics at each step
  - Defensive matchup effectiveness
  - Game situation (score, time, quarter)

**Location:** `BackEnd/engine/phase_resolution.py` (line ~1667)

**Example Logic:**
```python
# Analyze each step to find the most likely point of failure
# Consider: ball handler's BH attribute, defender's ST attribute,
# pressure situations, passing difficulty, etc.
```

---

### 2. Defensive Player Selection for Steals

**Current State:**
- Steal stopper step is created but doesn't specify which defensive player makes the steal
- Placeholder comment exists in code

**Enhancement Needed:**
- Determine which defensive player makes the steal based on:
  - Defensive positioning at the stop step
  - Player attributes (defender's `ST` vs ball handler's `BH`)
  - Matchup analysis
  - Proximity to ball handler

**Location:** `BackEnd/engine/phase_resolution.py` (line ~1727)

**Example Logic:**
```python
# Find defensive player closest to ball handler at stop step
# Consider: defensive positioning, ST attribute, matchup effectiveness
# Add defensive player to stopper step pos_actions with "steal" action
```

---

## Related Files

- `BackEnd/engine/phase_resolution.py` - Main stopper system implementation
- `BackEnd/models/animator.py` - Skeleton to animation conversion (may need updates for stopper steps)
- `FrontEnd/static/js/phaser/animation/` - Frontend animation handling (may need updates for stopper animations)

