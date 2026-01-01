# Playbook Settings Defaults Analysis

> **Last Updated:** February 2025  
> **Status:** ✅ **Backend Implemented** | ⚠️ **Frontend Pending**

This document analyzes what the default values should be for `playbook_settings` initialization.

## Implementation Status

### ✅ Backend: Implemented (February 2025)
- **Location:** `BackEnd/api/gameplan_routes.py` → `initialize_playbook_settings()`
- **Implementation:** Even distribution with rounding (Option C)
- **Status:** Fully operational - used when initializing new teams/franchises/tournaments
- **Features:**
  - Even distribution across all plays in each section
  - Rounding logic ensures totals = 100%
  - Position filters initialized (standard and PF populated)
  - Slot assignments and motion dropdowns initialized as empty `{}`

### ⚠️ Frontend: Not Updated
- **Location:** `FrontEnd/static/playbooks.js` → `initDefaults()`
- **Current Behavior:** Still uses "first play = 100%" approach
- **Status:** Needs update to match backend implementation
- **Impact:** Frontend UI shows different defaults than backend creates, causing inconsistency

---

## Current State

### Documentation (user-flow.md)
**States:** "Equal distribution among the number of plays available in each section"

### Frontend Code (playbooks.js initDefaults()) ⚠️ **OUTDATED**
**Current Behavior (Needs Update):**
- Motion: First play = 100%, all others = 0%
- Set Play Inside: First play = 100%, second = 0%
- Set Play Attack: First play = 100%, second = 0%
- Set Play Outside: First play = 100%, second = 0%
- Man Defense: First play = 100%, others = 0%
- Zone Defense: First play = 100%, others = 0%

**This is NOT equal distribution** - it's "first play gets everything"

**Note:** Backend now uses even distribution, but frontend still uses this old approach. This causes inconsistency when:
- User creates new team/franchise/tournament (backend initializes with even distribution)
- User opens Playbooks screen (frontend shows first play = 100%)
- User saves without changes (frontend values overwrite backend defaults)

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

## Recommendation: Option C (Equal Distribution with Rounding) ✅ **IMPLEMENTED**

**Reasoning:**
1. Matches documentation ("equal distribution")
2. Matches training fallback behavior
3. Always totals exactly 100%
4. Most SS&S (consistent across system)

**Backend Implementation (✅ Complete):**
- **Location:** `BackEnd/api/gameplan_routes.py` lines 206-400
- Calculate equal distribution per section
- Round to ensure 100% total (last play gets remainder)
- Initialize all sections with equal percentages
- Initialize `slot_assignments` as empty `{}`
- Initialize `motion_dropdowns` as empty `{}`
- Initialize `position_filters` with standard and PF plays populated

**Frontend Implementation (⚠️ Pending):**
- **Location:** `FrontEnd/static/playbooks.js` lines 63-117
- **Current:** Still uses first play = 100% approach
- **Needed:** Update `initDefaults()` to match backend even distribution logic

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

## Implementation Details

### Backend Implementation (✅ Complete)

**Function:** `initialize_playbook_settings()` in `BackEnd/api/gameplan_routes.py`

**Algorithm:**
```python
# For each section (motion, set_play_inside, etc.):
1. Get all plays in section
2. Sort by name for consistency
3. Calculate: percentage_per_play = 100.0 / len(plays)
4. For each play (except last):
   - Assign: round(percentage_per_play)
   - Subtract from remainder
5. Last play gets: round(remainder) to ensure total = 100%
```

**Example Output:**
- Motion (3 plays): 33%, 33%, 34% (totals 100%)
- Set Play Inside (2 plays): 50%, 50%
- Zone Defense (3 plays): 33%, 33%, 34%

**Position Filters:**
- `standard`: Populated with basic plays (3-2 Motion, 4-1 Motion, 5-0 Motion, Base Post Play, Pick & Roll, Double Screen For SG)
- `PF`: Populated with PF-specific plays (PF Post Motion, PF Post Up, PF High Post Drive, PF Corner Shot, PF Quick Jumper)
- `PG`, `SG`, `SF`, `C`: Empty arrays (can be populated later)

### Frontend Implementation (⚠️ Needed)

**Current Issue:** `initDefaults()` in `FrontEnd/static/playbooks.js` still uses:
```javascript
percentage: i === 0 ? 100 : 0  // First play = 100%, others = 0%
```

**Required Update:**
```javascript
// Calculate even distribution
const playCount = plays.length;
const basePercentage = Math.floor(100 / playCount);
const remainder = 100 % playCount;

plays.forEach((play, index) => {
  let percentage = basePercentage;
  // Distribute remainder to first N plays
  if (index < remainder) {
    percentage += 1;
  }
  this.sections[sectionKey][playId] = {
    percentage: percentage,
    slot: null,
  };
});
```

**Files to Update:**
- `FrontEnd/static/playbooks.js` - `initDefaults()` method (lines 63-117)

## Decisions Made ✅

1. **Percentage Distribution:** ✅ **Option C (Equal Distribution with Rounding)** - Backend implemented
2. **Slot Assignments:** ✅ **Leave empty `{}`** - Backend implemented
3. **Motion Dropdowns:** ✅ **Leave empty `{}`** - Backend implemented
4. **Position Filters:** ✅ **Initialize standard and PF** - Backend implemented

---

## Next Steps

### ⚠️ Frontend Update Required

1. **Update `initDefaults()` in `playbooks.js`**
   - Replace "first play = 100%" logic with even distribution
   - Match backend rounding algorithm
   - Ensure totals = 100% for all sections

2. **Test Consistency**
   - Verify frontend defaults match backend defaults
   - Test with new team/franchise/tournament creation
   - Ensure no overwrite issues when saving

3. **Update Documentation**
   - Mark this document as fully implemented once frontend is updated
   - Update any other docs referencing playbook defaults

## References

- **Docs:** `docs/To Do/user-flow.md` - Lines 150-167 (Default Game Plan and Playbooks Settings)
- **Backend Code:** `BackEnd/api/gameplan_routes.py` - `initialize_playbook_settings()` (lines 206-400) ✅ **Implemented**
- **Frontend Code:** `FrontEnd/static/playbooks.js` - `initDefaults()` (lines 63-117) ⚠️ **Needs Update**
- **Training Fallback:** `BackEnd/models/training_execution_v2.py` - Even distribution fallback (lines 1335-1411)

