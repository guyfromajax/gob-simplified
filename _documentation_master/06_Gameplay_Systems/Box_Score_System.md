# Box Score System

> **Note (2026-06):** Tournament mode and Single Game mode are **sunset**. Tournament/single-game code paths mentioned below still exist but are no longer user-reachable; they'll be removed with the sunset-code purge. Everything else in this doc describes Franchise mode behavior.

A "box score" in GOB is the per-player stat lines plus team totals for a single game. This doc covers how box scores are **produced** (three different paths depending on game type), how they're **persisted** on game documents, when they're consumed in the **End of Game (EOG)** process, and where they're **displayed**.

---

## 1. The Stat Model

- Each in-engine player carries `player.stats["game"]` — a flat dict keyed by the stat names in `BOX_SCORE_KEYS` (`BackEnd/constants.py`): PTS, FGM/FGA, 3PTM/3PTA, FTM/FTA, REB (OREB/DREB), AST, STL, BLK, TO, F, MIN, DEF_A/DEF_S, plus special stats (fast break, outlet, HCT, FCP, points off turnovers, etc.).
- **MIN is tracked in seconds** during a game; it is converted to whole minutes (integer division by 60) only when rolled into season/career totals.
- Team totals come from `TeamManager.get_team_game_stats()` (`BackEnd/models/team_manager.py`) — a sum across the roster, exposed as `GameManager.team_totals` keyed by team **name**.
- `GameManager.get_box_score()` (`BackEnd/models/game_manager.py`) snapshots the full roster: lineup players keyed by position (`PG`…`C`), bench players keyed by their position attribute or `BENCH` (collisions get a `{pos}_{player_id[:8]}` suffix). Each row is `{ name, playerId, jersey, ...player.stats["game"] }`. The outer map is keyed by **`team.team_id`** (name only as fallback).

## 2. Three Production Paths

### A. User games (turn-by-turn play and user-triggered "Sim Quarter" / "Sim Full Game")

The real simulation engine (`GameManager`) runs and stats accumulate on the in-memory player objects per turn.

- **Live per-turn persistence:** after each macro turn, `GameManager.simulate_macro_turn` calls `stat_updater.update_game_stats()` which `$inc`s each player's deltas into the game doc's `players.$.stats` and `$set`s the score. This keeps the saved doc roughly current mid-quarter (timeout/resume safety) but is *not* the canonical box score.
- **Quarter saves (canonical):** `main.simulate_quarter` → `api.py` `simulate_quarter_endpoint` saves the game doc each quarter via `summarize_game_state(gm, exclude_animations=True)` (`BackEnd/utils/shared.py`). That summary embeds the full box score under **`teams[team_id].box_score`** (from `get_box_score()`) and team totals under **`teams[team_id].totals`**, sets `quarter`, `is_final` (quarter > 4 and score not tied), `home_team_id`/`away_team_id`, and `simulation_engine` = `"turn_by_turn"` or `"full_quarter_sim"`.
- **`start_box_score`:** at the top of every `simulate_quarter` call (`BackEnd/main.py`), `gm.game_state["start_box_score"] = gm.get_box_score()` snapshots start-of-quarter totals. It's returned in the API response (not persisted) so the live court sidebar can seed from quarter-start values when resuming.
- "Sim Quarter"/"Sim Full Game" from the court use this exact path — same engine, same saves — just without user playcalls.

### B. Full CPU sims (engine-simmed CPU vs CPU games)

During franchise week completion, CPU games that matter get the real engine: any game involving a **user-conference team**, the **user's next opponent** (scouting), and all **EOS bracket games**.

- `_run_franchise_cpu_full_simulation_core` (`BackEnd/api/franchise_routes.py`) calls `run_simulation(home, away)` — a complete engine game with **no DB writes during the sim** (safe for the `ThreadPoolExecutor` that runs these in parallel) — then builds the summary with the same `summarize_game_state()`.
- The caller assigns a generated `_id`, stamps `franchise_id` and `week`, upserts into `games`, then finalizes (Section 4). The box score is byte-for-byte the same shape as a user game's.
- If an engine sim throws, the fallback is a random score with **no box score** (standings row only).

### C. Distant sims (statistical box score generation)

Regular-season games where **neither team is in the user's conference** (and neither is the user's next opponent) skip the engine entirely:

1. `_run_distant_game_sim` produces only a **final score** from combined team ratings.
2. `build_distant_game_summary` (`BackEnd/models/distant_game_stats.py`) fabricates a statistically plausible box score from that score:
   - Team shooting lines are derived from points (`calculate_team_shooting_targets`), rebounds computed and reconciled across both teams, steals/turnovers/blocks/assists rolled from constants, fouls clamped against minutes.
   - Team stats are distributed to players (`_generate_team_player_stats`) weighted by ratings, with starter positions and per-player minutes; `_build_team_box_score` emits rows in the standard shape (starters keyed `PG`…`C`, bench keyed `BENCH_n`).
3. The returned dict is a complete game document: `simulation_engine: "distant"`, `quarter: 5`, `is_final`, `home_team_id`/`away_team_id`, the unified `teams[team_id]` object (with `box_score`, `totals`, `attributes`, fabricated `points_by_quarter`), plus top-level `box_score` and `team_totals`. `_persist_distant_franchise_game` upserts it into `games` and finalizes it like any other game.

Distant box scores contain **no scouting data** (no FB/press-trap rates, no play `game_stats`) — this changes how EOG team-attribute rules treat them (Section 4).

## 3. Where Box Data Lives on a Game Document

| Field | Notes |
|---|---|
| `teams[team_id].box_score` | **Canonical.** Position-keyed player rows; written by `summarize_game_state` (engine games) and `build_distant_game_summary` (distant). |
| `teams[team_id].totals` | Team totals for that side. |
| `box_score` (top level, keyed by team_id) | Always present on distant docs; readers (`finalize_game`, `GET /api/game/{id}`) check top level first and **fall back to building it from `teams[*].box_score`**. |
| `players[]` | Flat array with `stats` per player; kept current per turn via `update_game_stats`. Used for live energy/foul state, not the post-game display. |
| `team_totals` (top level, keyed by team name) | Read by the post-game page's team-stats table. |
| `eog_inputs` | Frozen EOG snapshot (totals + scouting per side) written at team-attribute time — see Section 4. |
| `team_attribute_changes` | Per-team attribute deltas written at EOG; consumed by the box score page's +/- team measure strip. |
| Legacy `home_team` / `away_team` objects | Older shape with nested `box_score`; still read as a last-resort fallback by `finalize_game` and `apply_stats_from_summary`. |

## 4. EOG Sequence — When the Box Score Gets Consumed

The franchise EOG flow for the user's game (driven by `FrontEnd/static/js/phaser/finalizeGame.js`):

1. **Final save** — the Q4/OT `simulate-quarter` call saves the game doc with `is_final: true` and the complete `teams[*].box_score`, and returns the doc as `final_game_document`.
2. **Phase A** — `finalizeGame.js` POSTs `/franchise/complete-week/phase-a` with the week, result row, and `game_document` (passing the doc eliminates a race with the Q4 save). The backend:
   - persists the user's result row into `franchises.results.{week}`;
   - calls **`stat_updater.finalize_game(game_id, mode="franchise", franchise_id=...)`** — the season/career rollup (Section 5);
   - records a coaching-archetype change for the community-highlights feed if the user's lead archetype moved;
   - calls **`_finalize_team_attributes_for_game`** → `update_team_attributes_after_game`, which builds the **`eog_inputs`** snapshot via `build_eog_inputs_from_game_doc` (`BackEnd/eog_attr_rules.py`) — canonical totals + scouting per side, with explicit source-fallback order (`teams[*].scouting` → `team_stats` → nested box score totals) — persists it on the game doc, computes team-attribute deltas from it, applies them to FTD, applies offensive-play CMD (`effectiveness`) decay from each play's share of `game_stats.times_run`, and `$set`s **`team_attribute_changes`** on the game doc for the box score page. (Frozen for late-postseason weeks via `_postseason_eog_team_attrs_disabled_for_week` — empty changes are written.)
3. **Phase B** — after the Post-Game Press Conference, `/franchise/complete-week/phase-b` runs the rest of the week's slate: full CPU sims (path B) and distant sims (path C), each one **upserted + finalized + team-attrs immediately**, then week-level wrap-up in `_finalize_franchise_week_after_cpu_games` (standings, national ranks, recruiting leans, training-squad gains, weekly news) and the week advance.
   - `/franchise/complete-week/start-cpu-sims` can run the CPU slate **early** (when the user starts their game); phase B then just merges the user row and finalizes the week.

Notes on the other paths and modes:

- **Distant games and team attributes:** `update_team_attributes_after_game` detects `simulation_engine == "distant"` and replaces the scouting-driven efficiency rules (offensive/defensive/FB/press-trap efficiencies and opponent modifiers) with small random rolls, since distant box scores carry no scouting data. Score/rebound-driven changes still use the fabricated totals.
- **Scrimmages:** the game doc (with box score) is saved normally, but `finalize_game(mode="scrimmage")` is an explicit no-op — no season/career aggregation.
- **`/franchise/save-result`** is an alternate endpoint (tournament-pattern) that performs the same steps as phase A's user-game handling — result row, box_score verification, `finalize_game`, archetype check, team attributes. The current frontend flow uses phase A.

## 5. Season/Career Rollup — `stat_updater.finalize_game` (franchise branch)

`BackEnd/utils/stat_updater.py`:

- **Idempotency:** claims the game by atomically adding it to `franchises.applied_games`; a game already claimed is skipped, so the multiple finalize call-sites (phase A, complete-week fallback, save-result) can't double-count.
- **Source:** the game doc's `box_score` (top level, else built from `teams[*].box_score`, else legacy `home_team`/`away_team`). The `players[]` array is deliberately **not** used — it only reliably holds the final lineup.
- **Processing:** every player row in the box score gets all stat fields `$inc`'d into both `season.*` and `career.*` (non-stat fields like `name`/`jersey`/`pos` skipped; `MIN` seconds → minutes), plus `GP + 1`, and `meta.team_id` set to the team's ObjectId string.
- **Destination:** `franchise_players_data` (FPD), one doc per `(franchise_id, player_id)`. Missing FPD docs are created on the fly from the universal `players` doc with zeroed stats.
- `apply_stats_from_summary` is an older equivalent that writes to the universal `players` collection; it survives only on a legacy `franchise_manager.py` path.

## 6. Display Surfaces

### Post-game box score page (`FrontEnd/static/box-score.html` / `box-score.js`)

- Loaded with `game_id` (+ `mode`, `franchise_id`, team names/ids) as URL params; works identically for user, CPU-full, and distant games since all three persist the same shape.
- **`mergeFullRosters`** fetches both rosters from `GET /roster/{team_identifier}` (passing `franchise_id` when mode is franchise), then maps stats from `gameData.box_score` — lookup order: `box_score[teamId]` → canonical name (uppercased, spaces/hyphens → underscores) → display team name.
- **`combinePlayersAndBoxScore`** merges roster rows with box-score rows by name/position so every roster player appears (zero lines for DNPs); copies a fixed stat-key set onto `player.stats`; jersey preference is box-score value, else roster (`jersey`/`jerseyNumber`/`jersey_number`).
- Team table renders from `team_totals` by display team name (`renderTeamStats`); player rows sort by highest RT, then position, then jersey; the special-stats popup shows FB/outlet/HCT/FCP/points-off-TO columns.
- Franchise games show the **team attribute +/- strip** from `team_attribute_changes` on the game doc (CMD decay is applied at EOG but not displayed here).

### Live court sidebar (`FrontEnd/static/js/phaser/gameScene.js`)

- `hydrateBoxScore()` seeds sidebar stats from **`start_box_score`** when continuing a game (skipped for brand-new games) and keeps `final_box_score` / `box_score` as `this.finalBoxScore` for end-state consumers. Team side resolves via `home_team_id`/`away_team_id` when keys are ids.
- The court Team tab "S3" pills (`renderTeamAttributePills` in `court.html`) show team *attributes*, not box-score stats — documented here only to disambiguate.

### Game fetch API (`GET /api/game/{game_id}`, `BackEnd/api/api.py`)

Returns `box_score` (top level, built from `teams[*].box_score` if needed), per-team objects with `box_score`/`totals`, `team_attribute_changes`, and scoreboard metadata — used when the box score page or court loads a saved game.

## 7. Path Differences at a Glance

| | User game (A) | Full CPU sim (B) | Distant sim (C) |
|---|---|---|---|
| Engine | Real (`GameManager`), turn by turn | Real (`run_simulation`), whole game | None — score-only sim |
| Box score source | Accumulated per turn | Accumulated per sim | Fabricated from final score |
| Saved when | Every quarter (+ per-turn `$inc`s) | Once, at week completion | Once, at week completion |
| `simulation_engine` | `turn_by_turn` / `full_quarter_sim` | *absent* (only the simulate-quarter endpoint sets it) | `distant` |
| Scouting / play `game_stats` | Yes | Yes | No (empty) |
| EOG efficiency attr rules | Scouting-driven | Scouting-driven | Random rolls |
| FPD season/career rollup | Yes (`finalize_game`) | Yes | Yes |

## 8. Key Files

| Area | Files |
|---|---|
| Runtime stats / box snapshot | `BackEnd/models/game_manager.py` (`get_box_score`), `BackEnd/models/team_manager.py` (`get_team_game_stats`) |
| Persistence shape | `BackEnd/utils/shared.py` (`summarize_game_state`) |
| Per-turn live writes | `BackEnd/utils/stat_updater.py` (`update_game_stats`) |
| Season/career rollup | `BackEnd/utils/stat_updater.py` (`finalize_game`) |
| Distant generation | `BackEnd/models/distant_game_stats.py` |
| EOG orchestration | `BackEnd/api/franchise_routes.py` (phase A/B, `_persist_distant_franchise_game`, `_finalize_team_attributes_for_game`, `update_team_attributes_after_game`) |
| EOG snapshot rules | `BackEnd/eog_attr_rules.py` (`build_eog_inputs_from_game_doc`) |
| Client EOG trigger | `FrontEnd/static/js/phaser/finalizeGame.js` |
| Post-game UI | `FrontEnd/static/box-score.html`, `FrontEnd/static/box-score.js` |
| Live court stats | `FrontEnd/static/js/phaser/gameScene.js` |
| Quarter sim / `start_box_score` | `BackEnd/main.py`, `BackEnd/api/api.py` (`simulate_quarter_endpoint`, `GET /api/game/{game_id}`) |

**Related docs:** `05_GP_Supporting_Systems/End_Of_Game_System.md` (team-attribute and CMD rules in depth), `00_Data_Systems/Games_Collection.md` (full game-doc schema and lifecycle).
