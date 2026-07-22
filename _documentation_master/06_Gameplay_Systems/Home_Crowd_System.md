# Home Crowd System

## Overview

Each game rolls a **Home Crowd Factor** (an integer **1–5**) once at game start. The factor models the home crowd's effect on the game and applies **only in-memory for that game** — it never mutates a team's stored attributes. A team's base shot threshold is unchanged when the game ends; the crowd effect is a separate additive delta held in `game_state` and added at shot/free-throw time.

The roll is weighted by the **home** team's `team_chemistry`. In Franchise, the home/away **Community Engagement** training focus can shift which weight band is used (or unlock the Upper Bonus band).

**Primary module:** `BackEnd/utils/home_crowd.py`

---

## Roll: weights by home team chemistry

The factor is drawn from `[1, 2, 3, 4, 5]` using `random.choices` with the band weights for the home team's clamped chemistry (`team_chemistry` clamped to 7–25). Source of truth: `_CROWD_WEIGHTS_BY_BAND` in `home_crowd.py`.

| Home `team_chemistry` | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| 7–10  | 30% | 40% | 15% | 10% | 5%  |
| 11–15 | 20% | 30% | 25% | 15% | 10% |
| 16–20 | 10% | 20% | 30% | 20% | 20% |
| 21–25 | 5%  | 15% | 20% | 30% | 30% |

### Upper Bonus Range

Used **only** when a Community Engagement shift pushes the roll **up** from the top (21–25) band — see "Community Engagement" below. Level 1 is never rolled in this band (`_UPPER_BONUS_WEIGHTS`).

| | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Upper Bonus | 0% | 10% | 20% | 30% | 40% |

---

## Factor impact

All impacts are scoped to the single game. They are stored as deltas in `game_state` and added when the relevant team attempts a shot or shoots a free throw (higher shot threshold = harder field goal).

| Factor | Away shot threshold | Home shot threshold | Away FT miss→make second chance |
|---|---|---|---|
| 1 | +0 | +0 | default (`FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE`) |
| 2 | +0 | +0 | 0.4 |
| 3 | +25 | +0 | 0.4 |
| 4 | +50 | +0 | 0.3 |
| 5 | +50 | −50 | 0.3 |

- **Shot threshold deltas:** `_shot_threshold_deltas_for_factor(factor)` returns `(away_delta, home_delta)`.
- **Free-throw second chance:** `effective_ft_miss_to_make_second_chance(game, offense_team_at_line)`. **Home** shooters always use the global 0.5 default; **away** shooters use the crowd tiers above (factor ≤1 → 0.5, 2–3 → 0.4, ≥4 → 0.3). See `Free_Throw_System.md` for how the miss→make second-chance roll is applied.

---

## Franchise: Community Engagement band shift

Single Game and Tournament have no training, so this applies **only in Franchise**. The Community Engagement focus (`culture-builder-community`, see `Training_System.md`) sets a `pending_community_engagement` flag on a team's franchise team data. The **next franchise game started** consumes that flag and shifts which weight band the home crowd roll uses:

- Beneficiary is **home** → shift the home roll **up** one band (top band → Upper Bonus Range).
- Beneficiary is **away** → shift **down** one band (floored at 7–10; no downward effect below the bottom band).
- **Both** teams have pending Community Engagement → shifts **cancel**; the roll uses the normal home chemistry band.

Pending flags are cleared when that game is started. If there is no game that week (e.g. bye), the effect carries to the **next** game played that season.

**Implementation:**
- `community_engagement_crowd_shift(user_ce, cpu_ce, user_is_home)` → `"none" | "up" | "down"` (pure shift logic).
- `consume_franchise_community_engagement_for_matchup(franchise_id, home_team_name, away_team_name, user_team_side)` reads both FTDs' pending flags, computes the shift, and clears both flags (`update_many`). Returns `"none"` if `franchise_id` or `user_team_side` is missing (can't resolve user-vs-cpu cancellation).
- `crowd_weights_for_home_team_chemistry(team_chemistry, crowd_shift)` applies the band shift before returning the weight row.

---

## Game-state keys and persistence

`initialize_home_crowd_in_game_state(game_state, home_team, crowd_shift)` is called once after `game_state` exists (from `GameManager` init, `BackEnd/models/game_manager.py`). It rolls the factor from `home_team.team_attributes["team_chemistry"]` (default 8) and writes:

| `game_state` key | Meaning |
|---|---|
| `home_crowd_factor` | The rolled factor (1–5). |
| `home_crowd_away_shot_threshold_delta` | Additive shot-threshold delta for the away team. |
| `home_crowd_home_shot_threshold_delta` | Additive shot-threshold delta for the home team. |

These keys (`HOME_CROWD_PERSIST_KEYS`) are saved on the game document. On resume, `restore_home_crowd_from_saved(game_state, saved)` reapplies them so the crowd factor is **not re-rolled** mid-game.

---

## Integration points

- **Init / CE shift consume:** `consume_franchise_community_engagement_for_matchup` is called in `BackEnd/api/api.py` when a franchise game is started (init-game and the new-game path of simulate-quarter); the resulting shift is passed into `initialize_home_crowd_in_game_state` via `GameManager` init.
- **Resume restore:** `restore_home_crowd_from_saved` is called in `api.py` when loading a saved game into memory.
- **Shot threshold application:** `home_crowd_shot_threshold_delta_for_offense(off_team, game)` is added to the offensive team's shot threshold in `BackEnd/utils/shared.py` and `BackEnd/models/shot_manager.py`.
- **Free-throw application:** `effective_ft_miss_to_make_second_chance` gates the FT miss→make second-chance roll in `BackEnd/engine/phase_resolution.py`.

---

## Key files

- `BackEnd/utils/home_crowd.py` — weights, roll, CE shift, deltas, game-state init/restore, FT second-chance.
- `BackEnd/models/game_manager.py` — calls `initialize_home_crowd_in_game_state` at game init.
- `BackEnd/api/api.py` — CE consume on franchise game start; restore on resume.
- `BackEnd/utils/shared.py`, `BackEnd/models/shot_manager.py` — apply shot-threshold delta.
- `BackEnd/engine/phase_resolution.py` — apply FT miss→make second chance.
- `BackEnd/tests/test_home_crowd.py` — coverage for deltas, FT tiers, and restore.
