

**Base Behavior**
- Offense team executes the called Motion play per the defined skeleton

**Non-Skeleton Movement Options**
- Subtle Movement
- Freelance Audible
- Freelance Forced
- Hot Read

**Subtle Movement**
- Definition: these are small micro movements by one or more offensive players during a step
- Benefits
    - Breaks the mononotous pattern of structred movements without breaking the overall flow of the motion skeleton. This makes the play a bit harder (or less easy is a more accurate term) for the defense to read and react to.
    - Allows the offender to potentially spot opportunities they would not notice if they simply stay wihtin the predefined motion skeleton
- Risks
    - May throw off the team's motion skeleton progression and force them into a suboptimal freelance situation
- Movements
    - All of these have the primary objective of simply doing something slightly off pattern to keep the defense off balance. The explanations below describe additional potential objectives for each.
    - Ball Handler Movements
        - Ball handler dribbles in place or stands in place without dribbling to assess the situation or deal with the defensive pressure (no movement)
        - Ball Hanlder dribbles a few grid spots backward to assess the situation (2-5 euclidan grid spots away from the basket)
        - Ball Handler dribbles to teh side, only applies if he's positiond outside the three point line and his movement stays outside the three point line - up to halfway between his spot and the next defined spot (i.e. if he's at the key he'll dribble half way toward the upper or lower midWing) -- these are only possible when the bordering spot is unoccupied by a teammate
        - Ball Handler slowly dribbles in a few grid spots toward the basket. This allows him to get a feel for the status of his defender, as well as survey his teammates down on teh block for a quick pass, or his teammates on the outside who may be able to sneak to an open spot is his dribbling in draws other defenders inward. (2-5 euclidian grid spots toward the basket)
    - Non Ball Handler Movements -- only occur if the ball handler executes a subtle movement or we're in a freelance situaton (forced or audible)
        - **note for all fo these, if the bh is in a subtle movement, the non-bh player will hold at this new spot until either the next predefined skeleton step is put into motion, in which case he'll go to his spot defined in that step. Or if a shot is attempted, he'll behave as he normally does for the shot attempt -- either getting into rebound position or attempting to cut of the drive if it is an attack shot and he is within distance of the drive path. If the bh is in a freelance situation, the player will hold this position until freelance starts then he'll execute freelance as defined below.
        - movements:
            - lowPost players can flash to the midLane, one of the midPost or one of the highPost spots to receive a quick pass and attempt an inside or attack shot, or make a a quick pass to a teammate as teh pass sucks teh defenders inward.
            - players outside the 3-point arc can slide to an open spot outside the 3-point arc in an attempt to get more open
            - outsie players can take a few hard steps (2-5 euclidian grid spots) inward then pop back to their startig spot in an attempt to shake their defender and create an Freelance Audible/Hot Read shot
            - outside players can take a few hard steps inward (2-5 euclidian grid spots) to see if they can beat their defender and execut a cut toward the basket and receive a pass form teh bh. This is particularly effective against aggressive defenses that are over playing a deny the pass or high pressure.
            - inside paleyrs can slide a few steps outward (2-5 euclidian grid spots) toward a teammate on the outside to feel out the oppoortunit to set a backdoor cut

**Freelance Audible**
- Definition: a purposeful decision to break the motion offense skeleton and enter freelance progression
- Benefits:
    - Creates opportunities outside the standard motion skeleton
    - Serves as an overall pallette cleanser keeping the defense off-balance in continusouly anticipating established motion patterned plays.
- Risks
    - Easy for offense to flub execution and force themselves into a sub-optimal situation with increased chance of committing a turnover, committing a foul, or taking a bad shot.

**Freelance Forced**
- Definition: motion offense gets disrupted, either due to poor offense execution or superior defense execution, and offense is forced into a freelance progression. This differs from Freelance Audible in that the Audicle is a conscious choice by the offense, while Forced is a situation where the offense is forced into it.
- Benefits
    - Limited, only real benefit is it keeps the HCO turn alive so the offense can attempt a shot
- Risks
    - High likelihood of sub-optimal offensive sitatuion like turnover, offensive foul, or poor shot attempt.

**Hot Read**
- Definiation: offense makes a conscious choice to break from the motion skeleton in an attempt to take advantage of a specific situation. This is like a Freelance Audible in that is a conscious choice, but different in that it is done so with a specific opportunity in mind, whereas the Freelance Audible is purely a conscious choice to try something different with no specific opportunity identified.
- Benefits
    - Offense has identified an ideal situation and has an opportunity to take advantage of it.
- Risks
    - This is reliant on the offensive player making the right reat that the Hot Read is actually a good opportunity. If it is not, it can lead to a suboptimal siituation that leads to a turnover, offensive foul, or poor shot attempt.
- Speciic Hot Reads
    - Ball handler realizes he has an opportunity for an advantage in an outside or attack shot based on the defender who is guarding him.
    - Ball handler realize a teammate has an opportunity for and advantage in an outside, attack, or inside shot based on the defender who is guarding them. 
- Hot Read criteria per shot type is locaiton based
    - Potential inside shot, potential shooter must be stationed at an inside location: lower/upper lowPost, lower/upper midPost, midLane, basketSpot, or a grid spot within that geometric area
    - Potential Outside or Attack shot: potential shooter must be located at any non-inside location or a grid spot otuside the geometric inside spots area

**Movement Options Logic per HCO turn**
- Step 0: 
    - Start with an offensive player level data structure, below is my porposed data structure but tell me what you recommend based on our data persistence methods and SS&S rules:
        {player string id: {"inside": false, "attack": false, "outside": false}} x 5 (one for each offensive player). Also if we use this structure, LMK if we should store all five of these object to a list attached to teh team document. Note these true/false values to not persist beyond hte HCO turn. They start every new turn as false. Unless you think it's best to set these once coming out of the set lineup screen, then persist them wihtin the game until either team changes their lineup so we don't need to run the calculation at the start of each HCO turn?
- Step 1: Determine if any mismatches favor the offense to set any Movement Options to True
    - if defense playcall is a man defense:
        - Identify man defense matchups and calculate each matchup's Shot Type Scores
            - Inside Score: ((offender's SC + ST) - (defender's ID + ST)) / 2 
            - Outside Score: (offender's SH) - (defender's OD) 
            - Attack Score: ((offender's SC + AG) - (defender's ID + AG)) / 2 
            - there will be 15 scores total, 3 for each matchup.
                - if a player has a score > 25, then that Movement Option is true. 
                    - Example: Offense PG has +28 Attack Score, -7 Inside Score, +11 Outside Score 
                     - {player string id: {"inside": false, "attack": true, "outside": false}}    
    - elif defense playcall is a zone defense:
        - Calculate Defense Shot Scores on a team level, delineated by zone areas
            - Inside D Score = sum of ID for any D player who's zone area touches an inside spot / number of those players
            - Outside D Score = sum of OD for any D player who's zone area touches an outside spot / number of those players
            - Attack D Score = sum of AG for any D player who's zone area touches an attack spot / number of those players
        - Calculate offense Shot Scores on an individual level
            - Each players (SC+ST) / 2 = players inside score
            - Each player's SH = outside score
            - Each player's (SC + AG) = attack score
        - Calculate the 15 Mismatch Scores same as we do for man defense and set the appropriate data items to true if applicable
    - any player/shot type values that are true will be potential optimal reads for the offense as they execute their HCO turn
        
- Step 2: run the motion skeleton, and at each step calculat the following
    - Does the ball handler choose to execute a sekelton stopping action, a hot read or freelance audible or subtle movement, or move immediately to the next step in the skeleton?
    - calculation
        - offense_score = (bh read + offense team discipline) * random.randint(1,6)
        - if offense_score < 110 run the nested logic here, else proceed to the progression point noted below:
            - tempo modifier: slow = -25, normal = 0, fast = 25
            - roll = random.randint(1,100) + tempo modifier
            - if roll > 4 * current shot clock value, ball handler chooses a skeleton breaking action
                - 75% shot attempt
                    - Inside Shot if he is at an inside location
                    - he chooses to attack shot our outside shot via the following logic
                        - attack score = (bh AG + SC) / 2
                        - outside score = bh SH
                        - sum = attack score + outside score
                        - shot_roll = random.randint(1, sum)
                        - if shot_roll <= attack_score, attack shot is chosen, else outside shot is chosen
        - porgression point: calculate defense score
            - defense_score = (bh defender defensive action + defense team fight) * random.randint(1,6)
            - defensive action = inside defense if ball hanlder is at an inside location (let's verify the fucntion), or outside/pressure defense (let's verify the function)
        - if offense_score > defense_score + defense team def efficiency + defense team chemistry
            - hot read is possible if one exists in this step
            - if one exists, 50% it is executed and 50% it is not. Thresholds are adjusted for offense team aggressiveness setting
                - aggressive: 70% executed, 30% not executed
                - passive: 30% executed, 70% not executed
            -if the ball handler executes:
                - the ball handler's first read is for himself, if he is in a hot read situation, he'll attempt the shot. If he is in multiple hot read situations, choose one at random.
                - then he'll identify teammates in a hot read situation, if multiple exist, choose the one closest to the bh. If there is a tie, choose one at random.
            -if the ball handler does not execute, there is not subtle movement and we move immediately to the next skeleton step
        - elif the defense score > offense score + offense team off efficiency + offenste team chemsitry
            - disruption moment happens
                - 50% chance this is a subtle movement is forced 
                - 20% chance a Freelance Forced is forced
                - 30% chance no effect
                - these thresholds adjust based on the defense team's aggression setting
                    - aggressive (Freelance Forced + 10%, no effect -10%)
                    - passive (Freelance Forced -10%, no effect +10%)
        - else 50% chance the ball handler does a Subtle Movement and 50% chance he passes immediately. These thresholds are are adjusted based on offense teama and defense team aggressiveness settings.
            - offenset team
                - aggressive: pass immediately + 20%, subtle movement -20%
                - passive: pass immediately -20%, subtle movement +20%
            - defense team:
                - aggressive: pass immediately -20%, subtle movement +20%
                - passive: pass immediately +20%, subtle movement -20%
            **note these can cancel each other out for no net effect, or they can build on each other to create a 90/10 scenario


**Spot Classifications For Shot Type**
- Inside Spots: lower/upper lowPost, basketSpot, midLane, basketSpot
- Outside Spots / Attack Spots: any non-inside spot

**Hot Reads exist at a step if...**
- A player with a shot type = true is placed at a spot within that shot type area

**Freelance Behavior**
- if the offense enters a freelance situation, players will randomly choose to:
    - execute a subtle movmeent (50%)
    - or move to a new predefined location (predefined as it exists in our constants) that is wihtin 9 euclidian grid spots of his existing location
    - if offense team off eff + team chemsitry > 15, players can never move to the same location
    - if players do move to the same location, execute a visual collission effect (both sprites reach the spot and rattle off each other -- rattle each sprite 3x back and forth like we rattle rim shots, then have them land offset from the target spot by 2 euclidian grid spots, in oppositte directions)
- shot attempt resolution: use the same shot resolutio logic, including use of tempo modifier, as is detailed above for normal HCO skeleton steps.
