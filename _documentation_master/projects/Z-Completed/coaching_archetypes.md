
##Macro
**Archetypes need to sync**
1. Playbooks
2. Game Plans
3. Training
4. Lineup Setting during games

**Approach**
1. Team Level: does teh team have evergreen identity level strategies that they will utilize regardless of matchups?
2. Opponent level: does the upcoming opponent have dynamics that dictate specific strategies?

**Team Identity Archetype Checks**
All checks are done before training runs that week
- Week 1: team establishes their identity and starting five
    - These starting five will start every game until the next checkpoint, at which the starting five will be recalculdated
    - The top rated bench player will also be rotated into the starting lineup if his RT at a position is wihtin 5 of the projected starter
- Checkpoint 1, Week 7: if team win rate < 30%, they recalibrate their identity, all teams evaluate recalibration of starting lineup
- Checkpoint 2, Week 13: if team win rate < 50%, they recalibrate their identity, all teams evaluate recalibration of starting lineup
- Checkpoint 3, Week 20: if team win rate < 50%, they recalibrate their identity, all teams evaluate recalibration of starting lineup

**Team Strategy Weekly Adjustments**
Each week the team will **consider** adjusting its strategy based on opponents talents and tendencies

##Game Plan Settings
**Note**
1. All calculations are done using the team's projected starting 5
2. Charts below are percentage chance of each setting from 0 to 4. Example, (0, 5, 15, 50, 30) = 0:0%, 1:5%, 2:15%, 3:50%, 4:30%

**Offense**
1. Identify the strong and good scorers on the team, using the following thresholds:
    - One attribute
        75+ = strong
        50-69 = good
    - Two attributes
        150+ = strong
        100-149 = good
    - Focus
        - SC: inside
        - SH: outside
        - SC + AG: attack
2. Give inside, attack, and outside scores based on step one.
    - Strong scorer = 5 points
    - Good scorer = 2 points
2a. Score totals
    - If sum of all three (inside, attack, outside) > 15, team offense is set play heavy (0, 5, 15, 50, 30)
    - Elif sum of all three is between 10-15: team offense is balanced (5, 20, 50, 20, 5)
    - Else team offense is motion heavy (30, 50, 15, 5, 0)

**Offense Focus Strategy (Inside, Attack, Outside)**
- Set inside, attack, and outside weightings proportionally based on scores from Offense Step 2, this will be the team's core identity
- Vary these a bit week to week to avoid being predictable and to take advantage of matchup advantages

**Defense**
- Calucualte team's man defense score
    - PG & SG, each OD + AG
    - SF: 0.5 * (OD + ID + AG + ST)
    - PF & C, each ID + ST
    - Add all five position scores
- Calcualte team's zone defense score as sum of all five projected starters' IQ
- If Man Defense Score > 50 + Zone Defense Score, defense is man heavy

**Fast Breaks**
- Team Level: Based on team ND and team fb efficiency attribute
- Opponent Level: based on opponent fb opp modifier

**HC Trap & FC Press**
- Team Level: Baed on team ND, frontcourt defenders' AG + OD, and team pt efficiency attribute
- Opponent Level: based on opponent pt off modifier

**Offense Tempo**
- Team level: Based on team ND and does the team have a talent advantage (if they do they want to push the tempo to generate more possessions)

**Play Alteration**
- Team Level: command of the playbook and IQ

**Aggression**
- Team level: ND, defense efficiency, discipline

**Rebounding**
- Opponent Level: if opponent fast breaks a lot skew higher, if not, skew lower
- Team Level: higher fb opp modifier will allow teams to skew lower