# Franchise Mode Overview

Franchise Mode is the game's primary (and currently only active) mode: a multi-season career where team and player progression persists across games and seasons. This doc is the top-level orientation map — the season lifecycle, where franchise state lives, and how a game consumes that state — with pointers to the detailed system docs. It intentionally does not duplicate their content.

---

## Season lifecycle

A franchise season runs 36 weeks for **128 teams** (conference → region → out-of-region scheduling):

| Weeks | Phase |
|---|---|
| 1 | Training camp (before any games). After camp in season 2+, rosters above 12 must cut down before gameplay resumes |
| 1–26 | Regular season (26-week schedule, one game per team per week) |
| 20–26 | Recruiting visits run alongside the late regular season |
| 27–29 | Conference tournaments (first round / semis / championship) |
| 30–31 | Region tournaments |
| 32–34 | National tournament (week 34 = National Championship) |
| 35 | Awards + live recruiting / signings (recruiting orders, point spend) |
| 36 | Signed-results / wrap-up state; `Go To Next Season` becomes the primary CTA |

`Go To Next Season` (`POST /franchise/finish-season`) runs an **in-place season rollover** on the same franchise instance — players age (JH → FR → SO → JR → SR), signed recruits join rosters, and the user returns directly to FCC for the new season.

Weekly progression is driven by `POST /franchise/complete-week` (user game commit, CPU sims, training reset, news generation, recruiting updates). The FCC hero CTA reflects the lifecycle state week by week — see `FCC.md` for the full CTA state machine and tournament-round labels.

## Where franchise state lives

Franchise progression never writes to the universal `players` / `teams` collections. Those are read once at franchise creation; everything after that is franchise-scoped:

| Store | Keyed by | Holds |
|---|---|---|
| `franchises` doc | `_id` (franchise ObjectId) | `week`, `current_season`, schedule, standings-supporting game refs, EOS tournament state (`conference_tournaments`, `region_tournaments`, `national_tournament`, `eos_tournament`), `season_inbox`, `season_news`, recruiting state, `players` (career-stats map) |
| `franchise_team_data` (FTD) | `franchise_id` + `team_id` | Per-team progression: team attributes, `plays` (with effectiveness), `scouting_data`, `playbook_settings`, strategy settings |
| `franchise_players_data` (FPD) | `franchise_id` + `player_id` | Per-player progression: trained attributes (SC, SH, …, NG), year, roster membership |

Season initialization (`FranchiseManager.initialize_season`, `BackEnd/models/franchise_manager.py`) generates the 26-week schedule, sets `week = 1`, and seeds FTD/FPD for all 128 teams from the universal collections. `FRANCHISE_START_WEEK` env var can start a franchise at a later week for testing.

Roster size rule: teams carry **12–15 players** from post-recruiting through the season transition; after week-1 training camp the roster must be cut to a legal 12 before gameplay resumes (`cut-players.html`, `cut_required` on the command-center payload).

## How a game consumes franchise state

1. `POST /api/init-game` with `mode=franchise` loads FTD for **both** teams via `load_ftd_data_for_team()` (`BackEnd/api/api.py`), normalized by `prepare_ftd_for_new_game()` (`BackEnd/utils/franchise_ftd_game_seed.py`). `GameManager` is constructed with `home_team_attributes` / `away_team_attributes`, strategy, plays, scouting, and per-team `playbook_settings`.
2. Rosters load through `load_roster(team_name, franchise_id=...)` (`BackEnd/utils/roster_loader.py`), which reads **FPD** and merges franchise-specific attributes over the universal player base — so trained attributes (including NG changes) are live in gameplay.
3. The summarized game document stores team objects under `teams.{canonical_team_id}`; completed games feed standings, stats, Geek Points, and the user's coaching-archetype record.

## Detailed system docs

- `Team_Builder_System.md` (this folder) — per-franchise slot overlay (custom program); identity/ObjectId rules, Apply, resolver, assets
- `FCC.md` (this folder) — the Franchise Command Center: tabs, hero CTA state machine, data wiring, caches, endpoints
- `06_GMO_Supporting_Systems/Season_Init_System.md` — franchise/season initialization detail
- `06_GMO_Supporting_Systems/Training_System.md` — training camp + weekly training, attribute/effectiveness movement
- `06_GMO_Supporting_Systems/Recruiting_System.md` — recruit generation, leans, visits, week-35 signing
- `06_GMO_Supporting_Systems/EOS_Write_Path_Inventory.md` — end-of-season tournament write paths
- `06_GMO_Supporting_Systems/News_System.md` — weekly news stories (FCC News card + tab)
- `03_Data_Persistence/Data_Persistence_System.md` — FTD / FPD / game-document persistence detail
- `00_General_Systems/Geek_Points_System.md`, `00_General_Systems/Coaching_Archetype_System.md` — per-user reward and archetype tracking fed by franchise games

## Regression tests

- `tests/test_franchise_game_scoping.py::test_schedule_scopes_game_lookup_to_franchise`
- `tests/test_franchise_game_scoping.py::test_save_game_result_legacy_lookup_uses_franchise_scope`
- `tests/test_franchise_game_scoping.py::test_schedule_endpoint_does_not_leak_cross_franchise_game_docs`
