# Situational Logic (Q4/OT)

**Score Delta** = Offense Team Score − Defense Team Score (zero in the case of a tie).

All logic below applies only when **quarter ≥ 4**. Evaluate the time-band table first to determine Slow It Down, Quick Shot, shot ratios, and Force Foul; then apply Execution.

---

## Time-band table (source of truth)

**Time Remaining 2:01 – 3:00**
- If Score Delta ≥ 12 → Slow It Down = True
- Else if Score Delta < -12 and > -24 → Quick Shot = True  
  - Outside Shot Chance = 60%, Attack = 20%, Inside = 20%
- Force Foul = False

**Time Remaining 1:01 – 2:00**
- If Score Delta ≥ 9 → Slow It Down = True
- Else if Score Delta < -9 and > -18 → Quick Shot = True  
  - Outside = 70%, Attack = 20%, Inside = 10%
- Force Foul = False

**Time Remaining 0:31 – 1:00**
- If Score Delta ≥ 3 → Slow It Down = True
- Else if Score Delta < -3 and > -12 → Quick Shot = True  
  - Outside = 80%, Attack = 15%, Inside = 5%
- Force Foul: True if 3 < Score Delta < 12, else False

**Time Remaining 0:01 – 0:30**
- If Score Delta ≥ 1 → Slow It Down = True
- Else if Score Delta < -1 and > -9 → Quick Shot = True  
  - If Score Delta < -2: Outside Shot Chance = 100%  
  - Else: run normal playcall logic
- Force Foul: True if 0 < Score Delta < 9, else False

When Score Delta falls in neither Slow It Down nor Quick Shot for that band → use normal logic (no tempo or shot overrides).

---

## Slow It Down / Quick Shot Execution

**When Slow It Down applies (per time-band table):**
- Calculate Force Foul at the BIP or SIP step if applicable; otherwise at the very beginning of the HCO step.
- If Force Foul = True: defense commits a foul immediately on the pass receiver of the BIP/SIP pass (pass must be animated first), or at HCO on the last rebounder; `time_elapsed = random.randint(1, 3)`; process next step accordingly (goal: get to bonus and force free throws).
  - The player being fouled is the offense player receiving the inbound pass on BIP & SIP steps, or the offense player who holds the ball entering the HCO step (no passes); the fouling defender is the defender closest to the player being fouled at the moment of the foul.
  - Foul animation: move the defensive fouling player's sprite to the offensive player being fouled sprite, execute the announcement system with the fouling player image and text "Quick Foul".
- If Force Foul = False: proceed to next step.
- Override Offense Team’s Fast Break setting to 0 (temp override; revert when Slow It Down no longer applies).
- Next step (if Force Foul = False): offense tempo = "slow".

**When Quick Shot applies (per time-band table):**
- Offense tempo = "fast".
- Play focus / shot chances = per time-band table (Outside / Attack / Inside ratios, or 100% outside / normal logic in 0:01–0:30 as specified).
- Override Defense Team's FCP & HCT settings to 0 (temp override; revert when Quick Shot no longer applies).

Temp overrides (Fast Break, FCP, HCT) are re-evaluated each turn and revert when the situation no longer applies.

---

## Force Foul Execution

**Force Foul after inbound:** When Slow It Down + Force Foul apply, we set a pending Force Foul after each BIP or SIP. On the next turn we **run the Force Foul first** (before any state routing). That way the foul is executed whether the next step would have been HCO, HCT, or FCP—and we avoid running next-turn choice logic (e.g. HCO vs HCT vs FCP) when it would only be overwritten by the foul result.

**Force Foul after DREB:** On a defensive rebound (HCO shot miss → DREB), we **evaluate Force Foul immediately**. If Slow It Down + Force Foul apply, we execute the foul right away: we do not run the normal “next step” logic (no Fast Break vs HCO decision, no outlet pass). The victim is the last rebounder; the fouling defender is the defender closest to that rebounder. We inject a FOUL turn and then enter the standard defensive non-shooting foul flow (possession flip, SIDE_INBOUND or FREE_THROW). Animation: no outlet pass; on the FOUL turn we animate the defender moving to the rebounder and announce “Quick Foul.”

## Announcement System

Situational and result announcements are driven by a central game announcement system. At **turn start** (during turn preparation, before animation), the following context announcements may be shown based on turn data:

- **Fast Break** — when the turn is a fast break (and not steal-initiated).
- **Press!** / **Trap!** — when a baseline inbound is setting up FCP or HCT (defense).
- **Slow It Down** / **Quick Shot** — when an HCO turn has Slow It Down or Quick Shot set (offense).
- **Final Shot** — when the turn is a Final Turn shot attempt (offense). Not shown for FINAL_HOLD (hold until 0).

At **turn end** (or at specific animation moments), the system announces shot results (e.g. "It's Good!", "Shooting Foul!"), fouls ("Quick Foul", "CHARGE!", "BLOCKING FOUL!", etc.), rebounds, steals, and turnovers. Force Foul animations use the announcement system with the fouling player image and text "Quick Foul" as described in Force Foul Execution above.

---

## Final Turn Execution

**Trigger:** The first possession with `time_remaining ≤ 30` seconds that is **not** OREB and **not** Fast Break (i.e. state is HCO, HCT, or FCP) is eligible for Final Turn. Only one Final Turn is triggered per quarter/OT (`final_turn_triggered_this_period`). The *next* turn after an OREB or Fast Break (when time is still ≤ 30 and quarter ≥ 4) is the one evaluated for Final Turn.

**Qs 1–3:**
- The first team to take possession of the ball with ≤ 30 seconds remaining will hold for the final shot, so time_elapsed will be equal to time remaining.
  - This applies to all turn types except OREB and Fast Break. OREB and Fast Break will execute as normal.
  - If the result of a Final Turn turn is a Shot Attempt, it will use the entire time remaining as time elapsed, the team will shoot, and the quarter will end afterward. Note: if there is a shooting foul, the free throw(s) will run as normal then we'll enter Quarter Break.
  - Note: for future instances there may be an offensive foul, non-shooting defensive foul, steal, or dead ball turnover, but for now, those will not be possible.
  - **Starting Alignment:** The offense and defense will both enter "Final Turn State", with locations defined below:
    - Offense positions for Final Turn State setup:
      - Randomly choose ball handler: 60% chance PG, 30% SG, 10% SF.
        - If SF is ball handler, then flip his placement logic below with SG, so the ball handler always starts at either deep upper wing or deep lower wing.
      - PG: deep lower wing or deep upper wing (chosen at random).
      - SG: deep lower wing or deep upper wing (whichever the PG does not line up at).
      - SF / PF: each randomly assigned to one of upper corner, lower corner, upper midCorner, lower midCorner (note: one must be in an upper location and one must be in a lower location).
      - C: key.
    - Defense lines up in a 2-3 zone or 3-2 zone (chosen randomly).
  - **Play Execution:**
    - Shot choice will be chosen at random: 50% outside, 50% Attack.
    - Shooter will be chosen at random:
      - If Outside, each player will be ranked according to their SH Attribute (if two players are tied, rank them randomly): #1: 50% chance, #2: 30%, #3: 20%, #4: 9%, #5: 1%.
      - If Attack, each player will be ranked according to the sum of their SC + AG Attributes (if two players are tied, rank them randomly): #1: 50% chance, #2: 30%, #3: 20%, #4: 9%, #5: 1%.
      - The shooter moves to the wing on the vertical half of the court of his starting spot (if he's in an upper spot, he goes to upper wing; if he's in a lower spot, he goes to lower wing). If he's the C, he chooses lower wing or upper wing at random.
      - If the shooter is the ball handler, he dribbles to that wing location. If he's not the ball handler, he moves to his location, then the ball handler passes the ball to him.
        - If the ball handler and shooter are on the same vertical half of the court, they stay on that half. If they are on opposite vertical halves, the ball handler will dribble to the deep key then execute the pass.
        - As the ball handler and shooter move to their spots during this step, the other 3 or 4 players (all except ball handler and shooter) will move to one of the following locations on the opposite vertical half. So if the shooter is at the upper wing, all other players move to spots at lower, and vice versa for lower wing.
          - Locations: midWing, wing, midCorner, corner, deep wing, deep baseline.
          - Two or more players cannot occupy the same spot.
        - **Explicit:** When the ball handler is not the shooter, he moves to **deep key** (not key) before the pass; all other offensive players (the 3 or 4 who are neither ball handler nor shooter) move to random, distinct spots on the opposite vertical half from the shooter’s wing, from the set: midWing, wing, midCorner, corner, deep wing, deep baseline.
        - **Outside shot:** With 3–5 seconds remaining, the shooter attempts his shot from the wing (one step: shoot at wing). Same animation pipeline as Motion outside.
        - **Attack shot:** The shooter executes two steps, reusing Motion offense logic: (1) **Drive destination** is chosen from the shooter’s current position (the wing — upper or lower) using the same rules as Motion (`_determine_attack_drive_destination`). (2) **Drive to basket:** shooter moves to that destination (e.g. upper lowPost, basketSpot). (3) **Shot attempt:** shooter releases from that spot. The skeleton therefore has two extra steps (drive, then shoot) for the shooter only; the same skeleton-to-animation pipeline and frontend step loop as Motion attack are used, so no separate animation path.
          - Note: the detail of the shot being attempted with 3–5 seconds remaining is irrelevant now, but it will be relevant once we adjust the game engine to count down the clock in real time instead of in chunks turn by turn like we do now.
      - Execute the shot via our standard shot attempt logic, and process the result as we do all shot attempts with 0 seconds remaining in the quarter. Process Make or Miss; if no shooting foul the quarter ends; if Charge on attack shot, the quarter ends; **if blocking foul on Final Turn attack shot, award exactly two free throws (no and-1, no 3 FTs for a three-point attempt)**; if shooting foul, the quarter ends with the number of free throw(s). After the shot (or FTs if shooting foul), quarter ends and game ends if it is the final period.
  - **Alignment (backend + frontend):** The backend sends `oDestinations` and `dDestinations` in a single convention (home-side coordinates only). The frontend applies the same rule as all other setups: **one attacking side, both teams there; flip only when away offense.** When the away team is on offense, the frontend flips both offense and defense positions so the whole setup is on the away (attacking) half; when the home team is on offense, no flip is applied.
  - **Announcement:** "Final Shot" is announced at the start of a Final Turn shot attempt (see Announcement System); not shown for FINAL_HOLD.

- **Final play of the quarter (post-shot behavior):** When the Final Turn shot (or the last free throw after a Final Turn shooting foul) ends the period, the following applies. The backend marks the turn with `quarter_ends_after` and does **not** create a follow-up turn (no BIP, no rebound turn). The frontend then holds, announces if applicable, and runs the existing quarter-end flow without requesting or animating a next turn.
  - **Final Turn shot (make):** Backend does not create or append a BASELINE_INBOUND turn. Frontend: after the shot animation completes, hold the ball at the rim for **3 seconds**, announce **"It's Good!"** (reuse existing announcement), then end the quarter. No BIP; no players moving to inbound; everyone stays in place.
  - **Final Turn shot (miss):** Backend does not set `pending_oreb` and does not create or append a DREB or OREB turn (no rebound animation or follow-up). Frontend: after the shot animation completes, hold the ball at the bounce spot for **3 seconds**, then end the quarter. No rebound turn is requested or animated.
  - **Final Turn shooting foul:** Free throw(s) run as normal. After the last free throw, backend does not create BIP when the quarter ends (`time_remaining == 0`). Frontend: after the last FT animation, hold for **3 seconds**, then end the quarter (no BIP). Config: `finalTurn.holdFinalShotMs` (default 3000 ms) controls the hold duration for these cases.

**Q4 (and OT):**
- If Slow It Down is true and Force Foul is false: produce a **FINAL_HOLD** turn. The offense and defense get into Starting Alignments, and the offense holds the ball until the clock reaches 0 (`time_elapsed = time_remaining`). No shot is attempted. Quarter (or game) ends after this turn.
- If Slow It Down is true and Force Foul is true: execute the Force Foul (existing logic); no special Final Turn alignment for that possession.
- If Quick Shot: treat as a normal quick shot turn (no Final Turn alignment or play execution).
- If not Slow It Down, and not Quick Shot, and not Force Foul: treat as the same final shot logic as above (trailing or tied; a team leading should never enter this instance).
