# Sim Playcalling System

## Overview

The Sim Playcalling System chooses offensive and defensive calls for gameplay turns.

Current architecture:
- Universal offensive plays live in the `plays` collection.
- Team-owned play copies live in mode-specific team documents and carry mutable team data like `effectiveness`, `momentum`, `cloaking`, and `target_shooter`.
- `play_id` is the canonical identity for playbook percentages and slot assignments.
- `name` is display text and compatibility fallback only.

Primary runtime file:
- `BackEnd/models/turn_manager.py`

Supporting files:
- `BackEnd/api/gameplan_routes.py`
- `BackEnd/utils/playbook_settings_utils.py`
- `BackEnd/utils/team_play_utils.py`

## Offensive Selection Flow

1. Check for a user offense override in `strategy_calls["offense_call"]`.
2. If present, resolve the play by name, look up the team-owned play copy, and load the universal play doc by `play_id`.
3. If no override, choose `motion` vs `set_play` from `strategy_settings["offense"]`.
4. If `set_play`, choose focus from `inside` / `attack` / `outside`.
5. Query matching universal plays.
6. Weight candidate plays using `playbook_settings`:
   - `motion`
   - `set_play_inside`
   - `set_play_attack`
   - `set_play_outside`
7. Store the result in `game_state["current_playcall"]`, plus `offense_play_type` and `offense_play_focus`.

## Defensive Selection Flow

1. Check for a user defense override in `strategy_calls["defense_call"]`.
2. If no override, choose Man vs Zone from strategy settings.
3. If Zone is selected, choose the specific zone from `playbook_settings["zone_defense"]`.
4. Save the result into `game_state["defense_playcall"]`.

## Playbook Identity Rules

Offensive playbook persistence now uses `play_id` keys:

```python
playbook_settings = {
    "motion": {play_id: percentage},
    "set_play_inside": {play_id: percentage},
    "set_play_attack": {play_id: percentage},
    "set_play_outside": {play_id: percentage},
    "slot_assignments": {
        "1": {"section": "motion", "playId": play_id, "playName": display_name}
    },
    "motion_dropdowns": {play_id: "inside|attack|outside|-"}
}
```

Compatibility behavior:
- Runtime still tolerates old name-keyed percentage maps.
- Runtime still tolerates name-based `slot_assignments`.
- Resolution prefers `play_id` first, then falls back to `name`.

## Team-Owned Play Copies

Team play copies currently store:

```python
plays[storage_key] = {
    "play_id": "mongo_object_id_as_string",
    "name": "display name",
    "play_type": "motion|set_play",
    "play_focus": "inside|attack|outside|None",
    "target_shooter": "PG|SG|SF|PF|C|None",
    "effectiveness": int,
    "momentum": int,
    "cloaking": int,
    "game_stats": {...},
    "season_stats": {...}
}
```

Notes:
- Some stored team docs are still keyed by play name.
- Runtime helpers in `team_play_utils.py` support both name-keyed and `play_id`-keyed team `plays` maps.

## CPU vs User Teams

- User teams use saved playbook weights when available.
- CPU teams still use equal-weight fallback selection unless they are explicitly reading stored playbook settings in the same mode context.
- All teams still use the same universal play library.

## User Overrides

Playcall Center offense overrides still send play names because gameplay call text is name-based.

That is acceptable because:
- override selection is a UI interaction
- backend resolves the selected display name to the team-owned play copy
- all persistent weighting and slot logic is now `play_id`-based

## Mode Storage

`playbook_settings` is stored in mode-specific team state:
- Single Game: game doc team object, with core-team fallback where applicable
- Tournament: tournament team object
- Franchise: franchise team data / active game team object

## Rename Safety Status

Current rename-safe areas:
- offensive playbook percentages
- slot assignments
- motion dropdowns
- most play-selection weighting paths

Still compatibility-based rather than fully canonical:
- some team `plays` maps are still stored name-keyed
- user offense overrides still arrive as display names

## Key Files

- `BackEnd/models/turn_manager.py`
- `BackEnd/api/gameplan_routes.py`
- `BackEnd/utils/playbook_settings_utils.py`
- `BackEnd/utils/team_play_utils.py`
