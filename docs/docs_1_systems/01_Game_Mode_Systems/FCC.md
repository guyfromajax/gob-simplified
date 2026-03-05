# Franchise Command Center (FCC)

Franchise-mode hub: team info, standings, schedule, stats, traits, recruits, tournament bracket, and national rankings. Data is scoped by **franchise_id** and the user’s **team_id** (ObjectId).

---

## Data wiring

- **Franchise-level:** All tab data uses `franchise_id` (e.g. `/franchise/standings`, `/franchise/leaders`, `/franchise/team-stats`, `/franchise/team-traits`).
- **User’s team:** Use **`team_id`** (ObjectId string), not team name. Resolved from URL param `team_id` or from `/franchise/command-center/data` (`team_id`, `team`).
- **Command center response** also includes **`user_conference`** and **`user_region`** (from the user’s team document) for Stats and Team Traits scope toggles. Conference/region are dynamic (no assumption the user is in Conference 1).

| Use | Endpoint / param |
|-----|-------------------|
| Team tab (attributes, plays, scouting) | `/franchise/team-data?franchise_id=...&team_id=...` |
| Roster | `/roster/{userTeamId}?franchise_id=...` |
| Training, Game Plan, Set Lineup | Include `team_id=${userTeamId}` in URL params |

---

## Tabs (overview)

| Tab | Content |
|-----|--------|
| **Standings** | Slim view: user's conference (top) and sister conference (bottom) only. Link to **Resources → Standings** for full 16 conferences. Data: `scope=user_region&team_id=...`. |
| **Roster** | Roster table + player stats. |
| **Team** | Team Report (attributes), Playbook Summary. |
| **Schedule** | User's conference schedule only (no toggles on FCC). |
| **Recruits** | Recruit list. |
| **Tournament** | EOS bracket (weeks 15–17); shared with TCC layout. |
| **Resources** | Standings, Stats, Schedule, Team Traits, Rankings (standalone pages). Blue buttons; **Back To Locker Room** (orange) on each page. |

---

## Standings tab

- **Slim view (FCC):** Two blocks only — **Your conference** (top) and **Sister conference** (same region, bottom). No region toggles on the FCC. Team names link to roster view. A note links to **Resources → Standings** for the full 16-conference view.
- **Data:** `/franchise/standings?franchise_id=...&scope=user_region&team_id=...` returns only teams in the user's and sister conference; response includes `user_conference`, `sister_conference`, and `standings` (filtered). Sorted by wins then natl_rank (asc). Full standings (all conferences) are on the standalone **standings.html** page (region toggles A–H).

---

- **On FCC:** User's conference schedule only (no conference toggles). Only games involving the user's conference teams are shown.
- **Full schedule:** The standalone **schedule.html** (via Resources) has 16 conference toggles and lands on the user's conference.
- **Data:** `/franchise/schedule` returns `schedule`, `team_id`, and `team_conferences` (team_id → conference 1–16).

---

## Resources tab and standalone pages

- **Resources tab (on FCC):** Five buttons (blue fill, white bold): Standings, Stats, Schedule, Team Traits, Rankings. Each opens a standalone page with franchise_id and team_id in the URL.
- **Standalone pages:** standings.html, stats.html, schedule.html, team-traits.html, rankings.html. Each has **Back To Locker Room** (orange fill) to return to FCC. Stats/Team Traits: Conference | Region | National toggles. Rankings: Top 25 / All 128. Schedule: 16 conference toggles. Standings: region toggles A–H.
- **Legacy (moved off FCC):** Stats tab content is on stats.html; Team Traits on team-traits.html; Rankings on rankings.html. Scope toggles (Conference | Region | National) and full schedule/standings toggles are on the standalone pages only.

---

## Tournament tab (EOS bracket)

- **When:** Weeks 15–17 after EOS tournament is initialized. Bracket rendered in **Tournament** tab.
- **Layout:** Same as TCC Bracket tab. Shared renderer: `renderBracketShared()` in `bracket.js` (5-column grid, matchups, logos, seeds, scores). Container uses class `bracket`; `tournament.css` and `franchise-command-center.css` apply.
- **Data:** Team names from `/franchise/team-stats` (build `teamIdToNameMap`). Options use `eos_tournament.seeds`, `getLogo`, and `isUserTeam(id)` for user-team highlighting.

---

## Scouting Report button

- **Visibility:** Regular season (weeks 0–14) and EOS (15–17) when user team is not eliminated; controlled by `updateScoutingButton()`.
- **Flow:** Upcoming opponent from `/franchise/play-next-game`. On click, fetch `/franchise/team-data` (opponent) and `/franchise/scouting-report` (play usage); render via `scoutingReport.js` (`renderScoutingTeamReport`, `renderPlayUsage`, `setupScoutingReport`).
- **Backend:** `/franchise/scouting-report` uses `BackEnd/utils/scouting_utils.py::extract_plays_from_game_document()`.

---

## Exit Franchise button

- Replaces old “Coach/Username” under team logo. Label: **Exit Franchise**. On click, navigates to `/mode-select.html`.
