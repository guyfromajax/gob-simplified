# Making the animation feel rewarding

*Written 2026-09-06. Every file:line below was verified against the tree on that date.*

> # ⚠ READ BEFORE USING ANY NUMBER IN THIS DOCUMENT (added 2026-09-09)
>
> ## 1. STILL-PLAYER COUNTS DO NOT MEASURE THE COMPLAINT. They invert against a human observer.
>
> Calibrated against Jamie's eye on two families that point opposite ways (bugs.md item 33). He
> says MISS/post-shot looks CORRECT and FCP/HCT/FAST_BREAK look FROZEN. The detector says:
>
> | family | Jamie | movers/10 | movers/10 (≥1 ft) | ft/sec | ~~player ft ÷ ball ft~~ | ball ft/step (FE-accurate) |
> |---|---|---|---|---|---|---|
> | MISS post-shot | **CORRECT** | **3.75** | **3.47** | 11.68 | ~~0.229~~ | **7.80** |
> | FCP | frozen | 4.82 | 4.30 | 13.55 | ~~0.291~~ | **7.86** |
> | HCT | frozen | 6.00 | 5.82 | 21.16 | ~~0.592~~ | **11.71** |
> | FAST_BREAK | frozen | 7.24 | 6.83 | 28.02 | ~~0.914~~ | **8.41** |
>
> **FIVE** formulations were tried — the binary predicate, displacement magnitude, on-screen
> speed, motion relative to the ball, and ball displacement itself — and **not one orders the
> families correctly**. The family the human calls correct scores as the most frozen every time.
>
> The `player ft ÷ ball ft` column is **STRUCK**: it divided by a ball displacement that was
> misread (bugs.md items 36, 38). The ball is drawn at its CARRIER on 64-77% of steps
> (`animationPlayback.js:81-88`), so reading `ball.coords` scored a carried ball as motionless.
> Ball travel resolved the frontend's way is the final column, and it is the fifth failure: the
> three families Jamie calls FROZEN move the ball at least as much as the one he calls CORRECT.
> **Ball displacement briefly looked like the one measure that survived. It did not.**
>
> **A FUTURE SESSION MUST NOT PICK UP A STILL-PLAYER COUNT AND TREAT IT AS A MEASURE OF "LOOKS
> FROZEN".** The counts are arithmetically correct and they measure something real; they simply
> do not predict what a viewer notices. Until an instrument exists that does, **Jamie at the
> screen is the only ranking authority for feel work.** That is a legitimate outcome, not a
> failure to try hard enough.
>
> **THE SEARCH IS CLOSED — do not propose a sixth measure.** Settled 2026-09-09 after the ball
> measure fell. This is a decided position, not an open question.
>
> **AND CHECK YOUR COVERAGE BEFORE YOU BELIEVE A NUMBER.** Every one of these probes read a
> field that exists in the schema; the ball probe read the wrong one and resolved on only 4-15%
> of steps, silently scoring the rest as zero. A detector must mirror the CONSUMER of the value,
> and where it cannot, it must report the fraction of cases it actually resolved.
>
> ## 2. THE RANKING HAS BEEN STRUCK, not re-ordered.
>
> The "RANKING AT 2026-09-08, by measured size" section below is withdrawn. Re-ordering it would
> imply we can still rank these items, and per point 1 we cannot: every entry in it was sized in
> the units that invert.
>
> ## 3. ARM ATTRIBUTION. Every figure in this document is now tagged.
>
> The `PLAYED=1` shim bug (bugs.md items 29 and 31) meant many figures labelled "played arm" were
> measured on the sim arm. **Any figure below NOT explicitly tagged `[PLAYED]` or `[SIM]` should
> be read as ARM UNKNOWN and re-measured before it is relied on.** The same rule applies to
> preserved JSON under `.arm/`: no `played_arm` field means unknown, not played.

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

~~**Fix:** a STRETCH_CAP experiment — allow the duration to stretch up to some multiple of
the natural time (try 1.0 / 1.5 / 2.0) before falling back to freeze.~~

**STRUCK 2026-09-09. The prescription was wrong and was never implemented.** `STRETCH_CAP` is a
name in this document, not a mechanism in the tree. More importantly the direction was backwards:
the tail is a **deliberate decision, not a bug**. `stamp_tween_durations`
(`animation_step_helpers.py:1029`) caps each tween at the player's natural travel time precisely
so he does not glide slower than his attributes justify, and its docstring names *lazy drift* as
the anti-pattern it is avoiding. Stretching a tween to fill a step means slowing a man down so
the clock catches up, and a court of players moving at wrong speeds reads worse than a court of
players standing still. That judgement stays. What the author lacked was anything to put in the
gap.

**SHIPPED 2026-09-09 — FILL, do not stretch.** `stamp_arrival_settle` puts a delayed idle wander
in the tail: the player travels at his natural speed exactly as before, then settles in place for
the remainder. No duration changes anywhere, so no timing blast radius. See "Arrival-tail fill"
below.

#### RE-MEASURED 2026-09-08 at HEAD — defect 2 is the LARGEST remaining item, and the doc never had its size

Two stale line references above: `stamp_tween_durations` is at `:1029` and the formula at
`:1060`, not `:761`/`:792`. `STRETCH_CAP` does not exist anywhere in the tree — it is a
proposed name in this document, not a mechanism that shipped, so there is nothing to switch on.

**A tail is arithmetic the codebase already performs**, and it is reproducible from the payload
without a browser:

| | | |
|---|---|---|
| backend | `stamp_tween_durations` (`animation_step_helpers.py:1060`) | `tween_durations[pid] = min(dist / rate, step_t)`, game-seconds |
| frontend | `animationPlayback.js:1307-1310` | `playerDurationMs = max(50, round(tween * clockSecondMs))`, else the STEP duration |
| frontend | `animationPlayback.js:1064-1071` | `stepMs = wall_clock_hold_ms`, else `max(50, round(end.time_elapsed * clockSecondMs))` |

so `tail_ms = stepMs - playerDurationMs`. Measured on 8 played games (`scratch_tails_miss.py`),
with the FE's `max(50, ...)` floors applied on both sides because they change the answer for
short steps.

**NULL CONTROL.** Stripping `tween_durations` in process makes the FE fall back to step
duration for every player, so every tail must be exactly zero — and is, on 3 seeds. The
detector reads `tween_durations` and nothing else.

**THE SIZE:**

- **50.9% of moving player-steps carry a tail** (15,361 of 30,189).
- **524.5 s of dead tail per game** — **30.7% of the wall time moving sprites are on screen**,
  18.6% of all player-sprite time, **52.5 s per sprite per game**. (Per-player numerator needs a
  per-player denominator: comparing 524.5 s of tail against the 278.1 s of per-STEP animation
  time compares ten things to one and yields a nonsensical 188%.)
- Median tail **146 ms**, p90 **722 ms**, p99 **1,352 ms**, max **1,982 ms**. The median tailed
  step wastes **47.4%** of its duration; at p90, **80.6%**.

**THE DISTRIBUTION, which is the number that decides the fix** — a 40 ms tail and a 900 ms tail
are different problems and the old ratio could not tell them apart:

| tail | share | cumulative |
|---|---|---|
| 0-60 ms | 24.8% | 24.8% |
| 60-150 ms | 26.3% | 51.1% |
| 150-300 ms | 19.4% | 70.6% |
| 300-600 ms | 14.5% | 85.1% |
| 600-1000 ms | 9.8% | 94.8% |
| 1000+ ms | 5.2% | 100% |

**24.8% are below the 60 ms perceptibility floor** (`deadAirLedger.js:87`) and want nothing at
all. **29.4% are ≥300 ms** and are a visible pause.

**WHERE THE DEAD TIME CONCENTRATES — 69.6% of it is in ONE population:**

| continuity class | tails | share of tails | dead time | mean tail |
|---|---|---|---|---|
| `ease_in_out` (one-step journey) | 7,251 | 47.2% | **364.8 s/game (69.6%)** | **402 ms** |
| `ease_out` (arriving) | 3,681 | 24.0% | 72.5 s/game (13.8%) | 158 ms |
| `continuing` | 2,586 | 16.8% | 44.4 s/game (8.5%) | 137 ms |
| `ease_in` (departing) | 1,843 | 12.0% | 42.8 s/game (8.2%) | 186 ms |

A one-step journey is a short natural tween dropped into a long step, so it has the worst of
both — and it is 42.9% of all moving player-steps. Any fix that only targets `ARRIVING` steps
addresses 13.8% of the problem.

**EASING DID NOT SHRINK THE TAILS, and was never going to.** A Phaser tween's duration is
independent of its curve, so an early arrival is still an early arrival. The stillness-to-tails
ratio is **2.23 : 1** at HEAD against 2.11 : 1 before, i.e. unchanged within noise. What easing
changed is how the arrival *reads* — a decelerating stop rather than a halt — which may lower
perceived severity without touching the measured quantity. That is Jamie's eye, not this table.

**THE IDLE WANDER COVERS NONE OF IT, verified rather than assumed.** It gates on
`_idle_is_still(start, end)` across the WHOLE step (`animation_step_helpers.py:174`), so a
player who moves at all is excluded: **0 of 18,379 arriving player-steps carry a wander**, while
20,943 wander player-steps exist elsewhere, so the detector is alive.

**FILL, DO NOT STRETCH — what the measured shape suits.** Stretching durations changes timing,
which is a wider blast radius than anything shipped in this workstream. The tails are long
enough to fill instead: 402 ms mean on the dominant population is ample for a weight shift, the
wander mechanism is already eye-verified, and the continuity classifier already identifies the
steps. `applyIdleWander` starts immediately and has **no `delay` parameter**
(`arrivalHeartbeat.js:350`), so filling needs one added — modest, but it is an addition, not a
config change. It also snaps the sprite to authoritative rest before capturing wander bases
(`:363-364`), which is correct for a tail because the arrival coord *is* the rest.
The 24.8% of tails under 60 ms should be left alone.
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
2. ~~**Arrive-and-freeze (defect 2).** STRETCH_CAP experiment~~ — **SHIPPED 2026-09-09 as an
   arrival-tail FILL, not a stretch.** STRETCH_CAP never existed and the direction was backwards.
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

### SHIPPED 2026-09-08 — and the departure ambiguity above was resolved as (b)

The rule as written was ambiguous about a player DEPARTING from rest: "linear through the
middle" combined with "ease IN only on the first step" already implies departure easing, but
the summary line elsewhere in this doc said "two curves only (ease-out on arrival steps, linear
otherwise)", which implies departures snap. Resolved as **(b) — ease-in on departure, ease-out
on arrival, linear while continuing**, which is still two curves plus their combination. Both
readings are now selectable: `movementCurve.departureEasing` in `animation_config.js` turns
departure easing off, which collapses the behaviour to (a).

**The backend decides, the frontend maps.** Continuity is a fact the backend already authored
when it built the step list, so having the client re-derive it from step N+1 would create a
second source for one fact — the same shape as `compute_defender_grid`'s second draw and the
fresh-skeleton screen stats, both of which produced real defects here.
`stamp_movement_curves` (`BackEnd/utils/animation_step_helpers.py`) writes a per-player intent
name to `step.start.movement_curve`, and `resolveMovementCurve` (`animation_config.js`) is the
only place those names become Phaser curves.

**Linear is the default and is not stamped.** Mid-journey steps carry no entry, which is what
keeps a multi-step crossing from pulsing. `resolveMovementCurve` returns `Linear` for a missing
or unrecognised intent, so the safe direction is the default one.

**The continuity population, measured on the played arm, 8 seeds, 63,995 player-steps.** This
is what makes continuity handling load-bearing rather than theoretical:

| class | player-steps | of all | of moving | curve |
|---|---|---|---|---|
| STILL | 34,412 | 53.8% | — | none |
| ONE_STEP_JOURNEY | 12,686 | 19.8% | 42.9% | `ease_in_out` |
| DEPARTING | 5,688 | 8.9% | 19.2% | `ease_in` |
| ARRIVING | 5,688 | 8.9% | 19.2% | `ease_out` |
| CONTINUING | 5,521 | 8.6% | 18.7% | **none — stays linear** |

24,062 curves stamped across 8 games. Departures and arrivals are exactly equal, as they must
be — every multi-step journey has one of each — and that balance is asserted in
`tests/test_movement_curve_continuity.py`.

**A turn boundary counts as REST, not as continuation.** The emitted list is all the renderer
has, and assuming a journey continues past an edge we cannot see is what made
`CONTINUE_FROM_PREVIOUS` unshippable. The conservative failure is one extra deceleration at a
seam rather than a phantom mid-journey pulse.

**Scope: the schema path only, and that turns out to be nearly all of it.** The doc's
nine-site catalogue was stale — there are 34 `ease: "Linear"` sites in production, 26 of them
player movement. Only two are on the schema path. Rather than sweep the rest, the branch that
chooses between them was measured: `AnimationEngine.js:646-647` and `:1094` route a turn to the
schema renderer when `animation_steps` is non-empty, and `:1319` is the inverse. Across 8
played games (3,158 turns):

- **53.9% take the schema path** and are now eased.
- 46.1% take the legacy branch, but **45.9% of all turns carry no `animations[]` either**, so
  the legacy renderers create zero player tweens for them — every major legacy player-movement
  file (`ShotAnimationSystem.js:287,295`, `turnAnimation.js:986`, `freeThrow.js:88`,
  `FreeThrowAnimationSystem.js:330`, `fastBreak.js:3431`) gates on `turnData.animations`. These
  are not easing sites, they are empty turns.
- **0.3% — exactly 1 per game — reach a legacy renderer with content, and all of them are
  OPENING_TIP**, which `openingTip.js` already animates with `Quad.easeOut`.

So the "24 other linear sites" are overwhelmingly unreachable in a played game. Method:
runtime measurement of the backend-side branch condition on the played arm, not browser
instrumentation and not static import reachability — the import graph says every legacy module
is still imported by something and therefore discriminates nothing.

**One known uneased hole inside the schema path**, stated because it is a real inconsistency:
the path-knot branch (`animationPlayback.js:1313-1331`) does not receive the curve, because
easing each knot segment independently would reintroduce per-segment pulsing. It is the
fast-break ball handler only (`fb_drive_step_emitter.py:486-488`) and it is tiny — **20 of
29,583 moving player tweens across 8 games, 0.07%, about 2.5 per game.**

**Cost.** Zero new tweens; the change only sets `ease` on tweens that already existed. The
per-frame delta is one easing evaluation instead of a passthrough: 0.26µs per frame for 10
concurrent tweens, 0.0016% of a 16.67ms budget. That is a microbenchmark of the easing maths
and cannot see compositing.

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

## Defect 4 — unnecessary whole-step freezes (added 2026-09-06)

**Reported by Jamie from live observation.** Multiple steps freeze every player, or all but
one or two, when only one player's motion is actually load-bearing:

- **BIP (baseline inbound pass) turns** — everything freezes for a beat or several. Only the
  inbound passer needs to hold; the other nine should keep moving.
- **Pre-shot movement** — everyone except the shooter, and possibly the shot defender,
  appears to freeze. The rest should stay in organic motion.

### This is NOT defect 2

They produce the same complaint and have different mechanisms:

| | mechanism | fix |
|---|---|---|
| **defect 2** — arrive-and-freeze | player HAS a target, reaches it early, the leftover tail is dead | ~~duration (STRETCH_CAP)~~ → **FILL the tail** (`stamp_arrival_settle`, shipped 2026-09-09). Durations are deliberate and unchanged. |
| **defect 4** — whole-step freeze | player has NO target for the step, so is still for all of it | authoring (continuing targets) |

### RE-MEASURED 2026-09-08 — everything below supersedes the figures this section used to carry

The old numbers (2:1 stillness ratio, 22.9%/15.6% boundary split, "3 consecutive steps is
boundary-specific") predated the converter fix `54a2a9c0e` and both EOQ commits `76318cea4` /
`ea0fd79d9`. Re-measured at HEAD and again at `64f50e9f8` (the commit before the two EOQ
commits) with the same probe, 8 seeds each, one game per process, `PYTHONHASHSEED=0`.

Instrument: emitted backend step data, not the frontend ledger. A step is a whole-step freeze
when every player in `start.coords` has `end.coords` equal to it. Stillness and arrival-tail
player-seconds use `deadAirLedger.js`'s own formulas (`:251-258`, `:299-315`) so the totals stay
comparable to `dumpDeadAir()`. Detector was anti-vacuity checked against a hand-built frozen
step before use.

| | before (`64f50e9f8`) | HEAD | verdict |
|---|---|---|---|
| whole-step freeze, overall | 24.7% (1623/6568) | **25.5%** (1666/6546) | unchanged |
| — at a quarter-final turn | 37.8% (14/37) | **41.4%** (24/58) | unchanged |
| — mid-quarter | 24.6% | **25.3%** | unchanged |
| boundary / mid ratio | 1.54x | **1.64x** | **persists** |
| stillness : arrival tails | 2.12 : 1 | **2.11 : 1** | ratio holds |

**CORRECTION 2026-09-08, same day — the boundary verdict above is WITHDRAWN. There is no
boundary defect.** The rate in this table counts every emitted step regardless of duration.
`deadAirLedger.js:87` deliberately drops steps under `MIN_RECORDED_MS` (60ms) as "not
perceptible as dead air", and putback ball-arc subdivision emits runs of 40ms slices
(`time_elapsed` 0.114 game-sec x 350 = 40ms) in which players are stationary BY DESIGN. Those
slices concentrate at boundaries. Filtering to perceptible steps only:

| | all steps (above) | perceptible >=60ms |
|---|---|---|
| overall | 25.5% | **24.2%** (1487/6137) |
| boundary | 41.4% | **27.7%** (13/47) |
| mid-quarter | 25.3% | **24.2%** (1474/6090) |
| ratio | 1.64x, z=2.82, p=0.005 | **1.14x, z=0.55, p=0.58** |

**The boundary elevation dissolves once sub-perceptible slices are excluded.** The reading-(ii)
verdict was an artifact of the metric, not a finding about the period-end path. Neither reading
(i) nor (ii) is supported: there is no measurable boundary component left to fix. Quote the
perceptible column. The remaining defect is the uniform ~24%.

Lesson, and it is the same one as item 16: the instrument had a threshold for a reason and I
dropped it to match the brief's wording. The 60ms floor was not incidental — it is the
difference between "the court is frozen" and "this 40ms slice of a shot arc has no footwork".

**Boundary is nonetheless the small half of the problem.** Only 58 of 6,546 steps are at a
quarter-final turn. Even at 41.4% that is 24 frozen steps against 1,642 mid-quarter. Whatever
the boundary path does wrong, fixing it buys ~1.4% of the total. The uniform ~25% is the work.

**The absolute level is higher than the old figures and the two are not comparable.** The old
22.9%/15.6% came from the EOQ trace harness; this probe reports 41.4%/25.3% on the same
definition in words. Both arms here used one probe, so the before/after *delta* is sound; the
absolute levels should be quoted from this table and the old ones not quoted at all.

### Jamie's report is half confirmed and half refuted

Freeze rate by turn type at HEAD, 8 seeds:

| | frozen / steps | rate |
|---|---|---|
| `PUTBACK_MAKE` | 378 / 447 | **84.6%** |
| `PUTBACK_MISS` | 111 / 134 | **82.8%** |
| `SIDE_INBOUND` (SIP) | 570 / 855 | **66.7%** |
| `BASELINE_INBOUND` (BIP) | 439 / 1580 | 27.8% |
| `DEAD BALL` | 71 / 493 | 14.4% |
| `MAKE` | 45 / 397 | 11.3% |
| `FOUL` | 37 / 677 | 5.5% |
| `MISS` | 2 / 587 | 0.3% |
| `HCO` | 1 / 569 | 0.2% |
| `DREB` | 0 / 365 | 0.0% |

By phase, `OREB` is 489/643 = **76.0%**.

- **BIP: confirmed as a real offender, but it is not the worst.** It is third by rate and
  second by volume. SIP is 2.4x worse by rate on a path nobody has mentioned.
- **Pre-shot: REFUTED as defect 4.** `MISS` 0.3%, `HCO` 0.2%, `MAKE` 11.3%. Pre-shot steps
  almost always author motion for somebody. What Jamie sees there is defect 2 — players who
  have targets, reach them early, and stand in the tail. Do not sweep the sentinel at it; it
  will not move.
- **The biggest single offender is the putback family, which no one had flagged.** Putbacks
  carry no skeleton by design (`turn_manager.py:5410`, `:5424`), so `oreb_step_emitter.py`
  builds their steps by copying start coords to end coords at eight sites (`:296`, `:325`,
  `:398`, `:413`, `:485`, `:527`, `:590`, `:604`) and never touches `build_pass_step`. It is
  entirely outside the sentinel mechanism.

### The 3-consecutive-dead-steps case: still occurs, and the old reading was wrong

92 turns at HEAD (88 before) contain a run of 3+ consecutive whole-freeze steps; runs reach 12.
The doc previously recorded this as 1-of-46 at boundaries and 0-of-4,743 mid-quarter and called
it boundary-specific. **That is refuted.** The runs are overwhelmingly mid-quarter and
overwhelmingly `PUTBACK_MAKE` / `PUTBACK_MISS` in the `OREB` phase. It is a putback phenomenon,
not a period-end one. Worst observed: a 13-step `PUTBACK_MAKE` turn with 12 consecutive frozen
steps.

### The fix already exists and has a precedent

The first animation change of this project (2026-09-04, `709ba4110` "Invert the freeze
default in build_pass_step") introduced the `CONTINUE_FROM_PREVIOUS` sentinel in
`BackEnd/utils/transition_bridge.py`: off-ball players continue toward their previous
targets rather than freezing when no new target is authored. It was wired into
`after_steal_fast_break_step_emitter.py:448` and `fb_drive_step_emitter.py:405`.

**That default was never swept to the other emitters.** BIP still freezes by default — the same
defect, on the paths nobody was building at the time. This is the pattern behind nearly every
defect found on 2026-09-06.

### Emitter census (2026-09-08)

The sentinel is not something an emitter names. `grep -rn 'CONTINUE_FROM_PREVIOUS' BackEnd/
tests/` returns five hits, all inside `transition_bridge.py` (`:707`, `:710`, `:762`, `:778`,
`:810`). It is the **default value of `build_pass_step`'s `continuing_targets` parameter**
(`transition_bridge.py:761-763`). So an emitter gets continuation by calling `build_pass_step`
and saying nothing, and freezes by passing an explicit value.

Every `build_pass_step` call site, by AST (not grep), with what it passes:

| call site | `continuing_targets` | `previous_step` |
|---|---|---|
| `after_steal_fast_break_step_emitter.py:448` | default → **continue** | `steps[-1] if steps else None` |
| `fb_drive_step_emitter.py:405` | default → **continue** | `steps[-1] if steps else None` |
| `dynamic_hct_step_emitter.py:1334` | `continuing_targets` (authored) | not passed |
| `transition_bridge.py:899` | `lane_targets` (authored) | not passed |
| `transition_bridge.py:984` | `other_targets` (authored) | not passed |
| `transition_bridge.py:1349` | `setup_coords` (authored) | not passed |
| `transition_bridge.py:1499` | **explicit `None` → freeze** | not passed |
| `dynamic_hct_step_emitter.py:1510` | **explicit `None` → freeze** | not passed |

**A trap for the fix brief: the default alone is not enough.** Continuation is derived by
`_continuing_targets_from_previous_step(previous_step=...)` (`transition_bridge.py:810-814`),
and `previous_step` itself defaults to `None`. A call site that takes the sentinel default but
passes no `previous_step` gets an empty target map and freezes anyway. Only the two sites that
pass `steps[-1]` actually continue. Sweeping the sentinel without also threading `previous_step`
reproduces the defect while looking fixed — which is the failure mode
`tests/test_fb_step_builder_call_sites.py` was written against.

Emitters that never call `build_pass_step` are outside the mechanism entirely and freeze by
copying start coords into end coords. Ranked by measured freeze rate, this is the sweep order:

1. **`oreb_step_emitter.py`** — putbacks, 84.6%/82.8%, `OREB` phase 76.0%. Freeze-by-copy at
   `:296`, `:325`, `:398`, `:413`, `:485`, `:527`, `:590`, `:604`. Largest offender; also the
   most dangerous to change (see blast radius).
2. **`transition_bridge.py:1390` `build_sip_animation_steps`** — SIP, 66.7%. Its pass step is
   one of the two deliberate freezes; see below.
3. **`transition_bridge.py:1202` `build_bip_animation_steps`** — BIP, 27.8%. Jamie's report.
4. `skeleton_step_emitter.py` (9 freeze-copy sites), `ft_step_emitter.py` (3),
   `fb_outlet_pass_step_emitter.py` (3) — lower measured rates.
5. `covert_release_step_emitter.py`, `dreb_step_emitter.py`, `dynamic_fcp_step_emitter.py`,
   `hct_step_emitter.py`, `rim_runner_step_emitter.py`, `triangle_step_emitter.py` — no
   freeze-by-copy sites and no `build_pass_step`; `DREB` measures 0.0%.

### The two deliberate freezes, named

`709ba4110`'s own message: "Fixes the two call sites that never decided (after_steal,
fb_drive); leaves the two deliberate freezes untouched." Both pre-date it, confirmed by
`git show 709ba4110^` — `transition_bridge.py:1429` (now `:1499`) and
`dynamic_hct_step_emitter.py:1516` (now `:1510`). The commit touched four files and
`dynamic_hct_step_emitter.py` was not among them.

1. **`transition_bridge.py:1499` — the SIP inbound pass (SF→PG).** Stated in-line: "No
   continuing_targets → other 8 stationary at their step 2 end coords." Correct *as a decision
   the caller states*, which was the point of the inversion. **But it is not correct as
   behaviour, and it should not be treated as settled**: SIP measures 66.7% whole-step freezes,
   the second-worst family in the game. A dead-ball inbound is precisely when the other eight
   should be jockeying for position. Flagging it rather than protecting it.
2. **`dynamic_hct_step_emitter.py:1510` — the HCT attack-basket dish pass**
   (`metadata_reason="hct_ab_dish"`). This one is genuinely correct. The dish is a short, fast
   pass at the end of a drive the previous step already resolved; the drive step authored
   everyone's destinations and the dish occupies a fraction of a second. Continuing off-ball
   targets across it would re-drift players who have just arrived. Leave it.

### Acceptance

`dumpDeadAir()` before and after. Player stillness should fall substantially; arrival tails
should be **unchanged** (that is defect 2's territory, and if tails move the change reached
further than intended).

## STOP — the sentinel cannot reach the top three families (measured 2026-09-08)

**The sweep premise "extension, not invention" is wrong for the families that carry the
defect.** Measured before writing any emitter code, and it is the reason none was written.

`_continuing_targets_from_previous_step` (`transition_bridge.py:714-751`) derives targets from
the **previous step's `start.destination` map**, keeping only players with remaining distance.
It invents nothing. So threading the sentinel can revive exactly those players who were already
mid-journey toward an authored destination, and nobody else.

Recovery ceiling on already-emitted data, 4 seeds — of the whole-step freezes in each family,
the share where the previous step held at least one usable destination:

| family | frozen steps | rescuable by the sentinel | prior `destination` map all-null |
|---|---|---|---|
| `SIDE_INBOUND` | 284 | **0 (0.0%)** | 142 |
| `BASELINE_INBOUND` | 209 | 73 (34.9%) | 57 |
| `PUTBACK_MAKE` | 169 | **27 (16.0%)** | 138 |
| `PUTBACK_MISS` | 55 | **10 (18.2%)** | 45 |
| `DEAD BALL` | 34 | 26 (76.5%) | 0 |
| `MAKE` | 21 | 21 (100%) | 0 |
| `FOUL` | 21 | 0 (0.0%) | 0 |

The reason, shown on a real 13-step `PUTBACK_MAKE` chain: step 0 authors 9 movers with 9 usable
destinations and **they all arrive**. Steps 1-12 then carry `destination` maps that are entirely
null with the action map reading literally `['stationary']`. `_stationary_maps`
(`oreb_step_emitter.py:212-216`) writes `destinations = {pid: None}` for all ten, so from step 1
onward there is no target to continue toward. The chain is frozen from its second step and the
sentinel has nothing to read.

Same shape on SIP: step 0 (`sip_setup_walkin`) moves all ten with usable destinations and they
arrive; step 1 (`sip_passer_hold`) nulls every destination; step 2 (`sip_inbound_pass`) carries
10 non-null destinations of which **0 are usable** — each equals the player's own start coord.

**Consequence for the planned commits.** Commit 1 (oreb) would recover 16-18% of that family's
frozen steps. Commit 2 (SIP) would recover **zero**. And the isolated commit overturning the
deliberate freeze at `transition_bridge.py:1499` would also be a **no-op** — that freeze is not
the binding constraint, because step 1's hold step has already nulled every destination before
the pass step is reached. Overturning a deliberate decision for no measurable gain is the worst
available trade.

**What the real fix is.** For SIP, BIP and the putback family the work is to **author** off-ball
destinations in those emitters — where the other eight should be going during an inbound or a
putback — and only then let the sentinel carry them across the following steps. That is
invention, not extension: it decides new positions rather than continuing chosen ones, and it
needs a design pass with the blast radius below in scope from the start. It is a different task
with a different risk profile from the one this brief scoped.

**Clamp risk, quantified for whoever writes that design.** Where continuation targets do exist,
the remaining distances are large: median 16.7 grid units on BIP, 22.1 on `PUTBACK_MAKE`, p90 up
to 51.9, max 73.0. A 0.5-game-second step at cruise pace covers a small fraction of that, so
`_interrupted_coord`-style clamping is load-bearing, not a nicety. Invariant (A4) in the fix
brief is the right thing to have worried about.

## Defect 4 blast radius — the sentinel is NOT cosmetic (measured 2026-09-08)

**Extending continuing targets to off-ball players changes SIM OUTCOMES, not just what is
drawn.** Do not scope the fix as a rendering change.

The propagation path, end to end:

1. Emitted step end coords are committed onto **all ten** players.
   `sync_lineup_coords_from_turn` (`shared.py:3696`) — "align all ten active players'
   `Player.coords` with the same spatial data the frontend uses" — writes
   `player.coords = dict(positions[pid])` in a whole-lineup loop at `shared.py:3815-3821`, and
   `shared.py:3800-3806` states the last step's `end.coords` is authoritative and deliberately
   wins over the overlay maps. Called from `game_manager.py:931`.
2. `Player.coords` is then read by **whole-lineup loops that decide outcomes**, not by named
   participants:
   - **`resolve_over_the_back_foul` (`shared.py:878`)** loops the entire opposing lineup at
     `:903-910`, takes the nearest by `player.coords`, and at `:911` returns `None` when
     `nearest_distance > 4`. Only if it does not return does `:919` draw
     `otb_roll = random.randint(1, 100)` — and `random` in this module is the seeded sim RNG
     (`shared.py:2`, `from BackEnd.utils.sim_random import sim_rng as random`). Its return
     names `foul_team`, `foul_player` and `victim`. Live: called at `shared.py:974` and
     `game_manager.py:1139`.
   - **`resolve_offensive_rebound` (`shared.py:951`)** loops the entire `def_lineup` at
     `:1032-1043` and picks `nearest_defender` by distance from the shooter — i.e. off-ball
     defender coords name who contests the putback. Live: `turn_manager.py:5358`.
3. Measured, 4 seeded games, 243 `resolve_over_the_back_foul` calls: **70.4% return early with
   no draw** and 27.2% proceed to the roll. **19.8% sit within ±1.0 grid unit of the 4.0
   threshold** — one unit of off-ball movement flips them. Median nearest distance 6.53.

So this is a **draw-count change: SPC principle 8 territory.** The fix brief must carry the
poison-stash test, an equiv-v3 arm, and a re-cut reference — the same treatment the emission
half of the EOQ fix needed.

**What does NOT propagate**, so the brief does not over-scope: `compute_defender_grid`
(`animator.py:1241`) takes `skeleton, off_lineup, def_lineup` and computes defender geometry
from the *skeleton* on a deep copy, explicitly "PURE, sim-safe" (`:1242-1254`). It does not
read `Player.coords`. The interception contest is therefore not on this path.

**The decision rule the brief needs, stated now while we are honest.** Numbers will move. The
rule cannot be "did numbers move" — it must be:
- Whole-step freeze rate falls on the families swept, and arrival tails are unchanged.
- The OTB-foul *rate per rebound* moves within the range implied by the ±1.0-of-threshold
  population (19.8%), and does not move in a direction that makes fouls monotonically rarer —
  continuing players toward their previous targets should if anything put more bodies near the
  glass, not fewer.
- `DREB` stays at 0.0% freezes and its outcome distribution is untouched, since no DREB emitter
  is being swept.
An unexplained move outside those is "we broke something", not "players are in more plausible
places".

## Defect 4 — CLOSED 2026-09-08, and NOT by the fix this section was written to justify

The whole document above builds toward extending `CONTINUE_FROM_PREVIOUS`. That is not what
shipped, and the reason is worth keeping: the sentinel could not reach the top three families
(the "STOP" section above), and the blast-radius section established that it would have changed
sim outcomes rather than only what is drawn. What shipped instead is a **render-space idle**,
which changes nothing but the payload's `flourish` key.

**The framing was also wrong by 2.8x.** "Whole-step freeze" only counted a step where all ten
players were still, so a step with three moving and seven standing scored as not frozen. The eye
sees seven dead players. Per-player stillness on the played arm is **45.6%** (64,669 of 141,738
player-steps) against the 16.3% whole-step rate the workstream ran on. Defect 4 was measured
against the wrong denominator from the start.

### Families covered

Stamped in commit order. Every one gates on the INDIVIDUAL player's `start.coords` equalling his
`end.coords` for that step, above a 60ms perceptibility floor (`deadAirLedger.js:87`), under a
density cap of 6 of 10 with selection ordered by how long the player has been still so nobody
flickers in and out between steps.

| family | still player-steps / 8 played games | stillness | style, amplitude | excluded role |
|---|---|---|---|---|
| `hco_still` | 52,813 (82% of all of it) | 44.6% | resolver's geography-aware pick, 0.6 | — |
| `free_throw` | 1,930 | 82.1% | `survey_rock` ~3.5in, 0.6 | the shooter |
| `inbound` (SIP + BIP) | 3,523 + 1,524 | 66.7% / 60.0% | `jockey` ~4in, 0.6 | the inbounding passer |
| `make_hold` | 968 stamps | — | `survey_rock` ~3.5in, 0.6 | — |
| `oreb` | 1,705 | 62.0% | `jockey` **~7in, 1.0** | putback shooter, second rebounder |
| `fcp` | 1,587 | 48.2% | `shuffle` ~4in, 0.6 | ball handler |
| `hct` | 2,730 | 44.9% | `shuffle` ~3.5in, 0.5 | ball handler |

`oreb` is the only family that ships without the -40% still-player reduction. Boxing out is a
legs-and-hips contest between men leaning on each other, not a wait, so it takes the widest
amplitude in the set. Every style and amplitude is a tunable under
`animation_config.js` `flourish.idleWander.byFamily`.

One grid unit is almost exactly one foot (the 100x50 grid maps to a 94ft x 50ft court), so those
amplitudes are readable as real weight-shift distances.

### The two deliberate exclusions

**MISS — not stamped, and the number going down would be the defect getting harder to see.** It
is the largest content-free frozen family at 30.9%, and it is the one place an idle would make
things worse. A miss is LIVE play: boards crashing, guards leaking out. If those steps are
frozen the defect is that *nobody is sprinting when they should be*, and looping an idle over a
rebound scramble papers over an authoring gap. Logged as `bugs.md` item 19, needing its own
diagnosis of what those steps are FOR. Same error class as putting the sentinel on ball-carrying
steps: right mechanism, wrong moment.

**The putback rattle hold — not stamped, and the 60ms floor is what excludes it.** The putback
chain holds every player still for 8 rattle hops while the ball is on the rim
(`oreb_step_emitter.py` `overlay_players={}`, "putback: all players hold"), 62% of them carrying
the ball. That stillness is correct. `RATTLE_HOP_GAME_SECONDS` is 40/350 game-seconds, which
resolves to exactly 40.0ms of wall clock; measured, all 46 rattle hops per 8 games sit under the
floor and 0 of 46 are candidates. Verified rather than assumed, because it was a floor and not
an explicit filter doing the work, and guarded twice — once on the arithmetic and once on the
constant — so a timing change elsewhere cannot silently make the hold stampable. The LONGER
ball-on-rim beats that do clear the floor (`rattle_settle`, `bank_settle`, `bank_graze`,
`bounce`) are stamped on purpose: men watching a ball rattle are shifting their weight.

### What a "live ball" test could and could not settle

Before widening to FCP and HCT I built a discriminator for the item 19 error class — is the ball
in flight, loose, or attached to a moving owner on the steps that carry still players? It does
not work as a veto, and the reason is instructive. `free_throw` measures 64% "live ball" by that
test, because the shooter's own motion marks the step live while the other nine legitimately
stand — and free throws are the family Jamie has already eye-approved. So the metric cannot
distinguish an approved case from a proposed one. MISS stays excluded on the specific argument
about rebound scrambles, not on this number.

(The first version of that discriminator read `ball["x"]`, which exists in none of the three
`BallState` shapes, and returned 100% "unknown" — a vacuous instrument that would have been
reported as evidence. The anti-vacuity habit caught it.)

### Gate

The idle writer only ever writes `step.start.flourish`, and the gate is exact rather than merely
weaker than byte-identical: on all 8 seeds, played arm, **draw counts and step counts identical**,
and `flourish` the only key permitted to differ. It held on every commit. `_pressure_step_state`
also differs, and that was worth chasing rather than waving through: its `schema_projection` is a
complete snapshot of the emitted step during the Step 8 migration, so walking its 1,069 leaf
paths was necessary to show 308 differ and **zero differ without `flourish` in the path**.

That ordering is load-bearing, not incidental. The pressure stamp has to run BEFORE
`_project_pressure_step` or the snapshot is stale and the flourish vanishes the moment
`projection_source` flips to `"formal"`. Guarded structurally on source order, since no unit test
on the helper can see it.

Because the gate holds, equiv-v3 is not required and SPC principle 8 does not apply — verified,
not expected. Determinism: two playbacks of the same seeded game are byte-identical, true only
after `e0768409f` removed the heartbeat's `Math.random()`.

Stamps rose 45,066 -> 48,229 across 8 games. **Frame time did not move in shape**: the density cap
bounds concurrent tweens at ten regardless of stamp count, and a wander REPLACES a player's
heartbeat rather than stacking on it, so cost is 0.294 us/frame at the shipped cap of 6 (0.0018%
of a 60fps budget) against 0.067 at cap 0. That figure is the CPU cost of the idle update path
against a stubbed tween manager — it cannot see compositing or draw-call cost and is not an
end-to-end frame time.

### What is still open

Nothing in defect 4 itself. The expensive work it kept deferring is untouched and now has to be
justified on its own: deleting the content-free beats, and authoring real off-ball destinations.
Jamie's eye decides whether either is still needed. MISS (item 19) is the one family that
certainly needs one of them.

## Revised sequence

1. ~~**Fix the converter**~~ — DONE, commit `54a2a9c0e`. The offense build now reads `spot`.
2. **Whole-step freezes (defect 4)** — extension of an existing, tested mechanism; measured
   at ~2× the arrival-tail problem; ranked above defect 2 on both size and cost.
3. ~~**Continuity-aware easing (defect 1)** across all nine hardcoded sites, two curves only
   (ease-out on arrival steps, linear otherwise).~~ **SHIPPED 2026-09-08 — see the
   CONTINUITY-AWARE section above.** Two corrections to this line as written: there were 34
   linear sites, not nine, and the "linear otherwise" reading was resolved as (b) — departures
   ease too, selectable via `movementCurve.departureEasing`. Scoped to the schema path, which
   measured as 53.9% of turns and effectively 100% of rendered player movement.
4. **Arrive-and-freeze (defect 2)** — ~~STRETCH_CAP experiment~~, judged by eye. **RE-MEASURED
   2026-09-08 and confirmed as the largest remaining item: 524.5 s/game of dead tail, 30.7% of
   moving-sprite time.** STRETCH_CAP never existed in the tree, and the measured tail shape
   favours FILLING the tail over stretching the duration — see the re-measured section under
   "2. Arrive-and-freeze" and the ranking table.
5. **Then** decide what keys easing character on HCO, with the archetype question reopened
   on correct inputs.
6. **Overlap stagger, timing variation (defect 3), emphasis hierarchy** — as in the main
   document.

Not on this list: the End-of-Quarter animation defect. That is a bug, not craft — it is
logged in `bugs.md` and needs a trace, not a design pass.

## MISS frozen steps — DIAGNOSED 2026-09-08, and it is SMALL

`bugs.md` item 19 left MISS open as "30.9% of content-free frozen steps, the largest single
family". Diagnosed on 8 played games (`scratch_tails_miss.py`).

**FIRST, A KEYING CORRECTION.** The 30.9% cannot be reproduced by any turn-side keying, and
item 19's own attribution note explains why: its per-family figures came from
`offensive_state`, which lives on `game.game_state` (`opening_tip.py:115`) and is not carried
on the turn dict. So "MISS" there and `result_type == "MISS"` here are different populations,
and the two numbers are not a before/after pair. Everything below is keyed by `result_type`.

**WHOLE-STEP FREEZES BARELY EXIST HERE: 3 of 522 MISS steps (0.6%).** The stillness is
partial, which is exactly the understatement item 19 recorded for defect 4 generally — the mean
MISS step has **4.02 of 10 standing**, with a mode at 5 (19.5% of steps) and only 6.3% of steps
having everybody moving.

**WHERE IN THE TURN**, read off the ball rather than off a step index, since MISS turns run 5
to 16 steps and a quintile is not comparable between them:

| phase | steps | still/10 | mean dur | share of MISS wall time |
|---|---|---|---|---|
| 1 ball in the shooter's hands | 273 (52.3%) | 3.4 | 272 ms | 58.3% |
| 2 ball in flight | 97 (18.6%) | 4.6 | 173 ms | 13.2% |
| 3 on the rim (`rattle_hop`, `bank_graze`) | 82 (15.7%) | 5.4 | **76 ms** | 4.9% |
| 4 off the rim (`bounce`) | 51 (9.8%) | 5.3 | 300 ms | 12.0% |
| 5 the next break | 19 (3.6%) | **0.1** | 784 ms | 11.7% |

> ### ⚠ THE MISS NUMBERS BELOW WERE MEASURED ON THE SIM ARM. RE-MEASURED 2026-09-09.
>
> This whole section ran through the `PLAYED=1` shim bug (bugs.md items 29 and 31). MISS is the
> family the bug distorts MOST, because HCO is 83% of played steps and near-absent on the sim
> arm, so the MISS population measured here was a genuinely different population — 522 steps
> across 8 games instead of 6,129.
>
> | claim | published (SIM) | corrected (PLAYED) | factor |
> |---|---|---|---|
> | total MISS wall time | 15.9 s/game | **247.0 s/game** | 15.5x |
> | MISS steps | 65.2/game | 766.1/game | 11.7x |
> | still MISS player-steps | 2,098 | 30,930 (3,866/game) | 14.7x |
> | frozen MISS steps | 3 across 8 games | 928 across 8 games | 309x |
> | frozen AND content-free | 1 across 8 games | 636 (79.5/game) | 636x |
> | the visible loose-ball slice | ~79 player-steps/game over 4.8 s | **782/game over 39.8 s** | 9.9x / 8.3x |
> | the `bounce` empty beat | 51 steps x 300 ms, 12.0% of MISS wall | 455 steps (56.9/game) x 300 ms, 6.9% of MISS wall | 8.9x |
>
> **THE DECISION THIS REVERSES.** MISS was ranked 4th of 4 — below the `bounce` beat and below
> the design work — on the strength of "4.8 s per game, the smallest remaining item". The real
> visible slice is 39.8 s per game, which puts it ABOVE the `bounce` beat (17.1 s/game corrected)
> and makes it the largest remaining defect after defect 2. The ranking table below is corrected.
>
> **WHAT SURVIVES UNCHANGED, and it is the important part.** The destination split still reads
> **0.0% `elsewhere`** on the played arm (56.9% no destination, 43.1% already there, against a
> published 50.2/49.8/0.0). So the diagnosis is untouched: this is an AUTHORING ABSENCE, not a
> tail or a mistimed tween, and no duration or curve change can reach it. The instruction not to
> stamp an idle over a live rebound also stands. Only the SIZE was wrong — but it was wrong in
> the direction that changes what we do next.

**Total MISS animation is 247.0 s per game** (published as 15.9 s/game off the sim arm; see the
banner above). It is not an order of magnitude smaller than defect 2: against defect 2's
corrected 1,849.6 s/game of dead tail it is roughly one part in seven.

**IT IS AN AUTHORING ABSENCE, NOT A RENDERING FAILURE.** Of 2,098 still MISS player-steps,
**50.2% have no authored destination at all and 49.8% are already standing on the destination
they were given. Exactly 0% have a destination they have not reached.** So no tail, no
mistimed tween, nothing a duration or curve change could touch — the engine explicitly says
"do not move".

**WHO IS STILL**, by authored `start.action`, cross-tabulated against phase:

| action | pre-release | in flight | on rim | off rim | total | still-rate |
|---|---|---|---|---|---|---|
| `stationary` | 496 | 319 | 439 | 245 | 1,499 (71.4%) | 86.5% |
| `guard_offball` | 289 | 40 | 5 | 25 | 359 (17.1%) | 35.0% |
| `pass` / `receive` | 27 | 90 | 0 | 0 | 117 | ~99% |
| `handle_ball` | 44 | 0 | 0 | 0 | 44 | 30.3% |
| `shoot` | 42 | 0 | 0 | 0 | 42 | 100% |
| `cut` / `sprint` | 6 | 0 | 0 | 2 | 8 | <2% |

### The basketball verdict, per sub-population

- **DEFENSIBLE — the shooter (`shoot`, 100% still, 42).** A shooter planted watching his own
  release is real basketball. Leave it.
- **DEFENSIBLE — `pass` / `receive` (117, ~99% still).** A passer who has just released and a
  receiver squaring up are both legitimately planted for a beat.
- **DEFENSIBLE — pre-release off-ball (496 `stationary` + 289 `guard_offball`).** 58.3% of MISS
  wall time is still a live half-court set with the ball in the shooter's hands. Men holding
  shape in a set offence, and defenders in help position, are correct. This is ordinary HCO
  stillness that happens to fall inside a turn labelled MISS, and it belongs to defect 4's
  already-stamped territory rather than to a rebound problem.
- **NOT DEFENSIBLE, and this is the real finding — 1,073 off-ball player-steps (51.1% of the
  MISS still population) are authored motionless while the ball is LOOSE.** 1,003 `stationary`
  plus 70 `guard_offball`, spread across ball-in-flight, on-rim and off-rim. Five men on
  average standing through a live rebound is not basketball; boards get crashed and guards leak
  out. **But note the perceptibility split: the on-rim beats average 76 ms** (the 50 ms
  `rattle_hop` sequence, the same deliberate rim hold excluded from the OREB stamping pass and
  below the 60 ms floor), so the genuinely visible slice is ball-in-flight plus off-rim —
  **629 player-steps, about 79 per game, over 4.8 s of wall time.**
- **ALREADY CORRECT — the next break (phase 5, 0.1 of 10 still).** When the engine does author
  a transition it authors it well. That is the proof that the loose-ball stillness is a gap in
  authoring rather than a limit of the mechanism.

**THE FIX IS AUTHORED MOVEMENT — rebound-crash and leak-out destinations for the ~79 visible
loose-ball player-steps per game.** Item 19's instruction stands and the measurement now
supports it: **do not stamp an idle here.** An idle loop over a live rebound would make the
number go down while making the defect harder to see, and the honest fix is the expensive one
this workstream has been deferring. At 4.8 s per game it is also, on measured size, the
*smallest* remaining item — see the ranking below.

**NEWLY SURFACED, nobody has logged it:** the `bounce` beat is **51 steps of 300 ms carrying
zero ball motion, zero sound and zero announcement**, with 5.3 of 10 standing — a content-free
perceptible 300 ms pause at the end of a miss, 12.0% of all MISS wall time. That is a
step-deletion candidate rather than a stamping or authoring one, and it is the clearest
instance of "an empty beat" the workstream has measured.

## END-OF-TURN FROZEN TAILS — measured 2026-09-09 **[PLAYED]**, not yet acted on

The one clean, previously unmeasured quantity to come out of the 2026-09-09 sessions, and the
explanation for Jamie's "all players hold for a beat on BIP". His hypothesis was that the pause
sits at the BIP→HCO transition. It does — but there is no between-turns mechanism. **Turns end
with fully-frozen steps**, and that tail is the pause.

| turn type | turns ending frozen | mean tail | s/game |
|---|---|---|---|
| HCO | 60.1% | 1.77 steps, 375 ms | **37.90** |
| FREE_THROW | 100% | 6.43 steps, 976 ms | 23.17 |
| SIDE_INBOUND | **100%** (212/212) | 2.00 steps, 526 ms | 13.93 |
| OREB | 61.1% | 4.94 steps, 715 ms | 8.85 |
| BASELINE_INBOUND | 37.9% | 1.96 steps, 524 ms | 1.64 |
| FCP / HCT / FAST_BREAK | 23-28% | ~1 step, 300-430 ms | 2.50 combined |
| **DREB** | **0%** (0/390) | — | 0.00 |

**≈88 s/game of court-wide frozen tail at the ends of turns.** It is NOT BIP-specific — that is
the larger finding. And **DREB proves it is not inevitable**: 390 turns, none of them ending
frozen.

THE SEAM ITSELF IS CLEAN, so this is the whole explanation: across every turn-to-turn pair,
coordinate continuity is exact (0.0% jumps, mean 0.00 ft) and **no `turn_stop` payload anywhere
carries a hold** (0.0 ms summed across all seams).

CAVEAT, and it is the important one: this is measured in the same frozen-step units that invert
against the human observer (see banner). It explains a specific complaint Jamie actually made,
which is why it is recorded — but its **size must not be used to rank it** against anything else.

## ~~RANKING AT 2026-09-08, by measured size~~ — STRUCK 2026-09-09

> **This ranking is withdrawn, not corrected.** Every item in it was sized in still-player-steps
> or in dead/frozen seconds derived from them, and those units invert against a human observer
> (see the banner at the top of this document and bugs.md item 33). Two of the four entries have
> also since been retracted on their own merits: MISS's loose-ball figure was 82% correct
> basketball (bugs.md item 32), and defect 2's headline was measured on the wrong arm.
>
> The table is kept below **struck through, for history only**. Do not re-order it and do not
> quote it. The next ranking of feel work has to come from Jamie at the screen until there is an
> instrument that tracks perception.

### ~~Struck table, retained for history~~

Supersedes every earlier ordering in this document. The prior ordering was written before the
converter fix, before defect 4 closed, and before any of these quantities existed.

| rank | item | measured size | cost of fix |
|---|---|---|---|
| ~~1~~ | ~~defect 2, arrive-and-freeze~~ | ~~1,849.6 s/game dead tail~~ **[PLAYED]** (this doc originally published 524.5 **[SIM]**) — but the unit inverts, see banner | low if FILLED; high if STRETCHED |
| ~~2~~ | ~~sequence item 5 / 6 — easing character, archetypes, stagger, emphasis~~ | never sized; **[N/A]** | design |
| ~~3~~ | ~~MISS loose-ball stillness (item 19)~~ | ~~782 player-steps/game over 39.8 s~~ **[PLAYED]** — **RETRACTED, 82% of it was correct basketball** (bugs.md item 32); the genuine residue is 6.9 s/game | n/a, retracted |
| ~~4~~ | ~~the `bounce` empty beat~~ | 455 steps (56.9/game) × 300 ms, content-free, 17.1 s/game **[PLAYED]** | low — deletion, step counts are principle 8 territory |

~~**Defect 2 is not close to being closeable**~~ — it is the largest measured quantity in the
workstream and 29.4% of its tails are visible pauses.

**~~MISS comes back small enough to downgrade~~ — RETRACTED 2026-09-09.** That sentence was
written off a sim-arm measurement. On the played arm MISS carries 782 visible loose-ball
player-steps per game over 39.8 s, 8.3x what was published, which puts it above the `bounce`
beat rather than below everything. Its cheap fix is still forbidden for the reason given — an
idle loop over a live rebound would shrink the number while hiding the defect — so it remains
expensive, but it is no longer small, and "expensive AND small" was the whole argument for
deferring it.

Sequence items 5 and 6 were out of scope for this measurement and are design rather than defect
work. With defect 1 shipped and defect 4 closed they remain a large body of work, but they are
**no longer clearly the largest remaining item**: MISS now outranks them on measured size, and
the two defects ahead of them are defect 2 and MISS.

---

## ARRIVAL-TAIL FILL (DEFECT 2) — SHIPPED 2026-09-09

> ## ⚠ EVERY NUMBER IN THIS SECTION WAS RE-MEASURED 2026-09-09. READ THIS FIRST.
>
> The figures originally published here were measured on the **SIM arm** while being labelled the
> played arm. `scratch_playedarm.py::use_played_arm(gm)` is a **no-op unless `PLAYED=1` is in the
> environment**; every probe called it, none set the variable, and none checked its return value.
> See bugs.md items 29 and 6d.
>
> **The fix itself is unaffected and its gate still passes** — re-run on the real played arm, 26
> key paths compared, `start.flourish` is the only one that differs, draws / step counts / turn
> counts identical on all 8 seeds, 0 delay mismatches, 0 sub-floor stamps. What was wrong was the
> SIZING, and it was wrong in the direction of understating the problem:
>
> | | as published (sim arm) | **corrected (played arm)** |
> |---|---|---|
> | dead tail per game | 703.4 s | **1,849.6 s** |
> | share of moving-sprite wall time | 31.7% | **38.8%** |
> | moving player-steps | 38,193 | 90,730 |
> | player-steps carrying a tail | 19,651 | 49,550 |
> | median tail | 145 ms | 192 ms |
> | total animation wall time / game | 364.4 s | 776.6 s |
> | `arrival_settle` stamps (8 games) | 10,782 | **25,038** |
> | idle stamp baseline (8 games) | 28,836 | **57,522** |
>
> **The design conclusions survive, and the one-line gate is MORE justified than before, not
> less.** Dead time is no longer concentrated in one continuity class — it spreads across all
> four (one-step journeys 38.3%, arriving 29.0%, continuing 18.6%, departing 14.0%, versus the
> 71.4% / 13.0% / 8.0% / 7.5% published). A rule keyed on continuity class would therefore have
> missed even more of the problem than originally argued. The shipped `minTailMs` of 150 now
> catches **59.0%** of tails rather than 49.3%, and the sub-60ms hard exclusion covers 15.6%
> rather than 24.7%.
>
> The 48,229 baseline the brief quoted was **right all along**; it was this session's 28,836 that
> was fiction. `hco_still` measures 44,520 across 8 played games against the 40,175 reported by
> the widening task, the residual being the seeded plays catalogue and the intervening
> `HCO_PASS_SAFETY_BASE` 175 -> 150 change (11bbaa16a).
>
> Frame times are **unaffected** — they were measured in a node harness that never touched the
> Python arm.
>
> Corrected figures are the ones to use. The tables further down this section are left as
> published, for the record of what was claimed.


> ### WHERE THIS LANDED, AND HOW TO REVERT IT
>
> **The commit message will not tell you, so read this before touching it.** The defect-2 fix was
> swept into **`a0d509173 "adjusted drive stop logic"`** by a concurrent process mid-stage, and
> that commit was pushed before it could be separated. History was left alone rather than
> force-pushed over a shared branch with another process actively writing to it.
>
> `a0d509173` is a **94-file commit** that ALSO contains **unrelated drive-stop logic**
> (`BackEnd/engine/attack_drive_clearance.py`) and ~85 court images. **Reverting the commit would
> revert all of that too.** A revert of defect 2 must therefore be done **by file list**, not by
> `git revert a0d509173`:
>
> | file | what it contributes |
> |---|---|
> | `BackEnd/utils/animation_step_helpers.py` | `stamp_arrival_settle` + `_arrival_tail_ms` and their constants |
> | `BackEnd/models/game_manager.py` | the single `stamp_arrival_settle(...)` call in `_append_turn` |
> | `FrontEnd/static/js/phaser/animation/arrivalHeartbeat.js` | the `delayMs` parameter and the `applyIdleWanderNow` split |
> | `FrontEnd/static/js/phaser/animation/flourishes.js` | the `arrival_settle` branch: `enabled` and `minTailMs` gating, `delayMs` pass-through |
> | `FrontEnd/static/js/phaser/animation/animation_config.js` | the `arrival_settle` tunables |
> | `tests/test_arrival_settle_fill.py` | the four poisoned guards |
> | `.gitignore` | `.arm/` probe output |
>
> **THE PRACTICAL ROLLBACK IS NOT GIT.** Set `flourish.idleWander.byFamily.arrival_settle.enabled`
> to `false` in `animation_config.js`. That is a one-line, no-deploy-risk kill switch, and it
> leaves the still-player wanders shipped in 14cbd4e50 / 844f53ece completely untouched.
>
> #### The kill switch is VERIFIED, not assumed
>
> An untested off switch is not a rollback path. `scratch_killswitch.mjs` drives the **real
> `runFlourish` dispatch** in `flourishes.js` — not a re-implementation — with one process per arm,
> because `animation_config.js` reads `globalThis.animation_config` once at module load and two
> arms in one process would share whichever config loaded first.
>
> | | `enabled: true` | `enabled: false` |
> |---|---|---|
> | arrival fills fed to `runFlourish` | 5 | 5 |
> | arrival wander tweens created | 3 | **0** |
> | arrival delayed calls scheduled | 3 | **0** |
> | still-player wanders fed | 5 | 5 |
> | still-player wander tweens created | **5** | **5** |
> | still-player delayed calls scheduled | 0 | 0 |
>
> So `enabled: false` renders zero arrival fills and schedules zero delayed calls, while all five
> still-player families (`hco_still`, `inbound`, `oreb`, `fcp`, `hct`) tween exactly as before —
> the rollback cannot take working behaviour down with it. The ON arm is checked first as an
> **anti-vacuity** control, because "zero fills" is indistinguishable from a harness that never fed
> the dispatch anything. The 3-of-5 figure is the shipped `minTailMs` 150 correctly dropping the
> 80 ms and 120 ms tails.
>
> **Poisoned two ways, both caught:** deleting the `enabled` check outright (switch becomes a
> no-op) → 3 fills render with the switch off, 2 checks fail; and misspelling the family so
> `arrival_settle` never matches the gate → 5 fills render and the threshold check fails too.
> File restored and the harness green again after each.
>
> The fixture seeding is clean in `157f8ff99` and these docs in `0fbc7331d`. Everything the commit
> message *should* have said is in this section.

The largest single item in this workstream by measured size, and the reframe matters more than
the code: **the tail is a deliberate decision, not a bug, and the fix is to fill it rather than
to remove it.**

### The fixture was hiding a third of it

Every game in the harness had been logging `No plays found for motion/set_play, using fallback`.
`plays_collection` was empty in mongomock, so `plays_catalog.all_docs()` returned nothing,
`_get_plays_by_type_and_focus` (`turn_manager.py:3254`) matched nothing, and every possession
took the fallback branch at `turn_manager.py:2969` and hardcoded an `"Inside"` playcall — which
carries no skeleton, so **no off-ball destinations were authored for the four men without the
ball**. That silence had already contributed to the idle_wander "0 fires" reading.

`tests/roster_fixtures.py::seed_universal_plays` now seeds the real catalogue from
`play_skeletons_export.json`: seven plays, four motion (4-1 Motion, 4-1 Flex Motion, 5-0 Motion,
3-2 Motion) and three set_play (Pick & Roll (Lower Wing) / attack, Double Screen For SG /
outside, Base Post Play / inside), each with four skeleton leans carrying real `pos_actions`.
Focus coverage is complete for both types, so the fallback cannot re-trigger.

**The fixture was deflating the defect, not inflating it.** Re-measured across 8 played games:

| | empty catalogue | seeded | change |
|---|---|---|---|
| dead tail per game | 524.5 s | **703.4 s** | +34.1% |
| share of moving-sprite wall time | 30.7% | **31.7%** | — |
| total animation wall time | 278.1 s | 364.4 s | +31.0% |
| moving player-steps | 30,189 | 38,193 | +26.5% |
| player-steps carrying a tail | 15,361 | 19,651 | +27.9% |
| stillness : tails ratio | 2.23 : 1 | 2.25 : 1 | unchanged |
| median tail | 146 ms | 145 ms | unchanged |

The distribution shape is materially identical — sub-60ms 24.8% → 24.7%, ≥300ms 29.4% → 30.8% —
so every design conclusion drawn before the seeding survives. The item is simply larger.

### Where the dead time actually sits

| continuity class | share of all dead time | mean tail |
|---|---|---|
| `ease_in_out` (one-step journey) | **71.4%** | 417 ms |
| `ease_out` (arriving) | 13.0% | 159 ms |
| `continuing` | 8.0% | 141 ms |
| `ease_in` (departing) | 7.5% | 192 ms |

This is why **the gate is one line — tail over a threshold — and not a list of continuity
classes.** A rule aimed at ARRIVING steps would have reached 13% of the problem. The classes
were for sizing; tail size is what decides whether a human can see the pause.

### What shipped

- **`applyIdleWander` gained a `delayMs`** (`arrivalHeartbeat.js`). Implemented as a *deferred
  call*, not a `delay` on the counter tween. The body takes ownership from the heartbeat, snaps
  the sprite to rest and **captures its base positions at call time**; delaying only the tween
  would leave that capture mid-movement and yank the sprite back to a position the player had
  already left. Default 0 calls straight through, so the wanders shipped in 14cbd4e50 /
  844f53ece are unchanged.
- **`stamp_arrival_settle`** (`animation_step_helpers.py`), called from `game_manager._append_turn`
  — the same universal seam the curve stamp uses. It runs there rather than in an emitter because
  it must see every emitter's still-player stamps before it can share their density budget.
- **ONE density cap, shared.** The fill counts idlers already on the step and fills only the
  headroom. Two independent caps would let a step carry the cap twice over, which is precisely
  the "busy court" the cap exists to prevent. Measured: 0 violations, mean idlers/step 3.31 → 4.54.
- **Its own family, `arrival_settle`**, with independent style and amplitude, because a man who
  has just sprinted and stopped decelerates into a settle — a different motion from a man who has
  been standing around. `jockey` at `amplitudeScale` 0.6, `minTailMs` 150.
- **Hard 60 ms floor in the backend** (24.7% of tails), with `minTailMs` as Jamie's tunable on
  top so he can raise the threshold without a backend round-trip. Raising it can only ever stamp
  fewer players, so it can never push the court past the cap.

### Gate

8 seeds, played arm, in-process no-op arm so both arms run byte-identical code. **25 key paths
compared; `start.flourish` is the only one that differs.** `start.coords`, `end.coords`,
`start.tween_durations`, `start.movement_curve`, `_pressure_step_state` and the other 20 are
digest-identical. Draws, step counts and turn counts identical on all 8 seeds. Determinism holds
across two separate processes.

Frame time at cap 3 / 6 / 10: 0.237 / 0.340 / 0.494 µs per frame — **0.0030% of a 60 fps budget
at cap 10**. The delayed path costs the same as the immediate one, because concurrency is bounded
by the ten sprites on court: a delayed start cannot create an eleventh idler, only move *when*
the tenth begins. This is CPU cost of the idle update path against a stubbed tween manager and
cannot see compositing.

Stamp total 28,836 → 39,618 over 8 games.

### Two things for Jamie's eye, and they are the real risks

1. **Does a player who just sprinted and then shifts his weight read as SETTLING, or as
   FIDGETING?** That is the aesthetic failure mode of this change, and it is the *opposite* of
   every previous family — those failed by being too subtle. Bracket `minTailMs` at 60 / 150 /
   300 and `amplitudeScale` at 0.3 / 0.6 / 1.0, and use `enabled: false` for a clean A/B.
2. **With arrival fills on top of the existing still-player wanders, does the court read as
   BUSY?** The density cap is the lever here, not the amplitude.

### Found while gating, NOT fixed here

`hco_still`, `free_throw` and `make_hold` write **zero** stamps on this harness — in both arms,
and with both an empty and a seeded catalogue. `build_skeleton_animation_steps` runs 153 times
per game and returns steps carrying no flourish of any family, so those stamps are *writing
nothing* rather than being stripped downstream. This is a pre-existing defect in the shipped
still-player increment and it affects both gate arms identically, so it does not touch the
result above. It also explains why the brief's 48,229 stamp baseline does not reproduce. Needs
its own diagnosis.
