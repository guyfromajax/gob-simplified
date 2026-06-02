This doc summarizes the steps and potential steps that are part of each Turn Type.

**Opening Tip**
Step 1: Jump Ball (required)
Step 2: Resolution (required)

**BIP**
Step 1: BIP Alignment (required)
-if Fast Break: all players move at sprint
-else: all players move at cruise
Step 2: Inbound Pass (required)

**SIP**
Step 1: SIP Alignment (required)
Step 2: Inbound Pass (required)

**HCO**
Step 1: Handoff (conditional)
Step 2: Walk Up (required / conditional?)
Steps 1-3+: Animation Skeleton (required)

##Handoff Step
-Handoff Step Occurs if:
    -if this is the first step of an HCO turn
    -AND BH != Step 0 skeleton BH 
    -AND bh starting x coord < 71 (home offense) or > 29 (away offense)
- If the BH is the PG, in lieu of the pass sub-step, the PG will hold his place while the other 9 players are moving into position for an amount of time dependent on the offense team's current tempo setting:
    -fast = 1 game second
    -normal = 2 game seconds
    -slow = 3 game seconds
    -fallback = 2 game seconds
-If the BH is not the PG, PG moves into position to receive the pass, BH remains stationary, and the other 8 players move up the court

##Kickout Step
-Kickout Step Occurs if:
    -if this is the first step of an HCO turn
    -AND BH != Step 0 skeleton BH 
    -AND bh starting x coord >= 71 (home offense) or <= 29 (away offense)
-Execute current OREB Kickout Step exactly as it is currenlty coded.

##Walk Up Step
-Walk Up Step Occurs if: 
    -AND bh starting x coord < 71 (home offense) or > 29 (away offense)
- BH: cruise speed
- Other 9 players: sprint speed

##Other Steps
-Skeleton (pass, stopper, shoot, movement, hold)
-Ball flight (shot only) — variant-aware end coord; `sfx_on_ball_release` (tiered launch) + `sfx_on_ball_arrival` (variant result)
-Variant intermediate (rattle hops, bank-make settle, bank-miss graze, airball OOB continuation)
-Rim hold (makes)
-Bounce (miss; skipped for AIRBALL)
-Rebound/Get Back/Release: overlay motion threaded across shoot + ball flight + variant + hold or bounce

##Post-Shot Variant Chain ([SFX_System.md](../05_Features/SFX_System.md))
| Variant | Flight end | Intermediate | Terminal | SFX |
|---|---|---|---|---|
| SWISH (make) | MSSS | — | hold | `swish.wav` arrival |
| CLANK (miss) | rim | — | bounce | `clank.wav` arrival |
| BACK_OF_RIM make | MSSS | — | hold | `back-of-rim.wav` arrival + `swish.wav` @ +150 ms timed |
| BACK_OF_RIM miss | rim | — | bounce | `back-of-rim.wav` arrival |
| RATTLE_* make | MSSS or rim | N hops + settle to MSSS | hold | per-hop `rattle-leather.wav` release + settle `swish.wav` arrival |
| RATTLE_* miss | MSSS or rim | N hops | bounce | per-hop `rattle-leather.wav` release |
| BANK_MAKE | bank point | settle bank→MSSS | hold | `bb-rim-swish.wav` arrival + `swish.wav` @ +100 ms timed |
| BANK_MISS | bank point | graze bank→rim-graze | bounce | `bb-clank{,-2}.wav` arrival (50/50 backend-rolled) |
| AIRBALL | 2-short of MSSS | OOB continuation → resting | — (no bounce) | `airball.wav` arrival |

##Advance Triggers
-Handoff — player_reaches_position (PG converge) + ball_reaches_player (inbound pass sub-step)
-Kickout — player_reaches_position (positioning) + ball_reaches_player (pass sub-step)
-Walk Up — player_reaches_position (gate player(s) reach their destination)
-Skeleton step (regular movement) — player_reaches_position (slowest **offensive** mover reaches destination)
-Pass step (skeleton w/ ownership transfer) — player_reaches_position (slowest offensive mover, or ball_reaches_player when pass flight gates step T)
-Stopper step (FCP foul/steal/turnover truncation) — player_reaches_position (players involved in stop action)
-Shoot — player_reaches_position (gate switches to shooter reaching shot spot)
-Ball flight — shot_resolved (ball reaches rim/sweet spot)
-Hold (1000ms make) — fixed_duration (T=0 game-sec; announcement hold drives wall-clock)
-Bounce (miss/block) — fixed_duration (T = 300ms wall-clock)

**HCT**
Step 1: Walk Up (required)
Steps 2+: HCT Dynamic Execution (required)

**FCP**
Steps 1+: FCP Skeleton Execution (required)

**OREB**
Step 1: Rebound Capture (captor → bounce; attemptors → bounce ±4x/±6y)
Step 2: Kickout
Step 2A: Kickout Positioning
Step 3: Putback Attempt
Step 4: Ball Flight
Step 5: Bounce (miss/block) or hold (make)

**DREB**
Step 1: Rebound Capture (captor → bounce; attemptors → bounce ±4x/±6y)
If OTB fires on the defensive rebound battle, Step 1 still completes the rebound capture and ball attach, then emits `"Over The Back!"` and `turn_stop: FOUL`. SIP/free-throw continuation is produced by the backend's standard non-shooting foul progression, not by frontend inference.


**Free Throw** (one attempt per turn; `ft_step_emitter`)

Step 1: Lane setup (shooter → line; lane players → FT spots; gate = shooter)

Step 2: Shoot (shooter `shoot` / `shot_motion`; ball attached)

Step 3: Ball flight (`FREE_THROW_SHOT_GRID_PER_GAME_SECOND` = 12; SFX `free-throw-swish.wav` / `free-throw-miss.wav`)

Step 4a: Hold (make) 
    -if this is the final FT, transition to BIP via our standard made shot to BIP transition process
    -if this is not the final FT, hold for 1000ms the teleport the ball to teh free throw shooter (note this is a rare excetion where a ball teleport is acceptable)

Step 4b: Rim beat + bounce to `ball_bounce_x/y` (miss)
    -if this is the final FT, calcualte OREB or DREB and execture the reboudn step via our standard process. Final miss → discrete **DREB** or **OREB** turn (not embedded on FT row)
    -if this is not the final FT, hold the ball at the bounce spot for 1000ms then teleport the ball to the FT shooter (note this is a rare excetion where a ball teleport is acceptable)
    -also ensure that the bounce spot for either use case (final FT or not final FT) is determined via our standard random logic for missed shots.

**Fast Breaks** (schema playback via `animation_steps`; `after_steal` still on legacy `fastBreak.js`)

All three migrated FB emitters route MAKE/MISS/BLOCK shot outcomes through skeleton's `_build_post_shot_sub_steps` (`skeleton_step_emitter.py:1988`), which appends the same post-shot chain as HCO (ball_flight → variant → hold/bounce) and sets `schema_rendered_arc=True` on the terminal `SHOT_ATTEMPT` turn_stop. Non-shot branches (steal / bat OOB / hold-up / outlet-denied / defensive-stop) terminate without that chain. See HCO §Post-Shot Variant Chain for the shared sub-step table.

## Covert Release (`covert_release_step_emitter`)

Step 1: Outlet pass (skipped if rebounder == outlet receiver)
- AT: `ball_reaches_player` (receiver)
- Outlet passer + receiver stationary; get-back defenders execute "read on outlet pass" positioning (see [Fast_Break_System.md](../05_GP_Supporting_Systems/Fast_Break_System.md) §Get-back defender read)

Step 2: Outcome branch keyed off `result_type`

| `result_type` | Sub-steps appended | Turn_stop | `schema_rendered_arc` |
|---|---|---|---|
| MAKE / MISS / BLOCK | Shoot motion → **[skeleton post-shot chain]** | `SHOT_ATTEMPT` | ✓ |
| DEFENSIVE_STOP | Confrontation step (BH + stopper) | implicit end → next HCO | ✗ |
| FOUL | Stopper step | `FOUL` | ✗ |
| STEAL | Outlet contest stop | `STEAL` | ✗ |

### CR Defensive Stop sub-step logic
- **Viability:** 
  - Geography: Each defender is checked against the ball handler at outlet position. A defender is "viable" as a stopper only if both are true:
    -Defender is ahead of ball handler on x grid
    -Defender is within +- 8 y grid spots of ball handler
    -if either of these is not true, the defender becomes a race defender
  - Defense Team Aggression Setting
    - Aggressive: 100% chance defender will attempt stop if he passes geography check
    - Normal: 50% chance defender will attempt stop if he passes geography check
    - Passive: 0% chance defender will attempt stop if he passes geography check
    - if defender does not attempt a stop, he becomes a race defender
- **Skill Check**
  - break_score = (ball_handler.AG + ball_handler.BH + offense team fb_efficiency attribute) × die
  - stop_score = (stopper.AG + stopper.OD + defense team fb_opp_modifer attribute) × die 
  - if stop score >= break score, Defensive Stop triggers
- **Trigger:** BH-beats-stopper gate fails (stopper wins). `result_type = "DEFENSIVE_STOP"`.
- **Movers:** BH (sprint, AG-scaled) → BH stop spot. Stopper (normal, AG-scaled) → stop spot in front of BH.
- **Gate:** slower of the two traversals (BH vs stopper) is the advance trigger; the faster one waits visually.
- **Ball:** stays with BH throughout.
- **Announcement:** `step.end.announcement = "Nice Stop!"` (secondary, defense team, stopper headshot, `meta.sfx = "fb_defensive_stop"`, 1000ms hold).
- **Step 2 (extra):** step-back / HCO setup. FB BH retreats to a deep frontcourt spot. HCO BH (default = team's PG) takes a position near FB BH on the same horizontal half (over-and-back avoided by construction). Remaining 8 players take HCO setup positions via the standard `pos1..pos4` alias mapping; defenders mirror with same-lineup-position matchup (2-3 zone footprint by construction).
- **Transition:** implicit end (`next = next_step` past the array) → caller spawns the next HCO turn.

## Rim Runner (`rim_runner_step_emitter`)

Step 0: Burst
- AT: `player_reaches_position` (RR reaches `rr_to`)
- Archetypes: RR = `burst` on movement-check success, `sprint` on failure; outlet receiver = `sprint`; get-back defenders = `sprint`; outlet passer = `stationary`; others = drift toward attacking basket (per `rim_runner_burst_phase` payload)
- RR destination (`rr_to`): upper or lower wing (depending on which is his vertical half) on the offense side of the court
  - X & Y: roll `movement_factor` vs `0.6×AG + 0.2×IQ + 0.2×CH` — success → RR moves at burst speed toward rr_to; fail → RR moves at sprint speed toward rr_to; clamped at the destination; sign by home/away offense
  - Vertical half (uses pre-sprint y): if `y > 24` → upper; else lower
  - Dynamic override when prior shot has `ball_bounce_x` in mid-court band (home `25 < x < 50`; away `50 < x < 75`): X measured from `outlet_receiver_target + burst_delta`, not from RR's pre-burst x
- Outlet contest defender moves to `outlet_defender_to` (passer x ±2, same y as passer)

Step 1: Branch keyed off outlet contest outcome

| Branch | Steps after Burst | Turn_stop | `schema_rendered_arc` |
|---|---|---|---|
- **Skill Check**
  - outlet_pass_score = (rebounder.PS×0.5 + rebounder.ST×0.3 + rebounder.IQ×0.2 + offense team fb_efficiency) * random.randint(1,6)
  - outlet_pass_d_score = (defender.IQ×0.5 + defender.OD×0.3 + defender.ST×0.2 + defense team fb_opp_modifer) * random.randint(1,6)
  - Final Decision: if outlet_pass_d_score . (2 * outlet_pass_score), outlet denied, else outlet pass success
| **Outlet denied** (`rim_runner_outlet_failed=True`) | Outlet-denied defender close-out; "FB Outlet Pass Denied!" announcement; horizontal drift of non-involved players | implicit end → next HCO | ✗ |
| **Outlet pass success** | Outlet pass step (`ball_reaches_player`; skipped when `skip_outlet_pass`) → Step 2 | — | — |

Step 2: Branch keyed off RR read result (after successful outlet)

| Branch | Steps appended | Turn_stop | `schema_rendered_arc` |
|---|---|---|---|
| **Hold-up** (no lane pass) | Hold-up settle (BH +6x toward basket, ±8y) + parallel horizontal drift of others | implicit end → next HCO (`_rimRunnerHoldUpInboundPass` if BH ≠ PG) | ✗ |
| **Lane pass intercepted** | Lane pass step → interception at contact-point grid | `STEAL` | ✗ |
| **Lane pass batted OOB** | Lane pass step → bat at contact-point grid → continue to nearest sideline/baseline; "Batted Ball Out Of Bounds!" | `DEAD_BALL_TURNOVER` | ✗ |
| **Lane pass + shot** | Lane pass ("Fast Break!" announcement) → Shoot motion → **[skeleton post-shot chain]** | `SHOT_ATTEMPT` | ✓ |

ATs: lane pass = `ball_reaches_player` (RR for shot; primary defender for steal/bat OOB). Shoot motion = `player_reaches_position` (RR reaches shot spot).

### RR Hold-Up vs Lane Pass decision logic (Step 2)

Backend stages (in `resolve_rim_runner_fast_break`) that decide whether the BH attempts the lane pass to RR or holds up:

**Stage B — Burst scores** (sum × die per side; separate die per side; team-level FB attributes baked in)
- `burst_offense_score = (rr.AG × 0.7 + rr.IQ × 0.3 + offense.fb_efficiency) × random.randint(1, 6)`
- Defense base depends on whether primary defender is in the get-back pool:
  - **In get-back**: `burst_def_base = primary.IQ × 0.6 + primary.AG × 0.5`
  - **NOT in get-back**: `burst_def_base = primary.IQ × 0.5 + primary.AG × 0.5`
- `burst_defense_score = (burst_def_base + defense.fb_opp_modifier) × random.randint(1, 6)`
- If no primary defender: `burst_defense_score = 0.0`

**Stage C — `fb_open` decision** (objective: is the lane open?)
- Rim Runner: `fb_open = burst_offense_score > burst_defense_score`
- Triangle: `fb_open = (burst_offense_score × 0.8) > burst_defense_score` (stricter than RR but looser than the prior 0.6× spec)

**Stage D — PG read** (BH's subjective assessment)
- `read_score = (ball_handler.IQ + offense.fb_efficiency) × random.randint(1, 6)`
- `read_threshold = 200 − (5 × offense.fb_efficiency)` — higher fb_efficiency lowers the threshold
- `correct_read = read_score > read_threshold`
- Note: fb_efficiency now influences BOTH sides of the comparison (additive on score, subtractive on threshold).

**Stage E — `pass_attempted` decision**
- Reads `aggression = off_team.strategy_settings["aggression"]` (integer 0-4 — raw slider, NOT the rolled `aggression_call`)
- `is_aggressive = aggression >= 3`

| BH read | Aggression | `pass_attempted` |
|---|---|---|
| Correct read | any | `= fb_open` (correctly passes iff lane is open) |
| Misread + aggressive (≥ 3) | — | `random.choice([True, True, False])` (≈ 67% attempt) |
| Misread + normal/passive (< 3) | — | `random.choice([True, False])` (50/50) |

**Stage F — Outcome**
- `pass_attempted == True` → Lane Pass branch (intercept / bat OOB / shot resolution)
- `pass_attempted == False` (RR only) → Hold-Up branch (`rim_runner_no_lane_pass = True`)
- `pass_attempted == False` + Triangle → Triangle decision tree

### RR Outlet Denied sub-step logic
- **Trigger:** outlet pass contest fails (outlet defender wins the attribute roll). `rim_runner_outlet_failed = True` on the turn.
- **Movers:** outlet defender (standard, AG-scaled) → close-out spot at `ball_holder.x + 2 toward basket, ball_holder.y`. Ball holder is the outlet passer (rebounder) normally; if `skip_outlet_pass` (rebounder == receiver), the defender anchors on the receiver instead.
- **Ball:** stays with ball holder (no pass fires).
- **Announcement:** `step.end.announcement = "FB Outlet Pass Denied!"` (secondary, defense team, defender headshot, `meta.sfx = "fb_outlet_denied_court"`, 1000ms hold).
- **Additional steps (after defender close-out):** step 2 = outlet receiver cutback + drift of non-involved players; step 3 = recovery pass back to rebounder.
- **Transition:** implicit end → caller spawns the next HCO turn (with `hco_setup.inbound_pass` when BH ≠ PG).

### RR Hold-up sub-step logic
- **Trigger:** BH (outlet receiver) does NOT attempt the lane pass to RR. `rim_runner_no_lane_pass = True` on the turn.
- **BH settle target:** `bh.x + 6 toward attacking basket`, `bh.y ± 8 toward y=25` (clamped to `[1, 49]` on y, `[4, 97]` on x). Archetype = `standard`, action = `handle_ball`.
- **Other 9 players:** drift +40 grid spots toward attacking basket at `standard` rate. Offense → `cut`; defense → `guard_offball`. End coords clamped via interrupted-coord at `rate × T` so no one overshoots the BH gate.
- **Ball:** stays with BH.
- **Gate:** `player_reaches_position` keyed to BH reaching the settle target.
- **Announcement:** `step.start.announcement = "No Fast Break"` (secondary, offense team, BH headshot, `meta.sfx = "no_fast_break"`, decision-pill payload, 1000ms hold).
- **Transition:** implicit end → caller spawns the next HCO turn (with `hco_setup.inbound_pass` when BH ≠ PG, via `_rimRunnerHoldUpInboundPass`).

## Triangle (`triangle_step_emitter`)

Steps 0-1: Burst + outlet pass (shared with Rim Runner; outlet-denied reuses RR's denied path)

Step 2: RR read gate (stricter threshold: `fb_open = (burst_offense_score × 0.8) > burst_defense_score`)
- If `pass_attempted = True`: route to RR lane-pass branch (intercept / bat OOB / shot)
- If `pass_attempted = False`: proceed to Step 3

Step 3: Triangle setup ("Fast Break!" announcement)
- AT: `player_reaches_position` (RR + BH both reach setup spots)
- Corner players: `sprint` to upper/lower corner (lower-y → lower corner)
- BH: non-burst to wing (upper if y > 25 else lower)
- RR: non-burst to same-side lowPost as BH wing
- Trailer (rebounder/outlet passer): non-burst to opposite wing
- Defenders: closest-by-x → RR, second-closest-by-x → BH (skeleton HCO man-matchup); other 3 → random lane spots
- If defense `fb_opp_modifier > 5`: non-get-back defenders use `burst`

Step 4: Decision branch keyed off `triangle_branch` (from `decision = randint(1, 8)`)

| `triangle_branch` | Decision | Steps after setup | Turn_stop | `schema_rendered_arc` |
|---|---|---|---|---|
| `triangle_rr_post` | 1-2 | BH → RR pass → Shoot motion → **[skeleton post-shot chain]** | `SHOT_ATTEMPT` | ✓ |
| `triangle_corner_three` | 3 | Wait for same-side corner → BH → corner pass → Shoot motion → **[skeleton post-shot chain]** | `SHOT_ATTEMPT` | ✓ |
| `triangle_bh_wing_three` | 4 | Shoot motion → **[skeleton post-shot chain]** (no decision lead-in) | `SHOT_ATTEMPT` | ✓ |
| `triangle_bh_drive` | 5-6, drive 1-2 | BH drive to lowPost + RR to midLane → Shoot motion (attack) → **[skeleton post-shot chain]** | `SHOT_ATTEMPT` | ✓ |
| `triangle_drive_rr_feed` | 5-6, drive 3-4 | BH drive → BH → RR pass at midLane → Shoot motion → **[skeleton post-shot chain]** | `SHOT_ATTEMPT` | ✓ |
| `triangle_drive_corner_kick` | 5-6, drive 5 | BH drive → BH → corner pass → Shoot motion → **[skeleton post-shot chain]** | `SHOT_ATTEMPT` | ✓ |
| `triangle_enter_hco` | 7-8 | (no shot; live coords carry forward; if BH ≠ PG, BH → PG pass once PG reaches HCO step 0) | implicit end → next HCO | ✗ |

Triangle-specific shot rules inside `[skeleton post-shot chain]`:
- Corner-3: shot defender only if any defender within Euclidean 6 of shooter
- No-defender corner-3: shot good if `shot_score > (190 - offense_team.fb_efficiency)`

## DREB → FB coord bridge (UESS §8.2 contract)

FB step 0's `start.coords` per player must equal prior DREB turn's `final_coords`. Sources for non-rebounder coords on the prior shot turn:

| Role | Source priority |
|---|---|
| Outlet receiver (CR) | `defense_release_coords` → `offense_getback_coords` → `player.coords` |
| Outlet receiver (RR / Triangle) | `roles["ball_handler_outlet_x/y"]` from `rim_runner_burst_phase.receiver_to` |
| Get-back defenders | `offense_getback_coords` → `defender.coords` |
| Rebounder (outlet passer) | `last_rebounder` position from DREB turn |
| All other non-rebounder offense | `player.coords` (sync'd by `sync_lineup_coords_from_turn` at DREB turn end) |

Any non-match between DREB `final_coords` and FB step 0 `start.coords` is a teleport.


## Fast Break — Backend Resolution Stages

(Distinct from schema steps. Stages run inside the FB resolvers BEFORE
the AnimationStep[] is emitted. Schema steps are the visual rendering of
the result of these stages.)

### Rim Runner / Covert Release (DREB-triggered)

**Stage 1: Pre-shot skill check ("BH beats defender")**
- `phase_resolution.py:1224, 1587-1596`
- `break_score = ball_handler.AG + ball_handler.BH * die`
- `stop_score = defender.AG + defender.OD * die`
- If stopper wins: `hold_up=True`, FB ends in defensive stop (no shot,
  transition to HCO). `stopper_id` is set.
- If BH wins: `hold_up=False`, proceed to stage 2.

**Stage 2: Shot location** (universal helper — gated by `USE_UNIVERSAL_FB_SHOT_GEOMETRY_RR` / `_CR`)
- New: shooter target = `basket_x ± random(2, 3)` toward center,
  `y = random.randint(19, 31)`. Replaces the play-specific shot spot.
- Legacy path preserved behind the flag for revert.

**Stage 3: Shot defender selection + contested decision** (universal helper)
- Defender single target: `shooter_x ± 2` toward basket, same y as shooter.
- "Available defenders" race to target at AG-based sprint rate.
- Race pool per FB:
  - RR: excludes **Stopper** AND **Outlet defender**. Race pool = Trail
    + Get-back defenders.
  - CR: excludes **Stopper** only (no outlet defender concept). Race
    pool = Trail + Get-back defenders.
  - (Steal-FB: all 5, no exclusions — same helper.)
- First arriver → shot defender. Others freeze at interpolated positions
  at t_first, clamped no closer than 6 grid spots from basket
  (no-pull-backward edge case for defenders starting inside the zone).
- Stopper and Outlet defender stay at their end-of-preceding-step
  positions (no movement during the shot step).
- Contested if closest defender's x is past shooter's x at t_shooter;
  else uncontested.

**Stage 4: Shot resolution**
- `calculate_shot_score(shooter, ..., defender=first_arriver_or_None, apply_defense=contested)`.
- Uncontested → `apply_defense=False`, threshold override to 1 →
  automatic MAKE (matches OREB putback uncontested rule and Steal-FB).

### Steal Fast Break (steal-triggered)
- Single resolver in `after_steal_fast_break.py`.
- No Stage 1 stopper gate — the steal IS the gate (BH already has the
  ball at the steal moment).
- Stages 2-4 use the same universal helper as RR/CR above, with all 5
  defenders in the race pool.

### Triangle (DREB-triggered) — INTENTIONALLY UNTOUCHED
- Triangle's existing shot location and shot defender selection logic
  remain in place. The universal helper is NOT applied to Triangle.


**Final Shot**

---

## Turn routing (`offensive_state`)

**Canonical signal:** `game.game_state["offensive_state"]` — which resolver runs next (`HCO`, `HCT`, `FCP`, `FAST_BREAK`, `FREE_THROW`). Handlers (`shot_manager`, `phase_resolution`, etc.) must set it on every exit path; `next_play_type` is display/logging only.

**Rule (source of truth):** [`BackEnd/models/turn_manager.py`](../../BackEnd/models/turn_manager.py) ~1671–1687 — if a handler omits `offensive_state`, that is a handler bug.

**Not routed via `offensive_state`:** `OREB`, `DREB`, `BASELINE_INBOUND` — use `pending_*` flags when extra payload is required (`pending_oreb`, `pending_dreb_fb_play_key`, `pending_terminal_ft`, `situational_force_foul_pending`).

**Hardening (open):** log/assert when a turn resolves without updating `offensive_state` — see [`projects/offensive_state_hardening.md`](../projects/offensive_state_hardening.md).
