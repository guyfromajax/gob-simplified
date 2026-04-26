# PGPC Phase 0 — Snapshot schema and trigger map

**Purpose:** Single contract between the **finalized game document**, **franchise/session context**, and **`get_qualifying_questions`**. Aligns with `PGPC_Trigger_Condition_Assessment.md` and every `'condition'` key in `BackEnd/utils/press_conference_questions.py` (43 distinct keys as of this doc).

**Companion:** `PCPG_Workplan.md` Phase 0.

---

## 1. Frozen payload rule

When creating a `press_conference_sessions` document, store either:

- **`pgpc_snapshot`**: embedded copy of the exact `game_doc` subtree + `franchise_context` dict used for qualification, **or**
- **`pgpc_snapshot_hash`** + immutable reference to a stored blob,

so late patches to the game record cannot change an in-progress session.

---

## 2. Canonical types (Python `TypedDict` — specification)

**Code:** `BackEnd/models/pgpc_snapshot.py` (types). **Context stub:** `BackEnd/pgpc_context.py` → `build_franchise_context_for_pgpc` (re-exported from `BackEnd.utils.shared` for discoverability next to `summarize_game_state`). Result primitives + OT; §B fields as implementation lands. Names are prescriptive; adjust to match existing `summarize_game_state` keys exactly.

```python
from typing import TypedDict, NotRequired, Any

# --- Game document (finalized user game) ---

class TeamGameSummary(TypedDict, total=False):
    score: int
    box_score: list[dict[str, Any]]  # rows: BOX_SCORE_KEYS
    points_by_quarter: list[int]     # index = quarter - 1; grows for OT
    totals: dict[str, Any]
    attributes: dict[str, Any]      # team chemistry / attrs

class GamePlayerRow(TypedDict, total=False):
    playerId: str
    team: str                        # team_id this player belongs to
    pos: str | None                  # end-of-game lineup slot only — NOT for “starter”
    stats: dict[str, Any]            # game box stats
    attributes: dict[str, Any]       # EM, CH, MO, NG; EM not duplicated in stats

class PGPCTierC(TypedDict, total=False):
    """Persist when sim hooks exist (assessment §C). All optional until implemented."""
    clutch_time_scoring: NotRequired[dict[str, Any]]
    unanswered_run: NotRequired[dict[str, Any]]
    first_blood: NotRequired[dict[str, Any]]
    lead_changes: NotRequired[int]
    game_winner_shot: NotRequired[dict[str, Any]]
    early_foul_trouble: NotRequired[dict[str, Any]]  # e.g. per-player F at end Q2

class GameDocForPGPC(TypedDict, total=False):
    quarter: int
    is_final: bool
    teams: dict[str, TeamGameSummary]  # keys = team_id
    players: list[GamePlayerRow]
    # Product rule: opening five at tip — required for bench vs starter triggers
    opening_lineup: dict[str, list[str]]  # team_id -> exactly 5 playerId
    pgpc_tier_c: NotRequired[PGPCTierC]

# --- Built at session creation (not necessarily stored on game) ---

class FranchiseContextForPGPC(TypedDict, total=False):
    franchise_id: str
    user_id: str
    week: int
    user_team_id: str
    opponent_team_id: str
    # Result primitives (can be derived from game if preferred)
    user_won: bool
    margin_user_minus_opp: int
    overtime: bool
    # History / aggregates (assessment §B)
    winning_streak_after_game: int
    losing_streak_after_game: int
    opponent_natl_rank: NotRequired[int | None]
    opponent_is_conference_leader: NotRequired[bool]
    season_series_vs_opponent: NotRequired[dict[str, int]]  # e.g. {"w": int, "l": int}
    first_game_of_season: NotRequired[bool]
    last_regular_season_game: NotRequired[bool]
    must_win_seeding: NotRequired[bool]
    clinched_conference_seed: NotRequired[bool]
    prestige_new_high: NotRequired[bool]
    prestige_drop_streak: NotRequired[int]
    entered_top_25_first_time: NotRequired[bool]
    fell_out_top_25: NotRequired[bool]
    team_chemistry_band: NotRequired[str]  # or float; match question filters
    above_500_first_time_season: NotRequired[bool]
    fell_below_500: NotRequired[bool]
    # RT join: map player_id -> overall RT for “star” / vs-rating triggers
    player_overall_rt: NotRequired[dict[str, float]]

class PGPCInputBundle(TypedDict):
    game: GameDocForPGPC
    context: FranchiseContextForPGPC
```

**Notes**

- **`opening_lineup`:** Written once at Q1 opening tip via `BackEnd/opening_lineup_snapshot.py` (immutable thereafter; restored from DB on load). Without it, skip `bench_pts`, `bench_outscores_starter`, and any trigger that needs “did not start.”
- **`points_by_quarter`:** Required for `come_from_behind_win` / `blown_loss` (sum indices `0:3` vs final W/L). If missing on legacy games, those triggers fail closed (skip) until backfill.
- **`player_overall_rt`:** Not on `GamePlayerRow`; load from FTD / franchise player data by `playerId` when building `FranchiseContextForPGPC`.

---

## 3. Trigger condition → data source (full bank)

Each row is one **`trigger.condition`** value. **Filters** (e.g. `min_margin`, `overtime`, `specificity`) are evaluated in code alongside the condition; sub-keys are documented only where non-obvious.

| `condition` | Assessment section | Source |
|---------------|-------------------|--------|
| `always` | — | No predicate; always qualifies. |
| `win` | A | `user_won` or `teams[user].score > teams[opp].score`. |
| `loss` | A | Negation of `win`. |
| `come_from_behind_win` | A | `sum(user points_by_quarter[0:3]) < sum(opp [...])` and user won. |
| `blown_loss` | A | `sum(user [...]) > sum(opp [...])` after Q3 and user lost. |
| `bench_pts` | A + opening | Sum `PTS` for user players **not** in `opening_lineup[user_team_id]`; compare to filter thresholds. |
| `bench_outscores_starter` | B + opening | Compare bench vs **opening** starter stats per product rule. |
| `fg_pct_gap` | A | Derived FGM/FGA (team or sum players). |
| `fastbreak_pts_gap` | A | `FB_PTS` (or equivalent) user vs opp. |
| `paint_pts_gap` | A | `PIP` / paint totals. |
| `three_pt_pct` | A | 3PT% user and/or opp vs filter. |
| `team_def_pct` | A | `DEF_S`, `DEF_A` → `100 * DEF_S / max(DEF_A,1)` (confirm formula). |
| `player_def_pct` | A | Same on player row. |
| `player_pts` | A | `players[].stats` + filters. |
| `player_reb` | A | Same. |
| `player_three_pt_made` | A | Same. |
| `player_fouls` | A | Same; foul-out uses filters. |
| `player_ft` | A | FT makes/attempts + filters. |
| `player_em` | A | `players[].attributes.EM` + band filter. |
| `opponent_star_pts` | A + B | Highest `player_overall_rt` on opp roster → that player’s PTS in this game. |
| `player_pts_vs_rating` | B | PTS vs `player_overall_rt` threshold. |
| `player_reb_vs_rating` | B | REB vs RT threshold. |
| `player_pts_rating` | B | Combined PTS + RT rule per filter. |
| `limited_minutes_high_rt` | B (+ opening) | `MIN` from box + RT join; optional “did not start” = not in `opening_lineup`. |
| `winning_streak` | B | `winning_streak_after_game` vs `filters.min_streak`. |
| `losing_streak` | B | `losing_streak_after_game` vs `filters.min_streak`. |
| `first_game_of_season` | B | `FranchiseContextForPGPC`. |
| `last_regular_season_game` | B | Context. |
| `must_win_seeding` | B | Context / standings product. |
| `clinched_conference_seed` | B | Context. |
| `prestige_new_high` | B | Context / FTD. |
| `prestige_drop_streak` | B | Context. |
| `entered_top_25_first_time` | B | Context. |
| `fell_out_top_25` | B | Context. |
| `team_chemistry` | B | Team attrs / chemistry band in context or `teams[user].attributes`. |
| `above_500_first_time_season` | B | Context. |
| `fell_below_500` | B | Context. |
| `clutch_time_scoring` | C | `game.pgpc_tier_c.clutch_time_scoring` (or skip if absent). |
| `unanswered_run` | C | `pgpc_tier_c.unanswered_run`. |
| `first_blood` | C | `pgpc_tier_c.first_blood`. |
| `lead_changes` | C | `pgpc_tier_c.lead_changes`. |
| `game_winner_shot` | C | `pgpc_tier_c.game_winner_shot`. |
| `early_foul_trouble` | C | `pgpc_tier_c.early_foul_trouble`. |

**`win` / `loss` filters commonly seen in the bank**

| Filter | Source |
|--------|--------|
| `min_margin`, `max_margin` | `abs(user_score - opp_score)` |
| `overtime` | `quarter > 4` and/or `len(points_by_quarter) > 4` / `overtime` in context |
| `specificity` | `generic` vs ranked/upset/etc. → extra context flags + opponent rank |

---

## 4. Line-by-line assessment cross-check

| Assessment § | This schema |
|--------------|-------------|
| **§A** Box / quarter / players / derived gaps | `GameDocForPGPC.teams`, `players`, `opening_lineup` where noted. |
| **§B** Franchise / FTD / streaks / seeds | `FranchiseContextForPGPC` + `player_overall_rt`. |
| **§C** Tier C | `pgpc_tier_c` subtree; absent → questions with those conditions do not qualify. |
| **§D** Tier 1 vs 2 alignment | Implement in qualification: if `requires_tracking` and Tier C field missing → False. |
| **§F** Selection | Out of scope here; see work plan Phase 3. |

---

## 5. Implementation checklist

1. Confirm **actual** keys on saved game JSON match `GameDocForPGPC` (rename in TypedDict or add aliases in builder).
2. Add **`opening_lineup`** write path in engine/summarize; default `[]` / omit → bench triggers skipped.
3. Implement **`build_franchise_context_for_pgpc(game, franchise, …) -> FranchiseContextForPGPC`** as single place for §B.
4. Add unit tests: one fixture per **§A** mechanic + one Tier C–gated “missing blob → not qualified.”

---

## 6. Change log

- **Initial:** Phase 0 snapshot + 43-condition map tied to assessment A/B/C.
