# Player development framework — design brief

**Status:** **done** (2026-08-07). Architecture accepted; build shipped under **§10**; **§11** (development vs authorship) closed. Where §§1–9 disagree with §10, §10 wins.

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

- **A per-attribute floor per position** — decay never subtracts below it; Apply refuses authored violations. No corrective write.
- **A training cost on the point budget** — off-profile work consumes points at `1/η` per allocation unit. Gains land at full size when the coach pays. Implausible builds become expensive in breadth, not silent zeros.

**The current `OFFSEASON_ATTRACTOR_ALPHA` blend toward `position_profile(training_position)` is retired by this design.** It is the mechanism producing 24% career shape retention, and its legitimate function is served by the floor.

## 3. Denominators

**Force split — share of explained variance in final shape.** Identity is a *retaining* force; it causes no movement, it prevents it. Measuring it in movement would score it at zero. So the force split asks how much of what a player ends up being is explained by who he was versus what you did with him.

**Phase shares of career attribute L1 are not a target.** They remain a diagnostic readout only. The retired 35/35/30 split was chosen before the three phases had settled identities; the offseason's share moves whenever training strength changes, so chasing it tunes the wrong thing.

## 4. Targets

Directional, not exact.

### Phase (behavioural — 35/35/30 retired)

| Phase | Acceptance |
|---|---|
| **Training camp** | A genuine decision point with real weight (`CAMP_WEEKS=3`, `CAMP_GAIN_SCALE=1.4` held). |
| **In-season training** | Responsive week to week — allocation and focus move attributes; remainder + distinct bands keep partial commitment alive. |
| **Offseason** | Judged by whether **potential pays off**, not by share of career attribute L1. Acceptance basis = untrained maturation table (§10.4). |

Shape movement stays camp + in-season by architecture (level-only offseason); ~0% offseason shape is expected.

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

**The position floor binds at Apply** for authored rosters — a violation cannot be established; the user is told which player and which attribute, and fixes it.

**In season, the floor bounds decay only.** Training adds; decay subtracts; decay stops at the floor. No corrective write ever lifts an attribute. The user never sees a value they didn't cause — they see a value stop falling. Apply-only would fail the anti-starvation purpose (neglect across a season, no second Apply).

Silent upward adjustment remains forbidden (§4.5b).

## 6. What you derive — propose, don't invent

**The floor values.** A minimum per attribute per position, derived from the current league distribution rather than chosen. Propose a method and the resulting table, with the percentile or rule you used and why. These are the numbers a user will hit when Apply refuses their roster, so they need to be defensible.

**The cost curve.** How sharply training *budget cost* should rise with distance from positional archetype. Propose a shape and justify it against what it makes possible and impossible.

**The current baseline.** Where the system sits against every target above, today, measured — phase shares, retention, and coach-aligned versus profile-aligned movement. We know retention is 0.245; the rest is unmeasured.

**Feasibility.** For each element: buildable as specified, buildable with changes, or blocked. Say which, and say what the changes are.

## 7. Validation

**The shape-dispersion metric goes into the attribute system's permanent validation suite.** This is the most important line in this document.

Seven separate occurrences of the same masking pattern — including one I introduced into the audit built to catch it — is not seven bugs. It is one missing test. Any future tuning pass validated only on RT percentiles, career multiples or anchor-landing will reproduce this exactly.

**No parameter in this framework may be signed off on a level-based metric.**

## 8. Explicitly out of scope

- **Pillar 3 / the coaching accumulator.** Level, dormant, documented, separate decision.
- **Play questions from §10.6** — moderate hedging; focus-amp decisiveness. Decide in play.
- **Three stale documentation claims** found in the audit: the module header saying it is "NOT wired into any live path," the `develop_rollover` docstring describing a dead distribution parameter, and `Training_System.md` documenting camp bonuses that no longer exist. Correct these; they are the same class as "no court generator exists," which cost a full cycle.

## 8a. Unowned — surfaced here, no owner yet

These are not in the framework build and have **no assigned next step**. Flagged so they are not forgotten because they fell out of an "out of scope" list:

1. **Recruit generation branch** — init draws from frozen `recruit_set_0001` at mean attr σ **15.7**; subsequent classes from live `generate_recruits_list` at σ **11.6**. A real **26% variety loss after season one**. Same helper, different branch — not signing selection.
2. **`training_position` has no live write path.** It defaults to `position_intent`, so nobody can redirect the position a player is developed toward. The position floor and gain percentage follow it — conversion / positional-redirect coaching cannot be expressed until a write path exists.

## 9. Rules

- Report before changing. Nothing in §§1–9 alone authorises a code change; §10 is the build lock.
- Where code and documentation disagree, the code wins and the disagreement is a finding.
- If a target cannot be hit by the mechanism as designed, say so rather than approximating it quietly. Directional is fine; silently unreachable is not.

## 10. Accepted for build (2026-08-07)

### 10.1 Direct gain percentages (supersedes the historical cost derivation below)

> **Current representation:** the cost representation described historically in this subsection is retired. The live system stores `TRAINING_GAIN_PERCENTAGES` directly, charges one point per notch, and applies position/class percentages to gain before the remainder split. The complete authoritative table is in `../11_Design_Systems/Tunable_Constants.md`.

- `cost_a = 1/η_a`, `η_a = clamp((w_a/w_max)^γ, η_min, 1)`.
- **γ = 1.0**, **η_min = 0.25** (max cost 4). Class cost multipliers: FR 1.0 / SO 1.1 / JR 1.25 / SR 1.4.
- Gains use allocation **units** and normal `IN_SEASON_GAIN_SCALE`; η never multiplies the gain roll.
- Spent budget = `Σ units_a × cost_a × class_mult` must fit the week’s point pool (24 in-season / 30 camp).

**Historical weight basis — retired source weights, not `POSITION_WEIGHTS` alone.**

**Standing rules:**

1. Dedicated retired source weights (no longer present in live code).
2. **Universals cost 1 everywhere: ND, FT, IQ.**
3. **Absent from the cost table → cost 1.** Absence never falls through to max cost.
4. **Explicit `0` = physically constrained only** (“a body like that can’t do this”). Skills sit in the graduated mid-band.
5. Seed from `POSITION_WEIGHTS`, strip universals, add mid-band weights for absent skills / **lift any rating weight below 0.10** (or that would otherwise max-tax an on-role skill), then apply physical zeros. Tiny rating weights mean “doesn’t predict this RT,” not “shouldn’t be trainable.”

**Explicit zeros:**

| Pos | Attr | Sentence |
|---|---|---|
| PG | RB | A point-guard frame does not have the height or mass to be an elite rebounder. |
| PG | ID | A point-guard frame cannot hold post position or anchor the paint. |
| SG | RB | A shooting-guard frame does not have the size to dominate the glass. |
| SG | ID | A shooting-guard frame cannot be a rim protector — the body is not built to hold the lane. |
| C | AG | A centre's size and mass prevent elite lateral agility — the body does not change direction like a wing. |

**Not zeros:** SF RB (wings rebound); C OD (scheme/effort — mid-band ~2.5); PF SC (lifted — PFs score).

**Historical source weights (final, post AG/ST mono; no longer live):**

```
PG: BH 0.30, AG 0.25, PS 0.15, OD 0.15, SH 0.135, SC 0.12, ST 0.105, RB 0, ID 0
SG: SH 0.42, OD 0.25, SC 0.231, AG 0.231, BH 0.168, PS 0.168, ST 0.147, RB 0, ID 0
SF: OD 0.20, SC 0.18, SH 0.14, AG 0.1053, ID 0.1099, RB 0.1099, PS 0.0772, BH 0.0772, ST 0.088
PF: RB 0.30, ST 0.22, ID 0.20, SC 0.165, SH 0.14, AG 0.1364, OD 0.105, PS 0.105, BH 0.10
C:  ID 0.32, RB 0.32, ST 0.2462, SC 0.18, SH 0.128, OD 0.128, BH 0.1067, PS 0.1067, AG 0
```

(Universals omitted → cost 1. Derived costs capped at 3.0; explicit zeros → 4.0.)

**Final cost matrix:**

```
       ST    AG    SC    SH    ID    OD    PS    BH    RB    FT    IQ    ND
PG   2.86  1.20  2.50  2.22  4.00  2.00  2.00  1.00  4.00  1.00  1.00  1.00
SG   2.86  1.82  1.82  1.00  4.00  1.68  2.50  2.50  4.00  1.00  1.00  1.00
SF   2.27  1.90  1.11  1.43  1.82  1.00  2.59  2.59  1.82  1.00  1.00  1.00
PF   1.36  2.20  1.82  2.14  1.50  2.86  2.86  3.00  1.00  1.00  1.00  1.00
C    1.30  4.00  1.78  2.50  1.00  2.50  3.00  3.00  1.00  1.00  1.00  1.00
```

**Ordered attributes (cross-position monotonicity):**

| Attr | Order | Rule |
|---|---|---|
| RB, ID | cheaper as bigger | PG ≥ SG ≥ SF ≥ PF ≥ C |
| BH, PS, AG | dearer as bigger | PG ≤ SG ≤ SF ≤ PF ≤ C |
| ST | cheaper as bigger | PG ≥ SG ≥ SF ≥ PF ≥ C |

AG belongs in the ordered set: the C/AG wall (“size and mass prevent elite lateral agility”) is a size-order claim — SF must not undercut PG/SG just because a flat wing profile made AG its top weight.

**Do not order (document so nobody “fixes” them later):**

- **OD** — perimeter defense is not monotonic in size. It peaks at the wing and falls off toward both the pure guard and the post; SF sits cheapest and PG is not. Real basketball fact, not a table artefact.
- **SH** — shooting has no size order. Leave derived.

**Senior stacking:** passed (cost limits breadth; gains unchanged).

### 10.2 Floors — weight-scaled (not a uniform percentile)

**Rule shape:** floor strength tracks how much the attribute matters at that position. Live code stores the validated result directly in `SHAPE_FLOOR_MULTIPLIERS`, with universals always full.

```
rel = w_a / w_max   (historical derivation only; universals → rel = 1)
mult = 1 if universal or rel ≥ 0.50
     = 0 if rel ≤ 0.20          → need = 1 (minimal)
     = lerp otherwise
need = max(1, ceil(shape_P6[pos][attr] * mean(core-12) * mult))
```

Base distribution = **t0 shape-P6** (pre-development only). High-weight attrs get a real floor; low-weight / off-role get minimal; ND/FT/IQ get full floors everywhere.

**Why not uniform percentile:** a centre with SH=8 is a post player; a centre with ID=8 is starving. One number cannot tell those apart.

**Battery (weight-scaled, cost-table basis, P6, HIGH=0.5, LOW=0.2):**

| Creative | Worst attr | Clearance (pts) |
|---|---|---:|
| stretch_four | RB | +6 |
| shooting_big | BH | +8 |
| undersized_rim_protector | SH | +5 |
| point_forward | AG | +3 |
| three_and_d | PS | +14 |
| **traditional_post** | **SH** | **+3** (was the binding +0/+1 case — gone) |
| pure_distributor | SC | +13 |
| small_ball_five | ID | +7 |
| scoring_pg | IQ | +10 |
| slashing_sf | SH | +2 |
| **Pass / ≥2 / ≥3** | | **10/10 / 10/10 / 9/10** |

| Pathological | Result |
|---|---|
| 12 original (harsh/mild/glass/statue) | **12/12 refuse** |
| starved_id_c (ID=8) | refuse on ID |
| starved_id_pf (ID=8) | refuse on ID (needs cost-table basis — `POSITION_WEIGHTS` alone misses PF ID) |

**Target met:** creative clears ≥2; pathology refused; traditional post no longer binding.

**Standing calibration rule:** derive the *shape percentile base* only from a pre-development population. Never from a developed snapshot (C ID abs@median 15→61). The weight scaling is the rule; the percentile is just the distributional input.

**Do not rebuild floors from bare `POSITION_WEIGHTS`** — it omits PF ID (and similar), so a rim-protector PF with ID=8 would incorrectly pass. Preserve `SHAPE_FLOOR_MULTIPLIERS`.

### 10.3 Camp

Parameterised: **`CAMP_WEEKS`** and **`CAMP_GAIN_SCALE`**.

**Ship / hold at `CAMP_WEEKS = 3`, `CAMP_GAIN_SCALE = 1.4`**. Minimum weeks is 2. Camp-only bonus resurrection rejected. Camp weeks use the 30-pt budget, skip pre-training decay, and apply `CAMP_GAIN_SCALE` instead of `IN_SEASON_GAIN_SCALE`. Roster cuts and Practice Squad init run after the **last** camp week. Do not raise scale to chase a retired phase-share target or a shape ratio.

### 10.4 Offseason — level only; maturation is the acceptance test

**Retire `OFFSEASON_ATTRACTOR_ALPHA`.** Offseason keeps **level** only: rescale current attributes to the ladder `target_rt` (plus HT/WT). Camp and in-season own shape. Floors replace the attractor’s anti-starvation job. Shape share near 0% is expected.

**Acceptance basis — untrained maturation** (offseason only, zero training, n=80/tier, artifact `tmp/s11_framework_baseline/untrained_maturation.json`). A future change that quietly weakens maturation fails these reference numbers:

| entry_tier | Δ mean attr FR→SR | Δ RT | SR RT |
|---|---:|---:|---:|
| Poor | +14.4 | +16.8 | 41 |
| BelowAverage | +17.1 | +20.9 | 52 |
| Average | +19.8 | +24.2 | 60 |
| Good | +23.2 | +27.8 | 70 |
| Great | +28.4 | +34.2 | 82 |
| Elite | +32.8 | +41.0 | 100 |

High vs low `potential_factor` (1.15 vs 0.85), same tier — gaps that must remain visible:

| entry_tier | Δmean-attr gap | ΔRT gap | SR RT gap |
|---|---:|---:|---:|
| Poor | +3.3 | +4.7 | +11.7 |
| BelowAverage | +4.5 | +6.0 | +15.0 |
| Average | **+6.2** | **+7.5** | **+17.7** |
| Good | +6.0 | +7.2 | +18.9 |
| Great | +9.0 | +9.9 | +24.4 |
| Elite | +7.4 | +11.7 | +28.9 |

Ladder medians land. Potential pays off without training. Offseason attribute *share* (~11% beside healthy training) is not an acceptance metric.

### 10.5 Validation (permanent)

**Shape-dispersion enters the permanent suite with this build**, not after. Every parameter here was chosen against shape; a suite that can only see level will undo the next tuning pass. No framework parameter may be signed off on a level-based metric alone (§7).

**Along / across shape movement** also lives in the suite (`BackEnd/utils/shape_movement.py`). Raw cosine retention conflates:

- **Along-shape (sharpening)** — movement parallel to the player's starting deviation from flat. "More of the same."
- **Across-shape (conversion)** — the orthogonal residual. "Change who he is."

Reference is specialisation, not a null — concentrating on top-three sharpens and moves cosine just as surely as conversion. Mild > reference on cosine is not an inversion. Read the across-shape ladder for conversion intent; read along-shape for sharpening. Do not re-open tuning against a cosine "null strategy" that does not exist in this test.

### 10.6 Gain-path resolution (shipped)

Two quantisation defects fixed:

1. **Fractional remainder** (`training_gain_remainders`) — sub-integer scaled gains accumulate across weeks instead of `int(round(·))` zeroing ~19% of 1–3-pt rolls.
2. **Distinct bands** in `PLAYER_ATTR_GAIN_RANGE_BY_POINTS` (E[raw|5] held at 4.5):

| pts | band | E[raw] |
|---|---|---:|
| 0 | (−2,−1) | −1.5 |
| 1 | (1,3) | 2.0 |
| 2 | (2,3) | 2.5 |
| 3 | (2,4) | 3.0 |
| 4 | (3,5) | 4.0 |
| 5 | (3,6) | **4.5 held** |

**Mechanism close-out** — phase and force impact tables (canonical): [`Player_Development_System.md` → Framework measured outcomes](Player_Development_System.md#framework-measured-outcomes-reference). Cosine span 0.40–0.84; across-shape ladder clean; attractor gone; coaching owns ~99% of shape; moderate @0.77 is a hedged conversion responding correctly.

**Play questions (parked):** whether moderate should be able to hedge; how decisive the focus amp should be. Decide in play (§8).

**Camp held** at 3 / 1.4. Diagnostic phase shares after remainder + re-band (reference, gain-driven attr L1): camp 37% / in-season 52% / offseason 11%. Not targets — see §4.

---

## 11. Development vs authorship — **closed**

**Resolved 2026-08-07 with this framework.** Development no longer undoes authorship.

| Claim | Status |
|---|---|
| Coaching owns shape | Shipped — camp + in-season; ~99% of shape movement |
| Identity persists | Current shape is the identity force; floors bound starvation without a mean pull |
| Attractor gone | `OFFSEASON_ATTRACTOR_ALPHA = 0.0`; offseason is level-only |
| Team Builder authored shape survives | No proportional bite toward `position_profile` each rollover |

The earlier Team Builder measurement correctly found that authorship was not uniquely victimised —
**individuality** was, league-wide, via α. The durable measurements and rationale are summarized in
[`Player_Development_System.md`](Player_Development_System.md#reshape-vs-grow--closed-grow-level-coach-shape).
That model question ("reshape vs grow") is answered: **grow level, coach shape**. Do not re-open α
or authorship drift against the retired blend.

**Unowned follow-ons** from this work: §8a (recruit σ branch; `training_position` write path).
