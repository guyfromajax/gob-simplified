# Player Attribute System (**verified 2026-06-13**)

> Frontend display-order/formatting doc. Verified vs `training-report.js`: emoji map (`getEmotionEmoji` L1103-1109: ≥80 😎 / ≥60 😊 / ≥40 😐 / ≥20 😕 / else 😡) and momentum-pill math (`createMomentumPill` L1112+: green=success / red=error / `(mo/5)*50%` fill, +5→50%) **match exactly**; NG `toFixed(2)`, integer floor for SC–FT (`createAttributeCell` L1046+). **Correction applied:** `ATTRIBUTE_ORDER` is **14 attributes (MO excluded)** at L53-55 — *not* 15 at L16-18. MO is rendered on the **lineup screen** (`set-lineup.js` L1528/L1568), not in the Training Report grid; `createAttributeCell` retains an MO branch but the Report's order array never feeds it MO.

---

## Attribute Generation & Progression

**Scope:** New franchises only. Governs how player attributes are generated at entry and how they grow across a four-year career (JH → FR → SO → JR → SR). Written at all four creation points: universal pool, franchise player docs, recruits, walk-ons.

> Reasoning, rejected options, migration record and validation narrative are archived at `_documentation_master/projects/Z-Completed/Player_Attribute_Recalibration_Design.md`.

### Entry tiers

JH RT is drawn from a single right-skewed distribution; tiers are labels on bands of it, not separate generation paths. `entry_tier` and `position_intent` are top-level fields on the player.

| Tier | JH RT anchor | SR RT (1 peak) | Frequency |
|---|---|---|---|
| Poor | ~20 | 40 | 7% |
| Below Average | ~25 | 50 | 20% |
| Average | 30 | 60 | 40% |
| Good | 35 | 70 | 20% |
| Great | 40 | 80 | 11% |
| Elite | 50 | 100 | 2% |

- Right-skewed by design: Elite is +20 above Average, Poor only −10 below. No mirrored bottom tier; floor ~RT 18-20.
- Tier is a label, not a mechanic. Rung multipliers and the growth model are tier-independent — they multiply whatever JH anchor was drawn. Nothing branches on tier.
- Recruits entering as FR/SO/JR are slotted onto the ladder at their year and walk the remaining rungs.
- Walk-ons run through the same generator at Poor tier with a drawn position intent (~3 of 15 per roster).

### Class-year ladder (rungs)

Career growth applies as multipliers of the JH anchor. `RUNG_MULTIPLIERS`, one-peak path (peak at SO→JR):

| Rung | Multiplier | Average | Good | Great | Elite |
|---|---|---|---|---|---|
| JH | 1.00 | 30 | 35 | 40 | 50 |
| FR | 1.17 | 35 | 41 | 47 | 58 |
| SO | 1.43 | 43 | 50 | 57 | 72 |
| JR (peak) | 1.80 | 54 | 63 | 72 | 90 |
| SR | 2.00 | 60 | 70 | 80 | 100 |

- Measured class p50 RT for the Average tier lands **~35 / 41 / 54 / 60** (FR/SO/JR/SR).
- Standard (non-peak) per-rung increments `STD_RUNG_INCREMENT` × JH anchor: FR .17 / SO .20 / JR .15 / SR .18 (Σ .70 → 1.7x career at zero peaks). Peaks add `PEAK_BONUS` on top.
- Spacing is deliberately middle-bulged, not even: front-loading makes freshmen too good; back-loading makes the first two seasons feel dead.

### Growth profiles — peaks

Two independent systems rolled at generation, stored on the player, never displayed: peak count (*how much*) and family timing (*when*).

Peak counts **stack** — more peaks = more total career growth, not redistribution of a fixed budget:

| Peaks | Share (`PEAK_COUNT_DISTRIBUTION`) | Career multiple | Average ends | Elite ends |
|---|---|---|---|---|
| 0 | 20% | 1.7x | ~50 | ~85 |
| 1 | 55% | 2.0x | 60 | 100 |
| 2 | 22% | 2.3x | ~70 | ~115 |
| 3 | 3% | 2.6x | ~78 | ~130 |

- `PEAK_BONUS` = +0.30 × JH anchor, fixed per peak (not a rung multiplier).
- Which rung peaks is a second roll, `PEAK_RUNG_WEIGHTS`: JR .42 > SO .28 > SR .20 > FR .10. A JH→FR peak is the freshman phenom; a JR→SR peak the late bloomer.
- Peaks apply identically at every tier; because they are multipliers, outcomes scale. Development can beat recruiting by ~1 tier, but not more — recruiting stays the dominant lever.
- CH drives the peak-count distribution (`CH_PEAK_WEIGHTING`), shifting it up/down; it stays probabilistic (a high-CH recruit can still roll zero peaks — the bust).

### CH — the hidden driver

- `ch_seed` — frozen at generation, immutable, hidden, drives the peak-count distribution. Independent of `entry_tier`, which creates the diamond in the rough (a Poor entrant with high CH and three peaks).
- Live `CH` — remains trainable and fatigue-relevant for whatever the sim reads.
- CH distribution is flat `randint(1,100)`.
- CH is re-rolled at each franchise init unless `preserve_character`, so the same universal player develops differently across saves.

### Attribute families

Growth is shaped per family so a player *reads* differently at FR (raw athlete, no feel) than at SR (polished), not merely larger:

| Family | Attributes | Curve |
|---|---|---|
| Physical | ST, AG (+ HT, WT) | Front-loaded; essentially complete by end of SO |
| Skill | SC, SH, ID, OD, PS, BH, RB, FT | Steady across all four rungs |
| Mental | IQ, ND | Back-loaded |

- `CH` is not in a family (hidden driver, above).
- Family assignment is independent of the malleable/static split (`SC SH ID OD PS BH RB ST AG FT` vs `ND IQ CH EM MO`), which governs fatigue rescaling, not development. The two must not be conflated.

`FAMILY_CURVES` — weight multiplier per rung (physical / skill / mental):

| Rung | Physical | Skill | Mental |
|---|---|---|---|
| FR | 3.0 | 1.0 | 0.30 |
| SO | 2.0 | 1.2 | 0.60 |
| JR | 0.60 | 1.3 | 2.2 |
| SR | 0.35 | 1.2 | 3.2 |

Resulting share of each rung's growth (phys/skill/mental): FR 35/58/7 · SO 26/65/9 · JR 11/66/23 · SR 9/61/30. Mental share is position-weighted (a PG gains more RT credit for IQ than an SF does).

Family timing — three independent rolls at generation (`FAMILY_TIMING_WEIGHTS`):

| Family | Early | Standard | Late |
|---|---|---|---|
| Physical | 30% | 55% | 15% |
| Skill | 25% | 50% | 25% |
| Mental | 20% | 50% | 30% |

Peaks control *how much*; timing controls *when*. The two axes stay orthogonal in code.

**HT has its own curve** (`HT_CURVE_BY_TIMING`), separate from the physical family — it is the only attribute whose growth can change a player's best position. Career HT gain `HT_TOTAL` ~Normal(3.2, 1.9) clamped [0,8]; ~8% of players gain none. HT growth flips a player's best position ~5.3% of the time.

### RT ceiling & above-100 attributes

- RT gains compress above `RT_COMPRESSION_THRESHOLD` = 95 and approach a practical ceiling `RT_SOFT_CAP` = 130 (`_compress_rt`). Elite entry with three peaks lands ~130.
- Individual attributes are **not** capped at 130 — a few reaching 140-150 is intended, arising from specialization (RT is a weighted mean, so concentrating growth spikes two attributes while RT stays moderate).
- Players with any attribute ≥ 100 land at **~5.5% of the pool** (up to ~7.5% in the fitted growth model, ~19% of seniors). Accepted as structural, not tuned away.

### Growth mechanics (summary)

- **Offseason development event** fires at season rollover, before Training Camp: look up rung → base budget → apply CH-seeded peak check → apply family-timing modifiers → distribute across attributes by position weights × family curve → roll HT/WT → recompute all five RTs → emit a report. Non-core attributes grow slowly but never zero out.
- **In-season training shapes rather than earns** — weekly decay and per-point gains both shrunk so net stays roughly flat under reference (baseline) coaching; attributes still move visibly. Specialization is expressed as *rate*, not direction: everything grows, focused attributes grow much faster.
- **Accumulator** — in-season allocation aims the offseason budget (attributes trained most get the largest offseason share) and is separately scored to a coaching-quality signal. It is also the mid-season switch penalty: switch focus late and the aim scrambles.
- **Coaching-quality multiplier** (`f`, bounded [0.85, 1.20]) is built but currently **dormant** — the live seam returns None so `f` = 1.0 for every player and the league holds exactly on the ladder. It activates with per-player training focus (planned).

### Data model

`entry_tier` and `position_intent` are top-level fields. Growth state is one nested subdocument:

```
entry_tier            // top-level
position_intent       // top-level

development: {
  peak_count,         // 0-3, rolled at generation
  peak_rungs,         // e.g. ["SO_JR", "JR_SR"]
  family_timing: { physical, skill, mental },   // early | standard | late
  ch_seed,            // frozen career CH, hidden
  focus_accumulator   // in-season aiming → offseason budget
}
```

- Carried forward explicitly by `finish_season`; a dropped field silently reverts a player to the default curve.
- Players with no profile (legacy saves) get one rolled and persisted on first encounter (lazy backfill), with peaks assigned to remaining rungs only.

### Tunable Constants

| Constant | Value | Effect |
|---|---|---|
| `JH_ANCHOR_BY_TIER` | 20/25/30/35/40/50 | JH RT anchor per tier (Poor→Elite) |
| `TIER_FREQUENCY` | .07/.20/.40/.20/.11/.02 | Share of generated players per tier |
| `RUNG_MULTIPLIERS` | 1.00/1.17/1.43/1.80/2.00 | JH→SR one-peak ladder |
| `STD_RUNG_INCREMENT` (× anchor) | FR .17 / SO .20 / JR .15 / SR .18 | Non-peak per-rung growth (Σ .70 → 1.7x) |
| `PEAK_COUNT_DISTRIBUTION` | .20/.55/.22/.03 | 0-3 peaks, before CH weighting |
| `PEAK_BONUS` | +0.30 × JH anchor per peak | Career growth added per peak |
| `PEAK_RUNG_WEIGHTS` | JR .42 / SO .28 / SR .20 / FR .10 | Where a single peak lands |
| `CH_PEAK_WEIGHTING` | low→high spread | How `ch_seed` shifts the peak distribution |
| `CH_DISTRIBUTION` | flat `randint(1,100)` | Career CH seed source |
| `FAMILY_CURVES` | FR 3.0/1.0/.30 · SO 2.0/1.2/.60 · JR .60/1.3/2.2 · SR .35/1.2/3.2 | Per-rung phys/skill/mental growth weights |
| `FAMILY_TIMING_WEIGHTS` | phys 30/55/15 · skill 25/50/25 · mental 20/50/30 | Early/standard/late timing odds |
| `HT_TOTAL` | Normal(3.2, 1.9) clamp [0,8], 2.5 in/rung cap | Career height gain |
| `NON_CORE_GROWTH_MULTIPLIER` | 0.06 | Vestigial — offseason additive-budget floor, superseded by the shape attractor (see `Player_Development_System.md`) |
| `RT_COMPRESSION_THRESHOLD` | 95 | RT above which gains compress |
| `RT_SOFT_CAP` | 130 | Practical RT ceiling |
| `COACHING_F_MIN` / `COACHING_F_MAX` | 0.85 / 1.20 | Bounds on the (dormant) coaching multiplier |
| `QUALITY_CAP` | 4 pts/attr/week | Coaching-quality saturation point |

---

> The remainder of this document covers attribute **display** (order and formatting).

## Base Constants

**Purpose:** Defines the standard display order and formatting rules for player attributes across all game interfaces.

**Core Attribute Order (Training Report = 14 attributes; MO is a 15th attribute shown only on the lineup screen):**
1. SC - Shooting Close
2. SH - Shooting
3. ID - Inside Defense
4. OD - Outside Defense
5. PS - Passing
6. BH - Ball Handling
7. RB - Rebounding
8. ST - Strength
9. AG - Agility
10. ND - Endurance
11. IQ - Intelligence Quotient
12. FT - Free Throws
13. NG - Nerve/Game (Energy)
14. EM - Emotion
15. MO - Momentum *(excluded from `ATTRIBUTE_ORDER` / Training Report; rendered on the lineup screen)*

**Formatting Rules:**
- **SC through FT (12 attributes)**: Integer values, no decimals
- **NG**: Decimal with 2 places (0.00-1.00)
- **EM**: Emoji display (0-100 range)
- **MO**: Red/Green horizontal pill visualization (-5 to +5)

**Key Files:**
- `FrontEnd/static/training-report.js` - Attribute order constant and display logic
- `FrontEnd/static/training-report.css` - Momentum pill styling
- `FrontEnd/static/set-lineup.js` - Lineup screen attribute display

## System Flow

1. **Attribute Order Constant**: `ATTRIBUTE_ORDER` array defines standard order
2. **Display Rendering**: All attribute displays use this order for consistency
3. **Formatting Application**: Each attribute type uses appropriate formatting (integer, decimal, emoji, pill)
4. **Subset Displays**: When showing subset, maintain relative order

## Long Form Documentation

### Overview

The Player Attribute System ensures consistency in how player attributes are presented across all game interfaces. This includes the standard display order, formatting rules for different attribute types, and visual representations for special attributes (NG, EM, MO).

**Status:** ✅ Fully implemented - Standard attribute order enforced in Training Report and other displays

**Location:** Frontend display logic  
**Key Constant:** `ATTRIBUTE_ORDER` in `training-report.js` (~L53-55) — **14 entries, MO excluded** (see code comment L52: "MO (Momentum) is excluded from Training Report display")

### Standard Attribute Display Order

**CRITICAL:** When displaying player attributes in a horizontal row, they must appear in this exact order. *(The Training Report renders #1-14 only; MO (#15) is shown on the lineup screen, not the Report grid.)*

1. **SC** - Shooting Close
2. **SH** - Shooting
3. **ID** - Inside Defense
4. **OD** - Outside Defense
5. **PS** - Passing
6. **BH** - Ball Handling
7. **RB** - Rebounding
8. **ST** - Strength
9. **AG** - Agility
10. **ND** - Endurance
11. **IQ** - Intelligence Quotient
12. **FT** - Free Throws
13. **NG** - Nerve/Game (Energy)
14. **EM** - Emotion
15. **MO** - Momentum

**Implementation:**
```javascript
// FrontEnd/static/training-report.js (~L53-55) — MO intentionally excluded
const ATTRIBUTE_ORDER = [
  'SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT', 'NG', 'EM'
];
```

> MO is **not** in this array, so the Training Report grid does not render it. MO's pill is shown on the lineup screen instead (`set-lineup.js`). The `createAttributeCell` MO branch (`training-report.js` ~L1074) only fires if a caller passes `MO`, which `ATTRIBUTE_ORDER` no longer does.

**Applies To:**
- Training Report Player Report section
- Lineup screens
- Player detail pages
- Any other attribute grid or table displays
- Subset displays (maintain relative order)

### Attribute Display Formatting

#### Standard Integer Attributes (SC through FT)

The first 12 attributes (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT) are displayed as **integer values**:
- No decimal places
- Direct numeric display (e.g., `85`, `72`, `50`)
- Range: 0-100 (typical)

#### NG (Nerve/Game / Energy)

- **Format:** Decimal value with 2 decimal places
- **Range:** 0.00 to 1.00 (typically displayed as 0.90, 0.99, 1.00, etc.)
- **Display Examples:** `1.00`, `0.99`, `0.98`, `0.90`, `0.75`
- **Purpose:** Represents player energy level (100% = 1.00)
- **Storage:** Stored as float in player attributes

#### EM (Emotion)

- **Format:** Emoji display based on value
- **Range:** 0-100
- **Emoji Mapping:**
  - **>= 80:** 😎 (Sunglasses) - Very positive
  - **>= 60:** 😊 (Big smile) - Positive
  - **>= 40:** 😐 (Straight face) - Neutral
  - **>= 20:** 😕 (Slight frown) - Negative
  - **< 20:** 😡 (Angry face) - Very negative
- **Purpose:** Visual representation of player emotional state
- **Implementation:** Value converted to emoji during display rendering

#### MO (Momentum)

- **Format:** Red/Green horizontal pill visualization
- **Range:** -10 to +10
- **Visual Design:**
  - **Container:** Horizontal pill with dark background
  - **Center Line:** Yellow vertical line at 50% (center point)
  - **Positive Momentum (0 to +10):** Green fill extending right from center
    - Fill width proportional to value (e.g., +5 = 25% fill, +10 = 50% fill)
  - **Negative Momentum (-10 to 0):** Red fill extending left from center
    - Fill width proportional to absolute value (e.g., -5 = 25% fill, -10 = 50% fill)
  - **No Integer Display:** The numeric value is NOT displayed on top of the pill
- **Purpose:** Visual representation of player momentum trend
- **CSS:** Styled in `training-report.css`

### Implementation Examples

**Training Report Player Report:**
- **Attributes view:** Displays the 14 `ATTRIBUTE_ORDER` attributes (SC–EM) in standard order with appropriate formatting (MO excluded)
- **Training Changes view:** Displays only changed attributes, maintaining standard order
- **Code:** `training-report.js` uses `ATTRIBUTE_ORDER` constant to filter and order attributes

**Lineup Screens:**
- Follows same order and formatting rules
- EM and MO use same visual representations
- Reference implementation in `set-lineup.js`

**Player Detail Pages:**
- Should follow same order and formatting rules
- When displaying a subset of attributes, maintain relative order (e.g., if showing SC, SH, MO, they appear in that order)

### Key Files

**Frontend:**
- `FrontEnd/static/training-report.js` - Training Report attribute display implementation
  - `ATTRIBUTE_ORDER` constant (~L53-55, 14 entries, MO excluded)
  - Attribute filtering and ordering logic (~L937-951)
  - `createAttributeCell` NG/EM/MO formatting (~L1046), `getEmotionEmoji` (~L1103), `createMomentumPill` (~L1112)
- `FrontEnd/static/training-report.css` - Momentum pill styling
- `FrontEnd/static/set-lineup.js` - Lineup screen attribute display (reference for EM/MO formatting)

**Backend:**
- `BackEnd/models/player.py` - Player class with attribute storage
- `BackEnd/constants/__init__.py` - Attribute constant definitions (if any)

### Consistency Requirements

**All attribute displays must:**
1. Use the exact order defined in `ATTRIBUTE_ORDER`
2. Apply appropriate formatting based on attribute type
3. Maintain relative order when displaying subsets
4. Use consistent visual representations for NG, EM, and MO

**Benefits:**
- ✅ **User Experience:** Consistent attribute presentation across all interfaces
- ✅ **Maintainability:** Single source of truth for attribute order
- ✅ **Visual Clarity:** Special formatting for NG, EM, MO improves readability
- ✅ **Scalability:** Easy to add new attributes while maintaining order
