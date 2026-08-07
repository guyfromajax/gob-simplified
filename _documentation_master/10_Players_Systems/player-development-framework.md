# Player development framework — design brief

**This is a design brief, not an implementation prompt.** Nothing changes in code from this document. What comes back is feasibility, derived values, and a measurement of where the system sits against these targets today.

---

## 1. Scope

**Shape only.** A player's relative profile across the twelve attributes — what kind of player he is.

**Level is out of scope.** Career magnitude stays governed by `entry_tier`, `potential_factor` and the ladder. The dormant coaching accumulator (`f`, pillar 3) is a level mechanism and is not blocked by, and does not block, anything here.

## 2. Architecture

Three things influence a player's shape, and they are **not three ingredients in one blend.** Two are forces; one is a constraint.

**Force 1 — Identity.** The player's **current** shape. Not the shape he arrived with. Coaching does not fight a rubber band; it *moves the anchor*. Two years of working on a player's jumper makes him a shooter, and from then on "stay himself" means staying the shooter he was made into.

**Force 2 — Coaching.** Training allocations and focus, applied at camp and weekly. This is the user's agency over who a player becomes.

**Constraint — Position.** *Not a share of a blend.* The position profile exists to prevent attribute starvation, and a floor is the right shape for that job. Pulling every player toward the positional mean to stop a handful from starving drags down players who were never near the edge.

It becomes two things instead:

- **A per-attribute floor per position** — a hard minimum a player cannot fall below.
- **A training-efficiency cost** — gains are less efficient the further an attribute sits from its positional archetype. Implausible builds become expensive rather than impossible, and the coach keeps agency.

**The current `OFFSEASON_ATTRACTOR_ALPHA` blend toward `position_profile(training_position)` is retired by this design.** It is the mechanism producing 24% career shape retention, and its legitimate function is served by the floor.

## 3. Denominators

Two splits, and they need different units. This matters — conflating them produces targets that can't be hit.

**Phase split — share of total attribute movement across a four-year career.** Every phase causes movement, so movement is the natural unit.

**Force split — share of explained variance in final shape.** Identity is a *retaining* force; it causes no movement, it prevents it. Measuring it in movement would score it at zero. So the force split asks how much of what a player ends up being is explained by who he was versus what you did with him.

## 4. Targets

Directional, not exact.

### Phase

| Phase | Target share of career attribute movement |
|---|---|
| Offseason | 35% |
| Training camp | 35% |
| In-season training | 30% |

Note how this falls out given the architecture: the offseason owns **level** — rescale to ladder, physical growth — while camp and in-season own **shape**. That division is already what the code does, and it makes the 35 / 65 split coherent rather than arbitrary.

### Force

| Force | Target share of explained variance in final shape |
|---|---|
| Identity (current shape) | 55% |
| Coaching | 45% |

**Restated as a single measurable parameter: career shape retention ≈ 0.55.** Today it is **0.245**.

But retention alone is not sufficient, because *where* a player moves matters as much as how far. Two numbers are required:

1. **Career shape retention ≈ 0.55** — how much of himself persists.
2. **Of the movement that does occur, the share that is coach-aligned rather than profile-aligned.** Under this design that should be high. A player losing 45% of his shape *toward what his coach trained* is the design working; losing 45% toward the league mean is the bug we just found wearing a better number.

### Malleability by class

**Declines with year.** A freshman is more reshapeable than a senior — it matches how players actually develop, it makes recruiting a freshman feel different from inheriting a senior, and the code already assumes it.

Consequence to accept deliberately: the 55/45 is a **career average**, not a constant. Coaching is worth more than 45% in years one and two and less in three and four.

## 5. Team Builder interaction

**The position floor binds at Apply.** A roster violating a floor cannot be established; the user is told which player and which attribute, and fixes it.

It does not engage quietly once the season starts. Silent adjustment is the pattern this feature forbids everywhere else, and a user seeing attributes he didn't choose is exactly what §4.5b exists to prevent.

## 6. What you derive — propose, don't invent

**The floor values.** A minimum per attribute per position, derived from the current league distribution rather than chosen. Propose a method and the resulting table, with the percentile or rule you used and why. These are the numbers a user will hit when Apply refuses their roster, so they need to be defensible.

**The efficiency curve.** How sharply training cost should rise with distance from positional archetype. Propose a shape and justify it against what it makes possible and impossible.

**The current baseline.** Where the system sits against every target above, today, measured — phase shares, retention, and coach-aligned versus profile-aligned movement. We know retention is 0.245; the rest is unmeasured.

**Feasibility.** For each element: buildable as specified, buildable with changes, or blocked. Say which, and say what the changes are.

## 7. Validation

**The shape-dispersion metric goes into the attribute system's permanent validation suite.** This is the most important line in this document.

Seven separate occurrences of the same masking pattern — including one I introduced into the audit built to catch it — is not seven bugs. It is one missing test. Any future tuning pass validated only on RT percentiles, career multiples or anchor-landing will reproduce this exactly.

**No parameter in this framework may be signed off on a level-based metric.**

## 8. Explicitly out of scope

- **Pillar 3 / the coaching accumulator.** Level, dormant, documented, separate decision.
- **The recruit generation branch** — init draws from frozen `recruit_set_0001` at σ 15.7, subsequent classes from live `generate_recruits_list` at σ 11.6. A real 26% variety loss after season one, and its own decision.
- **`training_position` has no live write path.** It defaults to `position_intent`, so nobody can redirect the position a player is developed toward. Under this design the floor follows position, so this becomes more visible — flag it, don't fix it here.
- **Three stale documentation claims** found in the audit: the module header saying it is "NOT wired into any live path," the `develop_rollover` docstring describing a dead distribution parameter, and `Training_System.md` documenting camp bonuses that no longer exist. Correct these; they are the same class as "no court generator exists," which cost a full cycle.

## 9. Rules

- Report before changing. Nothing in this document authorises a code change.
- Where code and documentation disagree, the code wins and the disagreement is a finding.
- If a target cannot be hit by the mechanism as designed, say so rather than approximating it quietly. Directional is fine; silently unreachable is not.
