# Franchise Command Center (FCC)

## Tournament tab (EOS bracket)

**Location:** `FrontEnd/static/franchise-command-center.js` — `renderTournamentBracket()`; shared UI in `FrontEnd/static/bracket.js`.

**Functionality:**
- When the user opens the **Tournament** tab (weeks 15–17, after EOS is initialized), the bracket is rendered with the same layout as the TCC Bracket tab.
- **Shared renderer:** `renderBracketShared(container, bracketData, teamIdToNameMap, options)` from `bracket.js` — same DOM (5-column grid, matchups, logos, seeds, scores) as TCC.
- **Team names:** One request to `/franchise/team-stats?franchise_id=...`; response `teams` (each with `team_id`, `team`) is used to build `teamIdToNameMap`. No per-team fetch.
- **Layout:** Container `#tournament-bracket-container` has class **`bracket`** so `tournament.css` applies (grid, rounds, matchup wrappers). Same padding/min-height as TCC via `franchise-command-center.css`. Wrapper has `overflow-x: auto` for horizontal scroll when needed.
- **Options:** Passes `eos_tournament.seeds`, `getLogo` (using `formatTeamName`), and `isUserTeam(id)` (vs `userTeamId`) for user-team highlighting.

**Related:** `docs/To Do/Archive/tournament_eos_bracket_merge_plan.md` §9; `Tournament_Execution_System.md` (Tournament display).

---

## Scouting Report Button

**Location:** `FrontEnd/static/franchise-command-center.js`

**Functionality:**
- Button visibility controlled by `updateScoutingButton()` - shows during regular season (weeks 0-14) and EOS Tournament (weeks 15-17) if user team not eliminated
- Determines upcoming opponent via `/franchise/play-next-game` endpoint
- On click, `loadScoutingReport()` fetches team data and play usage from:
  - `/franchise/team-data` - opponent team attributes
  - `/franchise/scouting-report` - last game play usage data
- Renders using shared functions from `js/shared/scoutingReport.js`:
  - `renderScoutingTeamReport()` - team attributes grid
  - `renderPlayUsage()` - play usage table
- Modal setup via shared `setupScoutingReport()` function

**Backend:**
- `/franchise/scouting-report` endpoint uses shared utility `BackEnd/utils/scouting_utils.py::extract_plays_from_game_document()`

---

## Exit Franchise Button

**Location:** `FrontEnd/static/franchise-command-center.html`, `FrontEnd/static/franchise-command-center.js`, `FrontEnd/static/tournament.css`

**Functionality:**
- Replaces the old top-left "Coach/Username" text under the team logo.
- Button label: **Exit Franchise**.
- On click, exits the active franchise command-center session view and routes user to `/mode-select.html`.
