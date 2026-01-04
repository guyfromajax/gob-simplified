## Box Score System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Data Sources**:
   - **Roster API** (`/roster/{team_name}`): Returns player baseline data (jersey, year, height, weight, attributes)
   - **Box Score API** (`get_box_score()`): Returns player stats for all players (lineup + bench) with name, playerId, jersey, and all stat values
   - **Game Summary**: Includes team totals, box score, and player energy levels

2. **Display Components**:
   - **Team Statistics**: Totals (PTS, FGM/FGA, 3PTM/3PTA, FTM/FTA, REB, AST, STL, BLK, F, TO, DEF_A/DEF_S), Special stats (Fast Break Points, Points In Paint, Points Off Turnovers)
   - **Player Statistics**: Standard stats table (all tracked stats per player), Special stats popup (Fast Break, Outlet Passes, Traps, Presses, Points Off TOs)
   - **Jersey Number Display**: Appears next to player names (`Player Name (#44)`) and in special stats popup header

3. **Data Processing**:
   - `combinePlayersAndBoxScore()`: Merges roster data with box score stats
   - Handles both lineup players (by position) and bench players
   - Preserves jersey numbers from multiple possible sources (`jersey`, `jerseyNumber`, `jersey_number`)

**Box Score System Flow (4 Steps)**

1. **Data Retrieval** - Fetch roster data from `/roster/{team_name}` API and box score data from `get_box_score()` method
2. **Data Merging** - Combine roster and box score data using `combinePlayersAndBoxScore()` function
3. **Rendering** - Display team statistics and player statistics tables with formatted values
4. **Special Stats** - Show detailed special stats popup when player name is clicked

**Long Form Documentation**

### Overview

The Box Score System displays comprehensive game statistics for both teams and individual players. It aggregates data from the Statistics System and presents it in a user-friendly format accessible from the post-game screen.

**Location:** `FrontEnd/static/box-score.html`, `FrontEnd/static/box-score.js`, `BackEnd/models/game_manager.py`  
**Status:** ✅ Fully implemented with jersey number display and special stats popup  
**Scope:** Team-level and player-level statistics display

### Data Sources

**Backend Data:**
- **Roster API** (`/roster/{team_name}`): Returns player baseline data including `jersey`, `year`, `height`, `weight`, `attributes`
- **Box Score API** (`get_box_score()`): Returns player stats for all players (lineup + bench) with `name`, `playerId`, `jersey`, and all stat values
- **Game Summary**: Includes team totals, box score, and player energy levels

**Frontend Processing:**
- `combinePlayersAndBoxScore()`: Merges roster data with box score stats
- Handles both lineup players (by position) and bench players
- Preserves jersey numbers from multiple possible sources (`jersey`, `jerseyNumber`, `jersey_number`)

### Player Jersey Number Display ✅ **NEW** (January 2025)

**Issue:**
Jersey numbers were not appearing in the box score display or special stats popup because the backend APIs were not including jersey data.

**Root Cause:**
- Roster API (`/roster/{team_name}`) was missing `jersey` field in response
- Box Score API (`get_box_score()`) was missing `jersey` field for both lineup and bench players

**Fix:**
- **Roster API**: Added `"jersey": p.get("jersey", 0)` to player objects in `/roster/{team_name}` endpoint
- **Box Score API**: Added `"jersey": player.jersey` to both lineup and bench player entries in `get_box_score()` method

**Display:**
- Jersey numbers appear next to player names in the box score table: `Player Name (#44)`
- Jersey numbers appear in special stats popup header: `Player Name | #44`
- Handles jersey number 0 as valid (some players may have jersey 0)

**Key Files:**
- `BackEnd/api/api.py` - Roster API endpoint (line 1896)
- `BackEnd/models/game_manager.py` - `get_box_score()` method (lines 757-788)
- `FrontEnd/static/box-score.js` - Jersey number display logic (lines 397-428, 1156-1181)

### Team Statistics Display

**Team Totals:**
- Points, Field Goals, 3-Pointers, Free Throws
- Rebounds (Defensive, Offensive, Total)
- Assists, Steals, Blocks, Fouls, Turnovers
- Defensive Attempts and Success Rate

**Special Team Stats:**
- **Fast Break Points**: Aggregated from player `FB_PTS` stats
- **Points In The Paint**: Aggregated from player `PIP` stats
- **Points Off Turnovers**: Aggregated from player `POT` stats

### Player Statistics Display

**Standard Stats Table:**
- All tracked stats per player (FGM/FGA, 3PTM/3PTA, FTM/FTA, etc.)
- Minutes played (formatted as MM:SS)
- Defensive and Screen success rates (percentages)

**Special Stats Popup:**
- **Column 1**: Fast Break stats (Offense/Defense attempts and success rates), Outlet Passes (Attempts/Score)
- **Column 2**: Traps (HCT) stats (Offense/Defense attempts and success rates), Points Off TOs (integer value)
- **Column 3**: Presses (FCP) stats (Offense/Defense attempts and success rates)

### Court Page Team Box Score (S3) — Team Measures

**Location:** `FrontEnd/static/court.html` (Team tabs S3)

**Layout:** Horizontal pills (same style as Command Center/Training Report) in this order:
1. Shooting (`shot_threshold`)
2. Rebounding (`rebound_modifier`)
3. Offense Efficiency (`offensive_efficiency`)
4. Defense Efficiency (`defensive_efficiency`)
5. Fast Break Efficiency (`fb_efficiency`)
6. Press/Trap Efficiency (`pt_efficiency`)
7. Aggression (`aggression`)
8. Discipline (`discipline`)
9. Momentum (`momentum_score`)
10. Team Chemistry (chemistry bar)

**Behavior:** Uses red/green pill component; Team Chemistry uses a fill bar (0–25). Values display next to labels; chemistry shows "value / 25".

**Styles:** Reuses `command-center-team-styles.css` for pills; court-specific layout defined in `court.html`.

### Key Files

**Frontend:**
- `FrontEnd/static/box-score.html` - Box score page structure
- `FrontEnd/static/box-score.js` - Box score rendering and data processing (`combinePlayersAndBoxScore()`, `renderPlayerStatsTable()`, `showSpecialStatsPopup()`)

**Backend:**
- `BackEnd/api/api.py` - Roster API endpoint (`/roster/{team_name}`)
- `BackEnd/models/game_manager.py` - Box score generation (`get_box_score()` method, lines 757-788)
- `BackEnd/models/team_manager.py` - Team stat aggregation (`get_team_game_stats()`)

