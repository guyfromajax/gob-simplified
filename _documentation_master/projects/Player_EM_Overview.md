# Player EM Overview

Locked 2026-09-17. **EM = Emotion**, integer **1–100** (display still maps 0–100 emoji bands). **Not** in-game energy (**NG**).

**FPD is the week-to-week source of truth.** `franchise_players_data.attributes.EM` (+ `anchor_EM`) is what the roster shows, what training writes, what EOG writes, and what a franchise game seeds from. The game document `players[].attributes.EM` is the in-game copy; timeout/resume still restores from the **game** save.

Canonical module: `BackEnd/utils/player_em.py`.

---

## 1. How EM is established

Shared helper: `Player.randomize_game_attributes()` in `BackEnd/models/player.py`.

- Copies core 12 (SC–FT) as-is.
- `NG = 1.0`, `MO = 0`.
- `CH = random.randint(1, 100)` unless `preserve_character=True`.
- **`EM = random.randint(1, 100)`**, then `anchor_EM = EM`, unless `preserve_emotion=True` (franchise **game** init).

Player generation (`BackEnd/utils/player_generation.py` `generate_player`) rolls EM 1–100 independently. Pool TSV load sets EM to **0** until something randomizes it.

### Franchise init (season 1)

`FranchiseManager` clones every universal-pool player into FPD and **always** runs `randomize_game_attributes` on the clone. Pool EM is discarded. Walk-ons come from `generate_walk_on_profile()` → `generate_player`.

Team Builder apply: core 12 from the editor, then `_finalize_franchise_attributes` → `randomize_game_attributes` (fresh CH/EM/MO). Walk-on overlay keeps generator CH/EM/MO when present.

### Season init / rollover (`finish_season`)

Returning players: FPD `attributes` **copied as-is**, including EM. Offseason `develop_rollover` does **not** touch EM.

Newly signed recruits / week-35 walk-ons: `_normalize_new_franchise_player_attributes` → `randomize_game_attributes(..., preserve_character=True)`. **EM is re-rolled 1–100** at roster entry. Recruit CH is kept.

### Tournament / Single Game

Still re-roll EM 1–100 at game init (`preserve_emotion=False`).

---

## 2. Week-to-week rules (locked)

Clamp after every change: `max(1, min(100, value))`. **Each player gets their own roll** in every instance.

### Training (weeks 1–26, including camp week 1)

User and CPU auto-train share `execute_training` / `apply_training_points`. Two **independent** rolls, then one clamp:

`new_em = clamp(em + focus_delta + breaks_delta)`

Focus + breaks EM is **not** shown on the training-report changes grid (`TRAINABLE_PLAYER_ATTRS` still excludes EM).

**Coaching focus** (`sub_option` = full radio `value`):

| Focus | Band |
|---|---|
| Inspire (`culture-builder-inspire`) | `+ random.randint(2, 5)` |
| Community Engagement (`culture-builder-community`) | `+ random.randint(2, 5)` (crowd flag unchanged) |
| Confidence (`culture-builder-confidence`) | `+ random.randint(0, 2)` |
| Discipline (`authoritarian-discipline`) | `+ random.randint(-5, 0)` |
| Execution (`authoritarian-execution`) | `+ random.randint(-3, 0)` |
| Any Systems Coach leaf (`systems-coach-*`) | `+ random.randint(-2, 0)` |
| Any Player Maximizer leaf (`player-maximizer-*`) | `+ random.randint(0, 2)` |
| Rebounding / Teamwork / Team Building | no focus EM |

Inspire still applies **MO** `+ random.randint(1, 2)` and its fight/chemistry side effects. Community Engagement still sets FTD `pending_community_engagement` (home crowd), not via the EM helper.

**Breaks** slider (missing → 0):

| Points | Band |
|---|---|
| 0 | `+ random.randint(-5, -3)` |
| 1 | `+ random.randint(-2, 0)` |
| 2 | `+ random.randint(0, 2)` |
| > 2 | `+ random.randint(2, 5)` |

Pre-training decay still skips EM. Training closed after week 26.

### Franchise game init

`_initialize_game_stats` calls `randomize_game_attributes(..., preserve_emotion=True)` when either team has `franchise_id`. **CH still re-rolls; MO still zeros; EM is copied from the Player/FPD value already on the roster.** Timeout/resume still restores EM from the game document.

### EOG (every franchise game, both teams)

Applied in `_finalize_team_attributes_for_game` via `apply_franchise_eog_player_em`, **including weeks 27–36** when team attributes are frozen. Idempotent (`player_em_eog_applied` on the game doc) so `save-result` + `complete_week` cannot double-apply. **Practice Squad games are skipped.**

Inputs per player:

- **RT** = max `position_ratings` on the **FPD** doc (roster RT).
- **Minutes** = box `MIN` stored as seconds, displayed as `floor(seconds / 60)`. DNP / missing = 0.
- **CH** = FPD `attributes.CH` (not the in-game CH re-roll).

CH ranges: Range 1 `> 69`; Range 2 `40–69`; Range 3 `< 40`.

**RT > 69**

| Minutes | Range 1 | Range 2 | Range 3 |
|---|---|---|---|
| > 19 | `randint(2, 5)` | `randint(2, 4)` | `randint(1, 4)` |
| 15–19 | `randint(0, 1)` | `randint(-1, 1)` | `randint(-1, 0)` |
| else | `randint(-5, -2)` | `randint(-6, -3)` | `randint(-7, -3)` |

**RT 50–69** (`< 70` and `> 49`)

| Minutes | Range 1 | Range 2 | Range 3 |
|---|---|---|---|
| > 19 | `randint(1, 3)` | `randint(1, 2)` | `randint(0, 2)` |
| 15–19 | `randint(0, 1)` | `randint(-1, 1)` | `randint(-1, 0)` |
| else | `randint(-2, 0)` | `randint(-3, -1)` | `randint(-4, -1)` |

**Else (RT ≤ 49)**

| Minutes | Range 1 | Range 2 | Range 3 |
|---|---|---|---|
| > 19 | `randint(3, 7)` | `randint(2, 6)` | `randint(2, 5)` |
| 15–19 | `randint(2, 5)` | `randint(2, 4)` | `randint(2, 3)` |
| else | `randint(-1, 0)` | `randint(-1, 0)` | `randint(-2, 0)` |

Writes FPD `attributes.EM` and `anchor_EM`.

### Press conference / gameplay

Question bank has `player_em_up` / `player_em_down` tags; `effect_tag_resolver.py` is **not implemented**. The sim does not read EM (NG is energy). Home crowd does not write EM.

---

## 3. Display

- Emoji: ≥80 😎 / ≥60 😊 / ≥40 😐 / ≥20 😕 / else 😡 (`training-report.js` `getEmotionEmoji`).
- Training report **attribute order** still includes EM; the **changes grid** does not show an EM delta.
- Player detail falls back to 50 if missing.

---

## 4. Key files

- `BackEnd/utils/player_em.py` — clamp, focus/breaks bands, EOG table, FPD writeback
- `BackEnd/models/player.py` — `randomize_game_attributes(preserve_emotion=…)`
- `BackEnd/models/training_execution_v2.py` — `apply_training_em`; Inspire MO kept in the inspire block
- `BackEnd/api/franchise_routes.py` — `_finalize_team_attributes_for_game` player-EM EOG; training persist already includes EM
- `BackEnd/main.py` — franchise game init preserves EM
- `tests/test_player_em.py`
- `_documentation_master/09_Training_Systems/Training_System.md`
- `_documentation_master/06_Gameplay_Systems/End_Of_Game_System.md`
- `_documentation_master/06_Gameplay_Systems/Game_Init_System.md`
- `_documentation_master/10_Players_Systems/Player_Attribute_System.md`
