
# Distant Gameplay System

## Overview
Efficient simulation for 56-60 distant games per week (all non-user-conference matchups). User's 4-8 conference games run full turn-based sim.

### Exception — next opponent (regular season, complete week)

When **`complete_week`** simulates CPU games (`_complete_week_finish_cpu_and_persist` in `BackEnd/api/franchise_routes.py`), a matchup that would normally be **distant** (neither team in the user’s conference) still uses the **full step-by-step** sim (`run_simulation` + persisted game doc + `finalize_game`) if **either team is the user’s scheduled opponent in the next regular-season week** (week **N+1**, weeks **1–26** only). The upcoming opponent’s **conference does not matter** for this rule.

Resolution of “who is the user’s next-week opponent” is **`_user_next_regular_season_opponent_id`**, which reads **`franchise_doc["schedule"][week]`** for **`current_week + 1`**. EOS / tournament weeks are unchanged by this override.

## EOG Team Attributes

- Distant-simmed franchise games now persist full game documents with:
  - final scores
  - player box scores
  - team totals
- This allows the normal end-of-game team-attribute system to run for distant games as well.
- Totals-driven EOG attributes (box score / team totals paths) still use the same rules as other franchise games where applicable.
- Install-style team attrs (`offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `fb_opp_modifier`, `pt_efficiency`, `pt_opp_modifier`) do not have reliable full-sim usage inputs in distant sim, so for distant games only each of the six is set to `random.randint(-2, 1)`.
- The game doc is marked with `simulation_engine="distant"` so EOG can branch explicitly without affecting TBT behavior.

## Architecture

### Win Probability Calculation (implement now)
1. Calculate each team's **base score**: `prestige + int(0.1 * total_player_attrs)` (same inputs as standings / FTD).
2. **Momentum:** add `mo_multiplier × team_wins` to that team's score for this roll.
   - **`team_wins`:** franchise **regular-season wins only** (weeks **1–26** in `franchise.results`), same aggregation as **`calculate_franchise_standings`** used for **`GET /franchise/standings`** (standings.html). Postseason / EOS weeks in `results` do not change this win count.
   - **`team_chemistry`** for the multiplier comes from FTD **`team_attributes.team_chemistry`**. Clamp to **7–25** for band lookup: values **&lt; 7** are treated as **7** for bands; **&gt; 25** as **25** (same effect as explicit floor/ceiling multipliers: low → 1×, top band → 6×).
   - Bands on clamped chemistry: **&lt; 11 → 1**, **&lt; 16 → 2**, **&lt; 21 → 3**, **&lt; 25 → 4**, **= 25 → 6**.
3. **Home edge:** add **`2 × home_team_chemistry`** (raw FTD value; same field as today) to the **home** team's score only.
4. Roll **`randint(1, combined_total)`** where **`combined_total = home_team_score + away_team_score`**. If **`roll ≤ home_team_score`**: home wins; else away wins.

**Order:** base → momentum (both teams) → home chemistry bonus (home only) → roll.

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

## Final Scores (implement now)

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


**Ignore everything below this line, these are working notes**

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
