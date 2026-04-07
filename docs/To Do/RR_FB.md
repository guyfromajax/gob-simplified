# RR Fast Break

## Purpose
Define the V1 Rim Runner Fast Break flow as a clear step-by-step process.

## Branch Ownership

- `rr.phase.burst` owns only burst movement and the outlet-result fork.
- `rr.phase.outlet_denied` owns the denied outlet sequence through pass receipt at the cut-back spot.
- `rr.phase.hold_up` owns the no-lane-pass settle through ball-handler arrival at the hold-up destination.
- `rr.phase.interception` owns the interception sequence through ball attach to the stealer.
- `rr.phase.bat_oob` owns the bat-out sequence through ball arrival at the out-of-bounds destination.
- Once one RR branch owner starts, the parent burst phase must not re-apply the original burst destinations afterward.

## Flow

1. Previous HCO shot attempt turn
- During shot-attempt resolution, backend calculates:
  - `get-back` players from the shooting team
  - whether a DREB Fast Break is eligible
  - the DREB Fast Break playcall
- The shot result is then resolved.
- If the result becomes a defensive rebound (`DREB`), the precomputed Fast Break trigger and playcall are used for the next turn.
- Current implementation note: DREB Fast Break playcall is currently Rim Runner.
- Advance Trigger: Yes — shot result is committed. (doc: No, code: Yes)

2. DREB -> RR Fast Break entry
- If Fast Break is not triggered, play routes to normal next-turn flow.
- If Fast Break is triggered, the next turn becomes `FAST_BREAK` with Rim Runner roles and data attached.
- Advance Trigger: Yes — `FAST_BREAK` route/turn is committed after the DREB outcome. (doc: No, code: Yes)

3. RR roles are assigned
- Backend identifies:
  - rebounder / outlet passer
  - rim runner
  - outlet receiver
  - outlet defender
  - get-back defenders
  - all other transition players
- Advance Trigger: Yes — RR role payload is fully resolved and attached to the turn. (doc: No, code: Yes)

4. RR burst phase is calculated
- Backend calculates movement targets for:
  - rim runner burst
  - outlet receiver movement
  - outlet defender movement
  - all other player transition movement
- Advance Trigger: Yes — burst-phase movement targets are fully resolved and attached to the turn. (doc: No, code: Yes)

5. Outlet pass result is calculated
- Backend resolves the outlet-pass contest.
- Result is one of:
  - `outlet denied`
  - `outlet completed`
- Advance Trigger: Yes — outlet-pass contest result is committed. (doc: No, code: Yes)

6. Outlet denied branch
- If the outlet is denied, the denial sequence is played.
- Branch owner: `rr.phase.outlet_denied`.
- The outlet receiver cuts back toward the passer while the other players continue their transition movement.
- The outlet passer identity must resolve deterministically for this branch.
- The actual passer sprite handed into the branch is the canonical passer authority for denied-pass execution; payload passer ids are advisory/fallback only.
- Outlet passer, outlet receiver, and outlet defender are excluded from drift during the denied sequence.
- The outlet receiver then receives the outlet pass at the cut-back spot.
- The denied branch must execute an actual outlet-pass receive at that cut-back spot; it must not degrade into a generic dribble-out fallback because the passer identity was lost.
- Once that denied-pass receive happens, the branch owns the live player positions; the parent burst phase must not re-apply the original burst destinations afterward.
- Play then settles into `HCO`.
- Current behavior remains an RR non-shot stop result.
- Advance Trigger: Yes — outlet receiver receives the denied-pass outlet at the cut-back spot. (doc: No, code: Yes)

7. Outlet completed branch
- If the outlet is completed, the outlet receiver gets the ball at the outlet target.
- Backend then evaluates whether the outlet receiver passes to the rim runner.
- Advance Trigger: Yes — outlet receiver receives the outlet pass at the outlet target. (doc: No, code: Yes)

8. RR lane-pass decision
- Backend calculates:
  - whether the rim runner is open
  - whether the outlet receiver makes the correct read
  - whether the outlet receiver actually throws the pass
- Advance Trigger: Yes — lane-pass decision is committed (`pass` / `no pass`). (doc: No, code: Yes)

9. No lane pass branch
- If the outlet receiver does not pass to the rim runner:
- Branch owner: `rr.phase.hold_up`.
  - the outlet receiver holds up
  - the other 9 players continue moving toward the offense basket
- The advance trigger for this branch is the moment the ball handler reaches the hold-up destination.
- At that moment, all other drift movement is stopped, those stopped drifts are not awaited, and play hands off to normal `HCO` setup from live carried-over positions.
- Play then settles into `HCO`.
- Advance Trigger: Yes — ball handler reaches the hold-up destination. (doc: Yes, code: Yes)

10. Lane pass branch
- If the outlet receiver passes to the rim runner, backend resolves the pass result.
- Branch owner: result-specific RR branch owner (`rr.phase.shot`, `rr.phase.interception`, or `rr.phase.bat_oob`).
- The lane-pass sequence uses the rim runner's committed post-burst position as the starting point for the receive action.
- Result is one of:
  - rim runner receives and shoots
  - defender intercepts
  - defender knocks the ball out of bounds
- Advance Trigger: No — this branch splits into result-specific advance triggers. (doc: Yes, code: Yes)
- Successful pass -> shot attempt: Yes — use the existing shot-attempt policy `shot release/result committed`. (doc: Yes, code: Yes)
- Interception: Yes — moment the ball attaches to the intercepting player's sprite. (doc: Yes, code: Yes)
- Ball knocked out of bounds: Yes — moment the ball reaches the out-of-bounds destination. (doc: Yes, code: Yes)

11. Turn resolution
- RR shot outcome resolves through normal shot resolution.
- RR non-shot defensive outcomes route to the correct next turn:
  - `HCO`
  - or `SIDE_INBOUND`
- Advance Trigger: Yes — final outcome/next-turn route is committed. (doc: No, code: Yes)
