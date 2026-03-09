# Season Init System

This document covers the start of a new season inside an existing Franchise instance. This is distinct from `Mode_Init_System.md`, which covers brand new mode-instance creation.

## Scope

- Applies only when a user finishes week 36 and presses `Go To Next Season`.
- Does not touch the universal `players` or `teams` collections.
- Rebuilds the next season entirely from persisted franchise-instance data.

## High-Level Flow

1. Read the current franchise instance state from:
   - `franchises`
   - `franchise_team_data`
   - `franchise_players_data`
   - `franchise_recruits_data`
2. Remove graduating seniors from the franchise instance.
3. Carry all returning players forward into the next season.
4. Add signed recruits and walk-ons produced by week 35 recruiting.
5. Reset season-level state.
6. Generate the next season's recruits and schedule.

## Player Continuity

- Returning players keep their existing franchise `player_id`.
- Signed recruits and walk-ons receive new franchise-scoped UUID player ids.
- Player `career` stats persist.
- Player `season` stats reset to zero for the new season.
- Player years advance:
  - Freshman -> Sophomore
  - Sophomore -> Junior
  - Junior -> Senior
  - Seniors / Graduates are removed from the franchise instance

## Roster Rebuild

For each franchise team:

1. Start with all returning non-graduating players.
2. Add all week-35 signed recruits.
3. Add any generated walk-ons needed to reach 15 total roster players.
4. Build scholarship state:
   - keep all returning scholarship players except graduates
   - add signed recruits who accepted scholarship offers
   - hard cap = 12
   - if the cap is somehow exceeded, remove scholarship from the lowest-RT freshman scholarship player
5. Build active roster / training squad state:
   - active group = scholarship players first
   - if active group is below 12, add highest-RT non-scholarship players until it reaches 12
   - remaining players go to `training_squad_players`
   - `training_squad_players` may contain 0-3 player ids

## Team Fields Reset

Each FTD doc is reset for the new season:

- `Recruits` -> keys `"1"` through `"20"` set to `None`
- `recruiting_orders_week_35` -> `{}`
- `recruit_visit` -> `None`
- `training_reports` -> `{}`
- `playing_time_promise_players` -> signed freshmen who accepted a PT promise
- `scholarship_players` -> current scholarship player ids
- `training_squad_players` -> current training-squad player ids

## Franchise Fields Reset

On next-season init:

- `current_season` increments by 1
- `week` resets to `1`
- EOS bracket state clears
- `recruiting_results` clears
- `recruiting_lean_updates_applied` clears
- `week_35_recruiting_ran` resets to `False`
- `week_35_recruiting_results` clears
- `awards` clears
- training status resets to preseason
- current-season game docs tied to the franchise are deleted

## New Recruit Generation

After the prior season closes:

- delete the prior season's `franchise_recruits_data` docs
- generate 200 fresh recruits
- assign each recruit:
  - new `recruit_id`
  - `Home Region`
  - `Lean`

## Schedule Generation

- Generate a fresh 26-week regular-season schedule for the new season.
- This is the franchise-instance continuation schedule, not a new franchise bootstrap.

## SS&S Rules

- New franchise instance init may use universal data.
- New season init inside an existing franchise must not.
- Franchise continuity is preserved through FTD/FPD/FRD state only.
