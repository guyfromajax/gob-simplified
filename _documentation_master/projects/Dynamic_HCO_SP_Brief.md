
**Dynamic HCO Set Plays**
- The offense does not look to execute subtle movements in Set Plays. They either look to exeucte the play that is called and progress skeleton steps as defined, or execute a Hot Read if the ball handler deems that one is available. 
- The defense can still force subtle movements with pressure. If the offense is forced into a subtle movement in a set play, they can either recover and continue to exectue the Set Play, or be forced into a freelance situation.
- If the ball handler is forced into a subtle movment step, then non bh offenders can also look to execute a subtle movement in order to get into position for a hot read pass reception.

**If Offense Get Knocked Into A Subtle Movement**
- bh performs subtle movement, non-bh players make a read and if they exceed the threshold they make a sublte movement (I think we have teh non-bh reads alerady wired from motion plays, but LMK if not)
- progression once subtle movement is executed
    - bh reads if shoot, hot read pass, or hold and look to re-enter the set play skeleton
        - if he chooses to shoot or pass, execute it
        - elif he chooses to re-enter set play skeleton run the following logic
            - offense score = (offense team chemistry + offense team off execution) * random.randint(1,6)
            - defense score = (defense team chemistry + defense team def execution) * random.randint(1,6)
            - if offense_score > defense_score, re-enter set play skeleton, else enter freelance forced situation


**Notes**
- We should apply per step reconciliation for steal/db turnover/foul, LMK if we need to align on this or if re-using the existing logic and code works here
- LMK if we need to wire vs man defense first, then vs zone. Or if we can do both at the same time
