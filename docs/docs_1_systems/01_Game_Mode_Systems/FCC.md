# Franchise Command Center (FCC)

Franchise-mode hub: team info, standings, roster, team report, recruits, tournament bracket, and links to standalone resource pages (standings, stats, schedule, team traits, rankings, recruiting). Data is scoped by **franchise_id** and the user’s **team_id** (ObjectId).

---

## Data wiring

- **Franchise-level:** All tab data uses `franchise_id` (e.g. `/franchise/standings`, `/franchise/leaders`, `/franchise/team-stats`, `/franchise/team-traits`).
- **User’s team:** Use **`team_id`** (ObjectId string), not team name. Resolved from URL param `team_id` or from `/franchise/command-center/data` (`team_id`, `team`).
- **Command center response** also includes **`user_conference`** and **`user_region`** (from the user’s team document) for Stats and Team Traits scope toggles. Conference/region are dynamic (no assumption the user is in Conference 1).
- **Command center response** also includes:
  - `current_recruiting_results_week` for the FCC Recruiting button state
  - `lean_recruits` for the FCC Recruits tab
  - `week_35_user_recruits` for the FCC Recruits tab after week `35` recruiting runs
  - `team_name_map` so recruit lean team IDs render as team names

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
| **Recruits** | Phase-based recruit list. Before week `36`, show recruits currently leaning toward the user's team. Starting week `36`, show the user team's signed recruits and walk-ons. Default sort RT descending. All columns are sortable. |
| **Tournament** | EOS bracket (weeks 27–34); shared with TCC layout. |
| **Resources** | Standings, Stats, Schedule, Team Traits, Rankings, Recruits (standalone pages). Blue buttons; **Back To Locker Room** (orange) on each page. |

---

## Standings tab

- **Slim view (FCC):** Two blocks only — **Your conference** (top) and **Sister conference** (same region, bottom). No region toggles on the FCC. Team names link to roster view. A note links to **Resources → Standings** for the full 16-conference view.
- **Data:** `/franchise/standings?franchise_id=...&scope=user_region&team_id=...` returns only teams in the user's and sister conference; response includes `user_conference`, `sister_conference`, and `standings` (filtered). Sorted by wins then natl_rank (asc). Full standings (all conferences) are on the standalone **standings.html** page (region toggles A–H).

---

## Recruits tab

- **Weeks 1-35 (pre-results):** Only recruits whose `Lean.1`, `Lean.2`, or `Lean.3` currently matches the user's `team_id`.
- **Week 36 onward:** Show signed recruits and walk-ons for the user's team from `week_35_recruiting_results`.
- **Columns before week 36:** `Name`, `Home Region`, `Archetype`, `HT`, `WT`, `POS`, `SC`, `SH`, `ID`, `OD`, `PS`, `BH`, `RB`, `AG`, `ST`, `ND`, `IQ`, `FT`, `RT`, `Current Lean`.
- **Columns starting week 36:** Same as the standalone recruiting results page, but omit `Signed`.
- **Walk-ons:** Display `(walk on)` next to the player name.
- **Sort behavior:** Default sort is `RT` descending. All header columns are sortable. Repeated clicks toggle `desc -> asc -> desc`.
- **Current Lean rendering:** Uses the same lean-display rules as the recruiting standalone pages, with team IDs translated to team names via `team_name_map`.

---

## Resources tab and standalone pages

- **Resources tab (on FCC):** Seven buttons (blue fill, white bold): Standings, Stats, Schedule, Team Traits, Rankings, Recruits, Awards. Each opens a standalone page with `franchise_id` and `team_id` in the URL.
- **Awards button state:** Dead through week `34`; active starting week `35`.
- **Standalone pages:** standings.html, stats.html, schedule.html, team-traits.html, rankings.html, recruiting.html. Each has **Back To Locker Room** (orange fill) to return to FCC. **Schedule** is only on schedule.html (no Schedule tab on FCC); schedule.html has 16 conference toggles and lands on the user's conference. Stats/Team Traits: Conference | Region | National. Rankings: Top 25 / All 128. Standings: region toggles A–H.
- **Legacy (moved off FCC):** Stats tab content is on stats.html; Team Traits on team-traits.html; Rankings on rankings.html. Scope toggles (Conference | Region | National) and full schedule/standings toggles are on the standalone pages only.

---

## Recruiting button

- **Placement:** Upper-right hero area under `Run Training / Play Now`.
- **Weeks 1-19:** Dead button with copy `Recruiting Begins Week 20`.
- **Weeks 20-26, before current-week recruiting is processed:** Active button with copy `Recruiting`; opens `recruiting-orders.html`.
- **Weeks 20-26, after current-week recruiting is processed:** Active button with copy `Week ## Recruiting Visits`; opens `recruiting-results.html`.
- **Weeks 27-34:** Dead button with copy `Recruiting Returns Later`.
- **Week 35:** Primary CTA copy `Recruiting`; opens `recruiting-orders.html`. Show bold green copy below it: `Recruiting Is Live`. The week-35 page header reads `Recruiting Focus List`.
- **Week 36:** Primary CTA copy `Go To Next Season`; recruiting orders are closed.
- **Post-championship state:** After EOS national week `34` completes, franchise mode advances to week `35`.

---

## Tournament tab (EOS bracket)

- **When:** Weeks 27–34 after EOS tournament is initialized. Bracket rendered in **Tournament** tab.
- **Layout:** Same as TCC Bracket tab. Shared renderer: `renderBracketShared()` in `bracket.js` (5-column grid, matchups, logos, seeds, scores). Container uses class `bracket`; `tournament.css` and `franchise-command-center.css` apply.
- **Data:** Team names from `/franchise/team-stats` (build `teamIdToNameMap`). Options use `eos_tournament.seeds`, `getLogo`, and `isUserTeam(id)` for user-team highlighting.
- **Tooltip:** On hover over a bracket team logo, show `"{team name} {team mascot}, conference {team conference}"`. Example: `"Bentley-Truman Sterling Knights, conference 1A"`.

---

## Scouting Report button

- **Visibility:** Regular season (weeks 0–14) and EOS (15–17) when user team is not eliminated; controlled by `updateScoutingButton()`.
- **Flow:** Upcoming opponent from `/franchise/play-next-game`. On click, fetch `/franchise/team-data` (opponent) and `/franchise/scouting-report` (play usage); render via `scoutingReport.js` (`renderScoutingTeamReport`, `renderPlayUsage`, `setupScoutingReport`).
- **Backend:** `/franchise/scouting-report` uses `BackEnd/utils/scouting_utils.py::extract_plays_from_game_document()`.

---

## Exit Franchise button

- Replaces old “Coach/Username” under team logo. Label: **Exit Franchise**. On click, navigates to `/mode-select.html`.
- To the right of **Exit Franchise**, show `Season XX`, where `XX` is the franchise document's `current_season` value.

## Go To Next Season

- **Week 36 CTA:** Primary hero button copy is `Go To Next Season`.
- **Confirmation:** Uses the existing FCC confirmation modal before proceeding.
- **Behavior:** Calls the franchise-only next-season init flow and returns the user directly to FCC for the same `franchise_id`.
- **Important:** This is not a delete-and-reselect flow. The user does not go back to team select, and the franchise instance persists with aged returning players, signed recruits, walk-ons, and preserved career stats.
