**HCT Turn Logic**
-Note 1 that all coords listed below are in home on offense orientation, we'll need to flip coords for away on offense orientation.
-Note 2: we use the same ball handeler + pos1, pos2 pos3, pos4 assingments as we use for target shooter + pos1, pos2, pos3, pos4 logic to assing positions. LMK if you need me to explain.

##Goals
-Defense's goal: get teh ball and two ball handler defenders into a position to execute a trap
-Offense's goal: get the ball past x 64 and either attempt a shot within the HCT turn (first goal) or transition to HCO turn (secondary goal)

##Offense Goal Spots##
-Primary/Safe: x: 57-64 and y: 22-28 (perfect spot: x: 60, y: 25)
-Secondary: x: 64 to basket x and y: 10-30
-Situtional: any x > 64 and any y if number of defenders with x coord > 64 == 0 or 1

##Defense Goal Spots
-Pirmary: x: 50 - 57 and (y < 10 or y > 40)
*Defense will execute a trap in this sitiion if two defenders are within trap distance of the ball handler
-Secondary: x: midCorner spot x or greater and (y < 10 or y > 40)
*Defense will execute a trap in this sitiion if two defenders are within trap distance of the ball handler

#Step Logic
-step 1: the ball handler brings the ball up teh court until he reaches a x spot 44 where he'll assess teh situation
    - ball handler receives the BIP pass and he holds stationary for one game second while the other 9 players move up the court, then the ball handler also moves up the court. He moves at our standard game aniation pace (tell me approx how many game seconds this will take)
    -the defenders targer their starting position for the HC Trap. One note, the defensive PG targets the exact center court spot
    -the four non bh offenders will target spots within ranges as follows:
        -pos 1: x spot between upper wing and deep upper wing, y spot between upper deep baseline and upper deep wing
        -pos 2: x spot between lower wing and deep lower wing, y spot between upper lower deep baseline and lower deep wing
        -pos 3: x spot between lower apex and lower wing, y spot between lower midPost and lower midCorner
        -pos4: x spot between upper apex and upper wing, y spot between upper midPost and upper midCorner
-step 2 (instigation point 1): once teh ball handler reaches x 44 (have him target a random y in range 21-29), the defesnive PG will come to meet him, defender will target x 46 and ball handler's y
    -ball handler makes a decision -- he either chooses to attack the middle or pick a side and pass to a teammate. The defender's goal is to get him to pick a side and pass to a teammate. The offender's main goal is to protect the ball with teh secondary goal of attacking the middle IF it is optimal (let's make the optimal read a pure 50/50 for now -- 50% chance it's attack and 50% chance it's pass)
    -ball handler read score. If > 190, he chooses optimal, otherwise he chooses random
-step 3
    -if attack, we calculdate the defender's outside defesne score and the ball handlers ball handlings core.
        -outside d score = calculate_defender_pressure_score value + (defense team's pt efficiency attribute value * random.randint(1,6))
        -ball handling score = calculate_ball_handling_score value * (offense team's pt opp modifier value * random.randint(1,6))
        -if d score > o score: positive d outcome
            -ball handler commits a dead ball turnover (double dribble or travel) and we enter our dead ball turnover announce and next step progression (will expand this in the future)
        -elif o score >= d score: positive o outcome
            -ball handler dribbles across half court and to the deep key spot, then we transition to HCO turn (will expand this logic later)

-



##Goal Achievement
-if offense gets ball past x 64 they will either attmmpt a shot or tranistion to HCO
*Defender count = # of defenders with x coord > 64
*Offender count = # of offenders with x coord > 64
*if Offender count > Defender count: shot attempt = optimal option, else HCO transition = optimal option
*Ball hanlder makes a read via the player_read helper. 
    - if read > 190, player makes correct read/choice else he makes a random read/choice
    -if choice == hco transition
        -if player is the ball handler for step 0 of the HCO play turn, he backs up to a ranomly chosen spot from (deep key, deep upper wing, deep lower wing), while the other four offensive players move to a random spot as follows (x range: 64-84, y range 26-45 if currenty y coord > 25, else y range 5-25)
        -else ball hanlder moves to a randomly chosen spot from (deep key, deep lower wing, deep upper wing) and the step 0 ball handler moves to a spot within 5 x coord and 5 y coords of him -- the other 3 offensvei players behave as above
        -the five defenders move to a random spot with x range 70-90 and the same y logic as the offensive players
        - this step ends when both the current ball handler and step 0 playcall ball handler (i.e. pass reciever) reach their spots, we hold for 2 game seconds, the ball is passed to teh step 0 ball handler. Then no matter where players are, we stop animation for this turn and progress to step 0 of the HCO playcall
    -if choice = shot attempt, teh ball handler has three options
        - attempt an outside shot from his location, drive to the basket from his locaiton, pass to a teammaate who has x > 64. 
            -if defender count = 0, this choice will always be to drive, or pass to a teammate who is closer to the basket, else we'll use optiomal logic
        -optimal logic
            -if ball handler SH > 80, optimal = shoot, elif ball handler SC + AG > 105, optimal = drive, else optiml = pass
            - if ball handler chooses to drive, he drive target spot will be as follows based on ball handlers starting y coord
                -y > 30, upper low Post, y < 20, lower lowPost, else basketSpot
                -any teammaates with x  64 will target a spot from this list, excluding the driver's target (lower lowPost, upper lowPost, midLane, upper midPost, lower midPost, upper midBaseline, lower midBaseline)
                    -upper/lower locations logic will be the same as teh ball handler's logic -- all temmates can targetthe midLane. Teammatess cannot taget teh same location
                -if teh ball handler has teammages in any of those locations, 50% chance he shoots (attack shot) and 50% chance he passes to a teammate
                    -if he passes to a teammate that teammate will shoot (inside shot)
            -ball handler makes a read score, if read > 190, he chooses the optimal option, esle he chooses a random option
            -defenders behave in standard manner in an attempt to get into position to defend the shot
            -it is parmoutn tht we track defenders' locations at the exact moment of the shot attempt (we've been trying to do this elsewhere in the code and we're failing miserbly, it's been extremely spotty and inconssitent at best). If a defender is within 4 x spots and 6 y spots of teh shooter, thy will be the shot defender
            -all defenders will target a spot within the range of basket x to midLane x -3 and y spot within +6 to -6 y spots of the basket y spot

##Special Situations
-if the offense does not cross half court (x 50) within 10 seconds, it is a 10-second violation. the turnover is credited to the ball handler at the moement of the turnover. We can evaluate this via the shot clock If the shot clock reaches 25 nd the ball handler's x coord < 50 (home offense) or > 50 (away offense) then we announce "10-Second Violation" via our announcement system and run our standard dead ball turnover logic, executing a possession change and transitioning to SIP turn.









**Standard HC Trap**
**HC Traps are designed to get two defenders on teh ball handler during a shift
**When two guys are guarding teh ball handler we need each to be 1-4 xspots ahead fo the ball handler toward the basket, one to be +2 y spots avoe ball handler y, the other to be -2 y spots belwo teh ball handler y. We annot have defenders sitting on top of each other.
**Trap is broken and we enter HCO turn once the offense reaches x 73 if home offense, or x 27 if away is offense, and the offense has not attempted a shot on the HCT turn, and thre have been no turn ending events (o foul, d foul, steal, dead ball turnover)

##Zone Definitions##
Normal
PG: center court, deep key, deep upper wing, deep lower wing, key
SG: deep upper baseline, deep upper wing, upper wing
SF: deep lower baseline, deep lower wing, lower wing
PF: topLane, upper apex, lower apex, upper higPost, lower highPost
C: midLane, upper midPost, lower midPost, basket spot, upper low post, lower low post

Upper Shift
PG (guarding ball hadler): min x value of 54 (max x value of 46 is away is on offense)
SG (guarding ball handler): min x value of 50
SF: deep key, key
PF: upper apex, upper highPost
C: midLane, upper midPost, upper lowPost, basketPost, lower lowPost, lower midPost

Lower Shift
PG: (guarding ball hadler): min x value of 57 (max x value of 43 is away is on offense)
SG: deep key, key
SF: (guarding ball handler): min x value of 50
PF: upper apex, upper highPost
C: midLane, upper midPost, upper lowPost, basketPost, lower lowPost, lower midPost

Shift Triggers

Lower Shift; ball handler y < 20

Upper Shift: ball handler y > 30




**Question Tracker**

Maintained as we implement. Sections:
- **Open (first-cut blockers)** — must resolve before each next implementation step.
- **Open (deferred / post-first-cut)** — known gaps to revisit when we expand scope.
- **Answered** — preserved with brief notes for context.

---

## Open — first-cut blockers

(Empty — first-cut implementation landed. Open the section as new gaps surface during testing.)

## Open — deferred / post-first-cut

These will block subsequent cuts but not the first one. Re-open as we widen scope.

- **D2.** Pass-to-side branch of step 2: full sequence (which teammate, what y range, what timing). The "read" gate (player_read > 190) returns here once the branch exists.
- **D3.** x=64 transition trigger logic + BH read at x=64 (shot vs HCO transition).
- **D4.** Shot-attempt branch decision tree: SH > 80 / SC+AG > 105 / pass-with-teammates. Drive target by y. Inside-spot teammate assignment.
- **D5.** Rim-protection cluster: defenders relocate to (x∈[77,87], y∈[19,31]) when shot-attempt branch is engaged. Movement pace + collision handling.
- **D6.** Defender shot-defender heuristic at shot moment (within 4 x / 6 y). User flagged prior implementations as "spotty"; need to specify which existing path was failing so we don't repeat the bug.
- **D7.** HCO playcall handoff: which playcall, where step-0-BH starts vs current end coords, who computes the HCO step-1 movement vs HCT's tail.
- **D8.** Foul / steal emergent outcomes (currently first cut emits only DEAD BALL or HCO).
- **D9.** 10-second violation gate (constant defined; runtime check not yet wired). User confirmed: shot clock reaches 20 (10 sec elapsed from 30) AND BH hasn't crossed x=50 → "10-Second Violation" announcement → SIP.
- **D10.** Trap-break trigger (x=73 / x=27): still on the books but currently superseded by the x=44 instigation point + step 3 outcome.
- **D11.** Pass interceptions mid-flight (stolen pass).
- **D12.** Per-tick energy decay vs. once-per-turn.
- **D13.** Determinism / seeded RNG for replays.
- **D14.** Distant sim path: skips animation today; dynamic HCT will need a "decisions only, no movement" short-circuit for franchise CPU sim.
- **D15.** When does step-2 movement of *other* defenders / offensive teammates kick in (deferred for first cut; user said only PG-defender moves in step 2).
- **D16.** Result-type stats parity: first cut updates HCT used/success and BH TO stat. Confirm box-score / scouting / season totals don't drift vs. skeleton path.

## Answered

1. **Tick / step model** — discrete step gates, not a fixed cadence. Each step ends on a defined trigger; movement waypoints inside a step animate at the standard ~800ms granularity. ✓
2. **Initial state** — HCT enters from BIP. BIP skeleton drives the inbound; dynamic HCT takes over from the BH's post-BIP coords. ✓
3. **Offensive movement before x=64** — BH advances at challenged-open-floor pace (16 units/sec) toward (44, target_y in 21-29). Other 4 offenders move toward pos1-4 ranges (geometric, mapped by `_build_set_play_alias_map`-style alias). ✓
4. **Defense behavior** — defenders target zone-Normal centroids in step 1 (defensive PG override = exact center court). Trap engages at step 2 via PG-defender converge. ✓
5. **End conditions (first cut)** — DEAD BALL → SIP; HCO → HCO turn. Other end conditions deferred. ✓
6. **x=73 vs x=64** — first cut works at x=44 (instigation point 1). Both x=64 and x=73 deferred. ✓
7. **Foul / steal integration** — DEAD BALL is emergent from a contested score formula at step 3. Other outcomes deferred. ✓
8. **Read frequency** — at instigation points only; one read per point (deferred for step 2's first cut). ✓
9. **Defender count == 0 override** — deferred (post-first-cut). [originally Tier-2 question]
10. **Optimal shot/drive/pass** — deferred; SC+AG > 105 confirmed as a sum. [originally Tier-2]
11. **Inside-spot teammate movement** — deferred. [originally Tier-2]
12. **50/50 shoot-vs-pass branch** — deferred. [originally Tier-2]
13. **Movement pace constants** — exist in `BackEnd/constants/__init__.py`: `CHALLENGED_OPEN_FLOOR_GRID_PER_GAME_SECOND` (16) for HCT advance, `ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND` (12) for drive-pace dribble. Confirmed. ✓
17. **Game clock / shot clock** — game seconds confirmed for the 1-sec hold; clock runs per step using `step_clock_seconds`. ✓
20. **Read threshold 190** — intentional 50/50-ish gate for average IQ/CH players. ✓
21. **Coord orientation** — home-on-offense orientation; flip via `get_away_player_coords` when away offense. Same convention as zone constants. ✓
23. **BH stuck** — addressed via 10-sec violation when wired (D9). ✓
25. **Energy decay** — applied once at HCT entry (existing scaffolding preserved in dynamic path). ✓ (per-tick decay deferred — D12)
26. **Stat tracking parity** — first cut maintains HCT used/success counters + ball-handler TO stat. Full parity check open (D16). ✓
27. **BH selection** — always PG for first cut (BIP receiver). Future: personnel/scouting-driven. ✓
A (BH starting position) — comes from BIP receive coords (player.coords post-BIP). ✓
B (defender step-1 targets) — zone-Normal centroids; defensive PG → exact center court. ✓
C (movers post-1-sec) — keep moving toward target until they arrive OR until BH reaches his target (whichever comes first). ✓
D (step-2 movers) — only defensive PG; other 9 hold (first cut). ✓
E (step-2 trigger) — fires when BH arrives at his exact target (x=44, target_y). ✓
F (step-2 read timing) — instant when defensive PG and BH meet. ✓
G (step-3 dead-ball animation) — BH animates to a random point along his path to deep key, defender follows, announce at that point. ✓
H (HCO handoff — first cut) — other 9 hold positions through step 3; HCO step 0 will animate them to setup positions in the next turn. ✓
I (pass-to-side) — deferred (D2). ✓
J (10-sec violation) — shot clock = 20, BH hasn't passed x=50; deferred to runtime wiring (D9). ✓
K (BH = PG) — first cut only. ✓