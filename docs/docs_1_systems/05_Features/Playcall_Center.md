## Playcall Center ✅ **ACTIVE** (March 2025)

In-game tactical hub at the bottom of the court. User overrides apply only to the **user's team**; stack button highlights sync only when the call belongs to the user's team.

---

### Structure

**Status row** (`#playcall-status-row`)
- Left: `OFFENSE` label + current offensive playcall name (`#offense-status-text`)
- Right: current defense type + aggression (`#defense-status-text`) + `DEFENSE` label

**Main row** (`#playcall-main-row`) — three zones, no gap:
- **Offense Card Zone (33%)** — `.pcc-card-zone`
  - Single **play card** (`.pcc-play-card`) showing one play at a time: player headshot (`.play-headshot`), play name (`.play-name`), play focus (`.play-focus`) inside `#offense-play-scroller` with multiple `.play-option` items (one visible).
  - **Nav column** (`.pcc-nav-col`): ▲ (`#play-nav-up`), ▼ (`#play-nav-down`), ✕ (`#clear-offense-override-x`).
  - **Behavior**: ▲/▼ scroll through slots (browse only). **Click** the visible play option to **select** it (highlight + send override). ✕ clears offense override.

- **Stacks Zone (34%)** — `#pcc-stacks-zone`
  - Three equal vertical stacks with group labels and red ✕ at bottom:
    - **Tempo**: Fast / Normal / Slow — IDs `#tempo-fast`, `#tempo-normal`, `#tempo-slow`, `#clear-tempo-x`
    - **Aggression**: Passive / Normal / Aggr — IDs `#aggr-passive`, `#aggr-normal`, `#aggr-aggressive`, `#clear-aggression-override-x`
    - **Press/Trap**: Press / Trap / None — IDs `#press-btn`, `#trap-btn`, `#press-trap-none-btn`, `#clear-press-trap-x`
  - **Behavior**: Click a stack button to select (highlight + send override). ✕ clears that stack’s override. Stack highlights are synced from turn data **only when the call belongs to the user’s team** (tempo when user on offense, aggression and press/trap when user on defense).

- **Defense Card Zone (33%)** — `.pcc-card-zone.defense-zone`
  - **Nav column** (left): ▲ (`#defense-nav-up`), ▼ (`#defense-nav-down`), ✕ (`#clear-defense-card-x`).
  - **Play card** with scheme name only (`.defense-play-name`). Schemes in order: **Man Normal**, 2-3 Zone, 3-2 Zone, 1-3-1 Zone.
  - **Behavior**: ▲/▼ **browse** schemes (no highlight, no API). **Click the defense card** to **select** the currently displayed scheme (highlight + send override). ✕ resets to Man Normal, clears defense and aggression overrides, unhighlights. **Starts unhighlighted**; game uses default defense until user selects a scheme.

**Container**
- `#playcall-center` dimensions (max-height, min-height, padding, positioning) are fixed; all layout fits within that footprint. Game controls strip lives inside the court container below the canvas, not in the Playcall Center.

---

### Override system flow

1. **User selection (frontend)**
   - Offense: click a visible play option (after scrolling with ▲/▼ if desired). Defense: scroll with ▲/▼ then **click the defense card**. Stacks: click a stack button.
   - `setPlaycallOverride(type, value)` in `court.html` sends POST to `/api/set-playcall-override` with only the field being changed (`offense_override`, `defense_override`, `aggression_override`, `tempo_override`, or `press_trap_override`). `value === null` clears that override.

2. **API** (`/api/set-playcall-override`)
   - Request: `game_id`, `user_team_side`, and any of: `offense_override`, `defense_override`, `aggression_override`, `tempo_override`, `press_trap_override`.
   - Only processes fields present in the request. Updates `user_team.strategy_calls` accordingly. Clearing: sending `null` for a field clears that override (e.g. `tempo_override: null`).

3. **Backend application**
   - **Offense**: Applied when user’s team is on offense; cleared after one use.
   - **Defense**: Applied when user’s team is on defense; persistent until user clears. API accepts full names (e.g. "2-3 Zone"); "Man Normal" is sent as `"Man"` for backend compatibility.
   - **Aggression**: Applied in `set_strategy_calls()` when user’s team is on defense; persistent until cleared.
   - **Tempo**: Applied in `set_strategy_calls()` when user’s team is on offense; cleared after one use.
   - **Press/Trap**: Read in `determine_defensive_pressure_type()` when user’s team is applying pressure (after a made shot). `"press"` → FCP, `"trap"` → HCT, `"none"` → HCO; otherwise falls back to `strategy_settings` (hc_trap / fc_press).

4. **Frontend highlighting**
   - **Offense**: `.play-option.selected` on the chosen play; cleared when `turnData.offense_override_cleared === true` or when user clicks ✕.
   - **Defense**: `.pcc-play-card.selected` on the defense card only when the user has explicitly selected a scheme (click card). Unhighlighted on load and after ✕ or `clearPlaycallOverrides()`.
   - **Stacks**: `.pcc-stack-btn.selected` synced from turn data **only when the call is for the user’s team** (tempo when user on offense; aggression and press_trap when user on defense). Prevents computer team’s calls from driving the user’s stack highlights.

---

### Override data structure

```python
team.strategy_calls = {
    "offense_call": None | str,           # Play name; cleared after one use
    "defense_call": None | str,           # "Man", "2-3 Zone", "3-2 Zone", "1-3-1 Zone"; persistent
    "aggression_override": None | str,   # "passive", "normal", "aggressive"; persistent
    "tempo_override": None | str,         # "slow", "normal", "fast"; cleared after one use
    "press_trap_override": None | str,   # "press", "trap", "none"; persistent until cleared
    "press_override": None,               # Legacy
    "trap_override": None                # Legacy
}
```

---

### Player headshot assignment (offense card)

- Set plays: intended shooter from `play.skeletons.successful` final step (`action == "shoot"`).
- Motion plays: analyze steps 1–10 of `play.skeletons.base_loop` for most likely shooter per focus.
- Map shooter position to player ID from lineup (URL). Set headshot on page load via `populatePlayHeadshots()` in `court.html`.

---

### Clear behavior

- **Offense ✕**: Clears offense override and all offense play `.selected`.
- **Stack ✕**: Clears that stack’s override and deselects its buttons.
- **Defense ✕**: Resets to Man Normal, clears defense and aggression overrides, unhighlights defense card, deselects aggression stack buttons.
- **`window.clearPlaycallOverrides()`**: Clears all play and stack selections, resets defense to unhighlighted Man Normal (no override). Used when overrides are consumed or reset elsewhere.

---

### Key files

- **`FrontEnd/static/court.html`**: Playcall Center HTML (`#playcall-center`, status row, main row, offense card, stacks zone, defense card), CSS (`.pcc-*`, `.play-option`, `.play-headshot`, etc.), `initPlaycallCenter()` (all button/card handlers), `setPlaycallOverride()`, `populatePlayHeadshots()`, slot-based play navigation (▲/▼, `showPlay()`).
- **`FrontEnd/static/js/phaser/ui/playcallCenter.js`**: `updatePlaycallCenter(turnData, homeTeamId)` — status row text, stack button sync (only when call is user’s team), playcall reveal HUD trigger. `clearPlaycallHighlights()` — clears `.play-option.selected` and stack `.pcc-stack-btn.selected`.
- **`FrontEnd/static/js/phaser/utils/playcallDisplay.js`**: Scoreboard playcall display (separate from Playcall Center panels).
- **`BackEnd/api/api.py`**: `PlaycallOverrideRequest` (includes `press_trap_override`), `/api/set-playcall-override` handler (set/clear all override types).
- **`BackEnd/models/turn_manager.py`**: `set_strategy_calls()` / `set_playcalls()` — applies offense, defense, tempo, aggression from strategy_calls. `determine_defensive_pressure_type()` — applies user `press_trap_override` when user’s team is applying pressure.
- **`BackEnd/models/team_manager.py`**: `strategy_calls` default keys including `press_trap_override`.
