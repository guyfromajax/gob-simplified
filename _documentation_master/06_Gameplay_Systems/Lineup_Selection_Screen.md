## Lineup Selection Screen ✅ **COMPLETE** (January 2025; re-verified against code June 2026)

**Base Constants**

1. **Positions**: PG, SG, SF, PF, C (5 positions)
2. **Fouled Out**: Players with 5+ fouls always excluded (applies to both manual and auto-set)
3. **Auto-Set Only - Energy Thresholds**: Default NG >= 80%, Late Q4/OT NG >= 64%
4. **Auto-Set Only - Foul Restrictions**: Q1 (>1), Q2 (>2), Q3 (>3), Q4 (>3 if >4min remaining), OT (none, but 5+ excluded)

---

## Lineup Selection Screen Overview

**Lineup Selection Screen Flow (4 Steps)**

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
- **Single Game (sunset)**: Roster base attributes + Game stats/attributes (EM, MO, CH, NG)
- **Franchise**: Roster evolved attributes + Game stats/NG
- **Tournament (sunset)**: Roster base + tournament attributes + Game stats/NG

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
- `FrontEnd/static/set-lineup.js` - `loadRoster()`, `autosetLineup()` → `POST /api/autoset-lineup`, `updateSlotDisplay()`, `renderRoster()`, `updatePlayButton()`
- `FrontEnd/static/js/phaser/utils/autosetLineupApi.js` - `generateBothLineupsFromApi()` for sim Q2–Q4 (same endpoint)

**Backend:**
- `BackEnd/api/api.py` - `/api/game/{gameId}`, `/api/init-game`, `POST /api/autoset-lineup`, `GET /roster/...` (includes `team_chemistry` when franchise/tournament context is passed)
- `BackEnd/api/franchise_routes.py` - `/franchise/roster`
- `BackEnd/api/tournament_routes.py` - `/tournament/roster`
- `BackEnd/utils/db_utils.py` - `is_player_eligible_for_lineup()`, `build_lineup_from_mongo()`, `autoset_lineup_player_ids_from_payload()`, `fill_unified_lineup_gaps()`, `_team_chemistry_pool_sizes()`
- `BackEnd/main.py` - `_ensure_complete_lineup()` (uses `fill_unified_lineup_gaps` for missing slots)
- `tests/test_unified_autoset_lineup.py` - pool sizes + payload autoset + waterfall smoke tests

---

## Auto-Set Lineup Feature

**Canonical algorithm (all callers)**

1. **Eligibility:** `is_player_eligible_for_lineup()` + waterfall (relax NG, then quarter foul limits) until ≥5 players qualify. Fouled out (**F ≥ 5**) always excluded.
2. **Slot rating:** Prefer `position_ratings[pos]`; else trait average from `POSITION_TRAITS[pos]` in `BackEnd/utils/db_utils.py`.
3. **Chemistry pools:** Shuffle PG–C order, then for each fill slot **i** (1–5), take the top **N** by slot rating (`N` from table); if **N > 1**, pick uniformly at random among those **N**.

   | Chemistry | Pos 1 | Pos 2 | Pos 3 | Pos 4 | Pos 5 |
   |-----------|-------|-------|-------|-------|-------|
   | > 20      | 1     | 1     | 1     | 1     | 2     |
   | 16–20     | 1     | 1     | 1     | 1     | 3     |
   | 11–15     | 1     | 1     | 1     | 2     | 3     |
   | ≤ 10      | 1     | 1     | 1     | 3     | 3     |

   TC is capped at 25; unparseable TC defaults to 12.

4. **User lineup screen:** `set-lineup.js` clears slots → `POST /api/autoset-lineup` (roster rows + `game_state` + `team_chemistry`) → refresh UI + toast. `team_chemistry` comes from `GET /roster/...` when franchise/tournament query params are used; otherwise **15**.
5. **Phaser sim (Q2–Q4):** `bootGame.js` → `generateBothLineupsFromApi()` (`autosetLineupApi.js`) — same endpoint; rosters via `fetchTeamRoster()`.
6. **Computer / in-sim:** `build_lineup_from_mongo()`; **gap-fill** after foul-outs: `fill_unified_lineup_gaps()` via `_ensure_complete_lineup()` in `BackEnd/main.py`.

**Partial lineup repair:** When only some slots are empty, pool sizes **N₁, N₂, …** apply to the shuffled **missing** positions only (filled slots are left unchanged).
