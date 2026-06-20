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
- `HCT_TEN_SECOND_LIMIT = 10.0` — actual game-seconds allowed to cross half court
  (measured as elapsed time from possession start, not an absolute shot-clock value;
  disabled when <10s remain in the quarter at possession start) — see §8.

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
- **Defense's goal**: get the ball and two ball-handler defenders into position to execute a trap. Traps can be executed anywhere outside the ABA, but Optimal Trap Areas are the ideal spots for the the defense to exeucte a trap.
- **Offense's goal**: get the ball past x=64 and either attempt a shot within the
  HCT turn (first goal) or transition to HCO turn (secondary goal).

**Attack Basket Area (ABA) — the sole trap-break zone**
- **Definition**: x: 64 → basket-x, **y: 10–40** (the band spans lower wing y=10 →
  upper wing y=40). Effectively **x > 64** within that y-band.
- An HCT possession resolves out of the trap **only** when the BH or PR **reaches the
  ABA**; everywhere else past half court the loop continues and the trap persists.

**Trap-break / HCO trigger.** On reaching the ABA, the BH makes a read that chooses
between **HCO** and a **Fast Break** (the two outcomes; the FB executor is in §7):
- **Optimal choice** by ABA head-count: `defenders > offenders` (counted within the
  ABA) → **HCO**; `defenders ≤ offenders` (ties → attack) → **Fast Break**.
- **Read** (`player_read`):
  - read > **200** → take the **optimal** choice.
  - read **125–200** → **HCO**, *unless* the offense's `aggression` setting is
    **"aggressive"** → then **Fast Break**.
  - read ≤ **125** → **50/50** random (HCO or Fast Break).

**Zone precedence (checked at the top of each loop iteration):**
1. In ABA → §7 goal achievement (HCO or Fast Break per the read above).
2. Anywhere else (past half court but outside the ABA y-band) → **not a trap break**;
   continue the §4 loop (BH read → decision). The trap persists.

**Optimal Trap Areas**
- **Primary**: x: 50–57 and (y < 10 or y > 40). Defense executes a trap here if two
  defenders are within trap distance (11) of the ball handler.
- **Secondary**: x ≥ wing-spot-x and (y < 10 or y > 40). Same trap condition.

> **Deep-corner edge (watch item).** A BH who reaches high x with y *outside* 10–40
> (a deep baseline corner) has no natural ABA resolution until the shot-clock /
> `MAX_LOOP_ITERATIONS` backstop fires (settles to HCO). Mitigation if it surfaces in
> play: widen the ABA y-band, or add a "deep-x ⇒ treat as ABA" fallback so any real
> rim penetration always resolves.

**Terminal conditions (turn enders)**

| Ender | `next_turn` | Possession flips? | Status |
|-------|-------------|-------------------|--------|
| DEAD BALL (turnover) | SIDE_INBOUND → SIP | Yes | Built |
| HCO transition | HCO | No | Built |
| Shot attempt | (shot resolution) | depends on make/miss | §7 — target |
| 10-second violation | SIP | Yes | ✅ Built (D9) |
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
  - **pos1**: x between deep upper wing and x 51 (x 49 for away offense); y between upper deep baseline and upper deep wing.
  - **pos2**: x between deep lower wing and x 51 (x 49 for away offense); y between lower deep baseline and lower deep wing.
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
If the advance lands the BH in the **Attack Basket Area** → §7 goal achievement
(trap break: HCO / shot / FB). Landing anywhere else past half court (outside the
Attack Basket Area) is **not** a trap break → run another read → attack/pass/hold
iteration; the trap continues.

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

**Why this bounds the loop:** every segment (hold 1–2s, pass flight+hold, advance,
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
                     + (off_team.pt_opp_modifier * random.randint(1, 6))
```

- if `d_score > o_score + (off_chemistry + off_pt_opp_modifier)` → **positive d (DEAD BALL)**:
  BH commits a dead-ball turnover (double dribble / travel) → dead-ball announce + next-step progression.
- elif `o_score >= d_score + (def_chemistry + def_pt_efficiency)` → **positive o**:
  the BH beats the pressure/trap and **advances** toward the basket. He resolves the
  possession **only if** the trap-break trigger is met at the next zone check (reaches
  the **Attack Basket Area** → §7 HCO/shot/FB); reaching any other spot is not a
  break — he continues the §4 loop and the trap persists.
- else → **neutral**: BH advances per §4 advance rule, then re-reads (or holds-up / attacks if in range).

### Trap Moment (two defenders)

```
outside_d_score    = calculate_defender_pressure_score (BH defender)
                     + 0.5 * calculate_defender_pressure_score (trapper)
                     + (def_team.pt_efficiency * random.randint(1, 6))
ball_handling_score = calculate_ball_handling_score
                     + (off_team.pt_opp_modifier * random.randint(1, 6))
```

Outcome branches (DEAD BALL / HCO / neutral) are identical to the Pressure Moment above.

### Attribute-driven contest model (D8 — ✅ built)

> Merged from the former `Dynamic_HCT_D8_Scoping.md` (now retired). This is the
> live model `_resolve_moment` + `_apply_moment_outcome` implement; it **extends**
> the simple DEAD BALL / HCO / neutral bands above with emergent **steal / foul /
> turnover** outcomes. **Status:** D8a built; **D8b open** = mid-flight interception
> (D11), over-and-back detection (D20), and final coefficient calibration (§11).

The `d_score`/`o_score` band gates stay the structural fork; inside each winning
region we compute **attribute-derived event odds** instead of forcing one result.

- `m = d_score − o_score` — contest margin (positive ⇒ defense winning).
- **defense-wins** region (`m > GATE_D`, `GATE_D = off_chem + pt_opp`) → {STEAL,
  DEAD BALL, O_FOUL, no-event}.
- **offense-wins** region (`o_score ≥ d_score + (def_chem + pt_eff)`) → mostly
  POS_O, small **D_FOUL**.
- else **neutral** (no event — the re-read beat).

**Design decisions (resolved with owner):** outcomes are **attribute-driven** (not a
flat table); the check runs **every** moment, throttled by a global rate scalar;
foul attribution is **literal** (the actual involved participant); the **aggression**
dial is a trade-off multiplier `AGG_MULT` on the event-fire rate, the steal share,
and `p_dfoul` (it does **not** change who wins the moment); **offense `fight`**
(only offense) suppresses all defense-wins events at the gate, on the same scale as
defense `discipline` suppresses D_FOUL. Hold's "a defender reaches the BH" path runs
this **same** contest (the old 50/50 hardcode is gone).

**Defense-wins — (a) does an event fire?**

```
m_norm  = clamp(m / M_REF, 0, 1)
p_event = clamp(DEF_WIN_BASE * m_norm
                * AGG_MULT[aggression_call]      # aggressive D forces MORE total events
                * (1 - W_FIGHT * fight_off)      # gritty OFFENSE resists ALL D-wins events
                * GLOBAL_SCALAR, 0, P_EVENT_MAX)
# fight_off = OFFENSE team `fight` (centered 0, ±10). Defense `fight` is NOT used.
```
Roll `random() < p_event`; false → no-event (BH retains, normal re-read).

**Defense-wins — (b) which event?** Anchored baseline weights × attribute factors
(each centered at 1.0 for an even matchup), normalized, one draw:

```
DB_W0, STEAL_W0, OFOUL_W0 = 50, 30, 20            # even-matchup baseline split

def_steal = OD*0.4 + AG*0.4 + IQ*0.2   [defender]   # strip ability
bh_secure = CH*0.4 + BH*0.4 + IQ*0.2   [BH]         # ball security
bh_handle = BH*0.4 + CH*0.3 + IQ*0.3   [BH]         # clean-handle (self-TO resistance)

steal_factor = clamp((1 + S_SENS*(def_steal - bh_secure)/REF + W_PTEFF*pt_efficiency)
                       * AGG_MULT[aggression_call], F_MIN, F_MAX)
db_factor    = clamp(1 + DB_SENS*(REF - bh_handle)/REF - W_PTOPP*pt_opp_modifier, F_MIN, F_MAX)
ofoul_factor = clamp(1 + O_SENS_IQ*(IQ[def]-IQ[BH])/REF + O_SENS_DISC*discipline/DISC_SCALE, F_MIN, F_MAX)

P(event) = (W0 * factor) / Σ(all three)            # STEAL / DEAD BALL / O_FOUL
```

**Offense-wins — D_FOUL vs clean POS_O:**

```
beaten_norm = clamp((o_score - d_score) / M_REF, 0, 1)
agility_gap = clamp(AG[BH] - AG[def], 0, REF)
p_dfoul = clamp(DFOUL_BASE * beaten_norm
              * (1 - W_DISC_REACH * discipline_def)     # undisciplined (<0) → more reach fouls
              * (1 + W_AG_BEATEN  * agility_gap / REF)   # beaten/slow defender → reach
              * AGG_MULT[aggression_call]
              * GLOBAL_SCALAR, 0, P_DFOUL_MAX)
```
Roll `random() < p_dfoul` → D_FOUL (bonus → FTs, else SIDE_INBOUND); else POS_O.

**Foul attribution (literal):** `D_FOUL` → the involved defender (`bh_defender`, or
on a trap the credited participant); `O_FOUL` → the BH. Both: `record_stat("F")`,
`team_fouls += 1`, foul-out check, bonus routing; `O_FOUL` also flips possession.

**First-pass tunable constants** (one block; calibrate against sim output — §11):

| Const | Meaning | First-pass |
| --- | --- | --- |
| `DB_W0 / STEAL_W0 / OFOUL_W0` | even-matchup baseline split (50/30/20) | `50 / 30 / 20` |
| `AGG_MULT` | aggression dial (event rate + steal share + D_FOUL) | `passive 0.7 / normal 1.0 / aggressive 1.3` |
| `GLOBAL_SCALAR` | master per-moment event-frequency knob | `1.0` |
| `DEF_WIN_BASE` | base P(any event) on a full D-win | `0.45` |
| `P_EVENT_MAX` | cap on per-moment event prob | `0.60` |
| `M_REF` | margin counting as a "decisive" win | `25` |
| `REF` | league-average attribute (centering) | `50` |
| `F_MIN / F_MAX` | clamp on each attribute factor | `0.3 / 2.5` |
| `S_SENS` | steal sensitivity to (defender − BH) gap | `1.2` |
| `DB_SENS` | dead-ball sensitivity to weak BH handle | `1.0` |
| `O_SENS_IQ` | charge sensitivity to (def IQ − BH IQ) | `0.8` |
| `O_SENS_DISC` | charge sensitivity to team `discipline` | `0.5` |
| `DISC_SCALE` | discipline normalizer | `20` |
| `W_PTEFF` | def `pt_efficiency` → steal factor | `0.04` |
| `W_PTOPP` | off `pt_opp_modifier` → resist self-TO | `0.04` |
| `DFOUL_BASE` | base P(D_FOUL) on a decisive blow-by | `0.12` |
| `P_DFOUL_MAX` | cap on D_FOUL prob | `0.25` |
| `W_DISC_REACH` | team `discipline` → fewer reach fouls | `0.04` |
| `W_FIGHT` | OFFENSE `fight` → fewer D-wins events | `0.04` (= `W_DISC_REACH`) |
| `W_AG_BEATEN` | defender AG deficit vs BH → reach foul | `0.6` |

**Resulting percentages (first-pass constants):**

- *Does anything fire?* decisive D-win, normal aggression → ~45% an event fires
  (~65% no-event); scales with margin, aggression (passive ~24.5% / aggressive
  ~45.5%), and offense `fight` (`+10 → ~21%`, `−10 → ~49%`).
- *Which event* (given one fires): even matchup → **STEAL 30% / DEAD BALL 50% /
  O_FOUL 20%**; elite ball-stopper vs avg BH → ~40 / 39 / 21; weak handler vs avg
  defender → ~32 / 50 / 17.
- *Offense-wins → D_FOUL:* even decisive blow-by (`discipline = 0`) → ~12%;
  undisciplined D + big AG gap → up to 25% (cap); disciplined D → ~7%. `AGG_MULT`
  scales it (~15.6% aggressive / ~8.4% passive).

> Centering caveat: `steal_factor` uses a player *difference* (scale-robust);
> `db_factor` + the `ofoul` IQ term use absolute `REF` — set `REF` to the league-mean
> attribute at calibration. `discipline` is centered at 0 (no reference needed).
> All team attrs at 0 / unset → factor 1 (no-op).

### No defenders in range (broken HCT)

When `detect_by_distance()` returns **none** (no defender within 11 of the BH), the
BH still reads like any other iteration, but with **reduced attack thresholds** (an
open floor invites attack):

- read > 175 → **attack**
- read > 110 → **pass**
- else → **hold**

`pass` and `hold` route to their normal handling (§6 pass movement; hold per §5).
`attack` triggers the **broken-HCT cutoff** resolution.

#### Broken-HCT cutoff model

The open-floor attack is a **race to the rim against a single cutoff defender**:

1. **BH targets a y-keyed Attack Basket Area spot** (so a clean arrival resolves via
   §7), chosen from his current y at the start of the drive:
   - `19 ≤ y ≤ 32` → **topLane (74, 25)**.
   - `y > 32` → **upper apex (80, 36)**.
   - `y < 19` → **lower apex (80, 15)**.
   (Spots flip in x for away offense; the y bands read the same.) He drives there at
   his open-floor drive pace.
2. **Closest defender attempts a cutoff.** Solve the interception geometry along the
   BH's straight path to the target spot: for each point `P` on the path, compare the
   BH's travel time to `P` (`dist / bh_drive_rate`) against the defender's travel time
   to `P` (`dist / defender_rate`, defender speed from his **AG**-based rate). The
   **meet point** is the *first* `P` the defender can reach **no later than** the BH.
3. **No meet point exists (no angle)** → the BH reaches the spot untouched → resolve via
   **§7 goal achievement**: run the **§2 3-tier HCO/FB read** (same as any other ABA
   arrival), then HCO or the unified **Fast Break executor** (D23) accordingly.
4. **A meet point exists (defender has an angle)** → BH and defender **collide at the
   meet point**; resolve with the **D8 `_resolve_moment` contest, steal excluded**
   (its weight re-normalized into the others — a full-speed drive collision is a
   charge/block/lost-handle situation, not a pickpocket):
   - **normal progression** (BH wins) → he gathers and **picks up his dribble** (see
     *Dribble-alive state* below); re-enters the §4 loop **limited to pass/hold**.
   - **O_FOUL** (charge) → offensive foul on the BH → turnover (process per D8).
   - **D_FOUL** (block) → defensive foul on the cutoff defender (process per D8:
     team-foul / bonus → FT, etc.).
   - **DEAD BALL** → lost-handle turnover → SIP, possession flips.
5. **Off-ball movement (the other 8 players)** during this action — **each rolls to
   drift or hold.** Every player except the BH and the cutoff defender independently
   rolls `HCT_DRIFT_PROBABILITY` (**50%**) to **drift toward the offensive rim** at
   the `drift` archetype rate (**8** grid/game-sec, AG-scaled) for the step duration
   (never overshooting the rim), or otherwise **hold** in place. Applies to **both
   teams' off-ball players** and to **both** drive sub-cases (clean arrival and
   meet-point collision). (The previous "teammates fill the Attack Basket Area;
   non-cutoff defenders take midLane" rule is **superseded**; richer directional
   off-ball motion TBD.)

#### Dribble-alive state

A BH who wins a broken-HCT cutoff collision has **used his dribble**:
- While dribble-dead, his reads (both §4-loop and §5-broken) collapse to **pass or
  hold only** — the **attack/drive option is removed**. (Implementation: skip the
  attack tier; e.g. read > pass-threshold → pass, else hold.)
- Because he cannot drive, the **"hold → no defender reaches" case no longer routes
  to a broken-HCT drive**. Instead he simply **re-reads (pass or hold)** while all
  other players keep moving that beat — so if he holds for one or more beats a
  defender will eventually reach him (pressure / trap contest), which keeps the loop
  bounded.
- **Reset:** the restriction lifts the moment **possession transfers to another
  player** (a completed pass makes the receiver the new, dribble-alive BH) or **the
  turn ends**.

### Hold resolution (universal)

`hold` = the BH keeps the ball without dribbling for **random(1, 2) game seconds**
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
- **No defender reaches the BH before the window elapses**:
  - **Dribble alive** → enter the **broken-HCT cutoff resolution** directly (the §5
    "No defenders in range" attack execution: BH races to his y-keyed ABA spot
    (topLane / upper apex / lower apex) vs the closest cutoff defender → FB/HCO or a
    meet-point contest). No new read.
  - **Dribble dead** (he picked it up on an earlier cutoff win) → he **cannot drive**,
    so he simply **re-reads (pass or hold)** while everyone keeps moving.

> **D8 reconciliation (✅ built — see §5 *Attribute-driven contest model*):** the old 50/50
> steal → 50/50 foul hardcode has been **replaced** by the same attribute-driven
> `_resolve_moment` calculation that Attack uses, so a defender's steal/foul/TO odds
> come from attributes (and team `discipline`/`pt_efficiency`/`pt_opp_modifier`/`fight`
> + the `aggression` dial) regardless of whether the contact came from an attack or a
> hold. Hold keeps its own *structure* (1–2s window, who-arrives gating, "no defender
> arrives → broken-HCT"); only the contest math is unified. A pressure-with-no-event
> moment simply returns to the loop for a fresh read (the BH retains).

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

> **D22 override:** the **PF/C rows above no longer drive their in-loop placement** —
> the PF and C now follow the ball-reactive **"Defensive PF/C coverage"** model below
> for the whole possession. The `HCT_STANDARD_*` PF/C entries remain only as the
> initial/centroid reference. The PG/SG/SF rows are unchanged.

### Standard HC Trap

- HC Traps put two defenders on the BH during a shift.
- Each trapper sits 1–4 x-spots ahead of the BH (toward the basket); one at BH_y+2,
  the other at BH_y−2. Defenders cannot stack on the same spot (see
  `compute_hct_trap_formation` + `resolve_hct_defender_collisions`).

### Defensive PF / C coverage (D22 — Behavior Change 2)

The defensive **PF and C** get a dedicated, ball-reactive coverage model for the whole
HCT possession — **replacing** their old static `HCT_STANDARD_NORMAL`-centroid anchor
(they no longer just sit there). The **PG / SG / SF keep their existing §6 behavior**
(trap / pressure / pass defense); this rule is **PF/C only**.

**Shared conventions**
- **Movement:** PF/C move toward their target at their **AG-based sprint rate**,
  interrupted + position-tracking (re-evaluated each segment, D15-style).
- **"The ball" = the ball-handler's position.** During a pass *inside* the ABA, the
  **receiver** governs (switch on the catch).
- **ABA** = x>64, **y 10–40** (corrected, D22).
- **Ball band** (by the ball's y): **center 22–28**, **upper >28**, **lower <22**.
- **ABA half** (only for counting offenders): **lower half = y 1–25**, **upper half =
  y 26–50**.
- Role default: **C = upper-half defender, PF = lower-half defender.**
- **Cutoff/defend the BH** reuses the §5 interception/meet-point solver against the
  BH's current target; if the BH is stationary (shooting) the defender closes out to
  the BH's spot. *(Hook: once the upcoming "BH drifts to basketSpot" behavior exists,
  the center-band PF cutoff targets that drift; until then it defends the BH's §7
  target / current spot — confirmed.)*
- All named spots **flip in x** (`x → 100 − x`) when the away team is on offense; the
  y bands/halves are unchanged.
- Reference spots: `key (64,25)`, `topLane (74,25)`, `midLane (80,25)`,
  `basketSpot (87,25)`, `upper wing (73,40)`, `upper bird (85,36)`,
  `lower wing (73,10)`, `lower bird (85,15)`, key↔topLane midpoint `(69,25)`.

**A) Ball IS in the ABA**
1. **Center band (ball y 22–28):** C → **basketSpot**; PF → **defend the BH** (cutoff
   solver toward his target; basketSpot-drift cutoff once that behavior lands).
2. **Upper band (ball y >28):** C → **defend the BH** (cutoff solver); PF → **midLane**.
3. **Lower band (ball y <22):** PF → **defend the BH** (cutoff solver); C → **midLane**.

**B) Ball is NOT in the ABA** (anywhere else, incl. the backcourt)
1. **Center band (ball y 22–28):** PF → **key↔topLane midpoint (69,25)**; C → **midLane**.
2. **Upper band (ball y >28):**
   - PF → **topLane**.
   - C → **upper wing** **if no offender is in the ABA's upper half** (offenders with
     y ≥ 26 and inside the ABA).
   - **Else** (≥1 such offender):
     a. Pick the **upper-half ABA offender closest to the basket**.
     b. If that offender's **x > upper bird x (85)** (home) / **x < 15** (away) → C
        sits on the straight **BH→offender** line at the point **60% from the BH /
        40% from the offender** (deny the entry pass).
     c. Else (offender x ≤ 85 home / ≥ 15 away) → C sits at **upper bird**.
3. **Lower band (ball y <22):** mirror of (2) with **PF/C roles swapped** and
   **upper→lower** spots:
   - C → **topLane**.
   - PF → **lower wing** if no offender is in the ABA's lower half (y ≤ 25, inside ABA).
   - Else: pick the lower-half ABA offender closest to the basket; if its x > lower
     bird x (85 home / <15 away) → PF on the BH→offender line at 60%-from-BH; else →
     PF at **lower bird**.

> **Sequencing note:** today the ABA resolves in a single beat (the BH's §7
> shot/HCO fires the moment he enters), so the "Ball IS in the ABA" PF/C rules mostly
> inform **shot-contest positioning** (the C at basketSpot naturally becomes the rim
> shot-defender). They become fully load-bearing once the planned interactive ABA
> (BH drift / multi-beat finish) lands.

### Pass Movements

A pass goes to one of the two teammates closest to the BH. Execute the
**Vertical-Half Pass Movement** if it qualifies, else the **Central Pass Movement**.

> **Implementation note (approximated — follow-up):** the detailed per-player
> Vertical-Half / Central spot assignments below are the **design target**, not yet
> fully built. The current build renders the pass via the universal `build_pass_step`
> primitive (offense holds spacing during the flight) and lets off-ball offense keep
> hustling toward their **§4 setup spots** (D15b) rather than these pass-specific spots.
>
> **Pass flight = rate-limited close, then read-and-react (shared across plays).** The
> defense does **not** snap onto the receiver. During the flight the defenders close
> at their **own rate** (`_move_defense`, interrupted by the flight duration) toward
> their play-specific targets anchored on the receiver (the incoming ball) — Standard
> re-forms the trap around the receiver, Straight Pressure keeps each man on his man
> (the on-ball role + rover shift toward the receiver). On the catch the receiver
> becomes the BH with a live dribble (D21) and the loop **re-reads at the top** —
> there is **no forced reception hold**. His §5 read decides attack / hold / pass: if
> no defender is in range he attempts a **Trap Break** drive to his y-keyed ABA spot
> (the shared broken-HCT cutoff — lower apex / topLane / upper apex by his y) while the
> closest defender races to cut him off, exactly as a primary BH would. The new BH also
> drives at **his own** AG-rate. Replacing this with the exact choreography below is an
> open refinement (folded into the upcoming movement-authenticity work).

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
y 10–40). The possession resolves as either a **Fast Break** or a **HCO transition**.

- **Defender count** = # of defenders within the Attack Basket Area; **Offender
  count** = # of offenders within the Attack Basket Area.
- **Optimal choice**: `Defender count > Offender count` → **HCO** (HCO entry trigger 2,
  §2); else (`offenders ≥ defenders`; **ties → attack**) → **Fast Break**.
- The **3-tier read** that picks HCO vs Fast Break (incl. the `aggression`-keyed
  middle tier and the 50/50 floor) is specified in **§2 — Trap-break / HCO trigger**.
- **HCO** runs the *HCO transition branch* below. **Fast Break** runs the *Fast Break
  execution* below (the single FB executor used for both this ABA resolution and the
  broken-HCT topLane arrival).

### HCO transition branch — execution (reuse existing HCO entry logic)

All HCT→HCO transitions (the Attack Basket Area resolution, and the broken-HCT exit
that funnels into it) use the **existing HCO entry primitives** rather than a bespoke
choreography. The prior "back up to deep key + pass to step-0 BH" sequence is removed.

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

### Fast Break execution

The single FB executor, used for **both** entry points: (a) the ABA read chose
*Fast Break* (§2), and (b) the broken-HCT cutoff race delivered the BH to its y-keyed
ABA spot clean (§5). Roles: **BH** = ball carrier; **finisher** = a teammate leaking
ahead. During the FB **drive step**, every player other than the BH (driving to the
rim) and the lone rim protector (contesting) independently rolls
`HCT_DRIFT_PROBABILITY` (**50%**) to **drift toward the offensive rim** at the `drift`
archetype rate (**8** grid/game-sec, AG-scaled, no overshoot) or otherwise **hold** —
on both teams. (Richer directional off-ball motion, e.g. finisher relocation, TBD.)

**Drive target (BH):** `basket_x ± random(2,3)` toward center, `y = random(19,31)`
(the D18 / steal-FB target). Traversal time `t_bh = euclidean(start, target) / bh_rate`.

**Count finishers** — `n_ahead` = non-BH offenders whose x is **at or beyond the BH's**
(toward the basket: x ≥ BH_x home / ≤ BH_x away).

#### A) `n_ahead == 0` — solo drive

Resolve in priority order:
1. **Cutoff?** A defender can intercept along the drive path (`_cutoff_meet_point`:
   defender arrival ≤ BH arrival at some point on the path) → resolve the collision via
   the D8 meet-point contest (`_resolve_moment(exclude_steal=True)`):
   - **normal progression** → BH is **stopped at the meet point** → he takes a
     **contested pull-up** (`shot_type="attack"`, the HCO/§7 drive attack shot) with the
     stopping defender as shot defender.
   - **O_FOUL** (charge) → offensive foul → turnover.
   - **D_FOUL** (block) → defensive foul (bonus → FTs).
   - **DEAD BALL** (lost handle) → turnover → SIP.
2. **Else, rim contest:** no cutoff but a defender can **meet him at the basket**
   (rim-protector arrival ≤ `t_bh`, the D18 arrival test) → **contested FB shot** with
   that defender as shot defender (`resolve_hct_fast_break_shot`).
3. **Else** (no defender in range) → **uncontested FB shot** (auto-make shape).

#### B) `n_ahead > 0` — drive or dish

**Finisher setup (off-ball, set before the drive resolves):**
- The **finisher** = the non-BH offender **closest to the basket**. He relocates to a
  **lowPost on the opposite vertical half from the BH's drive target** (BH target upper
  → finisher *lower* lowPost; BH target lower → finisher *upper* lowPost). If the BH
  drives **center** (target y 22–28) → finisher to the **lowPost on his own starting
  vertical half**.
- **Secondary defender:** if a defender other than the BH defender exists, the
  **next-closest-to-basket** defender targets the finisher with the **D6 shot-defense
  offset** (`finisher_x ± 2` toward basket, same y) to contest a catch-and-shoot.

**Resolve the BH drive:**
- **Cutoff?** (`_cutoff_meet_point`, as in A.1) → D8 meet-point contest:
  - **O_FOUL** → turnover; **D_FOUL** → defensive foul; **DEAD BALL** → turnover → SIP.
  - **normal progression (no foul/turnover)** →
    - **75%** → BH **passes to the finisher**, who shoots an at-rim **FB shot**
      (`resolve_hct_fast_break_shot`) — contested by the secondary defender if assigned
      & in range, else uncontested.
    - **25%** → BH **pulls up** at the meet point (contested `shot_type="attack"` shot,
      cutoff defender as shot defender).
- **No cutoff** → BH reaches the basket and shoots — **contested FB shot** if a rim
  protector arrives in time, else **uncontested** (same terminal sub-cases as A.2 / A.3).

#### Outcome + stats

All FB rim shots use `resolve_hct_fast_break_shot`'s make/miss → turn shape (scoring,
rebound, defensive-foul FTs, possession flips on make / defensive rebound); the
contested pull-up uses the `shot_type="attack"` resolver. Reuse the steal-FB stat
wiring (`shot_defender_id`, contested flag, etc.). Foul/turnover outcomes from the
meet-point contest process exactly as their D8 equivalents (O_FOUL / D_FOUL / DEAD BALL).

> Implementation flag (D6): snapshot defender/shooter coords at the **exact** moment of
> the shot/contest — prior attempts at this have been spotty. The FB shot defender is
> chosen by **arrival time** (above), not the old 4×/6y proximity snapshot.

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
  turnover. Evaluate via **actual elapsed time**: capture the shot clock at the start
  of the possession (`shot_clock_start`); when `shot_clock_start − shot_clock ≥
  HCT_TEN_SECOND_LIMIT` (10) and the BH's x < 50 (home offense) / > 50 (away offense),
  announce "10-Second Violation" and run the standard dead-ball turnover flow → SIP.
  Measuring elapsed time (rather than an absolute shot-clock value) keeps it correct
  when the shot clock is capped to a short quarter (e.g. 13s left → shot clock 13,
  which must **not** instantly trip the rule). It also **cannot fire** when fewer than
  10s remained in the quarter at possession start (`time_remaining`), because the
  period buzzer ends the possession first. Once the ball crosses half court this rule
  no longer applies (only the shot-clock-0 terminal remains).
  *(✅ Built — D9. Both clock terminals are checked at the top of each loop
  iteration; the engine tags `turnover_type` ("SHOT_CLOCK" / "TEN_SECOND"), the
  wrapper carries it onto the DEAD BALL result (possession flips → SIDE_INBOUND),
  and the FE announcement typeMaps render "Shot Clock Violation!" / "10-Second
  Violation!". A defense-forced dead ball stays untyped → generic FE announce.)*
- **Offensive foul**: *TODO — define trigger formula.*
- **Steal**: *TODO — define trigger formula + mid-flight pass interception (D11).*

---

## §9 — Stats & Integration

- **Stat tracking** (`_record_hct_stats` + `record_stat`): on DEAD BALL, record BH `TO`
  and increment `def_scouting["defense"]["HCT"]["success"]`. `HCT used` is incremented
  on entry. HCT_A / HCT_S (offense) and HCT_A_D / HCT_S_D (defense) per existing conventions.
- **Possession flip**: `result_type in ("DEAD BALL", "STEAL")` flips possession.
- **next_turn**: HCO → HCO; DEAD BALL → SIDE_INBOUND (and `offensive_state` reset to HCO if currently FCP/HCT).
- **Box-score / scouting / season-total parity**: ✅ confirmed for produced outcomes
  (D16, Cut 2); foul/steal-stat parity folded into D8.

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
- **D4.** ✅ **Built (2D-2a + 2D-2b + 2D-2c) — ⚠️ superseded by D23.** The original §7 shot-attempt tree: the Attack-Basket fork + shoot-in-place (2D-2a); the shoot/drive/pass optimal logic (SH>80 / SC+AG>105 / pass) + drive target by y + inside-spot teammate relocation + 50/50 drive→dish (2D-2b); and the top-level pass (2D-2c). **Now:** the ABA non-HCO resolution is the unified Fast Break executor (D23); the `shot_type="attack"` drive resolver is reused, shoot-in-place + top-level pass are retired.
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
- **D8.** ✅ **Core built (Cut 2 / D8a) → see §5 *Attribute-driven contest model*.** Attribute-driven foul / steal / turnover emergent outcomes: `STEAL`, `DEAD BALL`, and `O_FOUL` in the defense-wins region; `D_FOUL` (reach-in) in the offense-wins region. Implemented in `_resolve_moment` + the loop's `_apply_moment_outcome`, wired through the wrapper (F / STL / TO stats, foul-out, bonus→FREE_THROW routing, steal→fast-break, possession flips) and the emitter (`STEAL` / `FOUL` turn-stops). Hold's defender-reaches path now shares the same contest engine. Aggression (`AGG_MULT`) raises event/steal/foul rates; offense `fight` symmetrically suppresses defense-wins events. **Deferred to D8b:** mid-flight interception (D11), over-and-back detection (D20), and final coefficient calibration.
- **D9.** ✅ **Built (Cut 2)** — shot-clock (≤0) and 10-second (≤20 & not past half court) terminals checked each loop iteration; engine tags `turnover_type` ("SHOT_CLOCK"/"TEN_SECOND"), wrapper carries it onto the DEAD BALL turnover (possession flips → SIDE_INBOUND), FE announces "Shot Clock Violation!" / "10-Second Violation!".
- **D22.** ✅ **Built (Behavior Change 2).** (a) **ABA y-band corrected** to **10–40** (`ATTACK_BASKET_Y_MAX = 40`; lower wing → upper wing y; was erroneously 10–30). (b) **Defensive PF/C ball-reactive coverage** (`_pf_c_targets` / `_pfc_help_denial`, wired through `_defense_targets` → `_move_defense` / `_position_defense`) replaces their static NORMAL-centroid anchor for the whole possession (PG/SG/SF unchanged): ball-in-ABA → on-ball close-out + basketSpot/midLane anchor by band; ball-not-in-ABA → topLane / midLane / key-topLane-midpoint anchors plus a wing/bird/pass-denial help rule keyed to the closest deep ABA offender (tie-break → higher x). PF/C move at **AG sprint**, re-evaluated each beat. The in-ABA "defend the BH" close-out currently converges between BH and basket; the §5 interception solver hooks in once the interactive-ABA "BH drift to basketSpot" behavior is defined (forward dep, not yet built).
- **D11.** Pass interceptions mid-flight (stolen pass).
- **D12.** Per-tick energy decay vs. once-per-turn.
- **D13.** Determinism / seeded RNG for replays.
- **D14.** Distant sim path: "decisions only, no movement" short-circuit for franchise CPU sim.
- **D15.** ✅ **Built (Cut 2) — defender side.** The engine now moves defenders with **rate-limited, interrupted, position-tracking** motion instead of snapping them onto the BH every segment. `_defense_targets` computes each defender's §6 desired spot (normal → PG converges; trap → two trappers + center; others hold); `_move_defense` advances each defender from its *actual* current spot toward that target at its own AG rate (backcourt `standard`; **PF/C `sprint`**, D22), **interrupted** by the segment duration (`_interrupted_coord`), matching the emitter's render. Wired into the **advance**, **hold**, and **pass-flight** segments (the broken-HCT cutoff moves only the cutoff defender). Consequence: a quicker BH gains **real separation** — the chasing defender trails (no longer "ahead"), so `_detect_moment` returns `"none"` and the **broken-HCT / fast-break (D18)** branch becomes reachable in normal play (verified). Only the initial **converge** still snaps by design (initial engagement); the pass defense now **closes at rate** during the flight (no snap) and the receiver reads-and-reacts on the catch (see §6 Pass Movements).
- **D15b.** ✅ **Built (Cut 2) — offense side.** The engine now tracks each off-ball player's *actual* position instead of assuming they've arrived at setup. `_walk_up_loop_start_offense` seeds loop-start coords by replaying the BH-gated walk-up (off-ball move toward setup at `sprint` for the BH's standard-rate travel time, interrupted — mirrors the emitter's `build_walk_up_step`), reading the prior turn's `final_coords`; `_move_offense` then advances them toward setup each time-advancing segment (converge / advance / hold / pass flight), excluding the BH and any mid-catch receiver. The broken-HCT cutoff (and the FB drive step) is the exception — the off-ball 8 each **roll 50% to drift toward the rim (`drift`, 8 grid/sec) or hold** during it (`HCT_DRIFT_PROBABILITY`). Consequence: the position-dependent reads — the **Attack-Basket "defenders > offenders"** HCO trigger (`_count_in_attack_basket`) and **pass targeting** (`_select_pass_receiver`, `_select_top_level_pass_receiver`, whose pool = teammates past x=64) — now use real lagging coords, so a teammate who set up deep but hasn't arrived isn't counted/targeted as if present (verified). Falls back to "arrived at setup" when no prior-turn coords exist (first possession / offline tests). Engine and render stay aligned (the emitter consumes the engine's tracked segment coords; its interrupted clamp becomes a no-op safety net).
- **D16.** ✅ **In-scope portion built (Cut 2).** Bookkeeping parity vs. the skeleton path for the outcomes the dynamic loop actually produces. Already present: `["used"]` (shared pre-branch), `_record_hct_stats` (HCT_A/_S + HCT_A_D/_S_D) on HCO / DEAD BALL / all three shot types, `TO` + `["success"]` on the violation/forced turnovers, and full box score on dynamic shots (`FGA`/`FGM`/`PTS` via `apply_scoring`, defensive-foul `F`+FTs, rebound stats). Added: the **defensive-success scouting bump** (`def_team.scouting_data["defense"]["HCT"]["success"] += 1`) on a clean dynamic-shot stop (miss, no shooting foul) in both shot resolvers, matching the skeleton SHOT-miss path. **Deferred to D8:** loop-level `O_FOUL`/`D_FOUL` (`F`, `team_fouls`, foul-out, bonus→FREE_THROW) and `STEAL` (`STL`, `last_stealer`, steal→fast-break) stats — the dynamic loop doesn't emit those outcomes yet, so their parity is folded into D8.
- **D17.** ✅ Resolved — read thresholds: §4 loop reads attack>200 / pass>120; §5 broken-HCT reads attack>175 / pass>110 (intentional rescale — open floor invites attack); §7 goal-achievement read now >200 (was 190; optimal-vs-random gate, a different decision type than the §4/§5 action gates).
- **D18.** ✅ **Built (Cut 2 / Phase 2D-1)** — Fast-break-from-broken-HCT executes the **equivalent of a Steal Fast Break** (§7): BH attacks the basket; shot defender = defender closest to the basket, assigned the steal-FB shot-defense spot; contested if he reaches in time, else uncontested (auto-make). Implemented in `engine/dynamic_hct_shot.py::resolve_hct_fast_break_shot` reusing `compute_fb_shot_geometry` (lone rim-protector race pool) + `ShotManager.calculate_shot_score`; produces a full MAKE/MISS shot turn (scoring / rebound / defensive-foul-FT / possession / `next_play_type`). Engine routes broken-HCT → topLane via the **cutoff race** (`_do_broken_hct_cutoff`; a clean arrival with a numbers edge seeds the FB); emitter appends the drive + `_build_post_shot_sub_steps`. ✅ Now reachable in normal play: D15's interrupted defender movement lets a quicker BH out-run the PG so `moment == "none"` can occur.
- **D19.** ✅ **Superseded.** Pass-defense no longer snaps-and-persists a formation around the receiver. The flight now uses **rate-limited** closing (`_move_defense` anchored on the receiver) and the catch hands off to the §5 read-and-react loop (no forced reception hold), so there is no per-tick re-pose to persist. The new BH also recomputes his **own** AG drive rate.

### Answered

1. **Tick / step model** — discrete step gates, not a fixed cadence. Each step ends on a defined trigger; movement waypoints inside a step animate at the standard ~800ms granularity. ✓
2. **Initial state** — HCT enters from BIP. BIP skeleton drives the inbound; dynamic HCT takes over from the BH's post-BIP coords. ✓
3. **Offensive movement before x=64** — BH advances at challenged-open-floor pace (16 units/sec) toward (44, target_y in 21–29). Other 4 offenders move toward pos1–4 ranges (geometric alias map). ✓
4. **Defense behavior** — defenders target zone-Normal centroids in step 1 (defensive PG override = exact center court). Trap engages at converge via PG-defender. ✓
5. **End conditions (first cut)** — DEAD BALL → SIP; HCO → HCO turn. Other end conditions deferred. ✓
6. **x=73 vs x=64** — ✅ resolved: the x=73 trap-break trigger was removed; x=64 is the Attack Basket Area boundary; HCO entry = the Attack Basket Area resolution only. ✓
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
23. **BH stuck** — addressed via the 10-sec violation (✅ wired — D9). ✓
24. **Pass branch scope** — fully specified in §6 (target). ✓
25. **Energy decay** — applied once at HCT entry (per-tick decay deferred — D12). ✓
26. **Stat tracking parity** — ✅ parity confirmed for produced outcomes (HCT used/success, HCT_A/_S, BH TO, dynamic-shot box score + defensive-success bump on a clean stop); foul/steal-stat parity folded into D8 (D16). ✓
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
- J (10-sec violation) — shot clock = 20, BH hasn't passed x=50; ✅ runtime wired (D9). ✓
- K (BH = PG) — first cut only. ✓

---

## §11 — What's Left To Build (plain list)

Design is complete. These are the remaining work items.

**Deferred features (build later, on purpose):**
- ✅ Fouls, steals, and dead-ball turnover outcomes (D8a — built; see §5 *Attribute-driven contest model* for the formulas + tunable constants). Remaining D8b: mid-flight interception (D11), over-and-back classification (D20), coefficient calibration.
- **Over-and-back violation (D20).** Once the BH has crossed x=50 he may not pass
  to a backcourt teammate (x<50 home / x>50 away). **Guard built (preventive):**
  `_select_pass_receiver` drops any backcourt teammate from the two-closest pool
  when the BH is past half-court, so a legal teammate is chosen when one exists.
  The FB executor's dish is forward-only (finisher is at/ahead of the BH toward the
  rim), so it satisfies the guard by construction. **Still TODO:** detect an *actual*
  over-and-back (no legal option, or a forced backward pass) and process it as a
  dead-ball turnover.
- Mid-flight pass interception — stealing a pass in the air (D11).
- Pass-defender target persistence — keep defenders' pass-defense targets steady across loop iterations so they don't jitter each tick (D19).

**Cut 2 — build the full loop (already specified, just needs coding):**
- The full §4 loop: continuous detection, repeated reads, neutral-advance iterations.
- Pass branch / pass-to-side movement (D2).
- x=64 transition read — shot vs HCO (D3).
- ⚠️ **Shot-attempt decision tree: shoot / drive / pass (D4) — built (2D-2a/2b/2c), now superseded by D23.** The ABA non-HCO resolution is now the unified **Fast Break executor** (§7), not the shoot/drive/pass tree. The `shot_type="attack"` drive resolver is **kept** (reused for the FB contested pull-up); shoot-in-place + the top-level pass branch are **retired**.
- ✅ **Rim-protection collapse (D5) — built (Phase 2D-2a).** Defenders close toward the rim band on a shot attempt.
- ✅ **Shot-defender pick at the shot release (D6) — built (Phase 2D-2a).** Nearest defender within 4 x / 6 y of the shooter, on deterministic engine coords.
- ⚠️ **Broken-HCT fast break (D18) — built (Phase 2D-1), now folded into D23.** Real make/miss rim attempt via `dynamic_hct_shot.resolve_hct_fast_break_shot` (reuses the Steal-FB contest core). D23 makes this the **single FB executor** for both the broken-HCT topLane arrival *and* the ABA Fast-Break resolution; the resolver core is reused.
- ✅ **Interrupted defender movement (D15) — built (Cut 2).** Defenders chase at their own rate (interrupted, position-tracking) instead of snapping onto the BH, so a quicker BH gains real separation and broken-HCT fires.
- ✅ **Off-ball offense position tracking (D15b) — built (Cut 2).** Engine tracks each teammate's actual lagging position (walk-up replay + per-segment hustle), so the Attack-Basket count and pass-targeting reads use real coords.
- ✅ **Shot-clock + 10-second violation wiring (D9) — built (Cut 2).** Clock terminals tagged + announced (turnover → SIDE_INBOUND, possession flips).
- ✅ **Stats parity with the skeleton path (D16) — built (Cut 2).** Bookkeeping matches for the outcomes the dynamic loop produces (used/success, HCT_A/_S, dynamic-shot box score, defensive-success bump on a clean stop); foul/steal-stat parity folded into D8.

**Behavior Change 3 (FB rework):**
- **D23.** **Unified Fast Break executor + ABA HCO/FB read.**
  - ✅ **Stage 1 built.** The §2 3-tier read (`_aba_hco_or_fb`, HIGH 200 / MID 125,
    offense-`aggression`-keyed middle tier) now picks HCO vs Fast Break at the ABA
    **and** on a clean broken-HCT topLane arrival. The non-HCO result routes through
    one executor (`_do_fast_break`) → `resolve_hct_fast_break_shot` (drive + lone
    rim-protector contested/uncontested attempt), folding in D18. The old D4
    shoot-in-place + top-level-pass routing is **retired** (no longer produced by the
    engine).
  - ⏳ **Stage 2 pending** (the new nuance): count finishers (`n_ahead`); solo-drive
    cutoff-along-the-path → contested pull-up (`shot_type="attack"`); drive-or-dish
    (finisher opposite-half lowPost fill + secondary-defender D6 cover; 75% dish /
    25% pull-up on a no-foul cutoff). Needs resolver overrides (forced shot defender +
    finisher shooter) + emitter steps for the finisher relocation / dish pass.
- **D24.** ❌ **Removed (reverted).** The Offense Situational Multiplier (a positional
  `OSM` coefficient on the contest-gate margin terms) has been **removed entirely** —
  both gates are now plain `d_score`/`o_score` + `(chem + pt_*)` with no multiplier.
  (`_offense_situational_multiplier` / `_in_optimal_trap_area` and the `HCT_OSM_*` /
  `HCT_OTA_*` constants are deleted.) The §2 *Optimal Trap Area* zones remain a
  descriptive "ideal trapping ground" concept with no contest-math effect.

**Infrastructure / later polish:**
- Per-tick energy decay instead of once-per-turn (D12).
- Seeded RNG / determinism for replays (D13).
- Distant-sim short-circuit — "decisions only, no movement" for franchise CPU sim (D14).

---

## §12 — Quick Reference: The Core Step Loop (TL;DR)

**One HCT turn = one whole possession.** The engine repeats a
**check → detect → read → resolve → move** loop; each pass emits one animation step.
It exits when the BH reaches the Attack Basket Area, a turnover/foul/steal fires, or
a clock violation hits.

### The loop, step by step

| # | Step | What it does | Advance trigger |
|---|------|--------------|-----------------|
| 0 | **Walk-up** (once) | BH brings the ball up to `(44, y 21–29)`; the other 9 hustle toward setup spots | BH reaches his spot |
| 1 | **Check clocks** | shot-clock ≤ 0 → violation; shot-clock ≤ 20 & behind half court → 10-sec violation | — (instant) |
| 2 | **Detect** | Count defenders within **11** of the BH (and on the basket side) → none / pressure / trap | — (instant) |
| 3 | **Read** | BH rolls a read score → **attack / pass / hold** | — (instant) |
| 4 | **Resolve + move** | Run the chosen branch (below); everyone moves one beat | branch-specific (see below) |

Then loop back to step 1.

### Decision thresholds (the read)

Read score = `int( (IQ·0.8 + CH·0.2) · random(1,6) )`, then:

| Situation | attack if | pass if | else |
|-----------|-----------|---------|------|
| **Defender(s) near** (§4 loop) | read > **200** | read > **120** | hold |
| **No defender near** (broken HCT) | read > **175** | read > **110** | hold |
| **At the Attack Basket Area** (§7) | read > **200** → optimal (HCO/FB); **125–200** → HCO unless offense aggressive; **≤125** → 50/50 | | |

### Player movement levels (per beat)

| Mover | Speed | Notes |
|-------|-------|-------|
| BH walk-up | `CHALLENGED_OPEN_FLOOR` = **16** grid/sec | only during step 0 |
| BH **advance** (beat the pressure/trap) | `+random(6,12)` x toward basket, `random(−6,6)` y | one neutral/won beat |
| BH **drive / cutoff race** | `ATTACK_DRIVE` = **12** grid/sec | open-floor attack to y-keyed ABA spot (topLane `(74,25)` / upper apex `(80,36)` / lower apex `(80,15)`) |
| BH **hold** | stationary for `random(1,2)` game-sec | defenders keep closing |
| Backcourt defenders | AG-based **`standard`** rate | interrupted + position-tracking (real separation possible) |
| Front defenders (PF/C) | AG-based **`sprint`** rate | ball-reactive coverage (§6 D22) |
| Off-ball offense | AG-based **`sprint`** toward setup | except during the cutoff race / FB drive → see drift |
| Off-ball **drift** (cutoff race + FB drive steps) | `drift` = **8** grid/sec toward the rim | per-player **50%** (`HCT_DRIFT_PROBABILITY`) to drift vs hold; both teams |

AG rates via `ag_to_grid_per_game_sec`; AG=50 reproduces the legacy constants.

### Pressure vs. trap detection

At each beat, look at defenders within **11** grid-spots of the BH whose x is on the
basket side of the BH:

- **0 in range →** broken HCT (open floor) — use the lower read thresholds; `attack`
  becomes a **cutoff race** to the y-keyed ABA spot (topLane / upper apex / lower apex).
- **1 in range →** **Pressure Moment** (on `attack`, or when one defender reaches the
  BH during a `hold`).
- **2+ in range →** **Trap Moment**. Two trappers = the defensive **PG** + the closest
  other in-range defender (if the PG is out of range, the two closest). Trappers sit
  **1–4 x-spots ahead** of the BH at **BH_y ± 2**.

### Result algorithm (attack, or contact during a hold)

**1. Score the contest** (higher = better for that side):

```
d_score = defender_pressure_score              (Trap: + 0.5 × 2nd trapper’s pressure_score)
          + def_team.pt_efficiency × random(1,6)
o_score = ball_handling_score + (off_team.pt_opp_modifier × random(1,6))
```

**2. Pick the region** (the structural fork):

- **Defense wins** — `d_score > o_score + (off_chem + off_pt_opp)`
- **Offense wins** — `o_score ≥ d_score + (def_chem + def_pt_eff)` → BH **advances**;
  resolves the possession **only** if that advance reaches the **Attack Basket Area**.
- **Neither (neutral)** — BH advances one beat, then re-reads. *(no turnover/foul)*

**3. Roll the outcome inside the winning region** (the D8 layer — full math in §5):

- **Defense-wins →** roll *does an event fire?* `p ≈ DEF_WIN_BASE(0.45) × margin ×
  aggression × (1 − fight_off)`. If yes, pick one by attribute-weighted odds
  (even-matchup baseline **STEAL 30 / DEAD BALL 50 / O_FOUL 20**). If no event →
  BH keeps it, loop continues.
- **Offense-wins →** small **D_FOUL** (reach-in) chance `≈ DFOUL_BASE(0.12) × margin
  × aggression × (undisciplined?) × (beaten/slow?)`; else a clean advance.

**Dials:** `aggression` raises the event / steal / D_FOUL rates (it does **not** change
who wins); offense **`fight`** symmetrically lowers all defense-wins events;
`discipline` lowers D_FOUL; `pt_efficiency` / `pt_opp_modifier` nudge steal / self-TO.

### Cutoff race (broken-HCT attack)

BH sprints to a y-keyed ABA spot (`19 ≤ y ≤ 32` → topLane `(74,25)`; `y > 32` → upper
apex `(80,36)`; `y < 19` → lower apex `(80,15)`); the closest defender solves an
interception point (BH drive pace vs his AG rate). **No angle →** BH arrives → §7 FB/HCO by ABA head-count.
**Angle →** collide at the meet point → resolve with the same contest **minus steal**
(charge / block / lost-handle / clean win). A clean win makes the BH **dribble-dead**
(pass/hold only until he gives it up).

### The handful of knobs to tune

| Knob | Where | First-pass |
|------|-------|------------|
| Read thresholds | §4 / §5 | attack 200/175, pass 120/110 |
| Detection / trap radius | §1 | **11** |
| Advance distance | §4 | x `+6..12`, y `±6` |
| Hold window | §5 | `1–2` game-sec |
| Move speeds | §1 | walk-up 16, drive 12, AG rates |
| Win-margin gates | §5 | `(chem + pt_*)` added to the loser's score (no multiplier) |
| D8 event rate / split / D_FOUL | §5 table | base 0.45, 30/50/20, 0.12 |
| Aggression / fight / discipline scaling | §5 | `AGG_MULT 0.7/1.0/1.3`, `W=0.04` |
| Clock terminals | §1 / §8 | shot-clock 0; 10-sec = 10 actual elapsed sec behind half court (disabled if <10s left in quarter) |
| Loop backstop | §1 | `MAX_LOOP_ITERATIONS = 15` |

### Fast Break execution (summary)

Full spec in **§7**. On a Fast Break (ABA read chose FB, or broken-HCT topLane arrival):
- Count **finishers** — `n_ahead` = non-BH offenders at/ahead of the BH toward the rim.
- **Solo (`n_ahead == 0`):** BH drives (`basket_x ± 2..3`, y 19–31); priority — cutoff
  contest (`_cutoff_meet_point` → stop + contested pull-up / O_FOUL / D_FOUL / DEAD BALL)
  → else rim-protector contest (`resolve_hct_fast_break_shot`) → else uncontested.
- **With finisher (`n_ahead > 0`):** the closest-to-rim teammate fills the opposite-half
  lowPost (own half if the BH drives center); a secondary defender (D6 offset) covers him.
  On a cutoff with no foul/TO → **75%** dish → finisher FB shot, **25%** BH pull-up; no
  cutoff → BH rim shot (contested by arrival, else uncontested).
- **Knobs:** the 75/25 dish split, finisher lowPost target, D6 cover offset.

---

## §13 — Multiple HCT Trap Plays — Architecture & Implementation Plan

**Goal.** Turn today's single hardcoded trap into a *family* of selectable defensive
plays. The current behavior becomes **Standard Trap**; two more follow later
(**Straight Pressure**, **Diamond**). Selection, playbook storage, scouting, and
gameplay wiring **exactly mirror the Fast Break play system**; behavior dispatch uses
a pluggable play interface (the formalized version of FB's per-play modules).

### 13.1 — The three layers (and what changes)

| Layer | Today | Target |
|-------|-------|--------|
| **Selection** | `determine_defensive_pressure_type()` returns `"HCT"` (one flavor) | same fn also picks *which* trap and stashes it (SS&S) |
| **Dispatch** | `offensive_state == "HCT"` → `compute_dynamic_hct_turn` (monolith) | `compute_dynamic_hct_turn` resolves an `HCTPlay` from a registry and drives the loop via its methods |
| **Behavior** | ~2 dozen module constants in `dynamic_hct.py` + `HCT_STANDARD_*` tables | each lives on/under an `HCTPlay` implementation |

`offensive_state` **stays `"HCT"`** (coarse mode). The chosen play is a *sub-selector*,
so all existing routing, HCT stat parity, skeleton fallback, FE announcements, and
possession-flip handling keep working untouched.

### 13.2 — Selection pipeline (mirrors Fast Breaks)

| Fast Break piece | HCT equivalent |
|---|---|
| `constants/fast_break_play_types.py` | new `constants/hct_trap_play_types.py` — keys, `HCT_TRAP_PLAY_KEYS`, `DEFAULT_HCT_TRAP_WEIGHTS` |
| `playbook_settings["fast_breaks"]` weight map | `playbook_settings["hc_traps"]` weight map |
| `play_key_for_fast_break_entry()` | `play_key_for_hct_trap()` (weighted-random over keys) |
| `pending_dreb_fb_play_key` stash | `game_state["hct_trap_play"]` stash |
| `scouting["offense"]["fast_break_plays"]` A/S | `scouting["defense"]["hct_trap_plays"]` A/S |
| `ensure_fast_break_plays()` migration | `ensure_hct_trap_plays()` migration |

Canonical keys: `standard_trap`, `straight_pressure`, `diamond`.

**Two deliberate (and inherent) differences from FB — because a trap is a *defense*
play:**
1. Weights are read from the **defending** team's `playbook_settings`; per-play A/S
   counters live under `scouting["defense"]`.
2. In the playbook/UI, `hc_traps` is a **defensive** category — a sibling of
   `zone_defense` / `man_defense`, not of `fast_breaks` (which is offensive). Only the
   *machinery* mirrors FB.

**Stash point (SS&S).** ~6 call sites do
`offensive_state = determine_defensive_pressure_type()`. Rather than duplicating the
trap-play pick at each, the single source of truth (`determine_defensive_pressure_type`)
computes it **once** when it returns `"HCT"` and writes `game_state["hct_trap_play"]`.
`compute_dynamic_hct_turn` reads that one synced value, with `play_key_for_hct_trap()`
as the fallback if missing. (FB's select-once → stash → consume-with-fallback shape.)

**Relationship to the existing gate.** `strategy_settings["hc_trap"]` (0–4) is
untouched — it remains the *"how often do I trap at all"* frequency gate.
`playbook_settings["hc_traps"]` only decides *which* trap once trapping is chosen.
(Identical dual structure to FB's `strategy_settings["fast_breaks"]` slider vs
`playbook_settings["fast_breaks"]` weights.)

### 13.3 — The `HCTPlay` pluggable interface

Base class with one implementation per play (Standard inherits the current logic
verbatim). Methods map to the loop's existing phase seams:

- `build_formation(...)` — trap formation + PF/C coverage (`HCT_STANDARD_*` tables).
- `detect_pressure_and_trappers(...)` — detection radius + who commits.
- `bh_decision(...)` — attack / pass / hold thresholds.
- `resolve_moment(...)` — `o_score`/`d_score` gates, `DEF_WIN_BASE`, outcome split.
- `movement(...)` / drift policy — rates, `HCT_DRIFT_PROBABILITY`.

**Play-agnostic plumbing stays OUTSIDE the play** (so every play inherits it
consistently): the time terminals (shot-clock 0 + the elapsed-based 10-second rule),
HCT stat parity (`HCT_A/_S`, `HCT_A_D/_S_D`), schema/step emission, and possession
flips. A registry maps key → `HCTPlay`; `compute_dynamic_hct_turn` becomes thin.

### 13.4 — Playbook touchpoints (add `hc_traps`, mirroring `fast_breaks`)

| Area | File(s) | Change |
|---|---|---|
| Default playbook | `gameplan_routes.py` (`initialize_playbook_settings`, success + error paths) | add `"hc_traps"` default weights |
| Section enumerations | `gameplan_routes.py` (`_has_*` scan), `team_settings_manager.py` (section lists ×2) | add `"hc_traps"` |
| Normalization | `api.py` (`normalize_string_keyed_map`), `team_settings_manager.py` | normalize/merge `hc_traps` like `fast_breaks` |
| Persistence/migration | `team_settings_manager.py` merge + `ensure_hct_trap_plays()` | old saves get `hc_traps` defaults on load |
| CPU teams | `cpu_playbook_customization.py` | `next_settings["hc_traps"] = _random_capped_three((...))` |
| Frontend UI | *(frontend repo — separate, deferred)* | `HCT Traps` weight section in the defense group |

API accepts/returns `hc_traps` immediately; until the frontend ships its slider
section, teams run on the default weights (PR1: 100% Standard Trap; PR2: 50/50
Standard / Straight Pressure; Diamond stays 0 until PR3).

### 13.5 — PR boundary (refactor-first)

- **PR1 (parity):** stand up the full pipeline (keys module, `hc_traps` settings +
  defaults + CPU gen + normalization, selector, defense-side scouting counters,
  `HCTPlay` interface + registry), but register **only `standard_trap`** carrying
  today's logic verbatim. Default weights = 100% `standard_trap` → selection always
  resolves to it → behavior provably unchanged. Verify via offline smoke (no crash,
  no behavior delta vs current).
- **PR2:** implement `straight_pressure` as a new `HCTPlay` (spec in §13.6); add to default weights.
- **PR3:** implement `diamond` as a new `HCTPlay`; add to default weights.
- **Frontend:** `HCT Traps` UI section (after backend lands).

### 13.6 — Straight Pressure (play #2) spec

Straight Pressure is **man-to-man backcourt pressure.** The three backcourt
defenders (PG/SG/SF) **lock onto a man at the converge** and stick to him until a
stop event (ball reaches the ABA / foul / dead-ball TO / steal / forced HCO),
**except** a man who enters the ABA is *released* and the freed defender fills a
**help role** (rover → key → wings). It diverges from Standard **only in the
backcourt**; everything frontcourt/ABA is inherited.

**Backcourt membership.** An offensive player is a *backcourt offender* iff
`x < 64` (home) / `x > 36` (away). This is the `_is_backcourt_offender` test —
deliberately **x-based**, distinct from the ABA y-band test (a deep player at
`x>64, y>40` is frontcourt, not a backcourt outlet).

**Initial man assignment (locked at the converge, by positioning):**
- **center/PG defender → the ball handler** (`_converge_xy`, on-ball).
- The two off-ball defenders (def SG/SF) cover, by **nearest-matchup (no cross)**,
  the **two non-BH backcourt offenders closest to the BH**, taking the **higher-y**
  and **lower-y** of those two.
  - **1 non-BH backcourt offender:** the off-ball defender **nearest** that man
    takes him; the other becomes the **rover/trapper**.
  - **0 non-BH backcourt offenders:** the off-ball defender **nearest the BH**
    becomes the rover/trapper; the other becomes the **key** defender.

**Sticky man defense + targets:**
- A man defender whose man **holds the ball** plays **on-ball** (`_converge_xy`);
  otherwise he **denies ball-side** — on the **BH→man line at 60% from the BH**
  (`STRAIGHT_PRESSURE_DENY_FRACTION`). The on-ball role therefore *shifts to
  whichever defender's man receives a pass* — defenders never abandon their man to
  chase the ball.
- **Rover/trapper** continuously tracks the **live ball-handler** (`_converge_xy`).
- **Key defender** sits at the **key** (`HCO_STRING_SPOTS["key"]`, x=64), toggling
  to **upper wing** if BH `y > 28` / **lower wing** if BH `y < 22`; **but** he
  **mans up** on any offender **returning to the backcourt from the ABA** (this
  takes precedence, then follows normal sticky-man rules).

**Trap (re-introduced, rover-only):** moment detection allows a `trap` **only when
an active rover has reached the BH** (the rover is in `MOMENT_RANGE`); otherwise it
caps at `pressure`. With no rover, Straight Pressure never double-teams
(`trapper=None`, single-defender math). A real trap uses the Standard trapper
geometry + D8 contest math.

**Role transitions (man enters the ABA → release):** the freed defender fills the
first open role: **(1) rover** if none exists, else **(2) key** if none exists,
else **(3) wings** — the current key defender and the freed defender each take the
nearer of the two wing spots (future-proof; reachable e.g. after the original BH
passes and cuts to the ABA while a rover + key already exist).

**Inherited unchanged from Standard Trap:**
- def PF/C D22 ball-reactive ABA-zone coverage (`_pf_c_targets`).
- The §2 3-tier ABA read and the §7 HCO/Fast-Break transition once the ball reaches
  the ABA.
- Decision thresholds, movement rates/archetypes, broken-HCT cutoff, time terminals,
  stat parity, schema emission, possession flips.

**Implementation seams (the `HCTPlay` methods Straight Pressure overrides):**
- `begin_possession(...)` → returns a fresh stateful `StraightPressure` carrying the
  locked man-assignment / role state (`_straight_pressure_begin`); the registry
  singleton stays stateless. Standard's base returns `self`.
- `detect_moment(...)` → Standard detect, then `trap` → `pressure` **unless** an
  active rover is in range.
- `defense_targets(...)` → `_straight_pressure_targets` (sticky man deny/on-ball +
  rover + key/wing toggle + PF/C via `_pf_c_targets`); mutates the per-possession
  state for man→ABA role transitions. Standard inherits the base (`_defense_targets`).

## §14 — Pass Contests (interceptions & bat-out-of-bounds)

> **Status:** design spec (not yet built). A **universal** pass-contest primitive,
> prototyped first in the HCT pass branch (§6), then generalized to other pass paths.
> All passes are contestable; geometry makes the overwhelming majority complete cleanly.

### 14.0 — Why this is "true to the sim"

The sim already resolves a contested pass in exactly this shape — the **Rim Runner
lane pass** (`rim_runner_fast_break.py`): a geometry gate (perpendicular distance to
the pass line + a side gate) decides *who can* contest, an attribute roll decides
*whether/how*, and the outcome is **tiered** (steal / bat-OOB / completion). We also
already own an **arrival-time race solver** — the §5/D21 `_cutoff_meet_point` (walk
the path, find the first point a defender reaches no later than the mover) — and a
standardized **steal composite** (`_steal_credit_defender`: OD·0.4 + AG·0.4 + IQ·0.2).
Pass contests reuse these rather than inventing a parallel system.

### 14.1 — The primitive (contract)

```
resolve_pass_contest(passer, receiver_xy, ball_speed, candidate_defenders,
                     offense_modifier) → { outcome, deflector, contact_point }
    outcome ∈ {COMPLETE, INTERCEPT, BAT_OOB}
```

Pure & geometry-first (no Player/game dependency — caller adapts), so it is callable
from any pass path and trivially unit-testable. `passer` is a descriptor
`{xy, PS, CH, IQ}`; `ball_speed` is the pass rate (`PASS_GRID_PER_GAME_SEC`);
`offense_modifier` is the turn-type offense rating that feeds the **passer safety gate**
(§14.3). Resolution runs three stages in order — geometry gate → passer safety gate →
interception band — short-circuiting to `COMPLETE` as soon as any stage clears the pass.

### 14.2 — Stage 1: hybrid geometry gate (per candidate defender)

A defender is an **eligible** contester iff **both** hold:
1. **In the lane (spatial):** perpendicular distance from the defender to the
   passer→receiver segment ≤ `PASS_LANE_DIST` (start at **8** grid, the RR value).
   Prevents a far-but-fast defender from "teleport-stealing" purely on speed.
2. **Reachable in time (temporal):** walk the segment (the D21 method) — at sample
   point `s`, the ball arrives at `t_ball = (L·s)/ball_speed` and the defender at
   `t_def = dist(def, point)/ag_rate(def)`. The defender is eligible at the **first**
   `s` where `t_def − iq_headstart ≤ t_ball`. `iq_headstart` = anticipation, scaled
   from IQ up to `PASS_IQ_ANTICIPATION_MAX_SEC` (a smart defender jumps the lane).
   (Foot-speed `ag_rate` still drives this *physical* race — `CH` only enters the band.)

Among eligible defenders, the **contester** is the one whose contact occurs
**earliest along the flight** (smallest `s` → first hand on the ball). His
`contact_point` is that sampled point.

### 14.3 — Stage 2: passer safety gate (offense counter)

Only if a contester exists. A good passer can defuse the lurking defender entirely
(this **replaces** the old additive `off_modifier` on the band — the offensive counter
is now its own explicit roll, not a threshold nudge):

```
pass_score = (PS·0.6 + CH·0.2 + IQ·0.2) × random(1,6)        # the PASSER's attributes
if pass_score > PASS_SAFETY_BASE − offense_modifier:          # base 200
    → COMPLETE  (no interception in play)
```

`offense_modifier` is the **turn-type** offense rating, resolved by
`resolve_offense_pass_modifier(turn_type, off_team_attributes)`. A higher rating
**lowers** the bar the passer must clear, so good offenses complete more passes — the
offensive mirror of RR's *defensive* `fb_opp`:

| turn type | `team_attributes` key |
|---|---|
| `HCO` | `offensive_efficiency` |
| `HCT` | `pt_opp_modifier` |
| `FAST_BREAK` | `fb_efficiency` |
| all others | `offensive_efficiency` (fallback) |

### 14.3b — Stage 3: interception band (what happens)

Only if the passer fails the safety gate:

```
intercept_score = (OD·0.6 + CH·0.2 + IQ·0.2) × random(1,6)     # hands/awareness, not foot-speed
```

- `intercept_score > PASS_INTERCEPT_TIER_HI`  (250) → **INTERCEPT**
- `intercept_score > PASS_INTERCEPT_TIER_MID` (200) → **BAT_OOB**
- else                                              → **COMPLETE**

(The tiers are now fixed — all offensive influence lives in the §14.3 passer gate.)

### 14.4 — Stage 4: outcomes & consequences

| outcome | meaning | consequence |
|---|---|---|
| `COMPLETE` | clean catch (common) | existing behavior — receiver becomes BH and reads (§6) |
| `INTERCEPT` | clean pick | **STEAL** terminal; possession flips; seed the transition from `contact_point`; credit via `_steal_credit_defender` |
| `BAT_OOB` | knocked out of bounds | **DEAD BALL**; **offense retains** (matches Rim Runner) → `SIDE_INBOUND`; no possession flip |

`contact_point` is the agreed backend/frontend contact grid (generalize
`_compute_interception_contact_grid`).

### 14.5 — HCT wiring (the prototype)

In the §6 pass branch, after the receiver + `pass_seconds` are known, gather the five
defenders as candidates (geometry filters them; in Straight Pressure the man-defenders
sitting at **60% on the BH→man line are literally in the lane**, so interceptions
emerge from the man-to-man positioning, not a bolted-on roll). Run
`resolve_pass_contest` with the passer descriptor and `offense_modifier =
resolve_offense_pass_modifier("HCT", off_team.team_attributes)` (HCT → `pt_opp_modifier`):

- `COMPLETE` → unchanged (rate-limited close during flight + receiver read-and-react).
- `INTERCEPT` → `result_type="STEAL"`, `stealer = _steal_credit_defender(...)`,
  `steal_coords = contact_point`, seed the transition (same path as the existing HCT
  steal terminal). Recorded as an **HCT** turn (`current_turn="HCT"`, `HCT_*_D`).
- `BAT_OOB` → `result_type="DEAD BALL"`, `possession_flips=False`,
  `next_play_type="SIDE_INBOUND"`.

**Animation:** shorten the `_pass_segment` flight to `contact_point`; `INTERCEPT`
attaches the ball to the deflector; `BAT_OOB` sends it out of bounds — reusing the RR
interception / bat-OOB render vocabulary.

### 14.6 — Knobs to tune

- `PASS_LANE_DIST` (8) — spatial lane width.
- `PASS_IQ_ANTICIPATION_MAX_SEC` — how much IQ buys as a reaction head-start.
- Interception composite weights (OD 0.6 / CH 0.2 / IQ 0.2).
- Passer-safety composite weights (PS 0.6 / CH 0.2 / IQ 0.2) and `PASS_SAFETY_BASE` (200).
- `PASS_INTERCEPT_TIER_HI` (250) / `PASS_INTERCEPT_TIER_MID` (200) — set the
  steal/bat/complete mix once the passer fails the safety gate.

### 14.7 — Phasing

1. **Extract + unit-test** `resolve_pass_contest` (geometry first; band with injected RNG). *(this PR)*
2. Wire into the **HCT pass branch** (§14.5) — INTERCEPT + BAT_OOB terminals.
3. Generalize to HCO / inbound pass paths; optionally refactor Rim Runner onto the
   shared primitive (single source of truth).
4. Animation polish (contact grid + OOB).

### 14.8 — Open items

- `PASS_SAFETY_BASE` (200) and the `offense_modifier` scale — confirm efficiency/opp
  modifier magnitudes land the safe-pass rate where we want (tune in step 2).
- Whether `BAT_OOB` should ever be a turnover (clean knock) vs always offense-retains
  (current decision: **always offense-retains**, per RR parity).
- A future 4th outcome — **tipped-but-live** (deflection that starts a scramble rather
  than a dead ball) — deferred.