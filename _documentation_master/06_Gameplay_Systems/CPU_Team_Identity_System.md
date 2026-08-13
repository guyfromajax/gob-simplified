# CPU Team Identity System ✅ **SHIPPED** (August 2026)

> ⚠️ **CALIBRATION PENDING RE-MEASUREMENT (post-recal, 2026-08).** The frozen constants here —
> `SIGNAL_SCALE`, the `STARTER_STRENGTH_MEAN` residualisation and its slopes, and the fuel-budget
> terciles (`< 30.3209` / `30.3209–35.7506` / `>= 35.7506`) — were fitted against the **pre-recalibration**
> attribute distribution. After the Player Attribute Recalibration (new RT formula, pool remap, −2
> height shift, regenerated attributes) these means/sds/quantiles no longer sit at their intended
> population points. The mechanism is unchanged; the **numbers need re-fitting** against the current
> 128-team distribution. Treat the specific constants below as stale until re-measured.

Describes what is **IN THE CODE**, not what was designed. Where something was designed,
measured and rejected, that is stated as such.

> **NAMING — do not conflate with Coaching Archetypes.**
> This document covers **CPU team identity**: a per-team *vision pair* that drives a CPU team's
> strategy sliders. It is a property of the 127 CPU teams in a franchise.
> [`02_User_Account_Systems/Coaching_Archetype_System.md`](../02_User_Account_Systems/Coaching_Archetype_System.md)
> covers the **user's coaching archetype**: a classification of the human player's own behaviour,
> stored on the `users` doc and surfaced as a badge. Different subjects, different storage,
> different lifecycle. The word "archetype" belongs to the user concept; "identity" to the CPU one.

---

## Why it exists

The previous CPU derivation used per-slider `_strategy_roll_*` thresholds that were **dead in
practice**: the `cum_nd > 350` gate matched **0 of 128 teams**, so the branch that raised
press/trap never fired, and **89% of the league fell through to one low-variance roll**. Every
CPU team played essentially the same way.

Identity replaces that. It derives eight frozen-scale signals from a team's projected starting
five, scores ten visions against them, picks an affordable pair, and draws the sliders from that
pair's weight tables.

---

## Implementation map

| Piece | Location |
|---|---|
| Signals, vision scoring, selection, slider draw | `BackEnd/utils/team_identity.py` |
| Franchise persistence + assignment | `BackEnd/utils/franchise_identity.py` |
| Assignment call site | `complete_week` in `BackEnd/api/franchise_routes.py` |
| Single-game path | `TeamManager.__init__` (`else` branch when no `strategy_settings` supplied) |
| Self-regulation override | `_apply_self_regulation_override` in `BackEnd/utils/db_utils.py` |
| Gate / verification | `scripts/eog_gate_check.py` |

---

## 1. Signals

Computed from the **projected starting five** (`projected_starting_five` — greedy best
(player, open position) by `position_ratings`, the same five the Scouting Report uses).

| signal | definition | note |
|---|---|---|
| `fuel` | `min(ND)` over the five | **weakest link** — pressing is limited by the tiredest starter |
| `athleticism` | `p20(AG + ST)` | order statistic, not a sum |
| `intelligence` | `min(IQ)` | weakest link |
| `tempo_tilt` | `ΣOD − ΣSC` | NOT residualised — the shared AG term cancels, so it is confound-free |
| `scoring_tilt` | `ΣSH − ΣSC`, orthogonalised on `tempo_tilt` | |
| `inside_peak` | `peak(SC)` | residualised on strength, deliberately NOT orthogonalised on tempo_tilt |
| `attack_peak` | `peak(SC + AG)`, orthogonalised on `inside_peak` | |
| `breadth` | `−(max(SH) / ΣSH)` | negative so higher = more spread out |
| `multiple_signal` | `min(z_athleticism, z_intelligence)`, then standardised again | the second standardisation is load-bearing — without it the signal sits ~0.5 sd below the sum-based visions and can never win |

**All are FROZEN z-scores** against `SIGNAL_SCALE` (measured means/sds), not recomputed per
league. A league that trains up genuinely gains capability rather than being renormalised back
to the middle. Drift against the frozen scale is *signal*, not noise.

**Residualisation on starter strength.** `fuel`, `athleticism`, `intelligence`, `inside_peak`
and `attack_peak` are corrected for how strong the five is:
`residual = raw − SLOPE × (strength − STARTER_STRENGTH_MEAN)`.

⚠️ **The slopes differ by 3.3x and that has visible consequences.** `athleticism` carries slope
**0.2479** against `intelligence`'s **0.0749**, so a *stronger* five is penalised far harder on
athleticism than on IQ. A measured example: a franchise whose fives were 12.7 strength points
stronger showed intelligence **+0.30 sd** and athleticism **−0.23 sd** even though BOTH raw
signals had risen — the correction, not the roster, produced the apparent "smart but unathletic"
league. If a population's vision mix looks strange, check starter strength before concluding
anything about composition.

---

## 2. Vision scoring and selection

Ten visions — five offensive, five defensive.

| offensive | weights |
|---|---|
| Run and Gun | `fuel 2.0, tempo_tilt −1.0, breadth 0.5` |
| Spread | `scoring_tilt 2.0, inside_peak −0.5, breadth 1.5` |
| Inside-Out | `scoring_tilt −1.0, inside_peak 2.0, breadth −1.0` |
| Attack | `fuel 0.5, tempo_tilt −0.5, attack_peak 2.0, breadth 0.5` |
| **Motion** | **flat 0.60** |

| defensive | weights |
|---|---|
| Full-Court Press | `fuel 2.0, athleticism 1.5, tempo_tilt 1.0` |
| Man Lockdown | `fuel 0.5, athleticism 2.0` |
| Zone | `fuel −0.5, intelligence 2.0` |
| Multiple | `multiple_signal 2.0` |
| **Contain** | **flat −0.50** |

**Fuel budget.** Each vision costs 0-2; a team can afford pairs summing to its capacity.

| | cost | | capacity | residualised `fuel` |
|---|---|---|---|---|
| Run and Gun, Full-Court Press | 2 | low | 1 | `< 30.3209` |
| Attack, Motion, Man Lockdown, Multiple | 1 | mid | 2 | `30.3209 – 35.7506` |
| Spread, Inside-Out, Zone, Contain | 0 | high | 4 | `>= 35.7506` |

Bounds are **FROZEN terciles**, not recomputed per league — same reasoning as the scale.

**Selection** is a softmax over affordable *pairs* at **T = 0.5**, on the summed offensive +
defensive score.

⚠️ **Vision counts are NOT independent observations.** Two structural reasons:
1. **Flat-score visions are relative absorbers.** Motion (0.60) and Contain (−0.50) cannot move,
   so they gain share whenever the scored field weakens and lose it when it strengthens. Motion
   rose 10 → 17 teams in one measured comparison purely because Spread fell 0.53.
2. **Softmax relativity.** A vision's own score can be unchanged while its share collapses.
   Multiple's score moved −0.025 and it lost 12 teams, because Zone rose +0.479 and the gap
   widened from 0.167 to 0.671 — at T = 0.5 that is a ~2.7x odds shift.

Do not read a vision-count change as a statement about that vision.

### Measured population split (2026-08-12)

Dry-run over a live 128-team franchise on `gob-staging` (franchise `6a7c5a00…f5f29`, week 15,
post-recalibration pool). All 128 teams resolved a five; `no_five = 0`, 1,536/1,536 roster
players matched in FPD.

| Offensive vision | Teams | | Defensive vision | Teams |
|---|---:|---|---|---:|
| Inside-Out | **98 (77%)** | | Zone | **69 (54%)** |
| Motion | 10 | | Contain | 39 |
| Run and Gun | 10 | | Full-Court Press | 16 |
| Spread | 6 | | Multiple | 3 |
| Attack | 4 | | Man Lockdown | 1 |

Resulting slider spread — the quantity the inertness gate checks:

| Slider | distinct | variance | range |
|---|---:|---:|---|
| `aggression` | 5 | 1.046 | 0–4 |
| `hc_trap` | 5 | 1.025 | 0–4 |
| `fc_press` | 5 | 1.361 | 0–4 |
| `tempo` | 5 | 0.799 | 0–4 |
| `inside` | 4 | 0.689 | 1–4 |
| `outside` | 5 | 0.578 | 0–4 |

⚠️ **The offensive split is heavily concentrated and has NOT been validated.** 77% on one
vision may be correct — a post-recalibration pool of similar rosters will concentrate under
softmax — or it may mean the offensive fit function is under-discriminating on this pool. The
frozen scale constants in §1 were measured **before** the attribute recalibration and the
second −2in height shift, so the z-scores feeding selection are being taken against a pool
that has since moved.

Per `cpu_team_identity_spec.md` §9, **this cannot be settled distributionally** — different
aggregation forms produce near-identical population splits while disagreeing about a third of
the teams. Validation is downstream: do press-identity teams actually press effectively, and
do outside-identity teams out-shoot the league? Treat the table above as a baseline to detect
drift against, not as evidence the fit function is right.

---

## 3. Slider draw

Each vision names only the sliders it cares about, as weights over values `[0,1,2,3,4]`.

**Any slider a vision does NOT name draws from its own LEAGUE BASELINE, never a generic
neutral.** `hc_trap` / `fc_press` baseline at `[34,40,20,5,1]` (mean 0.99); handing them a
generic 2.0 would roughly **double league-wide pressing** as a side effect of wiring identity.

Tables live in `team_identity.OFFENSIVE_SLIDERS` / `DEFENSIVE_SLIDERS` / `LEAGUE_BASELINE`.

### Scale semantics — CONFIRMED (2026-08-12)

The two axis sliders are **play-type mixes**, not intensities. Each value is a literal ratio:

| value | `offense` (motion ↔ set play) | `defense` (man ↔ zone) |
|---|---|---|
| 0 | 100% motion | 100% man |
| 1 | 75/25 motion | 75/25 man |
| 2 | 50/50 | 50/50 |
| 3 | 75/25 set plays | 75/25 zone |
| 4 | 100% set plays | 100% zone |

Verified against every vector: Motion draws mean **1.45**, Spread 1.25, Run and Gun 1.05
(all motion-leaning); Inside-Out **2.75** and Attack 1.75 lean set-play. Man Lockdown draws
**0.50**, Zone **3.05**, Multiple 2.00 wide, Contain 1.65. Full-Court Press **does not name
`defense`** — press is orthogonal to the man/zone axis and is expressed through `fc_press`.

Because the scale is a ratio and not a preference, **a slider mean is directly readable as a
league play-type mix** — `defense` mean 2.0 across the league means half of all defensive
possessions are zone.

Measured means actually drawn, by vision:

| defensive vision | `fc_press` | `hc_trap` | `aggression` |
|---|---|---|---|
| Full-Court Press | 2.90 | 2.74 | 3.16 |
| Man Lockdown | 0.91 | 0.70 | 2.22 |
| Multiple | 0.76 | 0.76 | 2.29 |
| Zone | 0.78 | 1.11 | 1.54 |
| Contain | 0.50 | 0.85 | 0.85 |

---

## 4. Persistence — `ftd.identity`

Identity is **season-scoped state**, stored on each franchise team-data document.

```
identity: {
  offensive_vision   str
  defensive_vision   str
  assigned_season    int
  assigned_week      int
  fuel_capacity      int
  signals            {signal: z-score}
  scores             {"offense": {vision: score}, "defense": {vision: score}}
  constants_version  int
}
```

`ftd.strategy_settings` is overwritten with the derived draw at the same time. **Storing the
pair AND the sliders is deliberate** — the deferred five-week re-evaluation needs to read the
vision that produced them.

**Assignment is SEASON-KEYED**, which covers every trigger with one mechanism:

* no `identity` sub-document → assign (franchise creation)
* `assigned_season` != current season → reassign (attributes reset and rosters turn over)
* `constants_version` != `team_identity.CONSTANTS_VERSION` → reassign

Otherwise a no-op, so it is safe on a hot path.

⚠️ **It runs from `complete_week`, not from franchise creation.** Creation seeds FTD documents
**before rosters are attached** (`ensure_team_objects_exist` writes `strategy_settings` with no
`players` key), so there is no five to project. `complete_week` is the first point each season
where a roster is guaranteed. The call is wrapped so identity can never block a week.

⚠️ **Two id-shape traps.** `franchise_id` is an **ObjectId on FTD** but a **string on FPD**.
Querying FPD with the ObjectId returns zero documents *silently*, which presents as "no five
could be resolved" for all 128 teams rather than as an error. Both queries match either form.

---

## 5. Why identity was inert in franchise mode for its first version

`TeamManager.__init__` only runs the assignment when **no** `strategy_settings` are supplied.
In franchise they are **always** supplied — creation seeds every FTD with a flat-neutral all-2s
dict, which `prepare_ftd_for_new_game` passes straight into the constructor. The identity branch
never executed, and all 128 teams played with identical sliders.

**It was caught by a measurement gate, not by reading the code** — a week-1 capture showed
`aggression = hc_trap = fc_press = offense = tempo = 2` on every team, zero variance, no visions.
The data-shape checks all passed while the treatment was completely inactive.

The fix was not to change the constructor: FTD now supplies identity-derived settings, so the
existing branch does the right thing unchanged.

**`scripts/eog_gate_check.py` exists because of this.** It asserts the treatment, not just the
data: every team carries a persisted identity, and sliders **vary** across the league. Zero
variance on `aggression` / `hc_trap` / `fc_press` exits non-zero.

### It then went inert a SECOND time, by a different route (found 2026-08-12)

The fix above was correct and still is. It was attached to the wrong place.

`ensure_franchise_identities` was called from the `/franchise/complete-week` route only. But
**three** endpoints reach the CPU sim block, and the live UI takes the other two:

| Endpoint | Called by | Assigned identity? |
|---|---|---|
| `/complete-week` | `box-score.js` fallback branch only | ✅ |
| `/complete-week/start-cpu-sims` | `franchiseStartCpuSimsClient.js` | ❌ |
| `/complete-week/phase-b` | `franchisePhaseBClient.js` | ❌ |

So identity never ran in normal play. `gob-staging` carried **0/128 teams with an identity and
every slider flat at 2**, on a franchise created two days *after* identity shipped, on a build
containing it.

**The fix: assign at `_complete_week_finish_cpu_and_persist`**, the single function all three
entry points converge on, ahead of the sim block. A per-route call is what made this
reintroducible; the choke point makes it unreachable by construction.

**The lesson is about verification, not about routing.** The gate that catches this exists and
has existed since the first incident — `franchise_identity_summary` reported
`teams_with_identity: 0` the moment it was asked. Nobody asked. A gate is only a control if
something runs it; **run `scripts/eog_gate_check.py` after any change to the complete-week
call graph**, and treat "identity is documented as shipped" as an unverified claim until it
does.

⚠️ **Consequence for anything calibrated during the gap.** The EOG attribute bands were re-cut
against an identity-**ON** measurement season (harnesses call identity directly, so the gate
passed there) while live franchise play ran identity-**OFF**. Live play was therefore scoring
~4.4% below the league the bands assume. Re-check the bands against an identity-ON franchise
season before treating them as tuned.

---

## 6. Self-regulation override (foul trouble + fatigue)

A press team backs off when its guards are in trouble, the way a real one does. Sits on the
`strategy_settings_base` seam beside the sit-on-the-lead override, so it **reverts** the moment
the trouble clears.

**Complements the per-quarter foul limits rather than duplicating them.** Those are a
**PERSONNEL** lever evaluated only at rebuild boundaries; this is a **TACTICS** lever. And the
limits are switched off entirely in the final 4:00 of Q4 and all OT — where **39% of foul-outs
occur** — so there, this is the only brake that exists.

**Triggers**

* **Foul trouble** — clock-aware "on pace to foul out": `fouls > 5 × elapsed_fraction`, minimum
  2 fouls, counted **roster-wide** (a player benched at four fouls is the asset being protected).
  **Plus an absolute 4-foul floor applied ON-FLOOR ONLY.** The floor is load-bearing: by late Q4
  the pace line reaches ~4.7, so a player sitting on 4 would otherwise score as not-in-trouble
  exactly where it matters most. A benched four-foul player is not at imminent risk — that is
  what benching him accomplished.
  `severity = min(1, trouble_count / 3)`
* **Fatigue** — roster fraction below the NG eligibility floor, ramping 0.33 → 0.66. Same
  currency the lineup gate uses, so both agree about what "tired" means.
  The mechanism is real: `resolve_full_court_press_logic` and `resolve_half_court_trap_logic`
  call `apply_energy_decay(..., omit_zeros_for_defense=True)`, which strips the zero entries
  from a defender's decay list. Measured **1.30x** NG burn per defender-event on pressure turns;
  press teams take 18.5 pressure turns a game against Contain's 4.5.

**Response** — damp `aggression` / `hc_trap` / `fc_press` **proportionally toward the league
baseline mean**, never to a fixed value and never to zero. A press team backs off to roughly
average; it does not stop being a press team.

| | `aggression` | `hc_trap` | `fc_press` |
|---|---|---|---|
| weight from foul trouble | 1.00 | 0.50 | 0.50 |
| weight from fatigue | 0.40 | 0.80 | 0.80 |
| damp target (league baseline mean) | 2.00 | 0.99 | 0.99 |

**Deterministic — no RNG draw**, deliberately unlike the conservative override's
`random.choices`. This is a continuous response to a continuous state; a draw would make
behaviour jitter between stoppages, and it keeps the sim's draw count unchanged.

**Composition**

* **Conservative wins.** If `_conservative_strategy_active` (sit-on-the-lead), self-regulation
  is skipped entirely — both target the same three sliders and conservative damps harder.
* **Trailing late suppresses it.** Down `>= 6` in the final 5:00 of Q4, or at any point in OT,
  self-regulation is skipped: a team down two possessions should keep pressing despite foul
  trouble. Suppression, not inversion — raising sliders *above* the identity base is new
  behaviour belonging to the deferred mid-game adjustment layer.

**Cadence.** `autoset_strategy_settings` is only called at quarter breaks, timeouts and
foul-outs (~8.9 times per team-game). **The team will not back off mid-possession**, only at the
next stoppage.

**Measured behavioural result** (FCP teams, identity base → effective):

| slider | base when in trouble | effective in trouble | effective when clear |
|---|---|---|---|
| `aggression` | 2.86 | **2.56** | 2.86 |
| `hc_trap` | 2.69 | **2.16** | 2.91 |
| `fc_press` | 2.84 | **2.25** | 2.70 |

Replicates across pinned hash worlds. Scoring holds.

⚠️ **Open concern:** ~65-69% of FCP rebuilds register as in-trouble, against the 51% the
calibration predicted (the absolute-4 floor added the difference). The identity may be damped
too much of the time. Levers: `SELF_REG_FOUL_MIN`, the pace multiplier, or requiring the
4-foul player to be on the floor for the pace test too.

---

## 7. What identity does and does not change

Measured OFF vs ON, mean of two pinned hash worlds, 96 team-games each:

| metric | OFF | ON | Δ |
|---|---|---|---|
| points / team-game | 67.91 | 70.92 | **+4.4%** |
| possessions / team-game | 70.01 | 71.92 | +2.7% |
| PPP | 0.970 | 0.986 | +1.7% |
| fouls / team-game | 19.28 | 20.98 | +8.8% |
| foul-outs / team-game | 0.59 | 0.72 | +22.0% |

**Identity raises scoring ~3 points/team-game, and it is BOTH pace and efficiency**, roughly
evenly split. Both hash worlds agree on direction and magnitude.

**Foul concentration by vision** (identity ON): Full-Court Press **1.000** foul-outs/tg and
**24.46** fouls/tg, against Zone 0.434 / 19.30 and Contain 0.433 / 18.30. Press teams commit
clearly the most fouls and disqualify players ~2.3x as often as the passive visions.

The league-wide foul-out rate is already 0.59/tg with identity **OFF** against a real-basketball
~0.2-0.4. **That is a pre-existing calibration issue identity did not cause**, and it is the
larger number.

---

## 8. Measured and rejected

| | why |
|---|---|
| **Damping FCP aggression** (3.05 → 2.50) | Appeared to cut FCP foul-outs 1.308 → 0.808, but that was a **cross-hash-world artifact**. Under controlled comparison no lever moved foul-outs detectably — between-world spread on an unchanged arm (0.81 → 1.19) exceeded every between-arm difference. |
| **Tighter per-quarter foul limits** (`{1:1,2:2,3:2,4:3}`) | Cut Q3 foul-outs 14 → 6 but pushed Q4 up 21 → 25 — the same players foul out, later. Press concentration got *worse* (3.6x), and the waterfall fired on 20% of rebuilds versus 12.9%. The limits cannot reach a problem that lives in Q4. |

---

## 9. Tunable Constants

| constant | location | value | effect |
|---|---|---|---|
| `SIGNAL_SCALE` | `team_identity.py` | frozen means/sds | z-score basis; drift against it is signal |
| `RESIDUAL_SLOPE_VS_STRENGTH` | `team_identity.py` | fuel .1037 / ath .2479 / iq .0749 / inside .4065 / attack .7377 | strength correction; the ath-vs-iq ratio is why strong fives read as "smart" |
| `FUEL_CAPACITY_BOUNDS` | `team_identity.py` | `(30.3209, 35.7506)` | frozen terciles → capacity 1 / 2 / 4 |
| `VISION_COST` | `team_identity.py` | 0-2 per vision | affordability filter |
| `SOFTMAX_TEMPERATURE` | `team_identity.py` | `0.5` | selection sharpness; lower = more deterministic |
| `MOTION_FLAT` / `CONTAIN_FLAT` | `team_identity.py` | `0.60` / `-0.50` | flat scores — these are the relative absorbers |
| `CONSTANTS_VERSION` | `team_identity.py` | `1` | bump when any of the above change; forces reassignment |
| `SELF_REG_FOUL_PACE_MULT` | `db_utils.py` | `5.0` | fouls-vs-elapsed slope |
| `SELF_REG_FOUL_MIN` / `_ABS` | `db_utils.py` | `2` / `4` | min fouls to count; absolute floor (on-floor only) |
| `SELF_REG_FOUL_FULL_COUNT` | `db_utils.py` | `3` | players in trouble for full severity |
| `SELF_REG_NG_FLOOR_FRAC` / `_FULL_FRAC` | `db_utils.py` | `0.33` / `0.66` | fatigue ramp |
| `SELF_REG_WEIGHTS_FOUL` / `_FATIGUE` | `db_utils.py` | see §6 | per-slider damp weights |
| `SELF_REG_TARGETS` | `db_utils.py` | `2.00 / 0.99 / 0.99` | damp floor = league baseline means |
| `SELF_REG_DESPERATION_SECONDS` / `_MARGIN` | `db_utils.py` | `300` / `6` | trailing-late suppression |

### Slider draw vectors — CONFIRMED AS INTENDED (2026-08-12)

`OFFENSIVE_SLIDERS`, `DEFENSIVE_SLIDERS` and `LEAGUE_BASELINE` in `team_identity.py` are weight
vectors over values `[0,1,2,3,4]`. They were originally authored as a proposal ("§4 is my
proposal, not measured" — `cpu_team_identity_spec.md`). **Reviewed and accepted 2026-08-12** as
the play-type mixes they produce:

| Offensive vision | mean `offense` | mix |
|---|---:|---|
| Run and Gun | 1.05 | 74% motion / 26% set |
| Spread | 1.25 | 69% / 31% |
| Motion | 1.45 | 64% / 36% |
| Attack | 1.75 | 56% / 44% |
| Inside-Out | 2.75 | 31% motion / **69% set** |

| Defensive vision | mean `defense` | mix |
|---|---:|---|
| Man Lockdown | 0.50 | 88% man / 12% zone |
| Contain | 1.65 | 59% / 41% |
| Multiple | 2.00 | 50/50 (deliberately wide — width IS the identity) |
| Full-Court Press | 2.00 | 50/50 — **does not name `defense`**; press is orthogonal, expressed via `fc_press` |
| Zone | 3.05 | 24% man / **76% zone** |

⚠️ **The "Motion" vision is only the third-most motion-heavy**, behind Run and Gun (74%) and
Spread (69%). This was surfaced at review and **accepted as intended** — the vision names an
offensive *philosophy*, not a possession-type maximum. Do not "correct" the ordering without
an explicit decision; it looks like a bug and is not one.

### Playbook concentration ceiling — 25%, NOT to be lifted (2026-08-12)

`cpu_team_identity_spec.md` §5 called for the concentration caps to be **raised** so Inside-Out
and Attack could funnel harder. **That proposal is REJECTED.** The intended ceiling for a single
play's share of a normal playbook is **25%**.

The ceiling is not a constant — it is a schedule in `_set_play_percentages`
(`cpu_playbook_customization.py`), and it depends on how many set plays the book holds:

| set plays in book | top play share |
|---|---:|
| 1 | 100% |
| 2 | 55% |
| 3 | 45% |
| **4+ (normal)** | **20%** |

So the 25% ceiling binds only for 4+ play books; **a book with 1–3 plays structurally exceeds it**
and no cap can prevent that (three shares cannot each be ≤25% and sum to 100). `_random_capped_three`
separately caps each of three family shares at `max_pct=50`.

**Consequence accepted:** Inside-Out's spec design — concentrated personnel fed through diverse
actions — stays expressible on the *personnel* axis but not as extreme play funneling. The EOG
concentration penalty continues to apply, so specialization remains a real cost.

---

## 10. Open items

* **Vision-driven training allocation is DEFERRED.** The CPU reference plan is uniform across
  all 127 teams, so team-attribute drills are identical league-wide. Nothing yet tests forced
  specialisation on the training side.
* **Five-week re-evaluation is DEFERRED.** The persistence schema stores what it would need.
* **`play_calling` is a dead ghost setting** — drawn, never consumed.
* **Self-regulation fires on ~two-thirds of FCP rebuilds** (§6).
* **Single-mode measurements do not describe franchise.** Everything in §7 was measured in
  `mode="single"`. A fresh franchise matches single-mode closely at week 1 (all signals within
  ±0.05 sd), but the populations diverge as a season runs.

### Decisions taken 2026-08-12 — CLOSED, do not re-litigate

| # | Question | Decision |
|---|---|---|
| 1 | Slider scale semantics | **Ratios, confirmed.** `offense` 0=100% motion → 4=100% set plays; `defense` 0=100% man → 4=100% zone; 1/3 are 75/25 splits, 2 is 50/50. Code already matched. See §3. |
| 2 | Slider weight vectors | **Accepted as authored**, including the Motion-ordering quirk. See §9. |
| 3 | Playbook concentration caps | **Stay at 25%**; spec §5's "lift the caps" is rejected. See §9. |
| 4 | Backup-quality bar for rotation size | **Within-team comparison**, not an absolute RT bar. See below. |
| 5 | Do user teams get an identity? | **No.** The user sets their own sliders; an auto-assigned identity would fight them. |

**#4 in detail.** Rotation size counts "how many bench players are good enough to play." The
spec's `RT ≥ 50` is an **absolute** bar and does not survive a pool change — the spec itself
warns a pool migration moved the bench median 5 points and emptied the deep band. Since then the
attribute recalibration and a second −2in height shift both landed, so the bar is already stale.

**Replace it with a within-team difference: how many bench players are within X of the starter
they would replace.** A gap between two players on the same roster is invariant to any
recalibration; an absolute threshold is not. This is the same failure mode as the frozen
`SIGNAL_SCALE` constants in §1 — record it once, apply it everywhere.

**Cadence: re-derive every five weeks, aligned to the §8 identity re-evaluation.** Weekly was
considered and rejected: it creates a second cadence to reason about for no benefit, since the
bar moves on roster composition (recruiting, redshirts, transfers), not on week-to-week fatigue.
One clock for identity and its dependent surfaces.

⚠️ Rotation size is **not built** — no `rotation_size` exists anywhere in `BackEnd/`. This
decision is recorded for whoever builds it.

## Related docs

* [`02_User_Account_Systems/Coaching_Archetype_System.md`](../02_User_Account_Systems/Coaching_Archetype_System.md) — the USER's coaching archetype. **Different concept, see the naming note at the top.**
* [`04_Franchise_Mode_Systems/Team_Attribute_System.md`](../04_Franchise_Mode_Systems/Team_Attribute_System.md) — ranges, inits, drift
* [`06_Gameplay_Systems/CPU_Team_Rotation_System.md`](./CPU_Team_Rotation_System.md) — lineup selection and the NG gate
* [`06_Gameplay_Systems/End_Of_Game_System.md`](./End_Of_Game_System.md) — the EOG bands identity feeds
