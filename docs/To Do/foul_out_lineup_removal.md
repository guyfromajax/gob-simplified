# Foul Out Player Lineup Removal

## Issue
The foul out functionality is not currently removing fouled-out players from the lineup in the game experience.

## Expected Behavior
When a player fouls out:
- The fouled-out player should be removed from the current lineup
- If the fouled-out player is on the user's team, they should be removed from the active lineup display upon Lineup Screen page download
- The lineup should be updated to reflect the player's removal

## Current Status
**Not Implemented** - This functionality is documented in `NAVIGATION_DATA_REQUIREMENTS.md` (Bucket 3 - Foul Out special case) but is not currently working in the game experience.

## Related Documentation
- `docs/Core_System_Docs/NAVIGATION_DATA_REQUIREMENTS.md` - Bucket 3, Special Cases, Foul Out section
- Lineup State notes: "fouled out players will be removed from the current lineup at the start of player foul out instances. If the foul out player is on the user's team, he will be removed from the active lineup display upon Lineup Screen page download"

## Implementation Notes
- This should occur when transitioning from gameplay to Lineup screen after a foul out
- The foul out popup should trigger this removal
- Backend should update the lineup data to exclude the fouled-out player
- Frontend should reflect this change in the Lineup Screen display

