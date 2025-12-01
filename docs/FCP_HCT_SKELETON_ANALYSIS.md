# FCP/HCT Skeleton System Analysis: Timestamp Filtering vs Result-Based Selection

## Current System: Timestamp Filtering

### How It Works:
1. **Result determined FIRST** (before skeleton selection)
   - FCP: Lines 1324-1331 in `phase_resolution.py`
   - HCT: Lines 1929-1936 in `phase_resolution.py`
   - Result types: `D_FOUL`, `O_FOUL`, `HCO`, `SHOT`, `DEAD_BALL_TURNOVER`, `STEAL`

2. **Skeleton filtered by result_type**:
   - `get_fcp_skeleton(result_type)` → filters `FCP_1["steps"]` by `end_timestamp`
   - `get_hct_skeleton(result_type)` → filters `HCT_SCENES[random]` by `end_timestamp`
   - Steps included: `[step for step in skeleton["steps"] if step["timestamp"] <= end_timestamp]`

3. **Animation**: Only filtered steps are animated

### Problems:
- ❌ **Result must be known BEFORE animation** (breaks HCO pattern)
- ❌ **Complex timestamp management** (FCP_SKELETONS_DICT, HCT_SKELETONS_DICT)
- ❌ **Harder to debug** (which steps are included? Why is skeleton skipping?)
- ❌ **Different execution pattern from HCO** (not SS&S)
- ❌ **Root cause of "huge sticking bug"** (skeleton animation skipping)

---

## Proposed System: Result-Based Skeleton Selection (Like HCO)

### How It Would Work:
1. **Calculate "pressure score"** (similar to HCO's lean_score)
   - FCP: `offenseScore` vs `defenseScore` (already calculated, lines 1303-1318)
   - HCT: `offenseScore` vs `defenseScore` (already calculated, lines 1909-1924)

2. **Select skeleton variant based on pressure score**:
   - Similar to HCO's `get_skeleton_by_lean()` (lines 1598-1661)
   - Map pressure score to result type:
     - High offense score → "press_break" skeleton (leads to HCO or SHOT)
     - Low offense score → "steal" skeleton, "turnover" skeleton, "foul" skeleton
   - **OR** create separate skeletons for each result type:
     - `fcp_press_break_hco` skeleton
     - `fcp_press_break_shot` skeleton
     - `fcp_steal` skeleton
     - `fcp_turnover` skeleton
     - `fcp_offensive_foul` skeleton
     - `fcp_defensive_foul` skeleton
     - Same for HCT

3. **Animate FULL skeleton** (all steps, no filtering)

4. **Determine result AFTER animation** (like HCO does)

### Benefits:
- ✅ **Matches HCO pattern** (choose skeleton → animate fully → determine result)
- ✅ **Eliminates timestamp filtering complexity**
- ✅ **Easier to debug** (full skeleton, clear which one is selected)
- ✅ **More SS&S** (consistent execution pattern across turn types)
- ✅ **Fixes skeleton skipping bug** (no filtering = no routing issues)
- ✅ **Result can be determined after animation** (like HCO)

### Considerations:
- ⚠️ **Need to create multiple skeletons** (one per result type)
- ⚠️ **More skeleton data to manage**
- ⚠️ **But**: Similar to HCO's variant system (successful/mid_play_change/contested/broken)

---

## Result Handling Differences (User's Observation)

### HCO Results:
- MAKE (no foul)
- MAKE (foul/AND-1)
- MISS (OREB)
- MISS (DREB → HCO or Fast Break)
- FOUL (shooting)
- FOUL (non-shooting, bonus)
- FOUL (non-shooting, no bonus)
- TURNOVER (dead ball)
- TURNOVER (live ball → Fast Break)
- STEAL (→ HCO or Fast Break)

### FCP/HCT Results:
- **Press Break/Trap Break to HCO** (unique to FCP/HCT)
- **Press Break/Trap Break to SHOT** (unique to FCP/HCT)
- STEAL (→ HCO or Fast Break)
- DEAD_BALL_TURNOVER (→ Side inbound)
- O_FOUL (→ Side inbound, PC)
- D_FOUL (→ Free throw if bonus, else Side inbound)

### Fast Break Results:
- **DEFENSIVE_STOP** (unique to Fast Break)
- MAKE (no foul)
- MAKE (foul/AND-1)
- MISS (OREB)
- MISS (DREB → HCO or Fast Break)
- FOUL
- TURNOVER

### OREB Putback Results:
- PUTBACK_MAKE (→ Inbound or Free throw)
- PUTBACK_MISS (→ Another OREB or DREB)

**Conclusion**: User is correct - result handling is NOT identical across turn types. Each has unique results.

---

## Recommendation: **YES, Switch to Result-Based Skeleton Selection**

### Why This Would Help:

1. **Fixes the "Huge Sticking Bug"**:
   - Current issue: Skeleton animation sometimes skipped (routing problem)
   - Root cause: Result must be determined before animation, causing timing/routing issues
   - Solution: Match HCO pattern (animate first, result after) eliminates routing complexity

2. **More SS&S**:
   - **Stability**: Consistent execution pattern (HCO, FCP, HCT all work the same way)
   - **Scalability**: Easy to add new result types (just add new skeleton)
   - **Simplicity**: No timestamp filtering logic to maintain

3. **Easier Debugging**:
   - Clear which skeleton is selected (like HCO's variant selection)
   - Full skeleton animation (no filtering = no "why is this step missing?" questions)
   - Result determined after animation (matches HCO pattern)

4. **Better Architecture**:
   - Separates concerns: Animation (skeleton selection) vs Result (outcome determination)
   - Matches proven HCO pattern
   - Reduces complexity (no timestamp dictionaries to maintain)

### Implementation Approach:

1. **Create Skeleton Variants for Each Result Type**:
   ```
   FCP Skeletons:
   - fcp_press_break_hco (offense breaks press, transitions to HCO)
   - fcp_press_break_shot (offense breaks press, attempts shot)
   - fcp_steal (defense steals ball)
   - fcp_turnover (offense commits turnover)
   - fcp_offensive_foul (offense commits foul)
   - fcp_defensive_foul (defense commits foul)
   
   HCT Skeletons:
   - hct_trap_break_hco
   - hct_trap_break_shot
   - hct_steal
   - hct_turnover
   - hct_offensive_foul
   - hct_defensive_foul
   ```

2. **Select Skeleton Based on Pressure Score**:
   - Use existing `offenseScore` vs `defenseScore` calculation
   - Map to result type (same logic as current, but select skeleton instead of filtering)
   - Animate full skeleton

3. **Determine Result After Animation**:
   - Move result determination to AFTER skeleton animation
   - Match HCO pattern: `resolve_shot()` happens after skeleton completes

### Migration Path:

1. **Phase 1**: Create new skeleton structure (result-based variants)
2. **Phase 2**: Update `get_fcp_skeleton()` / `get_hct_skeleton()` to select by result type (not filter)
3. **Phase 3**: Move result determination to after animation (match HCO pattern)
4. **Phase 4**: Remove timestamp filtering logic (FCP_SKELETONS_DICT, HCT_SKELETONS_DICT)

---

## Comparison Table

| Aspect | Current (Timestamp Filtering) | Proposed (Result-Based Selection) |
|--------|------------------------------|-----------------------------------|
| **Execution Pattern** | Result → Filter Skeleton → Animate | Select Skeleton → Animate → Result |
| **Matches HCO?** | ❌ No | ✅ Yes |
| **Complexity** | High (timestamp dictionaries) | Low (skeleton selection) |
| **Debugging** | Hard (filtered steps) | Easy (full skeleton) |
| **SS&S** | ❌ Different pattern | ✅ Consistent pattern |
| **Skeleton Data** | 1 skeleton, filtered | Multiple skeletons, one per result |
| **Bug Risk** | High (routing issues) | Low (matches proven pattern) |

---

## Final Answer

**YES, switching to result-based skeleton selection (like HCO) would help significantly.**

**Reasons**:
1. ✅ Fixes the "huge sticking bug" (skeleton skipping)
2. ✅ Matches HCO's proven pattern (SS&S)
3. ✅ Eliminates timestamp filtering complexity
4. ✅ Easier to debug and maintain
5. ✅ Better architecture (separates animation from result)

**Trade-off**: Need to create multiple skeletons (one per result type), but this is similar to HCO's variant system and is a one-time setup cost.

**Recommendation**: Implement this change. It will make FCP/HCT execution match HCO execution, eliminating the routing complexity that's causing the bugs.

