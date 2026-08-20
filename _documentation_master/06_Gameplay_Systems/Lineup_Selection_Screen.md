## Lineup Selection Screen ✅ **COMPLETE** (January 2025; re-verified against code June 2026; timeout-read redesign Aug 2026)

**Base Constants**

1. **Positions**: PG, SG, SF, PF, C (5 positions)
2. **Fouled Out**: Players with 5+ fouls always excluded (applies to both manual and auto-set)
3. **Foul Trouble (display)**: F ≥ 3 on live gameplay surfaces (Set Lineup header / foul cells, court sim presentation)
4. **Auto-Set Only - Energy Thresholds**: Default NG >= 80%, Late Q4/OT NG >= 64%
5. **Auto-Set Only - Foul Restrictions**: Q1 (>1), Q2 (>2), Q3 (>3), Q4 (>3 if >4min remaining), OT (none, but 5+ excluded)

---

## Lineup Selection Screen Overview

**Lineup Selection Screen Flow (4 Steps)**

1. **Load Roster Data** - Fetch from mode-specific endpoint, merge game data if `gameId` exists
2. **Display Player Information** - Game / Attributes / Stats views in one table; on-court five grouped above bench
3. **Set Lineup** - Click or drag within the table (including empty on-court placeholder rows), real-time validation
4. **Save and Navigate** - Lineup saved to URL parameters, navigate to Game Plan/Box Score/Gameplay

**Long Form Documentation**

### Overview

The Lineup Selection Screen allows users to set their starting lineup before each game and during timeouts. The right-hand Starting Five cards were removed: the roster table is the lineup UI. Default view is **Game**.

**Key Features:**
- `Game | Attributes | Stats` segmented views (Game default)
- On-court (5) + Bench groups; empty slots as placeholder rows in PG→C order; BENCH group header only (no ON COURT header)
- ENG bar + RT beside the player name in all views (existing 90/80/70 energy bands)
- Game view production cluster: PTS · REB (DREB+OREB) · AST · DEF% between ENG and RT
- MO as −5…+5 pip ladder (red left / white right) in Game view
- Header reads (in-game only, current five): AVG ENG, BELOW 70%, FOUL TROUBLE (F≥3)
- Right rail: Playbook + Play Call Center shot-weight charts; Autoset / Game Plan / Playbooks bottom-anchored
- Game table max-width ~1180px (production gaps absorb surplus; energy bar stays fixed ~104px)

### Data Sources

**Backend:**
- **Roster API**: ✅ UNIFIED endpoint `/roster/{team_name}` with query parameters (`?franchise_id={id}` or `?tournament_id={id}`) for all modes
- **Game API** (`/api/game/{gameId}`): Returns player stats (including F = fouls), attributes (EM, MO, CH, NG)
- **Playbooks API** (`/api/playbooks`): `position_shot_weights.playbooks` + `position_shot_weights.playcall_center`

**Frontend:**
- `FrontEnd/static/set-lineup.html` / `set-lineup.js` / `set-lineup.css`
- `loadRoster()`, `renderRoster()`, `autosetLineup()` → `POST /api/autoset-lineup`

### Player Stats and Attributes Display

**Shared leading columns (all views):** POS · headshot · PLAYER · ENG · RT
- On-court POS = assigned slot; bench POS = highest-rated position
- On-court RT = that slot’s `position_ratings[pos]`; bench RT = highest rating
- ENG uses existing bands: ≥90 green, 80–89 yellow, 70–79 orange, &lt;70 red (bar fill; number is white opacity only)

**Game view:** ENG · PTS/REB/AST/DEF% · RT · F · MIN · MO (pips). Production numerals always show (including zeros).
**Attributes:** HT WT SC SH ID OD PS BH RB ST AG ND IQ FT (NG relocated into ENG; trailing RT relocated)
**Stats:** existing box-score columns unchanged after the shared prefix

**NG color bands (bars):** Red &lt;70%, Orange 70–80%, Yellow 80–89%, Green 90–100%.

**Momentum:** integer −5…+5; table pips fill outward from center; negative = brand red, positive = white.

### Player Eligibility Filtering (Fouled Out)

**How it works:** Each time the user enters the lineup screen (pre-game, after a timeout, after a quarter break), the screen fetches game data when `gameId` is present. When merging that game data into the roster, any player whose **game foul count (F) is ≥ 5** is marked ineligible (fouled out).

**FT shooter lock:** designated free-throw shooter cannot be removed (✕ hidden; badge on row); reorder via drag still allowed.

**Manual selection:** Fouled-out players cannot be added. Click bench → fill next empty PG→C slot. Drag onto an on-court row (including empty placeholder) assigns that slot / swaps.

### Key Files

**Frontend:**
- `FrontEnd/static/set-lineup.html` - Page structure
- `FrontEnd/static/set-lineup.js` - `loadRoster()`, `autosetLineup()` → `POST /api/autoset-lineup`, `renderRoster()`, `updatePlayButton()`
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

> **FT shooter safeguard:** when a free throw is pending and the designated shooter is on this team, `build_lineup_from_mongo()` force-includes them (`force_include_ids` → seated into their best open slot first) so autoset never benches the player owed free throws. See `Timeout_System.md` § Designated Free Throw Shooter Lock.

**Canonical algorithm (all callers)**

1. **Eligibility:** `is_player_eligible_for_lineup()` + waterfall (relax NG, then quarter foul limits) until ≥5 players qualify. Fouled out (**F ≥ 5**) always excluded.
2. **Slot rating:** Prefer `position_ratings[pos]`; else trait average from `POSITION_TRAITS[pos]` in `BackEnd/utils/db_utils.py`.
3. **Chemistry pools:** Shuffle PG–C order, then for each fill slot **i** (1–5), take the top **N** by slot rating (`N` from table); if **N > 1**, pick uniformly at random among those **N**.

   | Chemistry | Pos 1 | Pos 2 | Pos 3 | Pos 4 | Pos 5 |
   |-----------|-------|-------|-------|-------|-------|
   | > 15      | 1     | 1     | 1     | 1     | 2     |
   | ≤ 15      | 1     | 1     | 1     | 1     | 3     |

   TC is capped at 25; unparseable TC defaults to 12.

4. **User lineup screen:** `set-lineup.js` clears slots → `POST /api/autoset-lineup` (roster rows + `game_state` + `team_chemistry`) → refresh UI + toast. `team_chemistry` comes from `GET /roster/...` when franchise/tournament query params are used; otherwise **15**.
5. **Phaser sim (Q2–Q4):** `bootGame.js` → `generateBothLineupsFromApi()` (`autosetLineupApi.js`) — same endpoint; rosters via `fetchTeamRoster()`.
6. **Computer / in-sim:** `build_lineup_from_mongo()`; **gap-fill** after foul-outs: `fill_unified_lineup_gaps()` via `_ensure_complete_lineup()` in `BackEnd/main.py`.

**Partial lineup repair:** When only some slots are empty, pool sizes **N₁, N₂, …** apply to the shuffled **missing** positions only (filled slots are left unchanged).
