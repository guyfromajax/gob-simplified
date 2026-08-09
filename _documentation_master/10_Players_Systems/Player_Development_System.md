# Player Development System

> How players grow across a college career. **Camp and in-season training own shape** (~99% of career shape movement). The **offseason is level-only**: once per rollover it rescales the current attribute vector onto the ladder RT target (plus HT/WT). Floors and the training cost matrix are the position constraint — not an offseason blend toward the profile. Canonical measured outcomes are below; derivation archive: `_documentation_master/projects/Z-Completed/Player_Attribute_Recalibration_Design.md`. Framework: [`player-development-framework.md`](player-development-framework.md).

**Modules:** `BackEnd/utils/player_development.py` — `develop_one_offseason`, `develop_rollover`, `roll_growth_profile`. Shape constants: `BackEnd/constants/training_shape.py`. In-season execution: `BackEnd/models/training_execution_v2.py`.

## Offseason Development Event

Fires **once per player per rollover** (the offseason between seasons), before Training Camp. It targets an **absolute** rating and applies a **level-only** rescale — it does not redistribute shape:

```
target_RT = _compress_rt( jh_anchor × ladder_multiplier(rung) × coaching_factor f × potential_factor )
```

- `jh_anchor` — the player's JH-scale anchor, derived from `entry_tier` via `JH_ANCHOR_BY_TIER`.
- `ladder_multiplier(rung)` — the class-year rung on the ladder. **Includes the player's peak bonuses** (peaks stack on top of the standard rung increments).
- `f` — coaching-quality multiplier on the **RT target** (level, not shape), bounded `[0.85, 1.20]`. **Currently dormant at 1.0** for every player (`_coaching_accumulator_for_player` hardwired to `None`), so every program lands on the same ladder until per-player allocation capture ships (pillar 3). That dormancy is unfinished wiring, not a shape force — the shape attractor is retired (`OFFSEASON_ATTRACTOR_ALPHA = 0.0`).
- `potential_factor` — career-static ±15% ceiling scalar (`POTENTIAL_FACTOR_BAND = 0.15`), drawn once at generation, independent of `entry_tier` and `ch_seed`. **LIVE** (Potential Rating Phase 3). A pure scalar on the target, so it lifts the *level* while preserving the player's current attribute ratios under the level-only rescale. Legacy players with no stored value resolve deterministically from `player_id` (`resolve_potential_factor`).
- `_compress_rt` — soft cap near `RT_SOFT_CAP = 130`, asymptote ≈ 138. Below the cap it is identity; it only bends the very top. The extreme cohort Elite × 3-peak × 1.15 targets `50 × 2.6 × 1.15 = 149.5`, compressed to **137.3**. (Achieved RT, recomputed from attributes, can overshoot the compressed target for a <0.1% tail — a pre-existing property of recompute-from-attributes, not introduced by `potential_factor`.)

Because the target is absolute and re-anchored every rollover, in-season **level** movement is either re-absorbed or, under good coaching, kept as a bounded residual below the smallest rung increment. In-season **shape** is not unwound here — camp and weekly training keep it.

**Developed players land on the ladder (2026-08 level-close).** The offseason closes LEVEL fully (see Shape Attractor — retired for shape, retained for the level rescale), so a developed senior's median RT sits **exactly on his tier anchor** — pinned by `test_developed_seniors_land_on_tier_anchors`. Before the fix the α-step undershot a rising target and developed seniors landed at ~0.91× the anchor (Elite 91, not 100); it was masked for a long time because **generation** hits the anchors by construction and only cohort turnover exposes the drift. Career multiple by peak count is now exact: 0/1/2/3 peaks → 1.70/2.00/2.30/2.60×.

**Senior RT spread by tier (measured, p10/p50/p90, positions pooled).** With `f` dormant and `potential_factor` live: Poor 34/40/48 · BelowAvg 42/50/60 · Average 51/60/72 · Good 59/70/84 · Great 68/80/96 · Elite 85/100/120. **Medians land on the anchors** (40/50/60/70/80/100); `potential_factor` widens each adjacent-tier tail overlap by only ~2–3 RT on top of the peak-driven baseline (peaks are the dominant spread source). This blur is the design intent — it stops the projected-potential display from leaking `entry_tier`.

**RNG note (precise).** `potential_factor` is drawn **last** inside `generate_player`, so every *prior* draw for that same player (core attributes, CH, EM, weight) keeps its exact stream position — those fields are byte-identical to before the feature. However, the generator's `rng` is **shared across a generation run**, so consuming one extra value per player shifts the stream for every *subsequent* player in that run: **any seeded regeneration now yields a different downstream population than it did pre-feature.** This is harmless here — the retroactive pool write (Phase 5) and the projection read (Phase 4) both read stored state and never invoke generation — but a test that pins an exact seeded population across the whole run will differ.

### Potential Rating display

Potential Rating is fully shipped. The canonical projection helper is
`BackEnd/utils/rt_projection.py`:

```text
raw projection = JH_ANCHOR_BY_TIER[entry_tier] × 2.0 × potential_factor
displayed potential = max(raw projection, current highest RT)
```

The ratchet is computed at read time and is never separately persisted. Payloads expose the
already-ratcheted value as `potential_rt_ratcheted`; views must not repeat the formula. The shared
letter formatter renders `current/potential` while keeping the column header `RT`. Missing legacy
factors resolve deterministically from `player_id` and warn, because the universal pool backfill is
complete.

Consumers include Team Roster, the FCC roster/recruiting surfaces, Recruiting Hub pages, and
roster-management flows that explicitly show ceiling context. Other gameplay surfaces may continue
to show current RT alone. Core tests: `test_potential_factor.py` and `test_rt_projection.py`.

## Shape Attractor — **retired**

Live constant: `OFFSEASON_ATTRACTOR_ALPHA = 0.0` (level-only offseason; shape owned by camp / in-season + floors). See framework §10.4 / §11.

> Historical record below describes the α=0.55 blend that produced league shape convergence. Do not restore it.

Rather than distributing an additive budget, the *former* offseason targeted **both a level** (the ladder RT) **and a shape** (the position/tier/year profile), and separated them (2026-08 attractor-level fix):

```
# SHAPE — α-blend each attribute toward its profile-scaled target (training bias survives in the ratios)
blended[a] = before[a] + α × (profile[a]·k − before[a])
# LEVEL — close fully: one closed-form rescale so RT lands on the ladder exactly
s = target_RT / (fit · Σ weights·blended)          # RT = weighted_mean × fit is linear in the (all-growth) weights
moved[a] = round(blended[a] × s)
```

The earlier form applied only the SHAPE step (`before + α·(target−before)`) with **no** level close, which let α govern the level as well as the shape — a 55% step toward a target that rises every rung left a compounding ~9% gap. Consequences of the separated form:

- **Lands on the ladder by construction — now actually true.** The level close is exact, so developed RT hits the tier anchor; the old "by construction" claim was measurably false and is now pinned by a test.
- **Bidirectional and complete.** Pulls RT *fully* down to the ladder if the season overshot (the old form only clawed back 55% of an overshoot, leaving a permanent ratchet); fills non-signature attributes the old additive budget starved, so a center's scoring keeps growing.
- **α < 1 still makes it an attractor for SHAPE, not a clamp.** A user's in-season focus survives as a proportional spike in the ratios (paid for elsewhere, since the level is fixed to the ladder) — pulled toward the profile, never snapped onto it.

## Framework measured outcomes (reference)

Canonical close-out numbers for the shape framework ([`player-development-framework.md`](player-development-framework.md)). Prefer this section over scattered §10 notes or findings docs when citing phase or force impact.

**Basis (all tables below unless noted):** reference arm · n = 150 · gain-driven (camp + week_gain + offseason; decay excluded) · current build (`CAMP_WEEKS=3`, `CAMP_GAIN_SCALE=1.4`, attractor retired, fractional remainder + re-banded gains) · measured **2026-08-07** · script `scripts/s11_framework_baseline_measure.py` · artifacts `tmp/s11_framework_baseline/reference_phase_shares.json`, `baseline_strategy_spread.json`. Re-run the script rather than trusting the number alone.

### Phase impact — share of career movement

| Phase | Attribute movement | Shape movement |
|---|---:|---:|
| Training camp | 37.2% | 27.1% |
| In-season | 52.0% | 71.9% |
| Offseason | 10.8% | 1.0% |

**35 / 35 / 30 retired, not met.** Camp landed on the old attribute target (~35%). In-season came in above. The offseason's absolute contribution did not shrink because the offseason changed — its share fell because the gain-path fixes strengthened coaching and enlarged the denominator. Offseason shape ~1% is expected (level-only by design).

**Offseason acceptance** is the untrained-maturation table in framework §10.4 (potential pays off without training) — not phase share.

### Force impact

| Force | Outcome |
|---|---|
| **Coaching** | ~99% of shape movement (`of_shape_move_share_from_training_phases`). Coach-aligned projection **76.8%** on reference, **96.5%** on extreme; the residual is geometric overlap between reference emphasis and the position profile, not a competing pull. |
| **Player identity** | Not a fixed share — cosine retention spans **0.84 → 0.41** by coaching intent. Reference **0.825**, mild **0.839**, moderate **0.772**, extreme **0.405**. |

Player-development persistence contracts cover both sides of every Mongo boundary: read
projections must load every required field, and write projections must explicitly persist every
mutated sidecar. In particular, `training_gain_remainders` lives beside `attributes` on FPD, is
never written to core players, and is included in the annual player-development carry contract.
| **Position generics** | **0%** as a force. Expressed only as weight-scaled P6 floors (refuse at Apply; clamp decay) and the 1×–4× training cost matrix. |

**55 / 45 identity-to-coaching superseded.** Coaching owns all shape movement; how much of a player survives is the coach's decision. The old **0.55** figure describes an aggressive reshaping coach, not a property of the mechanism — a typical (reference) coach lands near **0.83**, which is correct: reinforcing strengths should not erase him.

Along / across decomposition (same basis; conversion-only reading): see `baseline_strategy_spread.json` → `strategy_across_shape_ladder` / `strategy_along_shape_ladder`. Suite: `BackEnd/utils/shape_movement.py`, `tests/test_training_shape_framework.py`.

## Anchor / Live Write Discipline

Development **reads the un-fatigued `anchor_X`** as input and **writes both `anchor_X` and live `X`**.

| Rule | Why |
|---|---|
| Read `anchor_X`, not live `X` | live may be fatigue-scaled (`live = anchor × NG`); reading it would bake fatigue into the anchor |
| Write **both** `anchor_X` and live `X` | `execute_training` treats `anchor_` as authoritative and resets `live = anchor` at week 1 — writing only live would let the next season's first training wipe the offseason growth |

### Mongo projection discipline (read-path counterpart)

**When you add a persisted player field, audit the Mongo `find(..., projection)` calls that load players — the read paths — the same way write paths are audited for a dropped carry.** A narrow projection silently drops a field just as a fixed copy-list does, and it fails quietly: the field is present in the DB but absent from the object the code sees. This has caused **three** silent losses on this codebase — the latest was `entry_tier`/`potential_factor` stripped by `roster_loader._load_from_db`'s four-field projection, which starved the Potential Rating display until the projection was widened (§Phase 4). Write paths already carry this discipline (the `entry_tier` persistence audit); read-side projections did not. Grep for `find(` projections touching `franchise_players_data` / `players` whenever a new persisted field must reach a surface.

## HT Grow-Into-Frame

Players are generated **below** their adult frame and grow into it over their college career. HT has its own curve, separate from the physical family, because it is the only attribute whose growth can change a player's best position.

- Career HT gain averages **~3.2 in** (`HT_TOTAL`). A JH lands ~3.2 in below his position frame; a senior sits at it.
- Class-year share of that career gain (standard timing): **JH→FR 40% · FR→SO 30% · SO→JR 20% · JR→SR 10%**.
- Applies to **both** fresh generation and the migration pool stagger (each pool player is set to `adult − remaining career gain` for his class year).
- HT growth changes a player's best position ~5.3% of the time (timing-independent by construction).

## The Four Invariants

Pinned by tests so a future change breaks a test rather than silently drifting the league. The invariant is **not** "nothing rots" — it is *reference primaries hold near flat, neglect costs, focus gains*. Re-fitted after distinct 1–5 gain bands + fractional remainder (`tests/test_in_season_invariants.py`; do not restore the old per-attr `|Δ| < 3` gate):

1. **Reference primaries hold near flat** — under the reference allocation, primary (pts=3) *mean* net over a season satisfies `|μ| < 4` (`FLAT_TOL`); each primary `|Δ| < 8`. Baseline (pts=1) attrs may drag mildly (must not collapse, must not gain).
2. **Reference RT stays below the smallest rung increment** — in-season RT net in `(−5, smallest_rung)`; the offseason absorbs the residual, no claw-back.
3. **Neglect declines** — a base-0 (untrained) attribute falls (`< −5` over a season).
4. **Full cycle holds for primaries** — season **plus** level-only rollover does not erode primaries (`mean Δ > −FLAT_TOL`); baseline may still drag.

Plus the CPU-path shape check (`test_cpu_path_preserves_shape`): under level-only offseason, **coaching still moves shape** — reference top-3 attrs finish above neglected attrs. Profile-alignment (≥70% of `position_profile`) was the attractor's job and is retired; floors replace its anti-starvation half.

**Test files:** `tests/test_in_season_invariants.py`, `tests/test_offseason_attractor.py`, `tests/test_training_shape_framework.py`.

## Open — training-squad progression is a second, uncorrected shape channel

`_apply_training_squad_progression_and_report` (`franchise_routes.py:11486`, `_ts_progression_delta`)
evolves every **training-squad** player's 13 attributes weeks 2–26 (user **and** CPU) by an
**independent CH-gated ±2 random walk per attribute**, with a min-1 clamp only — **no shape floors,
no fitted rung increment**. It is a distinct path from `develop_rollover`; the Four Invariants above
do **not** cover it (they test the reference-allocation offseason path).

Why this is a shape problem, not just "unfitted physics":

- **Level damage washes out; shape damage does not.** The offseason is absolute-target and rescales
  the current vector onto the ladder, so wherever in-season left the *level*, the rung close
  re-anchors it. But that rescale is **uniform — it preserves ratios** (§ Shape Attractor — retired;
  Offseason Development Event). So a floorless per-attribute random walk **permanently distorts the
  profile**, and the offseason merely scales the distorted shape up to target.
- That makes it a **second uncorrected shape channel**, structurally the same as the one under
  investigation after the attractor was retired (`OFFSEASON_ATTRACTOR_ALPHA = 0.0`) — and it runs on
  the **training squad, ~20% of the league**.

**Magnitude** (CH flat 1–100, weighting the delta bands): ≈ **−7 per attribute per season** on
average, with **~79% of training-squad players declining** (only CH > 79 has positive drift). Not
marginal.

**Measurement + warning:** the **same per-position shape check outstanding on the drift work** would
surface this. Whoever runs that check must account for this path first — **measuring shape drift
while a floorless random walk runs on a fifth of the league will attribute the drift to the wrong
cause.** (Flagged 2026-08 during the walk-on tier / peak-eligibility work; no fix attempted here.)

## Tunable Constants

Canonical lever table: [`Tunable_Constants.md`](../11_Design_Systems/Tunable_Constants.md) A — LEVERS. Development-relevant values:

| Constant | Value | Effect |
|---|---|---|
| `OFFSEASON_ATTRACTOR_ALPHA` | **`0.0`** (was 0.55) | **Retired.** Level-only offseason. Framework §11. |
| `CAMP_WEEKS` / `CAMP_GAIN_SCALE` | **3** / **1.4** | Camp phase length; camp gain scale (`training_shape.py`) |
| `IN_SEASON_GAIN_SCALE` | **0.18** | Scales positive weekly gains after camp |
| `PLAYER_ATTR_GAIN_RANGE_BY_POINTS` | 0:(−2,−1) … 5:(3,6) | Distinct raw bands; E[raw\|5]=4.5 held (`training_execution_v2.py`) |
| Gain-fit divisor / `CLASS_GAIN_MULT` | divisor cap **3.0**, walls **4.0**; FR **1.0** → SR **1/1.4** | flat integer spend `Σ notches = 24/30`; position/class multiply gain before remainder |
| Shape floors | t0 **P6** + weight scale HIGH **0.50** / LOW **0.20** | Decay clamp + TB Apply (diff-scoped) |
| `STD_RUNG_INCREMENT` (× JH anchor) | FR .17 / SO .20 / JR .15 / SR .18 (Σ .70 → 1.7× at zero peaks) | Per-rung standard growth; sets the class-year ladder |
| `PEAK_BONUS` | `+0.30 × jh_anchor`, fixed per peak | Each rolled peak adds this to the target; peaks stack (0–3), so career multiple runs 1.7× (0 peaks) → 2.6× (3 peaks) |
| `HT_TOTAL` (mean) | `Normal(3.2, 1.9)` clamped `[0,8]`; per-rung cap 2.5 in | Total career height gain; `HT_TOTAL_MEAN = 3.2` in sets how far below frame a JH starts |
| `HT_CURVE_BY_TIMING` (share of career HT gain, FR/SO/JR/SR) | early 55/30/12/3 · **standard 40/30/20/10** · late 15/25/35/25 | When height arrives; standard row is the grow-into-frame stagger |
| `COACHING_F_MIN` / `COACHING_F_MAX` | `0.85` / `1.20` | Bounds on `f` (level only). Currently dormant at 1.0 |
| `NON_CORE_GROWTH_MULTIPLIER` | `0.06` | **Vestigial** — retired distribution path; unused under level-only offseason |
| `RT_COMPRESSION_THRESHOLD` / `RT_SOFT_CAP` | `95` / `130` | RT soft-cap machinery; ~130 is the practical ceiling (individual attributes are uncapped) |
| `OFFSEASON_DISTRIBUTION_BLEND` | `0.70` | **Vestigial** — retired distribution path; unused under level-only offseason |
| `JH_ANCHOR_BY_TIER` | Poor→Elite JH-scale anchors (e.g. Average 30, Elite 50) | Maps `entry_tier` to the `jh_anchor` the target formula multiplies |

## Reshape vs grow — **closed** (grow level, coach shape)

**Surfaced 6 August 2026 via Team Builder §11; resolved 7 August 2026** in [`player-development-framework.md` §11](player-development-framework.md).  
Attractor retired (`OFFSEASON_ATTRACTOR_ALPHA = 0.0`); offseason is level-only; camp + in-season own shape; floors replace the mean pull.  

Historical measurements found that the old `0.55` attractor erased individuality league-wide,
not Team Builder authorship specifically: three Team Builder arms retained roughly 15% of their
initial profile deviation at graduation, while the corrected league-shape measurement projected
career cosine retention of **0.245**. Per-attribute variance had initially hidden the convergence
because level continued to fan out while player shapes collapsed. Those findings justified the
shipped level-only model; they are summarized here so the superseded project notes are unnecessary.

Do not restore α, reclassify archetypes as a workaround, re-derive `potential_factor` from authored
attributes, or create a special freeze for authored players. None addresses the retired league-wide
mean pull.

Two separate follow-ons remain open in
[`Player_Attribute_Recalibration_Backlog.md`](../projects/Player_Attribute_Recalibration_Backlog.md):

- `_coaching_accumulator_for_player` remains dormant, so coaching quality does not yet differentiate
  offseason **level** targets.
- Init recruit-set variety (mean attribute σ 15.7) differs from dynamic post-rollover generation
  (σ 11.6), and `training_position` still lacks a live write path.

## Key Files

- `BackEnd/utils/player_development.py` — offseason event (level-only), growth-profile roll, rollover driver
- `BackEnd/constants/training_shape.py` — camp, cost matrix, class cost mult, weight-scaled P6 floors
- `BackEnd/utils/shape_movement.py` — along/across shape decomposition (measurement / suite)
- `BackEnd/utils/player_generation.py` — JH start, grow-into-frame height draw
- `BackEnd/utils/position_ratings.py` — RT recomputation after development
- `BackEnd/models/training_execution_v2.py` — `execute_training`, gain bands, fractional remainder, decay + floor clamp
- `tests/test_offseason_attractor.py`, `tests/test_in_season_invariants.py`, `tests/test_training_shape_framework.py` — invariant / framework assertions
