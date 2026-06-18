# Player Momentum System

Momentum models hot/cold streaks. Two distinct values — don't conflate them:

- **Player MO** — per-player attribute, range **−10..+10** (`player.attributes["MO"]`). Changed by in-game events; reset at breaks; zeroed at game end.
- **Team Momentum** — **derived** sum of a team's 5 active (lineup) players' MO, range **−50..+50**. Computed on demand; never stored.

> **Tuning contract:** every value below is a named constant in `BackEnd/constants/momentum.py`, documented here 1:1. To retune, change the value in **both** this doc and `momentum.py` — the code reads the constant directly, so no other edits are needed. Player MO is always clamped to `[MO_MIN, MO_MAX]` via `player.clamp_mo`.

`anchor_MO` is the **training** baseline (a separate attribute). Gameplay never reads or writes `anchor_MO`.

---

## Tunable constants (`BackEnd/constants/momentum.py`)

| Constant | Value | Meaning |
|---|---|---|
| `MO_MIN` / `MO_MAX` | −10 / 10 | Per-player MO clamp range |
| `MO_BLOCK_DELTA` | 1 | Block: blocker +, blocked shooter − |
| `MO_STEAL_DELTA` | 1 | Steal: stealer +, victim − |
| `MO_AND_ONE_DELTA` | 1 | Made shot + shooting foul → shooter + |
| `MO_CHARGE_DELTA` | 1 | Charge: drawer +, charging player − |
| `MO_OREB_DELTA` | 1 | + on qualifying OREB |
| `MO_OREB_THRESHOLD` | 3 | OREB number that starts awarding (3rd and each after) |
| `MO_DUNK_DELTA` | 1 | **Deferred** — dunks not wired yet (hook only) |
| `MO_CONSECUTIVE_THRESHOLD` | 3 | Nth consecutive make/miss that starts awarding |
| `MO_CONSECUTIVE_DELTA` | 1 | + per consecutive make / − per consecutive miss |
| `MO_FT_MISS_MIN_ATTEMPTS` | 2 | only FT trips with >1 attempt qualify for the penalty |
| `MO_FT_ALL_MISS_DELTA` | −1 | flat, once per trip, when ALL attempted FTs miss |
| `MO_SET_PLAY_DELTA` | 1 | target_shooter makes the shot in a successful set-play skeleton |
| `MO_SHOT_ROLL_BASE` | (1, 6) | Default shot roll |
| `MO_SHOT_ROLL_POSITIVE` | (2, 6) | Favorable roll when MO > 0 and chance hits |
| `MO_SHOT_ROLL_NEGATIVE` | (1, 5) | Unfavorable roll when MO < 0 and chance hits |
| `MO_SHOT_IMPACT_PCT_PER_LEVEL` | 10 | P(modified roll) = \|MO\| × this (%) |
| `MO_SHOTCLOCK_BASE_PCT` | 40 | Shot-clock-violation base roll % |
| `MO_SHOTCLOCK_OFFENSE_DELTA` | −1 | Offense MO change; P = clamp(BASE − offenseTeamMO, 0, 100)% |
| `MO_SHOTCLOCK_DEFENSE_DELTA` | 1 | Defense MO change; P = clamp(BASE + defenseTeamMO, 0, 100)% |
| `MO_RESET_REDUCTION_MIN` / `_MAX` | 4 / 7 | Quarter + OT break decay toward 0 for active players (randint range) |
| `MO_TIMEOUT_REDUCTION_MIN` / `_MAX` | 2 / 4 | Timeout decay toward 0 for active players (randint range) |
| `MO_HALFTIME_HIGH_RESET` | (1, 3) | Halftime: MO == +MO_MAX → randint(1, 3) |
| `MO_HALFTIME_LOW_RESET` | (−3, −1) | Halftime: MO == −MO_MAX → randint(−3, −1) |
| `MO_FINAL_SHOT_BONUS` | 1 | + after reset if player made the quarter's Final Shot |
| `MO_TEAM_MIN` / `MO_TEAM_MAX` | −50 / 50 | Team Momentum range (= 5 × per-player range) |

Helpers live in `BackEnd/utils/player_momentum.py`; the per-player mutator is `Player.add_momentum(delta)` (`player.py`, clamps to ±10, never touches `anchor_MO`).

---

## Player MO events

Each event applies its delta via `add_momentum` (clamped). All file refs are functions, not fixed lines.

| Event | Effect | Where |
|---|---|---|
| **Block** | blocker **+1**, blocked shooter **−1** | `shot_manager.py` (block path) |
| **Steal** | stealer **+1**, victim **−1** | `phase_resolution.py` (turnover `STEAL`) |
| **Charge** | charge-drawer **+1**, charging player **−1** | `shot_manager.py` (charge return) |
| **And-1** (made shot + shooting foul) | shooter **+1** | `shot_manager.py` (main + block-recon), `shared.py` (putback) |
| **3rd+ OREB** | rebounder **+1** on `OREB` ≥ `MO_OREB_THRESHOLD` | `player.py` `record_stat` |
| **Consecutive shots** | see below | `player.py` `record_shot_result` |
| **Free Throws (all missed)** | shooter **−1** if he attempts **>1** FT in one trip and **misses all** of them (flat, once per trip) | `phase_resolution.py` `resolve_free_throw_logic` |
| **Set Play make** | the **target_shooter** **+1** when he makes the shot in a **successful** set-play skeleton | `phase_resolution.py` `resolve_half_court_offense_logic` |
| **Dunk** | **deferred** (constant + intent only) | — |

Doubly-good/bad cases are intentional: a block is **−1 MO + a `False`** on the shooter's streak list; an and-1 is **+1 MO + a `True`** on the streak list.

### Consecutive shots (`Shot_Result_List`)

A per-game, per-player boolean array (`True` = make, `False` = miss). Self-relative over the whole game — a player's streak is his own shots only, not the team's.

- On the **3rd** identical result in a row, and **each one after**: `+MO_CONSECUTIVE_DELTA` per consecutive make, `−MO_CONSECUTIVE_DELTA` per consecutive miss.
- **Qualifying shots:** HCO, HCT, FCP, Fast Break, and OREB **putbacks**. **Blocks count as a miss** (`False`). **Free throws are excluded** (never appended).
- Recorded by `Player.record_shot_result(made)`; appended at each shot resolution in `shot_manager.py` and `shared.py` (putback).
- `Shot_Result_List` lives in `stats["game"]` (list-typed) — see *Persistence*.

### Free throws — whole-trip miss penalty

- A **trip** is one visit to the line (one foul's FT sequence). If the shooter attempts **≥ `MO_FT_MISS_MIN_ATTEMPTS`** (2+) FTs in that trip and **makes none**, he takes a flat **`MO_FT_ALL_MISS_DELTA`** (−1) — **once**, at trip end.
- A single-FT trip never triggers it (e.g. an and-1's lone FT, or a missed 1-and-1 front end where the second was never unlocked).
- Free throws are **not** added to `Shot_Result_List`, so this is independent of the consecutive-shot streak.
- Counters (`mo_ft_trip_attempts` / `mo_ft_trip_makes`) accumulate across the per-FT calls in `game_state` and clear when the trip concludes.

### Set plays — target shooter make bonus

- When a **set play** (not Motion offense) resolves as the **`successful`** skeleton variant and the resulting shot is a **MAKE**, the shooter gets **`MO_SET_PLAY_DELTA`** (+1). The successful variant routes the ball to the play's `target_shooter` by construction, so the make is the target shooter scoring on the set play.
- Stacks with other shot-make effects (e.g. consecutive-make bonus, and-1).

---

## Player MO impact (shot attempts)

The base shooter roll and the OREB putback roll are **MO-aware** — `random.randint(1, 6)` is replaced by `mo_shot_roll(attributes)`:

- **MO > 0:** `|MO| × MO_SHOT_IMPACT_PCT_PER_LEVEL`% chance to roll `MO_SHOT_ROLL_POSITIVE` `(2,6)` instead of base. (MO 1 → 10%, … MO 10 → 100%.)
- **MO < 0:** same chance to roll `MO_SHOT_ROLL_NEGATIVE` `(1,5)` instead of base. (MO −1 → 10%, … MO −10 → 100%.)
- **Else:** `MO_SHOT_ROLL_BASE` `(1,6)`.

Wired at `shot_manager.py` (shooter base roll) and `shared.py` `oreb_shot_attempt` (putback roll). Passer/dribble/defense rolls are unaffected.

---

## Team Momentum (derived)

`team_momentum(team)` (`player_momentum.py`) = sum of the 5 active lineup players' MO, clamped to `[MO_TEAM_MIN, MO_TEAM_MAX]`. No stored value — computed on demand wherever needed (shot-clock-violation odds, court bar).

**Exposure to frontend** (all stamped in `GameManager._append_turn`, *after* the turn's MO changes apply):
- `home_team_momentum` / `away_team_momentum` — derived team values for the court bar.
- `player_momentum` — `{player_id: MO}` for every player, so the tooltip shows live MO (mirrors `player_energy` → NG).
- `summarize_game_state` also adds `team_momentum` to each team object (initial render / resume).

---

## Shot-clock violation MO

On any shot-clock violation, each **active** player rolls independently:

- **Offense:** `MO_SHOTCLOCK_OFFENSE_DELTA` (−1) at `clamp(MO_SHOTCLOCK_BASE_PCT − offenseTeamMO, 0, 100)`%.
- **Defense:** `MO_SHOTCLOCK_DEFENSE_DELTA` (+1) at `clamp(MO_SHOTCLOCK_BASE_PCT + defenseTeamMO, 0, 100)`%.

Team MO is snapshotted before any change. Applied by `apply_shot_clock_violation_momentum(offense, defense)`, called once per violation in `GameManager._append_turn` (the single funnel where every violation path converges on `turnover_type == "SHOT_CLOCK"`, before `switch_possession`, so `offense_team` is still the violator). A `_mo_sc_applied` guard prevents double-application.

---

## Resets (`apply_player_momentum_resets`)

Resets **never** run on a foul-out timeout.

| Trigger | Decay range | Bench | Active MO > 0 | Active MO < 0 | Where |
|---|---|---|---|---|---|
| **Q1→Q2, Q3→Q4, OT breaks** | `MO_RESET_REDUCTION_*` = **4/7** | → 0 | `max(0, MO − randint(4,7))` | `min(0, MO + randint(4,7))` | `main.py` `simulate_quarter` |
| **Timeouts** | `MO_TIMEOUT_REDUCTION_*` = **2/4** | → 0 | `max(0, MO − randint(2,4))` | `min(0, MO + randint(2,4))` | `game_manager.py` `call_timeout` |
| **Halftime (Q2→Q3)** | n/a (→0 + rails) | → 0 (rails apply) | → 0 unless rail | → 0 unless rail | `main.py` `simulate_quarter` (`is_halftime=True`) |

- Decay moves active players **toward** 0 by the trigger's randint range, **never crossing** 0; bench → 0. The range is passed into `apply_player_momentum_resets(..., reduction_min, reduction_max)` (defaults to the quarter/OT range; `call_timeout` passes the timeout range).
- **Halftime rails:** MO `+MO_MAX` → `randint(1,3)`; MO `−MO_MAX` → `randint(−3,−1)`; everyone else → 0.
- **Final-Shot bonus:** the player who made the quarter's Final Shot gets `+MO_FINAL_SHOT_BONUS` **after** the reset. Flagged via `game_state["mo_final_shot_maker_id"]` in `phase_resolution.py` `resolve_final_turn_shot_logic`; consumed and cleared in the reset.
- **End of game:** `reset_all_player_momentum(game)` zeros **every** player's MO (both teams, active + bench) at the live game-final detection (`is_final` in `api.py`), before the final save — no in-game momentum persists past the game. Distant-sim (CPU) games never change MO, so need no reset. See `End_Of_Game_System.md`.

---

## Persistence

- Player MO is serialized on the player snapshot (`attributes.MO`) in `summarize_game_state` and restored on load/resume (`api.py` / `franchise_routes.py`).
- `Shot_Result_List` rides the game doc in `stats["game"]` — restored on timeout/quarter resume, reset each game. It is **not** a `BOX_SCORE_KEY` and is excluded from team-stat summation (list-typed). See `Game_Init_System.md` → *Per-game stat arrays*.
- EOG reset runs before persistence, so saved docs (and any franchise writeback) record MO 0.

---

## Frontend (court momentum bar)

`FrontEnd/static/court.html` has a per-team bar (`home/away-momentum-neg`, `-pos`, center tick): **0 centered**, red fill (`#ff4444`) extends **left** to −50, green fill (`#34EC27`) extends **right** to +50.

Driven by `gameScene.js`: `momentumValueForTeam()` reads `turn.{home,away}_team_momentum` (then the summary `team_momentum` fallback), and `updateMomentumBar(side, value)` maps the −50..+50 value to fill widths each scoreboard update.

The **player tooltip** momentum bar reads live MO: each turn's `player_momentum` is folded into `playerStats[id].MO`, and the tooltip reads `playerStats.MO` (falling back to the load-time `player.attributes.MO`).

---

## Key files

| File | Role |
|---|---|
| `BackEnd/constants/momentum.py` | All tunable constants (source of truth) |
| `BackEnd/utils/player_momentum.py` | `mo_shot_roll`, `team_momentum`, `apply_shot_clock_violation_momentum`, `apply_player_momentum_resets`, `reset_all_player_momentum` |
| `BackEnd/models/player.py` | `clamp_mo`, `add_momentum`, `record_shot_result`, 5th-OREB hook, `Shot_Result_List` init/reset |
| `BackEnd/models/shot_manager.py` | Block / charge / and-1 deltas; MO-aware base shot roll |
| `BackEnd/utils/shared.py` | Putback and-1 + MO-aware putback roll; `summarize_game_state` team momentum |
| `BackEnd/engine/phase_resolution.py` | Steal delta; Final-Shot maker flag; FT all-missed penalty (`resolve_free_throw_logic`); set-play make bonus (`resolve_half_court_offense_logic`) |
| `BackEnd/models/game_manager.py` | `_append_turn` (shot-clock violation MO + per-turn team-momentum stamp); `call_timeout` reset |
| `BackEnd/main.py` | `simulate_quarter` quarter/halftime reset |
| `BackEnd/api/api.py` | EOG reset at `is_final` |
| `FrontEnd/static/court.html`, `js/phaser/gameScene.js` | Team momentum bar + player tooltip bar |

---

## Not covered here

- **Training "Inspire"** (Culture Builder): +1/+2 MO and updates `anchor_MO` at `training_execution_v2.py:628`. This is the only thing that moves the **training** baseline; it is not gameplay momentum.
- Per-archetype `momentum_score` training amplifier — still a TODO, not implemented.
- Legacy team-`momentum`/`momentum_score` fields and the old block/3PT team-momentum logic — **removed** (2026-06-18); superseded by derived Team Momentum above.
