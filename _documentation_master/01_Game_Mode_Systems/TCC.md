# Tournament Command Center (TCC)

## Bracket tab

**Location:** `FrontEnd/static/tournament.js` — `renderBracket()`; shared UI in `FrontEnd/static/bracket.js`.

**Functionality:**
- Renders the 8-team single-elimination bracket (round1, round2, final) with the same layout as the FCC Tournament tab.
- **Shared renderer:** `renderBracketShared(container, bracketData, teamIdToNameMap, options)` from `bracket.js` — single DOM implementation (5-column grid, matchups, logos, seeds, scores). TCC-specific logic (applyResults, derive round2/final from results, localStorage, updateCTA) runs before/after the call.
- **Team names:** `teamIdNameMap` is populated from `/tournament/team-stats` (response `teams`: each has `team_id`, `team`). Used for schedule, bracket, and scouting. Bracket tab passes this map and options (results, getLogo, isUserTeam) into the shared renderer.
- **Layout:** Container `#bracket` has class **`bracket`**; `tournament.css` provides grid (`.bracket`), round columns (`.round-1` … `.round-5`), matchup wrappers, team entries, logos.

**Related:** `docs/To Do/Archive/tournament_eos_bracket_merge_plan.md` §9; `Tournament_Execution_System.md` (Tournament display).

---

## Scouting Report Button

**Location:** `FrontEnd/static/tournament.js`

**Functionality:**
- Button visibility controlled by `updateScoutingButton()` - shows when tournament not completed and user team not eliminated
- Determines upcoming opponent from current round bracket matchups
- On click, `loadScoutingReport()` fetches team data and play usage from:
  - `/tournament/team-data` - opponent team attributes
  - `/tournament/scouting-report` - last game play usage data
- Renders using shared functions from `js/shared/scoutingReport.js`:
  - `renderScoutingTeamReport()` - team attributes grid
  - `renderPlayUsage()` - play usage table
- Modal setup via shared `setupScoutingReport()` function

**Backend:**
- `/tournament/scouting-report` endpoint uses shared utility `BackEnd/utils/scouting_utils.py::extract_plays_from_game_document()`

---

## Exit Tournament Button

**Location:** `FrontEnd/static/tournament.html`, `FrontEnd/static/tournament.js`, `FrontEnd/static/tournament.css`

**Functionality:**
- Replaces the old top-left "Coach/Username" text under the team logo.
- Button label: **Exit Tournament**.
- On click, exits the active tournament command-center session view and routes user to `/mode-select.html`.
