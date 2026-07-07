# Refine Comp Player Attributes

## Teams to consider refining player attributes for

- All teams in conferences 2–16
- Conference 1 teams are explicitly excluded

---

## Recruit Archetype Reference

> Source of truth: `RecruitManager` in `BackEnd/models/franchise_manager.py` — `_select_archetype()`, `_generate_recruit_profile()`, `_roll_recruit_character()`, `_generate_weight()`, `YEAR_TIER_RANGES`. Also documented in `_documentation_master/04_Franchise_Mode_Systems/Recruiting_System.md`.

Each archetype defines which **profile** attributes roll **Strong**, **Secondary**, or **Standard** (or **Weak** for Below Average), plus a height range. Position ratings are derived from the rolled attributes via `compute_position_ratings()`.

### Profile attributes (12)

`SC, SH, ID, OD, PS, BH, RB, AG, ST, ND, IQ, FT`

The core 12 used for team totals and gameplay. **`CH` is rolled separately** — not part of the archetype profile tier loop.

### Recruit attribute tiers by year

Used for recruit generation (`YEAR_TIER_RANGES` in code):

| Year | STRONG | SECONDARY | STANDARD | WEAK |
|------|--------|-----------|----------|------|
| JH | 20–80 | 10–60 | 1–40 | 1–20 |
| Freshman | 30–80 | 20–60 | 10–40 | 10–20 |
| Sophomore | 40–85 | 30–70 | 10–50 | 10–30 |
| Junior | 60–95 | 40–80 | 10–60 | 10–50 |

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

### Archetype trait & height configs

| Archetype | Strong (STRONG tier) | Secondary (SECONDARY tier) | Standard (everything else) | Height (in) |
|-----------|----------------------|----------------------------|----------------------------|-------------|
| **Five-Star** | All 12 profile attrs | — | — | 69–80 |
| **Four-Star** | — | All 12 profile attrs | — | 66–78 |
| **Defensive Wizard** | ID, OD | ST, AG | SC, SH, PS, BH, RB, ND, IQ, FT | 66–75 |
| **All-Around Scorer** | SH, SC | ST, AG | ID, OD, PS, BH, RB, ND, IQ, FT | 66–75 |
| **Classic PG** | BH, PS | OD, IQ | SC, SH, ID, RB, AG, ST, ND, FT | 66–72 |
| **Classic SG** | SH | OD | SC, ID, PS, BH, RB, AG, ST, ND, IQ, FT | 66–74 |
| **Classic SF** | SC, OD | AG | SH, ID, PS, BH, RB, ST, ND, IQ, FT | 69–75 |
| **Classic PF** | RB | ST | SC, SH, ID, OD, PS, BH, AG, ND, IQ, FT | 70–76 |
| **Classic C** | ID, ST | RB, SC | SH, OD, PS, BH, AG, ND, IQ, FT | 72–78 |
| **Pure Shooter** | SH, FT | — | SC, ID, OD, PS, BH, RB, AG, ST, ND, IQ | 66–73 |
| **Intangibles** | IQ, ND | — | SC, SH, ID, OD, PS, BH, RB, AG, ST, FT | 66–75 |
| **Athlete** | AG, ST, ND | — | SC, SH, ID, OD, PS, BH, RB, IQ, FT | 66–75 |
| **Inside Defender** | ST, ID | — | SC, SH, OD, PS, BH, RB, AG, ND, IQ, FT | 71–80 |
| **Outside Defender** | AG, OD | — | SC, SH, ID, PS, BH, RB, ST, ND, IQ, FT | 66–74 |
| **Average** | — | — | All 12 profile attrs | 66–75 |
| **Below Average** | — | — | All 12 profile attrs (WEAK tier) | 66–74 |
| **Outside Dual Threat** | SH, AG | — | SC, ID, OD, PS, BH, RB, ST, ND, IQ, FT | 66–75 |
| **Driver** | SC, AG | — | SH, ID, OD, PS, BH, RB, ST, ND, IQ, FT | 66–75 |
| **Outside C** | ST, SH | — | SC, ID, OD, PS, BH, RB, AG, ND, IQ, FT | 72–77 |
| **Three & D** | SH | ID, OD | SC, PS, BH, RB, AG, ST, ND, IQ, FT | 69–75 |

### Weight by height

Weight is derived from rolled height (`_generate_weight`):

| Height (in) | Weight (lbs) |
|-------------|--------------|
| < 72 | 150–181 |
| 72–75 | 170–194 |
| 76–80 | 195–231 |
| > 80 | 209–260 |

### Post-processing (recruit generation)

In `generate_recruits_list()`:

1. `_generate_recruit_profile()` rolls 12 profile attrs + height/weight.
2. `_roll_recruit_character()` sets `CH` (Intangibles floor by year, others 1–100).
3. `Player.randomize_game_attributes(..., preserve_character=True)` sets `NG`, `MO`, `EM`; preserves `CH`.
4. `compute_position_ratings(recruit, profile="recruit")` derives PG/SG/SF/PF/C.

### Quick archetype identity guide

| Archetype | Player identity |
|-----------|-----------------|
| Five-Star | Elite across the board; tallest range |
| Four-Star | Well-rounded, no standout tier |
| Defensive Wizard | Perimeter + interior D, athletic secondary |
| All-Around Scorer | SH/SC focused, athletic secondary |
| Classic PG | Ball handler / passer |
| Classic SG | Shooter with perimeter D secondary |
| Classic SF | Scorer + perimeter D, agile secondary |
| Classic PF | Rebounder, strength secondary |
| Classic C | Interior D + strength, rebound/score secondary |
| Pure Shooter | SH + FT specialist |
| Intangibles | IQ, durability; elevated CH floor by year (up to 100) |
| Athlete | Agility, strength, durability |
| Inside Defender | Big interior stopper |
| Outside Defender | Perimeter lockdown |
| Average | Generic middling profile |
| Below Average | Weak across the board |
| Outside Dual Threat | Shooter + athlete |
| Driver | Slasher / finisher |
| Outside C | Stretch big (ST + SH) |
| Three & D | Shooter with D secondary |

---

## Brief (TBD)

<!-- User to add refinement targets and approach for conferences 2–16 -->
