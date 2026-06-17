# Dynamic HCT (Half Court Trap) Turns

Target design for resolving an HCT possession as a **dynamic, looped turn** rather
than a fixed skeleton. This document is the north star (full target design); the
**Implementation Cuts + Question Tracker** (§10) records what is actually built so
far and what remains.

---

## §0 — Scope & Architecture Contract

**One HCT turn = one full possession.** The engine
(`compute_dynamic_hct_turn` in `BackEnd/engine/dynamic_hct.py`) runs the
read → decide → move loop (§4) internally to completion and returns a
**variable-length** list of intermediate step data. The emitter
(`BackEnd/engine/dynamic_hct_step_emitter.py`) turns that into schema animation
steps. The current fixed `[walk-up, converge, attack]` output is the degenerate
(shortest) case of this loop.

**Engine vs emitter responsibilities**
- **Engine**: owns the loop, all reads, moment detection, decision resolution,
  outcome selection, and the per-step target coords + durations. Returns
  intermediate data only (target coords, per-step seconds, result type, roles).
- **Emitter**: consumes the engine's intermediate data + `prior_turn.final_coords`
  / `prior_turn.final_ball_handler_id` and assembles the schema `AnimationStep`
  list, stamping tween durations and clock state.

**Loop iteration = one animation segment** (one step), gated by its own advance
trigger. Moment detection (§5) runs at **segment boundaries** (continuous,
distance-based), not on a fixed time tick.

**Orientation.** All coords in this doc are in **home-on-offense** orientation.
Flip via `get_away_player_coords` when the away team is on offense (same
convention as the zone constants in `BackEnd/utils/shared_defense.py`).

**Feature flag.** `USE_DYNAMIC_HCT` (in `phase_resolution.py`) selects the dynamic
path over the legacy skeleton-driven HCT. Flip to `False` to revert.

---

## §1 — Vocabulary, Constants & Thresholds

**Defensive Positions Legend**
- PG: Backcourt center defender
- pos1 & pos2: other backcourt defenders
- pos3 & pos4: front court defenders

**Offensive Positions Legend**
- PG: ball handler
- pos1 & pos2: back court offenders
- pos3 & pos4: front court offenders

**Position assignment note.** We use the same ball-handler + pos1..pos4
assignment scheme as the target-shooter + pos1..pos4 logic (mirrors
`_alias_map` / `_build_set_play_alias_map`). See §3.

**Distance thresholds**
- **Trap / pressure detection radius: 11** euclidean grid spots (used everywhere —
  detection *and* converge trigger; the old line-109 "12" was a typo).

**Pace constants** (defined in `BackEnd/constants/__init__.py`, referenced — not
re-derived here):
- `STANDARD_GRID_PER_GAME_SEC` — standard animation pace.
- `CHALLENGED_OPEN_FLOOR_GRID_PER_GAME_SECOND` (16) — HCT entry advance.
- `ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND` (12) — drive-pace dribble.
- AG-driven rates via `ag_to_grid_per_game_sec` / `calc_ag_segment_seconds`
  (AG=50 reproduces the legacy constants exactly).

**Shot-clock / violation constant**
- `HCT_SHOT_CLOCK_VIOLATION_THRESHOLD = 20` (10 seconds elapsed from a 30 start) — see §8.

**Defense starting locations** (home-defending orientation; flipped for away offense)

| Pos | Role | Spot | Coord |
|-----|------|------|-------|
| PG | center defender | exact center court | (50, 25) |
| SG (pos1) | upper-wing zone centroid | — | (62, 40) |
| SF (pos2) | lower-wing zone centroid | — | (62, 10) |
| PF (pos3) | frontcourt high-post zone centroid | — | (76, 22) |
| C (pos4) | paint/rim zone centroid | — | (83, 29) |

These are produced by `hct_initial_defender_coords` and the
`HCT_STANDARD_NORMAL` centroids (see §6).

---

## §2 — Goals & Terminal Conditions

**Goals**
- **Defense's goal**: get the ball and two ball-handler defenders into position to execute a trap.
- **Offense's goal**: get the ball past x=64 and either attempt a shot within the
  HCT turn (first goal) or transition to HCO turn (secondary goal).

**Offense goal spots**
- **Primary Safe Area (PSA)**: x: 57–64 and y: 19–32 (perfect spot: x=60, y=25).
- **Attack Basket Area**: x: 64 to basket-x and y: 10–30. The shared boundary x=64
  resolves to the **PSA** (PSA wins the overlap; Attack Basket is effectively x>64).

**HCO entry triggers (the only two).** An HCT turn transitions to HCO **only** when
one of these is true; nothing else triggers HCO:
1. The BH **reaches the Primary Safe Area** → HCO (100%).
2. The BH or PR **reaches the Attack Basket Area** AND `defenders > offenders`
   (counted within the Attack Basket Area) → HCO. If `defenders ≤ offenders`
   (ties → attack) the receiver attacks the basket instead (§7).

**Zone precedence (checked at the top of each loop iteration):**
1. In PSA → HCO (trigger 1).
2. In Attack Basket Area → §7 goal achievement (HCO if `defenders > offenders`, else shot/attack).
3. At x > 64 but **outside** both zones (e.g. y outside the Attack Basket band) →
   **not a goal**; continue the §4 loop (BH read → decision). *(This supersedes the
   old "Situational" goal spot — a numbers advantage now only matters within the
   Attack Basket Area, not as a standalone x>64 zone.)*

**Defense goal spots**
- **Primary**: x: 50–57 and (y < 10 or y > 40). Defense executes a trap here if two
  defenders are within trap distance (11) of the ball handler.
- **Secondary**: x ≥ midCorner-spot-x and (y < 10 or y > 40). Same trap condition.

**Terminal conditions (turn enders)**

| Ender | `next_turn` | Possession flips? | Status |
|-------|-------------|-------------------|--------|
| DEAD BALL (turnover) | SIDE_INBOUND → SIP | Yes | Built |
| HCO transition | HCO | No | Built |
| Shot attempt | (shot resolution) | depends on make/miss | §7 — target |
| 10-second violation | SIP | Yes | §8 — constant defined, not wired |
| Offensive foul | — | — | §8 — TODO |
| Steal | — | Yes | §8 — TODO |

---

## §3 — Roles & Position Assignment

- **Ball handler (BH)**: PG for first cut (the BIP receiver). Future:
  personnel/scouting-driven.
- **pos1..pos4** map to the remaining lineup positions via `_alias_map` (order
  PG, SG, SF, PF, C, excluding the BH position).
- **Defender roles**:
  - **BH defender** — primary on-ball defender (PG defender first cut).
  - **Trapper** — second defender that converges to form the trap.
  - **Center defender** — third backcourt defender.
  - **Front defenders** — pos3 / pos4.

**Backcourt defender targets** (used during convergence/relocation):
- **Primary BH / pass-receiver defender**: receiver's x ±2 (toward offense basket-x)
  and receiver's y.
- **Secondary defender (trapper)**: same x as receiver, ±2 y from receiver's y —
  if trapper's starting y > receiver's y he targets +2, else −2.
- **Center defender** (usually third backcourt player): y=25 and x ±4 of the
  receiver's x, whichever is closer to the offense basket-x.

---

## §4 — The HCT Loop (state machine)

All reads resolve to one of three decisions: **attack**, **pass**, or **hold**
(hold = keep the ball without dribbling). Optimal preference order: attack → pass → hold.

### Loop skeleton

```
setup()                              # entry walk-up (see "Setup" below)
shot_clock = game_state.shot_clock   # seeded once at turn start; decremented per segment
while not terminal:
    if time_terminal(shot_clock, bh): break   # shot-clock / 10-sec violation (see "Time terminals")
    if bh in Primary_Safe_Area: → HCO; break        # §2 trigger 1 (zone precedence)
    if bh in Attack_Basket_Area: → §7 Goal Achievement; break   # §2 trigger 2
    # x>64 outside both zones → fall through and keep looping (not a goal)
    moment = detect_by_distance()    # none | pressure(1 def ≤11) | trap(2 def ≤11, ≥1 ahead of BH)
    decision = read(BH)              # attack | pass | hold
    resolve(decision, moment):
        attack → Pressure (1 def) or Trap (2 def) resolution → DEAD BALL | HCO | neutral
        hold   → defense converges → Trap resolution
        pass   → Vertical-Half or Central pass movement (no moment)
    emit_segment()                   # append step(s); gate on the defining mover
    shot_clock -= segment_duration   # every segment consumes clock → guarantees a bound
    if terminal: break               # DEAD BALL→SIP, HCO, shot (later: foul/steal/violation)
    else: advance()                  # BH +rand(6,12) x toward basket, +rand(-6,6) y; defenders re-pose
```

### Setup (entry walk-up)

- BH receives the BIP pass and holds stationary for **1 game second** while the
  other 9 players move up the court; then the BH also advances at standard pace.
- BH target: **(44, random y in 21–29)**.
- Defenders target their HCT normal alignment (§1 table). Defensive PG targets
  exact center court (50, 25).
- The four non-BH offenders target spots within these ranges:
  - **pos1**: x between upper wing and deep upper wing; y between upper deep baseline and upper deep wing.
  - **pos2**: x between lower wing and deep lower wing; y between lower deep baseline and lower deep wing.
  - **pos3**: x between lower apex and lower wing; y between lower midPost and lower midCorner.
  - **pos4**: x between upper apex and upper wing; y between upper midPost and upper midCorner.
- Setup ends the moment the BH arrives at his target; the 9 movers freeze wherever they are.

### The Read

Use the standard player read helper:

```python
attrs = getattr(player, "attributes", {}) or {}
return int(((attrs.get("IQ", 0) * 0.8) + (attrs.get("CH", 0) * 0.2)) * random.randint(1, 6))
```

- read > 200 → **attack**
- read > 120 → **pass**
- else → **hold**

*Future note: consider adding a defender component to disrupt the BH's read.*

### Advance (non-terminal iterations)

When no terminal fires, the BH advances **random(6,12)** x toward the basket and
**random(−6,6)** y, defenders re-pose (§6), and the loop re-detects + re-reads.
If the advance lands the BH in the Primary Safe Area → **HCO (100%)** (HCO entry
trigger 1, §2). If the advance lands him in the Attack Basket Area → §7 goal
achievement. Otherwise → run another read → attack/pass/hold iteration.

### Time terminals (checked every iteration)

Because **one HCT turn = an entire possession** with an internal loop, the time
checks must run **inside** the loop, at each segment boundary — not just at the turn
boundary. (`run_micro_turn`'s `clock_enforced_states` check only fires *before* the
turn starts, so it can't catch the clock expiring mid-loop.)

**Mechanics**
- Seed a running `shot_clock` from `game_state.shot_clock_remaining` once at turn start.
- After each emitted segment, decrement `shot_clock` by that segment's duration
  (segments are ~1–3s, so checks are at segment granularity — close enough; these
  cases are rare).
- At the **top of each iteration**, evaluate the terminals before doing anything else.

**Precedence**
1. `shot_clock ≤ 0` → **shot-clock violation** (always; see §8) → turnover → SIP, possession flips.
2. else if `shot_clock ≤ 20` **and** the ball has **not** crossed half court
   (BH x < 50 home / > 50 away) → **10-second violation** (§8) → turnover → SIP,
   possession flips.
3. Once the ball has crossed half court, the 10-second rule no longer applies — only
   the `shot_clock ≤ 0` terminal remains.

**Why this bounds the loop:** every segment (hold 1–3s, pass flight+hold, advance,
moment) consumes clock, so `shot_clock` strictly decreases to a terminal. Reuse the
engine's existing `_build_shot_clock_violation_result` outcome shape, invoked from
inside the loop. A hard iteration cap is therefore **optional** (defensive backstop
against a zero-duration-segment bug), not load-bearing.

> Carryover note: HCT→HCO is **not** a possession change, so the shot clock does
> **not** reset (`_should_reset_shot_clock` returns False when `possession_flips` is
> False). The HCO turn seeds its starting shot clock from the same decremented
> `game_state.shot_clock_remaining`, so e.g. a trap broken at 17 → HCO starts at 17.

### Universal player clamps

Every per-player target/end coordinate the loop produces — for **all 10 active
players**, every segment — must pass through the **universal animation coordinate
clamp** (`clamp_animation_grid_coords` → `ANIMATION_CLAMP_BOUNDS`, subject to
`ANIMATION_CLAMP_EXEMPT_RESULT_TYPES`) so no active player is ever placed out of the
playable area. This matters here because the loop generates many randomized targets
(random advance, broken-HCT spots in the Attack Basket Area, pass-movement spots)
that can otherwise land off-court.

---

## §5 — Moment Resolutions

### Detection (continuous, by distance — runs at each segment boundary)

- **Trap Moment possible if**: two defenders are within **11** euclidean grid spots
  of the BH, AND at least one of them has x closer to the offense basket-x than the BH.
- **Pressure Moment possible if**: one defender is within **11** of the BH, AND his
  x is closer to the offense basket-x than the BH's.

### Decision → moment mapping

- **attack** → Pressure resolution if 1 defender in range; Trap resolution if 2+ in range (see Trapper selection).
- **hold** → time-boxed hold beat; outcome depends on what reaches the BH (see Hold resolution).
- **pass** → no moment (run pass movement, §6).

### Trapper selection (2+ defenders in range)

A trap is always executed by **exactly two** defenders. When more than two are
within trap range (11), pick the two trappers as follows:

1. The **central backcourt defender** (defensive PG) is always one trapper.
2. The second trapper is the **closest** of the other in-range defenders to the BH.
   If two or more are tied for closest, choose one at random.

**Fallback — PG not in range:** if the defensive PG is **not** within trap range
(e.g. the BH has beaten him off the dribble and left him trailing), drop the
PG-priority rule and pick the **two closest in-range defenders** to the BH; ties
broken at random.

Any remaining in-range defenders revert to their zone / help assignments (§6).
For exactly two in-range defenders, both trap (this already always includes the PG
via the shift tables in §6).

### Pressure Moment (one defender)

```
outside_d_score    = calculate_defender_pressure_score
                     + (def_team.pt_efficiency * random.randint(1, 6))
ball_handling_score = calculate_ball_handling_score
                     * (off_team.pt_opp_modifier * random.randint(1, 6))
```

- if `d_score > o_score + 2*(off_chemistry + off_pt_opp_modifier)` → **positive d (DEAD BALL)**:
  BH commits a dead-ball turnover (double dribble / travel) → dead-ball announce + next-step progression.
- elif `o_score >= d_score + 2*(def_chemistry + def_pt_efficiency)` → **positive o**:
  the BH beats the pressure/trap and **advances** toward the basket (he dribbles
  forward; e.g. toward the deep key / PSA). He transitions to HCO **only if** an HCO
  entry trigger is met at the next zone check (§2: in PSA, or in the Attack Basket
  Area with `defenders > offenders`); otherwise he continues the §4 loop.
- else → **neutral**: BH advances per §4 advance rule, then re-reads (or holds-up / attacks if in range).

### Trap Moment (two defenders)

```
outside_d_score    = calculate_defender_pressure_score (BH defender)
                     + 0.5 * calculate_defender_pressure_score (trapper)
                     + (def_team.pt_efficiency * random.randint(1, 6))
ball_handling_score = calculate_ball_handling_score
                     * (off_team.pt_opp_modifier * random.randint(1, 6))
```

Outcome branches (DEAD BALL / HCO / neutral) are identical to the Pressure Moment above.

> Implementation note: `pt_opp_modifier == 0` is treated as multiplier 1 (no-op) so
> an unset team attribute doesn't auto-zero the handling score.

### No defenders in range (broken HCT)

When `detect_by_distance()` returns **none** (no defender within 11 of the BH), the
BH still reads like any other iteration, but with **reduced attack thresholds** (an
open floor invites attack):

- read > 175 → **attack**
- read > 110 → **pass**
- else → **hold**

`pass` and `hold` route to their normal handling (§6 pass movement; hold per §5).
`attack` triggers the **broken-HCT** resolution:

**Offense**
- BH targets the perfect Primary Safe Area spot **(60, 25)**. If that spot is
  *behind* the BH (he is already past it toward the basket), he targets the
  **topLane** spot instead.
- The four teammates each target a **random** spot inside the **Attack Basket Area**
  (§2: x 64 → basket-x, y 10–30), constrained by their *starting* y:
  - starting y > 28 → must pick a spot in the **upper** half (upper = y > 25)
  - starting y < 22 → must pick a spot in the **lower** half (lower = y < 26)
  - central starting y (22–28) → may pick upper **or** lower

**Defense**
- The defender **closest to the BH** targets directly in front of the BH's x target
  — same y, **2 x-spots closer to the basket**.
- All other defenders target the **midLane** spot (to defend a potential pass).

**Resolution / exit**
- When the BH reaches the perfect Primary Safe Area spot (60, 25) → **enter HCO** via
  the existing HCO entry logic (§7 "HCO transition branch — execution"): Handoff step
  by default (`build_handoff_step`, `metadata_reason="hco_entry_handoff"`), which
  auto-branches — *hold-beat* if the BH is the play's step-0 initiator, else a
  converge+pass handoff to the skeleton-derived initiator.
- When the BH reaches the **topLane** spot → execute a **Fast Break** scenario (§7
  Fast-break-from-broken-HCT, D18 — the Steal-FB-equivalent rim attempt).

### Hold resolution (universal)

`hold` = the BH keeps the ball without dribbling for **random(1, 3) game seconds**
(this duration is the hold segment's advance trigger). During the hold the BH stays
put while all defenders keep moving toward their current targets. Outcome is driven
by what reaches the BH **before the hold window elapses**:

- **A defender reaches the BH** → he applies pressure **the instant he arrives**
  (this does not by itself end the hold window):
  - **50% steal attempt** → run the standard **steal resolution** logic.
    - Steal **succeeds** → turnover; possession flips; defense gets the ball (→ steal /
      fast-break flow).
    - Steal **fails** → **50% defensive foul** / **50% no stopping action** → on no-foul,
      proceed to the next loop iteration (BH read).
  - **50% pressure, no steal attempt** → **no outcome yet** (placeholder — future:
    feed into a Pressure Moment contest) → proceed to the next loop iteration (BH read).
- **A second defender** comes within trap distance (11) and converges, **arriving
  during the hold window** → execute a **Trap Moment** (§5). This fires even if the
  first defender already attempted (and failed) a steal earlier in the same window
  (as long as the possession hasn't already ended via a successful steal or a foul).
- **No defender reaches the BH before the window elapses** → enter the **broken-HCT
  resolution** directly (the §5 "No defenders in range" attack execution: BH heads to
  the perfect Primary Safe Area spot (60, 25), or topLane if that's behind him;
  teammates fill the Attack Basket Area; defenders per that section). No new read.

> Note: pressure-with-no-steal currently has no contest/turnover effect — it just
> burns the hold and returns to the loop. Outcomes will be added later.

---

## §6 — Movements

All defender positioning **reuses** `BackEnd/utils/shared_defense.py` — this section
specifies *which helper is called with which inputs*, not a parallel positioning
system. Key helpers: `hct_initial_defender_coords`, `compute_hct_trap_formation`,
`_get_hct_standard_zone_boundaries`, `resolve_hct_defender_collisions`, plus the
`HCT_STANDARD_NORMAL / _UPPER_SHIFT / _LOWER_SHIFT` tables and clamp constants.

### Zone definitions (reference: `HCT_STANDARD_*` in `shared_defense.py`)

**Normal**
- PG: center court, deep key, deep upper wing, deep lower wing, key
- SG: deep upper baseline, deep upper wing, upper wing
- SF: deep lower baseline, deep lower wing, lower wing
- PF: topLane, upper apex, lower apex, upper highPost, lower highPost
- C: midLane, upper midPost, lower midPost, basket spot, upper lowPost, lower lowPost

**Upper Shift** (ball handler y > 30 → PG & SG trap)
- PG (guarding BH): min x 54 (max x 46 if away offense)
- SG (guarding BH): min x 50
- SF: deep key, key
- PF: upper apex, upper highPost
- C: midLane, upper midPost, upper lowPost, basketSpot, lower lowPost, lower midPost

**Lower Shift** (ball handler y < 20 → PG & SF trap)
- PG (guarding BH): min x 57 (max x 43 if away offense)
- SG: deep key, key
- SF (guarding BH): min x 50
- PF: upper apex, upper highPost
- C: midLane, upper midPost, upper lowPost, basketSpot, lower lowPost, lower midPost

**Shift triggers**: ball handler y < 20 → Lower Shift; y > 30 → Upper Shift; else Normal.

### Standard HC Trap

- HC Traps put two defenders on the BH during a shift.
- Each trapper sits 1–4 x-spots ahead of the BH (toward the basket); one at BH_y+2,
  the other at BH_y−2. Defenders cannot stack on the same spot (see
  `compute_hct_trap_formation` + `resolve_hct_defender_collisions`).
- *(Superseded — D10.)* The old standalone "trap breaks → HCO at x=73 (home) / x=27
  (away)" trigger is removed. HCO entry is now governed solely by the two §2 triggers
  (reach the PSA, or reach the Attack Basket Area with `defenders > offenders`).

### Pass Movements

A pass goes to one of the two teammates closest to the BH. Execute the
**Vertical-Half Pass Movement** if it qualifies, else the **Central Pass Movement**.

#### Vertical-Half Pass Movement — qualifies if pass receiver's y > 29 or < 22

**Defense** (while the pass is animating):
- Backcourt:
  - Primary defender = backcourt defender closest to BH/PR who is **not** the
    defensive PG → targets primary-defender location.
  - PG → targets trapper-defender location.
  - Third backcourt defender → targets center-defender spot.
- Front court:
  - Defender in the same vertical half as the BH/PR → targets same y as BH/PR and an
    x halfway between BH/PR x and either (the x of any offensive player in the same
    vertical half whose x > 74) or, if none, halfway between BH/PR x and basket-x.
  - The other front defender → targets the topLane spot.

**Offense**:
- While the ball is in the air: all five players stationary.
- After reception:
  - **BH/PR**: holds at the reception spot for `random.randint(1,3)` game seconds;
    that elapse is the advance trigger → next step.
  - Backcourt center player → y=25 and x four spots closer to basket than BH-x.
  - Other backcourt player → previous BH/passer location, or (x=51, previous
    BH/passer y), whichever has the greater x.
  - Front offender on the same vertical half as BH → BH's y + random(−6,6),
    x = random(83,93).
  - Other front offender → highPost on the opposite vertical half.

#### Central Pass Movement — used if Vertical-Half does not qualify

**Defense** :
While the pass is animating:
    - Backcourt:
        - Primary defender = defensive PG → primary-defender location.
        - Other backcourt defenders → help-defender locations relative to their vertical half.
    - Front court:
        - pos4 → centroid of frontcourt high-post zone.
        - pos5 → centroid of paint/rim zone.
- After reception: 
    - all five defenders continue moving to their targets

**Offense**:
- While the ball is in the air: all five players stationary.
- After reception:
  - **BH/PR**: holds at the reception spot for `random.randint(1,3)` game seconds → advance trigger.
  - Other backcourt players → BH-x + random(−1,6), and BH-y − random(6,15) for the
    lower-half player / BH-y + random(6,15) for the upper-half player.
  - pos4 → `random.choice(wing, midWing, apex, bird)` on his vertical half.
  - pos5 → `random.choice(apex, wing, lowPost, midBaseline, corner, midCorner)` on his vertical half.

---

## §7 — Goal Achievement (Attack Basket Area)

Triggered when the offense reaches the **Attack Basket Area** (§2: x 64→basket,
y 10–30). They will either attempt a shot or transition to HCO.

- **Defender count** = # of defenders within the Attack Basket Area; **Offender
  count** = # of offenders within the Attack Basket Area.
- If `Defender count > Offender count` → **HCO transition** is optimal (HCO entry
  trigger 2, §2). Else (`offenders ≥ defenders`; **ties → attack**) → **shot
  attempt** is optimal.
- BH makes a read (`player_read`): if read > 200 he makes the optimal choice, else a random choice.

### HCO transition branch — execution (reuse existing HCO entry logic)

All HCT→HCO transitions (both §2 triggers, and the broken-HCT exit) use the
**existing HCO entry primitives** rather than a bespoke choreography. The prior
"back up to deep key + pass to step-0 BH" sequence is removed.

**No need to call the HCO playcall at HCT-end.** The next HCO turn resolves its own
playcall, and its entry orchestrator derives the **real step-0 ball handler (the play
initiator)** from the skeleton — *not* assumed to be the PG. The initiator is any
canonical position the play assigns, via the `target_shooter` / `pos1..pos4` system:
a play stores `target_shooter` (a canonical position), `_build_set_play_alias_map` +
`_apply_set_play_runtime_position_mapping` remap the alias-authored skeleton to
canonical positions, and `get_ball_handler_from_skeleton(skeleton, off_lineup,
step_index=0)` reads who holds the ball at **step 0** (the `handle_ball`/`receive`
action) — distinct from `roles.ball_handler`, which is the shooter / final-step BH.

The HCO entry orchestrator (`skeleton_step_emitter.py`) then runs universally:
- `current_bh_id` = prior turn's **`final_ball_handler_id`** (universal).
- `step0_bh_id` = the skeleton-derived **initiator** (any position).
- Handoff / Kickout / Walk Up route from `current_bh` → that initiator (receiver).

**What HCT must do at transition (supports a non-PG initiator):**
1. Stamp **`final_ball_handler_id` = the HCT-end BH** on the result (gives the
   orchestrator the correct `current_bh_id`).
2. Set `result_type` / `next_play_type = "HCO"`, `possession_flips = False` (so the
   shot clock carries over — §4).
3. **Do NOT** force `hco_setup.inbound_pass.to_player_id = PG` for HCT. (`_maybe_stamp_hco_setup`
   currently hardcodes the receiver to the next-offense PG, and `_apply_hco_setup_entry_ids`
   then *overrides* the skeleton-derived initiator with it — that override is the only
   thing forcing PG. With it suppressed for HCT, the orchestrator uses the real
   `step_index=0` initiator and the entry pass routes from the HCT-end BH → that player.)

**Entry-step selector (confirmed override of the stock `in_back_court` branch):**
- Default → **Handoff step** (`build_handoff_step`).
- If the entering BH is **inside the Attack Basket Area** → **Kick Out step**
  (`build_kickout_step`).
- The handoff/kickout primitives **already branch** on whether the entering BH **is**
  the step-0 initiator: if he is, the handoff is the hold-beat (no-pass) variant; if
  not, it's a converge+pass handoff / kickout to the initiator receiver. So the "BH is
  / isn't the step-0 BH" case is handled by existing logic — no new rule needed. This
  selector sets the entry *step type* only; the *receiver* is always the skeleton-derived
  initiator (above).

### Shot-attempt branch

BH has three options: attempt an outside shot from his location, drive to the
basket, or pass to a teammate with x > 64.
- If defender count = 0: the choice is always to drive, or pass to a teammate closer
  to the basket; else use optimal logic.
- **Optimal logic**: if BH SH > 80 → shoot; elif BH SC + AG > 105 → drive; else → pass.
  - If the BH drives, his drive target depends on starting y: y > 30 → upper lowPost;
    y < 20 → lower lowPost; else basketSpot.
  - Any teammate with x > 64 targets a spot from (lower lowPost, upper lowPost,
    midLane, upper midPost, lower midPost, upper midBaseline, lower midBaseline),
    excluding the driver's target. Upper/lower logic mirrors the BH's; all teammates
    can target midLane; no two teammates share a spot.
  - If the BH has teammates in any of those locations: 50% he shoots (attack shot),
    50% he passes (receiving teammate shoots an inside shot).
  - BH makes a read score: read > 200 → optimal option, else random.
  - Defenders behave in standard manner to get into position to defend the shot.
  - **Critical**: track defender locations at the exact moment of the shot attempt.
    If a defender is within 4 x and 6 y of the shooter, he is the shot defender.
    All defenders target a spot in range (basket-x to midLane-x − 3) and y within ±6 of basket-y.

> Implementation flag: prior attempts to snapshot defender locations at shot time
> have been spotty/inconsistent — this is D6 in the tracker. Identify the failing
> path before reimplementing.

#### Top-level pass (pass to a teammate with x > 64)

This is the third shot-attempt option (and the `else → pass` result of the optimal
logic) — distinct from the drive→dish pass above. It does **not** reuse §6's
backcourt pass-to rule (different candidate pool / intent).

**Receiver selection** (candidate pool = teammates with x > 64):
- **Default:** the teammate **closest to the BH**.
- **Override (open rim):** if a teammate is **within 9 euclidean of the basket** AND
  **no defender is within 9 euclidean of that teammate**, he receives instead. If
  two or more qualify, choose one **at random**.

**Receiver's action after the catch:**
- **If the receiver catches inside the Attack Basket Area** (x 64→basket, y 10–30) →
  act on the offender/defender ratio **counted within the Attack Basket Area**:
  - `defenders ≤ offenders` → **attack the basket** (fast-break scenario — same
    bridge as §7 Fast-break-from-broken-HCT, D18).
  - `defenders > offenders` → **hold → HCO**, entered via the **Kick Out step**
    (`build_kickout_step`, same primitive as OREB→HCO; *not* the handoff step,
    because the receiver starts inside the Attack Basket Area).
- **If the receiver catches at x > 64 but *outside* the Attack Basket Area** → he
  becomes the new BH and **re-enters the §4 loop** (detect → read attack/pass/hold →
  resolve). *(Implies the goal-area trigger must be Attack-Basket-Area-based, not raw
  x > 64 — see gap #6 / §2 zone precedence.)*

### Fast-break-from-broken-HCT (D18)

Entry: the §5 "No defenders in range (broken HCT)" branch when the BH reaches the
**topLane** spot. This is a *transition / numbers-advantage* break where the offense
already has the ball in the backcourt and has beaten the trap.

**Execute the equivalent of a Steal Fast Break** (`after_steal_fast_break.py`): the
dribbler attacks the basket and we resolve a single contested-vs-uncontested rim
attempt against the one defender who can get back to protect the rim. The BH is
already the carrier (no outlet pass), so we skip the steal/outlet seed and feed the
current HCT end-state straight into the same resolution shape:

1. **Dribbler attacks the basket.** BH target = `basket_x ± random(2,3)` toward
   center, `y = random(19,31)` (same as the steal FB BH target). Traversal time
   `t_shooter = euclidean(bh_start, bh_target) / bh_sprint_rate`.
2. **Shot defender = the defender closest to the basket.** Assign him the steal-FB
   **shot-defense position** (the defender single target: `BH_target_x ± 2` toward
   basket, same y — i.e. 2 grid spots closer to the rim than the BH's spot). His
   traversal time = `euclidean(start, defender_target) / sprint_rate` (AG-based).
3. **Reaches in time?** If the shot defender's arrival time `< t_shooter` (he beats
   the BH to the rim-defense spot) → **CONTESTED** FB shot with him as the shot
   defender (`calculate_shot_score(apply_defense=True)`; made if
   `shot_score >= shot_threshold`). Otherwise → **UNCONTESTED** FB shot
   (`apply_defense=False`; automatic make, matching the steal-FB / OREB-putback rule).
4. **Outcome + stats** — make/miss handled exactly as the steal FB; possession flips
   on a make/defensive-rebound per the standard shot turn; reuse the steal-FB stat
   wiring (`shot_defender_id`, contested flag, etc.).

> Reuse note: this is the steal-FB resolver minus the outlet/stealer seed — the BH is
> the shooter from his broken-HCT topLane coords, and only the **closest-to-basket**
> defender is evaluated as the lone rim protector (not all five sprinting to one spot).
> Confirm at build whether to call `resolve_after_steal_fast_break` with HCT seed
> coords or factor out its contest core into a shared helper.

---

## §8 — Special Situations

Both time terminals below are checked **inside the HCT loop** at each segment
boundary (see §4 "Time terminals"), not only at the turn boundary.

- **Shot-clock violation**: if the shot clock reaches **0** at any point in the loop,
  it is a shot-clock violation → turnover credited to the offense → **possession
  flips** → SIP. Reuse the engine's `_build_shot_clock_violation_result` outcome,
  invoked from inside the loop. This terminal always applies, regardless of court
  position.
- **10-second violation**: if the offense does not cross half court (x=50) within 10
  seconds, it is a 10-second violation, credited to the BH at the moment of the
  turnover. Evaluate via the shot clock: if the shot clock reaches
  `HCT_SHOT_CLOCK_VIOLATION_THRESHOLD` (20, i.e. 10 seconds elapsed from 30) and the
  BH's x < 50 (home offense) / > 50 (away offense), announce "10-Second Violation"
  and run the standard dead-ball turnover flow → SIP. Once the ball crosses half
  court this rule no longer applies (only the shot-clock-0 terminal remains).
  *(Constant defined; runtime check not yet wired — D9.)*
- **Offensive foul**: *TODO — define trigger formula.*
- **Steal**: *TODO — define trigger formula + mid-flight pass interception (D11).*

---

## §9 — Stats & Integration

- **Stat tracking** (`_record_hct_stats` + `record_stat`): on DEAD BALL, record BH `TO`
  and increment `def_scouting["defense"]["HCT"]["success"]`. `HCT used` is incremented
  on entry. HCT_A / HCT_S (offense) and HCT_A_D / HCT_S_D (defense) per existing conventions.
- **Possession flip**: `result_type in ("DEAD BALL", "STEAL")` flips possession.
- **next_turn**: HCO → HCO; DEAD BALL → SIDE_INBOUND (and `offensive_state` reset to HCO if currently FCP/HCT).
- **Box-score / scouting / season-total parity**: confirm dynamic path doesn't drift
  vs. the skeleton path (D16).

---

## §10 — Implementation Cuts + Question Tracker

Maintained as we implement. Sections:
- **Open (first-cut blockers)** — must resolve before each next implementation step.
- **Open (deferred / post-first-cut)** — known gaps to revisit when we expand scope.
- **Answered** — preserved with brief notes for context.

### Cut status

- **Cut 1 (built)**: Setup walk-up → converge (PG defender) → single attack outcome
  (DEAD BALL | HCO). Always takes the attack branch; one read; BH = PG. No loop,
  pass, shot, foul, steal, or violation yet.
- **Cut 2+ (target)**: the full §4 loop — continuous detection, multiple reads,
  pass branch, neutral-advance iterations, goal-achievement shot/HCO branches.

### Open — first-cut blockers

(Empty — first-cut implementation landed. Open as new gaps surface during testing.)

### Open — deferred / post-first-cut

These will block subsequent cuts but not the first one. Re-open as we widen scope.

- **D2.** Pass-to-side branch full sequence (which teammate, y range, timing). *(Now specified in §6 — promote to build when Cut 2 lands.)*
- **D3.** x=64 transition trigger logic + BH read at x=64 (shot vs HCO). *(Specified in §7.)*
- **D4.** Shot-attempt branch decision tree: SH > 80 / SC+AG > 105 / pass-with-teammates; drive target by y; inside-spot teammate assignment. *(Specified in §7. **Partial** — 2D-2a built the Attack-Basket fork + shoot-in-place leaf; drive/dish = 2D-2b, top-level pass = 2D-2c.)*
- **D5.** ✅ Built (2D-2a). Rim-protection collapse: on a shot attempt each defender moves (standard pace, interrupted to release time) toward the (x∈[77,87], y∈[19,31]) band; release coords computed in `resolve_hct_attack_basket_shot`. (No collision handling yet.)
- **D6.** ✅ Built (2D-2a). Shot-defender = nearest defender ending within 4 x / 6 y of the shooter **at the shot release**, evaluated on the engine-computed D5 release coords (deterministic — sidesteps the prior "spotty" runtime-snapshot timing). Contested → defended shot score; else open (still rolled vs. threshold, no auto-make).
- **D7.** ✅ Resolved (§7 "HCO transition branch — execution") — HCT→HCO supports a
  **non-PG initiator** via the existing `target_shooter`/`pos1..pos4` system: the HCO
  turn resolves its own playcall and the entry orchestrator derives the step-0 initiator
  from the skeleton (`get_ball_handler_from_skeleton(..., step_index=0)`).
  HCT must (1) stamp `final_ball_handler_id` = HCT-end BH, (2) set next_play_type=HCO /
  possession_flips=False, and (3) **suppress the PG override** (`_maybe_stamp_hco_setup`'s
  hardcoded `to_player_id = PG` + `_apply_hco_setup_entry_ids`) so the real initiator is
  used. Entry-step type = Handoff default / Kick Out if BH in Attack Basket Area; receiver
  = the initiator. **Build note**: gate the PG-override suppression for the HCT path.
  Other transitions (DREB / Steal / CR FB / RR FB → HCO) need the same upgrade — tracked
  separately in `HCO_Transition_System_ToDo.md` (do not solve here).
- **D8.** Foul / steal emergent outcomes (currently only DEAD BALL / HCO). *(Reserved as TODO in §8.)*
- **D9.** 10-second violation gate (constant defined; runtime check not wired).
- **D10.** ✅ Resolved — standalone x=73/x=27 trap-break HCO trigger removed; HCO entry now governed solely by the two §2 triggers (PSA, or Attack Basket Area with defenders>offenders).
- **D11.** Pass interceptions mid-flight (stolen pass).
- **D12.** Per-tick energy decay vs. once-per-turn.
- **D13.** Determinism / seeded RNG for replays.
- **D14.** Distant sim path: "decisions only, no movement" short-circuit for franchise CPU sim.
- **D15.** When step-N movement of *other* defenders / offensive teammates kicks in (first cut: only PG defender moves at converge). **Note (render vs. model):** the emitter now progresses off-ball offense toward their setup spots at sprint, interrupted per step and carried forward (the `_build_loop_step` interrupted-coord clamp — fixes the off-ball "jet"), so they *render* as still-en-route. But the **engine** still seeds `off_coords` for all five at the full setup targets and re-asserts them every segment — i.e., its internal model treats off-ball offense as already arrived. Harmless today (no engine decision reads off-ball offensive positions), but D15 (and any logic that does read them — e.g. the "defenders > offenders in the Attack Basket Area" HCO trigger, pass targeting) must switch the engine to track each off-ball player's *actual* lagging position rather than the assumed setup spot.
- **D16.** Result-type stats parity vs. skeleton path (box-score / scouting / season totals).
- **D17.** ✅ Resolved — read thresholds: §4 loop reads attack>200 / pass>120; §5 broken-HCT reads attack>175 / pass>110 (intentional rescale — open floor invites attack); §7 goal-achievement read now >200 (was 190; optimal-vs-random gate, a different decision type than the §4/§5 action gates).
- **D18.** ✅ **Built (Cut 2 / Phase 2D-1)** — Fast-break-from-broken-HCT executes the **equivalent of a Steal Fast Break** (§7): BH attacks the basket; shot defender = defender closest to the basket, assigned the steal-FB shot-defense spot; contested if he reaches in time, else uncontested (auto-make). Implemented in `engine/dynamic_hct_shot.py::resolve_hct_fast_break_shot` reusing `compute_fb_shot_geometry` (lone rim-protector race pool) + `ShotManager.calculate_shot_score`; produces a full MAKE/MISS shot turn (scoring / rebound / defensive-foul-FT / possession / `next_play_type`). Engine routes broken-HCT → topLane via `_psa_is_behind`; emitter appends the drive + `_build_post_shot_sub_steps`. ⚠️ Won't fire in normal play until step-N defender movement (D15) lets the offense beat the trap (the PG re-converges every segment today, so `moment == "none"` is rarely reached).
- **D19.** Pass-movement defender-target persistence: how defender pass-defense targets carry across loop iterations so they don't re-pose / thrash each tick. Cut-2 detail; not a blocker.

### Answered

1. **Tick / step model** — discrete step gates, not a fixed cadence. Each step ends on a defined trigger; movement waypoints inside a step animate at the standard ~800ms granularity. ✓
2. **Initial state** — HCT enters from BIP. BIP skeleton drives the inbound; dynamic HCT takes over from the BH's post-BIP coords. ✓
3. **Offensive movement before x=64** — BH advances at challenged-open-floor pace (16 units/sec) toward (44, target_y in 21–29). Other 4 offenders move toward pos1–4 ranges (geometric alias map). ✓
4. **Defense behavior** — defenders target zone-Normal centroids in step 1 (defensive PG override = exact center court). Trap engages at converge via PG-defender. ✓
5. **End conditions (first cut)** — DEAD BALL → SIP; HCO → HCO turn. Other end conditions deferred. ✓
6. **x=73 vs x=64** — ✅ resolved: x=73 trap-break trigger removed (D10); x=64 belongs to the PSA; HCO entry = the two §2 triggers only. ✓
7. **Foul / steal integration** — DEAD BALL is emergent from the contested score formula. Other outcomes deferred. ✓
8. **Read frequency** — at instigation points only for first cut; continuous (each segment boundary) is the target (§5). ✓
9. **Defender count == 0 override** — deferred (post-first-cut). ✓
10. **Optimal shot/drive/pass** — SC+AG > 105 confirmed as a sum. ✓
11. **Inside-spot teammate movement** — specified in §7; build deferred. ✓
12. **50/50 shoot-vs-pass branch** — specified in §7; build deferred. ✓
13. **Movement pace constants** — in `constants/__init__.py`: `CHALLENGED_OPEN_FLOOR_GRID_PER_GAME_SECOND` (16) for HCT advance, `ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND` (12) for drive-pace dribble. ✓
14. **Loop architecture** — one HCT turn = engine runs the loop internally, returns a variable-length step list (§0). ✓
15. **Moment evaluation** — continuous, distance-based, at segment boundaries (§5). ✓
16. **Defense positioning system** — reuse `shared_defense.py` helpers (§6). ✓
17. **Game clock / shot clock** — game seconds for the 1-sec hold; clock runs per step via `step_clock_seconds`. ✓
18. **Decision → moment mapping** — attack → Pressure(1)/Trap(2); hold → Trap; pass → no moment (§5). ✓
19. **Advance model** — non-terminal iterations advance BH random(6,12) x toward basket, random(−6,6) y, then re-detect + re-read (§4). ✓
20. **Goal-achievement read threshold** — set to >200 (D17); optimal-vs-random gate, distinct from §4/§5 action gates. ✓
21. **Coord orientation** — home-on-offense; flip via `get_away_player_coords` when away offense. ✓
22. **Trap radius** — 11 everywhere (line-109 "12" was a typo). ✓
23. **BH stuck** — addressed via 10-sec violation when wired (D9). ✓
24. **Pass branch scope** — fully specified in §6 (target). ✓
25. **Energy decay** — applied once at HCT entry (per-tick decay deferred — D12). ✓
26. **Stat tracking parity** — first cut maintains HCT used/success + BH TO; full parity check open (D16). ✓
27. **BH selection** — always PG for first cut (BIP receiver). Future: personnel/scouting-driven. ✓

**First-cut emitter contract (preserved)**
- A (BH starting position) — from BIP receive coords (player.coords post-BIP). ✓
- B (defender step-1 targets) — zone-Normal centroids; defensive PG → exact center court. ✓
- C (movers post-1-sec) — keep moving toward target until arrival OR until BH reaches his target. ✓
- D (step-2 movers) — only defensive PG; other 9 hold (first cut). ✓
- E (step-2 trigger) — fires when BH arrives at his exact target (x=44, target_y). ✓
- F (step-2 read timing) — instant when defensive PG and BH meet. ✓
- G (step-3 dead-ball animation) — BH animates to a random point along his path to deep key; defender follows; announce there. ✓
- H (HCO handoff — first cut) — other 9 hold through step 3; HCO step 0 animates them next turn. ✓
- I (pass-to-side) — specified in §6 (build deferred — D2). ✓
- J (10-sec violation) — shot clock = 20, BH hasn't passed x=50; runtime wiring deferred (D9). ✓
- K (BH = PG) — first cut only. ✓

---

## §11 — What's Left To Build (plain list)

Design is complete. These are the remaining work items.

**Deferred features (build later, on purpose):**
- Fouls, steals, and dead-ball turnover outcomes (D8).
- **Over-and-back violation (D20).** Once the BH has crossed x=50 he may not pass
  to a backcourt teammate (x<50 home / x>50 away). **Guard built (preventive):**
  `_select_pass_receiver` drops any backcourt teammate from the two-closest pool
  when the BH is past half-court, so a legal teammate is chosen when one exists.
  **Still TODO:** detect an *actual* over-and-back (no legal option, or a forced
  backward pass) and process it as a dead-ball turnover; extend the guard to the
  2D-2c top-level-pass selection.
- Mid-flight pass interception — stealing a pass in the air (D11).
- Pass-defender target persistence — keep defenders' pass-defense targets steady across loop iterations so they don't jitter each tick (D19).

**Cut 2 — build the full loop (already specified, just needs coding):**
- The full §4 loop: continuous detection, repeated reads, neutral-advance iterations.
- Pass branch / pass-to-side movement (D2).
- x=64 transition read — shot vs HCO (D3).
- Shot-attempt decision tree: shoot / drive / pass (D4). *(Partial — 2D-2a built the Attack-Basket fork + shoot-in-place; drive/dish = 2D-2b, top-level pass = 2D-2c.)*
- ✅ **Rim-protection collapse (D5) — built (Phase 2D-2a).** Defenders close toward the rim band on a shot attempt.
- ✅ **Shot-defender pick at the shot release (D6) — built (Phase 2D-2a).** Nearest defender within 4 x / 6 y of the shooter, on deterministic engine coords.
- ✅ **Broken-HCT fast break (D18) — built (Phase 2D-1).** Real make/miss rim attempt via `dynamic_hct_shot.resolve_hct_fast_break_shot` (reuses the Steal-FB contest core). *(Won't trigger until D15 lets the offense beat the trap.)*
- 10-second violation runtime wiring (D9).
- Step-N movement for the other defenders / teammates, not just the PG defender (D15).
- Stats parity with the existing skeleton path (D16).

**Infrastructure / later polish:**
- Per-tick energy decay instead of once-per-turn (D12).
- Seeded RNG / determinism for replays (D13).
- Distant-sim short-circuit — "decisions only, no movement" for franchise CPU sim (D14).
