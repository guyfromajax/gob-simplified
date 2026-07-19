# Computer Team Playbook Customization

**Status:** Implemented June 2026

**Purpose:** Document how franchise CPU teams receive bespoke playbooks tied to their roster strengths, scheduled matchup group, and refresh cadence. This system gives computer teams persistent team identity without adding work to weekly training or recalculating playbooks during gameplay breaks.

**Primary files:**
- `BackEnd/utils/cpu_playbook_customization.py`
- `BackEnd/models/franchise_manager.py`
- `BackEnd/api/api.py`
- `BackEnd/api/franchise_routes.py`
- `BackEnd/models/turn_manager.py`

**Related docs:**
- `../06_Gameplay_Systems/Game_Init_System.md` — franchise FTD to game-document snapshot at game start.
- `../06_Gameplay_Systems/Computer_Team_Game_Init_System.md` — computer-team strategy defaults and playbook defaults.
- `../06_GMO_Supporting_Systems/Mode_Init_System.md` — default `initialize_playbook_settings` shape and team play-copy fields.

---

## Overview

Computer team playbooks are customized in **franchise game init**, not during weekly training.

At season init, the system identifies the unique CPU teams on the user team's regular-season schedule and stores them in ordered groups. At franchise game init, the current franchise week determines whether a group should be built or updated. If so, every CPU team in that group is refreshed in FTD before the current game snapshots FTD into `GameManager` and the game document.

This means:
- Playbook customization is persistent on FTD.
- The current game uses the latest FTD playbook snapshot.
- Training load screens do not carry this work.
- Playbooks do not update at quarter breaks, timeouts, or foul-outs.
- Strategy settings still drive high-level choices like man vs zone, motion vs set, and fast-break tendency.

---

## Data Surfaces

The system updates two FTD fields.

| Field | Purpose |
|-------|---------|
| `playbook_settings` | Percentages for motion plays, set plays, fast-break plays, zone defenses, and man-defense option. |
| `plays` | Per-team play copies. This is where `motion_focus` for motion plays and `target_shooter` for set plays live. |

This distinction matters. Motion focus and target shooter are **not** stored in `playbook_settings`; they are stored on each team play copy in `plays`.

Refresh metadata is also stored on each refreshed FTD row:

| Field | Purpose |
|-------|---------|
| `cpu_playbook_last_refresh_week` | Idempotency guard so the same team is not refreshed twice in the same week. |
| `cpu_playbook_last_refresh_group` | The stagger group refreshed for that team. |

The generated playbook settings also mark `_meta.cpu_customized = true`.

---

## Season Init Grouping

At franchise season init, `FranchiseManager.initialize_season()` builds `cpu_playbook_schedule` on the franchise document.

The grouping rules are:
1. Read the user's full regular-season schedule.
2. Identify each **unique** opponent in order of first matchup.
3. Ignore duplicate later matchups against the same opponent.
4. Store the ordered opponents in groups of four, with the final group containing the remainder.

Expected regular-season opponent count:
- 7 conference opponents
- 8 sister-conference / region opponents
- 4 out-of-region opponents
- 19 unique opponents total

Stored shape:

```json
{
  "cpu_playbook_schedule": {
    "ordered_opponents": ["team_id_1", "team_id_2"],
    "groups": {
      "1": ["team_id_1", "team_id_2", "team_id_3", "team_id_4"],
      "2": ["team_id_5"]
    }
  }
}
```

If older franchise docs do not have this field, game init rebuilds and persists it from the saved schedule.

---

## Refresh Cadence

The system uses staggered build/update weeks.

| Week | Action |
|------|--------|
| 1 | Build Group 1 |
| 2 | Build Group 2 |
| 3 | Build Group 3 |
| 4 | Build Group 4 |
| 5 | Build Group 5 |
| 11 | Update Group 1 |
| 12 | Update Group 2 |
| 13 | Update Group 3 |
| 14 | Update Group 4 |
| 15 | Update Group 5 |
| 21 | Update Group 1 |
| 22 | Update Group 2 |
| 23 | Update Group 3 |
| 24 | Update Group 4 |
| 25 | Update Group 5 |

Game init refreshes **every CPU team in the active group**, up to four teams. The group does **not** need to include the user's current-week opponent. This is intentional: refresh cadence follows the schedule grouping, not the active matchup.

Example:
- Week 7 has no build/update action.
- Week 12 updates every team in Group 2.
- If the user's Week 12 opponent is not in Group 2, that opponent still uses its most recent FTD playbook.

---

## Game Init Flow

`POST /api/init-game` runs the refresh before FTD is loaded into the game.

Flow:
1. Receive franchise game init request.
2. Load franchise doc and current week.
3. If current week maps to a CPU playbook group, refresh that group's CPU teams.
4. Reload home/away FTD rows via `load_ftd_data_for_team`.
5. Normalize FTD via `prepare_ftd_for_new_game`.
6. Build `GameManager`.
7. Apply FTD `playbook_settings` to `gm.home_team.playbook_settings` and `gm.away_team.playbook_settings`.
8. Persist the same baseline into the game document under `summary["teams"][team_id]["playbook_settings"]`.

The greenfield Q1 `simulate-quarter` path also calls the refresh before loading FTD, preserving parity with `init-game`.

### Complete-Week CPU Full Sims

Some complete-week CPU games use the full turn-by-turn simulation path instead of the distant-score shortcut. Those games are created in `BackEnd/api/franchise_routes.py`, not through `POST /api/init-game`.

For that path, the worker loads both teams' FTD rows directly, runs `prepare_ftd_for_new_game()`, builds a franchise-mode `GameManager`, and assigns:

```text
gm.home_team.playbook_settings = dict(home_prepared["playbook_settings"])
gm.away_team.playbook_settings = dict(away_prepared["playbook_settings"])
```

This is required because full CPU sims generally do not have a live `game_id`. Runtime play selection should therefore read the in-memory `TeamManager.playbook_settings`; a `games` collection fallback is not a reliable source for these simulations.

---

## Playbook Build Logic

Build weeks are weeks 1-5. During a build week, the target CPU team's playbook is created from its projected starters and available team play copies.

### Projected Starters

The system resolves one player per position:
- Prefer the current `TeamManager.lineup` when available.
- Otherwise select the best roster player for each open position by position rating.

The five positions are:
- `PG`
- `SG`
- `SF`
- `PF`
- `C`

### Strengths And Weaknesses

Inside / attack / outside strengths use the same shape as computer game-plan strategy logic.

Scores:
- `inside = cumulative SC`
- `outside = cumulative SH`
- `attack = (cumulative SC + cumulative AG) / 2`

Classification:
- Rank the three scores as lowest, middle, highest.
- A focus is **strong** if `highest - 70 > middle`.
- A focus is **weak** if `lowest + 70 < middle`.
- All other focuses are neutral.

These classifications are used for motion focus odds, motion percentages, and set-play counts.

### Motion Focus Odds

Each selected motion play receives a `motion_focus` roll using:

| Focus state | Chances |
|-------------|---------|
| Strong focus | 5 |
| Weak focus | 1 |
| Neutral focus | 2 |
| Balanced | 4 |

If `balanced` is selected, the play's `motion_focus` is stored as `None`.

### Scoring Ability By Position

For each projected starter, the system calculates scoring ability by focus:

| Focus | Formula |
|-------|---------|
| Outside | `2 * SH` |
| Attack | `AG + SC` |
| Inside | `ST + SC` |

Scorer tier:

| Ability | Tier |
|---------|------|
| `> 160` | Elite |
| `> 130` | Great |
| `> 100` | Good |
| Otherwise | Standard |

Set-play `target_shooter` odds by tier:

| Tier | Chances |
|------|---------|
| Elite | 5 |
| Great | 3 |
| Good | 2 |
| Standard | 1 |

For each selected set play, the play's `play_focus` determines which scoring ability formula is used to choose the target position.

---

## Motion Play Selection

Build weeks always select the three core motion plays:
- `5-0 Motion`
- `4-1 Motion`
- `3-2 Motion`

`PF Post Motion` is also selected when the projected starting PF has PF position rating `> 49`.

### Motion Percentages

Motion percentages start as even distribution across selected motion plays.

Then strengths and weaknesses adjust the mapped motion play:

| Focus | Motion play | Strong adjustment | Weak adjustment |
|-------|-------------|-------------------|-----------------|
| Attack | `5-0 Motion` | `+15%` | `-15%` |
| Outside | `4-1 Motion` | `+15%` | `-15%` |
| Inside | `3-2 Motion` | `+15%` | `-15%` |

When one play is adjusted, all other selected motion plays are adjusted proportionally in the opposite direction.

Percentages are clamped to a minimum of `1%` and rebalanced to total `100%`.

### Update Weeks

Motion plays are not updated on update weeks. Existing motion selections are preserved.

---

## Set Play Selection

### Build Weeks

For each focus, the system randomly chooses set plays with that focus:

| Focus state | Number of set plays |
|-------------|---------------------|
| Strong | 4 |
| Weak | 2 |
| Neutral | 3 |

This means a build week can select 6-12 set plays across inside, attack, and outside.

### Update Weeks

On update weeks, existing set plays are preserved.

For each focus classified as strong:
- Add one new randomly selected set play with that focus.
- Only unused eligible plays are considered.
- If no unused eligible play exists, do nothing.

### Set Play Percentages

After the selected set-play list is finalized:
1. Shuffle all selected plays.
2. Assign:
   - Play 1: `20%`
   - Play 2: `15%`
   - Play 3: `10%`
3. Assign the remaining `55%` evenly across all other selected plays.
4. Clamp/rebalance to total `100%`.

---

## Defense Playbooks

### Man Defense

Three first-class man variants (Base / Deny / Loose Man), weighted like the zone map:

```json
{
  "man_normal": 100,
  "man_tight": 0,
  "man_loose": 0
}
```

(`man_normal`=Base, `man_tight`=Deny, `man_loose`=Loose; legacy `man_pressure` folds to `man_tight` on save.)

This does **not** mean CPU teams always play man. Man vs zone is still determined by the team's `strategy_settings.defense` / gameplay selection rules. This map only weights which man variant is selected (`_select_man_defense_with_playbook_weights`) when man defense is chosen. See [`integrating_new_d_plays.md`](../projects/integrating_new_d_plays.md).

### Zone Defense

Zone percentages are randomized across:
- `zone_23`
- `zone_32`
- `zone_131`

Rules:
- Total must equal `100%`.
- No one zone can exceed `50%`.
- Each zone receives at least `1%`.

---

## Fast Break Playbooks

Fast-break play percentages are randomized across:
- `covert_release`
- `rim_runner`
- `triangle`

Rules:
- Total must equal `100%`.
- No one fast-break play can exceed `50%`.
- Each fast-break play receives at least `1%`.

The fast-break opportunity rate is still controlled by game-plan `strategy_settings.fast_breaks`. The playbook only controls which DREB fast-break concept is chosen after a fast-break opportunity exists.

---

## Runtime Consumption

CPU playbook settings are consumed in gameplay.

| Area | Runtime behavior |
|------|------------------|
| HCO motion/set play selection | Uses `playbook_settings.motion` / `playbook_settings.set_plays` for the offense team, including CPU teams. |
| Zone type selection | Uses `playbook_settings.zone_defense` for the defense team, including CPU teams. |
| DREB fast-break play selection | Uses `playbook_settings.fast_breaks` from the rebounding/offense team. |
| Set-play target shooter | Uses the selected team play copy's `target_shooter`. |
| Motion focus | Uses the selected team play copy's `motion_focus`; `None` means balanced/default. |

High-level tactical decisions remain separate:
- `strategy_settings.offense` controls motion vs set-play tendency.
- `strategy_settings.inside`, `attack`, and `outside` control focus tendency.
- `strategy_settings.defense` controls man vs zone tendency.
- `strategy_settings.fast_breaks` controls fast-break opportunity rate.

---

## Idempotency And Persistence

The game-init refresh is idempotent per team per week.

Before refreshing a CPU team, the system checks:

```text
cpu_playbook_last_refresh_week == current_week
```

If true, the team is skipped.

This prevents repeated game loads or retries from rebuilding the same CPU playbook multiple times in the same week.

---

## Implementation Notes

### Utility Module

`BackEnd/utils/cpu_playbook_customization.py` owns:
- `build_user_schedule_cpu_playbook_groups`
- `group_for_cpu_playbook_week`
- `build_cpu_playbook_for_team`
- `refresh_cpu_playbook_group_for_game_init`

This keeps the generation logic testable outside the large route files.

### Season Init

`BackEnd/models/franchise_manager.py` writes `cpu_playbook_schedule` to the franchise doc during `initialize_season`.

### Game Init

`BackEnd/api/api.py` calls `_refresh_cpu_playbooks_for_franchise_game_init()` before FTD rows are loaded for the game.

### Runtime Selectors

`BackEnd/models/turn_manager.py` now loads `playbook_settings` by matching the requested `team_id` to either the offense or defense `TeamManager`, without requiring `is_user_team`.

Every `TeamManager` initializes `playbook_settings` to `{}` so legacy/non-franchise paths have a safe baseline. Franchise game init and complete-week CPU full sims overwrite that baseline with FTD-customized playbooks when available.

`BackEnd/constants/fast_break_play_types.py` already supports weighted DREB fast-break play selection from `playbook_settings.fast_breaks`.

---

## Verification

Focused tests:
- `tests/test_cpu_playbook_customization.py`

Regression tests used at implementation:

```bash
MONGO_URI= MONGO_DB_NAME=gob-test ./.venv/bin/python -m pytest \
  tests/test_cpu_playbook_customization.py \
  tests/test_fast_break_rr_triangle_updates.py \
  tests/test_gameplan_game_doc_precedence.py
```

Implementation verification result:
- `19 passed`

Tests are run with `MONGO_URI=` and `MONGO_DB_NAME=gob-test` so pytest uses mongomock and does not touch staging or production databases.

---

## Tuning Reference

These values are intentionally gathered here so they are easy to revise later.

| Setting | Current value |
|---------|---------------|
| Build groups | 5 groups, first four groups of 4 and final group of remaining opponents |
| Build weeks | 1, 2, 3, 4, 5 |
| Update weeks | 11, 12, 13, 14, 15, 21, 22, 23, 24, 25 |
| Strong threshold | `highest - 70 > middle` |
| Weak threshold | `lowest + 70 < middle` |
| Motion strong adjustment | `+15%` |
| Motion weak adjustment | `-15%` |
| Minimum percentage | `1%` |
| Max zone percentage | `50%` |
| Max fast-break percentage | `50%` |
| PF Post Motion requirement | Projected starting PF position rating `> 49` |
| Elite scorer | Ability `> 160` |
| Great scorer | Ability `> 130` |
| Good scorer | Ability `> 100` |
