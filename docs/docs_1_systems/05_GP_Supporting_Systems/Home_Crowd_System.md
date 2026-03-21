
**Home Crowd Factor**
At the start of each game, determine the Home Crowd Factor for that game. it will be a value between 1-5

**Random Roll based on home team team chemistry score**

##Team Chemistry 7-10##
- 1: 30%, 2: 40%, 3: 15%, 4: 10%, 5: 5%

##Team Chemistry 11-15##
- 1: 20%, 2: 30%, 3: 25%, 4: 15%, 5: 10%

##Team Chemistry 16-20##
- 1: 10%, 2: 20%, 3: 30%, 4: 20%, 5: 20%

##Team Chemistry 21-25##
- 1: 5%, 2: 15%, 3: 20%, 4: 30%, 5: 30%

##Upper Bonus Range##
Used **only** when the **home** team’s Community Engagement (Franchise training, ``culture-builder-community``) shifts the roll **up** one band from the 21–25 chemistry tier (see ``Training_System.md``). Same percentages for every user/CPU home game that qualifies.
- 1: 0%, 2: 10%, 3: 20%, 4: 30%, 5: 40%


**Franchise: Community Engagement (summary)**  
Single Game and Tournament have no training; this applies **only in Franchise**. If the user or the computer (distant training template) selected Community Engagement and the flag is still pending on franchise team data, the **next franchise game started** adjusts which row above is used for the home crowd roll: **up** one chemistry band for the home team when the beneficiary is **home**, **down** one band when the beneficiary is **away** (floor at 7–10 = no downward effect). If **both** teams in the matchup have pending Community Engagement, shifts **cancel** and the roll uses normal home chemistry. Pending flags are cleared when that game is started. If there is no game that week (e.g. bye), the effect carries to the **next** game played in that season.


**Home Crowd Factor Impact**
Note all impacts are contained to teh game only. Example, Team A (away team)'s shot threashold is 100 entering the game, and is adjusted to 150 based on teh home crowd factor, when the game completes, Team A's shot threshold is back to 100. So I suggest we set a seprate variale within the game and add it to the teams shot threshold each time they attempt a shot.
1: No impact
2: away team FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE = 0.3
3: away team shot sthreshold +=25, away team FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE = 0.3
4. away team shot sthreshold +=50, away team FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE = 0.2
5. away team shot sthreshold +=50, away team FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE = 0.2, home team shot threshold -= 50