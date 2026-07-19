# Sim Playcalling System

## Overview

The Sim Playcalling System chooses offensive and defensive calls for gameplay turns.

Current architecture:
- Universal offensive plays live in the `plays` collection.
- Team-owned play copies live in mode-specific team documents and carry mutable team data like `effectiveness`, `momentum`, `cloaking`, and `target_shooter`.
- `play_id` is the canonical identity for playbook percentages and offensive Playcall Center order.
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
   - `set_plays`
7. Store the result in `game_state["current_playcall"]`, plus `offense_play_type` and `offense_play_focus`.

## Defensive Selection Flow

1. Check for a user defense override in `strategy_calls["defense_call"]`.
2. If no override, choose Man vs Zone from strategy settings.
3. If Zone is selected, choose the specific zone from `playbook_settings["zone_defense"]`
   (`_select_zone_defense_with_playbook_weights`).
4. If Man is selected, choose the specific man play (Base / Deny / Loose) from
   `playbook_settings["man_defense"]` (`_select_man_defense_with_playbook_weights`) — symmetric to the
   zone picker. Canonical `defense_id`s: `man` (Base) / `man-tight` (Deny) / `man-loose` (Loose).
5. Save the result into `game_state["defense_playcall"]`.

> **First-class man plays (2026-07-19):** Deny/Loose are distinct `defense_id`s with their own
> scouting rows + usage %, and drive the HCO defender posture (`man-tight`→tight, `man-loose`→loose,
> base→normal). Authoritative record: [`integrating_new_d_plays.md`](../projects/integrating_new_d_plays.md).

## Playbook Identity Rules

Offensive playbook persistence now uses `play_id` keys:

```python
playbook_settings = {
    "motion": {play_id: percentage},
    "set_plays": {play_id: percentage},
    "man_defense": {"man_normal": percentage, "man_tight": percentage, "man_loose": percentage},
    "zone_defense": {"zone_23": percentage, "zone_32": percentage, "zone_131": percentage},
    "fast_breaks": {play_id_or_fb_key: percentage},
    "pc_order": {
        "offense": [play_id, ...],
        "defense": ["Man", "2-3 Zone", ...]
    }
}
```

The five weighted sections (`motion`, `set_plays`, `man_defense`, `zone_defense`, `fast_breaks`) are the same set normalized/validated in `gameplan_routes.py`. Defensive selection reads `zone_defense` (canonical keys `zone_23` / `zone_32` / `zone_131`); `pc_order.defense` carries display-name order only.

Compatibility behavior:
- Runtime still tolerates old name-keyed percentage maps.
- Runtime still tolerates split set-play maps and legacy `slot_assignments`.
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
- Franchise (live mode): franchise team data / active game team object
- Single Game *(sunset)*: game doc team object, with core-team fallback where applicable
- Tournament *(sunset)*: tournament team object

> Single Game and Tournament are sunset modes (not user-facing); their storage branches remain only while the code does. See `01_Game_Mode_Systems/Sunset_Modes.md`.

## Rename Safety Status

Current rename-safe areas:
- offensive playbook percentages
- offensive Playcall Center ordering (`pc_order.offense`)
- most play-selection weighting paths

Still compatibility-based rather than fully canonical:
- some team `plays` maps are still stored name-keyed
- user offense overrides still arrive as display names

## Key Files

- `BackEnd/models/turn_manager.py`
- `BackEnd/api/gameplan_routes.py`
- `BackEnd/utils/playbook_settings_utils.py`
- `BackEnd/utils/team_play_utils.py`
