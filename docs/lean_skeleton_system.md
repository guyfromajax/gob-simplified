# Lean Skeleton System

## Overview

The Lean Skeleton System adds dynamic play variety to half-court offense by selecting from 4 different skeleton variants based on offensive vs defensive matchup quality.

**Goal:** Provide tactical variety between possessions while keeping backend processing costs low and payload sizes manageable.

---

## System Components

### 1. Skeleton Variants

Each play in MongoDB now has 4 skeleton variants:

```javascript
{
  "name": "Motion - Inside Focus",
  "play_type": "motion",
  "play_focus": "inside",
  "skeletons": {
    "successful": {...},      // Lean >= 1: Play executes perfectly
    "mid_play_change": {...}, // Lean 0-0.99: Play adjusts mid-execution  
    "contested": {...},       // Lean -0.01 to -1: Defense engaged
    "broken": {...}           // Lean < -1: Defense disrupts
  }
}
```

**Current Status:** 
- ✅ All 7 plays migrated to new structure
- ✅ Each play has `successful` skeleton (former "standard")
- ⏳ Empty placeholders for `mid_play_change`, `contested`, `broken`

### 2. Lean Score Calculation

**Function:** `generate_logic()` in `BackEnd/engine/phase_resolution.py`

**Location:** Line 565-601

**Current Implementation:** Placeholder returning random lean score (-2 to 2)

**TODO:** Implement real logic based on:
- Offensive play type/focus vs defensive setup
- Team attributes (speed, execution, discipline)
- Player attributes (relevant to play requirements)
- Game situation (score differential, time remaining, quarter)

**Example Logic to Implement:**
```python
def generate_logic(off_call, def_call, off_team, def_team, off_lineup, def_lineup):
    score = 0
    
    # 1. Evaluate offensive execution capability
    if off_call == "Motion - Inside Focus":
        # Check C's post-up ability
        c_player = off_lineup.get("C")
        score += (c_player.attributes["PO"] - 50) / 25  # -2 to +2 range
        
        # Check SG's passing ability
        sg_player = off_lineup.get("SG")
        score += (sg_player.attributes["IQ"] - 50) / 50  # -1 to +1 range
        
        # Check team execution
        score += (off_team.attributes["execution"] - 50) / 50
    
    # 2. Evaluate defensive disruption
    if def_call == "Man Defense":
        # Check defensive C's post defense
        def_c = def_lineup.get("C")
        score -= (def_c.attributes["PD"] - 50) / 25
    
    # 3. Apply modifiers based on game situation
    # (e.g., trailing teams might force plays = lower score)
    
    return max(-2, min(2, score))  # Clamp to -2 to 2 range
```

### 3. Skeleton Selection

**Function:** `get_skeleton_by_lean()` in `BackEnd/engine/phase_resolution.py`

**Location:** Line 1048-1082

**Mapping:**
```python
if lean_score >= 1:      → "successful"
elif lean_score >= 0:     → "mid_play_change"
elif lean_score >= -1:    → "contested"
else:                     → "broken"
```

**Fallback:** If selected variant is empty/missing, falls back to "successful"

### 4. Integration Flow

```
resolve_half_court_offense_logic()
  ↓
1. generate_logic() → returns lean_score
  ↓
2. get_hco_skeleton(lean_score=lean_score)
  ↓
3. get_skeleton_by_lean() → selects variant
  ↓
4. Returns selected skeleton
  ↓
5. Animation system renders skeleton
```

---

## Cost Analysis

**AWS Budget:** $0.125 per user per month (5% of $2.50/month after 50% margin on $5 subscription)

**Per-Possession Cost:**
- Current system: $0.0000015 per possession
- User plays 36,000 possessions/month
- **Total cost: $0.054/user/month** ✅ Well under budget!

**Why This is Scalable:**
- ONE lean calculation per possession (not per step)
- Skeleton selection is simple dictionary lookup
- No complex branching during animation
- Small payload (1 skeleton sent to frontend)

---

## Migration Summary

### Database Changes ✅
- Renamed "standard" → "successful" for all 7 plays
- Added empty placeholders for 3 new variants
- Migration script: `scripts/migrate_play_skeletons.py`

### Backend Changes ✅
- Added `generate_logic()` function (placeholder)
- Added `get_skeleton_by_lean()` function  
- Updated `get_hco_skeleton()` to accept lean_score
- Updated `_get_skeleton_from_team_plays()` to use lean_score
- Updated `Play.get_skeleton()` default to "successful"
- Updated all "standard" references to "successful"

### Frontend Changes ✅
- Updated Play Builder to create all 4 skeleton variants
- New plays will have empty placeholders for variants 2-4

---

## Next Steps

### Phase 1: Content Creation (Current Priority)
1. **Populate skeleton variants** for each play
   - Start with high-frequency plays (motion plays)
   - Create distinct animations for each variant
   - Test that each skeleton has proper steps/events

2. **Skeleton Design Guidelines:**
   - **Successful:** Play executes as designed, ideal outcome
   - **Mid-play change:** Ball handler recognizes opportunity and adjusts (e.g., PG drives instead of passing)
   - **Contested:** Defense is bodied up, passes are tighter, shots are contested
   - **Broken:** Defense disrupts timing, offense forced to improvise or reset

### Phase 2: Logic Implementation
1. **Implement `generate_logic()` function**
   - Map play types to relevant offensive attributes
   - Map defensive setups to countering attributes
   - Balance scoring to distribute evenly across -2 to 2 range
   - Test with various team/lineup combinations

2. **Validation:**
   - Track lean score distribution (should be roughly bell curve)
   - Verify stronger teams trend toward positive lean
   - Verify weaker teams/bad matchups trend negative

### Phase 3: Tuning & Expansion
1. **Balance skeleton frequency**
   - Monitor which skeletons appear most often
   - Adjust lean thresholds if needed
   - Ensure all variants get meaningful usage

2. **Add game situation factors**
   - Score differential (trailing = more risky = potential lean penalty)
   - Time remaining (end of game = more pressure)
   - Player fatigue/energy

3. **Expand to more plays**
   - Attack plays
   - Outside plays
   - Set plays

---

## Testing

### Manual Test
```bash
# Start game and observe console output
python BackEnd/run.py

# Look for these log lines:
[generate_logic] Lean score: 1.23
playcall: Motion - Inside Focus, lean_score: 1.23
```

### Verify Skeleton Selection
- Lean >= 1 should use "successful" skeleton
- Lean 0-0.99 should fall back to "successful" (until mid_play_change is populated)
- Once variants populated, should see different animations

---

## Budget & Scalability Notes

✅ **Current cost: $0.054 per user per month** (well under $0.125 budget)

**Room for expansion:**
- Could add 1-2 more decision points per possession if needed
- Could make lean calculation more complex (factor in more attributes)
- Could track game situation factors dynamically

**Do NOT:**
- Add per-step calculations (would blow up cost)
- Send multiple skeletons in payload (increases network cost)
- Re-evaluate lean score during animation (defeats purpose of skeleton system)

---

## Files Modified

- `BackEnd/engine/phase_resolution.py` - Added lean logic and skeleton selection
- `BackEnd/models/play_manager.py` - Updated default skeleton to "successful"
- `FrontEnd/static/play-builder.html` - Create all 4 skeleton variants
- `scripts/migrate_play_skeletons.py` - Database migration script (NEW)
- MongoDB plays_collection - All 7 plays updated

---

## Questions or Issues?

Common issues:
- **"Skeleton falls back to successful every time"** → Other variants are empty, populate them with steps
- **"Lean score always random"** → generate_logic() is placeholder, implement real logic
- **"Different plays but same animation"** → Check that play document in DB has populated skeletons

For further discussion, refer back to brainstorming session notes.

