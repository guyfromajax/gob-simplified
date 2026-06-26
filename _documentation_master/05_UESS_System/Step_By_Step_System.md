This doc summarizes the steps and potential steps that are part of each Turn Type, including each step's **advance trigger** — the condition that ends the step. The backend pre-computes the trigger's time T (game-seconds) for every step regardless of condition; the frontend playback engine awaits exactly that duration before rendering step end. (Merged from `05_Animation_System/Advance_Triggers.md`, June 2026.)

**Advance trigger conditions (closed vocab):**
- `fixed_duration` — step ends after a backend-computed duration. T = the duration.
- `ball_reaches_player` — step ends when the ball arrives at a target player. T = pass distance ÷ pass speed.
- `player_reaches_position` — step ends when a target player arrives at a target coord. T = traversal time at the player's archetype rate.
- `shot_resolved` — step ends when shot outcome is determined.
- `stopper_action` — step ends on backend-rolled foul / steal / dead-ball turnover event.

**FB pass rates** (constants in `BackEnd/constants/__init__.py`): sharp outlet (`outlet_score >= FB_OUTLET_QUALITY_THRESHOLD` = 50) flies at `FB_PASS_GRID_SPOTS_PER_GAME_SECOND` = 40 grid/game-sec; sloppy at `FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY` = 30 (the ball hangs longer, the play reads less crisp); all FB pass steps floored at `FB_PASS_MIN_GAME_SECONDS` = 0.5 game-sec. HCO's canonical pass rate is separate: `PASS_GRID_SPOTS_PER_GAME_SECOND` = 24.

## Universal step patterns

(Merged from `05_Animation_System/Step_Types_System.md`, June 2026.) Each step type below is a recurring pattern of player + ball movement that can be composed into any turn; the per-turn sections later in this doc build on this vocabulary.

- **Parallel Movement** — Multiple players move toward their own destinations in parallel; one player's natural traversal sets step T, others clamp to `rate × T`. "Drift" (settle-pace movement toward attacking-basket-relative targets) is just this step type with settle-pace archetype defaults.
- **Pass** — Ball travels passer → receiver; passer and receiver typically stationary; non-key players may continue prior movement in parallel.
- **Reset** — Ball handler delivers ball to PG and the other players reposition to random lane spots; bridges a turn-end (FB / HCT / FCP / OREB) into the next HCO turn. See spec + status below.
- **Shot Motion** — Shooter sprints to the shot spot with defender contesting; terminates the turn via `turn_stop: SHOT_ATTEMPT`.
- **Intercept** — Defender catches a pass mid-flight; ball bends from passer to contact point to defender; terminates via `turn_stop: STEAL`.
- **Batted Ball** — Defender deflects a pass mid-flight; ball bends from passer to contact point and drifts to the nearest OOB grid; terminates via `turn_stop: DEAD_BALL_TURNOVER`.
- **Stopper** — Anything other than a shot attempt that ends a turn — dead ball turnover, steal, or foul.

### Reset step spec

> **Implementation status (June 2026):** the universal helper exists — [`BackEnd/utils/reset_step_helper.py`](../../BackEnd/utils/reset_step_helper.py) `build_reset_steps()`, which cites this section as its spec — but is **not yet invoked from any emitter**. The live HCO seam (post-FB-defensive-stop, post-hold-up, post-outlet-denied, post-DREB, post-steal) is currently rendered by the HCO entry orchestrator's Handoff / Kickout / Walk Up steps (`transition_bridge.py`), driven by `hco_setup.inbound_pass` hints from the source turn. Wiring `build_reset_steps` in is tracked in `projects/UESS_Backlog.md` (the "Handoff+walk-up after steal too fast" item notes the orchestrator's converge beat is faster than this spec intends).

Reset is a **named pattern**, not a new primitive — it composes Parallel Movement + Pass:

- **Over-and-back guard:** if home offense and the ball handler's x ≥ 50, the PG cannot move to x < 50 to receive the pass (away offense mirrored: BH x ≤ 50 → PG x clamped ≥ 50... i.e. PG x clamped to the midline).
- **Lane spots** = random choice of `basketSpot`, `lower lowPost`, `upper lowPost`, `lower midPost`, `upper midPost`, `midLane`, `upper highPost`, `lower highPost`, `topLane` (mirrored for away offense).
- **Ball Handler** holds his position.
- **Offense PG:**
  - if not the ball handler — one **PG converge** step (gate = PG arrival): PG sprints to a random spot within 10 grid Euclidean of the ball handler (over-and-back clamped), then one **inbound pass** step (gate = ball reaches PG).
  - if the ball handler IS the PG — single step: he holds his position for 2 game seconds (`fixed_duration`).
- **All other 8 or 9 players** move toward their pre-picked random lane spot at `standard` rate (offense `cut`, defense `guard_offball`); targets persist across both Reset sub-steps so the drift reads continuously; end coords clamp via interrupted-coord at `rate × T`.
- **Instances used** (per the helper's intended call sites): following each of —
  - CR FB: Defensive Stop
  - RR FB: Hold Up
  - RR FB: Outlet Denied
  - DREB before transition to HCO
  - Steal that does not lead to Fast Break

---

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

##Gating player & step T (skeleton steps)
HCO is skeleton-driven: the emitter walks `skeleton.steps[i]` + `step_clock_seconds[i]` and emits one AnimationStep per skeleton step (typically 4-10 after inbound trim). T = `step_clock_seconds[i]`; faster movers reach their destinations earlier and idle until T.
- Steps `0..N−2`: gate = **slowest mover** (player with the largest start→end distance).
- Step `N−1` (final): gate = **shooter** (offense player with `shoot` in pos_actions); falls back to slowest mover if the final step has no shoot action (non-shot outcomes).

Final step branches on `result_type` (same outcome map as HCT's outcome step):
- `MAKE`/`MISS`/`BLOCK` → `turn_stop: SHOT_ATTEMPT`
- `D_FOUL`/`O_FOUL`/`FOUL` → `turn_stop: FOUL`
- `STEAL` → `turn_stop: STEAL`
- `DEAD_BALL` / `DEAD_BALL_TURNOVER` / `TURNOVER` → `turn_stop: DEAD_BALL_TURNOVER`
- `SHOT_CLOCK_EXPIRED` → `turn_stop: SHOT_CLOCK_EXPIRED`

After HCO/HCT/FCP MISS with defensive rebound, a discrete DREB turn is generated (parallel to OREB). See DREB section below.

**HCT**
Step 1: Walk Up (required)
Steps 2+: HCT Dynamic Execution (required)

Per-step advance triggers (all `player_reaches_position`; T = `step_clock_seconds[i]`):

| # | Step | Gating player |
|---|---|---|
| 0 | Setup | slowest setup mover (max start→end distance) |
| 1 | BH advance | BH |
| 2 | PG converge | PG defender (defender on BH) |
| 3 | Outcome | BH (same `result_type` → `turn_stop` outcome map as HCO) |

**FCP**
Steps 1+: FCP Skeleton Execution (required)
- Same skeleton machinery as HCO (slowest-mover gating, shooter gate on shot steps). Stopper-action steps gate on the players involved in the stop event.

**OREB**
Step 1: Rebound Capture (captor → bounce; attemptors → bounce ±4x/±6y)
Step 2: Kickout
Step 2A: Kickout Positioning
Step 3: Putback Attempt
Step 4: Ball Flight
Step 5: Bounce (miss/block) or hold (make)

**DREB**
Step 1: Rebound Capture (captor → bounce; attemptors → bounce ±4x/±6y)
- AT: `player_reaches_position` (rebounder → ball bounce coords); T = rebounder traversal time at `sprint` archetype
If OTB fires on the defensive rebound battle, Step 1 still completes the rebound capture and ball attach, then emits `"Over The Back!"` and `turn_stop: FOUL`. SIP/free-throw continuation is produced by the backend's standard non-shooting foul progression, not by frontend inference.
DREB normally ends implicitly after this single step and routes to HCO/HCT/FCP/FAST_BREAK.


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

**Fast Breaks** (schema playback via `animation_steps` for all four FB plays: Covert Release, Rim Runner, Triangle, After Steal)

All four FB emitters route MAKE/MISS/BLOCK shot outcomes through skeleton's `_build_post_shot_sub_steps` (`skeleton_step_emitter.py`), which appends the same post-shot chain as HCO (ball_flight → variant → hold/bounce) and sets `schema_rendered_arc=True` on the terminal `SHOT_ATTEMPT` turn_stop. Non-shot branches (steal / bat OOB / hold-up / outlet-denied / defensive-stop) terminate without that chain. See HCO §Post-Shot Variant Chain for the shared sub-step table.

## Covert Release (`covert_release_step_emitter`)

Step 1: Outlet pass (skipped if rebounder == outlet receiver)
- AT: `ball_reaches_player` (receiver); T = distance ÷ FB pass rate (sharp/sloppy gating — see FB pass rates at top), floored at 0.5 game-sec
- Outlet passer + receiver stationary; get-back defenders execute "read on outlet pass" positioning at `sprint` (see [Fast_Break_System.md](../05_GP_Supporting_Systems/Fast_Break_System.md) §Get-back defender read). Defenders who retreat instead target a random spot in the defender box near the attacking rim (home offense `(87–91, 20–30)`; away `(9–13, 20–30)`; second retreater offset ≥2 grid on both axes to avoid stacking)
- All other players (non-passer, non-receiver, non-getback — typically 5–7): drift a random 1–6 grid spots toward the attacking basket along x (y held) at `standard` rate. Keeps the outlet pass visually focused on ball + receiver; they ramp up to sprint with the play on step 2

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
- **Gate:** `player_reaches_position` on the slower of the two traversals (BH vs stopper); the faster one waits visually.
- **Ball:** stays with BH throughout.
- **Announcement:** `step.end.announcement = "Nice Stop!"` (secondary, defense team, stopper headshot, `meta.sfx = "fb_defensive_stop"`, 1000ms hold).
- **Step 2 (extra):** step-back / HCO setup; gate = `player_reaches_position` on the slowest mover (max traversal at `drive` rate). FB BH retreats to a random one of `HCO_SETUP_OFFENSE_BH_DEEP_SPOTS` (`{deep key, deep upper wing, deep lower wing}`). HCO BH (default = team's PG; only moves if different from FB BH) takes a position within `HCO_SETUP_HCO_BH_RADIUS` = 10 grid units of FB BH on the same horizontal half (home offense → x ≥ 50; away → x ≤ 50; over-and-back avoided by construction). Remaining offense players take HCO setup positions via the standard `pos1..pos4` alias mapping (pos1 → upper wing, pos2 → lower wing, pos3 → upper lowPost, pos4 → lower lowPost; pos4 dropped when FB BH ≠ HCO BH); defenders mirror with same-lineup-position matchup (2-3 zone footprint by construction).
- **Transition:** implicit end (`next = next_step` past the array) → caller spawns the next HCO turn.

## Rim Runner (`rim_runner_step_emitter`)

Step 0: Burst
- AT: `fixed_duration`, `T_game_seconds = 1.0`
- Archetypes: RR = `burst` on movement-check success, `sprint` on failure; outlet receiver = `sprint`; get-back defenders = `sprint`; outlet passer = `stationary`; others = drift toward attacking basket (per `rim_runner_burst_phase` payload)
- RR destination (`rr_to`): offense `basketSpot` (`HCO_STRING_SPOTS`, mirrored for away offense)
  - Roll `movement_factor` vs `0.6×AG + 0.2×IQ + 0.2×CH` — success → `burst`; fail → `sprint`
  - Backend interruption math advances RR toward `basketSpot` for exactly 1.0 game-second at the chosen AG-scaled archetype rate; RR is not forced to `basketSpot` unless his rate/distance allows it
  - Dynamic x-base metadata may be stamped when prior shot has `ball_bounce_x` in the mid-court band (home `25 < x < 50`; away `50 < x < 75`), but it no longer changes `rr_to`
- Outlet receiver: fixed outlet x by side (`45` home offense, `55` away offense); y snaps to the opposite wing band from RR (`15` if RR starts upper, else `35`)
- Outlet contest defender moves to `outlet_defender_to` (passer x ±2 toward basket, same y as passer)
- Get-back defenders: defender 1 targets 2 x spots ahead of RR's burst-end position (same y as RR); defender 2 (if present) targets the same-side `lowPost` near the basket (`upper lowPost` if RR's burst-end y > 24, else `lower`; coords from `HCO_STRING_SPOTS`)
- Other O (2 non-RR, non-receiver) and other D (non-getback): drift forward 1–4 x spots toward the offense's attacking basket; y unchanged

Step 1 (outlet pass success): Outlet pass — AT: `ball_reaches_player` (receiver); T = passer→receiver distance ÷ FB pass rate. Passer stationary, releases ball at step start; receiver stationary at `receiver_to`; RR continues toward `basketSpot` using the same `burst` / `sprint` archetype chosen in Step 0 (**Triangle exception**: the RR is forced to `sprint` in this step regardless of the Step-0 roll — see Triangle in [Fast_Break_System.md](../06_Gameplay_Systems/Fast_Break_System.md)); other movers' tweens keep running through step 1 by default (the opt-in `UESS_FB_CRITICAL_EVENT_PATTERN` flag in `fastBreak.js` would freeze them at the step 0 boundary instead).

Step 1: Branch keyed off outlet contest outcome

**Outlet contest skill check** (Step A in `resolve_rim_runner_fast_break`):
- Distance gate: outlet defender must be within 10 grid Euclidean of the outlet passer to contest; beyond that → auto-success (no roll)
- `outlet_offense_score = (rebounder.PS×0.5 + rebounder.ST×0.3 + rebounder.IQ×0.2) × random.randint(1,6)`
- `outlet_defense_score = (defender.IQ×0.5 + defender.OD×0.3 + defender.ST×0.2) × random.randint(1,6)` (0.0 if no defender / out of range)
- Team FB attributes (each clamped to ±10) enter the final inequality, not the bases: success iff `(1.5 × outlet_offense_score) + (3 × fb_efficiency) > outlet_defense_score + (2 × fb_opp_modifier)`

| Branch | Steps after Burst | Turn_stop | `schema_rendered_arc` |
|---|---|---|---|
| **Outlet denied** (`rim_runner_outlet_failed=True`) | Outlet-denied defender close-out; "FB Outlet Pass Denied!" announcement | implicit end → next HCO (Reset step) | ✗ |
| **Outlet pass success** | Outlet pass step (`ball_reaches_player`; skipped when `skip_outlet_pass`) → Step 2 | — | — |

Step 2: Branch keyed off RR read result (after successful outlet)

| Branch | Steps appended | Turn_stop | `schema_rendered_arc` |
|---|---|---|---|
| **Hold-up** (no lane pass) | Hold-up settle (BH +6x toward basket, ±8y) + parallel horizontal drift of others | implicit end → next HCO (`_rimRunnerHoldUpInboundPass` if BH ≠ PG) | ✗ |
| **Lane pass intercepted** | Lane pass step → interception at contact-point grid | `STEAL` | ✗ |
| **Lane pass batted OOB** | Lane pass step → bat at contact-point grid → continue to nearest sideline/baseline; "Batted Ball Out Of Bounds!" | `DEAD_BALL_TURNOVER` | ✗ |
| **Lane pass + shot** | Lane pass ("Fast Break!" announcement) → Shoot motion → **[skeleton post-shot chain]** | `SHOT_ATTEMPT` | ✓ |

ATs: lane pass = `ball_reaches_player` (RR for shot; primary defender for steal/bat OOB). Shoot motion = `player_reaches_position` (RR reaches shot spot). Shot motion is the terminal step — there is no separate "shot resolution" step; the playback engine's `runShotAttempt` handler renders the release after the shooter snaps to the shot spot at step end.

Lane-pass step per-role movement (shot branch): RR moves toward the pass catch target while the ball flies from the outlet receiver/BH; outlet receiver/BH stationary, releases lane pass; everyone else stationary at the prior step endpoints. The "Fast Break!" announcement plays on `step.start` (secondary style, offense side, passer headshot, decision-pill payload from the FB play label).

Interception branch: RR tweens to a partial position (`rr_to.x + 3` toward basket, same y — not the full catch spot); stealer tweens to the interception contact grid at `sprint`; "Interception!" `step.end` announcement (defense side, stealer headshot, `meta.sfx: "steal"`, 1000ms hold).

Bat-OOB branch: RR tweens to `rr_to.x + 4` toward basket; batting defender sprints to the contact grid and deflects; ball flies BH → contact grid (`BallInFlight`), then step end = `BallLoose` at the nearest OOB grid (`advance_trigger.metadata.contact_coords` + `oob_coords` drive the frontend bend + drift); "Out of bounds!" `step.end` announcement (neutral, no headshot, 650ms hold).

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
- **Sim distance gate:** outlet defender must be within 10 grid Euclidean of the outlet passer at burst start to claim the denial; beyond that the contest auto-succeeds (denial is geometrically implausible at distance). Gate lives in `rim_runner_fast_break.py` Step A; the animation is unaffected (defender still tweens toward the contest spot during burst).
- **Movers:** outlet defender (standard, AG-scaled) → close-out spot at `ball_holder.x + 2 toward basket, ball_holder.y`. Ball holder is the outlet passer (rebounder) normally; if `skip_outlet_pass` (rebounder == receiver), the defender anchors on the receiver instead.
- **Ball:** stays with ball holder (no pass fires).
- **Announcement:** `step.end.announcement = "FB Outlet Pass Denied!"` (secondary, defense team, defender headshot, `meta.sfx = "fb_outlet_denied_court"`, 1000ms hold).
- **Transition:** the RR turn ends at the defender close-out (implicit end). The cutback + recovery-pass beats have been moved to the next HCO turn's **Reset step** (destination-turn pattern) — `hco_setup` on the turn payload signals the next HCO turn to render the inbound to PG.

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

| Outcome | Emitter path | Steps (summary) |
|---|---|---|
| `pass_attempted = True` | **`append_lane_pass_to_rr_resolution_steps`** (shared with Rim Runner; `rim_runner_step_emitter.py`) | Same as RR Step 2 table: hold-up / intercept / bat OOB / lane pass → shoot → **[skeleton post-shot chain]** |
| `pass_attempted = False` | Triangle-only setup tree (below) | Step 3+ |

**Lane-pass quick shot** (outlet receiver passes ahead to RR — no Triangle corners/setup):
- Detection: `rim_runner_pass_attempted` on turn_result, **no** `triangle_setup_phase`.
- Passer on lane-pass step = `rim_runner_burst_phase.outlet_receiver_id` (ball handler after burst; outlet pass step skipped when `skip_outlet_pass`).
- Shot motion uses **`_build_shot_motion_step`** (RR), not `_build_triangle_shot_motion_step`.
- Announcement subtitle uses play label **"Triangle"** via `_fb_play_label(fast_break_play)`.
- Miss → DREB: same discrete DREB promotion as other migrated FB misses (schema bounce on MISS turn, rebound capture on DREB turn).

Step 3: Triangle setup ("Fast Break!" announcement) — only when `pass_attempted = False`
- AT: `player_reaches_position` gated on the **BH** reaching his setup spot (`gate_player_id = bh_id` in `_build_parallel_move_step`; T = BH traversal at `sprint` rate, AG-scaled)
- Corner players: `sprint` to upper/lower corner (lower-y → lower corner)
- BH: `sprint` to wing (upper if y > 25 else lower)
- RR: `sprint` to same-side lowPost as BH wing
- Trailer (rebounder/outlet passer): `sprint` to opposite wing
- Defenders: closest-by-x → RR, second-closest-by-x → BH (skeleton HCO man-matchup); other 3 → random lane spots; all use `sprint`

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

Triangle branch-step ATs: pass steps (BH → RR / BH → corner) = `ball_reaches_player` (receiver; T = pass flight at `FB_PASS_GRID_SPOTS_PER_GAME_SECOND`, floored at `FB_PASS_MIN_GAME_SECONDS`); drive step (`triangle_bh_drive` / `triangle_drive_rr_feed` / `triangle_drive_corner_kick`) = `player_reaches_position` gated on **BH** reaching `triangle_drive_to` (BH at `sprint` / `handle_ball`, RR rides along at `sprint` / `cut` to `triangle_rr_drive_to`); shot motion = `player_reaches_position` (shooter reaches shot spot).

Triangle-specific shot rules inside `[skeleton post-shot chain]`:
- Corner-3: shot defender only if any defender within Euclidean 6 of shooter
- No-defender corner-3: shot good if `shot_score > (190 - offense_team.fb_efficiency)`

## After Steal (`after_steal_fast_break_step_emitter`)

Pure schema renderer — the backend resolver (`after_steal_fast_break.resolve_after_steal_fast_break`) precomputes all 10 players' end coords and the contested decision; the emitter just builds steps.

Step 1: Drive step (single step, all 10 players)
- Stealer (= BH) sprints to `bh_target` (2-3 grid spots out from basket, y ∈ [19, 31]); ball attached
- Defenders → defender single target (first arriver) or frozen/clamped intermediate positions
- Other 4 offensive players → unique sampled HCO setup spots, interpolated at t_shooter
- "Fast Break!" announcement on `start`; AT: `player_reaches_position` (stealer reaches BH target)

Step 2: **[skeleton post-shot chain]** via `_build_post_shot_sub_steps` (shared with HCO / OREB). Make-hold announcement post-processed from "It's Good!" to "Fast Break Score!" (or "Fast Break Score! And 1!").

Foul handling mirrors the OREB putback foul path (and-1 on make, 2 FTs on miss → standard FT turn continuation).

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
- `phase_resolution.py` (legacy DREB-FB path); same formula as §CR Defensive Stop sub-step logic, separate die per side:
- `break_score = (ball_handler.AG + ball_handler.BH + offense fb_efficiency) × die_off`
- `stop_score = (stopper.AG + stopper.OD + defense fb_opp_modifier) × die_def`
- If stopper wins (`stop_score >= break_score`): `hold_up=True`, FB ends in defensive stop (no shot,
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


**Final Shot** (end-of-quarter ``final_turn``) — UESS schema path: ``turn_manager._emit_hco_animation_steps`` → ``build_skeleton_animation_steps`` emits full ``animation_steps[]``. Skeleton step 0 is Final Turn alignment (all ten players to ``oDestinations`` / ``dDestinations`` spots); backend stamps ``_step_t_floor_game_seconds`` on step 0 so the clock burns until ~3s (Outside) or ~4s (Attack) remain before pass/drive/shoot steps. Frontend plays the **full** step list from index 0 via ``runSchemaPlaybackTurn`` / ``playTurn()`` — no step-0 skip, FE alignment tween, or coord patch. Legacy ``Animator.skeleton_to_animations`` / ``animations[]`` remains fallback when schema steps are absent.

---

## Turn routing (`offensive_state`)

**Canonical signal:** `game.game_state["offensive_state"]` — which resolver runs next (`HCO`, `HCT`, `FCP`, `FAST_BREAK`, `FREE_THROW`). Handlers (`shot_manager`, `phase_resolution`, etc.) must set it on every exit path; `next_play_type` is display/logging only.

**Rule (source of truth):** `TurnManager.run_micro_turn` ([`BackEnd/models/turn_manager.py`](../../BackEnd/models/turn_manager.py)) — if a handler omits `offensive_state`, that is a handler bug (see the "REMOVED: Overwrite logic" note; the manager does not patch it).

**Not routed via `offensive_state`:** `OREB`, `DREB`, `BASELINE_INBOUND` — use `pending_*` flags when extra payload is required (`pending_oreb`, `pending_dreb_fb_play_key`, `pending_terminal_ft`, `situational_force_foul_pending`).

**Hardening (open):** log/assert when a turn resolves without updating `offensive_state` — see [`projects/offensive_state_hardening.md`](../projects/offensive_state_hardening.md).
