## Lineup Selection Screen ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Positions**: PG, SG, SF, PF, C (5 positions)
2. **Fouled Out**: Players with 5+ fouls always excluded (applies to both manual and auto-set)
3. **Auto-Set Only - Energy Thresholds**: Default NG >= 80%, Late Q4/OT NG >= 64%
4. **Auto-Set Only - Foul Restrictions**: Q1 (>1), Q2 (>2), Q3 (>3), Q4 (>3 if >4min remaining), OT (none, but 5+ excluded)

---

## Lineup Selection Screen Overview

**Lineup Selection Screen Flow (5 Steps)**

1. **Load Roster Data** - Fetch from mode-specific endpoint, merge game data if `gameId` exists
2. **Display Player Information** - Show stats (PTS, REB, AST, Def%), attributes (EM, MO, NG), fouls
3. **Set Lineup** - Drag-and-drop players to positions, real-time validation
4. **Save and Navigate** - Lineup saved to URL parameters, navigate to Game Plan/Box Score/Gameplay

**Long Form Documentation**

### Overview

The Lineup Selection Screen allows users to set their starting lineup before each game and during timeouts. It displays comprehensive player information including current game stats, attributes, and eligibility status for all roster players.

**Key Features:**
- Drag-and-drop lineup selection (5 positions)
- Real-time display of player stats and attributes
- Player eligibility filtering (fouled out)
- Grid view and player card view modes
- Pre-game and in-game (timeout) lineup management

### Data Sources

**Backend:**
- **Roster API**: ✅ UNIFIED endpoint `/roster/{team_name}` with query parameters (`?franchise_id={id}` or `?tournament_id={id}`) for all modes
- **Game API** (`/api/game/{gameId}`): Returns player stats (including F = fouls), attributes (EM, MO, CH, NG)

**Frontend:**
- `loadRoster()`: Loads roster, merges game data if `gameId` exists; derives fouled-out status from game stats (F ≥ 5) on each visit
- `updateSlotDisplay()`: Displays stats/attributes for lineup players

### Player Stats and Attributes Display

**Lineup Players Show:**
- Stats: PTS, REB (OREB+DREB+REB), AST, Def% (DEF_S/DEF_A*100)
- Attributes: EM (emoji), MO (visual bar -10 to +10), NG (color-coded %), Fouls

**NG color bands (lineup bars and grid view aligned):** Red &lt;70%, Orange 70–80%, Yellow 80–89%, Green 90–100%.

**Data Flow:**
- **Pre-Game**: Roster loads → Game initialized (`/api/init-game`) → Game data merged → All players get EM/MO/CH
- **In-Game**: Roster loads → Game data fetched → Stats/attributes merged → Lineup players display current values

**Mode-Specific Handling:**
- **Single Game**: Roster base attributes + Game stats/attributes (EM, MO, CH, NG)
- **Franchise**: Roster evolved attributes + Game stats/NG
- **Tournament**: Roster base + tournament attributes + Game stats/NG

### Pre-Game EM/MO Display Fix

**Issue:** EM/MO not displaying on pre-game lineup screen despite initialization.

**Root Cause:** `/api/game/{gameId}` only returned lineup players (5), not all roster players (12).

**Fix:** Changed to `team.get_all_players()` to return all players, ensuring all roster players get EM/MO attributes.

### Player Eligibility Filtering (Fouled Out)

**How it works:** Each time the user enters the lineup screen (pre-game, after a timeout, after a quarter break), the screen fetches game data when `gameId` is present. When merging that game data into the roster, any player whose **game foul count (F) is ≥ 5** is marked ineligible (fouled out). No separate ineligible list is persisted or passed from the backend for this screen—eligibility is derived from current game stats on every visit.

**Manual selection:** Fouled-out players (5+ fouls) cannot be added to the lineup. They are greyed out and non-draggable in both grid view and player (card) view.

**Visual indicators:** Reduced opacity, grey styling, disabled drag-and-drop and click-to-fill for fouled-out players in grid and player views. Fouled-out players already in the lineup are removed when the lineup is restored/applied (e.g. from URL or after merge).

**Note:** Energy and foul count filtering (NG thresholds, quarter-specific restrictions) are only applied in the Auto-Set Lineup feature, not for manual selection.

### Key Files

**Frontend:**
- `FrontEnd/static/set-lineup.html` - Page structure
- `FrontEnd/static/set-lineup.js` - `loadRoster()`, `updateSlotDisplay()`, `renderRoster()`, `updatePlayButton()`

**Backend:**
- `BackEnd/api/api.py` - `/api/game/{gameId}`, `/api/init-game`
- `BackEnd/api/franchise_routes.py` - `/franchise/roster`
- `BackEnd/api/tournament_routes.py` - `/tournament/roster`
- `BackEnd/utils/db_utils.py` - `is_player_eligible_for_lineup()`, `build_lineup_from_mongo()`

---

## Auto-Set Lineup Feature

**Auto-Set Lineup Flow (5 Steps)**

1. **Clear Current Lineup** - Remove all players from slots
2. **Randomize Position Order** - Shuffle positions array
3. **For Each Position**: Get available players (NG >= 80%, eligible) → Get top 3 by position rating → Randomly pick one
4. **Update Display** - Update slot displays, re-attach event listeners
5. **Notify User** - Show toast: "Lineup auto-generated!"

**Long Form Documentation**

### Overview

The Auto-Set Lineup feature automatically generates a starting lineup by selecting players based on position ratings and eligibility criteria.

**Location:** `FrontEnd/static/set-lineup.js` - `autosetLineup()` (lines 565-614)

### Algorithm

1. Clear current lineup
2. Randomize position order
3. For each position (in random order):
   - Filter available players (not assigned, NG >= 80%, eligible)
   - Get players with position ratings, sorted desc
   - Take top 3 candidates
   - Randomly pick one
4. Update displays and re-attach event listeners
5. Show notification

**Selection Criteria:**
- **Fouled Out**: 5+ fouls always excluded
- **Energy**: NG >= 80% (default) or >= 64% (late Q4/OT) - Auto-Set only
- **Foul Restrictions**: Quarter-specific restrictions (Q1 >1, Q2 >2, Q3 >3, Q4 >3 if >4min) - Auto-Set only
- **Position Rating**: Only considers players with rating for target position
- **Selection**: Top 3 rated players, random pick (adds variety)
- **Not Already Assigned**: Players can't be assigned to multiple positions

**Result:** Lineup auto-generated with top-rated eligible players at each position.

### Key Files

**Frontend:**
- `FrontEnd/static/set-lineup.js` - `autosetLineup()` (lines 565-614)
