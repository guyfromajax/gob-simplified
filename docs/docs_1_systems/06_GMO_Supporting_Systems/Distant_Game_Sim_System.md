
# Distant Gameplay System

## Overview
Efficient simulation for 56-60 distant games per week (all non-user-conference matchups). User's 4-8 conference games run full turn-based sim.

## Architecture

### Win Probability Calculation (implement now)
1. Calculate each team's **combined score**: prestige + int(0.1 * total_player_attrs)
2. Home team gets a +100 bonus added to their combined score
3. Roll `randint(1, combined_total)`- If roll <= home_team_score: home team wins
   - If roll > home_team_score: away team wins

### Margin of Victory (implement now)

**Core concept**: The same roll that determined the winner also determines the margin.
The roll's distance from the threshold (as a percentage of the winning team's total)
drives the margin — the further from the threshold, the larger the blowout.

**Step-by-step:**

1. Calculate the win threshold: `threshold = home_team_score`
2. Calculate the roll's distance from threshold as a percentage:
   - If home team won: `dominance = (threshold - roll) / threshold`
   - If away team won: `dominance = (roll - threshold) / (combined_total - threshold)`
   - Result: `dominance` is always between 0.0 (nail-biter) and 1.0 (maximum blowout)

3. Map dominance to margin using D1 distribution buckets:
   - `0.00 – 0.18` → margin = randint(1, 3)    # ~18% of games, 1-3 point games
   - `0.18 – 0.45` → margin = randint(4, 9)    # ~27% of games, 4-9 point games
   - `0.45 – 0.77` → margin = randint(10, 19)  # ~32% of games, 10-19 point games
   - `0.77 – 1.00` → margin = randint(20, 40)  # ~23% of games, 20+ point games

4. Rating gap modifier — scale the margin upward for mismatched teams:
   - Calculate rating gap: `gap = abs(home_team_score - away_team_score) / combined_total`
   - If `gap > 0.20` (meaningful mismatch): `margin = int(margin * 1.25)`
   - If `gap > 0.35` (large mismatch): `margin = int(margin * 1.50)`
   - If `gap <= 0.20` (closely matched): no modifier

##Final Scores (implement now)

1. Generate total points:
   `total_points = max(78, min(220, normal(mean=138, sd=15)))`

2. Calculate raw scores:
   `winning_score = ceil((total_points + margin) / 2)`
   `losing_score = winning_score - margin`

3. Clamp losing score floor:
```
   if losing_score < 39:
       losing_score = 39
       winning_score = losing_score + margin
```

4. Clamp winning score ceiling:
```
   if winning_score > 121:
       winning_score = 121
       losing_score = winning_score - margin
```

5. If both clamps conflict, margin gives way:
```
   if losing_score < 39:
       losing_score = 39
       margin = winning_score - losing_score
```

6. Assign scores to correct teams:
```
   if home_team_won:
       home_score = winning_score
       away_score = losing_score
   else:
       away_score = winning_score
       home_score = losing_score
```

### Templates
- **Count**: Five hundred pre-baked outcome templates
- **Structure**: Outcome-class specific (blowout win, close win, close loss, blowout loss, etc.)
- **Not matchup-specific**: Templates are generic outcome classes, not pre-tuned for specific team pairings

### Template Selection
1. Determine winner and margin of victory from roll
2. Select corresponding template from the five hundred based on outcome class
3. Apply template to generate box score and player stats

### Calibration
- **Data source**: Statistical baselines from user and user-conference games
- **Metrics to capture**: Means, standard deviations, outcome distributions across:
  - Final scores
  - Individual player stats (FG%, rebounds, assists, turnovers, etc.)
  - Team-level outcomes (bench scoring, bench minutes, etc.)
- **Template design**: Build each of five hundred templates using these distributions to ensure box scores and player stats feel realistic and calibrated to actual gameplay

## Next Steps
- Pull real college basketb


##Brainstorming Code##

# Step 1: Calculate raw scores
total_points = normal(mean=138, sd=15, floor=78, ceiling=220)
winning_score = ceil((total_points + margin) / 2)
losing_score = winning_score - margin

# Step 2: Clamp losing score floor
if losing_score < 39:
    losing_score = 39
    winning_score = losing_score + margin

# Step 3: Clamp winning score ceiling
if winning_score > 121:
    winning_score = 121
    losing_score = winning_score - margin

# Step 4: If both clamps conflict, margin gives way
if losing_score < 39:
    losing_score = 39
    margin = winning_score - losing_score