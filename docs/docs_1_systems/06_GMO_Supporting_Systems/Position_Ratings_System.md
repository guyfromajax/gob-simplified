# Position Ratings System

## Overview

The Position Ratings System calculates 1–100 ratings for each player at all five basketball positions (PG, SG, SF, PF, C) based on their attributes and height. These ratings determine a player's effectiveness at each position and are used throughout the game for lineup selection, player evaluation, and roster management.

## Calculation Method

Each position rating is calculated using a **weighted sum** of player attributes, where each attribute has a specific weight (0–1) that represents its importance for that position. The result is clamped to a 1–100 integer scale.

### Formula

```
Rating = Clamp(Sum(attribute_value × weight) + height_rating (if applicable))
```

- Attributes are retrieved from `player.attributes` (or top-level fallback)
- Missing attributes default to `0`
- Final result is clamped to 1–100 range

## Height Conversion

Height (in inches) is converted to a 1–100 rating using a linear scale:

- **60 inches** (5'0") = 1
- **84 inches** (7'0") = 100
- Formula: `1 + (height - 60) × (99 / 24)`
- Values below 60 clamp to 1, values above 84 clamp to 100

Height is used as a direct factor in PF and C position calculations.

## Position Weights

### Point Guard (PG)
BH, IQ, PS, (OD, AG), (SH, SC)

- **PS** (Passing): 15% // was 20%
- **BH** (Ball Handling): 30% // was 20%
- **IQ** (Basketball IQ): 25% // was 20%
- **SH** (Shooting): 5% // was 10%
- **OD** (Outside Defense): 10% // was 10%
- **AG** (Agility): 10% // was 10%
- **FT** (Free Throw): 5% // was 5%
- **SC** (Scoring): 0% // was 5%

### Shooting Guard (SG)
SH, OD, (AG, SC), (IQ, PS)

- **SH** (Shooting): 40% // was 20%
- **OD** (Outside Defense): 25% // was 20%
- **AG** (Agility): 10% // was 20%
- **SC** (Scoring): 10%
- **PS** (Passing): 5% // was 10%
- **BH** (Ball Handling): 0% // was 10%
- **FT** (Free Throw): 5% // was 5%
- **IQ** (Basketball IQ): 5% // was 5%

### Small Forward (SF)
(AG, ST), (SC, SH, ID, OD), (RB, IQ)

- **AG** (Agility): 25% // was 20%
- **ST** (Strength): 25% // was 20%
- **SC** (Scoring): 10%
- **SH** (Shooting): 10%
- **ID** (Inside Defense): 10%
- **OD** (Outside Defense): 10%
- **FT** (Free Throw): 5% // was 5%
- **IQ** (Basketball IQ): 5%
- **PS** (Passing): 0% // was 5%
- **RB** (Rebounding): 0%

### Power Forward (PF)
RB, ST, ID, (height, IQ, SC)

- **RB** (Rebounding): 35% // was 25%
- **ST** (Strength): 30% // was 20%
- **IQ** (Basketball IQ): 5% // was 15%
- **SC** (Scoring): 5% // was 10%
- **ID** (Inside Defense): 15% // was 10%
- **height**: 5%
- **FT** (Free Throw): 5% // was 5%
- **PS** (Passing): 0% // was 5%
- **SH** (Shooting): 0% // was 5%

### Center (C)
(SC, ID, height), (ST, RB), IQ

- **SC** (Scoring): 25% // was 20%
- **ID** (Inside Defense): 25% // was 20%
- **height**: 20%
- **ST** (Strength): 10%
- **RB** (Rebounding): 10%
- **PS** (Passing): 0% // was 5%
- **IQ** (Basketball IQ): 5% // was 5%
- **FT** (Free Throw): 5% // was 5%
- **AG** (Agility): 0% // was 5%

## When Position Ratings Are Calculated

Position ratings are recalculated:

1. **During Game Initialization**: All players get fresh ratings based on current attributes
2. **After Training**: Training modifies player attributes, so position ratings are recalculated to reflect changes
3. **On Demand**: Scripts can recalculate ratings for all players in the database when attributes are updated

## Storage

Position ratings are stored in the player document as:

```javascript
{
  "position_ratings": {
    "PG": 75,
    "SG": 82,
    "SF": 68,
    "PF": 45,
    "C": 32
  }
}
```

## Usage

Position ratings are used for:

- **Lineup Selection**: Auto-Set Lineup selects players based on their best position ratings
- **Player Cards**: Display the highest position rating on player cards
- **Roster Views**: Sort and filter players by position effectiveness
- **Game Logic**: Determine player effectiveness at their assigned position

## Implementation

The calculation logic is implemented in `BackEnd/utils/position_ratings.py`:

- `compute_position_ratings(player: dict) -> Dict[str, int]`: Main calculation function
- `_height_to_rating(height: float) -> float`: Height conversion function
- `_clamp(value: float, lower: int = 1, upper: int = 100) -> int`: Result clamping

