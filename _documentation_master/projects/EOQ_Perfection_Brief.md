
**Objective**
We need to bring absolute perfection to End of Game (EOG) and End of Quarter (EOQ) logic and execution. 

**Reason**
This is the type of thing that hard-core sports sim gamers care about, at an extreme level. EOQ/EOG moments are the most consequential moments for this type of gamer, because at this point, the game is on the line. All of their planning, strategy, and execution comes down to these crucial EOG moments. 

While these HSSG's (Hardcore Sports Sim Gamers) hate losing games, they understand that is part of true sports sim games and they accept it. What they cannot accept is losing a game on flawed logic or decision making by their players, or buggy clock execution or game execution in the final moments. 

If they lose a game because their palyers made a mistke, their player missed a key shot, or their opponent simply ouplayed them in the final two minutes, they'll fight to come back stronger for the next game. If they lose a game due to faulty logic or buggy execution in EOG moments, they will completely walk away from the game and never give it another chance.

##Tasks
**Eliminate Faulty Next Turns After Shot Resolution**
- Don't animate or exeucte rebound turns or BIP after a Final Shot (HCO or Free Throw). The ball should hold at the rim on a make or bounce the the bounce spot on a miss. We hold this beat for 2 wall seconds, then display the end of quarter modal.

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
- Condition: if the team wit teh ball is looking to execute a Fianl Shot, we will still enter the final shot if the clock condition allows us to.
- If the clock reaches 0:00 before th offense team is able to execute the Final Shot logic, whomever is holding the ball at 0:01 will attempt a shot from the location he is at at that point. This will be called Forced Last Second Shot (FLSS)
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
    - LFSS SFX files
        - braddock-finalshot and sammy-launch are available for random choice in all LFSS instances
        - duke-heave is also availaible if x <= 50 (or >= 50 if away offense)

    