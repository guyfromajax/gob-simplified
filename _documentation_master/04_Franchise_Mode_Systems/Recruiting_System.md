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

### When invites are assigned

Assignment runs when the player **runs training** for that week, not when the board is saved.
`POST /franchise/run-training` → `_process_weekly_recruiting_invites()` resolves every team's visit
in one pass, writes `recruiting_results.<week>`, and stamps each team's FTD `recruit_visit`. Saving
the board only persists FTD `Recruits`. Re-running training in the same week cannot reassign — the
processor returns early when `recruiting_results.<week>` already exists. Week 20 rejects training
outright until a board is saved; weeks 21–26 simply produce no visit from an empty board.

### Invite board (Hub, weeks 20–26)

**Twenty ranks, always drawn.** Two columns of ten (1–10 / 11–20). An unfilled rank renders as an
`Open` slot, not an absence — the panel is a static size, and the number of invites left is legible
without a counter doing the arithmetic.

| Region | Contents |
|---|---|
| Panel header | `Invite Board` · `n/20` · **Submit Invites** (right-justified). No footer bar. |
| Row | Headshot · name + archetype (stacked) · Pos · RT (cur/pot) · Yr · Ht · Wt · Lean ladder · visit chip · remove |
| Visit chip | `Wk 20`…`Wk 26` on a recruit who has already visited you, stamped in the row's own control zone so it never shifts the data columns |
| Season panel | Expands to a visit log, ascending by week — one row per week 20–26, future weeks shown open |

**Removed by instruction, code kept:** the *This Week* movement column. `thisWeekCellHtml` and
`topUnvisitedId` remain in `recruiting-hub.js`, dormant and uncalled, against a possible return.
Row movement classes (`.dropped` / `.gained`) still come off the same wire events and are still styled.

**Removed outright:** the *Invite Target* hero (board rank 1 already **is** the invite target — the
hero restated it), the *Clear* button (a one-press wipe of a ranked board with no confirm and no
undo), and the right rail (*This Week* / *Roster Capacity*).

**Known limitation.** `.doc { max-width: 1360px }` caps the Hub page, so the pool's Lean and Watch
columns stay scroll-only; adding `Wt` cost ~44px more. Not a board bug — noted where it bites.

### Recruit Visit modal

On returning to the FCC from the training report in weeks 20–26, a Moment modal on the shared Sammy
chrome announces the recruit visiting the user's team: *"Hey Coach, here is this week's invite!"*

- **Table** mirrors the Walk-On Welcome row — Name · Pos · Yr · Ht · Wt · **Rgn** · the core 12 on
  the 0–10 scale · RT — with **Region** the one column a recruit adds, because it decides whether he
  is a realistic target. RT shows **current/potential** as letter grades.
- **Sammy image** comes from `getTeamSammyImage()`: the team-coloured portrait for the eight teams
  in `TEAM_COACH_ABBR` (conference 1), the generic white Sammy otherwise. No conference check of its
  own — the mapping already encodes it.
- **No visit, no modal.** An empty board, or the user's pick losing the prestige-weighted draw,
  ends the week silently rather than announcing nothing.
- **Once per week**, via `recruit_visit_modal_seen_week` and
  `PATCH /franchise/recruit-visit-modal-seen`. Week-stamped, so each of weeks 20–26 gets its own
  reveal and the next week arms it with nothing needing to clear the flag. Reset at season rollover.

The Walk-On Welcome modal now shows **current/potential** RT too; walk-ons carry `entry_tier` and
`potential_factor` through signing, so the ceiling is computed at the payload boundary rather than
stored.

## 7. Week 35 final recruiting

### User board

- Maximum 20 entries.
- Total points budget: 50 — and that budget is the ONLY limit; there is no per-recruit cap.
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

### Signing Day reveal (on submit)

Submitting orders runs the signings and then plays them back **before** the summary. Scope is the
**user's conference only** (8 teams), highest RT first, one every **3000ms**. Presentation only —
the engine already resolves in RT order, so this shows a sequence that already happened.

- **Walk-ons are excluded.** They are roster backfill, not signings; their first reveal is the next
  season's Walk-On Welcome modal.
- **Skip control** jumps to the user's next signing. Once none remain the CTA becomes *Skip To End*
  with `0 signings remain for your team` beneath it — the same state a coach who signed nobody sees.
- **Progress** carries the count (`12/45`) and a meter whose stops are the real RT grade bands read
  from `rtBucket.js` at runtime, so the run reads A++ → F without a second copy of the thresholds.
- **No replay.** Reaching the end PATCHes `/franchise/week-35-reveal-seen`, which season-stamps
  `week_35_reveal_seen_season`. A refresh after submitting does not replay it, and a new season gets
  its own reveal without anything having to clear the flag.

### Week 36 results — league list

The week-36 screen is a **list**, not a playback (the drama moved to Signing Day). Every signing in
the league, grouped by conference then team, ordered: the user's conference → its **sister
conference** (`_sister_conference`: same region, other conference) → conferences 1–16 ascending with
those two removed so neither repeats. Conferences display as `E1` / `E2`. Walk-ons excluded here too.

The FCC's Recruiting Results modal is unchanged and still fires on first FCC entry after week 35.
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

After the **last camp week** (`CAMP_WEEKS`, currently 1) training completes, user and CPU camp cuts
reduce each roster to 12. Walk-ons who **survive onto that 12** (not sent to `training_squad_players`)
receive:

1. **Jersey** — same helper as week-35 signing (`position_intent`, conflict-aware), skipped if
   `meta.jersey` is already set.
2. **Portrait** — random kit from the season pool, skipped if `meta.image_id` (or top-level
   `image_id`) is already set (e.g. Team Builder):
   - **Season 1:** the 71-id walk-on pool only (`portrait-kits/walk_on_portraits/`,
     manifest `BackEnd/data/walk_on_portraits_manifest.json`).
   - **Season 2+:** walk-on pool ∪ recruit `set_0001` kit ids (`recruit_sets._base_image_pool`),
     drawn at random with no split.
   League-wide within the franchise season: used ids (from either pool) live on one list,
   `franchises.walk_on_image_ids_used`; when the applicable pool is exhausted, ids may repeat.
   Cleared at `finish_season`. Imageless on Training Squad is intentional until they make an
   active 12.
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

## 10b. Watchlist

An **unordered, uncapped shortlist** of recruit ids the player is tracking. `recruiting_watchlist` on the franchise doc; toggled by `PATCH /franchise/recruiting-watchlist`; surfaced in the pool as a star per row and as a Views filter.

**It is not a board.** Ranks and the 20-slot cap belong to the week-20 invite board (FTD `Recruits`). Conflating them would make every star press imply a position.

| Aspect | Behavior |
|---|---|
| Shape | Flat list of recruit ids, de-duplicated, insertion order preserved |
| Cap | None. `MAX_BOARD` (20) caps the *board*, not the shortlist |
| Seeds the board | At week 20, **client-side only**, and only when no board is saved |
| Writes | `recruiting_watchlist` and nothing else |

### The seeding rule

> Watchlist seeding must never write FTD `Recruits`.

`has_saved_board` derives from `_team_order_list(ftd["Recruits"])`, and the server guard that 400s week-20 training keys off it. (The FCC's *button* moved to `board_saved_week` — see the invite step in `FCC.md` — but the server guard did not.) Persisting a seed on page load would make `_team_order_list` non-empty before the player saved anything, silently reopening the gate. `Recruits` is written by `save_recruiting_orders` and nowhere else.

This is the same failure mode as `seedAlloc()` — pre-committing the player to a choice they never made — so it is asserted in `tests/test_recruiting_watchlist.py` rather than left to review. The seed also runs only when the board is empty, so it can never reorder or overwrite a board the player built, and it orders by RT descending because the shortlist itself carries no ranks.

## 10c. Recruit pool (450 rows)

Columns: **Recruit · Pos · RT · Yr · Ht · Wt · Rgn · Attributes · Lean · Watch**. Name/Pos/RT lead because they answer "is he worth watching" fastest and keep the sorted column beside the name; Lean and Watch pair at the right edge because both are about *you and him*, not about him.

- **`.pool.condensed` is deleted.** It hid the attribute columns whenever the dock was open — i.e. exactly during the invite phase, when you are comparing recruits. Attributes are visible in every phase.
- Name column is **capped at 248px, not flexed**; the table is `width: max-content` (~1030px), so no dead space opens between the name and Pos.
- Headers centered over their columns, with **Attributes centered across the whole 12-chip block**. (The mockup right-aligns that header; the build prompt corrected it.)
- Sticky header, sortable columns, **RT descending by default**.
- Attribute values use the product-wide 0–10 scale via `RecruitingCommon.formatAttrValue`, not the mockup's raw 0–100 placeholders.
- Headshots: `API_CONFIG.getRecruitImageUrl(image_id, {size:'card'})` with `loading="lazy"`, then `ensureRecruitImage` → retry → drop to the generic frame on a second failure.
- Region grouping is replaced by a flat sortable list plus a **Rgn column**; region is now a dropdown filter.
- Filters in two labelled rows. **Filter**: region dropdown (9 options, rarely changed) + position and year as segmented controls (few options, switched constantly — a dropdown costs a click every time) + name search. **Views**: Watchlist · Leans to me · Unranked by me, mutually exclusive; clicking the active one clears it.

## 10d. Signing Day (week 35)

The player makes every commitment, and the screen shows only facts.

**No load-time allocation.** `seedAlloc()` is **deleted**. It allocated 12/9/6 points — 27 of 50 — and attached **binding** playing-time promises to two recruits, unmarked, on page load. The page loads at **0 of 50 with zero promises**; only a previously *saved* allocation is restored. Any future helper must be a button the player presses, never a load-time side effect.

**No percentage anywhere.** The old odds bar computed `base(standing) + points × 2.2 + (promise ? 18 : 0)` — an admitted placeholder, blind to rivals — and displayed it as a percent. A number like "62%" is a promise the sim cannot keep. Two honest columns replace it:

| Column | Shows | Source |
|---|---|---|
| **Standing** | Lean position and its multiplier — `#1 ×5`, `#2 ×3`, `— ×1` | `leanModel` (mirrors the backend `score = (1 + points + PT_bonus) × lean_mult`) |
| **Field** | How many programs are funding him: a count plus a segment bar with the user's segment highlighted | `payload.competition_counts` |

If you find yourself deriving a probability to rank or sort on this screen, that is the placeholder growing back. A regression test walks every text node and fails on a literal `%`.

**Competition counts** — `_week_35_competition_counts(fid)` returns `recruit_id → number of programs funding him`, counting only entries with `points > 0` (a zero-point slot is not competition) and once per team. Knowable because CPU week-35 boards are seeded server-side on the user's first save. Returns `{}` before boards exist, which renders as "no field yet" rather than as zero competition.

**Roster capacity is a server number.** `_roster_capacity_payload(fid, team_id)` ships as `payload.roster_capacity` (`roster_spots`, `scholarships`, `roster_cap: 15`, `roster_used`). It wraps the pre-existing `_calculate_available_roster_spots` / `_calculate_available_scholarships` rather than recomputing. **Signing day** reads it. The invite board's rail was removed, so it is no longer a second consumer. Nothing derives capacity client-side; funding was previously uncapped against a hard 15-man ceiling.

**Removed:** the scholarship toggle. It was normalized false/dormant and affected neither score nor roster state — a visible control that did nothing. `order_entries` no longer carries a `scholarship` key.

**Added back:** year and archetype on the signing row. A senior and a freshman previously looked identical on the screen where 50 points get committed.

**Submit summary** replaces the blind 950ms redirect. After the save lands, the player sees what they committed — points, standing, multiplier, field per recruit — and leaves on their own click.

### Submitting and running are two presses on two screens

Submitting **saves**. Running is a separate, deliberate press back on the FCC, so the
irreversible step never rides on the same click as the save.

| Step | Where | Button |
|---|---|---|
| 1. Commit points | Hub · Signing Day | `Submit Orders` → `POST /franchise/recruiting-orders` |
| 2. Leave | Submit-summary modal | `Go To Locker Room` (amber) → FCC. `Back to Orders` still reopens the board. |
| 3. Run | FCC hero | `Run Recruiting Day` (green) → Hub `?action=run` |
| 3b. Change your mind | FCC hero, below the green | `Edit Recruiting Orders` (ghost) → Hub |

- **The hub owns the run.** `POST /franchise/run-week-35-recruiting` and the reveal that
  follows it both live in `recruiting-hub.js`, so the FCC hands the press over as
  `?action=run` rather than duplicating them. `maybeAutoRun()` is guarded three ways — a
  URL is user-editable: Signing Day phase only, orders must exist, and never after the
  signings have run.
- **The pair is state-driven.** `recruiting_wire.week_35_orders_submitted` derives from
  FTD `recruiting_orders_week_35` — the *same* field `run_week_35_recruiting` requires —
  so the green button can never offer a run the endpoint would 400. Cleared at rollover
  with the rest of FTD, so last season's orders cannot arm next season's button.
- **Before orders exist** the green button is still `Recruiting` → mode
  `week35-recruiting`, and there is no ghost button. That mode is what raises the
  optional **Cut Players?** offer, so the cut stays on the way *in*, before points are
  committed against a roster size — it does not repeat on the run press.
- **Colour law.** Green is the gating action, so only `Run Recruiting Day` is green. The
  modal's CTA turned amber the moment it stopped committing anything, and
  `Edit Recruiting Orders` is a ghost fill at the same box size as `#play-now`.

**Pre-flight rail** is the one place on this screen allowed to editorialize, and every warning must name the recruit *and* the number driving it:

> `6 programs funding DeAndre Pope, you're #2 at ×3 — 5 points is unlikely to carry.`
> `19 points unspent and 4 roster spots; Ruiz is uncontested at ×1.`
> `Binding promise on Vance at ×1 — he has no lean toward you, so the promise carries the whole bid.`

A clean board says "Nothing flagged" rather than showing an empty panel.

## 10e. Results (week 36)

**Playback, not a new engine.** The resolution already processes recruits one at a time in RT order. The results screen replays that sequence with Next / Auto-play / Skip all. Nothing here changes who signs where.

**Every row explains itself:** headshot, linked name, position, RT pair, where he signed, your points, your standing and multiplier, field size, and a one-line why.

### The why must come from the resolution

`_generate_week_35_recruiting_results` writes a `resolution` block onto each signed entry, recording the numbers the signing was actually decided by:

| Field | Meaning |
|---|---|
| `field_size` | Programs funding him (`points > 0`), matching `_week_35_competition_counts` |
| `points_by_team` | Points each funder committed |
| `scores_by_team` | Every board's score as the engine computed it |
| `winner_team_id` / `winner_score` / `winner_points` | Who won and on what |
| `lean_multipliers` | Each boarded team's multiplier |
| `lean_at_resolution` | The ladder at decision time |
| `pt_offer_count` | Playing-time offers, which scale the PT bonus |

`week_35_signing_reason()` assembles the sentence from **those recorded numbers only**. It never calls `_week_35_team_score` — a second implementation of the scoring rule is how the client drifted the first time, and `test_week_35_signing_reason.py` guards it structurally by parsing the function body. A pre-existing signing with no `resolution` block renders `—` rather than an invented reason.

**Multiplier drift, fixed.** The engine scores slot 3 at **×2**. An earlier client table listed only `{1: 5, 2: 3}` and defaulted rank 3 to ×1, so signing day would have displayed the wrong multiplier. There is now one definition — `WEEK_35_LEAN_MULTIPLIERS` — used by `_week_35_team_score` and served to the client as `payload.lean_multipliers`.

**Class summary** after the sequence: signed, funded, class average RT, points spent, and roster spots remaining — the last read from the same `_roster_capacity_payload` helper signing day uses.

**Scope.** The sequence covers recruits you boarded plus everyone you signed. A recruit you never boarded is not part of your season and is excluded, so the "You never boarded him" reason exists server-side for completeness but does not appear on this screen.

### Carry-back fix: reachable warnings

The signing pool defaults to `sTab: 'mine'`, which hides recruits with no lean to you — exactly the ×1 and "no field yet" cases the pre-flight rail warns about. Each recruit-specific warning is now a button routed through the existing `jumpTo()`, which switches to the All tab and flashes the row. Aggregate warnings (over budget, more funded than spots) name no recruit and stay non-clickable. **The `mine` default is unchanged** — the defect was the unreachable warning, not the tab.

## 11. Key files and tests

### Code

- `BackEnd/models/franchise_manager.py` — class size, year weights, recruit/walk-on generation,
  initial leans, season-one initialization.
- `BackEnd/models/recruit_sets.py` — unused-set selection and dynamic fallback.
- `BackEnd/utils/player_generation.py` — shared player construction.
- `BackEnd/api/franchise_routes.py` — weekly orders, visits, leans, week 35, rollover.
- `BackEnd/utils/rt_projection.py` — Potential Rating projection.

### Tests

- `tests/e2e/invite-board.spec.js` — board writes, 20-slot cap, drag reorder, header CTA.
- `tests/e2e/invite-board-layout.spec.js` — 20 always-drawn slots, two columns, visit chip, open
  future weeks, pool `Wt`.
- `tests/e2e/week35-signing-pair.spec.js` — the FCC's Signing Day pair: green CTA split,
  ghost button visibility/size/colour, branch order vs `cut_required`.
- `tests/e2e/signing-reveal.spec.js` — `run handoff` block: the modal runs nothing, and
  `?action=run`'s three guards.
- `tests/e2e/recruits-pool.spec.js` — column order, sorting, filters.
- `tests/test_recruiting_watchlist.py` — the seeding rule (never writes FTD `Recruits`).

### Related system docs

- [`Player_Attribute_System.md`](../10_Players_Systems/Player_Attribute_System.md)
- [`Player_Development_System.md`](../10_Players_Systems/Player_Development_System.md)
- [`Practice_Squad_System.md`](Practice_Squad_System.md)
- [`Tunable_Constants.md`](../11_Design_Systems/Tunable_Constants.md)

When changing recruit supply or year distributions, update the recruit class size, recruit-year
weights, and walk-on-year weights as one steady-state intake system; changing one alone shifts the
league’s long-term class and roster composition.
