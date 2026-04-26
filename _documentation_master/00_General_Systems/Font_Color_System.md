## Font Color System ✅ **UNIFIED** (January 2025)

**Base Constants**

1. **Energy Thresholds**:
   - Green: `> 0.89` (89-100%) - High energy
   - Yellow: `>= 0.8` and `<= 0.89` (80-89%) - Medium-high energy
   - Orange: `>= 0.7` and `< 0.8` (70-80%) - Medium-low energy
   - Red: `< 0.7` (0-70%) - Low energy

2. **Color Values**:
   - Green: `#00aa00` (Dark green)
   - Yellow: `#cccc00` (Dark yellow)
   - Orange: `#ff8800` (Orange)
   - Red: `#cc0000` (Dark red)

**Font Color System Flow (3 Interfaces)**

1. **Lineup Rows (5 Slots)**
   - Calculate energy percentage: `(NG * 100)`
   - Determine CSS class: `high` (>89%), `medium` (80-89%), `low` (70-80%), `critical` (<70%)
   - Apply class to energy display: `<div class="player-energy ${energyClass}">${energyPercent}%</div>`
   - CSS applies font color based on class

2. **Player Grid (Roster Table)**
   - Get NG value from player attributes
   - Determine background color: Green (>0.89), Yellow (>=0.8), Orange (>=0.7), Red (<0.7)
   - Apply background color to NG cell (always) and player name cell (if NG <= 0.89)
   - Use white font (`#fff`) on colored backgrounds, bold for player name when colored

3. **Player Box Score (Court Page)**
   - Get NG value from `turn.player_energy[playerId].NG`
   - Calculate color using `getEnergyColor(ng)` function
   - Apply font color to all cells in player's row (name, PTS, REB, AST, FOULS, STL, BLK, TO, DEF_A, DEF_S, DEF_PCT)
   - Update dynamically as player energy changes during gameplay

**Long Form Documentation**

### Overview

The Font Color System provides consistent visual feedback for player energy (NG - Nerve/Game) levels across all game interfaces. All three interfaces use identical thresholds (70/80/89%) and color values for consistency.

### Implementation Details

**Lineup Rows:**
- **Location:** `FrontEnd/static/set-lineup.js` - `updateSlotDisplay()` (lines 658-699)
- **System:** CSS classes (`high`, `medium`, `low`, `critical`) applied to energy percentage text
- **CSS:** `FrontEnd/static/set-lineup.css` - `.player-energy` classes (lines 610-630)

**Player Grid:**
- **Location:** `FrontEnd/static/set-lineup.js` - `renderRoster()` (lines 360-415)
- **System:** Background color with white font on NG cell (always) and player name cell (if NG ≤ 0.89)
- **Visual:** More prominent than lineup rows, helps identify low-energy players in roster

**Player Box Score:**
- **Location:** `FrontEnd/static/js/phaser/gameScene.js` - `getEnergyColor()` (lines 489-494) and `applyPlayerStats()` (lines 980-1003)
- **System:** Font color applied to all cells in player's row, updates dynamically during gameplay
- **Visual:** Comprehensive real-time feedback as energy changes

### Design Rationale

**Consistency:** All interfaces use identical thresholds and colors for consistent visual language across the game experience.

**Visual Hierarchy:**
- Lineup Rows: Font color only (subtle)
- Player Grid: Background color (prominent)
- Player Box Score: Font color on all cells (comprehensive, real-time)

**Color Psychology:** Green = Good, Yellow = Caution, Orange = Warning, Red = Critical

### Key Files

- `FrontEnd/static/set-lineup.js` - Lineup Rows and Player Grid logic
- `FrontEnd/static/set-lineup.css` - Lineup Rows CSS classes
- `FrontEnd/static/js/phaser/gameScene.js` - Player Box Score color application
- `BackEnd/models/player.py` - Player NG attribute storage
- `BackEnd/models/turn_manager.py` - `player_energy` population for frontend updates
