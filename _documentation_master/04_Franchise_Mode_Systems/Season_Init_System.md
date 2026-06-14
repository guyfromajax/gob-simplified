# Season Init System (**verified 2026-06-13**)

This document covers the start of a new season inside an existing franchise instance.

> Verified vs code — accurate. Coaching-focus carryover confirmed: `carryover_coaching_focus_counts_for_new_season` (`franchise_coaching_focus_counts.py`, `_COACHING_FOCUS_SEASON_CARRYOVER_RATIO = 0.25` → 75% reduction, int-rounded, 4 archetypes) is called by `finish_season` (`franchise_routes.py:12264`) when writing the next-season FTD row; week-1 training-camp weight `random.randint(2, 4)` (else 1) confirmed. Remaining content is intentionally high-level (what persists/resets) and drift-resistant. Team play-copy field list owned by `Mode_Init_System.md`.

> **Related init docs (init family):** `Mode_Init_System.md` (owner of the `initialize_playbook_settings` shape + team play-copy fields), `../05_GP_Supporting_Systems/Game_Init_System.md` (per-game init), `../05_GP_Supporting_Systems/Computer_Team_Game_Init_System.md` (TeamManager strategy defaults). This doc owns the **new-season rollover** rules (what persists / resets).

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
- team play copies **persist across the season** and continue to carry their identity fields (`play_id`, `name`, `play_type`, `play_focus`, `target_shooter`) — full field list owned by `Mode_Init_System.md` → Team Play Initialization

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
