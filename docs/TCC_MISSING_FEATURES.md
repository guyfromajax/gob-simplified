# Tournament Command Center - Missing Features

## Issues Identified

### 1. No Box Scores on Schedule Tab
**Status:** Missing  
**FCC Implementation:** Adds `[Box Score]` link for completed games with `game_id`  
**TCC Implementation:** Only adds `[Training Report]` links, missing box score links  
**Fix Required:** Add box score link logic to `renderSchedule()` in `tournament.js`

### 2. Leaders Not Including User Game Players
**Status:** Needs Investigation  
**FCC Implementation:** `/franchise/leaders` includes all players from franchise document  
**TCC Implementation:** `/tournament/leaders` calls `recompute_tournament_leaders()`  
**Fix Required:** Verify backend endpoint includes all players, check frontend rendering

### 3. Team Stats Grid Not Populating
**Status:** Needs Investigation  
**FCC Implementation:** `/franchise/team-stats` returns team stats array  
**TCC Implementation:** `/tournament/team-stats` exists and should return similar data  
**Fix Required:** Verify endpoint returns data correctly, check frontend rendering

### 4. Player Stats Not on Team Tab
**Status:** Missing  
**FCC Implementation:** `renderRosterStats()` displays player stats table in Team tab  
**TCC Implementation:** `renderTeamReport()` only shows team attributes, no player stats  
**Fix Required:** Add player stats display to Team tab (similar to FCC)

## Additional Features to Review

### FCC Features (excluding Recruits/Standings):
- ✅ Bracket tab (TCC has this)
- ✅ Roster tab with stats (TCC has this)
- ✅ Team tab with attributes + player stats (TCC missing player stats)
- ✅ Stats tab with leaders + team stats grid (TCC has structure, needs fixes)
- ✅ Schedule tab with box scores (TCC missing box scores)
- ✅ Training reports linked from schedule (TCC has this)
- ✅ Team Report section (TCC has this)
- ✅ Playbook Summary section (TCC has this)

## Implementation Plan

1. **Fix Box Scores on Schedule** - Add `game_id` check and box score link
2. **Fix Leaders** - Verify backend includes all players, fix frontend if needed
3. **Fix Team Stats Grid** - Verify backend returns data, fix frontend if needed
4. **Add Player Stats to Team Tab** - Add `renderRosterStats()` equivalent to TCC

