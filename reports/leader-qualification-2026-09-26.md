# Leader qualification (decision 29h)

Branch `fix/leader-qualification`. Implementation commit `519d4cfbf81a02ee80476625a08a7e4aa4824568`. Not merged, not pushed. `main` was not touched. `FrontEnd/static/sounds/` was not committed.

## What changed

Season rate leaders qualify when `attempts >= floor * team games`. Team games are wins plus losses from `franchise.results` for the scope being read (`calculate_franchise_standings`). A tie adds neither a win nor a loss. There is no separate games-played minimum. Zero team games never qualifies. Exactly the floor qualifies. One attempt below does not.

The five floors live in one dict, `LEADER_QUALIFICATION_FLOORS`, with `qualifies(stat, attempts, team_games)` in `BackEnd/constants/leader_qualification.py`.

| Stat | Attempts per team game | Field |
| --- | --- | --- |
| FG% | 5 | FGA |
| 3PT% | 2 | 3PTA |
| FT% | 2 | FTA |
| DEF% | 8 | DEF_A |
| SCR% | 5 | SCR_A |

Career scope was left on the old rule. Career FG% and DEF% still require the denominator to be at least 5 times that player's own GP, and GP greater than 0. Season scope (anything other than `career`) uses `qualifies` and the team's completed games.

Files:

- `BackEnd/constants/leader_qualification.py` (new)
- `BackEnd/api/franchise_routes.py` — season FG% and DEF% in `get_leaders`
- `BackEnd/utils/franchise_league_news.py` — FG% and DEF% boards
- `BackEnd/utils/community_highlights.py` — regular-season top defender
- `tests/test_leader_qualification.py` (new)
- `tests/test_franchise_leaders_endpoint.py` — missed-games drop-out
- `_documentation_master/11_Design_Systems/UX_System.md` — section 13
- `_documentation_master/02_User_Account_Systems/Community_Highlights_System.md` — the 156 DEFA line now points at the shared DEF% floor

No new SQLite operator. Season leaders load `franchises.find_one({_id}, {results: 1})` and `franchise_players_data.find({franchise_id})`, then filter in Python before the limit. Both shapes already compile on the adapter. The same route test passed on mongomock and with `GOB_PERSISTENCE=sqlite`.

## Consumers

Changed (league-leader style):

- `get_leaders` season FG% and DEF% (`GET /franchise/leaders`). Was `denominator >= player GP * 5`.
- League news `LEADER_SPECS` FG% and DEF% (`franchise_league_news._build_leaders`). Was 7.0 FGA per player GP and 6.0 DEF_A per player GP. Now `qualifies` with that team's W+L. A board is still omitted unless 10 players qualify.
- Community highlights top defender (`_top_defender_season_summary`). Was a flat 156 DEF_A. Now `qualifies("DEF%", DEF_A, team games)` for regular-season weeks 1–26 only, matching the record line on that card. The em dash still shows when nobody qualifies. The loop still skips a player with GP 0 before the floor; that is "did not appear," not a volume floor.

Left alone:

- End-of-game / POTG defensive bonus when `DEF_A > 10` in one game (`franchise_routes`, around the EOG bonus).
- Season awards score: DEF% bonus only when `DEF_A >= 130` (`_season_awards_score`). That is a composite award score, not a rate leaderboard.
- Tournament leaderboards in `stat_updater`: FG% / FT% / 3PTM skip only when attempts are 0. Not a per-game floor, and those games are not franchise season games.
- `pgpc_qualification.py` `three_pt_pct`, `team_def_pct`, `player_def_pct`: question-bank `user_min_attempts` / `min_defa` on one game.
- `pgpc_player_slot.py`: single-game slot picks (`DEF_A >= 4` or `3`, `FTA >= 4` or `1`).
- `press_conference_questions.py`: single-game triggers (`user_min_attempts: 10`, `min_defa: 5`).
- `scouting_utils._season_def_pct_whole`: shows DEF% when `DEF_A > 0`. Display, not a ranking floor.
- Team-stats tables that divide by `DEF_A` when it is positive. Display, not a ranking floor.
- Player momentum: no FG% / 3PT% / FT% / DEF% / SCR% volume floor.
- Leaders does not rank 3PT%, FT%, or SCR% today. The floors are defined so a later consumer can call `qualifies`.

## Qualifier census

Save: a copy of `tmp/offline-parity.sqlite`, advanced with `complete-week` from week 5 through week 14, read at week 15. Franchise Lancaster `6ab284847ab3853ae89a1184`. Not the live Application Support save. 128 teams, 1,920 players, every team at 14 completed games (W+L). Floors were not changed after this count.

Required attempts at 14 team games: FG% 70 FGA, 3PT% 28 3PTA, FT% 28 FTA, DEF% 112 DEF_A, SCR% 70 SCR_A.

| Stat | Min per team | Median per team | Max per team | League total |
| --- | --- | --- | --- | --- |
| FG% | 0 | 4 | 7 | 472 |
| 3PT% | 0 | 3 | 7 | 417 |
| FT% | 0 | 4 | 8 | 479 |
| DEF% | 0 | 1 | 6 | 191 |
| SCR% | 0 | 2 | 6 | 256 |

Targets were about 5–7 per team for FG% and DEF%, and about 3–4 for 3PT% and FT%. 3PT% (median 3) and FT% (median 4) sit in that band. FG% median 4 is a little under 5–7. DEF% median 1 is well under 5–7 (37 teams have nobody). SCR% is reported only. Floors were not retuned.

## Leaders load time

The full Leaders scan is still the eight category reads. On SQLite, six of them are still full-table aggregates. FG% and DEF% are a franchise `find` plus the team-games lookup. In-process, on the week-15 file, five interleaved pairs after one warmup of each path:

| | Times (seconds) | Median |
| --- | --- | --- |
| Before (old pipelines, player GP × 5) | 10.628, 12.866, 19.367, 9.812, 16.048 | 12.866 |
| After (`get_leaders`) | 3.183, 15.668, 20.226, 9.185, 12.960 | 12.960 |

A fresh loopback on that same file, `GET /franchise/leaders` (new code): warmup 13.656s, then 7.165 / 3.047 / 9.090, median 7.165s. The same request with `If-None-Match` returned 304 in 0.014s. An earlier pass on the long-lived sim process was about 21s and is not the number above. The spread on this machine is large (about 3s to 20s). Both the old and new scans stay far above 300ms. The rule change did not make the first load cheap.

No local Mongo was listening on 127.0.0.1:27017, so Mongo was not timed. The missed-games route test passed on mongomock and on the SQLite adapter.

The first open of a week is still a multi-second scan. A repeat open in that same week is already a 304: `GET /franchise/leaders` is `@browse_cached`, and the tag is `franchise:season:week:browse_rev:BUILD:signature`, so it does not change until the week, the revision, or the build does. That is the right cache for every visit after the first. It does not help the first visit. A per-week leaders snapshot written in the existing week-advance finalize `$set`, next to `office_week_snapshots`, would turn that first visit into a read of one document and would stay inside the capstone (no sim engine, `cpu_week_pool`, end-of-game persistence, or `sim_rng` change). Not built.

## Tests

- `tests/test_leader_qualification.py`: 15 passed (each of the five stats at the floor, one below, and zero team games).
- `tests/test_franchise_leaders_endpoint.py`: 2 passed. The new case is a team with 10 completed games. The player with GP 4 and 40 FGA (clears 5 × GP, misses 5 × team games) drops out of season FG% and DEF%. The teammate at exactly 50 FGA / 80 DEF_A stays. Career FG% still includes both. `GET /franchise/leaders` returns only the full-season player for FG%.
- Same two files again with `GOB_PERSISTENCE=sqlite`: 17 passed.
- `tests/test_franchise_league_news.py`: 2 passed (boards still have 10 rows; the fixture's 30 FGA and 24 DEF_A still clear 5×3 and 8×3).
- `tests/test_office_digest.py`: 13 passed.
- `tests/test_persistence_adapter.py`: 41 passed (with the files above, 73 passed in 15.46s).
- Standings: `tests/test_roster_team_record.py` 9 passed. Office digest also calls `GET /franchise/standings`.
- `tests/test_community_highlights_game_copy.py` 15 passed and `tests/test_franchise_stats.py` 2 passed (26 passed together).

STATUS: COMPLETE
