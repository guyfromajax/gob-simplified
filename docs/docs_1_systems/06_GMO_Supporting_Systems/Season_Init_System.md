# Season Init System

This document covers the start of a new season inside an existing franchise instance.

## Scope

Season init rebuilds the next season from franchise-instance persistence only.

It does not:
- read universal player progression as source of truth
- rebuild team playbooks from scratch in a way that drops franchise state

## Play / Playbook Relevance

For the current playbook migration, the important season-init rules are:

- team-owned `plays` remain franchise-instance state
- `training_reports` reset each season
- playbook settings persist as franchise-instance team state unless explicitly rebuilt
- team play copies continue to carry:
  - `play_id`
  - `name`
  - `play_type`
  - `play_focus`
  - `target_shooter`

## Fields Reset

Season init resets:
- `training_reports`
- recruiting state
- season-progress fields
- current-season game docs

Season init does not intentionally wipe:
- the franchise team’s play library metadata
- the team’s playbook identity model

## Rename / Identity Note

Because the current rollout moved playbook settings to `play_id`, season-init continuity should treat:
- `play_id` as stable identity
- `name` as mutable display text

Any future season-init rebuild of playbook settings should preserve `play_id` keys.
