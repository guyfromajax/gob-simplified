# Player Development System

> How players grow across a college career. The primary growth event is the **offseason development event**, fired once per player at each season rollover; in-season training only *shapes* and *aims* it. Reasoning and derivation live in the archived design doc: `_documentation_master/projects/Z-Completed/Player_Attribute_Recalibration_Design.md`.

**Module:** `BackEnd/utils/player_development.py` — `develop_one_offseason`, `develop_rollover`, `roll_growth_profile`.

## Offseason Development Event

Fires **once per player per rollover** (the offseason between seasons), before Training Camp. It targets an **absolute** rating, not an incremental budget:

```
target_RT = jh_anchor × ladder_multiplier(rung) × coaching_factor f
```

- `jh_anchor` — the player's JH-scale anchor, derived from `entry_tier` via `JH_ANCHOR_BY_TIER`.
- `ladder_multiplier(rung)` — the class-year rung on the ladder. **Includes the player's peak bonuses** (peaks stack on top of the standard rung increments).
- `f` — coaching-quality multiplier, bounded `[0.85, 1.20]`. **Currently dormant at 1.0** for every player (the live coaching-quality seam returns `None`), so the league holds exactly on the ladder until per-player allocation capture ships.

Because the target is absolute and re-anchored every rollover, nothing drifts: in-season movement is either re-absorbed or, under good coaching, kept as a bounded residual below the smallest rung increment.

## Shape Attractor

Constant: `OFFSEASON_ATTRACTOR_ALPHA = 0.55`.

Rather than distributing an additive budget, the offseason **pulls each attribute a fraction α of the way** toward the tier/year/position **profile scaled to the target RT**:

```
moved = round(before + α × (target_attr − before))
```

It targets **both a level** (the ladder RT) **and a shape** (the position/tier/year profile). Consequences:

- **Bidirectional, not budget-gated.** Pulls RT *down* to the ladder if the season overshot; fills non-signature attributes that the old additive budget starved — the target profile floors them (at `PROFILE_FILLER`), so a center's scoring keeps growing.
- **α < 1 makes it an attractor, not a clamp.** A user's in-season focus survives as a spike he pays for elsewhere — it is pulled toward the profile, never snapped onto it.

## Anchor / Live Write Discipline

Development **reads the un-fatigued `anchor_X`** as input and **writes both `anchor_X` and live `X`**.

| Rule | Why |
|---|---|
| Read `anchor_X`, not live `X` | live may be fatigue-scaled (`live = anchor × NG`); reading it would bake fatigue into the anchor |
| Write **both** `anchor_X` and live `X` | `execute_training` treats `anchor_` as authoritative and resets `live = anchor` at week 1 — writing only live would let the next season's first training wipe the offseason growth |

## HT Grow-Into-Frame

Players are generated **below** their adult frame and grow into it over their college career. HT has its own curve, separate from the physical family, because it is the only attribute whose growth can change a player's best position.

- Career HT gain averages **~3.2 in** (`HT_TOTAL`). A JH lands ~3.2 in below his position frame; a senior sits at it.
- Class-year share of that career gain (standard timing): **JH→FR 40% · FR→SO 30% · SO→JR 20% · JR→SR 10%**.
- Applies to **both** fresh generation and the migration pool stagger (each pool player is set to `adult − remaining career gain` for his class year).
- HT growth changes a player's best position ~5.3% of the time (timing-independent by construction).

## The Four Invariants

Pinned by tests so a future change breaks a test rather than silently drifting the league. The invariant is **not** "nothing rots" — it is *reference holds flat, neglect costs, focus gains*:

1. **Reference holds flat** — a player trained at the reference allocation nets ≈ 0 per on-position attribute over a season (`|Δ| < 3`).
2. **Reference RT stays below the smallest rung increment** — the offseason absorbs the in-season residual, no claw-back.
3. **Neglect declines** — a base-0 (untrained) attribute falls (`< −5` over a season).
4. **Full cycle holds** — season **plus** rollover erodes nothing; the offseason restores what a correctly-coached season did not.

Plus the CPU-path **"preserves shape"** invariant: the offseason regrows toward the profile, preserving each player's relative attribute ordering (a shooter stays a shooter).

**Test files:** `tests/test_in_season_invariants.py`, `tests/test_offseason_attractor.py`.

## Tunable Constants

| Constant | Value | Effect |
|---|---|---|
| `OFFSEASON_ATTRACTOR_ALPHA` | `0.55` | Fraction of the gap to the profile closed each offseason. Higher = faster convergence and tighter shape; lower = user focus persists longer as a spike |
| `STD_RUNG_INCREMENT` (× JH anchor) | FR .17 / SO .20 / JR .15 / SR .18 (Σ .70 → 1.7× at zero peaks) | Per-rung standard growth; sets the class-year ladder |
| `PEAK_BONUS` | `+0.30 × jh_anchor`, fixed per peak | Each rolled peak adds this to the target; peaks stack (0–3), so career multiple runs 1.7× (0 peaks) → 2.6× (3 peaks) |
| `HT_TOTAL` (mean) | `Normal(3.2, 1.9)` clamped `[0,8]`; per-rung cap 2.5 in | Total career height gain; `HT_TOTAL_MEAN = 3.2` in sets how far below frame a JH starts |
| `HT_CURVE_BY_TIMING` (share of career HT gain, FR/SO/JR/SR) | early 55/30/12/3 · **standard 40/30/20/10** · late 15/25/35/25 | When height arrives; standard row is the grow-into-frame stagger |
| `COACHING_F_MIN` / `COACHING_F_MAX` | `0.85` / `1.20` | Bounds on the coaching multiplier `f` — coaching is worth ≈ ±1 tier step. Currently dormant at 1.0 |
| `NON_CORE_GROWTH_MULTIPLIER` | `0.06` | **Vestigial** — the additive budget's non-signature floor; the shape attractor replaced that path. Non-signature filling now comes from the target profile's `PROFILE_FILLER`. |
| `RT_COMPRESSION_THRESHOLD` / `RT_SOFT_CAP` | `95` / `130` | RT gains compress above 95; ~130 is the practical ceiling (individual attributes are uncapped) |
| `OFFSEASON_DISTRIBUTION_BLEND` | `0.70` | **Vestigial** — the additive-budget distribution blend; superseded by the shape attractor (`OFFSEASON_ATTRACTOR_ALPHA`). |
| `JH_ANCHOR_BY_TIER` | Poor→Elite JH-scale anchors (e.g. Average 30, Elite 50) | Maps `entry_tier` to the `jh_anchor` the target formula multiplies |

## Key Files

- `BackEnd/utils/player_development.py` — offseason event, growth-profile roll, rollover driver
- `BackEnd/utils/player_generation.py` — JH start, grow-into-frame height draw
- `BackEnd/utils/position_ratings.py` — RT recomputation after development
- `BackEnd/models/training_execution_v2.py` — `execute_training`, anchor/live reset at week 1
- `tests/test_offseason_attractor.py`, `tests/test_in_season_invariants.py` — invariant assertions
