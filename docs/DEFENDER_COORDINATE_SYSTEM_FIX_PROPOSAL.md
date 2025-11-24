# Defender Coordinate System - Proper Fix Proposal

## Current Problem

The current implementation is a **hack** that patches symptoms instead of building a simple, stable, scalable system:

1. **Hacky x_direction logic**: Setting `x_direction = 1` for both cases with comment "becomes LEFT after flip"
2. **Still using `is_away_offense` flag**: Despite plan saying "Direct Calculation: Calculate `x_direction` from coordinates and basket position, not from `is_away_offense` flag"
3. **"Closer to basket" verification failing**: The logic doesn't actually position defenders closer to basket
4. **Not geometric**: The calculation doesn't use actual basket position

## Root Issue

The old function's behavior doesn't match geometric reality:
- **Home offense**: Basket at x=10, BH at x=64 → Defender should be at x < 64 (closer to basket)
  - But old function puts defender at x > 64 (farther from basket)
- **Away offense**: Basket at x=90, BH at x=64 → Defender should be at x > 64 (closer to basket)
  - But old function puts defender at x < 64 (farther from basket)

**The old function was NOT positioning defenders closer to basket!**

## Proper Solution: Pure Geometric Calculation

### Core Principle
**Calculate defender position geometrically from basket and ball handler coordinates. No flags, no special cases.**

### Implementation

```python
def calculate_defender_coords(
    offensive_coords: dict,
    target_basket: dict,
    aggression_level: str,
    spot: str = "key",
    ball_handler_coords: dict = None,
    is_ball_handler: bool = False
    # NO is_away_offense parameter!
) -> dict:
    """
    Calculate defender coordinates using pure geometric calculation.
    
    All coordinates are in HOME orientation (wrapper handles flipping).
    """
    ox = offensive_coords["x"]
    oy = offensive_coords["y"]
    basket_x = target_basket["x"]
    basket_y = target_basket["y"]
    
    if is_ball_handler:
        # BH DEFENDER: Always closer to basket than ball handler
        # Calculate direction vector from offensive player to basket
        dx = basket_x - ox  # Positive = toward basket (right), Negative = away from basket (left)
        dy = basket_y - oy  # Positive = toward basket (down), Negative = away from basket (up)
        
        # Normalize direction (unit vector)
        distance_to_basket = ((dx ** 2) + (dy ** 2)) ** 0.5
        if distance_to_basket == 0:
            # Offensive player is at basket (edge case)
            unit_x = 0
            unit_y = 0
        else:
            unit_x = dx / distance_to_basket
            unit_y = dy / distance_to_basket
        
        # Get spacing based on aggression
        spacing = get_spacing(aggression_level, is_ball_handler=True)
        
        # Calculate defender position: move toward basket by spacing amount
        def_x = ox + (unit_x * spacing)
        def_y = oy + (unit_y * spacing)
        
        # Apply spot-specific adjustments (corners, posts, etc.)
        # ... (edge cases handled here)
        
        # Verify defender is closer to basket (should always pass now!)
        if not verify_defender_closer_to_basket(def_x, def_y, ox, oy, basket_x, basket_y):
            logging.warning(f"⚠️ [CALCULATE_DEFENDER_COORDS] BH defender not closer to basket!")
```

### Benefits

1. **Simple**: Pure geometric calculation, no flags
2. **Stable**: Works the same way regardless of which team is on offense
3. **Scalable**: Easy to extend for new scenarios
4. **Correct**: Actually positions defenders closer to basket
5. **No coordinate flipping in calculation**: Wrapper handles all orientation transformations

### Coordinate Contract

- **Wrapper (`get_defender_coords`)**: Handles all coordinate flipping
  - Input: Coords in any orientation
  - Converts to HOME orientation
  - Calls `calculate_defender_coords` (pure geometric)
  - Converts result back to original orientation
- **Core function (`calculate_defender_coords`)**: Pure geometric calculation
  - Input: All coords in HOME orientation
  - Output: Coords in HOME orientation
  - No knowledge of away/home offense

## Migration Path

1. Remove `is_away_offense` parameter from `calculate_defender_coords`
2. Replace hacky `x_direction` logic with geometric calculation
3. Update wrapper to not pass `is_away_offense` to core function
4. Test that "closer to basket" verification passes
5. Verify behavior matches expected positioning

## Questions to Answer

1. **Why did old function position defenders opposite from basket?**
   - Was it intentional (e.g., "help side" positioning)?
   - Or was it a bug?
   - Should we match old behavior or fix to be geometric?

2. **Do we need to update call sites?**
   - Current call sites pass coords in various orientations
   - Wrapper should handle all of this automatically
   - But we should verify all call sites use wrapper

3. **What about non-BH defenders?**
   - They use different logic (relative to assignment)
   - Should they also be geometric?
   - Or is relative positioning correct for them?

