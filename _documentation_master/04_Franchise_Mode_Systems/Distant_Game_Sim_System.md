
# Distant Gameplay System

> **Status (Phase 6 — 2026-07-04).** Full v2 combined score + **ranked full-sim promotion** (`natl_rank ≤ 15` both teams). Integration tests in `tests/test_distant_sim_integration.py`. Constants: `BackEnd/constants/distant_sim.py`. Engine: `BackEnd/distant_sim_engine.py`. Tuning plan: [`Distant_Sim_Tuning.md`](../projects/Distant_Sim_Tuning.md).

## Overview
Efficient simulation for 56-60 distant games per week (all non-user-conference matchups). User's 4-8 conference games run full turn-based sim.

### Exception — next opponent (regular season, complete week)

When **`complete_week`** simulates CPU games (`_complete_week_finish_cpu_and_persist` in `BackEnd/api/franchise_routes.py`), a matchup that would normally be **distant** (neither team in the user’s conference) still uses the **full step-by-step** sim (`run_simulation` + persisted game doc + `finalize_game`) if **either team is the user’s scheduled opponent in the next regular-season week** (week **N+1**, weeks **1–26** only). The upcoming opponent’s **conference does not matter** for this rule.

Resolution of “who is the user’s next-week opponent” is **`_user_next_regular_season_opponent_id`**, which reads **`franchise_doc["schedule"][week]`** for **`current_week + 1`**. EOS / tournament weeks are unchanged by this override.

### Exception — ranked promotion (Phase 5, regular season)

When a matchup would otherwise be **distant** (neither team in the user’s conference), it still uses **full CPU sim** if **both** teams have FTD **`natl_rank ≤ DISTANT_RANKED_FULLSIM_MAX_RANK`** (**15** by default). This gives elite non-user-conference matchups turn-based sim parity with the user’s conference (~2–4 extra full sims/week). Disable by setting the constant to **0**.

Check: `distant_sim_should_promote_ranked_fullsim()` in `BackEnd/distant_sim_engine.py`; wired in `_complete_week_finish_cpu_and_persist` before the distant branch.

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

### Win Probability Calculation

1. Calculate each team's **base score**: `prestige + int(DISTANT_TALENT_ATTR_MULT × talent_signal)` (**0.20**).
   - **`talent_signal`** (Phase 3, distant-only — not written to FTD for ranking):
     - **Option A:** sum live FPD core attrs for active roster (`ftd.players`) at sim time.
     - **Option B (fallback):** frozen `total_player_attrs` + team-attribute composite (`offensive_efficiency + defensive_efficiency − int(shot_threshold / 20)` when present).
2. **Record momentum:** add `DISTANT_MO_MULT × (team_wins − team_losses)` plus streak bonus/penalty.
   - **`team_wins` / `team_losses`:** franchise **regular-season** W/L only (weeks **1–26**).
   - **`DISTANT_MO_MULT`** from FTD **`team_attributes.team_chemistry`** (clamp **7–25**). Bands: **&lt; 11 → 8**, **&lt; 16 → 10**, **&lt; 21 → 12**, **&lt; 25 → 16**, **= 25 → 22**.
   - **Streak bonus (Phase 4):** if `distant_win_streak ≥ 3`: **`+DISTANT_STREAK_BONUS × (streak − 2)`**; if `distant_loss_streak ≥ 3`: **`−DISTANT_STREAK_PENALTY × (streak − 2)`**.
3. **Season momentum:** add **`momentum_score × DISTANT_MO_SCORE_WEIGHT`** (**28**).
   - Clamped **−10..+10**. Reset to **0** at season init.
   - After each distant game: winner **`+1.5 × chemistry_scale`** (+ streak bonus); loser **`−0.8 × chemistry_scale`** (+ **−2.0** if loss ends win streak ≥ 3).
   - Streak counters: `distant_win_streak`, `distant_loss_streak` on FTD `team_attributes`.
4. **Tier amplification (Phase 4):** after week **≥ 5**, multiply `(record_momentum + season_momentum)` by tier band from win pct and add the delta.
   - **≥ .750 → 7.0×**, **≥ .650 → 3.25×**, **≥ .550 → 1.0×**, **≥ .450 → 0.45×**, **else → 0.25×**.
5. **Home edge:** add **`2 × home_team_chemistry`** to the **home** team only.
6. Roll **`randint(1, combined_total)`** — home wins if **`roll ≤ home_combined`**.

**Order:** base → record momentum (incl. streak) → season momentum → tier adjustment → home chemistry bonus (home only) → roll.

Implementation: `BackEnd/distant_sim_engine.py`; wired from `franchise_routes.py` `_distant_sim_team_combined()`. Within a **`complete_week`** batch, in-memory FTD and RS standings caches update after each distant game so later same-week sims see current `momentum_score` and W/L.

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

The player-stat distribution layer (box scores down to individual players) is documented separately in `Distant_Game_Sim_Player_Stats.md` (built in `BackEnd/models/distant_game_stats.py`).

## Integration & Validation (Phase 6)

| Check | Coverage |
|---|---|
| Momentum persist on FTD | `compute_distant_momentum_score_updates` after each distant game; within-week in-memory FTD cache via `distant_sim_apply_result_to_standings_cache` |
| Distant game doc shape | `simulation_engine="distant"`, full box scores, `quarter=5`, `is_final=True` (`build_distant_game_summary`) |
| Ranking integrity | v2 freezes `total_player_attrs` on FTD; live FPD talent signal is distant-sim-only (never written back) |
| Ranked promotion | `distant_sim_should_promote_ranked_fullsim` before distant branch in `complete_week` |
| Tests | `tests/test_distant_sim.py` (29) + `tests/test_distant_sim_integration.py` (6) |
| Calibration | `scripts/distant_sim_monte_carlo.py` — distant engine: ~2.9 teams/season at 22+ wins (10k seasons, seed 42) |

**Manual playtest (open):** See [`Distant_Sim_Tuning.md` § Phase 6 playtest checklist](../projects/Distant_Sim_Tuning.md) — spot-check national standings weeks 10/18/26, FTD momentum after distant games, ranked promotion for top-15 matchups.
