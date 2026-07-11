# Refine Comp Player Attributes

## Teams to consider refining player attributes for

- All teams in conferences 2–16
- Conference 1 teams are explicitly excluded

---

## Recruit Archetype Reference

> Recruit-generation reference only (`RecruitManager` in `BackEnd/models/franchise_manager.py`). Comp rewrites use the **trait mappings** below; they do **not** roll height or weight.

Each archetype defines which **profile** attributes roll **Strong**, **Secondary**, or **Standard** (or **Weak** for Below Average). Position ratings use existing height + rolled attributes via `compute_position_ratings()`.

### Profile attributes (12)

`SC, SH, ID, OD, PS, BH, RB, AG, ST, ND, IQ, FT`

The core 12 used for team totals and gameplay. **`CH` is rolled separately** — not part of the archetype profile tier loop.

### Recruit attribute tiers by year

Used for recruit generation (`YEAR_TIER_RANGES` in code):

| Year | STRONG | SECONDARY | STANDARD | WEAK |
|------|--------|-----------|----------|------|
| Freshman | 30–80 | 20–60 | 10–40 | 10–20 |
| Sophomore | 40–85 | 30–70 | 10–50 | 10–30 |
| Junior | 60–95 | 40–80 | 10–60 | 10–50 |
**Note these are directional

### Computer-team rewrite tiers by year

Used when manually rewriting universal comp rosters (conferences 2–16). **Not used for recruit generation.**

| Year | STRONG | SECONDARY | STANDARD | WEAK |
|------|--------|-----------|----------|------|
| Freshman | 30–80 | 20–60 | 10–40 | 10–20 |
| Sophomore | 40–85 | 30–70 | 10–50 | 10–30 |
| Junior + Senior | 60–104 | 40–80 | 10–60 | 10–50 |

**How tiers are applied per archetype (profile attrs only):**

- **Strong attrs** → roll from the year's STRONG range
- **Secondary attrs** → roll from the year's SECONDARY range
- **All other profile attrs** → roll from the year's STANDARD range
- **Below Average** → every profile attr rolls from the year's WEAK range
- **Five-Star** → all 12 profile attrs roll STRONG
- **Four-Star** → all 12 profile attrs roll SECONDARY
- **Average** → all 12 profile attrs roll STANDARD

### Character (`CH`) rolling — recruits

Implemented in `_roll_recruit_character()`:

| Archetype | CH roll |
|-----------|---------|
| **Intangibles** | `random.randint(year STRONG minimum, 100)` — floor from **recruit** `YEAR_TIER_RANGES` (JH 20, FR 30, SO 40, JR 60); **max always 100** (not capped at year STRONG max e.g. 85) |
| **All others** | `random.randint(1, 100)` — fully random, not tier-based |

CH is set before `Player.randomize_game_attributes(..., preserve_character=True)`, which init's `NG`, `MO`, `EM` without overwriting recruit `CH`. Signed recruits keep `CH` through `_normalize_new_franchise_player_attributes` (same preserve flag).

### Archetype selection weights

Weighted random via `random.choices`:

| Archetype | Weight | ~% of pool |
|-----------|--------|------------|
| Five-Star | 1 | ~1.0% |
| Four-Star | 4 | ~4.0% |
| Average | 13.6 | ~13.6% |
| Below Average | 13.6 | ~13.6% |
| Each other archetype (×16) | 3.6 each | ~3.6% each |

**All 20 archetypes:** Five-Star, Four-Star, Defensive Wizard, All-Around Scorer, Classic PG, Classic SG, Classic SF, Classic PF, Classic C, Pure Shooter, Intangibles, Athlete, Inside Defender, Outside Defender, Average, Below Average, Outside Dual Threat, Driver, Outside C, Three & D.

### Archetype trait configs

| Archetype | Strong (STRONG tier) | Secondary (SECONDARY tier) | Standard (everything else) |
|-----------|----------------------|----------------------------|----------------------------|
| **Five-Star** | All 12 profile attrs | — | — |
| **Four-Star** | — | All 12 profile attrs | — |
| **Defensive Wizard** | ID, OD | ST, AG | SC, SH, PS, BH, RB, ND, IQ, FT |
| **All-Around Scorer** | SH, SC | ST, AG | ID, OD, PS, BH, RB, ND, IQ, FT |
| **Classic PG** | BH, PS | OD, IQ | SC, SH, ID, RB, AG, ST, ND, FT |
| **Classic SG** | SH | OD | SC, ID, PS, BH, RB, AG, ST, ND, IQ, FT |
| **Classic SF** | SC, OD | AG | SH, ID, PS, BH, RB, ST, ND, IQ, FT |
| **Classic PF** | RB | ST | SC, SH, ID, OD, PS, BH, AG, ND, IQ, FT |
| **Classic C** | ID, ST | RB, SC | SH, OD, PS, BH, AG, ND, IQ, FT |
| **Pure Shooter** | SH, FT | — | SC, ID, OD, PS, BH, RB, AG, ST, ND, IQ |
| **Intangibles** | IQ, ND | — | SC, SH, ID, OD, PS, BH, RB, AG, ST, FT |
| **Athlete** | AG, ST, ND | — | SC, SH, ID, OD, PS, BH, RB, IQ, FT |
| **Inside Defender** | ST, ID | — | SC, SH, OD, PS, BH, RB, AG, ND, IQ, FT |
| **Outside Defender** | AG, OD | — | SC, SH, ID, PS, BH, RB, ST, ND, IQ, FT |
| **Average** | — | — | All 12 profile attrs |
| **Below Average** | — | — | All 12 profile attrs (WEAK tier) |
| **Outside Dual Threat** | SH, AG | — | SC, ID, OD, PS, BH, RB, ST, ND, IQ, FT |
| **Driver** | SC, AG | — | SH, ID, OD, PS, BH, RB, ST, ND, IQ, FT |
| **Outside C** | ST, SH | — | SC, ID, OD, PS, BH, RB, AG, ND, IQ, FT |
| **Three & D** | SH | ID, OD | SC, PS, BH, RB, AG, ST, ND, IQ, FT |
| **Athletic Shooter** | SH, AG | -- | OD, SC, ID, PS, BH, RB, ST, ND, IQ, FT |
| **Inside Scorer** | SC, ST | RB, ID | SH, OD, PS, BH, AG, ND, IQ, FT |
| **Outlet Passer** | PS, ST | RB, ID | SH, OD, SC, BH, AG, ND, IQ, FT |
| **Scoring PF** | RB, SC | ST | SH, ID, OD, PS, BH, AG, ND, IQ, FT |
| **Defensive PF** | RB, ID | ST | SC, SH, OD, PS, BH, AG, ND, IQ, FT |
| **All-Around Wing** | AG | SC, SH, OD, ID | PS, BH, RB, ST, ND, IQ, FT |
| **Scoring PG** | BH, PS | SC, SH | IQ, OD, ID, RB, AG, ST, ND, FT |


### Post-processing (recruit generation only)

In `generate_recruits_list()` — **not used for comp rewrites**:

1. `_generate_recruit_profile()` rolls 12 profile attrs (recruits also roll height/weight in code).
2. `_roll_recruit_character()` sets `CH` (Intangibles floor by year, others 1–100).
3. `Player.randomize_game_attributes(..., preserve_character=True)` sets `NG`, `MO`, `EM`; preserves `CH`.
4. `compute_position_ratings(recruit, profile="recruit")` derives PG/SG/SF/PF/C.

---

## Comp rewrite algorithm (draft)

Goal: reshape **conferences 2–16** players so attrs reflect a **basketball archetype**, while each player's **core-12 sum is unchanged**. **Existing height, weight, and year are preserved** (never re-rolled). **CH is re-rolled** per comp rules below.

### Inputs (per player)

| Input | Source |
|-------|--------|
| `target_sum` | Current sum of SC…FT (immutable) |
| `band` | Quintile from population rank of `target_sum` (see Player_Attr_Analysis.md) |
| `archetype` | **User-authored assignment logic** (in progress) + new archetypes (TBD) |
| `identity_mode` | `strict` (~75%) or `wildcard` (~25%) — see below |

**Band assignment:** sort all 1,536 comp players by `target_sum`, split into five equal-count groups (same cutpoints as analysis doc). A player's band is determined by their **current total**, not their year.

### Band stats (from gob-staging, 2026 analysis)

| Band | Avg total | Avg ÷ 12 | Low | High |
|------|----------:|---------:|----:|-----:|
| Tier 1: Top 20% (81–100) | 741.9 | 61.8 | 617 | 1,034 |
| Tier 2: 61–80 | 552.8 | 46.1 | 498 | 616 |
| Tier 3: 41–60 | 454.9 | 37.9 | 412 | 497 |
| Tier 4: 21–40 | 353.3 | 29.4 | 290 | 412 |
| Tier 5: Bottom 20% (1–20) | 195.6 | 16.3 | 24 | 289 |

Population reference: mean total **459.9**, median **455.5** (~**38.3** per attr if flat).

### Band-based tier ranges (replaces year table for comp rewrites)

Per-attribute roll ranges are **derived from the player's band**, not year. Formulas (then clamp each attr to **1–100**):

```
μ = band_avg_total / 12          # band mean per attribute
lo = band_low_total / 12         # floor implied by band
hi = band_high_total / 12        # ceiling implied by band

STRONG:     [round(μ × 1.05), min(100, round(hi × 1.05))]
SECONDARY:  [round(μ × 0.85),  min(100, round(μ × 1.25))]
STANDARD:   [1, round(μ × 1.05)]       # floor always 1 — only Below Average uses WEAK
WEAK:       [1, max(1, round(lo × 0.85))]   # Below Average archetype only
```

**Authoritative tier table:** see **4-Step Process → Step 3a** (per-band STRONG / SECONDARY / STANDARD / WEAK ranges).

Ranges are **roll hints**, not caps. Reconciliation pushes attrs toward `target_sum` when rolls miss (including toward 100 when needed).

> **Why band not year:** Year tiers assume development over time. Comp rewrites already have a talent level baked into `target_sum`. Band encodes that talent level using observed roster data.

### Step 1 — Archetype roll (draft attributes)

Roll the **12 profile attrs** (SC…FT) from band tier ranges per archetype strong / secondary / standard / weak mapping. **CH is not part of this roll** — see CH rules below.

Archetype pool for comp rewrites: **all existing recruit archetypes** (Five-Star through Three & D) **plus new archetypes** (definitions TBD — user authoring).

**Example — Classic PG, 41–60 band, `target_sum` = 470:**
- BH, PS → STRONG (40–43)
- OD, IQ → SECONDARY (32–47)
- Everything else → STANDARD (1–40)

Sum the 12 rolls → `draft_sum`.

### Character (`CH`) — comp rewrite rules

CH is **outside** the core-12 `target_sum` (not reconciled against it). Set after profile attrs are finalized:

| Archetype | CH roll |
|-----------|---------|
| **All players** | `random.randint(1, 100)` |

Also set `anchor_CH = CH`. Intangibles strong tier is **IQ, ND** only — CH is not archetype-weighted on comp rewrites.

### Step 2 — Reconcile to `target_sum`

```
delta = target_sum - draft_sum
```

**If `delta > 0` (under budget):** add points one at a time to attrs in priority order until delta = 0:

1. Strong attrs (archetype identity first)
2. Secondary attrs
3. Standard attrs  
Never exceed 100 on an attr. If capped, spill to next priority.

**If `delta < 0` (over budget):** remove points one at a time:

1. Standard attrs first (preserve identity)
2. Secondary attrs
3. Strong attrs last  
Never go below 1.

**Tie-break within a tier:** random among eligible attrs, or prefer attrs furthest from tier midpoint (less distortion).

This guarantees exact sum preservation and keeps most adjustment on non-identity attrs.

### Step 3 — Identity vs wildcard (~75% / ~25%)

| Mode | Rate | Behavior |
|------|------|----------|
| **Strict** | ~75% | Steps 1–2 only. Reconciliation respects strong → secondary → standard priority. |
| **Wildcard** | ~25% | After Step 1, before reconcile: pick **1–2 standard-tier attrs** and re-roll from **STANDARD range of an adjacent band** (one band up or down, 50/50). Then reconcile. Identity attrs (strong/secondary) untouched. |

Wildcard adds variety without extreme outliers — adjacent band STANDARD ranges overlap heavily with the home band, and reconciliation prevents runaway totals.

**Optional mild noise (strict mode):** when rolling STANDARD attrs only, with 15% chance use `randint(standard_lo - 3, standard_hi + 3)` clamped to 1–100 before reconcile. Keeps strong/secondary clean.

### Step 4 — Sanity checks (per player)

- [ ] `sum(attrs) == target_sum`
- [ ] each attr ∈ [1, 100]
- [ ] strong attrs ≥ median of standard attrs (soft check; flag if violated after reconcile)
- [ ] recompute `position_ratings`; optional: flag if best RT moved by >15 vs pre-rewrite

### Decisions (locked)

| # | Decision |
|---|----------|
| 1 | **Archetype assignment** — user-authored logic (separate doc / WIP). New archetypes coming; hang tight before implementation. |
| 2 | **CH** — `randint(1, 100)` for every player (not part of core-12 reconcile). |
| 3 | **Archetype pool** — all existing archetypes **plus** new ones (Athletic Shooter, Inside Scorer, etc.). |
| 4 | **Conference 1** — excluded entirely (no rewrite). |

### Pending (user)

- [ ] Archetype assignment rules
- [ ] New archetype definitions (strong / secondary / standard attrs)
- [ ] Team-level targets (RT distribution, superstar counts, etc.)

### Implementation sketch (future script)

```
for player in conf_2_16_players:
    target_sum = sum(core_12)
    band = quintile_from_lookup(target_sum)
    archetype = assign_archetype(player)   # user logic
    mode = "wildcard" if random.random() < 0.25 else "strict"
    attrs = roll_archetype_attrs(archetype, band, mode)   # SC..FT only
    attrs = reconcile(attrs, target_sum, archetype)
    attrs["CH"] = random.randint(1, 100)
    attrs["anchor_CH"] = attrs["CH"]
    # height, weight, year unchanged on player doc
    recompute position_ratings(existing height, new attrs)
```

---

## Brief (TBD)

Team-level refinement targets (RT distribution, superstar counts, etc.) — to be added after archetype assignment + new archetype defs land.

## 4-Step Process

**Step 1: Get player sum total**
- Sum SC…FT → lock as `target_sum`.
- Assign quintile **band** from population rank of that total (see band table above).

**Step 2: Assign archetype**
- Your assignment logic picks archetype (existing + new).
- No randomness in this step — wildcard is rolled in Step 3 only.

**Step 3: Roll attribute values**

**3a — Core roll (every player)**
- Look up **band tier ranges** below for the player's band.
- For each of the 12 attrs, `randint(lo, hi)` from the tier its archetype slot uses (STRONG / SECONDARY / STANDARD / WEAK).
- Sum rolls → `draft_sum`.

**Per-band roll ranges (STRONG / SECONDARY / STANDARD / WEAK)**

Derived from quintile stats in `Player_Attr_Analysis.md`, manually calibrated. Each cell is `randint(lo, hi)` inclusive.

| Band | STRONG | SECONDARY | STANDARD | WEAK |
|------|--------|-----------|----------|------|
| Top 20% (81–100) | 65–90 | 45–79 | 1–65 | 1–44 |
| 61–80 | 45–70 | 35–55 | 1–45 | 1–35 |
| 41–60 | 40–60 | 32–47 | 1–40 | 1–29 |
| 21–40 | 31–50 | 25–37 | 1–31 | 1–21 |
| Bottom 20% (1–20) | 20–40 | 14–30 | 1–17 | 1–2 |

*Only **Below Average** uses WEAK (all 12 attrs). **Five-Star** → STRONG all 12. **Four-Star** → SECONDARY all 12. **Average** → STANDARD all 12. STANDARD floor is **1** in every band so filler attrs can roll low while identity attrs stay on STRONG/SECONDARY tiers.*

**3b — Wildcard (~25%, Step 3 only)**
- `randint(1, 4) == 1` → wildcard in play; else skip.
- If in play:
  - Pick **2 standard-tier attrs** at random (never strong or secondary).
  - Re-roll each from the **band-scaled wildcard range** (wider than STANDARD, capped by band ceiling):

| Band | Wildcard range |
|------|----------------|
| Top 20% | 45–90 |
| 61–80 | 35–70 |
| 41–60 | 32–60 |
| 21–40 | 25–50 |
| Bottom 20% | 14–40 |

- Re-sum → `draft_sum`.

**Step 4: Reconcile to `target_sum`**

- `delta = target_sum - draft_sum`
- If `delta == 0`, skip to post-steps.

**4a — Split delta across archetype pools (random weights)**

Partition `|delta|` into three random pool budgets that sum to `|delta|`:
- **Strong pool** (archetype strong attrs)
- **Secondary pool**
- **Standard pool**

Random weight draw (then scale to `|delta|`):
- If **adding** (`delta > 0`): strong 45–70%, secondary 20–35%, standard = remainder.
- If **removing** (`delta < 0`): standard 45–70%, secondary 20–35%, strong = remainder (protect identity).

**4b — Apply within each pool (+1 / −1 at a time)**

For each pool with a budget > 0:
- Randomly pick an attr in that pool.
- Apply +1 (if adding) or −1 (if removing).
- Respect cap **100** and floor **1**; if blocked, pick another attr in the pool.
- Repeat until pool budget exhausted.

**4c — Spillover**

If a pool can't absorb its full budget (all attrs capped/floored):
- Spill remaining to the next pool in priority order:
  - Adding: strong → secondary → standard
  - Removing: standard → secondary → strong
- Same +1/−1 random pick rules until `delta` fully applied.

**Post-steps**
- `CH = randint(1, 100)`, set `anchor_CH`
- Recompute `position_ratings` (existing height + new attrs)
- Write to DB (conf 2–16 teams, `gob-staging.players` only)


## Archetype Assingment System

Tier 1:
- top 1% (14 total players) will be assigned Five-Star Archetype
- choose 58 other players at random from Tier 1 to be Four-Star Archetype
- all remaining players go into standard process

Tiers 2 & 3:
- all players go into standard process

Tier 4:
- the bottom 6% (bottom 30% of this tier) are assigned Average Archetype
- all remaining players go into standard process

Tier 5:
- the top 7% (top 35% of this tier) are assigned Average Archetype
- all remaining players are assigne below aveage

Standard Process
- identify the players top RT position from the sister doc in the players_backup collection. If there's a tie, choose one position at random
- choose one of the archeypes below, at random, based on the percentages defined udner the lead RT position

**PG**
- Classic PG (50%)
- All Around Scorer (10%)
- Intangibles (10%)
- Outside Defender (15%)
- Scoring PG (10%)
- Intangibles (5%)

**SG**
- Classic SG (40%)
- Defensive Wizard (5%)
- All Around Scorer (10%)
- Pure Shooter (15%)
- Intangibles (5%)
- Outside Defender (10%)
- Outside Dual Threat (10%)
- Athletic Shooter (5%)

**SF**
- Classic SF (30%)
- Defensive Wizard (10%)
- All Around Scorer (10%)
- Intangibles (5%)
- Athlete (10%)
- Outside Dual Threat (10%)
- Driver (10%)
- Three & D (10%)
- All Around Wing (5%)

**PF**
- Classic PF (40%)
- Intangibles (5%)
- Inside Defender (10%)
- Inside Scorer (10%)
- Scoring PF (15%)
- Defensive PF (15%)
- Intangibles (5%)

**C**
- Classic C (40%)
- Inside Defender (20%)
- Outside C (15%)
- Inside Scorer (20%)
- Outlet Passer (5%)
