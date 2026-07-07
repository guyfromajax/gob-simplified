# Refine Comp Player Attributes

## Teams to consider refining player attributes for

- All teams in conferences 2–16
- Conference 1 teams are explicitly excluded

---

## Recruit Archetype Reference

> Source of truth: `RecruitManager` in `BackEnd/models/franchise_manager.py` — `_select_archetype()`, `_generate_recruit_profile()`, `_generate_weight()`, `YEAR_TIER_RANGES`. Also documented in `_documentation_master/04_Franchise_Mode_Systems/Recruiting_System.md`.

This is the same archetype system used when generating recruits. Each archetype defines which attributes roll **Strong**, **Secondary**, or **Standard** (or **Weak** for Below Average), plus a height range. Position ratings are then derived from the rolled attributes via `compute_position_ratings()`.

### Rolled attributes (13)

`SC, SH, ID, OD, PS, BH, RB, AG, ST, ND, IQ, FT, CH`

The core 12 used for team totals and gameplay are `SC` through `FT` (excludes `CH`). `CH` is still rolled per archetype but is overwritten during post-processing (see below).

### Attribute tiers by year

Every attribute rolls from one of four tiers. The recruit's **year** selects which numeric ranges apply:

| Year | STRONG | SECONDARY | STANDARD | WEAK |
|------|--------|-----------|----------|------|
| JH | 20–80 | 10–60 | 1–40 | 1–20 |
| Freshman | 30–80 | 20–60 | 10–40 | 10–20 |
| Sophomore | 40–85 | 30–70 | 10–50 | 10–30 |
| Junior | 60–95 | 40–80 | 10–60 | 10–50 |

**How tiers are applied per archetype:**

- **Strong attrs** → roll from the year's STRONG range
- **Secondary attrs** → roll from the year's SECONDARY range
- **All other attrs** → roll from the year's STANDARD range
- **Below Average** → every attr rolls from the year's WEAK range (ignores strong/secondary lists)
- **Five-Star** → all 13 attrs roll STRONG
- **Four-Star** → all 13 attrs roll SECONDARY
- **Average** → all 13 attrs roll STANDARD (no strong/secondary)

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
| **Five-Star** | All 13 attrs | — | — | 69–80 |
| **Four-Star** | — | All 13 attrs | — | 66–78 |
| **Defensive Wizard** | ID, OD | ST, AG | SC, SH, PS, BH, RB, ND, IQ, FT, CH | 66–75 |
| **All-Around Scorer** | SH, SC | ST, AG | ID, OD, PS, BH, RB, ND, IQ, FT, CH | 66–75 |
| **Classic PG** | BH, PS | OD, IQ | SC, SH, ID, RB, AG, ST, ND, FT, CH | 66–72 |
| **Classic SG** | SH | OD | SC, ID, PS, BH, RB, AG, ST, ND, IQ, FT, CH | 66–74 |
| **Classic SF** | SC, OD | AG | SH, ID, PS, BH, RB, ST, ND, IQ, FT, CH | 69–75 |
| **Classic PF** | RB | ST | SC, SH, ID, OD, PS, BH, AG, ND, IQ, FT, CH | 70–76 |
| **Classic C** | ID, ST | RB, SC | SH, OD, PS, BH, AG, ND, IQ, FT, CH | 72–78 |
| **Pure Shooter** | SH, FT | — | SC, ID, OD, PS, BH, RB, AG, ST, ND, IQ, CH | 66–73 |
| **Intangibles** | IQ, ND, CH | — | SC, SH, ID, OD, PS, BH, RB, AG, ST, FT | 66–75 |
| **Athlete** | AG, ST, ND | — | SC, SH, ID, OD, PS, BH, RB, IQ, FT, CH | 66–75 |
| **Inside Defender** | ST, ID | — | SC, SH, OD, PS, BH, RB, AG, ND, IQ, FT, CH | 71–80 |
| **Outside Defender** | AG, OD | — | SC, SH, ID, PS, BH, RB, ST, ND, IQ, FT, CH | 66–74 |
| **Average** | — | — | All 13 attrs | 66–75 |
| **Below Average** | — | — | All 13 attrs (WEAK tier) | 66–74 |
| **Outside Dual Threat** | SH, AG | — | SC, ID, OD, PS, BH, RB, ST, ND, IQ, FT, CH | 66–75 |
| **Driver** | SC, AG | — | SH, ID, OD, PS, BH, RB, ST, ND, IQ, FT, CH | 66–75 |
| **Outside C** | ST, SH | — | SC, ID, OD, PS, BH, RB, AG, ND, IQ, FT, CH | 72–77 |
| **Three & D** | SH | ID, OD | SC, PS, BH, RB, AG, ST, ND, IQ, FT, CH | 69–75 |

### Weight by height

Weight is derived from rolled height (`_generate_weight`):

| Height (in) | Weight (lbs) |
|-------------|--------------|
| < 72 | 150–181 |
| 72–75 | 170–194 |
| 76–80 | 195–231 |
| > 80 | 209–260 |

### Post-processing (after profile roll)

In `generate_recruits_list()`:

1. `Player.randomize_game_attributes(attributes)` sets `NG = 1.0`, `MO = 0`, and **overwrites `CH`** with `random.randint(1, 100)` and sets `EM = random.randint(1, 100)`. This means the archetype-rolled `CH` (e.g. Intangibles STRONG CH) is discarded.
2. `compute_position_ratings(recruit, profile="recruit")` derives PG/SG/SF/PF/C from final attributes + height.
3. Names, year, lean list, and home region are assigned separately.

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
| Intangibles | IQ, durability, character (CH overwritten post-roll) |
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
