**Distant Training Logic**
- All non-user teams use distant training
- User team continues to use standard training

**Ordering:** Teams = order of FTD query results. Players = order of `player_ids` in the FTD `players` field (player_0 → first id, player_1 → second, … player_11 → twelfth).

## Steps
1. Pre-load the 50 templates that match the current run, then choose one at random per team. Query the distant_training collection in the appropriate database (gob-staging for staging, gob for production) filtered by training_type:
    - If week == 1 (i.e. training camp): training_type == "tc" (50 docs)
    - Else: training_type == "regular" (50 docs)
2. Collect the teams from the FTD docs linked to the franchise
3. Add the team_values to each team's existing team attributes
4. Collect the players from the FPD docs linked to the franchise
5. Assign template slots by existing player order (no randoms): player_0, player_1, player_2, … through player_11
6. Add the players values for each player to the players' existing attributes
7. Ensure all changes persist through our data persistence system
8. Adhere to all team attribute and player attribute clamping rules as defined in the Attribute_Clamp_System.md document




**Collection Script Creation Brief**
##Create 100 documents with the following fields & values:
-training_type: 50 "tc", 50 "regular"
-focus: leave all as "" for now
-team_values: direction below
-player_values: direction below


##team values
-shot_threshold values
    -tc documents (50 total)
        - -5, -6, -7, -8, -9 (3 documents each) (15)
        - -10, -11, -12, -13, -14, -15 (4 documents each) (24)
        - -16, -17, -18 (2 documents each) (6)
        - -21, -22, -24, -28, -31 (1 document each) (5)
    -regular documents (50 total)
        - +13, +11, +8, +7, +5 (2 documents each) (10)
        - -5, -6, -7, -8, -9 (5 documents each) (25)
        - -10, -11, -12, -13, -14, -15 (2 documents each) (12)
        - -18, -22, -30 (1 document each) (3)
-rebound modifier values
    -tc documents (50 total)
        - 0 (3 documents each) (3)
        - +0.01, +0.02, +0.03 (7 documents each) (21)
        - +0.04, +0.05 (10 documents each) (20)
        - +0.06, +0.07, +0.09 (2 doc each) (6)
    -regular documents (50 total)
        - -0.09, -0.06, -0.05, -0.02, -0.01 (3 documents each) (15)
        - 0, +0.01, +0.02, +0.03 (7 documents each) (28)
        - +0.04, +0.05 (2 documents each) (4)
        - +0.06, +0.07, +0.09 (1 doc each) (3)
-momentum is always 0 for both tc and regular
-the other 9 
    -offense efficiency, defense efficiency, pt efficiency, fb efficiency, fb opp modifier, pt opp modifier, discipline, fight, team chemistry
    -tc documents (50 total)
        - cumulative points to spread across the 9 attributes (all positive numbers)
            - 11, 14, 15 (1 each) (3)
            - 16, 17, 18, 19, 20 (8 each) (40)
            - 21, 22 (3 each) (6)
            - 23 (1 each) (1)
        - in the script take the cumulative points and assign random values between 0 and 3 until all points are accounted for
    -regular documents (50 total)
        - cumulative points to spread across the 9 attributes (all positive numbers)
            - 9, 10, 11 (2 each) (6)
            - 12, 13, 14, 15, 16 (8 each) (40)
            - 17, 18 (2 each) (4)
        - in the script take the cumulative points and assign random values between -1 and 3 until all points are accounted for
        

##player values
-create a players field and make it a key/value dict structure
-create 12 instances inside the players field and give each instance a sub-dict, with the keys being each of the 13 trainable attributes
-13 trainable attributes are: SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT, CH
-example structure: {player_1: "SC": -1, "SH": 3, "ID": 0, "OD": 0, "PS": 3,...."CH": 1}
    
-tc documents (50 total)
    - cumulative points to spread across the 12 players (all positive numbers)
        - each integer 490 - 494 (1 each) (5)
        - each integer 495 - 499 (2 each) (10)
        - each integer 500 - 504 (6 each) (30)
        - each integer 505 - 509 (1 each) (5)
    - in the script take the cumulative points and assign random values between 0 and 12 to each of the players' 13 trainable attributes until all points are accounted for, under the following parameters:
        - number of 0 assignments must be between 8-12
        - number of 10-12 assignments must be between 0-3
        - number of 6-9 assignments must be between 23-27
        - the remainder of the assignments must be between 1-5
-regular documents (50 total)
    - cumulative points to spread across the 12 players (all positive numbers)
        - each integer 20 - 34 (1 each) (15)
        - each integer 35 - 49 (2 each) (30)
        - each integer 50 - 54 (1 each) (5)
    - in the script take the cumulative points and assign random values between -5 and 5 to each of the players' 13 trainable attributes until all points are accounted for, under the following parameters:
        - -5 or 5 values for a player attribute: max 1 each
        - -4 or 4 values for a player attribute: max 3 each
        - the remainder of the points should be spread across the players' attributes with at least 40% being between -3 to -1

 