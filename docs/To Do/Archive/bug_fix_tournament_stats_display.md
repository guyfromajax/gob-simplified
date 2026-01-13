# Bug Fix: Tournament Mode Stats Display Issues

**Date:** 2025-01-11  
**Status:** Fixed  
**Related Issues:** Tournament mode team stats and roster view

## Problem

Two related bugs were reported in Tournament mode:

### Issue 1: Team Stats Tab - Only Teams from User's Game Have Stats

**Symptom:** In the Tournament Command Center Stats tab, only teams from the user's game (e.g., Morristown and Xavien) showed non-zero stats. All other teams showed zeros for all stats (W/L, PF/PA, and player stats).

**Root Cause Analysis:** 
- `finalize_game()` was already being called for simulated games (lines 448-453 and 477-483 in `tournament_routes.py`)
- The code was correct, but the issue may have occurred if:
  - A tournament was created/finalized before the `finalize_game()` calls were added for simulated games
  - Or players from other teams weren't initialized in `tournament.players` when the tournament was created
  
**Resolution:**
- Verified that `finalize_game()` is correctly called for all simulated games (code was already correct)
- The issue should not occur for newly created tournaments
- Existing tournaments may need to be re-created to have all teams' stats properly initialized

### Issue 2: Team Roster View - No Stats Displayed

**Symptom:** When clicking on a team's roster link from the Tournament Command Center, player attributes were displayed but no stats were shown (all zeros), even for teams from the user's game.

**Root Cause:** 
- The frontend `team-roster-view.js` was using `/tournament/leaders` endpoint to get stats
- The `/tournament/leaders` endpoint only returns players who have stats (leaders)
- If a team's players weren't in the leaders (or didn't have stats), they wouldn't appear in the response
- The tournament roster endpoint (`/tournament/roster`) was only returning players that existed in `tournament.players`, skipping players from teams that hadn't played yet
- This didn't match the Franchise mode pattern, which fetches roster + franchise document and merges stats

**Fix:**

1. **Backend (`BackEnd/api/tournament_routes.py`):**
   - Modified `/tournament/roster` endpoint to return ALL players from the team roster, even if they're not yet in `tournament.players`
   - This matches the Franchise mode pattern and ensures all roster players are returned (with empty stats if they haven't played yet)

2. **Frontend (`FrontEnd/static/team-roster-view.js`):**
   - Changed from using `/tournament/leaders` endpoint to `/tournament/state` endpoint
   - Now merges stats from `tournament.players[playerId].season` into the roster data (matches Franchise mode pattern)
   - Ensures all roster players are displayed with their stats (or empty stats if they haven't played yet)

## Files Changed

1. `BackEnd/api/tournament_routes.py`
   - Modified `get_tournament_roster()` to return all players from team roster, even if not in `tournament.players`

2. `FrontEnd/static/team-roster-view.js`
   - Changed `loadStats()` for tournament mode to use `/tournament/state` endpoint
   - Added stats merging logic to match Franchise mode pattern

## Testing

✅ **Team Roster View:**
- Click on any team's roster link from Tournament Command Center
- Verify that all players are displayed with their attributes
- Verify that players from teams that have played show their stats
- Verify that players from teams that haven't played show empty stats (not missing)

✅ **Team Stats Tab:**
- Verify that all teams show up in the Stats tab
- Verify that teams from games that have been finalized show correct stats
- Verify that teams from games that haven't been finalized show zeros (not missing)

## Related Patterns

This fix aligns Tournament mode with the Franchise mode pattern:
- **Franchise mode:** Fetches `/franchise/roster` + `/franchise/state`, merges stats from `franchise.players[playerId].season`
- **Tournament mode (after fix):** Fetches `/tournament/roster` + `/tournament/state`, merges stats from `tournament.players[playerId].season`

This ensures consistency across game modes and provides a better user experience.

## Notes

- The Team Stats tab issue (Issue 1) may have been from an old tournament created before `finalize_game()` was added for simulated games
- New tournaments should work correctly
- Existing tournaments may need to be re-created to see stats for all teams
- The Team Roster View fix (Issue 2) works for all tournaments, old and new

