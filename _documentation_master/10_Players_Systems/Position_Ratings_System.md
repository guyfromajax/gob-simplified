# Position Ratings System

Calculates a rating (RT) for each player at all five positions (PG, SG, SF, PF, C) from their attributes and height. RT drives lineup selection, player/recruit evaluation, roster management, and CPU roster logic.

Source of truth: `BackEnd/utils/position_ratings.py`. For the reasoning behind the current model (rejected additive-height design, PF/SF mush, centre-supply collapse, fitting narrative), see the archived design at `_documentation_master/projects/Z-Completed/Player_Attribute_Recalibration_Design.md`.

## Formula

```
RT_pos = attribute_weighted_mean(pos) × height_fitness(pos, height)
```

- **Attribute weighted mean** — `Sum(attribute_value × weight)` over that position's weights. Each position's weights sum to 1.0, so the sum is a mean on the 0–100 attribute scale.
- **Height fitness** — a multiplier in `[0.50, 1.15]` (see below).
- **Result** — rounded and **floored at 1** (`_clamp(total, lower=1, upper=None)`). There is **no explicit upper cap**; RT sits at or below ~100 by construction (attributes are 0–100, fitness ≤ 1.15), though a few elite players legitimately exceed 100.
- Attributes read from `player.attributes` first, then top-level fallback; missing attributes default to `0`.

**Height is a multiplier, not a weighted term.** This lets height *gate* a position — a short player cannot rate as a centre — rather than merely forgoing a few points, which is what an additive height weight allowed. Every position carries a fitness curve; gating only the bigs leaves guards ungated at every height.

## Position Weights (`POSITION_WEIGHTS`)

**One table for everyone — players and recruits use the same weights and the same formula.** There is no separate recruit profile: a player's RT must not change at signing unless development has occurred.

| Attr | PG | SG | SF | PF | C |
|------|-----|-----|-----|-----|-----|
| BH | .30 | — | — | — | — |
| IQ | .25 | .05 | — | .05 | .04 |
| PS | .15 | .05 | — | — | — |
| OD | .10 | .25 | .20 | — | — |
| AG | .10 | .07 | .22 | .16 | — |
| SH | .05 | .42 | .14 | .14 | — |
| SC | — | .11 | .18 | .08 | .18 |
| ID | — | — | .16 | — | .32 |
| RB | — | — | .05 | .30 | .22 |
| ST | — | — | — | .22 | .20 |
| FT | .05 | .05 | .05 | .05 | .04 |

Each column sums to 1.0. A `—` is weight 0 (attribute does not contribute to that position).

## Height Fitness (`HEIGHT_FITNESS`)

Multiplicative, piecewise-linear. Peaks at the position's ideal height (fitness `1.0`) and declines by an **asymmetric** per-inch penalty away from ideal, clamped to `[0.50, 1.15]`. Below the ideal, `fitness = 1.0 − short_penalty × (ideal − h)`; above it, `1.0 − tall_penalty × (h − ideal)`. Height ≤ 0 returns the floor.

| Pos | Ideal (in) | Short penalty /in | Tall penalty /in |
|-----|-----------|-------------------|------------------|
| PG | 70.5 | .020 | .050 |
| SG | 73.0 | .030 | .045 |
| SF | 75.5 | .035 | .035 |
| PF | 77.5 | .050 | .025 |
| C | 79.5 | .060 | .010 |

*(Ideals are −3in from the original pass-1 values (73.5/76/78.5/80.5/82.5) after the two 2026-08 HS shifts, −1 then −2; penalties unchanged. These are the live `HEIGHT_FITNESS` tuple values.)*

The asymmetry is what separates neighbouring positions structurally: a guard's fitness falls off fast when he is tall, a centre's falls off fast when short but barely when tall.

## PF / C separation

PF and C previously shared four of five weighted attributes (RB, ST, ID, SC), so no weight tuning could separate them and both interior positions collapsed/overlapped. Separation is now structural, on two axes:

- **Signature attributes each neighbour ignores.** PF = the mobile, stretch big: carries **AG .16** and **SH .14** and **no ID**. C = the rim-protecting anchor: carries **ID .32** (the largest single weight at any position) and **no AG, no SH**.
- **Asymmetric height fitness.** PF peaks at 77.5 in and penalises being too tall gently; C peaks at 79.5 in and penalises being short steeply. The two curves pull the positions apart instead of fighting over shared attributes.

## When RT is calculated

- **Game init** — all players get fresh ratings from current attributes (franchise games recompute in-sim, so a formula change bites immediately).
- **After training** — training changes attributes; RT recomputed.
- **On demand / migration** — bulk recompute across the DB when attributes change. Most read surfaces (lineup autoset, CPU roster/conversion, scouting, recruiting, UI) read the **stored** `position_ratings`, so stored values must be refreshed for a formula change to be visible outside the sim.

## Storage

Persisted DB field is `position_ratings` (written by `game_manager._update_position_ratings`):

```javascript
{
  "position_ratings": { "PG": 75, "SG": 82, "SF": 68, "PF": 45, "C": 32 }
}
```

`add_position_ratings(player)` writes results under the in-memory key `ratings`; the canonical persisted field is `position_ratings`.

## Usage

- **Lineup selection** — Auto-Set Lineup picks players by best position ratings.
- **Player cards / roster views** — display and sort by position effectiveness.
- **Recruiting** — evaluation and Hub surfaces (see Recruit RT display below).
- **Game logic** — player effectiveness at assigned position.

## Implementation (`BackEnd/utils/position_ratings.py`)

- `compute_position_ratings(player: dict) -> Dict[str, int]` — main entry; RT per position = weighted mean × `height_fitness`, `_clamp(..., lower=1, upper=None)`. No `profile` parameter.
- `height_fitness(position, height) -> float` — multiplicative fitness, clamped to `[HEIGHT_FITNESS_FLOOR, HEIGHT_FITNESS_CAP]`.
- `POSITION_WEIGHTS`, `HEIGHT_FITNESS`, `HEIGHT_FITNESS_FLOOR`, `HEIGHT_FITNESS_CAP` — the tables above.
- `add_position_ratings(player)` — returns a copy with ratings under key `ratings`.
- `_clamp(value, lower=1, upper=100)` — `compute_position_ratings` passes `upper=None`, so RT is only floored at 1.

## RT display (UI)

RT remains numeric internally. Overall/best RT and each PG/SG/SF/PF/C rating
are converted to the unified letter-grade display only at the UI or prose
boundary. Players and recruits of every year use the same bands. See
`Styleguide.md` §RT Letter-Grade Scale for the canonical mapping, colors,
formatter, and rollback switch.

## Tunable Constants

| Constant | Value | Effect |
|----------|-------|--------|
| `POSITION_WEIGHTS` | see table | Per-position attribute weights (each sums to 1.0). |
| `HEIGHT_FITNESS` | see table | Per-position `(ideal, short_penalty/in, tall_penalty/in)`; sets each position's height peak and drop-off. |
| `HEIGHT_FITNESS_FLOOR` | `0.50` | Minimum height multiplier; caps how far a badly-fitting height can drag RT down. |
| `HEIGHT_FITNESS_CAP` | `1.15` | Maximum height multiplier (guard rail; the apex is 1.0, so the cap does not normally bind). |
