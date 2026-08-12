# Team Builder Phase 0 — `score{}` consumer enumeration

**Date:** 2026-08-01  
**Purpose:** Condition 3 before restoring core-name keys on `gm.score` / persisted `summary["score"]`.

After Phase 0, keys are always **core** `teams.name` (same as `TeamManager.name`). Consumers that look up by the URL chrome name must prefer API `display_name` for labels and **core** `name` / URL `home`/`away` for dict keys.

## Runtime (engine / GM)

| Site | Access pattern | Impact if keys = core |
|---|---|---|
| `GameManager.__init__` | `self.score = {home.name: 0, away.name: 0}` | Uses `.name` — OK once `.name` is core |
| `BackEnd/engine/phase_resolution.py` | `game.score.get(off_team.name, …)` | OK |
| `BackEnd/models/turn_manager.py` | score updates keyed by team `.name` | OK |
| Drive / FB / steal integrations | `game.score` / `game_state["score"]` by `.name` | OK |
| `BackEnd/main.py` sim loops | `gm.game_state["score"][gm.home_team.name]` | OK |
| `BackEnd/practice_squad/sim.py` | same | OK (synthetic names, not TB) |
| `BackEnd/utils/situational_logic.py` | by `.name` | OK |

## Persistence / API summarize

| Site | Access pattern | Impact |
|---|---|---|
| `summarize_game_state` | builds `score` from `teams_obj[*].name` / `game.score.get(game.*.name)` | Must keep keys = core; expose `display_name` on team rows for UI |
| `api.py` init-game | `gm.score = {gm.home_team.name: 0, …}` then `summary["score"] = {home_team, away_team}` | Request names must be core; stop rewriting to display |
| `api.py` simulate-quarter restore | `gm.score[gm.home_team.name] = …` | OK |
| `franchise_routes` box/resume | `score_map.get(home_team_name)` with names from game doc / team rows | OK if doc stores core; resume already has id fallbacks |

## Frontend

| Site | Access pattern | Impact |
|---|---|---|
| `bootGame.js` scorebug / sim full | `turn.score[homeTeamName]` then fallback `homeTeam` (URL) | URL `home`/`away` must be **core**; chrome labels use `home_display` / response `display_name` |
| `gameScene.js` `updateScoreboard` | same pattern | Same |
| `potg.js` | `scoreSource[homeTeamName]` | Prefer core name from game payload |
| `tournament.js` | name-keyed scores | Non-TB; unchanged |
| `set-lineup.js` header scores | `score[userTeamName]` from URL team names | Use core URL `home`/`away` |

## Tests

Many unit tests build `game.score` with fixture team `.name` — remain valid when `.name` is core.

## Staging check (2026-08-01)

- Active `team_builder` franchises: **0**
- Games with score/team names matching known TB displays (Hanson, etc.): **0**
- Non-core score keys found: Practice Squad regional synthetic names only — out of scope

**Conclusion:** No TB migration required; changing keys to core is safe on staging.
