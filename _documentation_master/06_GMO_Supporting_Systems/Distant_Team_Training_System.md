# Distant Team Training System

## Overview

Distant training applies to all non-user franchise teams when the user runs training.

Primary file:
- `BackEnd/api/franchise_routes.py`

Template source:
- `distant_training` collection

## What Distant Training Updates

Distant training currently updates:
- team attributes on FTD
- player attributes on FPD
- player position ratings after attribute changes
- optional `pending_community_engagement`

## What Distant Training Does Not Update

Distant training does **not** currently update:
- offensive play effectiveness
- defensive set effectiveness
- team `plays` data
- team `scouting_data`
- training reports for CPU teams

That means the play-effectiveness training system is currently user-team only.

## Flow

1. Load the correct distant template set for the training type.
2. Iterate all franchise teams except the user team.
3. Skip eliminated EOS tournament teams when applicable.
4. Apply template `team_values` to `team_attributes` with clamps.
5. Apply template `players.player_{i}` deltas to each ordered roster player with clamps.
6. Recompute position ratings for affected players.
7. Optionally set `pending_community_engagement`.

## Ordering Rules

- Team order follows FTD query order.
- Player order follows the FTD `players` array.
- If the FTD `players` array is missing, fallback uses the core team roster order.

## Relation to Playbooks Migration

The recent playbook / `play_id` migration does not materially change distant training behavior because CPU distant training still does not modify play effectiveness or playbook settings.
