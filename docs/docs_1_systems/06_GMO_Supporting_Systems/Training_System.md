## Training System

## Overview

Training updates:
- player attributes
- team attributes
- offensive play effectiveness
- defensive set effectiveness
- training report payloads

Primary execution file:
- `BackEnd/models/training_execution_v2.py`

Primary franchise route:
- `BackEnd/api/franchise_routes.py`

Training report frontend:
- `FrontEnd/static/training-report.js`

## User Team Training

User-team franchise training updates:
- `plays_data`
- `scouting_data`
- `training_report`

Play-effectiveness flow:
1. Load team-owned `plays_data`.
2. Capture original offensive play effectiveness.
3. Apply pre-training effectiveness decay when applicable.
4. Apply install-based play effectiveness gains.
5. Emit `plays_effectiveness_changes`.

## Play Identity in Training

Training report play deltas now use `play_id` as the canonical key when available.

Current report payload fields:

```python
training_report = {
    "plays_data": updated_plays,
    "scouting_data": updated_scouting_data,
    "plays_effectiveness_changes": {play_id: delta},
    "defenses_effectiveness_changes": {defense_name: delta}
}
```

Frontend rules:
- Training Report resolves offensive deltas by `play_id` first
- display still uses `name`

## Playbook Training Mode

Offense install distribution still depends on:
- `playbook_training_mode`
- `strategy_settings`
- `playbook_settings`

Important migration note:
- offensive `playbook_settings` maps are now `play_id`-keyed
- runtime compatibility still tolerates older name-keyed maps

## Training Report

The Training Report page now expects:
- `plays_data` entries carrying `play_id`
- `plays_effectiveness_changes` keyed by `play_id`

The offensive Playbook Summary section:
- renders play display names from `plays_data`
- resolves Command deltas from `plays_effectiveness_changes`

## Distant Training

CPU distant training does not currently update:
- offensive play effectiveness
- defensive set effectiveness

That behavior is separate from user-team training.

## Community Engagement

Community Engagement still affects:
- immediate EM adjustment
- pending home-crowd modifier state

It does not interact with the `play_id` / `target_shooter` migration directly.
