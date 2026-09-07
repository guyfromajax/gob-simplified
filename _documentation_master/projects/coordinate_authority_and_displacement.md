# Coordinate authority, and displacement as a mechanic

*Written 2026-09-06. Measured claims cite file:line and are marked. Design intent is marked
as such and is not yet built.*

---

## Part 1 — The problem (measured)

### Two representations, and why that is not the bug

GOB holds player positions in two forms:

- **spot names** — `"upper lowPost"`, `"center court"` — semantically meaningful, tunable in
  one place, readable in logs. Authored by the skeleton.
- **coordinates** — `{"x": 86, "y": 32}` — what all geometry actually needs.

`HCO_STRING_SPOTS` converts between them.

**Having both is correct and should be kept.** Names carry play intent; coordinates carry
geometry. The names are a genuine asset.

### The bug is that the conversion has more than one authority

Two readers of the same skeleton use different key lists:

- `BackEnd/engine/defender_placement.py:176-197` — checks `"coords"`, then `"location"`,
  **else hardcodes `{"x": 50, "y": 25}`**
- `BackEnd/engine/phase_resolution.py:4408` — reads `(pa.get("location") or pa.get("spot") or "key")`

The skeleton authors shot location under `"spot"`. The first reader does not look for that
key, so it falls through to a hardcoded court-centre literal. The second reader resolves it
correctly. **Same skeleton, same value, two converters, two answers.**

This is the §1 violation one level up: not a coordinate with two authorities, a *conversion*
with two authorities.

### Measured cost (n=10 games, 905 joined shots, 2026-09-06)

| branch taken by the shooter's shoot step | count | share |
|---|---|---|
| explicit `coords` | 618 | 68.3% |
| named `location` | 122 | 13.5% |
| **neither → hardcoded (50,25)** | **95** | **10.5%** |
| explicit coords, already at centre | 70 | 7.7% |

- 95 of 95 else-branch shots were awarded a value contradicting the authored spot, always in
  the same direction (a three for a two): **+1.90 points/game wrongly awarded**.
- The larger cost is not the points. Because `is_three` *and* shot distance both derive from
  the bad coordinate, these are graded as long-range attempts: **80% miss rate (76/95)
  against 42% (51/121) for correctly-resolved shots.** A post-up at the rim is scored as a
  heave from the logo, roughly 9.5 times a game.
- Why it always reads as a three: court centre sits on y=25, where the arc reaches its
  deepest point at x=64.0 (`shot_geometry.py:12-22, 46-82`). x=50 on that line is behind the
  arc, and mirroring 50 for away offense gives 50 — so it reads as a three for both teams,
  every time.

**Unmeasured scope note:** the same else branch serves *every position* in the animation
build, not just shooters. Off-ball players and defenders whose `pos_action` uses `"spot"`
would also be placed at court centre. Only shooters were measured.

### The two rules that would have prevented it

1. **One converter, in one place.** Every caller uses it. It accepts every key the skeleton
   actually writes.
2. **No silent fallback.** A converter that cannot resolve its input must raise or log
   loudly, never invent an answer. `else: coords = {"x": 50, "y": 25}` shipped a hardcoded
   logo shot on 10% of attempts and nobody knew.

Guard it the way the coord contract is guarded — a test that fails when a second converter
appears. That is bounded work with a defined end state, unlike auditing every consumer.

---

## Part 2 — Which coordinate is authoritative (principle)

A shot has two legitimate positions and they are **not** the same fact:

- the **intended** spot — what the play authored (`"upper lowPost"`)
- the **release** position — where the shooter's feet actually were

**Basketball scores on the second.** A play drawn at the elbow that gets shot from two feet
behind the arc is a three. So classification must read the *release* coordinate — which is
exactly what UESS §9.5 already requires: decide from the interrupted end coord, never the
destination.

**The rule:** names are authoring input. All logic — backend and frontend — consumes the
resolved integer coordinate. The name may travel alongside for diagnostics and **is never
classified from**.

Today `shot_manager.py:1039-1068` logs `coord_is_three`, `role_spot_is_three` and
`spot_name_is_three` side by side — three parallel classifications of one shot. Two of those
should not exist.

---

## Part 3 — Displacement as a mechanic (design intent, not built)

Once a single authoritative coordinate exists, the offset between the *base spot* and the
*actual position* stops being noise and becomes a simulation output.

**The core idea:** a player ends up off his base spot because something happened to him, and
that displacement then feeds everything downstream — shot value, shot distance, defender
proximity, and what gets drawn.

Worked example: a post defender out-muscling the post player pushes him off `upper lowPost`.
The shot is now further from the basket. The existing distance penalty does the rest. **The
defender is rewarded before the shot, not only at the contest** — a second channel for the
same attribute.

### Cases this frame covers

| case | displacement | outcome |
|---|---|---|
| strong post offender vs weak defender | **toward** the rim, deeper position | rewarded |
| strong post defender vs weaker offender | **away** from the rim | offender penalised |
| outside shooter finds a soft spot in the zone | off the standard spot, by design | rewarded |
| smart defender subtly forces a shooter off his spot | off the ideal spot | shooter penalised |

The mechanic must be **signed both ways**. If displacement only ever pushes offence away
from the rim, it is a defensive penalty rather than a contest, and offensive strength gets no
channel.

### What it requires

- **The coordinate must be genuinely authoritative.** Today a wrong coordinate costs ~1.9
  points/game and some ugly frames. Under this design, a consumer that reads the *base spot*
  instead of the displaced coordinate silently deletes the defender's post play — the
  mechanic fires, nothing downstream sees it, and the attribute appears to do nothing. That
  is a far worse failure than the bug above, and it is the same bug.
- **Displacement is decided once, in the engine, and emitted.** Never re-derived by the
  renderer or the shot path.
- **Calibration, not a first guess.** The distance lever is already steep — see the 80% vs
  42% figures above. A few grid spots will move make probability more than intuition
  suggests.
- **Sampling and contest resolution consume RNG**, on `sim_rng`, deterministic per seed.
  Draw-count change → SPC principle 8 (poison-stash, re-cut reference).
- **Spacing constraints.** Independent displacement per player will occasionally collapse
  spacing or stack two offenders. The envelope must be checked against neighbours.

### Why this also solves the "scripted" feel

A fixed set of destinations produces visible repetition, and repetition is what reads as
scripted. Contested positioning yields variability **as a byproduct** — one mechanism, two
payoffs. Cosmetic jitter would give variability without depth; this gives both.

Note the complement: a big man backing his defender down and gaining two grid spots over
three steps is legible and satisfying **only if the animation has easing and continuity**.
Without those it renders as two teleports at constant velocity. See
`rewarding_animation_fix.md` — the mechanic gives the animation something worth showing, and
the animation is what makes the mechanic felt rather than merely tabulated.

---

## Sequence

1. **Fix the foul-path 3PT misread** — the reported symptom, small, in progress.
2. **Consolidate the converter** — one function, every key, no silent fallback, guarded.
   Bounded; retires the whole defect class rather than the instances found so far.
3. **Easing and continuity** — see `rewarding_animation_fix.md`.
4. **Displacement as a mechanic** — Part 3 above, once 2 is done and the coordinate can be
   trusted.

Step 2 will change where players stand on ~10% of shot steps and an unknown share of
off-ball steps. It moves outcomes *and* the picture. Measure before, measure after, and
classify what moved rather than counting it.
