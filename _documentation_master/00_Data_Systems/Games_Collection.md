# Games Collection

The `games` collection stores live and completed game documents for all modes. Game docs are written by `summarize_game_state()` (`BackEnd/utils/shared.py`) and created at init by `init_game()` (`BackEnd/api/api.py`).

## Document Structure (current)

**Identification / metadata:**
- `_id` — 24-char hex from `generate_game_id()` (`BackEnd/utils/game_id_utils.py`). **Writes must use the canonical id:** `resolve_game_write_id()` finds an existing doc (string or `ObjectId`) before upserting — blind upsert on a string `_id` when the live doc uses `ObjectId` (or vice versa) creates **two Mongo records for one game**, which historically bypassed `applied_games`-only idempotency and double-rolled FPD season stats. `simulate_quarter_endpoint` (`BackEnd/api/api.py`) already resolves via `resolve_game_write_id`; franchise phase A uses `_persist_franchise_user_game_snapshot` and `purge_game_id_format_duplicates`.
- `game_id` (str) — duplicate identifier for compatibility
- `mode` — `"single"`, `"tournament"`, or `"franchise"`
- `franchise_id` (str) / `tournament_id` (str) — set for those modes only
- `week` (int) — franchise mode only

**Game state:** `quarter`, `is_final`, `clock`, `time_remaining`, `opening_tip_winner`, `computer_timeouts`.

**Teams (single source of truth):**
- `home_team_id` / `away_team_id` — **team_id strings** (e.g. `"XAVIEN"`), not ObjectId strings
- `teams` — dict keyed by the same team_id strings. Per-team entry: `name`, `team_id`, `mascot`, `colors`, `score`, `points_by_quarter`, `team_fouls`, `timeouts`, `attributes`, `box_score`, `totals`, `strategy_settings`, `strategy_calls`, `plays` (with `game_stats`), `scouting`, `playbook_settings`.
- There are **no** separate `home_team` / `away_team` dicts — that duplication was eliminated; all team data lives in `teams`.
- Franchise save-result also stamps legacy result fields `team1_id` / `team2_id` / `team1_score` / `team2_score` onto the doc. Do not query by them for team lookup — use `home_team_id` / `away_team_id`.

**Players:** `players` array (stats + attributes for rendering and stat persistence).

**Not persisted:** `turns` is saved as an empty array (`exclude_animations=True`); `text_log` and `entry_animation` are only included in frontend responses, never in DB saves. This keeps documents small.

## Team Key Rules

- Any game-doc structure keyed by team (e.g. `team_attribute_changes`) must use **team_id strings** so consumers (box score) can match `home_team_id` / `away_team_id`.
- EOG `team_attribute_changes` on the game doc stores **team-measure deltas** for the box score strip only. Offensive play effectiveness (CMD) adjustments after franchise games are written to `franchise_team_data.plays`, not duplicated on the game doc (see `End_Of_Game_System.md`).

## Query Pattern

Find a team's most recent game (e.g. scouting reports):

```python
last_game = db.games.find_one(
    {
        "franchise_id": str(franchise_id),
        "$or": [
            {"home_team_id": team_id_field},  # team_id string like "XAVIEN"
            {"away_team_id": team_id_field},
        ],
    },
    sort=[("_id", -1)],
)
```

Then read plays from `game["teams"][team_id]["plays"]`, filtering `game_stats.times_run > 0`.

An index on `games.franchise_id` is ensured at startup (`db.py`).

## Lifecycle & Cleanup

Principle: only games linked to an active Franchise or Tournament instance are kept.

Implemented behavior:
- **Single game:** deleted via `POST /api/games/delete-completed-single` once the user leaves (only when `is_final` and not linked to a franchise/tournament). Not deleted while the user is viewing the Box Score.
- **Franchise:** duplicate game docs for the same week/matchup are purged when phase A persists the user snapshot (`_persist_franchise_user_game_snapshot`) and during **`/franchise/save-result`** (legacy path). All franchise games cascade-delete when the franchise is deleted or reset (`db.games.delete_many({"franchise_id": str(fid)})`).
- **Tournament:** games cascade-delete with their tournament (`tournament_routes.py`, `admin_routes.py`).

## Related Docs

- `_documentation_master/00_Data_Systems/Database_System.md`
- `_documentation_master/05_GP_Supporting_Systems/End_Of_Game_System.md`
- `_documentation_master/03_Data_Persistence/Data_Persistence_System.md`
