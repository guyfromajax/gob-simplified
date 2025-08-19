# Backend Ticket: Add Rebound Fields to Miss Events

## Summary
Shot miss events returned by the backend do not include rebound details. Front-end needs the following fields to properly animate rebounds and track possession:

- `rebounder_player_id` – player ID of the rebounder
- `rebounding_team` – team ID of the rebounder's team
- `rebound_type` – indicates `OREB` or `DREB`

## Request
Update backend miss event payloads to include the fields above. Ensure they are present for both defensive and offensive rebounds and maintain snake_case naming.

## Acceptance Criteria
- Miss event responses include `rebounder_player_id`, `rebounding_team`, and `rebound_type`.
- Existing tests are updated or new tests added to cover these fields.
- Front-end can consume these fields without additional parsing.
