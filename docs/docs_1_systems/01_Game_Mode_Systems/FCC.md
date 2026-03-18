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
- **Standalone pages:** standings.html, stats.html, schedule.html, team-traits.html, rankings.html, recruiting.html. Each has **Back To Locker Room** (orange fill) to return to FCC. **Schedule** is only on schedule.html (no Schedule tab on FCC). Stats/Team Traits: Conference | Region | National. Rankings: Top 25 / All 128. Standings: region toggles A–H.
- **Legacy (moved off FCC):** Stats tab content is on stats.html; Team Traits on team-traits.html; Rankings on rankings.html. Scope toggles (Conference | Region | National) and full schedule/standings toggles are on the standalone pages only.

### Back To Locker Room behavior

- **FCC tab state lives in the URL** via `tab=...` on `franchise-command-center.html`.
- **Direct FCC outbound links** to standalone franchise pages include a relative `return_url` that preserves the full FCC URL, including the active tab.
- **Back To Locker Room** buttons on FCC-launched pages use `return_url` first. This restores the user to the same FCC tab they were on when they left.
- **Fallback behavior:** if a page was not launched directly from FCC and no valid `return_url` is present, the button falls back to the normal FCC URL. That lands the user on FCC’s default tab, which is Standings.
- **Safety rule:** `return_url` is sanitized to same-origin relative paths only. External redirects are ignored.
- **Examples:**
  - FCC `Roster` tab → `Standings` resource page → **Back To Locker Room** returns to FCC `Roster`
  - end-of-game flow → `box-score.html` → **Back To Locker Room** returns to FCC default `Standings`, because the page was not entered from FCC

### Schedule

- **Conference toggles:** `schedule.html` shows 16 conference toggles and lands on the user's conference by default.
- **Lazy load behavior:** On initial page load, only the user's conference schedule is fetched from `/franchise/schedule`.
- **On-demand fetches:** When the user clicks another conference toggle, `schedule.html` fetches only that conference's schedule from `/franchise/schedule?conference={n}`.
- **Session cache:** Conference schedule payloads are cached for the current browser session in memory and `sessionStorage`, keyed by franchise id, season, week, and conference.
- **Invalidation:** Changing franchise week or current season changes the cache key, so stale prior-week schedules are not reused.
- **Payload shaping:** The schedule endpoint returns the selected conference's schedule plus the team-name map needed to render roster links, so `schedule.html` no longer fetches standings data just to build team labels.

---

## Recruiting button

- **Placement:** Upper-right hero area under `Run Training / Play Now`.
- **Weeks 1-18:** No recruiting button. Show bold green copy `Recruiting Invites Begin Week 20`.
- **Week 19:** No recruiting button. Show bold green copy `Recruiting Invites Begin Next Week`.
- **Weeks 20-26, before current-week recruiting is processed:** No recruiting button. Show bold green copy `Recruiting Invites Active`.
- **Weeks 20-26, after current-week recruiting is processed:** Active button with copy `Week ## Recruiting Visits`; opens `recruiting-results.html`.
- **Weeks 27-34:** No recruiting button. Show bold green copy `Recruiting Returns Later`.
- **Week 35:** Primary CTA copy `Recruiting`; opens `recruiting-orders.html`. Show bold green copy below it: `Recruiting Is Live`. The week-35 page header reads `Recruiting Focus List`.
- **Week 36:** Primary CTA copy `Go To Next Season`; recruiting orders are closed.
- **Post-championship state:** After EOS national week `34` completes, franchise mode advances to week `35`.

---

## Tournament tab (EOS bracket)

- **When:** Weeks 27–34 after EOS tournament is initialized. Bracket rendered in **Tournament** tab.
- **Header by phase:**
  - weeks `27-29`: `Conference Tournament`
  - weeks `30-31`: `Region Tournament`
  - weeks `32-34`: `National Tournament`
- **Layout:** Shared renderer: `renderBracketShared()` in `bracket.js`.
  - Conference and National brackets use the full 5-column shared layout.
  - Region bracket uses a compact 2-round layout with the right-side bracket columns removed.
- **Stacked history view:**
  - weeks `27-29`: show only the user's Conference Tournament bracket
  - weeks `30-31`: show Region Tournament on top and the user's Conference Tournament below it
  - weeks `32-34`: show National Tournament on top, the user's Region Tournament below it, and the user's Conference Tournament at the bottom
  - weeks `35-36`: keep the same stacked National + Region + Conference tournament history visible until next season init clears EOS state
  - sections are separated by horizontal divider lines
- **Section backgrounds:**
  - Conference Tournament: white
  - Region Tournament: very light gray
  - National Tournament: slightly darker light gray
- **Data:** Team names from `/franchise/team-stats` (build `teamIdToNameMap`). Options use `eos_tournament.seeds`, `getLogo`, and `isUserTeam(id)` for user-team highlighting.
- **Tooltip:** On hover over a bracket team logo in Conference, Region, or National tournament views, show `"{team name} {team mascot}, conference {team conference}"`. Example: `"Bentley-Truman Sterling Knights, conference 1A"`.

---

## Scouting Report button

- **Visibility:** Regular season (weeks 0–14) and EOS (15–17) when user team is not eliminated; controlled by `updateScoutingButton()`.
- **Flow:** Upcoming opponent from `/franchise/play-next-game`. On click, fetch `/franchise/team-data` (opponent) and `/franchise/scouting-report` (play usage); render via `scoutingReport.js` (`renderScoutingTeamReport`, `renderPlayUsage`, `setupScoutingReport`).
- **Backend:** `/franchise/scouting-report` uses `BackEnd/utils/scouting_utils.py::extract_plays_from_game_document()`.

---

## Post-Training Camp Cuts

- **When:** After week 1 training camp only, if user roster size is greater than 12.
- **Modal:** On return to FCC from training report, present:
  - `You need to cut X players`
- **CTA:** Main upper-right CTA becomes `Cut Players` until roster is legal.
- **Flow:** `Cut Players` routes to `cut-players.html`. Once cuts are submitted and roster reaches 12, FCC returns to normal `Play Next Game` cadence.

---

## Exit Franchise button

- Replaces old “Coach/Username” under team logo. Label: **Exit Franchise**. On click, navigates to `/mode-select.html`.
- To the right of **Exit Franchise**, show `Season XX`, where `XX` is the franchise document's `current_season` value.

## Go To Next Season

- **Week 36 CTA:** Primary hero button copy is `Go To Next Season`.
- **Confirmation:** Uses the existing FCC confirmation modal before proceeding.
- **Behavior:** Calls the franchise-only next-season init flow and returns the user directly to FCC for the same `franchise_id`.
- **Important:** This is not a delete-and-reselect flow. The user does not go back to team select, and the franchise instance persists with aged returning players, signed recruits, walk-ons, and preserved career stats.
