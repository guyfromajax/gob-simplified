

1. Playcall Override During Opening Tip Sequence -- When a user selects a playcall override during the opening tip sequence (before the game is initialized), the play is highlighted in the playcall center UI but the override never reaches the backend. The frontend `setPlaycallOverride()` function blocks the API call because `game_id` is `null` at that point (the game hasn't been created yet via `/api/simulate-quarter`). The override only works after the first turn is simulated and `game_id` becomes available. **Solution:** Either queue the override and send it after game initialization, or defer the `game_id` check until the first turn is simulated.
2. Defensive Foul on missed shot attempt not announcing via our Announcement System

## Fixed Bugs (January 2025)

✅ **Tournament Command Center Stats Bugs** (Fixed: January 2025)
- **Totals showing "undefined"**: Fixed missing W/L initialization in totals object
- **Player stats not populating on Roster tab**: Fixed by ensuring `loadRoster()` is called after tournament updates
- **Team stats container scroll issue**: Fixed by removing `scroll-x` wrapper and using inline overflow styling
- **Note**: Computer teams showing 2 games is a backend issue (likely double finalization) - needs backend investigation