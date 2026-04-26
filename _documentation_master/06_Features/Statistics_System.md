# Statistics System

## Play Identity Update

Play statistics are now treated as `play_id`-first at the logic layer, with `name` remaining display text.

Current behavior:
- gameplay and training summary code carry `play_id` alongside play display name
- season stat rollups write to the actual stored team-play key
- runtime can still tolerate legacy name-keyed team `plays` maps

Implication:
- play renames should no longer break the main stat aggregation paths that were updated during the playbooks migration

## Training Report / Playbook Summary

Training report play deltas now resolve against `play_id`.

The report payload includes:
- `plays_data`
- `plays_effectiveness_changes`

`plays_effectiveness_changes` is keyed by `play_id` when available.
The frontend resolves those deltas against each play row using `play_id` first and display name only as fallback.

## DREB / OREB Putback Fix

The rebound fix remains in place:
- putback-miss rebounds are recorded on the canonical roster player instance
- rebound persistence uses the normalized player identity path

This fix is independent of the play identity migration.

## Scope

This feature doc is only the migration-specific supplement.
For broader gameplay stat rules, see:
- `docs/docs_1_systems/00_General_Systems/Statistics_System.md`
