## Triangle Fast Break

## Purpose
Define the Triangle Fast Break as a UESS-ready Fast Break play family that plugs into the shared Fast Break framework while using its own phase graph, targets, and decision branches.

Triangle is a derivative of the Rim Runner Fast Break:
- it uses the same DREB entry path
- it uses the same outlet contest / outlet-denied behavior
- it uses the same RR lane-pass read logic first
- only after the outlet succeeds and the outlet receiver chooses not to throw the RR lane pass does Triangle-specific structure begin

## System Structure

Triangle should not be implemented as a fully bespoke disconnected Fast Break stack.

It should live inside the universal Fast Break turn framework:
- shared Fast Break routing
- shared UESS contract rules
- shared carry-forward snapshot rules
- shared shot-resolution handoff

But Triangle has its own play-specific phase graph:
1. `triangle.phase.entry`
2. `triangle.phase.rr_read`
3. `triangle.phase.setup`
4. `triangle.phase.decision`
5. `triangle.phase.finish`

This is the recommended long-term Fast Break architecture:
- one universal Fast Break system
- different phase maps per Fast Break play

## Location Labels

Triangle uses the existing `HCO_STRING_SPOTS` labels in [`BackEnd/constants/__init__.py`](/Users/jamesdavies/gob-simplified/BackEnd/constants/__init__.py).

Required labels for this play:
- `upper corner`
- `lower corner`
- `upper wing`
- `lower wing`
- `upper lowPost`
- `lower lowPost`
- `upper midPost`
- `lower midPost`
- `upper highPost`
- `lower highPost`
- `topLane`
- `midLane`
- `basketSpot`
- `upper apex`
- `lower apex`
- `upper bird`
- `lower bird`

## Phase Ownership

- `triangle.phase.entry` owns RR-style DREB entry, outlet receiver placement, outlet contest, and outlet result fork.
- `rr.phase.outlet_denied` still owns the denied outlet branch.
- `triangle.phase.rr_read` owns the post-outlet RR lane-pass read.
- `triangle.phase.setup` owns Triangle offensive/defensive target movement after the RR lane pass is declined.
- `triangle.phase.decision` owns the ball handler’s Triangle decision tree.
- `triangle.phase.finish` owns the resulting pass/shot/HCO handoff branch.

Once one Triangle phase hands off to the next:
- prior phases must not re-apply old destinations
- live carried-forward positions remain authoritative

## Flow

1. Previous shot turn
- During the prior HCO or FT miss that becomes a DREB Fast Break, backend resolves Fast Break eligibility and the selected Fast Break play.
- If the selected play key is `triangle`, the next turn becomes `FAST_BREAK` with Triangle routing metadata.
- Advance Trigger: Yes — Fast Break route and `triangle` play selection are committed.

2. `triangle.phase.entry`
- Run RR burst, outlet receiver placement, outlet defender movement, and outlet pass result exactly the same as the Rim Runner Fast Break.
- If outlet is denied:
  - run the same denied-outlet comeback branch as RR
  - then enter `HCO`
- If outlet succeeds:
  - proceed to `triangle.phase.rr_read`
- Advance Trigger:
  - denied branch: outlet receiver receives the denied-pass comeback pass
  - successful outlet branch: outlet receiver receives the outlet pass at the outlet target

3. `triangle.phase.rr_read`
- Calculate `fb_open` the same way RR does, except with a stricter threshold.

Current formula:
- `burst_offense_score` is calculated the same way as RR
- `burst_defense_score` is calculated the same way as RR
- `fb_open = (burst_offense_score * 0.6) > burst_defense_score`

- Calculate `correct_read` the same way as RR.
- Calculate `pass_attempted` the same way as RR.

Branch result:
- if `pass_attempted = True`:
  - execute the RR pass attempt and downstream result exactly the same as RR
- if `pass_attempted = False`:
  - proceed to `triangle.phase.setup`

Advance Trigger:
- Yes — RR read decision is committed (`pass_attempted = True` or `False`)

4. `triangle.phase.setup`

### Offensive targets

The two offensive players who are not:
- the rim runner
- the outlet receiver / ball handler
- the rebounder / outlet passer

become the Triangle corner players.

#### Corner players
- both corner players use RR burst movement
- one targets `lower corner`
- one targets `upper corner`
- assignment rule:
  - the player with the lower starting `y` targets `lower corner`
  - the other targets `upper corner`
  - if starting `y` is tied, assign corners randomly

#### Ball handler
- non-burst movement
- if current `y > 25`, target `upper wing`
- else target `lower wing`

#### Rim runner
- non-burst movement
- target the low post on the same half as the ball handler’s wing:
  - `upper wing` -> `upper lowPost`
  - `lower wing` -> `lower lowPost`

#### Trailer
- the rebounder / outlet passer is the trailer
- non-burst movement
- target the wing opposite the ball handler’s wing:
  - if BH targets `lower wing`, trailer targets `upper wing`
  - if BH targets `upper wing`, trailer targets `lower wing`

### Defensive targets

All five defenders perform transition defense movement.

#### Defender assignments
- the defender closest by `x` to the offensive basket picks up the rim runner
- the defender second-closest by `x` to the offensive basket picks up the ball handler
- both of those defenders use skeleton HCO man-matchup placement logic

#### Remaining defenders
- the other three defenders target lane locations at random
- possible lane targets:
  - `lower lowPost`
  - `upper lowPost`
  - `lower midPost`
  - `upper midPost`
  - `lower highPost`
  - `upper highPost`
  - `basketSpot`
  - `midLane`
  - `topLane`
  - `lower bird`
  - `upper bird`
  - `lower apex`
  - `upper apex`

#### Burst modifier
- if defense team `fb_opp_modifier > 5`:
  - any non-get-back defenders use RR burst movement during this phase
- otherwise:
  - all defender movement in this phase is non-burst

### Assignment persistence
- the defender matched to the rim runner keeps tracking the rim runner’s assignment into Step 4 branches
- the defender matched to the ball handler keeps tracking the ball handler into Step 4 branches
- the other defenders:
  - continue moving to their original assigned target if not there yet
  - or hold their ground if already there
- if a shot is missed, all defenders participate in location-based rebound resolution as usual

Advance Trigger:
- Yes — the rim runner and the ball handler both reach their Triangle setup spots

5. `triangle.phase.decision`

The ball handler makes a Triangle decision after setup.

Decision roll:
- `decision = random.randint(1, 8)`

Branch table:
- `1` or `2`:
  - ball handler passes to the rim runner at the lowPost
  - rim runner attempts an inside shot via standard shot resolution logic
- `3`:
  - ball handler waits for the corner player on the same half as the BH wing to reach that corner
  - then passes to that corner player
  - corner player attempts a 3-point outside shot via standard shot resolution logic
- `4`:
  - ball handler shoots a 3 from his wing location via standard shot resolution logic
- `5` or `6`:
  - ball handler drives to the lowPost on the same half as his wing
  - rim runner moves to `midLane`
  - once BH reaches the lowPost, `drive_decision = random.randint(1, 5)`
    - `1` or `2`:
      - BH attempts an attack shot via standard shot resolution logic
    - `3` or `4`:
      - BH passes to the rim runner at `midLane`
      - RR attempts an inside shot via standard shot resolution logic
    - `5`:
      - BH passes to the corner player on the same half
      - corner player attempts a 3-point outside shot via standard shot resolution logic
- `7` or `8`:
  - enter `HCO`

### Additional branch rules

#### Rim runner location persistence
- for all non-drive branches:
  - RR remains at his lowPost location from `triangle.phase.setup`
- only the drive branch moves RR to `midLane`

#### Trailer persistence
- the trailer remains at the opposite wing unless interrupted by a later branch or the HCO handoff

#### Drive branch timing
- if BH drives:
  - the Step 4 decision is committed once the BH reaches the lowPost
- RR should already be at `midLane` by the time the drive-pass branch is available
- on drive-kick:
  - pass to the corner can be thrown in motion
  - no wait-for-corner-arrival requirement

Advance Triggers by branch:
- HCO branch:
  - same-half corner player reaches his corner location
- all non-HCO shot branches:
  - use shot-attempt advance trigger policy
  - `shot release/result committed`
- all pass branches leading into those shots:
  - pass reception

6. `triangle.phase.finish`

### Shot-defender rule for corner-player 3s
- only calculate a shot defender if a defender is within Euclidean distance `6` of the shooter

### Corner-player 3 custom override
- if there is no shot defender on a Triangle corner 3:
  - calculate the shot score as normal
  - use a Triangle-specific custom make threshold:
    - shot is good if `shot_score > (190 - offense_team.fb_efficiency)`
    - otherwise the shot is missed
- if there is a shot defender:
  - use standard shot resolution logic

### All other shots
- standard shot resolution logic

Advance Trigger:
- Yes — same as the underlying shot or pass branch trigger

7. HCO carry-forward rule

If Triangle enters `HCO`:
- player live positions at the moment the HCO decision is committed become the carry-forward positions for HCO step 0 start
- do not teleport players to new setup origins before HCO

If the current ball handler is not the PG:
- once the PG reaches his HCO step-0 location
- animate a pass from the current ball handler to the PG
- then continue normal HCO setup completion

If the current ball handler is the PG:
- continue into normal HCO setup without this extra pass

Advance Trigger:
- Yes — same-half corner player reaches his corner location, then HCO handoff begins from live carried state

## UESS Requirements

Triangle must obey the existing UESS dynamic-event contract.

For each Triangle phase:
- required movers must be explicit
- target destinations must be explicit
- movement profile must be explicit
- advance trigger must be explicit
- carried-forward snapshot must use live positions at the phase boundary

Triangle should therefore be implemented as:
- one Fast Break play family inside the universal Fast Break system
- not as a disconnected bespoke animation stack

## Implementation Notes

- RR entry behavior should be reused where possible rather than duplicated.
- RR denied-outlet branch should remain owned by the existing denied branch owner.
- Triangle-specific logic begins only after a successful outlet and a `no pass to RR` outcome from the RR read.
- Corner bursts use the same burst behavior as RR burst.
- Non-burst Triangle movement uses the current Fast Break non-burst duration.
- Triangle should be added to the canonical Fast Break System doc after implementation.
