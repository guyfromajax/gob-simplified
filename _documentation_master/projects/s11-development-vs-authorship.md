# §11 — Does development undo authorship?

> **Closed as a Team Builder question — 6 August 2026.**  
> Measurement: `s11-authorship-drift-findings.md`.  
> Living home: [`Player_Development_System.md` → Reshape vs grow](../10_Players_Systems/Player_Development_System.md#reshape-vs-grow--open-simulation-design).

## What §11 asked

Whether Team Builder authorship survives development. If the sim pulls authored attributes toward a target the user didn't choose, the roster they built decays — and TB becomes cosmetic after year one.

## What the measurement found

Control **0.147** · realistic **0.150** · extreme **0.147** retained profile-deviation at graduation.

Authorship is not being erased. **Individuality is** — and the same thing is happening to all 128 programs, every offseason, whether anyone authored them or not. The α-blend is a proportional pull: it takes the same 55% bite out of everyone's distance from the positional mean. Team Builder didn't create this; it made it visible.

## Why the original option space is mostly dead

| Option | Status |
|---|---|
| 1 — Accept + disclose | Still live as a *product* choice if the sim stays reshape-based — but it is no longer a TB-only decision. |
| 2 — Re-run archetype at Establish | **Dead.** Blend targets `position_profile(training_position)`, not archetype. |
| 3 — Re-derive `potential_factor` | **Dead.** Scalar on growth magnitude; does not touch the blend target. |
| 4 — Freeze authored attrs | Still wrong — creates two classes of player and a permanent special case. |

Both 2 and 3 assumed authorship was the victim. It isn't.

## The actual question (moved)

**Should development reshape a player, or grow him?**

That is a core simulation decision. It affects every program, scouting, recruiting, whether SIGNATURE bars mean anything after year two, and whether two programs feel different in season three. TB is the symptom and the reason it surfaced — not the scope.

Before choosing: measure **league-wide** convergence (spread across 128 programs at t0 vs t+3). That decides whether α is a tuning constant or the model itself must change. Separate open question: `_coaching_accumulator_for_player` hardwired to `None` (`f ≡ 1.0`) — unfinished, deliberate, or bug?

See the Player Development System doc for the full reframed design question, career-α math, and next measurement.
