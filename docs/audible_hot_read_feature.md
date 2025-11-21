# Audible/Hot Read Feature - Implementation Plan

## Feature Description

When the game reaches the step with the shoot action, if there is an instance of an offensive player with no defenders on them, the shooter may "read" this opportunity. If the shooter correctly reads it and determines the teammate who is not guarded is in a clear passing lane (feasible pass, not impossible like lower corner to upper corner), the shooter makes the pass and the unguarded player takes the shot instead.

This feature needs to work in both:
- **Backend Engine**: Simulate the audible decision and modify the play
- **Frontend Animation**: Animate the audible (pass → receive → shot)

## Current System Capabilities

### What We Already Have

1. **Defender Assignment Tracking**: We track `defender_to_offensive_player` per step in `zone_defender_assignments_by_step`, so we can detect unguarded players at any step.

2. **Step-by-Step Processing**: The animator processes steps sequentially, so we can inspect the shot step before resolving it.

3. **Skeleton Modification**: Skeletons are Python dictionaries, so we can modify steps (add pass, change shooter) before animation generation.

4. **IQ-Based Checks**: We already do attribute-based probability checks (e.g., help defense triggers).

## Implementation Challenges

### 1. Timing of Detection

- We need to detect the unguarded player **before** resolving the shot.
- Currently, shot resolution happens in `resolve_shot()` after roles are assigned.
- We'd need to check at the shot step during role assignment or before shot resolution.

### 2. Backend Modification

If conditions are met, we need to modify:
- **Roles**: Change `shooter` to the unguarded player, set original shooter as `passer`
- **Skeleton steps**: Insert a pass step before the shot, update the shot step's shooter
- **Defender assignments**: Recalculate for the new shooter

This is feasible but requires careful sequencing.

### 3. Frontend Animation

- Detect the audible from turn data
- Animate: pass → receive → shot (instead of direct shot)
- The animation system supports this, but we need to signal the audible and handle the modified sequence

## Recommended Implementation Approach

### Phase 1: Detection & Decision (Backend)

**Location**: In `assign_roles()` or before `resolve_shot()`

**Steps**:
1. Check the shot step for unguarded offensive players
2. Run IQ-based read check (probability based on shooter's IQ attribute)
3. Run passing lane feasibility check (criteria to be provided)
4. If all conditions pass, set flag: `roles["audible_detected"] = True` with unguarded player info

**Code Location**: `BackEnd/models/turn_manager.py` or `BackEnd/models/shot_manager.py`

### Phase 2: Skeleton Modification (Backend)

**If audible detected**:
1. Modify the skeleton:
   - Insert a pass step (original shooter → unguarded player)
   - Update the shot step to have the unguarded player shoot
2. Recalculate defender assignments for the new sequence

**Code Location**: `BackEnd/models/turn_manager.py` or `BackEnd/engine/phase_resolution.py`

### Phase 3: Animation (Frontend)

**Steps**:
1. Check for `audible_detected` in turn data
2. Animate the modified sequence (pass → receive → shot)

**Code Location**: `FrontEnd/static/js/phaser/animation/` (likely `turnAnimation.js` or `ballManager.js`)

## Potential Issues & Considerations

### 1. Defender Reassignment

After the pass, defenders may shift. We'd need to recalculate assignments for the new ball handler/shooter.

**Solution**: Re-run `assign_all_zone_defenders()` for the new sequence after skeleton modification.

### 2. Animation Timing

The pass/receive/shot sequence needs proper timing and ball ownership tracking.

**Solution**: Ensure ball ownership is correctly tracked through the pass → receive → shoot sequence.

### 3. Statistics Tracking

Ensure assists, shot attempts, etc. are credited correctly:
- Original shooter gets assist (if pass is made)
- New shooter gets shot attempt
- Original shooter should NOT get shot attempt

**Solution**: Update stat tracking logic to handle audible scenarios.

### 4. Passing Lane Feasibility Criteria

**To be defined by user**, but likely includes:
- Distance between players
- Court position (e.g., not lower corner to upper corner)
- Defensive positioning
- Angle of pass

## Implementation Checklist

### Backend
- [ ] Add function to detect unguarded players at shot step
- [ ] Add IQ-based read check function
- [ ] Add passing lane feasibility check function (criteria TBD)
- [ ] Add audible detection logic before shot resolution
- [ ] Add skeleton modification logic (insert pass step, update shot step)
- [ ] Add defender reassignment after skeleton modification
- [ ] Update roles to reflect new shooter/passer
- [ ] Add `audible_detected` flag to turn result
- [ ] Update stat tracking for audible scenarios

### Frontend
- [ ] Detect `audible_detected` flag in turn data
- [ ] Handle modified animation sequence (pass → receive → shot)
- [ ] Ensure proper ball ownership tracking
- [ ] Test animation timing and transitions

## Files That Will Need Modification

### Backend
- `BackEnd/models/turn_manager.py` - Role assignment and detection
- `BackEnd/models/shot_manager.py` - Shot resolution (may need to check before resolving)
- `BackEnd/utils/shared_defense.py` - Defender assignment recalculation
- `BackEnd/engine/phase_resolution.py` - Skeleton modification

### Frontend
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` - Animation sequence handling
- `FrontEnd/static/js/phaser/animation/ballManager.js` - Ball ownership and pass animation

## Verdict

**Yes, this is feasible and sustainable** with the current architecture. The main work is:
- Adding detection logic before shot resolution
- Modifying the skeleton when an audible is detected
- Recalculating defender assignments for the modified sequence
- Frontend handling the audible animation sequence

The existing step-by-step processing and defender tracking provide the foundation. The main complexity is ensuring defender assignments are recalculated correctly after the pass.

## Next Steps

1. Define passing lane feasibility criteria
2. Implement detection logic
3. Implement skeleton modification
4. Implement frontend animation handling
5. Test with various scenarios (unguarded players in different positions)

