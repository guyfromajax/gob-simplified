# Distant Game Sim — Player Stat Distribution System

> **Status (verified + IMPLEMENTED 2026-06-13).** This is built in `BackEnd/models/distant_game_stats.py` — every function below exists (orchestrated by `build_distant_game_summary()`, called from `_persist_distant_franchise_game()` in `franchise_routes.py`). Constants table verified exact against `computer_game_constants.py`. A few implemented signatures drifted slightly from this spec (noted inline): `identify_starters()` now returns `(set, dict)`; `calculate_team_blocks(constants, opponent_fga)`; `calculate_team_fouls(constants, opponent_fta, minutes)`. The Defensive Adjustment Layer remains unbuilt.

## Overview
This document defines the player stat distribution layer for the Distant Game Sim System.
It sits on top of the `_run_distant_game_sim()` function which handles
winner, margin, and final team scores. This layer takes those final scores and distributes
stats down to individual players in a lightweight, attribute-driven manner.

**Authoritative constants source:** `BackEnd/constants/computer_game_constants.py`
- Use that file as the single source of truth for target team stats.
- Percent constants in that file are stored as whole numbers (`44`, `33`, `68`), not decimals.
- Implementation should normalize those percentage constants to decimals before formula use.

**Governing philosophy**: SS&S — Simple, Stable, Scalable.
- No turn-by-turn logic
- No per-possession rolls
- One distribution pass per stat category per team
- Bulk I/O (fetch all rosters, compute in memory, write once)

---

## Order of Operations (per team, per game)

```
1.  identify_starters()           # Identifies 5 starters via shuffled position ratings
2.  distribute_minutes()          # MUST happen before all stat distributions
                                  # Minutes are the primary variance driver for all stats
                                  # Players with 0 MIN get all stats = 0
3.  simulate_team_points()        # Requires: team_score (from _run_distant_game_sim), minutes
4.  calculate_team_shooting_targets() # Requires: team_points + authoritative constants
5.  calculate_team_rebounds()     # Requires: shooting targets (missed shots)
6.  calculate_team_steals()       # Requires: authoritative constants
7.  calculate_team_blocks()       # Requires: authoritative constants
8.  calculate_team_assists()      # Requires: FGM target
9.  calculate_team_turnovers()    # Requires: opponent steals
10. calculate_team_fouls()        # Requires: opponent FTA
11. reconcile_rebounds()          # Cross-team: clamp to opponent's reboundable misses
12. distribute_all_stats()        # Distribute each stat using minutes-scaled weights + variance
13. build_team_totals_from_players() # Team totals are the cumulative result of player stats
```

---

## Utilities

### identify_starters()
> **Implemented signature:** `identify_starters(players) -> tuple[set, dict]` — returns both the starter id set and a `{position: pid}` map. The pseudocode below shows the original set-only form.
```python
def identify_starters(players: list) -> set:
    """
    Identify 5 starters by assigning each position (PG, SG, SF, PF, C)
    to the player with the highest rating at that position.
    Each player can only be assigned one position.
    Position order is shuffled per game to add lineup variance —
    players with similar ratings at multiple positions will rotate
    into different starting roles across games.
    """
    positions = ["PG", "SG", "SF", "PF", "C"]
    random.shuffle(positions)  # Per-game shuffle for lineup variance
    starters = {}
    assigned_players = set()

    for pos in positions:
        best_player = None
        best_rating = -1
        for player in players:
            pid = player["_id"]
            if pid in assigned_players:
                continue
            rating = player.get("position_ratings", {}).get(pos, 0)
            if rating > best_rating:
                best_rating = rating
                best_player = pid
        if best_player:
            starters[pos] = best_player
            assigned_players.add(best_player)

    return set(starters.values())
```

### distribute_minutes()
```python
def distribute_minutes(players: list, starters: set) -> dict:
    """
    Distribute 160 total minutes (32 min x 5 players on court) across 12 players.
    Starters average 22-28 min, bench averages 5-12 min.
    Variance built in for foul trouble, blowouts, hot/cold nights.
    Players with 0 MIN will have all stats set to 0.

    Minutes are the PRIMARY variance driver for all stats — a player's
    stat opportunity scales directly with their minutes share.
    """
    total_minutes = 160
    minutes = {}

    for player in players:
        pid = player["_id"]
        if pid in starters:
            roll = random.random()
            if roll < 0.10:      # 10%: foul trouble / bad night
                base = random.randint(14, 18)
            elif roll < 0.20:    # 10%: heavy minutes night
                base = random.randint(28, 32)
            else:                # 80%: normal starter
                base = random.randint(22, 27)
        else:
            roll = random.random()
            if roll < 0.10:      # 10%: DNP / barely plays
                base = random.randint(0, 3)
            elif roll < 0.20:    # 10%: breakout / foul trouble coverage
                base = random.randint(14, 20)
            else:                # 80%: normal bench
                base = random.randint(5, 12)
        minutes[pid] = base

    # Normalize to exactly 160
    total = sum(minutes.values()) or 1
    normalized = {
        pid: round((m / total) * total_minutes)
        for pid, m in minutes.items()
    }

    # Fix rounding drift — assign to starter with most minutes
    diff = total_minutes - sum(normalized.values())
    if diff != 0:
        top = max(
            (pid for pid in starters if pid in normalized),
            key=lambda p: normalized[p]
        )
        normalized[top] += diff

    # Clamp max 32 per player
    for pid in normalized:
        normalized[pid] = min(32, normalized[pid])

    # Re-fix total after clamp
    diff = total_minutes - sum(normalized.values())
    if diff != 0:
        top = max(normalized, key=normalized.get)
        normalized[top] += diff

    return normalized
```

### apply_minutes_scaling()
```python
def apply_minutes_scaling(weights: dict, minutes: dict) -> dict:
    """
    Scale all stat weights by each player's minutes share before distribution.
    A player with 0 minutes gets weight 0 — all stats become 0 automatically.
    minutes_share = player_minutes / 32 (max possible minutes)
    """
    return {
        pid: weight * (minutes.get(pid, 0) / 32)
        for pid, weight in weights.items()
    }
```

### get_variance_multiplier()
```python
def get_variance_multiplier() -> float:
    """
    Position-blind variance multiplier applied to all players uniformly.
    Starter/bench distinction is handled upstream by distribute_minutes() —
    minutes are the primary variance driver for stat opportunity.

    This multiplier adds game-to-game stat variance WITHIN a player's
    minutes allocation. A 20-minute player who rolls 1.30 can outscore
    a 30-minute player who rolls 0.70 — this is intentional and realistic.
    """
    return random.uniform(0.70, 1.30)
```

### distribute_stat()
```python
def distribute_stat(
    players: list,
    weights: dict,
    team_total: int,
    minutes: dict
) -> dict:
    """
    Generic distribution function used for all stats.
    1. Scale weights by minutes share (0 minutes = 0 stats automatically)
    2. Proportional base allocation from scaled weights
    3. Position-blind variance roll per player
    4. Renormalize to preserve team total
    5. Fix rounding drift to top contributor
    """
    # Scale weights by minutes before distribution
    scaled_weights = apply_minutes_scaling(weights, minutes)
    total_weight = sum(scaled_weights.values()) or 1

    # Proportional base
    raw = {
        pid: (w / total_weight) * team_total
        for pid, w in scaled_weights.items()
    }

    # Position-blind variance per player
    varied = {
        pid: pts * get_variance_multiplier()
        for pid, pts in raw.items()
    }

    # Renormalize to preserve team total
    varied_total = sum(varied.values()) or 1
    final = {
        pid: round((pts / varied_total) * team_total)
        for pid, pts in varied.items()
    }

    # Fix rounding drift — assign to top contributor
    diff = team_total - sum(final.values())
    if diff != 0:
        top = max(final, key=final.get)
        final[top] += diff

    return final
```

---

## Step 1: Points

### Weight Function
```python
def calculate_player_scoring_weight(player: dict) -> float:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})

    total_pos = sum(pos.values()) or 1
    frontcourt_blend = (pos.get("PF", 0) + pos.get("C", 0)) / total_pos
    backcourt_blend = (pos.get("PG", 0) + pos.get("SG", 0) + pos.get("SF", 0)) / total_pos

    inside_score = attrs.get("SC", 0) * (0.5 + 0.5 * frontcourt_blend)
    outside_score = attrs.get("SH", 0) * (0.5 + 0.5 * backcourt_blend)
    ft_score = attrs.get("FT", 0) * 0.3

    return inside_score + outside_score + ft_score
```

### Distribution
```python
def simulate_team_points(
    players: list,
    team_total: int,
    minutes: dict
) -> dict:
    weights = {p["_id"]: calculate_player_scoring_weight(p) for p in players}
    return distribute_stat(players, weights, team_total, minutes)
```

---

## Step 2: Team Shooting Targets

Derives team shooting targets from the team points total.
All constants pulled from `BackEnd/constants/computer_game_constants.py`.

Implementation should first normalize the constants file into a dict like:

```python
constants = {
    "points": TEAM_POINTS,
    "FGM": TEAM_FGM,
    "FGA": TEAM_FGA,
    "FG_pct": TEAM_FG_PCT / 100,
    "3PTM": TEAM_3PT_MADE,
    "3PTA": TEAM_3PTA,
    "3PT_pct": TEAM_3PT_PCT / 100,
    "FTM": TEAM_FT_MADE,
    "FTA": TEAM_FTA,
    "FT_pct": TEAM_FT_PCT / 100,
    "total_rebounds": TEAM_REB,
    "OREB": TEAM_OREB,
    "DREB": TEAM_DREB,
    "assists": TEAM_AST,
    "steals": TEAM_STL,
    "blocks": TEAM_BLK,
    "fouls": TEAM_FOUL,
    "turnovers": TEAM_TURNOVER,
}
```

```python
def calculate_team_shooting_targets(team_points: int, constants: dict) -> dict:

    # Step 1: FT points
    ft_pct_of_points = constants["FTM"] / constants["points"]  # ~18.6%
    ft_made = round(team_points * ft_pct_of_points * random.uniform(0.85, 1.15))
    ft_made = max(0, ft_made)

    # Step 2: FTA from FTM
    ft_pct = constants["FT_pct"] * random.uniform(0.90, 1.10)  # ~68.4%
    ft_attempts = round(ft_made / ft_pct) if ft_pct > 0 else 0

    # Step 3: FG points
    fg_points = max(0, team_points - ft_made)

    # Step 4: 3PT vs 2PT split
    three_pt_pct_of_fg = (constants["3PTM"] * 3) / (constants["points"] - constants["FTM"])
    three_pt_points = round(fg_points * three_pt_pct_of_fg * random.uniform(0.80, 1.20))
    three_pt_points = max(0, three_pt_points)
    two_pt_points = max(0, fg_points - three_pt_points)

    # Step 5: Makes from points
    three_pt_made = round(three_pt_points / 3)
    two_pt_made = round(two_pt_points / 2)
    fg_made = two_pt_made + three_pt_made

    # Step 6: Attempts from makes
    fg_pct = constants["FG_pct"] * random.uniform(0.92, 1.08)  # ~43.9%
    fg_attempts = round(fg_made / fg_pct) if fg_pct > 0 else 0

    three_pt_pct = constants["3PT_pct"] * random.uniform(0.90, 1.10)  # ~32.5%
    three_pt_attempts = round(three_pt_made / three_pt_pct) if three_pt_pct > 0 else 0

    # Step 7: Missed shots for rebound calculation
    fg_missed = fg_attempts - fg_made
    ft_missed = ft_attempts - ft_made

    # Step 8: Integrity check — implied points should match team_points ± 1
    implied_points = (two_pt_made * 2) + (three_pt_made * 3) + ft_made
    drift = team_points - implied_points
    if abs(drift) > 1:
        ft_made = max(0, ft_made + drift)  # Reconcile via FTM

    return {
        "FGM": fg_made,
        "FGA": fg_attempts,
        "FG_pct": round(fg_made / fg_attempts, 3) if fg_attempts > 0 else 0,
        "3PTM": three_pt_made,
        "3PTA": three_pt_attempts,
        "3PT_pct": round(three_pt_made / three_pt_attempts, 3) if three_pt_attempts > 0 else 0,
        "2PTM": two_pt_made,
        "FTM": ft_made,
        "FTA": ft_attempts,
        "FT_pct": round(ft_made / ft_attempts, 3) if ft_attempts > 0 else 0,
        "fg_missed": max(0, fg_missed),
        "ft_missed": max(0, ft_missed),
        "total_missed": max(0, fg_missed + ft_missed)
    }
```

---

## Step 3: Rebounds

### Team Rebounds
```python
def calculate_team_rebounds(shooting: dict, constants: dict) -> dict:

    # Unreboundable misses:
    # - End of quarter missed shots: ~1-2 per game
    # - First shot of multi-FT sequences: ~3-4 per game
    unrebounded = random.randint(2, 5)
    total_reboundable = max(0, shooting["total_missed"] - unrebounded)

    # OREB/DREB split from constants
    # Actuals: OREB 8.9, DREB 22.4, total 31.2
    oreb_rate = constants["OREB"] / constants["total_rebounds"]
    oreb_rate_varied = oreb_rate * random.uniform(0.85, 1.15)
    oreb_rate_varied = max(0.0, min(1.0, oreb_rate_varied))
    dreb_rate_varied = 1.0 - oreb_rate_varied

    total_rebounds = round(total_reboundable * random.uniform(0.90, 1.10))
    oreb = round(total_rebounds * oreb_rate_varied)
    dreb = total_rebounds - oreb

    return {
        "total_rebounds": total_rebounds,
        "OREB": max(0, oreb),
        "DREB": max(0, dreb),
        "total_reboundable": total_reboundable
    }
```

### Cross-Team Reconciliation
```python
def reconcile_rebounds(team_a: dict, team_b: dict) -> tuple:
    """
    Team A's rebounds bounded by Team B's reboundable misses and vice versa.
    Must be called after both teams' shooting breakdowns are calculated.
    """
    team_a_total = min(team_a["total_rebounds"], team_b["total_reboundable"])
    team_b_total = min(team_b["total_rebounds"], team_a["total_reboundable"])

    team_a_oreb = min(team_a["OREB"], team_a_total)
    team_a_dreb = team_a_total - team_a_oreb

    team_b_oreb = min(team_b["OREB"], team_b_total)
    team_b_dreb = team_b_total - team_b_oreb

    return (
        {"total_rebounds": team_a_total, "OREB": team_a_oreb, "DREB": team_a_dreb},
        {"total_rebounds": team_b_total, "OREB": team_b_oreb, "DREB": team_b_dreb}
    )
```

### Player Rebound Weight
```python
def calculate_player_rebound_weight(player: dict) -> float:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})
    height = player.get("height", 72)

    height_norm = (height - 66) / (84 - 66)  # 0.0 to 1.0

    total_pos = sum(pos.values()) or 1
    frontcourt_blend = (pos.get("PF", 0) + pos.get("C", 0)) / total_pos

    rb_component = attrs.get("RB", 0) * 1.0
    st_component = attrs.get("ST", 0) * 0.4
    height_component = height_norm * 30
    position_multiplier = 0.6 + (0.8 * frontcourt_blend)  # 0.6 to 1.4

    return (rb_component + st_component + height_component) * position_multiplier
```

---

## Step 4: Steals

### Team Steals
```python
def calculate_team_steals(constants: dict) -> int:
    # Actuals: 4.3 steals per team per game
    mean = constants["steals"]
    sd = mean * 0.25
    return round(max(0, random.gauss(mean, sd)))
```

### Player Steal Weight
```python
def calculate_player_steal_weight(player: dict) -> float:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})

    total_pos = sum(pos.values()) or 1
    backcourt_blend = (
        pos.get("PG", 0) + pos.get("SG", 0) + pos.get("SF", 0)
    ) / total_pos

    od_component = attrs.get("OD", 0) * 1.0
    ag_component = attrs.get("AG", 0) * 0.5
    position_multiplier = 0.6 + (0.8 * backcourt_blend)  # 0.6 to 1.4

    return (od_component + ag_component) * position_multiplier
```

---

## Step 5: Blocks

### Team Blocks
> **Implemented signature:** `calculate_team_blocks(constants, opponent_fga)` — the opponent-FGA safety clamp noted below is a real parameter.
```python
def calculate_team_blocks(constants: dict) -> int:
    # Actuals: 1.6 blocks per team per game
    mean = constants["blocks"]
    sd = mean * 0.30  # Blocks are volatile
    return round(max(0, random.gauss(mean, sd)))
```

### Player Block Weight
```python
def calculate_player_block_weight(player: dict) -> float:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})
    height = player.get("height", 72)

    height_norm = (height - 66) / (84 - 66)

    total_pos = sum(pos.values()) or 1
    frontcourt_blend = (pos.get("PF", 0) + pos.get("C", 0)) / total_pos

    id_component = attrs.get("ID", 0) * 1.0
    height_component = height_norm * 40  # Height dominant for blocks
    position_multiplier = 0.4 + (1.2 * frontcourt_blend)  # 0.4 to 1.6

    return (id_component + height_component) * position_multiplier
```

**Game-level safety clamp**: team blocks cannot exceed opponent FGA (never fires in practice but good guardrail).

---

## Step 6: Assists

```python
def calculate_team_assists(shooting: dict, constants: dict) -> int:
    # Actuals: 17.7 assists, assist rate = 17.7/25.5 = 69.4% of FGM
    assist_rate = constants["assists"] / constants["FGM"]
    varied_rate = assist_rate * random.uniform(0.85, 1.15)
    varied_rate = min(varied_rate, 0.95)  # Cap: some buckets always unassisted
    return max(0, round(shooting["FGM"] * varied_rate))
```

### Player Assist Weight
```python
def calculate_player_assist_weight(player: dict) -> float:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})

    total_pos = sum(pos.values()) or 1
    backcourt_blend = (
        pos.get("PG", 0) + pos.get("SG", 0) + pos.get("SF", 0)
    ) / total_pos
    pg_blend = pos.get("PG", 0) / total_pos  # PG gets extra weight

    iq_component = attrs.get("IQ", 0) * 1.0
    ps_component = attrs.get("PS", 0) * 0.8
    bh_component = attrs.get("BH", 0) * 0.5
    # PG gets double boost: backcourt_blend + pg_blend
    position_multiplier = 0.4 + (0.8 * backcourt_blend) + (0.4 * pg_blend)

    return (iq_component + ps_component + bh_component) * position_multiplier
```

---

## Step 7: Turnovers

```python
def calculate_team_turnovers(constants: dict, opponent_steals: int) -> int:
    # Actuals: 9.1 turnovers per team per game
    mean = constants["turnovers"]
    sd = mean * 0.20
    total = round(max(0, random.gauss(mean, sd)))
    # Constraint: turnovers must be >= opponent steals
    return max(total, opponent_steals)
```

### Player Turnover Weight (inverse — higher weight = more turnovers)
```python
def calculate_player_turnover_weight(player: dict) -> float:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})

    total_pos = sum(pos.values()) or 1
    backcourt_blend = (
        pos.get("PG", 0) + pos.get("SG", 0) + pos.get("SF", 0)
    ) / total_pos

    # Inverse: lower BH/IQ = higher turnover weight
    bh_inv = (100 - attrs.get("BH", 50)) * 0.6
    iq_inv = (100 - attrs.get("IQ", 50)) * 0.4
    # Ball handlers get more TOs even if skilled (they have the ball more)
    position_multiplier = 0.5 + (0.8 * backcourt_blend)

    return (bh_inv + iq_inv) * position_multiplier
```

---

## Step 8: Fouls

> **Implemented signature:** `calculate_team_fouls(constants, opponent_fta, minutes)` — also takes the minutes dict.
```python
def calculate_team_fouls(constants: dict, opponent_fta: int) -> int:
    # Actuals: 19.8 fouls per team per game
    mean = constants["fouls"]
    sd = mean * 0.15
    total = round(max(0, random.gauss(mean, sd)))

    # Soft constraint: blend with FTA-implied fouls
    # FTA/fouls ratio from actuals: 18.8/19.8 = 0.95
    fta_implied_fouls = round(opponent_fta / 0.95)
    total = round((total + fta_implied_fouls) / 2)

    return max(0, total)
```

### Player Foul Weight
```python
def calculate_player_foul_weight(player: dict) -> float:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})
    height = player.get("height", 72)

    height_norm = (height - 66) / (84 - 66)

    total_pos = sum(pos.values()) or 1
    frontcourt_blend = (pos.get("PF", 0) + pos.get("C", 0)) / total_pos

    st_component = attrs.get("ST", 0) * 0.5     # Physical players foul more
    height_component = height_norm * 20
    iq_inv = (100 - attrs.get("IQ", 50)) * 0.3  # Lower IQ = more fouls
    position_multiplier = 0.6 + (0.8 * frontcourt_blend)

    return (st_component + height_component + iq_inv) * position_multiplier
```

---

## Cross-Team Constraint Chain (game level)

Execute in this order to ensure internal consistency:

```python
# 1. identify_starters() for both teams
# 2. distribute_minutes() for both teams — must happen first
# 3. Calculate both teams' shooting targets independently
# 4. Calculate both teams' raw rebounds
# 5. reconcile_rebounds(team_a_rebounds, team_b_rebounds)
# 6. Calculate Team A steals (from constants)
# 7. Calculate Team B turnovers — clamp: max(total, team_a_steals)
# 8. Calculate Team B steals (from constants)
# 9. Calculate Team A turnovers — clamp: max(total, team_b_steals)
# 10. Calculate Team A fouls using Team B FTA
# 11. Calculate Team B fouls using Team A FTA
# 12. Distribute all stats to players using minutes-scaled weights + distribute_stat()
#     Note: pass minutes dict into every distribute_stat() call
#     Note: pass player_minutes into every calculate_player_shooting_breakdown() call
# 13. Build final team_totals by summing player stat lines
# 14. Reconcile any final player-level drift so team totals remain internally valid
```

---

## Constants Reference

All constants come from `BackEnd/constants/computer_game_constants.py`.

| Stat | Source Constant | Current Value |
|------|------------------|---------------|
| Points | `TEAM_POINTS` | 69 |
| FGM | `TEAM_FGM` | 25 |
| FGA | `TEAM_FGA` | 58 |
| FG% | `TEAM_FG_PCT` | 44 |
| 3PTM | `TEAM_3PT_MADE` | 5 |
| 3PTA | `TEAM_3PTA` | 16 |
| 3PT% | `TEAM_3PT_PCT` | 33 |
| FTM | `TEAM_FT_MADE` | 13 |
| FTA | `TEAM_FTA` | 19 |
| FT% | `TEAM_FT_PCT` | 68 |
| Total Rebounds | `TEAM_REB` | 31 |
| OREB | `TEAM_OREB` | 9 |
| DREB | `TEAM_DREB` | 22 |
| Assists | `TEAM_AST` | 18 |
| Steals | `TEAM_STL` | 4 |
| Blocks | `TEAM_BLK` | 2 |
| Fouls | `TEAM_FOUL` | 19 |
| Turnovers | `TEAM_TURNOVER` | 9 |

Implementation note:
- `TEAM_FG_PCT`, `TEAM_3PT_PCT`, and `TEAM_FT_PCT` are stored as whole-number percentages.
- Convert them to decimal form before using them in formulas.
- If the constants file changes, this distant sim system should follow it automatically.

---

## Per-Player Shooting Breakdown

After points are distributed to players, derive individual shooting stats
using player-specific percentages based on SC, SH, and FT attributes.

Important:
- Team points are the hard constraint from `_run_distant_game_sim()`.
- Team-level shooting targets are generated from constants after points are known.
- Player shooting is then distributed and reconciled so player points sum exactly to team points.
- Final team totals are built cumulatively from player stats.

### Player Shot Profile
```python
def calculate_player_shot_profile(player: dict) -> dict:
    """
    Derives each player's shot type tendencies from attributes.
    inside_pct: share of scoring from 2PT/inside
    outside_pct: share of scoring from 3PT/perimeter
    ft_pct: share of scoring from free throws
    """
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})

    total_pos = sum(pos.values()) or 1
    frontcourt_blend = (pos.get("PF", 0) + pos.get("C", 0)) / total_pos
    backcourt_blend = (pos.get("PG", 0) + pos.get("SG", 0) + pos.get("SF", 0)) / total_pos

    inside_tendency = attrs.get("SC", 0) * (0.5 + 0.5 * frontcourt_blend)
    outside_tendency = attrs.get("SH", 0) * (0.5 + 0.5 * backcourt_blend)
    ft_tendency = attrs.get("FT", 0) * 0.3

    total_tendency = (inside_tendency + outside_tendency + ft_tendency) or 1

    return {
        "inside_pct": inside_tendency / total_tendency,
        "outside_pct": outside_tendency / total_tendency,
        "ft_pct": ft_tendency / total_tendency
    }
```

### Player-Specific Percentage Functions

**Attribute-to-percentage mappings:**
- SC 0-100 → FG% 0.30-0.65
- SH 0-100 → 3PT% 0.20-0.50
- FT 0-100 → FT% 0.45-0.95

```python
def calculate_player_fg_pct(player: dict, shot_profile: dict) -> float:
    attrs = player.get("attributes", {})

    # SC maps to 2PT efficiency, SH maps to perimeter efficiency
    sc_fg_pct = 0.30 + (attrs.get("SC", 0) / 100) * 0.35  # 0.30 to 0.65
    sh_fg_pct = 0.28 + (attrs.get("SH", 0) / 100) * 0.25  # 0.28 to 0.53

    # Blend based on shot profile
    blended_pct = (
        sc_fg_pct * shot_profile["inside_pct"] +
        sh_fg_pct * shot_profile["outside_pct"]
    )

    varied = blended_pct * random.uniform(0.92, 1.08)
    return max(0.28, min(0.70, varied))


def calculate_player_3pt_pct(player: dict) -> float:
    attrs = player.get("attributes", {})
    base_pct = 0.20 + (attrs.get("SH", 0) / 100) * 0.30  # 0.20 to 0.50
    varied = base_pct * random.uniform(0.88, 1.12)
    return max(0.15, min(0.55, varied))


def calculate_player_ft_pct(player: dict) -> float:
    attrs = player.get("attributes", {})
    base_pct = 0.45 + (attrs.get("FT", 0) / 100) * 0.50  # 0.45 to 0.95
    varied = base_pct * random.uniform(0.93, 1.07)
    return max(0.40, min(0.98, varied))
```

### Per-Player Shooting Breakdown
```python
def calculate_player_shooting_breakdown(
    player: dict,
    player_points: int,
    shot_profile: dict,
    player_minutes: int
) -> dict:
    """
    Derives individual player shooting stats from their point total
    and shot profile. All percentages are player-specific based on
    SC, SH, and FT attributes.

    If player_minutes == 0 or player_points <= 0, returns all zeros.
    Minutes guard is explicit here since this function is called
    per-player outside of distribute_stat().
    """
    if player_points <= 0 or player_minutes == 0:
        return {
            "FGM": 0, "FGA": 0, "FG_pct": 0,
            "3PTM": 0, "3PTA": 0, "3PT_pct": 0,
            "2PTM": 0,
            "FTM": 0, "FTA": 0, "FT_pct": 0
        }

    # Step 1: Split points into FT and FG buckets
    ft_points = round(player_points * shot_profile["ft_pct"])
    fg_points = max(0, player_points - ft_points)

    # Step 2: FTM and FTA
    ft_pct = calculate_player_ft_pct(player)
    ft_made = max(0, ft_points)
    ft_attempts = round(ft_made / ft_pct) if ft_pct > 0 else 0

    # Step 3: Split FG points into 3PT and 2PT
    three_pt_points = round(fg_points * shot_profile["outside_pct"])
    two_pt_points = max(0, fg_points - three_pt_points)

    # Step 4: Makes from points
    three_pt_made = round(three_pt_points / 3)
    two_pt_made = round(two_pt_points / 2)
    fg_made = two_pt_made + three_pt_made

    # Step 5: Attempts from player-specific percentages
    fg_pct = calculate_player_fg_pct(player, shot_profile)
    fg_attempts = round(fg_made / fg_pct) if fg_pct > 0 else 0

    three_pt_pct = calculate_player_3pt_pct(player)
    three_pt_attempts = round(three_pt_made / three_pt_pct) if three_pt_pct > 0 else 0

    # Step 6: Integrity check — implied points should match player_points ± 1
    implied_points = (two_pt_made * 2) + (three_pt_made * 3) + ft_made
    drift = player_points - implied_points
    if abs(drift) > 1:
        ft_made = max(0, ft_made + drift)
        ft_attempts = round(ft_made / ft_pct) if ft_pct > 0 else 0

    return {
        "FGM": fg_made,
        "FGA": fg_attempts,
        "FG_pct": round(fg_made / fg_attempts, 3) if fg_attempts > 0 else 0,
        "3PTM": three_pt_made,
        "3PTA": three_pt_attempts,
        "3PT_pct": round(three_pt_made / three_pt_attempts, 3) if three_pt_attempts > 0 else 0,
        "2PTM": two_pt_made,
        "FTM": ft_made,
        "FTA": ft_attempts,
        "FT_pct": round(ft_made / ft_attempts, 3) if ft_attempts > 0 else 0
    }
```

### Team-Level Reconciliation
After distributing shooting stats to all 12 players, reconcile to match
team totals. Rounding across 12 players will cause drift.

```python
def reconcile_team_shooting(
    player_shooting: dict,
    team_shooting: dict
) -> dict:
    """
    Reconciles player shooting totals to match team shooting totals.
    Drift assigned to top scorer.
    """
    total_fgm = sum(p["FGM"] for p in player_shooting.values())
    fgm_drift = team_shooting["FGM"] - total_fgm

    total_3ptm = sum(p["3PTM"] for p in player_shooting.values())
    three_drift = team_shooting["3PTM"] - total_3ptm

    total_ftm = sum(p["FTM"] for p in player_shooting.values())
    ftm_drift = team_shooting["FTM"] - total_ftm

    if fgm_drift != 0 or three_drift != 0 or ftm_drift != 0:
        top_scorer = max(player_shooting, key=lambda p: player_shooting[p]["FGM"])
        player_shooting[top_scorer]["FGM"] += fgm_drift
        player_shooting[top_scorer]["2PTM"] += (fgm_drift - three_drift)
        player_shooting[top_scorer]["3PTM"] += three_drift
        player_shooting[top_scorer]["FTM"] += ftm_drift

        # Recalculate attempts for top scorer to stay consistent
        top = player_shooting[top_scorer]
        top["FGA"] = max(top["FGM"], top["FGA"])
        top["3PTA"] = max(top["3PTM"], top["3PTA"])
        top["FTA"] = max(top["FTM"], top["FTA"])

    return player_shooting
```

---

## Future Enhancement: Defensive Adjustment Layer

Not implemented in this phase. When added, the defensive adjustment will modify
each player's scoring and stat weights based on the opposing player guarding them.
Design to be determined in a future brainstorm session.

---

## Key Files
- `BackEnd/api/franchise_routes.py` — `_run_distant_game_sim()` (handles scores), `_persist_distant_franchise_game()` (calls `build_distant_game_summary`)
- `BackEnd/models/distant_game_stats.py` — **all functions in this document are implemented here** (orchestrated by `build_distant_game_summary()`)
- `BackEnd/constants/computer_game_constants.py` — Authoritative team-stat constants
- `Distant_Game_Sim_System.md` (same folder) — System doc (scores/winner/margin)
