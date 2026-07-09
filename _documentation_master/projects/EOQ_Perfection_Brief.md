
**Objective**
We need to bring absolute perfection to End of Game (EOG) and End of Quarter (EOQ) logic and execution. 

**Reason**
This is the type of thing that hard-core sports sim gamers care about, at an extreme level. EOQ/EOG moments are the most consequential moments for this type of gamer, because at this point, the game is on the line. All of their planning, strategy, and execution comes down to these crucial EOG moments. 

While these HSSG's (Hardcore Sports Sim Gamers) hate losing games, they understand that is part of true sports sim games and they accept it. What they cannot accept is losing a game on flawed logic or decision making by their players, or buggy clock execution or game execution in the final moments. 

If they lose a game because their palyers made a mistke, their player missed a key shot, or their opponent simply ouplayed them in the final two minutes, they'll fight to come back stronger for the next game. If they lose a game due to faulty logic or buggy execution in EOG moments, they will completely walk away from the game and never give it another chance.

##Tasks
**Eliminate Faulty Next Turns After Shot Resolution** — ✅ **Updated (clock-driven EOQ, 2026-06)**
- Quarter end is driven by `time_remaining` reaching 0, not automatic on every Final Turn shot.
- When clock **> 2** after a late-clock shot or final FT in an **active EOQ chain**: make → BIP → FLSS; miss OREB → putback; miss DREB → discrete DREB → FLSS (rebounder sprint-and-shoot, no HCO outlet); shooting foul → FTs then same rules after last attempt.
- When clock **≤ 2** in chain after miss DREB (or final FT DREB): terminal DREB + full clock burn.
- When clock **= 0**: no BIP, OREB, or DREB follow-up; frontend holds at rim/bounce (`holdFinalShotMs`, 2s) then quarter-end modal.
- See [`EOQ_System.md`](../06_Gameplay_Systems/EOQ_System.md) and [`Situational_Logic_System.md`](../06_Gameplay_Systems/Situational_Logic_System.md) §Final Turn and `BackEnd/utils/eoq_clock_progression.py`.

**All turn types covered by FLSS / EOG Perfection** — ✅ **Added (2026-07)**
- **HCO:** full Final Turn arming + `resolve_final_turn_shot` → internal FLSS fallback (preflight ≤ 8s). Fully wired.
- **DREB:** miss in chain → `flss_after_dreb` (clock > 2s) → `schedule_flss_after_dreb` forces `offensive_state=HCO` → FLSS consumed in HCO branch; `terminal_dreb_eoq` (≤ 2s) / `quarter_ends_after` (≤ 0) → clock drain. Verified.
- **OREB:** putback **is** the terminal shot (shot-clock-gated ≤ 2s → turnover; clock ≤ 0 → `quarter_ends_after`). No sprint-FLSS by design (rebounder already at rim). Verified.
- **HCT / FCP / FAST_BREAK:** these resolvers never consume the armed Final-Turn / `flss_possession_pending` flags (only the HCO `else` branch does). New `should_force_eoq_last_shot()` gate + `LOW_CLOCK_FLSS` branch in `run_micro_turn` force a true FLSS when a possession **starts** at `0 < time_remaining ≤ 8` (Q1-3 always; Q4/OT per `would_take_final_shot`). Above 8s the normal possession runs; `ensure_quarter_end_clock_drain` still ends the quarter if the clock hits 0 without a forced shot. Also fixed: the `clock ≤ 0` "Final Turn wins" `pass` now only applies to HCO, so a stray armed flag no longer blocks FLSS on non-HCO states.
- Backend: `BackEnd/utils/eoq_clock_progression.py` (`should_force_eoq_last_shot`), `BackEnd/models/turn_manager.py` (`LOW_CLOCK_FLSS` branch).

**Block Bugs on Final** (need to verify these still exist and if so, need to fix them)
- When a block occurs, we get a double announce of the block in some instances
- In some block instances, the ball was bouncing, incorrectly, to the oppositte end of teh court (these may be a legacy FE coord flipping issue, or it may be faulty logic in our back end bounce spot coords calculation)

**Add a Run Out The Clock Animation**
- Conditions to fire this animation
    - time remaining <= 30 seconds
    - offense team = winning team, or offense team = losing team and they are trailing by > 18 points
    - we are not a situation where the defense is looking to execute a force foul
- Step 1 Animation details
    - All active players move to the offense basket side of the court at our slowest speed archetype rate
    - Defense players target random positions in insie the lane or within 5 euclidian grid spots of the lane
    - Non-bh offense players target a spot randomly from this list: (key, upper/lower midWing, wing, midCorner, corner, topLane, and all deep spots on the offense side of the basket)
    - bh targets a random deep spot on teh offense sie of the basket
    - No players can double up on the same spot, if they roll teh same spot, choose one at random and move him to a random spot 5 euclidin grid spots away from that spot
    - advance trigger: all ten players reach their location
    - there is no logic to upper or lower choices or spot locaitons -- at this point in teh game, players do not care where they end up
- Step 2 Animation details (if acvance trigger is met in Step 1)
    - All players remain stationary
    - Clock runs to 0:00, we sound teh airhorn, and present the EOG/EOQ modal -- whichever we currently show at the end of the game. Note this situation will never lead to an overtime.

**Force Shots Exactly When Clock Reaches 0:00**
- Condition: if the team with the ball is in a Final Turn possession, we still enter Final Turn when the clock allows (preflight + rolled anchor).
- **Tie-break:** If Final Turn and FLSS would both trigger, **Final Turn wins** (`final_turn_shot_this_turn` defers low-clock FLSS routing).
- If preflight fails or clock is already 0 without Final Turn flagged → **FLSS** (Forced Last Second Shot).
- FLSS logic
    - if the player's x grid spot is >= 64 (flipped for away offense), we execute the shot as normal.
        - if he's at an inside shot location, he shoots an inside shot, else he shoots an outside shot
    - elif he the palyer's x grid spot is < 64 and >= deep key x (flipped for away offense), he executes an outside shot with a penalty applied to his shot score.
        - penalty = 100 - (offense team chemistry + (shooter's CH / 5))
        - shot score - pentaly = shooter's shot score
        - the cloesest defender will attempt to defend the shot -- his destination will be the same y as the shooter and 3 grid spots in  front of teh shooter between him and the basket.
            - there will be no location requirement for the shot defender. For now we will always have a shot defender
    - else: the shooter will shoot a long range shot, this shot will be undefended and calculated purely on the shooter's CH attribute and the distance he is from the basket x
        - roll = random.randint(1,100)
        - shot score = (shooter's CH - distance from his x and the basket x) / random.randint(1,6)
        - if shot score > roll, it's good, else it's a miss
- FLSS Shot animation
    - if x >= deep key x, animate ball as normal, no announce
    - else: animate ball as normal, and play the LFSS SFX files noted below.
    - LFSS SFX files (launch/heave only — Final Shot SFX excluded; see `BackEnd/constants/flss_sfx.py`)
        - sammy-launch on all penalty/heave FLSS instances
        - duke-heave also available when x <= 50 (or >= 50 if away offense)

    