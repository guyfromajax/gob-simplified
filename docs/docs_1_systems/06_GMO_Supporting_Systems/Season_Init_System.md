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

## Coaching focus counters (`coaching_focus` on FTD)

- **`training_reports`** are cleared for the new season, but **`coaching_focus`** archetype totals are **carried over** with a **75% reduction**: each of `authoritarian`, `systems_coach`, `player_maximizer`, `culture_builder` becomes **`int(round(old_value × 0.25))`** when `finish_season` writes the next-season FTD row (see `carryover_coaching_focus_counts_for_new_season` in `BackEnd/utils/franchise_coaching_focus_counts.py`).
- During **week 1 training camp** (first training before any `results["1"]`), new increments use weight **`random.randint(2, 4)`** per submit instead of `+1`. Full detail: `Training_System.md` → Data Storage → FTD `coaching_focus`.

## Rename / Identity Note

Because the current rollout moved playbook settings to `play_id`, season-init continuity should treat:
- `play_id` as stable identity
- `name` as mutable display text

Any future season-init rebuild of playbook settings should preserve `play_id` keys.
