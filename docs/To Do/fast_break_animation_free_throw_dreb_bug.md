# Fast Break Animation Bug: Free Throw Miss → DREB → Fast Break

## Issue
After a Free Throw turn (away team offense), Miss, DREB, then Fast Break turn (home team offense), both the outlet receiver and Fast Break defender animated in the wrong direction, resolving on spots near the away team basket.

## Scenario
1. Free Throw turn (away team offense)
2. Free Throw Miss
3. DREB (defensive rebound)
4. Fast Break turn (home team offense) - possession flipped
5. Fast Break outlet pass
6. **BUG**: Both outlet receiver and Fast Break defender animated towards wrong basket

## Backend Logs Analysis

**Turn Result:**
```
Turn 15 RESULT: FREE_THROW | Offense: SOUTH_LANCASTER | Next: FAST_BREAK | Defense Setup: None | Possession Flips: True
🔄 [DREB→FB] Flipped possession before Fast Break: South Lancaster → Ocean City, updated offense_team_id=OCEAN_CITY
```

**Fast Break Animation Debug:**
```
is_away_offense: False
offense_team.team_id: OCEAN_CITY
game.away_team.team_id: SOUTH_LANCASTER
ball_handler_outlet_x: 17
ball_handler_outlet_y: 32
```

**Problem Indicators:**
- `ball_handler_outlet_x: 17` - This is in the away team's half (x < 50), but home team (Ocean City) is on offense
- Using fallback coords: `⚠️ Using player.coords (fallback): 17, 32`
- Movement calculation: `17 + 9 = 26` - Moving further towards away basket (lower x values)

## Root Cause Hypothesis

The ball handler's starting position (`x: 17, y: 32`) appears to be on the wrong side of the court. This suggests:

1. **Coordinate System Issue**: After the DREB from free throw miss, the outlet passer's position might not be correctly determined or flipped
2. **Fallback Coordinate Issue**: The system is using `player.coords` fallback, which might be from the previous turn (before possession flip)
3. **Free Throw → DREB → Fast Break Transition**: This specific sequence might not properly handle coordinate transformation after possession flip

## Files to Investigate

- `BackEnd/models/animator.py` - `capture_fast_break_animation()` function
- `BackEnd/engine/phase_resolution.py` - Fast break logic and coordinate determination
- `BackEnd/models/turn_manager.py` - DREB handling and possession flip logic
- Fast break animation coordinate calculation and flipping logic

## Questions to Answer

1. How are outlet passer coordinates determined after a DREB from a free throw miss?
2. Should coordinates be flipped when possession changes from away to home team?
3. Is the `player.coords` fallback using coordinates from before the possession flip?
4. Does the free throw → DREB → Fast Break sequence need special coordinate handling?

## Related Code Sections

- Fast Break animation coordinate calculation
- DREB coordinate determination
- Possession flip coordinate transformation
- Free throw miss → DREB transition

## Priority
Medium - Edge case that affects specific game flow (Free Throw Miss → DREB → Fast Break)

## Status
Open - Needs investigation

