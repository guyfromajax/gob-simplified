# Recruiting System

> **Verified against current code: 2026-08-08.** This document describes the active franchise
> recruiting implementation. Historical archetype-based generation, 300/400-player recruit pools,
> and the old walk-on range tables have been removed from this reference.

## 1. System overview

Recruiting has three phases:

| Weeks | Phase |
|---|---|
| 1–19 | Game-performance lean movement |
| 20–26 | Weekly visit assignments and visit-based lean movement |
| 27–34 | Postseason game-performance lean movement |
| 35 | Final recruiting boards and signings |
| 36 | Results/transition state before `finish-season` starts the next season |

The principal implementation is `BackEnd/api/franchise_routes.py`. Generation and shared
recruit/walk-on constants live in `BackEnd/models/franchise_manager.py`; player construction lives
in `BackEnd/utils/player_generation.py`.

## 2. Data model

### Franchise recruits (`franchise_recruits_data` / FRD)

Each franchise owns its own recruit documents. Important fields:

- `franchise_id`, `recruit_id`, `image_id`
- `name`, `height`, `weight`, `year`, `archetype`
- `attributes`, `position_ratings`
- `entry_tier`, `position_intent`, `potential_factor`, `development`
- `Home Region`: region letter `A`–`H`
- `Lean`: `{ "1": ..., "2": ..., "3": ... }`

Lean values are `None`, literal `"open"`, or a team ObjectId serialized as a string. They are not
team display names. Team names are resolved at presentation edges so Team Builder overlays work.

### Franchise team data (FTD)

- `Recruits`: ranked weekly order slots, keys `"1"` through `"20"`.
- `recruit_visit`: the recruit assigned to visit that team during the current week.
- `recruiting_orders_week_35`: final-board entries containing `id`, `points`, `scholarship`, and
  `playing_time`.

### Franchise document

- `recruiting_results`: weekly visit results.
- `recruiting_lean_updates_applied.<week>`: visit-lean idempotency.
- `recruiting_performance_lean_applied.<week>`: performance-lean idempotency.
- `week_35_recruiting_results`: `signed_players` plus `signed_by_recruit_id`.
- `week_35_recruiting_ran`: prevents duplicate final recruiting.
- `used_recruit_set_ids`: prevents reuse of a prebuilt set in the same franchise.

## 3. Recruit generation

### Class size and source

`RECRUIT_CLASS_SIZE = 450`. New franchises and season rollover call
`load_unused_set_or_generate(..., count=450)`:

1. Load an unused document from `recruit_sets` when available (`set_0001` is also 450).
2. Otherwise generate 450 dynamically through `RecruitManager.generate_recruits_list`.
3. Assign image IDs to dynamically generated recruits.

The selected set ID is appended to `used_recruit_set_ids`; a set is not reused inside that
franchise.

### Recruit-year distribution

Each recruit independently draws from `RECRUIT_YEAR_WEIGHTS`:

| Recruit year | Weight |
|---|---:|
| JH | 55% |
| Freshman | 15% |
| Sophomore | 15% |
| Junior | 15% |

These are probabilistic weights, not exact per-class quotas. No recruit is generated as a Senior.

When a signed recruit enters the next active roster, the year advances once:

```text
JH → Freshman → Sophomore → Junior → Senior
```

The signed player then runs `develop_rollover` for that entry rung. JH therefore never appears on
an active roster.

### Player construction

Dynamic generation is position-intent-first:

1. Draw `position_intent` (approximately even across PG/SG/SF/PF/C).
2. Draw `entry_tier`: Poor 7%, BelowAverage 20%, Average 40%, Good 20%, Great 11%, Elite 2%.
3. Generate height, weight, core attributes, CH/EM/MO/NG, ratings, and `potential_factor` using the
   shared player generator for the selected position/tier/year.
4. Roll the frozen career `development` profile from CH.
5. Derive a cosmetic archetype label from intent and tier. Archetype does not generate attributes.

The development identity fields must survive FRD → signing → FPD. Missing values trigger fallback
derivation and can change a player’s career, so `carry_dev_fields` is the declared carry contract.

Canonical attribute mechanics are in
[`Player_Attribute_System.md`](../10_Players_Systems/Player_Attribute_System.md) and
[`Player_Development_System.md`](../10_Players_Systems/Player_Development_System.md).

## 4. Home region and initial leans

Each recruit receives a stable `Home Region` (`A`–`H`). A prebuilt set may supply it; dynamic or
unbaked recruits fall back to a random franchise region.

`FranchiseManager._build_recruit_lean` initializes:

- 75%: `Lean["1"] = "open"`; slots 2–3 empty.
- 25%: slot 1 is a random team from the recruit’s region.
- When slot 1 is a team, slot 2 has a 20% chance of being a different team from that region.
- Slot 3 starts empty.

## 5. Performance-based leans: weeks 1–19 and 27–34

Only teams that played can trigger a roll. A quality loss means losing by no more than eight points
to a better-ranked opponent (`opponent.natl_rank < team.natl_rank`). For each qualifying team, low
RT (`<30`) and high RT (`>=30`) recruits in its region roll separately:

| Weeks | Win: low/high | Quality loss: low/high |
|---|---:|---:|
| 1–10 | 50% / 25% | 40% / 20% |
| 11–15 | 60% / 40% | 40% / 25% |
| 16–19 | 80% / 60% | 50% / 30% |
| 27–34 | 90% / 75% | 60% / 50% |

When a roll succeeds, one eligible in-region recruit is chosen randomly:

- team absent + open slot → highest open lean slot;
- team absent + full list → replace slot 3;
- team at 2 or 3 → move up one place;
- team already at 1 → remove the lowest other occupied lean.

`recruiting_performance_lean_applied.<week>` makes the pass idempotent.

## 6. Weekly visits: weeks 20–26

### Orders and processing

The user saves up to 20 ranked recruit IDs in FTD `Recruits`. Previously saved orders persist into
later visit weeks until changed. Week 20 requires the user to have saved a board before training can
process recruiting.

CPU teams build up to 20 entries:

- choose 0–5 out-of-region recruits from another region’s top 15;
- choose up to 10 randomly from the home region’s top 16;
- fill remaining slots randomly from the rest of the home-region pool;
- sort selected recruits by RT before storing the order.

Recruit visits are resolved when weekly training processing runs. Each team receives at most one
visit and each recruit visits at most one team. The conflict resolver considers board priority,
existing leans, and a prestige-weighted team draw. Results are stored on the franchise and exposed
through `/franchise/recruiting-results`.

### Visit-based lean movement

If the visiting team is already on the recruit’s lean, it moves up one place (or stays first and
drops the lowest other lean). Otherwise:

| Team/recruit relationship | Win + open | Win + full | Loss + open | Loss + full |
|---|---:|---:|---:|---:|
| In region | 95% | 75% | 75% | 40% |
| Out of region | 80% | 60% | 50% | 30% |

An accepted team fills the highest open slot or replaces slot 3. The pass is guarded by
`recruiting_lean_updates_applied.<week>`.

## 7. Week 35 final recruiting

### User board

- Maximum 20 entries.
- Total points budget: 50.
- Each entry stores `id`, integer `points`, `scholarship`, and `playing_time`.
- `scholarship` is currently normalized false/dormant.
- Running recruiting without a saved user board is rejected.
- Saving the first user board lazily creates CPU boards that are still empty.

### CPU boards

CPU boards begin with all recruits already leaning toward that team, then fill remaining slots from
in-region recruits split around RT 25. They assign the 50 points across a low-RT flyer, a high-RT
target, and lean-list priorities; if there are no lean-list entries, points split across up to five
top in-region board recruits.

### Recruit scoring and signing

Recruits are processed in descending RT. Teams at the 15-player returning-roster cap are excluded.
Only teams that put the recruit on their week-35 board participate.

```text
subtotal = 1 board point + assigned points + playing-time bonus
score = subtotal × lean multiplier
```

- Playing-time bonus: 15 when only one or two teams offer it; 7 when more than two offer it.
- Lean multipliers: #1 = 5×, #2 = 3×, #3 = 2×, not on lean = 1×.
- At most four finalists remain; ties at the cutoff are randomly sampled.
- Winner is drawn proportionally from finalist scores.
- Scholarship offers do not currently affect score or roster scholarship state.

Signed results retain the player-generation fields, assign a non-conflicting position-based jersey
(`BackEnd/utils/jersey_assignment.py` — pool by **`position_intent`**, excluding numbers already
worn on the team's active roster; falls back to best RT position if intent is missing), and are
persisted under `week_35_recruiting_results`.

## 8. Walk-on generation and roster fill

`generate_walk_on_profile()` is shared by season-one initialization, week-35 roster fill, and Team
Builder wizard generation. It uses the same player generator with a **tier drawn per walk-on** from
`WALK_ON_TIER_WEIGHTS` (Poor 65 / BelowAverage 25 / Average 8 / Good 2 — no longer 100% Poor), draws
position intent and `potential_factor`, rolls a development profile (peaks restricted to the rungs
still ahead of the drawn roster year), uses flat CH 1–100, and stamps archetype `Walk On`. Season-1 / TB walk-ons start with `meta.jersey = None` and usually no
`meta.image_id` (TB authored portraits are left alone).

Walk-on years are separate from recruit years:

| Walk-on roster year | Weight |
|---|---:|
| Freshman | 10% |
| Sophomore | 40% |
| Junior | 40% |
| Senior | 10% |

The generator contract says these are direct roster years: no JH and no advancement. Season-one
initialization follows that contract and adds three walk-ons per team onto the pre-cut 15-man
`FTD.players` list (12 scholarship + 3 walk-ons).

### Making the active 12 (jersey + portrait)

After the **last camp week** (`CAMP_WEEKS`, currently 3) training completes, user and CPU camp cuts
reduce each roster to 12. Walk-ons who **survive onto that 12** (not sent to `training_squad_players`)
receive:

1. **Jersey** — same helper as week-35 signing (`position_intent`, conflict-aware), skipped if
   `meta.jersey` is already set.
2. **Portrait** — random kit from the 71-id walk-on pool (`portrait-kits/walk_on_portraits/`,
   manifest `BackEnd/data/walk_on_portraits_manifest.json`), skipped if `meta.image_id` is already
   set (e.g. Team Builder). League-wide within the franchise season: used ids live on
   `franchises.walk_on_image_ids_used`; when the pool is exhausted, ids may repeat. Cleared at
   `finish_season`.
3. **Paint** — user team eager-warmed into `players/master/<player_id>.png` in team colors; CPU
   lazy via `POST /player-image/ensure`.

Hook: `assign_walk_ons_making_active_roster` from `cut_franchise_players` (user) and
`_apply_cpu_training_camp_cuts` (CPU).

### Current week-35 discrepancy

After recruit signings, week 35 generates walk-ons until every team reaches 15 returning/signed
players. Those walk-ons then enter the shared `finish_season` signed-player loop, which currently
calls `advance_year(...)` for **all** signed entries before `develop_rollover`. Consequently:

- season-one walk-ons use the direct 10/40/40/10 year as generated;
- week-35 walk-ons are generated with 10/40/40/10 but are then advanced by the current shared
  rollover code (FR→SO, SO→JR, JR→SR; SR falls through to the defensive Freshman default).

That behavior conflicts with the comments and generator contract stating “no advance step.” This
document records the discrepancy; it does not choose or implement a correction.

## 9. Season rollover

`finish_season`:

1. Removes graduating seniors from active and Practice Squad populations.
2. Advances and develops returning players.
3. Converts week-35 signed entries into FPD documents, advances their year, and develops the entry
   rung.
4. Rebuilds every FTD roster, scholarship list, promise list, and team attributes.
5. Clears old FRD and creates the next 450-recruit class.
6. Resets recruiting orders/results/idempotency maps and returns the franchise to week 1.

## 10. API and frontend surfaces

### Backend routes

| Method | Route | Role |
|---|---|---|
| GET | `/franchise/recruits` | Recruit list |
| GET | `/recruit/{recruit_id}` | Single recruit |
| GET | `/franchise/recruiting-data` | Hub/board payload, user-team region, potential ratings, leans, results state |
| GET | `/franchise/recruiting-results` | Weekly visit result payload |
| POST | `/franchise/recruiting-orders` | Save weekly or week-35 boards |
| POST | `/franchise/run-week-35-recruiting` | Resolve final signings and advance 35→36 |

### Frontend

The current shared recruiting presentation uses:

- `FrontEnd/static/recruiting-hub.js`
- `FrontEnd/static/recruiting-common.js`
- `FrontEnd/static/recruiting-orders.js` / `recruiting-invites.js`
- `FrontEnd/static/recruiting-results.js`
- recruiting panels in `FrontEnd/static/franchise-command-center.js`

RT remains numeric in data and is rendered through the shared letter-grade helper. Recruiting
surfaces that expose ceiling context render current/potential from backend `potential_rt_ratcheted`.
In the Hub pool toolbar, `All` is ordered first, followed by the user team's region (from
`team_region` in the recruiting-data payload) and then the other region filters. The user region is
persistently identified in green with the `my region` label. The active-filter treatment remains
visually distinct.
Immediately to its right, the year filter offers `All`, `JR`, `SO`, `FR`, and `JH`; year, region,
name, and leaning filters compose rather than replacing one another.

## 11. Key files and tests

### Code

- `BackEnd/models/franchise_manager.py` — class size, year weights, recruit/walk-on generation,
  initial leans, season-one initialization.
- `BackEnd/models/recruit_sets.py` — unused-set selection and dynamic fallback.
- `BackEnd/utils/player_generation.py` — shared player construction.
- `BackEnd/api/franchise_routes.py` — weekly orders, visits, leans, week 35, rollover.
- `BackEnd/utils/rt_projection.py` — Potential Rating projection.

### Related system docs

- [`Player_Attribute_System.md`](../10_Players_Systems/Player_Attribute_System.md)
- [`Player_Development_System.md`](../10_Players_Systems/Player_Development_System.md)
- [`Practice_Squad_System.md`](Practice_Squad_System.md)
- [`Tunable_Constants.md`](../11_Design_Systems/Tunable_Constants.md)

When changing recruit supply or year distributions, update the recruit class size, recruit-year
weights, and walk-on-year weights as one steady-state intake system; changing one alone shifts the
league’s long-term class and roster composition.
