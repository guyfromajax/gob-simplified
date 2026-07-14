# Position Ratings System (**verified 2026-07-14**)

> Verified vs `BackEnd/utils/position_ratings.py` — **every weight table matches exactly**: PG/SG/SF/PF/C (`POSITION_WEIGHTS`), recruit PF/C (`RECRUIT_POSITION_WEIGHTS`, RB/ST/SC/ID 30 + height 10), short-height recruit tables (`RECRUIT_PF_WEIGHTS_SHORT`/`RECRUIT_C_WEIGHTS_SHORT`, RB/ST or SC/ID 35 + height 0), `RECRUIT_SHORT_HEIGHT_THRESHOLD_IN = 71.0`, PF height map (`<72 -> 0`, `72-75 -> 25`, `76+ -> 75`), and C height map (`<76 -> 0`, `76 -> 25`, `77 -> 50`, `78 -> 75`, `79+ -> 100`). Persisted DB field is `position_ratings` (`game_manager.py` `_update_position_ratings` L105). **One correction:** the result is `_clamp(total, lower=1, upper=None)` — floored at 1 with **no hard upper cap** (the ~100 ceiling is implicit because attributes and position height ratings are themselves 0–100), not an explicit 1–100 clamp.

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
- Final result is **floored at 1** (`_clamp(total, lower=1, upper=None)`); there is no explicit upper cap — values stay ≤100 only because every attribute and the height rating are themselves 0–100

## Height Conversion

Height is converted with position-specific helper functions for **PF** and **C**. The old linear helper remains in code for non-PF/C future use, but PF/C rating math uses the tables below.

<!-- - **60 inches** (5'0") = 1
- **84 inches** (7'0") = 100
- Formula: `1 + (height - 60) × (99 / 24)`
- Values below 60 clamp to 1, values above 84 clamp to 100 -->

Height is used as a direct factor in **PF** and **C** position calculations (weights differ for recruits vs roster players; see PF/C sections). For **recruits** under **71 inches**, PF/C use alternate weight tables that move weight off **height** into **RB/ST** (PF) or **SC/ID** (C); the PF/C height conversion still exists, but its weight is `0%` for those short-recruit PF/C rows.

**PF Height Conversion**
If height (in inches) ==:
a. < 72: 0
b. 72 - 75: 25
c. 76+: 75

**C Height Conversion**
If height (in inches) ==:
a. < 76: 0
b. 76: 25, 77: 50, 78: 75
c. 79+: 100

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
RB, ST, ID, (IQ, SC)

- **RB** (Rebounding): 30% (Recruits 30%) (if recruit's height < 71, 35%)
- **ST** (Strength): 25% (Recruits 30%) (if recruit's height < 71, 35%)
- **IQ** (Basketball IQ): 5%
- **SC** (Scoring): 5%
- **ID** (Inside Defense): 15%
- **height**: 10% (Recruits 10%) (if recruit's height < 71, 0%)
- **FT** (Free Throw): 5%
- **PS** (Passing): 0%
- **SH** (Shooting): 5% (Recruits 0%)

### Center (C)
(SC, ID, height), (ST, RB)

- **SC** (Scoring): 15% (Recruits: 30%) (if recruit's height < 71, 35%)
- **ID** (Inside Defense): 15% (Recruits: 30%) (if recruit's height < 71, 35%)
- **height**: 40% (Recruits: 10%) (if recruit's height < 71, 0%)
- **ST** (Strength): 15%
- **RB** (Rebounding): 15%
- **PS** (Passing): 0%
- **IQ** (Basketball IQ): 0%
- **FT** (Free Throw): 0%
- **AG** (Agility): 0%

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

- `compute_position_ratings(player: dict, profile: PositionRatingProfile = "player") -> Dict[str, int]`: Main calculation function; recruit profile applies `RECRUIT_POSITION_WEIGHTS`, and when recruit **height is under 71 inches** replaces **PF** and **C** rows with `RECRUIT_PF_WEIGHTS_SHORT` / `RECRUIT_C_WEIGHTS_SHORT` (via `_position_weights_table`). Calls `_clamp(total, lower=1, upper=None)`.
- `_pf_height_to_rating(height: float) -> float`: PF-specific height conversion (`<72 -> 0`, `72-75 -> 25`, `76+ -> 75`)
- `_c_height_to_rating(height: float) -> float`: C-specific height conversion (`<76 -> 0`, `76 -> 25`, `77 -> 50`, `78 -> 75`, `79+ -> 100`)
- `_height_to_rating(height: float) -> float`: Legacy linear height conversion helper; PF/C do not use it
- `_clamp(value: float, lower: int = 1, upper: int | None = 100) -> int`: Result clamping — but `compute_position_ratings` passes `upper=None`, so ratings are only floored at 1
- `add_position_ratings(player)` writes results under the in-memory key `ratings`; the canonical persisted DB field is `position_ratings` (written by `game_manager._update_position_ratings`).

## Recruit RT display (UI)

On recruiting surfaces, displayed **RT** is the recruit's **best position rating** (max of `PG`–`C`). Colored RT text uses **`getRecruitRtBucketClass`** in `/js/shared/rtBucket.js` with breakpoints **0–29 / 30–39 / 40–49 / 50+** (see `Recruiting_System.md` and Styleguide §Recruit RT Scale). Player roster/lineup RT uses the separate player scale via **`getRtBucketClass`**.
