## Playcall Center ✅ **ACTIVE** (January 2025)

**Structure**
1. Top Row: Status displays (offense playcall name, defense type + aggression)
2. Controls Strip: `Game Speed`, `Pause`, and `Timeout` buttons in a dedicated row between the court and Playcall Center
3. Left Panel: Offense override (6 plays in slot order, player headshots, navigation buttons, compact red X clear button)
4. Right Panel: Defense override (Man/Zone buttons, Passive/Normal/Aggressive buttons, red X clear buttons for defense and aggression rows)

**Visible UI Notes**
- The large `OFFENSE OVERRIDE` / `DEFENSE OVERRIDE` headers are intentionally hidden in the live court UI because the top-row `OFFENSE:` / `DEFENSE:` labels already provide that context.
- The bottom `Clear Override` button on the defense side is intentionally hidden. Defense overrides are cleared via the red `X` buttons attached to the defense and aggression rows.
- `Skip To End` is no longer rendered in the DOM. The sunset CSS and legacy listener code remain in place for compatibility, but the visible control is gone.
- The offense red `X` is grouped under the up/down navigation arrows instead of appearing as a tall standalone column.
- The lean meter has been removed from the visible Playcall Center layout. No center effectiveness widget is shown on `court.html`.

**Override System Flow (4 Steps)**
1. User Selection (Frontend)
   - User clicks play/defense button in Playcall Center
   - `setPlaycallOverride()` sends POST to `/api/set-playcall-override`
   - Only sends field being changed (not all fields with nulls)

2. API Endpoint (`/api/set-playcall-override`)
   - Receives `game_id`, `user_team_side`, override values
   - Only processes fields explicitly provided in request body
   - Updates `team.strategy_calls` with override values

3. Backend Application (`set_playcalls()` / `set_strategy_calls()`)
   - Called during HCO turn setup
   - Uses `game_state["user_team_side"]` to detect user team
   - Offense override: Applied if `team.strategy_calls["offense_call"] != None` and user on offense → cleared after use
   - Defense override: Applied if `team.strategy_calls["defense_call"] != None` and user on defense → persistent (not cleared)
   - Aggression override: Applied in `set_strategy_calls()` → persistent (not cleared)
   - Tempo override: Applied in `set_strategy_calls()` → cleared after use

4. Frontend Button Highlighting
   - Offense: Un-highlighted when `turnData.offense_override_cleared === true`
   - Defense/Aggression: Remain highlighted until manually cleared (persistent)

**Override Data Structure**
```python
team.strategy_calls = {
    "offense_call": None | str,          # Cleared after one use
    "defense_call": None | str,          # Persistent until manually cleared
    "aggression_override": None | str,   # Persistent until manually cleared
    "tempo_override": None | str,        # Cleared after one use
    "press_override": None,              # Future
    "trap_override": None                # Future
}
```

**Player Headshot Assignment**
1. Set Plays: Extract intended shooter from `play.skeletons.successful` final step (`action == "shoot"`)
2. Motion Plays: Analyze steps 1-10 of `play.skeletons.base_loop` to find most likely shooter per focus
3. Mapping: Map shooter position to player ID from lineup (URL parameters)
4. Image: Set `/static/images/players/{playerId}.png` on page load

**Key Files**
- `FrontEnd/static/court.html`: HTML structure, controls strip, `populatePlayHeadshots()`, `setPlaycallOverride()`
- `FrontEnd/static/js/phaser/ui/playcallCenter.js`: `updatePlaycallCenter()` and playcall panel helpers
- `FrontEnd/static/js/phaser/utils/playcallDisplay.js`: `updatePlaycallDisplay()`
- `BackEnd/api/api.py`: `/api/set-playcall-override` endpoint
- `BackEnd/models/turn_manager.py`: `set_playcalls()`, `set_strategy_calls()`
- `BackEnd/models/team_manager.py`: `TeamManager.__init__()` initializes `strategy_calls`
- `BackEnd/engine/phase_resolution.py`: Calculates `lean_result_value`, embeds in turn text
