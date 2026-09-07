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

# Appendix — easing, and why the archetype plan does not work as written

> **Revised 2026-09-06 after measurement. The original appendix proposed keying easing off
> the `move_archetype` system. That plan is wrong for 99% of turns — see *The archetype
> correction* below. The continuity rule survives; the archetype mapping does not.**

## Current easing logic: there is none — and it is in more places than one

`animateStep.js:292` hardcodes `ease: "Linear"`. It is **not** the only site. Also hardcoded:

- `ShotAnimationSystem.js` — six sites (`:913, :952, :1053, :1397, :1554, :1599`), each
  commented *"Match other player movements"*
- `FreeThrowAnimationSystem.js` — two sites (`:353, :376`)

**A change that touches only `:292` leaves shot-path and free-throw-path player movement
linear**, which will read as inconsistent rather than as an improvement. Any easing work
covers all nine sites or it is not worth doing.

## The archetype correction

The six rate constants at `BackEnd/constants/__init__.py:342-347` are real:

```
DRIFT 8 · CRUISE 13 · SHOT_MOTION 14 · STANDARD 14 · SPRINT 18 · BURST 32
```

But **`move_archetype` exists only in `dynamic_hct.py`** — the HCT family. Measured over
12 seeded games: **HCT is 7 of 6,940 builds; HCO is 6,891.**

`_defender_move_archetype` (`dynamic_hct.py:1879`) is a *defender* helper for §D15 beats, and
the archetype is written onto segments at six sites (`:2051, 2396, 2590, 2659, 2926, 3051`),
all in that one file. It is consumed by `dynamic_hct_step_emitter.py` (`:1275, 1320, 1364,
1380`, plus `_build_loop_step` at `:244, 296-297`) and reaches the frontend nowhere.

So the original claim — *"the engine already decided it, the renderer simply is not being
told"* — **holds for 0.1% of turns and is false for the 99% that are HCO.** On the path that
carries the game there is no archetype to carry.

**What this means for the plan:** easing on HCO needs a different key. Options not yet
evaluated: derive character from the step's action type (`post_up`, `cut`, `drift`,
`handle_ball` — these exist on every pos_action), from the distance-over-duration ratio the
tween already has, or extend archetype authorship to HCO. **Do not design this until the
converter bug below is fixed**, because the inputs are currently wrong.

## The catch that survives: easing must be CONTINUITY-AWARE

**Naive per-step easing is worse than linear on multi-step movement.** A player crossing the
court over three steps, eased in and out on each, produces three accelerate-decelerate cycles
— a visible pulsing stutter, more objectionable than constant velocity.

- **ease IN** only on the **first** step of a movement
- **ease OUT** only on the **last** step (where the player actually stops)
- **linear** through the middle

One acceleration and one deceleration per *journey*, never per step. The `continuing_targets`
work in `BackEnd/utils/transition_bridge.py` is the same question and may supply the signal.

This part is independent of the archetype question and is still the right first move.

## ~~BLOCKER~~ — CLEARED 2026-09-07. Easing is no longer blocked.

The converter is fixed. `defender_placement.py` now accepts `"spot"`, and the fallthrough
raises in dev/test and declines to place the player in production rather than substituting
court centre. Everything below is retained as the record of what was wrong and how big it
was; the after-numbers are at the end of the section.

Measured 2026-09-06, 12 seeded games, 192,393 offensive pos_actions:

**64.3% of off-ball pos_actions are hardcoded to court centre (50,25).** Shooters 65.0% —
there is no shooter concentration; the rate is uniform across all five positions and every
action type. Mean displacement **18 grid units**, a third of the floor.

It is **not** a fallback firing on missing data. Split by cause:
`ELSE_NOTHING_AUTHORED: 0` · `LOCATION_MISS: 0` · `ELSE_SPOT_IGNORED: 123,890 (all)`.
The skeleton authors the spot every time, under the key `"spot"`. The offense build at
`defender_placement.py:176-197` checks `"coords"`, then `"location"`, then gives up — while
**eleven other sites in the same module** read `off_action.get("location") or
off_action.get("spot")` correctly (`:520, 535, 694, 757, 784, 1013, 1033, 1036, 1099, 1119,
1122`), as does `attack_drive_clearance.py:252`.

**It reaches the screen.** In the schema path the client actually renders, distinct players
at exactly (50,25) in the same step, per game:

| players stacked on the logo | buckets/game |
|---|---|
| 4 | 166.2 |
| 5 | **644.5** |
| 6 | 1.3 |

~17% of all coord buckets show four or more players on the centre logo, 99.5% of it in HCO.

**Any eye test of easing run against this would have been judging easing through players
teleporting to and stacking on mid-court.** That was the reason to fix the converter first.

### After the fix (2026-09-07)

Every logo bucket in the table above is **0**, in both arms — 4-player 166.2 -> 0, 5-player
644.5 -> 0, 6-player 1.3 -> 0. `ELSE_SPOT_IGNORED` 123,890 -> 0, with `LOCATION_MISS` and
`SPOT_MISS` both 0, i.e. every authored name resolved to a real coordinate.

Two things to carry into the easing work:

- **Movement is now real, and longer.** Players travel between authored spots instead of
  snapping to and from the logo, so the mean per-step displacement the curves have to shape
  is different from anything observed before this date. Any easing judgement made before
  2026-09-07 is void.
- **Outcomes moved substantially** — points/team 65.65 -> 55.75 played, 68.95 -> 67.83 sim.
  Balance references need re-cutting; that is separate scheduled work. Easing must not be
  used to compensate for balance that has not yet been re-cut.

About 449/game single-player coordinates still land exactly on the logo. Those survived the
counterfactual and are most likely ordinary mid-court traffic, not misplacement. Logged open
in `bugs.md`; they are not expected to affect the eye test.

## Revised sequence

1. ~~**Fix the converter**~~ — DONE 2026-09-07. One reader that did not speak the vocabulary
   the rest of its own module speaks. It moved outcomes broadly and balance references still
   need re-cutting; it changed where players stand on ~64% of offensive actions.
2. **Continuity-aware easing** across all nine hardcoded sites, two curves only
   (ease-out on arrival steps, linear otherwise).
3. **Then** decide what keys easing character on HCO, with the archetype question reopened
   on correct inputs.
4. Overlap stagger, timing variation, emphasis hierarchy — as in the main document.
