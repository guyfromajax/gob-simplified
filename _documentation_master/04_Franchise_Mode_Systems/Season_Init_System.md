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
- **`team_attributes`** — re-rolled, not carried over: the 8 core attrs re-roll on a range scaled by roster carryover; other fields re-init like franchise creation (see `Team_Attribute_System.md` → § Season Rollover Re-Roll).

Season init does not intentionally wipe:
- the franchise team’s play library metadata
- the team’s playbook identity model

## Coaching focus counters (`coaching_focus` on FTD)

- **`training_reports`** are cleared for the new season, but **`coaching_focus`** archetype totals are **carried over** with a **75% reduction**: each of `authoritarian`, `systems_coach`, `player_maximizer`, `culture_builder` becomes **`int(round(old_value × 0.25))`** when `finish_season` writes the next-season FTD row (see `carryover_coaching_focus_counts_for_new_season` in `BackEnd/utils/franchise_coaching_focus_counts.py`).
- During **week 1 training camp** (first training before any `results["1"]`), new increments use weight **`random.randint(2, 4)`** per submit instead of `+1`. Full detail: `Training_System.md` → Data Storage → FTD `coaching_focus`.

## Walk-On Announcement

Two surfaces, one data shape. Both are written when the walk-ons are created, never derived later.

| Surface | Seasons | Written by |
|---|---|---|
| **"\<Team\> Walk Ons Announced"** news story | **1 and up** | `FranchiseManager.initialize_season` (S1) / `finish_season` (S2+) |
| **Walk-On Welcome modal** | **2 and up** | `finish_season` only |

Season 1 gets the story but not the modal — the first-time-experience flow owns that landing.

Shared row shape is `walk_on_news_row()` (`franchise_manager.py`): `name`, `pos`, `year`, `height`, `weight`, `attributes`, `rt`. Raw values only — the 0–10 attribute scale, two-letter year and RT letter grade are applied at the display boundary, so neither surface bakes in a format that can drift from the roster page.

### News Story

`build_walk_ons_news_story(team_name, rows)` returns a standard `season_news` story (`story_id` `w1-walk-ons`, `week` 1, `type` `walk_ons_announced`). Its body uses a **`player_table` rich line** — a line type added for this story, rendered by `news.js` as a roster-format table. `season_news` is cleared each rollover, so the un-seasoned `story_id` stays unique.

`news.html` loads `rtBucket.js`, `playerYear.js` and `css/rt-buckets.css` for the table. Note the `--rt-*-color` custom properties that stylesheet reads are set at runtime by `rtBucket.js`, not declared in any CSS file — loading the stylesheet alone would render the grades uncolored.

### Welcome Modal

Season-start reveal of the walk-ons who backfilled the user's roster at the prior season's Week 35. **Season 2+ only.**

**Why a snapshot and not a query.** The walk-ons are only identifiable during `finish_season`. `week_35_recruiting_results` is cleared in the same function, and once the players land in FPD the `"Walk On"` archetype no longer separates *this* season's arrivals from walk-ons still rostered from earlier seasons. So `finish_season` writes a display-ready payload before the wipe, mirroring `fcc_pending_new_lean_recruit_ids`.

| Aspect | Behavior |
|---|---|
| Written | `finish_season`, before `week_35_recruiting_results` is cleared |
| Read | `_build_walk_on_welcome_modal_payload` → FCC `walk_on_welcome_modal` |
| Trigger | First FCC landing of the new season (week 1, pre-Training-Camp) |
| Gate | `walk_on_welcome_modal_seen_season == current_season` |
| Dismiss | `PATCH /franchise/walk-on-welcome-modal-seen` — stamps season **and** clears the payload |
| Season 1 | Impossible by construction — only `finish_season` writes the payload |
| Zero walk-ons | No payload → no modal; season still stamped seen so it can't fire late |

**Fields**

| Field | Collection | Purpose |
|---|---|---|
| `pending_walk_on_welcome` | `franchises` | Display-ready walk-on rows: `player_id`, `name`, `pos`, `year` (already advanced), `height`, `weight`, `attributes`, `rt` |
| `walk_on_welcome_modal_seen_season` | `franchises` | Once-per-season gate |

**Sequencing.** No competing modal can be eligible on the same visit. The cut-required modal needs `week == CAMP_WEEKS` **and** training complete for that week (`_week_1_cut_requirement`); the rollover leaves training incomplete, so it only arms *after* Training Camp runs. Region-bye is a week-30 state. The modal still defers through `blockerVisible()` and registers in `fccHasCompetingModal()` so the archetype-evolution modal yields to it.

**Week 35 interaction.** Walk-ons are excluded from `_build_recruiting_results_modal_payload` — they are roster backfill, not a signing outcome, and now get their own reveal. Each player is introduced exactly once.

**UI.** Moment Modal on the shared Sammy chrome (`walkOnWelcomeModal.js`, `css/walk-on-welcome.css`). Team-uniform Sammy for the 8 Conference 1 programs via `getTeamSammyImage()`, generic otherwise. Table matches the roster page: name, pos, year, height, weight, 12 attributes on the 0–10 scale, RT as a letter grade. CTA "Go To Locker Room" scrolls to the FCC Home locker-room card.

### Tunable Constants

| Constant | Location | Value | Effect |
|---|---|---|---|
| `PENDING_WALK_ON_WELCOME_FIELD` | `franchise_routes.py` | `pending_walk_on_welcome` | Franchise-doc key holding the snapshot |
| `WALK_ON_WELCOME_MODAL_SEEN_SEASON_FIELD` | `franchise_routes.py` | `walk_on_welcome_modal_seen_season` | Once-per-season gate key |
| `MAX_RETRIES` | `walkOnWelcomeModal.js` | `300` | 1s-interval deferrals while another overlay is up (~5 min) before giving up |
| `story_id` | `build_walk_ons_news_story` | `w1-walk-ons` | News story key; unique because `season_news` clears each rollover |
| `.sammy-modal.is-wide` | `css/sammy-modal.css` | `720px` | Modal width; the 520px default cannot hold the 18-column table |

## Rename / Identity Note

Because the current rollout moved playbook settings to `play_id`, season-init continuity should treat:
- `play_id` as stable identity
- `name` as mutable display text

Any future season-init rebuild of playbook settings should preserve `play_id` keys.
