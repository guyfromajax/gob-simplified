# Practice Squad Games System

> **Status:** Implemented 2026-06-14. Regional pseudo-team leagues for Training Squad players + unsigned recruits.

## Terminology

| Term | Meaning |
|---|---|
| **Training Squad** | 3 ineligible development players per franchise team (`training_squad_players`) |
| **Practice Squad (PS)** | Regional all-star pseudo-teams that play simmed games (All-Americans … Scrubs) |

## Overview

- Runs **weeks 2–19** during `/franchise/run-training/distant-cpu` (after user training + distant CPU training).
- **Week 1 end:** after Training Camp cuts, build locked rosters (Teams 1–5), schedule, standings; publish **Practice Squad Rosters Announced** news.
- **No backfill** for franchises mid-season before this feature shipped.
- Cleared on **season rollover** (`practice_squad` doc field + `ps_season_stats` on FPD/FRD).

## Rosters

- Pool per region (A–H): unsigned FRD recruits (`Home Region`) + all `training_squad_players` from 16 teams in that region.
- **Teams 1–5:** 12 players, locked all season. Draft: random position order; top 2 RT at each position (`position_ratings[pos]`); final 2 spots by best-position RT.
- **Team 6 Scrubs:** random 12/week from remainder; stored on `practice_squad.scrubs_rosters.{week}`.
- Scrubs pool **< 5** after Teams 1–5 → forfeit all Scrubs games for the season.
- Scrubs weekly roster **< 5** → forfeit that week's Scrubs games.

## Schedule

- **Weeks 2–15:** double round-robin (8 regions × same tier), 1 game/team/week.
- **Weeks 16–18:** five 8-team tier tournaments (no Scrubs); standard bracket engine (1v8, 4v5, 2v7, 3v6).
- **Week 19:** All-Americans champ vs All-Stars champ; random home team.

## Simulation

- Full engine via `BackEnd/practice_squad/sim.py` with `TeamManager.roster_override`.
- Per-game randomized CPU defaults (strategy, team attrs, scouting, plays).
- Game docs: `games` collection, `mode: "practice_squad"`.
- Stats → `ps_season_stats` on FPD/FRD only (not season/career).

## Persistence

| Data | Location |
|---|---|
| Rosters, schedule, standings, brackets, scrubs weekly | `franchises.practice_squad` |
| Box scores | `games` (`mode=practice_squad`) |
| Player PS stats | `FPD.ps_season_stats` / `FRD.ps_season_stats` |

## News (`season_news`)

1. Week N Upset Report  
2. Week N Practice Squad Game Results (at complete-week; links to standings + box scores)  
3. Practice Squad All-Stars (TS attribute gains)  
4. Updated Recruiting Leans  

**Roster announcement (week 1):** region headings; team name links to roster page; one comma-separated line of `Name (RT)` per team (Teams 1–5 only).

## UI

| Page | Path |
|---|---|
| Standings + schedule accordion | `/practice-squad-standings.html` |
| Tournament brackets | `/practice-squad-bracket.html` |
| PS team roster + player stats | `/team-roster-view.html?mode=practice_squad&ps_team_id=…` |
| Box score | `/box-score.html?mode=practice_squad&game_id=…` |
| FCC Recruits tab link | **Practice Squad Season** → standings |

## Key files

| Area | Path |
|---|---|
| Orchestration | `BackEnd/practice_squad/manager.py` |
| Roster builder | `BackEnd/practice_squad/roster.py` |
| Schedule / brackets | `BackEnd/practice_squad/schedule.py` |
| Sim | `BackEnd/practice_squad/sim.py` |
| Stats rollup | `BackEnd/practice_squad/stats.py` |
| Training hook | `BackEnd/api/franchise_routes.py` → `_franchise_training_distant_phase_only` |
| Week news | `_append_franchise_week_news` |
| API | `/franchise/practice-squad/*` |
