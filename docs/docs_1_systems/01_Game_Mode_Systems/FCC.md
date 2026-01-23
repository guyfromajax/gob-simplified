# Franchise Command Center (FCC)

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

