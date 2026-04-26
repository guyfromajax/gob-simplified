# Post-Game Press Conference: Trigger Condition Assessment

This document maps trigger conditions in `BackEnd/utils/press_conference_questions.py` to **what data exists today** in persisted game/franchise state vs **what needs new simulation instrumentation**.

**Canonical game payload (franchise user game):** finalized documents produced from `summarize_game_state` (`BackEnd/utils/shared.py`) and stored on the game record. Relevant fields:

- `teams[team_id].box_score` — per-player rows with `BOX_SCORE_KEYS` stats (`BackEnd/constants/__init__.py`: FGA/FGM, 3PT, FT, REB, PTS, PIP, FB_PTS, DEF_A, DEF_S, MIN, F, etc.).
- `teams[team_id].points_by_quarter` — list whose **indices are quarter − 1** at scoring time; the list **grows** for OT (`add_points` uses `quarter_index = quarter - 1`). Q1–Q3 are always indices `0, 1, 2`.
- `teams[team_id].score`, `teams[team_id].totals`, `teams[team_id].attributes` (team attrs / chemistry live here, not in each box row).
- `players[]` — one entry per roster player with `playerId`, `team`, `pos` (lineup slot key if currently in lineup, else **`null` for bench**), `stats` (game box stats), and **`attributes.EM` / CH / MO / NG** (EM is **not** duplicated inside `stats`; use `players[].attributes.EM`).
- Top-level `quarter`, and `is_final` (`quarter > 4` and unequal scores) — **overtime games** can be detected from `quarter` / length of `points_by_quarter` / `is_final`, not only from margin.

Tier labels **1** and **2** in the Python question bank mean “no extra tracking” vs “needs tracking”; this doc aligns **engineering reality** with that intent.

**Product rule — “starter”:** For PGPC, **starter means the opening five at the start of the game** (tip / opening possession), not who finished in lineup slots. Any trigger that compares **bench vs starters** or sums **bench points** must use a persisted **opening-lineup snapshot** (see below), not `players[].pos` at final save (that reflects end-of-game lineup only).

---

## A — Satisfied from finalized game document (no new sim counters)

These can be evaluated from the **saved game** (box + `points_by_quarter` + `players[]` + metadata), possibly with simple derived math (FG%, bench PTS, DEF% from DEF_S/DEF_A).

| Condition keys (from question bank) | Notes |
|--------------------------------------|--------|
| **Margins / blowout / close** (`win` / `loss` + `min_margin`, `max_margin`) | Final scores on `teams[*].score`. |
| **Overtime** (`overtime: True` on win/loss) | Use final `quarter > 4` and/or `points_by_quarter` length > 4; align with how `is_final` is defined in `summarize_game_state`. |
| **`come_from_behind_win`** | **Was Tier 2 in prior draft — should be Tier A here.** Let `U = sum(points_by_quarter_user[0:3])`, `O = sum(points_by_quarter_opp[0:3])`. Condition: user **lost at end of Q3** (`U < O`) and **won game**. No play-by-play needed. |
| **`blown_loss`** | Symmetric: `U > O` after Q3, user **lost** game. |
| **Team stat gaps** (`fg_pct_gap`, `fastbreak_pts_gap`, `paint_pts_gap`, `three_pt_pct`) | Derive from team totals and/or summing player rows (FGM/FGA, 3PTM/3PTA, FB_PTS, PIP). |
| **`bench_pts`** (`bench_scoring_high` / `low`) | Sum **PTS** for all players **not** in the **opening five** snapshot for the user team. **Does not** use “`pos is None` at game end” — that misclassifies subs who started vs bench players who entered early. **Depends on opening-lineup persistence** (same hook as section B). |
| **Player volume / fouls / FT%** (`player_pts`, `player_reb`, `player_three_pt_made`, `player_fouls`, `player_ft`, `player_fouls` / foul-out) | From box stats on rows; match rows to `players[]` via `playerId` / name as you already do elsewhere. |
| **`player_em` (confident / frustrated)** | Use **`game.players[].attributes.EM`** on the saved game — **not** a column inside the box_score dict. |
| **`player_def_pct` / `team_def_pct`** | From **DEF_S** and **DEF_A** in box stats; define DEF% = `100 * DEF_S / max(DEF_A,1)` (confirm product formula once). |
| **`opponent_star_pts`** | Opponent’s **PTS** from box; “star” = highest **RT** on that team → RT is **not** on the game summary player blob (see section B). Needs roster/FTD join for RT, then PTS from this game’s box. |

**Correction vs prior doc:** Quarter-boundary **score snapshots already exist** as `points_by_quarter`; do not list `come_from_behind_win` / `blown_loss` as requiring new engine quarter snapshots unless we discover legacy games missing `points_by_quarter` (then **backfill/migration**, not sim hooks).

---

## B — No new sim instrumentation; needs franchise / FTD / season aggregates

These are **not** “box score only” but **do not require new play-by-play**. Implement at PGPC session build time by querying franchise + league data (and possibly scanning `franchise.results`).

| Condition keys | Notes |
|----------------|--------|
| **Win/loss specificity** (`win_top_10`, `win_major_upset`, `win_over_conference_leader`, `repeat_win_vs_opponent`, weak opponent / major upset losses, etc.) | Needs **opponent `natl_rank`** (FTD or standings), **conference leader** flag (standings API / computed table), **season series W–L** vs opponent (scan `franchise.results` for same pairing). Prior doc flags were correct; this is **not** on the single game document. |
| **`winning_streak` / `losing_streak`** | Consecutive W/L from **game history**, not box. |
| **Program / season context** (`prestige_new_high`, `prestige_drop_streak`, `entered_top_25_first_time`, `fell_out_top_25`, `team_chemistry`, `above_500_first_time_season`, `fell_below_500`) | FTD + franchise history snapshots; **chemistry** is team/FTD attrs (also not in player box rows). |
| **Season phase** (`first_game_of_season`, `last_regular_season_game`) | Schedule + `franchise.week` / season structure. |
| **`must_win_seeding` / `clinched_conference_seed`** | Requires **standings / elimination math** product may not expose yet — treat as **product + engine projection**, not box. |
| **All **RT**-gated questions** (`player_pts_vs_rating`, `player_reb_vs_rating`, `player_pts_rating`, `limited_minutes_high_rt`, star thresholds) | Persisted game has **no overall RT** on `players[]`. Join **`franchise_players_data`** (or core `players` + position ratings) by `player_id` for the user franchise. **Data is available without new sim tracking**; the question bank’s `tier: 2` / `requires_tracking: True` on `limited_minutes_high_rt` is about *coaching narrative*, not absence of MIN/RT fields. |
| **`bench_outscores_starter` / `bench_outperformer`** | **Starters = opening five** (product rule). Compare a bench player’s **PTS** (or other stat) vs **individual** opening starters — requires **`opening_lineup_player_ids`** (or per-team map of five `player_id`s) **written once at game start** and stored on the game document (or equivalent). Not derivable from final `players[].pos` alone. |

### Opening-lineup persistence (required for bench / “non-starter” triggers)

- **When:** Persist when the opening lineup is fixed (e.g. at tip-off or when Q1 simulation begins).
- **Shape (suggested):** `opening_lineup: { home_team_id: [pid×5], away_team_id: [pid×5] }` (or nested under `teams[team_id]`).
- **Consumers:** `bench_pts`, `bench_outscores_starter`, and any future copy that refers to “starters” vs “bench.”
- **Scope:** Small **game-state / summarize_game_state** addition — **not** full play-by-play Tier C.

---

## C — Needs new simulation / persistence hooks (true Tier 2)

These need **per-possession or fine-grained counters** not reconstructible from box + quarter totals.

| Condition keys | What to build |
|----------------|---------------|
| **`clutch_time_scoring`** | Points in **last N seconds of Q4** (and maybe OT) per team — needs clock-aware scoring or turn metadata. |
| **`unanswered_run`** | Longest consecutive scoring run without opponent scoring — needs ordering of scoring events. |
| **`first_blood`** | Opening run before opponent scores — needs early-possession sequence. |
| **`lead_changes`** | Count lead changes — needs score differential after each scoring event (or equivalent). |
| **`game_winner_shot`** | Last go-ahead basket / clutch basket attribution — needs play identity on scoring turns. |
| **`early_foul_trouble`** | Fouls **at halftime** — box only has **game** total F; need per-player **F at end of Q2** snapshot or incremental tracking. |

---

## D — Alignment with `press_conference_questions.py`

- Questions marked **`tier: 1`** should map to **section A or B** above. Several **RT**-based entries are tier 1 in the file but depend on **section B joins**, not “box only.”
- Questions marked **`tier: 2` / `requires_tracking: True`** should map to **section C**, **except**:
  - **`come_from_behind_win` / `blown_loss`** — engineering-wise belong in **section A** (update the Python `tier`/`requires_tracking` when you implement selectors).
  - **`limited_minutes_high_rt`** — **section B** (RT + MIN join); narrative “benched star” may also require **did not start** = not in opening five.
  - **`bench_outscores_starter` / `bench_pts`** — **section B** + **opening-lineup snapshot** (required; see above).

---

## E — Suggested implementation priority (engineering)

1. **PGPC context builder** that normalizes one struct: game (A) + franchise week + FTD + prior results (B).
2. **Persist opening five** on the game doc (`summarize_game_state` / init path) so **bench PTS** and **bench vs starter** triggers are correct.
3. **Promote Q3 comeback / blown lead** triggers using `points_by_quarter` (fast win, validates data).
4. **RT joins** from FPD for all star/surprise questions.
5. **Section C counters** in simulation loop, persisted on game doc or parallel `game_flow` object — order: `lead_changes` / `first_blood` (simpler) → `unanswered_run` → `clutch_time` → `game_winner_shot` (needs clear product definition).

---

## F — Selection logic reminder (from question bank header)

Apply max **2** questions per category, weight toward most specific conditions, shuffle answer letters per question. Archetype order must not be predictable.
