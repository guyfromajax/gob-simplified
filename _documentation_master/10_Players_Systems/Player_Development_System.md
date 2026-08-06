# Player Development System

> How players grow across a college career. The primary growth event is the **offseason development event**, fired once per player at each season rollover; in-season training only *shapes* and *aims* it. Reasoning and derivation live in the archived design doc: `_documentation_master/projects/Z-Completed/Player_Attribute_Recalibration_Design.md`.

**Module:** `BackEnd/utils/player_development.py` — `develop_one_offseason`, `develop_rollover`, `roll_growth_profile`.

## Offseason Development Event

Fires **once per player per rollover** (the offseason between seasons), before Training Camp. It targets an **absolute** rating, not an incremental budget:

```
target_RT = _compress_rt( jh_anchor × ladder_multiplier(rung) × coaching_factor f × potential_factor )
```

- `jh_anchor` — the player's JH-scale anchor, derived from `entry_tier` via `JH_ANCHOR_BY_TIER`.
- `ladder_multiplier(rung)` — the class-year rung on the ladder. **Includes the player's peak bonuses** (peaks stack on top of the standard rung increments).
- `f` — coaching-quality multiplier, bounded `[0.85, 1.20]`. **Currently dormant at 1.0** for every player (`_coaching_accumulator_for_player` hardwired to `None`), so the league holds exactly on the ladder until per-player allocation capture ships. **Open:** is that unfinished, deliberate, or a bug? See [Reshape vs grow](#reshape-vs-grow--open-simulation-design) — inert `f` plus a strong shape attractor is why the league converges rather than softens.
- `potential_factor` — career-static ±15% ceiling scalar (`POTENTIAL_FACTOR_BAND = 0.15`), drawn once at generation, independent of `entry_tier` and `ch_seed`. **LIVE** (Potential Rating Phase 3). A pure scalar on the target, so it lifts the *level* with the *same profile shape* — a shooter stays a shooter. Legacy players with no stored value resolve deterministically from `player_id` (`resolve_potential_factor`).
- `_compress_rt` — soft cap near `RT_SOFT_CAP = 130`, asymptote ≈ 138. Below the cap it is identity; it only bends the very top. The extreme cohort Elite × 3-peak × 1.15 targets `50 × 2.6 × 1.15 = 149.5`, compressed to **137.3**. (Achieved RT, recomputed from attributes, can overshoot the compressed target for a <0.1% tail — a pre-existing property of recompute-from-attributes, not introduced by `potential_factor`.)

Because the target is absolute and re-anchored every rollover, nothing drifts: in-season movement is either re-absorbed or, under good coaching, kept as a bounded residual below the smallest rung increment.

**Developed players land on the ladder (2026-08 attractor-level fix).** The offseason now closes the LEVEL fully (see Shape Attractor), so a developed senior's median RT sits **exactly on his tier anchor** — pinned by `test_developed_seniors_land_on_tier_anchors`. Before the fix the α-step undershot a rising target and developed seniors landed at ~0.91× the anchor (Elite 91, not 100); it was masked for a long time because **generation** hits the anchors by construction and only cohort turnover exposes the drift. Career multiple by peak count is now exact: 0/1/2/3 peaks → 1.70/2.00/2.30/2.60×.

**Senior RT spread by tier (measured, p10/p50/p90, positions pooled).** With `f` dormant and `potential_factor` live: Poor 34/40/48 · BelowAvg 42/50/60 · Average 51/60/72 · Good 59/70/84 · Great 68/80/96 · Elite 85/100/120. **Medians land on the anchors** (40/50/60/70/80/100); `potential_factor` widens each adjacent-tier tail overlap by only ~2–3 RT on top of the peak-driven baseline (peaks are the dominant spread source). This blur is the design intent — it stops the projected-potential display from leaking `entry_tier`.

**RNG note (precise).** `potential_factor` is drawn **last** inside `generate_player`, so every *prior* draw for that same player (core attributes, CH, EM, weight) keeps its exact stream position — those fields are byte-identical to before the feature. However, the generator's `rng` is **shared across a generation run**, so consuming one extra value per player shifts the stream for every *subsequent* player in that run: **any seeded regeneration now yields a different downstream population than it did pre-feature.** This is harmless here — the retroactive pool write (Phase 5) and the projection read (Phase 4) both read stored state and never invoke generation — but a test that pins an exact seeded population across the whole run will differ.

## Shape Attractor

Constant: `OFFSEASON_ATTRACTOR_ALPHA = 0.55`.

> **Open design question (2026-08-06):** this constant reshapes players toward a positional mean on a career schedule nobody chose against. See [Reshape vs grow](#reshape-vs-grow--open-simulation-design). Do not retune α as a casual lever until that question is answered.

Rather than distributing an additive budget, the offseason targets **both a level** (the ladder RT) **and a shape** (the position/tier/year profile), and it separates them (2026-08 attractor-level fix):

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
| `OFFSEASON_ATTRACTOR_ALPHA` | `0.55` | Fraction of the gap to the profile closed each offseason. See [Reshape vs grow](#reshape-vs-grow--open-simulation-design) before retuning — career retention at 0.55 is ~9% for a freshman, and the constant was fitted against single-season feel, not a four-year criterion. |
| `STD_RUNG_INCREMENT` (× JH anchor) | FR .17 / SO .20 / JR .15 / SR .18 (Σ .70 → 1.7× at zero peaks) | Per-rung standard growth; sets the class-year ladder |
| `PEAK_BONUS` | `+0.30 × jh_anchor`, fixed per peak | Each rolled peak adds this to the target; peaks stack (0–3), so career multiple runs 1.7× (0 peaks) → 2.6× (3 peaks) |
| `HT_TOTAL` (mean) | `Normal(3.2, 1.9)` clamped `[0,8]`; per-rung cap 2.5 in | Total career height gain; `HT_TOTAL_MEAN = 3.2` in sets how far below frame a JH starts |
| `HT_CURVE_BY_TIMING` (share of career HT gain, FR/SO/JR/SR) | early 55/30/12/3 · **standard 40/30/20/10** · late 15/25/35/25 | When height arrives; standard row is the grow-into-frame stagger |
| `COACHING_F_MIN` / `COACHING_F_MAX` | `0.85` / `1.20` | Bounds on the coaching multiplier `f` — coaching is worth ≈ ±1 tier step. Currently dormant at 1.0 |
| `NON_CORE_GROWTH_MULTIPLIER` | `0.06` | **Vestigial** — the additive budget's non-signature floor; the shape attractor replaced that path. Non-signature filling now comes from the target profile's `PROFILE_FILLER`. |
| `RT_COMPRESSION_THRESHOLD` / `RT_SOFT_CAP` | `95` / `130` | RT gains compress above 95; ~130 is the practical ceiling (individual attributes are uncapped) |
| `OFFSEASON_DISTRIBUTION_BLEND` | `0.70` | **Vestigial** — the additive-budget distribution blend; superseded by the shape attractor (`OFFSEASON_ATTRACTOR_ALPHA`). |
| `JH_ANCHOR_BY_TIER` | Poor→Elite JH-scale anchors (e.g. Average 30, Elite 50) | Maps `entry_tier` to the `jh_anchor` the target formula multiplies |

## Reshape vs grow — open simulation design

**Surfaced 6 August 2026 via Team Builder §11. Not a Team Builder problem.**  
TB measurement: `projects/s11-authorship-drift-findings.md`. Closed TB brief: `projects/s11-development-vs-authorship.md`.

### What the measurement actually found

Three arms on one median roster, same seed — control **0.147** · realistic **0.150** · extreme **0.147** retained profile-deviation at graduation.

Authorship is not being erased. **Individuality is**, and the same force hits all 128 programs every offseason. The α-blend toward `position_profile(training_position)` is proportional: it takes the same 55% bite out of everyone's distance from the positional mean. A user's authored 6'2" centre and an untouched base-league centre converge at the same rate.

Team Builder did not create this. It made it visible — third instrument finding after the empty defenses cache and the 443 in-loop DB writes per quarter.

### The number nobody chose against a career

At `OFFSEASON_ATTRACTOR_ALPHA = 0.55`, a freshman retains `(1 − α)³ ≈ 9%` of distinctive shape by graduation. Measurement found **~8%** — the model is behaving exactly as specified.

| Career retention target | Required α |
|---|---:|
| 75% across four years | ≈ 0.09 |
| 50% across four years | ≈ 0.21 |
| **Current** | **0.55** |

Current α is 2.6×–6× stronger than either career target. Tunable_Constants documents it as fitted for **single-season feel** (Average C SC ~52, focus spike ~+8). Confirm with whoever picked it before retuning — they may have had a reason — but the spread is large enough that it reads as a constant chosen without a career-length criterion.

### Separate open question — coaching differentiation is inert

`_coaching_accumulator_for_player` is hardwired to `None`, so `f ≡ 1.0` for every player.

The input that would differentiate development between programs is inert. Strong force toward the positional mean; nothing pushing programs apart. That is why the league converges rather than merely softening.

Is that unfinished (pillar 3 not shipped), deliberately disabled, or a bug? Needs its own answer. It may be the more consequential of the two findings.

### Dead options from the TB framing

| Option | Why dead |
|---|---|
| Re-run archetype classification at Establish | Blend targets `position_profile(training_position)`, not archetype. Reclassifying changes nothing unless it changes training position, and it wouldn't fix homogenization for anyone else. |
| Re-derive `potential_factor` from authored attrs | Scalar on growth *magnitude*. Does not touch the blend target. |
| Freeze authored attributes | Two classes of player; permanent special case. Still wrong. |

Both of the first two assumed authorship was the victim. It isn't.

### The actual question

**Should development reshape a player, or grow him?**

- **Reshape (current):** blend toward a positional mean. Necessarily subtracts from whatever a player is best at — that is where he is furthest from the mean. A 90-rebounding centre losing rebounding as he matures is regression to type wearing development's clothes.
- **Grow (alternative):** mostly add, distributed with a bias toward positional needs; subtract only in decline. Players improve; they don't get averaged. Preserves individuality without exempting anyone.

This is a core simulation decision. It affects scouting, recruiting, whether the SIGNATURE bars on the roster screen mean anything after year two, and whether two programs feel different in season three.

### Product asymmetry (why TB still matters as the symptom)

Everyone loses their shape. Only the Team Builder user *chose* theirs. The mechanism is not TB-specific and TB is not disadvantaged relative to the league — but the experience is worse for exactly the users who paid the most attention. That is why TB is the reason this surfaced, not an argument for a TB-specific fix.

### Before choosing — measure league-wide convergence

One roster proved the mechanism. The headline needs the league.

Measure attribute spread across all 128 programs' players at **t0 vs t+3**:
- standard deviation per attribute
- distance between best and worst team at each position

| If… | Then… |
|---|---|
| The league is measurably flattening | Headline finding; outranks TB-plan work. Model change (grow vs reshape), not a constant tweak. |
| Spread holds because recruiting injects variety faster than the blend removes it | α is a tuning question — cheaper. Still confirm career criterion before dialing. |

Either way, that measurement decides constant-vs-model before anything is designed.

## Key Files

- `BackEnd/utils/player_development.py` — offseason event, growth-profile roll, rollover driver
- `BackEnd/utils/player_generation.py` — JH start, grow-into-frame height draw
- `BackEnd/utils/position_ratings.py` — RT recomputation after development
- `BackEnd/models/training_execution_v2.py` — `execute_training`, anchor/live reset at week 1
- `tests/test_offseason_attractor.py`, `tests/test_in_season_invariants.py` — invariant assertions
