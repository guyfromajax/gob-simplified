# Making the animation feel rewarding

*Written 2026-09-06. Every file:line below was verified against the tree on that date.*

## The distinction this document exists to make

**UESS correctness and animation feel are different problems, and compliance work will not
improve feel.**

UESS is the contract that gets a player to the *right place*. Feel is entirely about what
happens *between* the places — acceleration, path shape, timing, emphasis. A perfectly
UESS-compliant animation can be lifeless. A messy one can feel great. Chasing coordinate
ownership will not fix "annoying," and no amount of it will produce "rewarding."

Both matter. They are separate workstreams and should be sequenced separately.

---

## Three diagnosed defects — the causes of "jerky, not organic, unnecessary stops and starts"

These were found weeks before this document and have never been acted on. None is an
architecture problem. All three are animation craft.

### 1. Linear easing — the single biggest feel problem in the codebase

`FrontEnd/static/js/phaser/animation/animateStep.js:292`

```js
ease: "Linear",
```

Every player starts at full speed instantly, holds constant velocity, and stops dead.
Nothing in the physical world moves like that, and linear easing is *the* signature of
amateur 2D animation. Real motion accelerates out of rest and decelerates into it.

**Fix:** an ease-in-out curve on the main player tween. One line. This will do more for
"organic" than any other single change available.

Suggested starting point: `"Sine.easeInOut"` for ordinary movement, `"Quad.easeOut"` for
a player arriving at a spot he intends to stop at, `"Quad.easeIn"` for one breaking into a
sprint. Judge by eye, not by argument.

### 2. Arrive-and-freeze

`BackEnd/utils/animation_step_helpers.py:761` (`stamp_tween_durations`), formula at `:792`

```python
durations[pid] = float(min(dist / rate, step_t))
```

A player who reaches his target before the step ends stands perfectly still for the
remainder. This is literally the "unnecessary stops and starts" symptom.

The tradeoff is real and unresolved: capping the duration gives arrive-and-freeze, while
stretching it to fill the step gives *lazy drift* — players gliding slower than their
attributes justify. The docstring names the lazy-drift anti-pattern, which is why the cap
exists.

**Fix:** a STRETCH_CAP experiment — allow the duration to stretch up to some multiple of
the natural time (try 1.0 / 1.5 / 2.0) before falling back to freeze. **Judge by eye.**
This one wants a person watching, not a metric.

### 3. Uniform beat length

`BackEnd/constants/__init__.py:337`

```python
HCO_STEP_T_FLOOR_GAME_SECONDS = 0.5   # Min step T for HCO skeleton steps
```

Every short movement takes at least half a game-second. Combined with a shot path that has
no release-timing model, this makes every beat approximately the same length. **Uniform
timing reads as mechanical even when every position is correct.**

**Fix:** vary step duration by what the step *is*. A shot release, a hard cut and an
off-ball drift should not occupy the same time slice.

### Measuring instrument that already exists

`FrontEnd/static/js/phaser/animation/deadAirLedger.js` — `dumpDeadAir()` at `:452`,
`resetDeadAir()` at `:484`. On by default, silent until called. It reports frozen steps,
announcement freezes, player stillness and arrival tails in player-seconds. Use it to
measure the effect of the changes above rather than arguing about them.

Prior measurement: stillness ran roughly 2x arrival tails, so defect 2 above is the larger
of the two contributors.

---

## The craft, for someone new to 2D animation

Four things carry almost all of the feel of moving characters.

**Easing.** Accelerate out of rest, decelerate into it. Never constant velocity. This is
defect 1 and it is the highest-value change on the list.

**Arcs.** Real bodies travel curves, not straight lines between two points. Players
currently move point-to-point. A slight arc on off-ball movement reads as human; a straight
line reads as a chess piece.

**Timing variation.** Identical beat lengths kill life even when the content varies. This
is defect 3.

**Overlap.** Not everything starts and stops on the same frame. Staggering five players by
40-80ms stops a formation looking like a marching band. Costs nothing, changes everything.

---

## "Rewarding" is a third axis, and it is a design pass not a code pass

Feel and reward are different. Right now every moment gets equal weight — a dunk, a routine
entry pass and a defensive shuffle all animate with the same energy and the same duration.

**Reward comes from unequal treatment.** Hold on the moment that mattered. Compress the one
that didn't. Let camera, sound and pacing mark significance. A game that animates everything
evenly has no highs, and a player learns there is nothing to look forward to.

Practically: build an emphasis hierarchy. Decide which outcomes deserve a beat of their own
(dunk, block, game-winner, and-one, steal-and-score) and which should be compressed
(routine pass, reset, off-ball drift). Then give the top tier extra time, a camera move, and
a sound cue the lower tiers don't get.

This is the work that turns "correct" into "fun," and none of it is in the backend.

---

## Recommended sequence

1. **Easing (defect 1).** One line, immediate visible payoff. Do this first.
2. **Arrive-and-freeze (defect 2).** STRETCH_CAP experiment, judged by eye.
3. **Overlap stagger.** Cheap, large perceived gain.
4. **Timing variation (defect 3).** Needs a view on what each step type deserves.
5. **Emphasis hierarchy.** The design pass. Largest effort, largest payoff on "rewarding."

UESS compliance runs underneath all of this as correctness hygiene — guarded, tested, and
tracked separately. It is not on this list, because it does not belong on this list.

---

## What this document is not

It is not a UESS document. If a coordinate is reaching the renderer wrong, that is a §1
ownership bug and belongs in the coord audit and its guards. Nothing here will fix that, and
fixing that will not produce anything on this page.

---

# Appendix — easing and the speed archetype system

*Added 2026-09-06. Constants verified at `BackEnd/constants/__init__.py:342-347`.*

## Current easing logic: there is none

`animateStep.js:292` hardcodes `ease: "Linear"` — one value, every player, every step,
every archetype. There is no logic to describe.

## The archetype system is already the right structure

```
DRIFT_GRID_PER_GAME_SEC        =  8   # slow off-ball relocation
CRUISE_GRID_PER_GAME_SEC       = 13   # BH bring-up / settle / transition
SHOT_MOTION_GRID_PER_GAME_SEC  = 14   # shooter during shot
STANDARD_GRID_PER_GAME_SEC     = 14   # base / AG curve anchor @ AG=50
SPRINT_GRID_PER_GAME_SEC       = 18   # max-effort movement
BURST_GRID_PER_GAME_SEC        = 32   # peak explosive start (FB outlet)
```

These are not merely speeds. They are **intents**, and an intent has a velocity *shape* as
well as a magnitude. Today the archetype sets only how far a player travels per second and
says nothing about how he gets there.

**Easing is the missing half of the same idea, keyed on data the engine already authors.**

## Proposed mapping — a starting point, to be judged by eye

| archetype | ease | rationale |
|---|---|---|
| `drift` | `Sine.easeInOut` | meandering, no urgency, soft at both ends |
| `cruise` | near-linear with soft ends | sustained locomotion genuinely *is* near-constant velocity |
| `standard` | `Sine.easeInOut` | the neutral case |
| `shot_motion` | `Quad.easeOut` | gather and settle into the release |
| `sprint` | `Quad.easeIn` | effort lives at the start |
| `burst` | `Expo.easeOut` | explosive — huge initial acceleration, then coast |

`burst` is the one to get right. It fires on fast-break outlets, which is exactly where the
game should feel most alive.

## The catch: easing must be CONTINUITY-AWARE

**Naive per-step easing will be worse than linear on multi-step movement.**

If a player crosses the court over three steps and each step eases in and out, the result is
three accelerate-decelerate cycles — a visible pulsing stutter. That is a more objectionable
artifact than constant velocity.

The rule:

- **ease IN** only on the **first** step of a movement
- **ease OUT** only on the **last** step (where the player actually stops)
- **linear** through the middle

One acceleration and one deceleration per *journey*, never per step.

The signal for this already exists in concept: the `continuing_targets` work in
`BackEnd/utils/transition_bridge.py` (freeze-by-default inversion, shipped 2026-09-04) is
precisely the question of whether a player is mid-journey or arriving.

## Architecturally this is clean, and it is UESS-correct

`_defender_move_archetype` (`BackEnd/engine/dynamic_hct.py:1879`) authors the archetype once
and carries it on the loop segment. Its own docstring:

> *"Single-motion-spec (UESS §1, rate dimension): this is authored HERE, once, and carried in
> the loop segment's `move_archetype` so the emitter renders at the SAME rate the engine
> decided from — it must never re-derive its own."*

That discipline is already correct. **The gap is that the frontend never receives it** —
`move_archetype` appears nowhere in `FrontEnd/static/js/phaser/` (verified 2026-09-06).

So the work is:

1. Carry `move_archetype` (and a continuity flag: first / middle / last of a journey)
   through the emitter onto the step the FE renders.
2. Have `animateStep` select its curve from those two fields.
3. The engine keeps deciding; the renderer keeps rendering and authors nothing.

**This is the rare case where the feel work and the UESS discipline pull in the same
direction** — the engine has already made the decision, and the renderer simply is not being
told what it decided.

## Sequencing note

This supersedes item 1 in the main sequence above. Do **not** simply swap `"Linear"` for
`"Sine.easeInOut"` globally — without the continuity rule that trade is not obviously a win.
The minimum viable version is: continuity flag + two curves (ease-out on arrival steps,
linear otherwise). Archetype-specific curves can follow once that reads correctly.
