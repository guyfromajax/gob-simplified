# Tournament Command Center (TCC)

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

