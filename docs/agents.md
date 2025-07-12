
# 🧠 GOB Agents Reference (`agents.md`)

This file documents key game engine agents, roles, and architectural logic used by the Geeked Out Basketball simulation engine. It exists to help Codex, collaborators, and future developers reason about the system consistently.

---

## 🎮 Game Structure

### `Turn`
A single possession in the game. Each turn contains multiple `steps`.

### `Step`
A single animation update within a turn. Typically ~5–8 steps per turn.

---

## 🏀 Player Roles

Each team has 5 active players:

| Position | Key | Description |
|----------|-----|-------------|
| Point Guard | `PG` | Primary ball handler |
| Shooting Guard | `SG` | Secondary perimeter scorer |
| Small Forward | `SF` | Wing scorer/defender |
| Power Forward | `PF` | Screener and post passer |
| Center | `C`  | Finisher and rebounder |

---

## 🧩 Core Animation System

### `capture_halfcourt_animation()`
Backend method that builds the animation packet for each turn.

- Builds `movement[]` per player
- Builds `hasBallAtStep[]` per player
- Stores player `action` and `coords` per step

### `hasBallAtStep[]`
An array (length = number of steps) for each player.
- `true` only if the player's action is `handle_ball`, `receive`, or `shoot` at that step
- Only one player should have `true` per step

### `ball_owner_by_step`
Internally tracks which offensive player should have the ball for each step. Used to populate `hasBallAtStep[]`.

---

## ⚙️ Frontend Animation Pipeline

### `playTurnAnimation()`
Main driver of per-step animation for each turn. Calls:

1. `runSetupTween()` – moves players to their step 0 positions
2. `updateBallOwnership(stepIndex)` – assigns `ballSprite` to the player with the ball
3. `animateStep()` – animates movement of each sprite

### `updateBallOwnership({ stepIndex })`
Assigns `ballSprite` position to the player with `hasBallAtStep[stepIndex] === true`.

- Uses a shared `currentBallOwnerRef` to persist ball holder across tweens
- Can include an optional `team === offenseTeamId` check (currently removed for debugging)

---

## 🏠 Team Architecture

### Teams
- Teams are identified by `team_id`, e.g., `"MORRISTOWN"` or `"FOUR_CORNERS"`
- Each sprite is assigned a `team_id` when created
- `offenseTeamId` and `defenseTeamId` passed into animation pipeline

### Home vs. Away
- `is_away_offense = offense_team.team_id === game.away_team.team_id`
- When true, coordinates are mirrored (flipped) before tweening

---

## 🚦Known Edge Cases (as of July 2025)

- `event_type = "SHOT"` is hardcoded due to incomplete foul/turnover logic
- On **away team possessions**, the **second pass (PG → PF)** is skipped
- On **home team possessions**, the **third pass (PF → C)** is skipped
- Defensive player movement is slightly off and will be addressed after pass logic is fixed

---

## 📦 Shared Game Assets

### `ballSprite`
- A shared Phaser `Image` object
- Assigned visually on each step via `setPosition(x, y)`
- Lives outside the player containers

### Team Logos
Stored in `/FrontEnd/static/images/team_logos/`  
Format: `.jpg` or `.webp`  
Naming convention: `bentley_truman.jpg`, `morristown.jpg`, etc.

---

## 🔧 In-Progress Logic

- Defensive player AI logic (incomplete)
- Foul, turnover, and free throw animation support
- Dynamic `event_type` resolution from `determine_event_type()`
