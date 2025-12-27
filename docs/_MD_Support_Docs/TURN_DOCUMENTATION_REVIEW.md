# Turn Documentation Review

**Date:** February 2025  
**Purpose:** Verify `turn_data_structure.md` and `TURN_EXECUTION_STRUCTURE.md` are current with codebase

---

## Summary

**Status:** ❌ **OUTDATED** - Both documents need significant updates

---

## turn_data_structure.md Issues

### ❌ **Missing Fields**

The following fields are present in the code but NOT documented:

1. **`offense_team_id`** (string)
   - **Code Location:** `turn_manager.py:786`
   - **Purpose:** Replaces `possession_team_id` - authoritative team on offense during this turn
   - **Status:** ✅ **Should be added** - This is the new standard field

2. **`current_turn`** (string)
   - **Code Location:** `turn_manager.py:469`
   - **Purpose:** Explicitly identifies turn type (HCO, FCP, HCT, FAST_BREAK, FREE_THROW, OREB, etc.)
   - **Status:** ✅ **Should be added** - Used for routing and debugging

3. **`next_turn`** (string)
   - **Code Location:** `turn_manager.py:132, 133, 266, 474, etc.`
   - **Purpose:** Explicit next turn type (set by `game_manager.determine_next_turn()`)
   - **Status:** ✅ **Should be added** - Used for transition logic

4. **`team_stats`** (object)
   - **Code Location:** `turn_manager.py:635-644`
   - **Purpose:** Current team stats from scouting_data (offense/defense)
   - **Structure:**
     ```json
     {
       "Team Name": {
         "offense": {...},
         "defense": {...}
       }
     }
     ```
   - **Status:** ✅ **Should be added**

5. **`team_totals`** (object)
   - **Code Location:** `turn_manager.py:649-652`
   - **Purpose:** Cumulative team game stats (from all players)
   - **Structure:**
     ```json
     {
       "Team Name": { /* team game stats */ }
     }
     ```
   - **Status:** ✅ **Should be added**

6. **`team_plays`** (object)
   - **Code Location:** `turn_manager.py:655-658`
   - **Purpose:** Play data for tooltips (effectiveness and tracking)
   - **Structure:**
     ```json
     {
       "Team Name": [ /* array of play objects */ ]
     }
     ```
   - **Status:** ✅ **Should be added**

7. **`player_energy`** (object)
   - **Code Location:** `turn_manager.py:740-749`
   - **Purpose:** Energy levels (NG attribute) for all active players (fatigue display)
   - **Structure:**
     ```json
     {
       "PLAYER_UUID": {
         "NG": 1.0,
         "team": "Team Name"
       }
     }
     ```
   - **Status:** ✅ **Should be added**

8. **`offense_tempo_call`** (string)
   - **Code Location:** `turn_manager.py:752`
   - **Purpose:** Actual tempo call made (for strategy bars)
   - **Status:** ✅ **Should be added**

9. **`offense_aggression_call`** (string)
   - **Code Location:** `turn_manager.py:753`
   - **Purpose:** Actual aggression call made (for strategy bars)
   - **Status:** ✅ **Should be added**

10. **`defense_tempo_call`** (string)
    - **Code Location:** `turn_manager.py:754`
    - **Purpose:** Actual tempo call made (for strategy bars)
    - **Status:** ✅ **Should be added**

11. **`defense_aggression_call`** (string)
    - **Code Location:** `turn_manager.py:755`
    - **Purpose:** Actual aggression call made (for strategy bars)
    - **Status:** ✅ **Should be added**

12. **`free_throws_remaining`** (integer, optional)
    - **Code Location:** `shot_manager.py:1028`, `game_manager.py:152, 1834`
    - **Purpose:** Number of free throws remaining after this turn (for turn-by-turn mode)
    - **Status:** ✅ **Should be added** - Used alongside `ftContext`

13. **`debug_turn_start`** (string, optional)
    - **Code Location:** `turn_manager.py:624`
    - **Purpose:** Debug string for turn start (if DEBUG enabled)
    - **Status:** ⚠️ **Optional** - Only for debugging

14. **`debug_turn_result`** (string, optional)
    - **Code Location:** `turn_manager.py:625`
    - **Purpose:** Debug string for turn result (if DEBUG enabled)
    - **Status:** ⚠️ **Optional** - Only for debugging

### ⚠️ **Deprecated/Removed Fields**

1. **`possession_team_id`** (string)
   - **Code Status:** REMOVED (marked for removal, only one instance remains for backward compatibility at line 134)
   - **Documentation Status:** Still documented in `turn_data_structure.md` line 17
   - **Action:** ⚠️ **Should be removed** from documentation - replaced by `offense_team_id`
   - **Note:** Code comment says "TODO: Remove (backwards compatibility)" - so it's being phased out

### ⚠️ **Field Updates Needed**

1. **`next_play_type`** - Document mentions this, which is correct, but should note that `next_turn` is also set (and is the authoritative value)

---

## TURN_EXECUTION_STRUCTURE.md Issues

### ❌ **Major Structural Changes**

#### 1. **FCP/HCT Execution Pattern - OUTDATED**

**Document Says:**
- FCP/HCT uses **filtered skeleton animation** (result-dependent steps)
- Result determined BEFORE skeleton animation
- Uses `get_fcp_skeleton()` / `get_hct_skeleton()` with timestamp filtering

**Code Actually Does:**
- ❌ **FCP/HCT now routes through AnimationRouter (same as HCO)**
- Code comment: "✅ COMMENTED OUT: FCP/HCT now routes through AnimationRouter (same as HCO)"
- Code comment: "FCP/HCT skeletons are different data (press break sequences), but use the same animation system"
- FCP/HCT routes to SHOT_ATTEMPT handler (for MAKE/MISS) or their respective handlers (FOUL, TURNOVER, etc.)
- **No special routing needed** - uses same system as HCO

**Action:** ⚠️ **Section needs complete rewrite** - The document describes an old approach that's been refactored

#### 2. **Free Throw Execution - Needs Update**

**Document Says:**
- Uses `ftContext` (ftIndex, ftTotal, bonusType)
- Batch mode approach

**Code Actually Does:**
- ✅ Also uses `free_throws_remaining` field (turn-by-turn mode)
- Code checks: `if (turnData.free_throws_remaining !== undefined)` - uses turn-by-turn mode
- Falls back to `ftContext` if `free_throws_remaining` not available (batch mode)
- **Both approaches supported**

**Action:** ✅ **Section needs update** - Document should mention both modes

### ✅ **Sections That Are Current**

1. **HCO Execution** - ✅ Current (routes through AnimationRouter, skeleton + result handling)
2. **Free Throw Structure** - ✅ Mostly current (just needs `free_throws_remaining` addition)
3. **BIP/SIP Execution** - ✅ Current
4. **Fast Break Execution** - ✅ Current
5. **OREB Execution** - ✅ Current
6. **Opening Tip** - ✅ Current
7. **Turn Types List** - ✅ Current (all types accounted for)

---

## Recommended Actions

### Priority 1: Critical Updates

1. **Update turn_data_structure.md:**
   - ✅ Remove `possession_team_id` from documentation
   - ✅ Add `offense_team_id` as primary field
   - ✅ Add `current_turn` and `next_turn` fields
   - ✅ Add `team_stats`, `team_totals`, `team_plays` fields
   - ✅ Add `player_energy` field
   - ✅ Add strategy call fields (`offense_tempo_call`, etc.)
   - ✅ Add `free_throws_remaining` field

### Priority 2: Structural Updates

2. **Update TURN_EXECUTION_STRUCTURE.md:**
   - ❌ **Rewrite FCP/HCT section** - Completely outdated (now uses AnimationRouter like HCO)
   - ✅ Update Free Throw section to mention both `free_throws_remaining` and `ftContext` modes

### Priority 3: Optional Updates

3. **Optional field documentation:**
   - Document `debug_turn_start` and `debug_turn_result` (debug-only fields)

---

## Code References

### Backend Fields (turn_manager.py)
- Line 786: `result["offense_team_id"] = self.game.offense_team.team_id`
- Line 469: `result["current_turn"] = state`
- Line 474: `result["next_turn"] = result["next_play_type"]`
- Lines 635-644: `result["team_stats"]`
- Lines 649-652: `result["team_totals"]`
- Lines 655-658: `result["team_plays"]`
- Lines 740-749: `result["player_energy"]`
- Lines 752-755: Strategy call fields

### Frontend FCP/HCT Changes (animateGameTurns.js)
- Line 806: Comment: "✅ COMMENTED OUT: FCP/HCT now routes through AnimationRouter (same as HCO)"
- Line 1190: HCO routes through AnimationRouter
- AnimationRouter.js: FCP/HCT routes to same handlers as HCO

---

## Conclusion

Both documents are **significantly outdated** and need updates to reflect:
1. Field changes (possession_team_id → offense_team_id, new fields added)
2. Structural changes (FCP/HCT execution pattern completely changed)
3. Free throw mode updates (both turn-by-turn and batch modes supported)

