
**Week 35 Awards & Player Aging**
##Update Stats##
-upldate all player and team career level stats
-reset all player and team season level stats to 0
-delete all game documents that are linked to the season that just finished
-archive season data (I need to define, table this for now)
-archive graduating players (I need to define, table this for now)

##Age Players##
-Seniors graduate (represent with "graduate" on the front end)
-Juniors become Seniors
-Sophomores become Juniors
-Freshmen become Sophomores
-Recruits become Freshmen

#FCC Update##
-Add an "Awards" button to the Resources tab in the FCC. Make this a dead button until week 25, then it becomes live and clicks to awards.html.

##Awards Page Conent##
- after week 34 completes
    - determine the All-American teams
        - use each player's season stats
        - use the same logic we use to determine player of the game after each game, with one adjustment 
            - in order for a player's DEF% to be calculated, he must have at least 130 DEFA or greater on the season
        - 1st Team = top five players
        - 2nd Team = players ranked 6-10
        - 3rd Team = random choice of five players among the players ranked 11-20

**Week 36: Run Recruiting**
-see Week 36 section of Recruiting_System.md doc for direction
-This is a separate recruiting-orders flow from weeks 20-26.
-Expose the Week 36 recruiting-orders screen during weeks `35-36` only.
-Week 36 recruiting orders persist on the user's FTD doc in `recruiting_orders_week_36`.
-On first load, if `recruiting_orders_week_36` is empty, auto-populate the top grid with all recruits who have the user's team in any lean slot, sorted by RT descending.
-On revisit, preload the saved `recruiting_orders_week_36` values instead of re-running auto-fill.
-Display `Available Roster Spots {X}` where `X = 15 - returning_non_graduating_player_count`.
-Graduating seniors still free future roster spots for this display, but they remain on the visible roster for now.
-Commitments / signings / roster mutation from Week 36 recruiting will be implemented in the next recruiting phase.
