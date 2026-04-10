
**National Rank and Prestige System**
These team traits apply to Franchise mode only.

## Current Aligned Rules
- Applies only to franchises created after deployment and marked with the new franchise rules/version flag.
- Older franchises stay on the legacy system permanently.
- `natl_rank` persists in FTD and is recalculated only during regular season weeks `1-26`.
- `natl_rank` freezes for EOS/tournament weeks and is reused for EOS seeding/display.
- `prestige` updates only during regular season weeks `1-26`.
- Regular season weeks `1-4` use a `2x` prestige-delta multiplier before dampeners/floor/ceiling are applied.
- `sos_avg` persists in FTD during the regular season, defaults to `64`, and freezes during tournament play.
- `total_player_attrs` is calculated at season creation / season rollover and then remains frozen for the rest of that season.
- Weekly rank/prestige updates run inside `complete_week()` after all user and computer games for that week have completed.

# Prestige & National Rankings System

## Overview
Two distinct but related systems:
- **Prestige**: Persistent program equity. Moves weekly during regular season weeks `1-26`. Carries into offseason and recruiting. Never resets.
- **National Rank**: Weekly ordinal snapshot. Calculated after each regular-season week's games and stored in FTD. Frozen for EOS/tournament weeks.

---

## Prestige

### Preseason Prestige
Set manually per team before season starts. Ranges:
- Best teams: 600–700
- Mid teams: 450–599
- Lower end teams: 300–449

### Prestige Bounds
- **Floor: 200** — no team drops below this regardless of losses
- **Ceiling: 800** — no team climbs above this regardless of wins

### Weekly Prestige Delta
After every regular-season game, both teams' prestige updates based on the result.

### Early Season Multiplier
- Weeks `1-4`: multiply both `winner_gain` and `loser_loss` by `2` before applying the floor/ceiling dampeners.
- Week `5` onward: revert to normal `1x` delta behavior.

```python
def calculate_prestige_delta(
    winner_prestige: int,
    loser_prestige: int
) -> tuple:
    """
    Returns (winner_gain, loser_loss) before dampeners applied.
    diff = winner_prestige - loser_prestige
    Positive diff = favorite won. Negative diff = upset.
    """
    diff = winner_prestige - loser_prestige

    if diff > 100:        # Heavy favorite won
        winner_gain = 8
        loser_loss = 6
    elif diff > 50:       # Moderate favorite won
        winner_gain = 9
        loser_loss = 8
    elif diff >= -50:     # Even matchup
        winner_gain = 10
        loser_loss = 10
    elif diff >= -100:    # Moderate upset
        winner_gain = 13
        loser_loss = 12
    else:                 # Major upset (100+ point underdog wins)
        winner_gain = 18
        loser_loss = 15

    # Floor dampener — reduce loss as loser approaches 200
    # Prevents teams from dropping below floor
    if 1 <= week <= 4:
        winner_gain *= 2
        loser_loss *= 2

    floor_proximity = min(1.0, max(0.0, (loser_prestige - 200) / 100))
    loser_loss = round(loser_loss * floor_proximity)

    # Ceiling dampener — reduce gain as winner approaches 800
    # Prevents teams from exceeding ceiling
    ceiling_proximity = min(1.0, max(0.0, (800 - winner_prestige) / 100))
    winner_gain = round(winner_gain * ceiling_proximity)

    return (winner_gain, loser_loss)


def apply_prestige_delta(
    winner: dict,
    loser: dict
) -> tuple:
    """
    Apply prestige delta to both teams after a game.
    Returns (updated_winner_prestige, updated_loser_prestige)
    """
    winner_gain, loser_loss = calculate_prestige_delta(
        winner["prestige"],
        loser["prestige"]
    )

    new_winner_prestige = min(800, winner["prestige"] + winner_gain)
    new_loser_prestige = max(200, loser["prestige"] - loser_loss)

    return (new_winner_prestige, new_loser_prestige)
```

### Prestige Delta Reference Table

| Matchup Type | Diff Range | Winner Gain | Loser Loss |
|---|---|---|---|
| Heavy favorite won | diff > 100 | +8 | -6 |
| Moderate favorite won | diff > 50 | +9 | -8 |
| Even matchup | -50 to +50 | +10 | -10 |
| Moderate upset | -100 to -50 | +13 | -12 |
| Major upset | diff < -100 | +18 | -15 |

**Note**: Floor and ceiling dampeners reduce deltas as teams approach 200 (floor) or 800 (ceiling). Deltas are deterministic — no random variance — so prestige movement is explainable and trustworthy for recruiting purposes.

### Season Validation
- **Best team, 26-0** (starts 677): avg gain ~8/win → +208 → ~800 ✅ hits ceiling naturally
- **Worst team, 0-26** (starts 332): floor dampener kicks in below 300, ends ~241 → clamped to 200 ✅
- **Mid team, 13-13** (starts 500): net ~0 → stays at ~500 ✅

---

## National Rankings

### Overview
Purely ordinal. 128 teams sorted by ranking score descending after each regular-season week's games complete. Recalculated weekly in weeks `1-26`, persisted to FTD as `natl_rank`, then frozen through tournament play.

### Ranking Formula by Phase

```
Preseason:   ranking_score = prestige + (total_attrs * 0.10)

Week 1:      ranking_score = prestige + (total_attrs * 0.04) + (100 * team wins)
Week 2:      ranking_score = prestige + (total_attrs * 0.03) + (100 * team wins)
Week 3:      ranking_score = prestige + (total_attrs * 0.02) + (100 * team wins)
Week 4:      ranking_score = prestige + (total_attrs * 0.01) + (100 * team wins)

Weeks 5–8:  ranking_score = (0.75 * prestige) + (100 * team wins) + ((129 - sos_avg) * 4)
Weeks 9–12:  ranking_score = (0.5 * prestige) + (80 * team wins) + ((129 - sos_avg) * 4)
Weeks 13–26:  ranking_score = (0.25 * prestige) + (60 * team wins) + ((129 - sos_avg) * 4)

```

### Phase Logic

**Preseason**: Uses `prestige + (total_attrs * 0.10)`. Reflects program reputation plus current roster quality.

**Weeks 1–4**: Team attributes phase out linearly. Rankings use the season's frozen `total_player_attrs` value, not a recalculated weekly value.

**Weeks 5–26**: Team attributes fully sunset. SOS replaces them. Rankings now reflect prestige (performance equity) plus schedule strength.

**Weeks 27+ / EOS**: `prestige`, `natl_rank`, and `sos_avg` all freeze. No tournament-week updates for this system.

### SOS (Strength of Schedule)

SOS is based on the opponent's **rank entering the week**:
- Week 1 SOS uses opponents' preseason ranks
- Week 2 SOS uses opponents' week-1 ranks
- Week 3 SOS uses opponents' week-2 ranks
- etc.

Implementation note:
- We do **not** need to persist an `opponent_ranks` array.
- We can derive weekly opponent matchups from franchise results and persist a lightweight SOS accumulator on FTD:
  - `sos_rank_sum`
  - `sos_games_played`
  - `sos_avg`

Formula:
```python
def calculate_sos_avg(sos_rank_sum: float, sos_games_played: int) -> float:
    if sos_games_played <= 0:
        return 64
    return sos_rank_sum / sos_games_played
```

**Key properties:**
- Win or loss — all games count toward SOS
- Average (not cumulative) — stable and comparable across weeks
- Stored on FTD during the regular season
- Only used in ranking formula weeks 5–26
- Inverted in formula: `(129 - sos_avg)` so tougher opponents = higher score
- Weight fixed at 4 (to be tuned after live season data)

### SOS Score Examples
```
Team A: avg opponent rank 20 (very tough schedule)
sos_score = (129 - 20) * 4 = 109 * 4 = 436

Team B: avg opponent rank 90 (weak schedule)
sos_score = (129 - 90) * 4 = 39 * 4 = 156

Difference: 280 points — meaningful but not dominant vs prestige range
```

### Full Ranking Calculation
```python
def calculate_ranking_score(
    team: dict,
    week: int,
    sos_avg: float = 64
) -> float:
    """
    Calculate a team's ranking score for the current week.
    Used to sort all 128 teams into national rank order.

    team: dict with 'prestige' and 'total_player_attrs' fields
    week: current week number (0 = preseason)
    sos_avg: current average of opponents' entering-week ranks
    """
    prestige = team["prestige"]
    total_attrs = team.get("total_player_attrs", 0)

    if week == 0:  # Preseason
        return prestige + (total_attrs * 0.10)
    elif week == 1:
        return prestige + (total_attrs * 0.04) + (100 * team_wins)
    elif week == 2:
        return prestige + (total_attrs * 0.03) + (100 * team_wins)
    elif week == 3:
        return prestige + (total_attrs * 0.02) + (100 * team_wins)
    elif week == 4:
        return prestige + (total_attrs * 0.01) + (100 * team_wins)
    elif 5 <= week <= 8:
        sos_score = (129 - sos_avg) * 4
        return (0.75 * prestige) + (100 * team_wins) + sos_score
    elif 9 <= week <= 12:
        sos_score = (129 - sos_avg) * 4
        return (0.5 * prestige) + (80 * team_wins) + sos_score
    else:  # Weeks 13-26
        sos_score = (129 - sos_avg) * 4
        return (0.25 * prestige) + (60 * team_wins) + sos_score


def generate_national_rankings(
    teams: list,
    week: int,
    previous_rank_by_team: dict
) -> list:
    """
    Generate full 128-team national rankings for a given week.
    Returns list of teams sorted by ranking score descending.

    previous_rank_by_team: dict mapping team_id to last week's natl_rank
    """
    scored = []
    for team in teams:
        team_id = team["team_id"]
        score = calculate_ranking_score(team, week, team.get("sos_avg", 64))
        scored.append({
            "team_id": team_id,
            "team": team["team"],
            "ranking_score": score,
            "prestige": team["prestige"],
            "previous_rank": previous_rank_by_team.get(team_id, 999),
            "random_tiebreak": random.random(),
        })

    if week == 0:
        scored.sort(key=lambda x: (-x["ranking_score"], x["random_tiebreak"]))
    else:
        scored.sort(key=lambda x: (-x["ranking_score"], x["previous_rank"], x["random_tiebreak"]))

    # Assign ordinal rank
    for i, entry in enumerate(scored):
        entry["national_rank"] = i + 1

    return scored
```

---

## Data Storage

### What persists (FTD or team document):
- `prestige` — updated after every regular-season game, carries into offseason
- `natl_rank` — updated after each regular-season week, then frozen through tournament play
- `sos_avg` — updated after each regular-season week, reset each season
- `sos_rank_sum` — internal SOS accumulator, reset each season
- `sos_games_played` — internal SOS accumulator, reset each season
- franchise rules/version flag — determines whether the franchise uses the legacy or v2 system
- weekly idempotency marker — prevents double-applying a week's prestige/rank update

### What does NOT persist:
- `ranking_score` — intermediate calculation only
- random tiebreak values — preseason random ordering is resolved once into stored `natl_rank`

---

## Execution Order (per week)

```
1. All games for the week complete (user + distant)
2. calculate_prestige_delta() for every game → apply_prestige_delta()
3. Add this week's opponent entering-week ranks into each team's SOS accumulators
4. generate_national_rankings() for all 128 teams
5. Store updated `prestige`, `natl_rank`, and `sos_avg` to FTD
6. Mark that week as applied so duplicate `complete_week()` calls cannot apply the update twice
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Prestige persistence | Carries into offseason | Recruiting currency |
| National rank persistence | Stored in FTD, frozen after week 26 | Needed for EOS seeding/display |
| SOS scope | All games, win or loss | Schedule difficulty independent of results |
| SOS activation | Week 5 | Too noisy before enough games played |
| Attribute phase-out | Weeks 1–4 linear | Early season results settle prestige |
| Total attribute refresh | Season creation / rollover only | Simplest, least error-prone |
| Delta variance | Deterministic | Explainable, trustworthy for recruiting |
| Prestige floor/ceiling | 200 / 800 | Prevents runaway drift |
| SOS weight | 4 (fixed) | Tune after live season data |
| Backward compatibility | Versioned per franchise | Old saves remain on legacy logic |

---

## Key Files
- `BackEnd/api/franchise_routes.py` — weekly game completion flow and season rollover
- `BackEnd/models/franchise_manager.py` — new-franchise preseason initialization
- `BackEnd/utils/franchise_rank_prestige.py` — shared rank/prestige utility functions
- `docs/docs_1_systems/06_GMO_Supporting_Systems/Rank_Prestige_System.md` — system doc
