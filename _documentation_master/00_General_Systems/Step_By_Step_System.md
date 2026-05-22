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

##Post-Shot Variant Chain (Sound_Design_Update.md)
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


**Free Throw** (one attempt per turn; `ft_step_emitter`)

Step 1: Lane setup (shooter → line; lane players → FT spots; gate = shooter)

Step 2: Shoot (shooter `shoot` / `shot_motion`; ball attached)

Step 3: Ball flight (`FREE_THROW_SHOT_GRID_PER_GAME_SECOND` = 12; SFX `free-throw-swish.wav` / `free-throw-miss.wav`)

Step 4a: Hold (final make) or return ball to shooter (non-final make)

Step 4b: Rim beat + bounce to `ball_bounce_x/y` (final miss) or return to shooter (non-final miss)

Final miss → discrete **DREB** or **OREB** turn (not embedded on FT row)

**Fast Breaks** (schema playback via `animation_steps`; legacy `fastBreak.js` until migrated)

## Covert Release (`covert_release_step_emitter`)
Step 1: Outlet pass (optional when rebounder == release player)
Step 2: Outcome (shot / defensive stop / foul / steal) → `turn_stop`
Step 3 (defensive stop only): implicit end → next HCO turn

## Rim Runner (`rim_runner_step_emitter`)
Step 1: Burst (RR + outlet receiver + secondary movers)
Step 2: Outlet pass (optional)
Step 3+: Branch — lane pass + shot | steal | bat OOB | hold-up | outlet denied

## Triangle (`triangle_step_emitter`)
Step 1–2: Burst + outlet pass (shared with Rim Runner)
Step 3: Triangle setup (BH / RR / corners / defenders to spots; "Fast Break!" announcement)
Step 4: Decision lead-in (branch pass or drive; skipped on `triangle_bh_wing_three`)
Step 5: Shot motion → `turn_stop: SHOT_ATTEMPT`
Branches: outlet denied / `triangle_enter_hco` reuse Rim Runner hold-up or denied steps


**Final Shot**

