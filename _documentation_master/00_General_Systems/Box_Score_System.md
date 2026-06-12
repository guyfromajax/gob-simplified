## Box Score System ✅ **COMPLETE** (January 2025; doc synced to code April 2026)

> **Note (2026-06):** Tournament mode and Single Game mode are **sunset**. References to `tournament_id` / tournament flows below describe code paths that still exist but are no longer user-reachable; they'll be removed with the sunset-code purge.

**Base Constants**

1. **Data Sources**:
   - **Roster API** (`GET /roster/{team_identifier}`): Player baseline data (jersey, year, height, weight, attributes, `position_ratings`, merged `attributes`). Path may be **team_id**, Mongo **ObjectId**, or **team name** (`BackEnd/api/api.py`, `get_team_roster`). Query params: optional **`team_id`**, **`franchise_id`**, **`tournament_id`**. The post-game page passes franchise/tournament ids when `mode` is franchise or tournament (`FrontEnd/static/box-score.js`, `mergeFullRosters`).
   - **Per-player game stats** (`GameManager.get_box_score()`): Top-level object keyed by **`team.team_id` if set, else `team.name`**. Each team value is a map of **position keys** (`PG`…`C`, `BENCH`, or `"{pos}_{player_id[:8]}"` when two bench players share a position label) → `{ name, playerId, jersey, ...player.stats["game"] }` for **lineup + full roster** (`BackEnd/models/game_manager.py`).
   - **Saved game / API payload**: Often includes **`box_score`** (by team id and/or legacy name) and **`team_totals`** (team-level aggregates; post-game UI reads these by **display team name** in `renderTeamStats`). Shapes may also live under **`teams[team_id].box_score`**. Finalize / career stat application: `BackEnd/utils/stat_updater.py`, summaries: `BackEnd/utils/game_summary_builder.py`. End-of-game attribute rules may aggregate from box score: `BackEnd/eog_attr_rules.py`.
   - **Franchise post-game (EOG):** After a finished franchise game is finalized, `BackEnd/api/franchise_routes.py` → `update_team_attributes_after_game()` updates FTD **`team_attributes`** from the canonical `eog_inputs` snapshot and persists **`team_attribute_changes`** on the **game** document for the box score’s **+/- team measure** strip. The same pass applies **offensive play CMD** (`plays.*.effectiveness`) decay on FTD from each play’s **share of `game_stats.times_run`** for that game (see `End_Of_Game_System.md`); that decay is **not** shown as a separate column on the box score page—only the team-attribute deltas are.
   - **Distant / simmed franchise games**: `BackEnd/models/distant_game_stats.py` (`_build_team_box_score`, `build_distant_game_summary`) builds `box_score` compatible structures.

2. **Surfaces (where box score data appears)**:
   - **Post-game box score page**: `FrontEnd/static/box-score.html`, `FrontEnd/static/box-score.js` — loads game by `game_id`, merges rosters, renders team + player tables, special-stats popup, franchise attribute deltas when applicable.
   - **Live court (Phaser)**: `FrontEnd/static/js/phaser/gameScene.js` — `hydrateBoxScore()` uses **`start_box_score`** (quarter baseline; empty for brand-new games) to seed sidebar stats, and keeps **`final_box_score`** or **`box_score`** for cumulative/final stats; resolves team side using **`home_team_id` / `away_team_id`** when keys are ids.
   - **Court team tab “S3”**: Not a traditional box score; **team attribute pills** (shooting threshold, efficiencies, chemistry bar, etc.) in `FrontEnd/static/court.html` (`renderTeamAttributePills`).

3. **Display Components**:
   - **Team statistics (post-game)**: From `gameData.team_totals` via `renderTeamStats()` — PTS, FGM/FGA, 3PTM/3PTA, FTM/FTA, REB, AST, STL, BLK, F, TO, DEF_A/DEF_S, plus special rollups (e.g. FB_PTS, PIP, POT) as implemented in `renderTeamStatsTable`.
   - **Player statistics**: Full table + **special stats popup** (Fast Break, Outlet, HCT, FCP, Points off TO, etc.).
   - **Jersey display**: Next to player name and in popup header; `0` is valid.

4. **Data Processing (post-game)**:
   - **`mergeFullRosters`**: Fetches both teams’ rosters, then maps players with stats from `gameData.box_score` using lookup order: **`gameData.box_score[teamId]`** → **canonical name** (uppercase, spaces/hyphens → underscores) → **display `teamName`** (`FrontEnd/static/box-score.js`).
   - **`combinePlayersAndBoxScore()`**: Merges roster rows with box_score rows by **name** / position; copies a fixed set of stat keys from box_score onto `player.stats`; bench-only players get synthetic map keys.
   - Jersey fallback chain on roster objects: `jersey`, `jerseyNumber`, `jersey_number`.

**Box Score System Flow (post-game page)**

1. **Load game** — `game_id` (+ `mode`, `franchise_id`, `tournament_id`, team names/ids as URL params).
2. **Roster fetch** — `GET /roster/{team_identifier}` per team with mode-specific query params.
3. **Merge** — `mergeFullRosters` → `combinePlayersAndBoxScore` for each side.
4. **Render** — `renderTeamStats`, `renderPlayerStatsTable`, interactions → `showSpecialStatsPopup`.

---

### Overview

The Box Score System shows team and player statistics after (or around) a game. Data is produced by the simulation (`GameManager`, `TeamManager.get_team_game_stats`) and persisted on game documents; the post-game UI merges **roster** and **box_score** so all roster players appear with correct jerseys and stats.

**Primary files:** `FrontEnd/static/box-score.html`, `FrontEnd/static/box-score.js`, `BackEnd/models/game_manager.py` (`get_box_score`), `BackEnd/models/team_manager.py` (`get_team_game_stats`).

### Data Sources (detail)

| Source | Role |
|--------|------|
| `GET /roster/{team_identifier}` | Roster + attributes for merge on box-score page |
| `GameManager.get_box_score()` | Runtime per-player stats map for summaries / saves |
| `team_totals` on game doc | Team-level rows on post-game page |
| `box_score` on game doc | Per-player lines; keys often **team_id** in live data |
| `stat_updater.finalize_game` / `apply_stats_from_summary` | Career/season rollups; multiple legacy layouts supported |

### Player Jersey Number Display (historical note)

Jerseys are included on roster API players (`jersey` from loaded player docs) and on each `get_box_score()` row. The post-game UI prefers box_score jersey when present, else roster.

**Key files:** `BackEnd/api/api.py` (`get_team_roster`), `BackEnd/models/game_manager.py` (`get_box_score`), `FrontEnd/static/box-score.js` (`combinePlayersAndBoxScore`, `renderPlayerStatsTable`, popup header).

### Team / Player Statistics (post-game)

- **Team row**: Driven by `team_totals[homeTeamName]` / `[awayTeamName]` in `renderTeamStats` (aligns with how the game document stores totals for display).
- **Player table**: Merged roster + `box_score`; sorting uses `highestRT` then position then jersey (`combinePlayersAndBoxScore` return order).
- **Special popup**: Columns for fast break, outlet, HCT, FCP, points off turnovers, etc. (see `showSpecialStatsPopup` and helpers in `box-score.js`).

### Court Page — Team tab S3 (team measures, not box score)

**Location:** `FrontEnd/static/court.html` — `renderTeamAttributePills`.

**Order (must match code):**

1. Shooting (`shot_threshold`)
2. Rebounding (`rebound_modifier`)
3. Offense Efficiency (`offensive_efficiency`)
4. Defense Efficiency (`defensive_efficiency`)
5. Fast Break Efficiency (`fb_efficiency`)
6. Press/Trap Efficiency (`pt_efficiency`)
7. Discipline (`discipline`)
8. Fight (`fight`)
9. Momentum (`momentum_score`)
10. Team Chemistry (`team_chemistry`, bar scaled 0–25)

**Styles:** `command-center-team-styles.css` + court-local CSS in `court.html`.

### Live court — sidebar stats seeding

**File:** `FrontEnd/static/js/phaser/gameScene.js` — inside scene `create`, `hydrateBoxScore`:

- **`start_box_score`**: Used when continuing a game so the table matches **start-of-quarter** totals (skipped for `isNewGame`).
- **`final_box_score` or `box_score`**: Stored as **`this.finalBoxScore`** for end-state / consumers.
- Player stat fields synced include PTS, REB, AST, F, STL, BLK, TO, DEF_A, DEF_S, DEF_PCT display string, etc., keyed by `playerId` via `nameToId`.

### Key Files (reference)

| Area | Files |
|------|--------|
| Post-game UI | `FrontEnd/static/box-score.html`, `FrontEnd/static/box-score.js` |
| Live court stats | `FrontEnd/static/js/phaser/gameScene.js` |
| Court S3 pills | `FrontEnd/static/court.html` |
| Roster HTTP | `BackEnd/api/api.py` |
| Runtime box / teams | `BackEnd/models/game_manager.py`, `BackEnd/models/team_manager.py` |
| Persist / finalize | `BackEnd/utils/stat_updater.py`, `BackEnd/utils/game_summary_builder.py` |
| Distant game box | `BackEnd/models/distant_game_stats.py` |
| EOG aggregation | `BackEnd/eog_attr_rules.py` |
| Client finalize payload | `FrontEnd/static/js/phaser/finalizeGame.js` (sends `game_document` including `box_score` when present) |

**Note:** `BackEnd/main.py` defines `build_box_score_from_player_stats`; it is **not referenced elsewhere** in the repo (legacy / utility only).
