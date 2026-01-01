# Backend Ticket: Add Rebound Fields to Miss Events

## Status: ⚠️ **PARTIALLY IMPLEMENTED**

## Summary
Shot miss events returned by the backend do not include complete rebound details. Front-end needs the following fields to properly animate rebounds and track possession:

- `rebounder_player_id` – player ID of the rebounder
- `rebounding_team` – team ID of the rebounder's team
- `rebound_type` – indicates `OREB` or `DREB`

## Current Implementation Status

### ✅ **Implemented:**
- `rebound_type` – Present in all miss event results (e.g., `shot_manager.py:850`, `turn_manager.py:2318`)
- `rebounderId` – Present in miss event results (using `player_id` attribute)

### ⚠️ **Partially Implemented:**
- `rebounder_player_id` – Frontend uses this as fallback to `rebounderId` (see `turnAnimation.js`, `fastBreak.js`, `freeThrow.js`), but backend primarily uses `rebounderId`

### ❌ **Not Implemented:**
- `rebounding_team` – **Missing from backend**. Only exists in TypeScript types (`types.d.ts`) but not populated in actual results.

## Request
Update backend miss event payloads to include the missing `rebounding_team` field. Ensure all three fields are consistently present for both defensive and offensive rebounds and maintain snake_case naming.

## Acceptance Criteria
- ✅ Miss event responses include `rebound_type` (DONE)
- ✅ Miss event responses include `rebounderId` (DONE, though frontend expects `rebounder_player_id` as well)
- ❌ Miss event responses include `rebounding_team` (NOT DONE)
- Existing tests are updated or new tests added to cover these fields.
- Front-end can consume these fields without additional parsing.

## Notes
- Frontend code already handles `rebounder_player_id` as a fallback to `rebounderId`, so backend could standardize on one field name
- `rebounding_team` would be useful for frontend to determine which team secured the rebound without parsing player IDs
