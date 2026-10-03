# Player Stats view — 2026-09-27

Team › Player Stats is the module view `player-stats-view` on the T1 wide-table template. `?tab=player-stats-tab` opens it. The view formats numbers. It does not compute them.

## What the old tab read

`#player-stats-tab` painted from `userRosterDataCache` (varsity) or the practice-squad list. `renderPlayerStatsTable` in `franchise-command-center.js` divided makes by attempts in the browser and printed `0.0` when the attempt count was 0. That panel is removed. The function no-ops without the old table.

## Endpoint

`GET /franchise/player-stats?franchise_id&team_id` is `@browse_cached` and listed in the client store. One row per varsity player, in roster order (`franchise_team_data.players`). Practice-squad players are not included.

The read is projected: the team document returns `players` only, and each player document returns identity plus the season scalars the table shows. SQLite logs `decoded=False` on `franchise_players_data`. Rates come from `stat_line` through `season_bases` in `t3_detail.py` (the same `_pct` / `_per_game` helpers as player detail). `stat_line`'s own payload is unchanged.

Each row: `player_id`, `name`, `position` (`_roster_position`), `year` (FR/SO/JR/SR), `jersey`, `per_game`, `totals`, `rates` (`fg_pct`, `tp_pct`, `ft_pct`, `def_pct`).

Per-game counting stats are null when GP is 0. GP is the game count in both bases. A rate is null when that attempt count is 0. A real 0% (attempts above 0, makes 0) is 0, and the view prints `0.0`.

## Columns

Grouped, alternating `--group-shade`: Player (portrait or monogram, name, POS · YR) | GP MIN | Scoring PTS FGM FGA FG% | 3PT 3PTM 3PTA 3PT% | Free throws FTM FTA FT% | Rebounding OREB DREB REB | Playmaking AST TO | Defense STL BLK DEF% | F.

Per game is the default. Per-game counting stats use one decimal, including a trailing `.0`. Totals are integers. Percentages do not change with the toggle. Null rates and null per-game values render an em dash. Default sort is PTS descending. There is no navy row: every player is on this team. A row click pushes `player-view` with `origin=team`, `return_tab=player-stats-view`, `pager=player-stats`, and writes `gob-view-player-stats-order`.

## Dropped

- Practice-squad scope. The view is varsity only.
- SCRA and SCR%. Those season fields are not on this table.
- DEFA (defensive attempts). DEF% stays.
- TREB as its own label. The column is the stored `REB`.
- Jersey is in the payload and is not a column. The player cell is portrait, name, and POS · YR.
- The old `TPA` alias. The season key is `3PTA`, the same key `stat_line` reads.

## Width

On the Lancaster save (12 players) and on the fixture, the table fits the card at 1280×720 and at 1920×1080. `.main` horizontal overflow is 0. The card's horizontal overflow is 0, so the scrolled-right shots are the same frame as the unscrolled ones. Narrow rules apply: one header, sticky under `--gob-stick-top`, no `gob-xs`.

The template does support a sticky first column (`.gob-xs th.pin` / `td.pin`). The Player column is marked `pin`, and a Player Stats rule keeps that header cell sticky against the shell rule that sets `.gob-xs thead th` to `position: static`. That path is the wide path. This roster does not take it. Header repeats every 16 body rows are also on the wide path. Twelve rows do not emit one.

## Timing

Offline copy of the save, Lancaster franchise `6ab284847ab3853ae89a1184`, team `69a6fcb68d2c56aa82e48a54`, 12 varsity players. Warm `build_player_stats`: 2.4, 2.3, 2.3, 1.9, 2.1 ms. Minimum 1.9 ms. Under the 150 ms target.

## Tests

- `tests/test_player_stats.py` on mongomock and on `GOB_PERSISTENCE=sqlite`: per-game versus totals (22 points in 2 games → 11 and 15.5 minutes), 0 attempts → null rates, 0-for-4 free throws → `ft_pct` 0, a player with 0 GP → per-game counting stats null, a player not on the varsity list omitted. SQLite asserts the player scan is projected.
- `tests/e2e/player-stats.spec.js`: Team sub-tab and the old tab id, per game / totals, sort, em dash versus `0.0`, row click with the pager and Back restoring scroll, no `.main` horizontal overflow at 1280 and 1920, skeleton, error and Retry. 5 passed.
- Passed with them: subtabs, t1-tables, t2-roster, t3-detail, shell-1b, navigation-history. shell-1's back-restore and old-tab mapping passed.
- shell-1 "sections and sub-tabs open the matching panel" timed out on the Roster tab. The expanded rail covered that tab's click point. The failure is before the Player Stats assertion. shell-1 "settings anchors beside the rail" failed once in the same rerun (settings host still at the collapsed rail edge while the face was expanded).

## Shots

`reports/player-stats-view/`. Pointer parked in `.main`. Real save and fixture, per game and totals, plus the scrolled-right frame, at 1280×720 and 1920×1080.

## Follow-up

The Player cell used `gob-player` without `gob-team`, so the portrait sat above the name and the name kept the browser underline. Rows were about 72px. It now uses the Roster markup (`a.gob-team.gob-player` plus `span.av`): a 28px circular portrait on the left, the name in `--text-100` with POS · YR in `--text-60` beside it, and no underline (Roster does not underline the name on hover either). The identity block is capped at the portrait height, so the row is the Roster row height. On the save copy the row measures 46px at both 1280 and 1920, the portrait is 28px, and the name sits to its right.

`player-stats.spec.js` asserts the Player Stats row is no taller than the Roster row and that the name's `text-decoration-line` is `none`. That spec, t2-roster, and shell-1b passed. One shell-1b recruiting `goBack` aborted on the first pass and passed on retry. `save-per-game` and `save-totals` were retaken at 1280 and 1920.

