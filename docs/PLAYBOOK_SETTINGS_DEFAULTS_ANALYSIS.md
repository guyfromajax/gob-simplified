# Playbook Settings Defaults Analysis

> **Last Updated:** January 2025  
> **Status:** Analysis - Awaiting Decision

This document analyzes what the default values should be for `playbook_settings` initialization.

---

## Current State

### Documentation (user-flow.md)
**States:** "Equal distribution among the number of plays available in each section"

### Frontend Code (playbooks.js initDefaults())
**Current Behavior:**
- Motion: First play = 100%, all others = 0%
- Set Play Inside: First play = 100%, second = 0%
- Set Play Attack: First play = 100%, second = 0%
- Set Play Outside: First play = 100%, second = 0%
- Man Defense: First play = 100%, others = 0%
- Zone Defense: First play = 100%, others = 0%

**This is NOT equal distribution** - it's "first play gets everything"

### Training System (training_execution_v2.py)
**Fallback Behavior:**
- When `playbook_settings` is missing or empty, uses **even distribution**
- Divides points equally among all plays in each section

---

## Options for Default Initialization

### Option A: Equal Distribution (Matches Documentation & Training Fallback)

**Approach:** Divide 100% equally among all plays in each section

**Example:**
- Motion (3 plays): 33.33%, 33.33%, 33.34%
- Set Play Inside (2 plays): 50%, 50%
- Zone Defense (3 plays): 33.33%, 33.33%, 33.34%

**Pros:**
- ✅ Matches documentation
- ✅ Matches training fallback behavior
- ✅ Consistent with "equal distribution" concept
- ✅ No single play dominates by default

**Cons:**
- ⚠️ Requires rounding logic (100% must total exactly)
- ⚠️ Different from current frontend behavior

### Option B: First Play = 100% (Matches Current Frontend)

**Approach:** First play in each section gets 100%, all others = 0%

**Example:**
- Motion: First play = 100%, others = 0%
- Set Play Inside: First play = 100%, second = 0%

**Pros:**
- ✅ Matches current frontend behavior
- ✅ Simple (no rounding needed)
- ✅ Clear default (one play per section)

**Cons:**
- ❌ Does NOT match documentation ("equal distribution")
- ❌ Does NOT match training fallback (even distribution)
- ❌ Inconsistent with stated defaults

### Option C: Equal Distribution with Rounding

**Approach:** Equal distribution, but handle rounding to ensure 100% total

**Implementation:**
```python
def calculate_equal_distribution(play_count):
    if play_count == 0:
        return {}
    base_percentage = 100 // play_count
    remainder = 100 % play_count
    percentages = [base_percentage] * play_count
    # Distribute remainder to first N plays
    for i in range(remainder):
        percentages[i] += 1
    return percentages
```

**Example:**
- Motion (3 plays): 34%, 33%, 33% (totals 100%)
- Set Play Inside (2 plays): 50%, 50%
- Zone Defense (3 plays): 34%, 33%, 33%

**Pros:**
- ✅ Matches documentation
- ✅ Always totals exactly 100%
- ✅ Handles any number of plays

**Cons:**
- ⚠️ Slightly uneven (first play gets +1% if remainder exists)

---

## Recommendation: Option C (Equal Distribution with Rounding)

**Reasoning:**
1. Matches documentation ("equal distribution")
2. Matches training fallback behavior
3. Always totals exactly 100%
4. Most SS&S (consistent across system)

**Implementation:**
- Calculate equal distribution per section
- Round to ensure 100% total
- Initialize all sections with equal percentages
- Initialize `slot_assignments` as empty `{}`
- Initialize `motion_dropdowns` as empty `{}`

---

## Slot Assignments & Motion Dropdowns Defaults

### Slot Assignments
**Default:** Empty object `{}`
- User must explicitly assign plays to slots 1-6
- No default assignments

### Motion Dropdowns
**Default:** Empty object `{}`
- User must explicitly select Inside/Attack/Outside for each motion play
- No default dropdown values

---

## Questions for Decision

1. **Percentage Distribution:** Should we use equal distribution (Option C) or first-play-100% (Option B)?
2. **Slot Assignments:** Should we initialize with default slot assignments (per user-flow.md Playcall Center plays) or leave empty?
3. **Motion Dropdowns:** Should we initialize with defaults or leave empty?

---

## References

- **Docs:** `docs/To Do/user-flow.md` - Lines 150-167 (Default Game Plan and Playbooks Settings)
- **Code:** `FrontEnd/static/playbooks.js` - `initDefaults()` (lines 63-117)
- **Code:** `BackEnd/models/training_execution_v2.py` - Even distribution fallback (lines 1335-1411)

