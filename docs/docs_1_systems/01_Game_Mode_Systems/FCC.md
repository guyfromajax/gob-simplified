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
| **Standings** | Region toggles (A–H); per region, conferences with tables: Team, W, L, %, PF, PA, Next. Team names link to roster view. |
| **Schedule** | 16 conference toggles (Conf A1 … Conf H16, 2 rows of 8). Default: user’s conference. Only games for that conference’s teams. |
| **Stats** | Scope toggles (Conference / Region / National); Team Stats table + stat leaders (PTS, 3PTM, REB, AST, BLK, STL). |
| **Team Traits** | Scope toggles (Conference / Region / National); team attribute totals table + Top 10 (excluding FT). |
| **Recruits** | Recruit list. |
| **Tournament** | EOS bracket (weeks 15–17); shared with TCC layout. |
| **Rankings** | National rank 1–128; toggle Top 25 / All 128. Conference 1 teams in primary color, bold. |

---

## Standings tab

- **8 region toggles:** Region A through Region H. One active at a time.
- **Per region:** Conferences in that region are listed in order (e.g. Region A: Conference A1, Conference A2; Region H: Conference H15, Conference H16). Each conference has a table: **Team | W | L | % | PF | PA | Next**. Teams sorted by wins then point differential. Team name links to `/team-roster-view.html` (franchise, same team_id, return to standings).
- **Data:** `/franchise/standings`. Response includes `region` and `conference` per team for grouping.

---

## Schedule tab

- **16 conference toggles:** Conf A1, Conf A2, … Conf H16 (2 rows of 8). No region or national toggles.
- **On load:** User’s conference is detected from command-center data (`user_conference`); that conference’s toggle is active and only games involving teams in that conference are shown.
- **Filter:** For the selected conference, each week shows only games where the away or home team is in that conference (conference games, region games, and OOR games that involve that conference).
- **Data:** `/franchise/schedule` returns `schedule`, `team_id`, and `team_conferences` (team_id → conference 1–16). Frontend caches schedule and re-renders from cache when the conference toggle changes.

---

## Stats tab

- **Scope toggles:** Conference | Region | National. Default: Conference.
  - **Conference:** 8 teams (and their players) in the user’s conference.
  - **Region:** 16 teams (and their players) in the user’s region.
  - **National:** All 128 teams and players.
- **Content:** (1) Team Stats table (W, L, PF, PA, FGM/FGA, 3PT, FT, REB, AST, STL, BLK, etc.). (2) Leaders sections (Points, 3PT Made, Rebounds, Assists, Blocks, Steals); user-team players highlighted in primary color and bold.
- **Data:** `/franchise/command-center/data` (user_conference, user_region), `/franchise/leaders`, `/franchise/team-stats`. Leaders and team-stats responses include `conference` and `region` per team/entry; frontend filters by scope.

---

## Team Traits tab

- **Scope toggles:** Conference | Region | National. Same behavior as Stats (user’s conference = 8 teams, user’s region = 16, national = 128). Default: Conference.
- **Content:** Team attribute totals table (SC, SH, ID, OD, PS, BH, RB, AG, ST, ND, IQ, FT, Total); team names in primary color, bold. Below: “Top 10 (excluding FT)” list.
- **Data:** `/franchise/team-traits`. Response includes `conference` and `region` per team; frontend filters by selected scope.

---

## Rankings tab

- **Display:** “{natl_rank}. {team_name}” (e.g. “7. Bentley-Truman”). No prestige in list.
- **Toggle:** Top 25 (default) | All 128.
- **Conference 1 teams:** Rendered in primary color and bold. Conference/primary_color come from command-center rankings payload (per team).
- **Data:** `/franchise/command-center/data` includes `rankings` (array of `natl_rank`, `team_name`, `primary_color`, `conference`), plus user’s `rank` and `prestige` for the top bar.

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
