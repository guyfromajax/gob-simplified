
# 🧠 Geeked-Out Basketball (GOB) Agents Reference (`agents.md`)
We are developing a game called Geeked-Out Basketball (GOB for short). Simply put, this is Football Manager for basketball. It's a deep-tactical basketball simulation game that is more about coaching and strategy than about action, animation, or button-mashing.

MACRO OBJECTIVE: We're building a game engine that is simple, stable, and scalable (SS&S). Use the SS&S lens in every project you undertake, every file you build, and every solution you develop. That is the most important component to building this game engine.

This file documents key game engine agents, roles, and architectural logic used by the Geeked Out Basketball simulation engine. It exists to help Codex, collaborators, and future developers reason about the system consistently.

## Product scope (Franchise-first)

**While this section stays in the document:** treat **Franchise mode** as the only active product priority for new work, fixes, and SS&S improvements. **Tournament** and **Single game** are **sunset**—do not extend or assume parity with franchise unless we explicitly revive them. Legacy routes and UI may still exist; default assumptions, tests, and docs should be **franchise-shaped**. Remove this section when product scope changes.

---

## 🎮 Game Structure

### `Turn`
A single possession in the game. Each turn contains multiple `steps`.

### `Step`
A single animation update within a turn. Typically ~3–8 steps per turn.

---

## 🏀 Player Roles

Each team has 5 active players:

| Position | Key | Description |
|----------|-----|-------------|
| Point Guard | `PG` | 
| Shooting Guard | `SG` |
| Small Forward | `SF` | 
| Power Forward | `PF` | 
| Center | `C`  | 

---

## 🧩 Core Animation System

### State Tracking (Core SS&S Pattern)
**State tracking is a fundamental component of the animation system.** Use single source of truth pattern for any state that persists across turns or operations.

**Principles:**
- **Single Source of Truth**: One place tracks state (e.g., `BallController` for ball state, `scene.currentPressureType` for FCP/HCT)
- **Lifecycle Methods**: Use explicit state transitions (e.g., `onShotStart()`, `onShotEnd()`)
- **Scene-Level State**: Track cross-turn context on scene object (e.g., `scene.currentPressureType`, `scene.currentOffenseTeamId`)
- **State Clearing**: Always clear state before transitions (prevents stale state bugs)

**Examples:**
- `BallController` - Single source of truth for ball ownership and flight state
- `scene.currentPressureType` - Tracks FCP/HCT pressure sequences
- `scene.gameState.ballHolder` - Tracks which player has the ball

**See:** `docs/Animation_System/animation_system.md` for detailed state tracking patterns and examples.

---

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

## 📦 Shared Game Assets

### `ballSprite`
- A shared Phaser `Image` object
- Assigned visually on each step via `setPosition(x, y)`
- Lives outside the player containers

---

## Repo-wide engineering playbook (additions)

Cross-cutting rules for safe feature work. **Subsystem behavior** remains documented under `docs/docs_1_systems/`. Keep using the SS&S lens from the top of this file.

### Canonical sources of truth (examples)

- Franchise national rank: prefer **`natl_rank`** where the product means national standing; **`rank`** should only appear as an explicitly documented response alias.
- Game documents: canonical **`team_id`** strings and documented shapes (see `docs/docs_1_systems/00_Data_Systems/`). Franchise masters may use ObjectId linkage—do not mix identifier styles without a shared resolver.
- Prefer **one owner field per concept** and extend the **API contract** instead of letting each page infer a different shape.

### UI feature change rules

- Canonical data should come from the **backend** where possible, not be re-derived differently on each page.
- **Filter, then rank/sort, then limit** when showing a scoped “top N.”
- Say whether a **rank** is absolute (e.g. national) or within-scope—and keep that consistent across tabs.

### Pre-merge checklist (micro-features)

1. Which **system** owns the source of truth for this field?
2. What **existing behavior** must stay unchanged?
3. **Frontend-only** change, or **backend / contract** update too?
4. Which **adjacent views** (FCC, stats, roster, box score) need re-verification?

### Stats / rankings surfaces

- Use **`natl_rank`** for national position where that is the promise.
- Conference/Region: confirm copy matches **absolute vs within-scope** rank behavior.
- National “Top 25” style filters: apply only where intended (e.g. team tables vs leader cards).
- **Leaders:** top *k* after scope filter, not before.

### FCC navigation

- Keep **tab state** URL-addressable where the product expects bookmarks/sharing.
- **`return_url`** is the return contract for FCC-launched flows; other entry points should use documented hub fallbacks.

### Further reading

- **Fragility patterns** (Jan 2025 examples; use as pattern guide, not a live bug list): `docs/To Do/Archive/codebase_fragility_analysis.md`
- **AG → movement speed:** `_documentation_master/00_General_Systems/UESS_System.md` §3.4 / §9.3
- **Manual QA before releases:** `_documentation_master/00_General_Systems/Manual_QA_Checklist.md`

---

## Best Practices (complex feature installs)

Captured from the Dynamic HCT Turns build — a large, stateful feature that landed close to right on the first install. Follow these for any complex feature so future installs have the same odds of going smoothly.

1. **Spec-first, single source of truth.** Write/expand a spec doc as *the* authority before coding, then make code conform to it. With a clear written spec, coding becomes translation, not invention. Rule of thumb: if you can't state a rule in one sentence, it's not ready to code.
2. **Resolve ambiguity before writing code.** On hard pieces, pause and ask targeted (ideally multiple-choice) questions until there's zero guessing. Minutes of questions prevent days of building the wrong thing.
3. **Centralize the tunable knobs.** Put each magic number / threshold in one named constant, not scattered inline. Decide upfront "what will I want to tune later?" so later tweaks are one-line changes, not hunts.
4. **Stage big features; verify each stage.** Split the feature into independently runnable stages and confirm each runs clean before building on it. Never write hundreds of lines before the first run.
5. **Build observability in early.** Add logging/tracing as part of the build, not after. For anything with state moving over time, debug from evidence, not guesses.
6. **Tight loop: change → run → trace → diagnose → fix.** Run the prototype constantly and feed real logs back. Short loops catch problems while context is fresh and the change set is small.
7. **Consistency sweep after every change.** After each edit, ask "where else does this concept live?" (doc section vs section, code vs doc) and update all of them so drift doesn't accumulate.

If you internalize only two: **#1 (spec-first single source of truth)** and **#2 (no coding until the rule is unambiguous)**. The other five keep those two honest.

---

