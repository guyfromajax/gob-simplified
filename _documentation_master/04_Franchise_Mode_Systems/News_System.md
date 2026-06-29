

**News Process**
-whenever a piece of news is developed, it is added to the News container in the Coach's Office tab on the FCC. 
-Latest news is placed at the top and prevous news is pushed down
-Show a max of 5 news headlines in the News container
-Have an always-present link at the bottom of the container wiht the copy "See All News". Upon click this takes the user to the standalone news page.

**Stadalone News Page**
- Headlines and links to news stories are categorized by release moment and kept present throughout the entire season. 
- When a new season is complete, the news page clears and starts to repopulate upon init of the next season.

**News Moments**
- Regular Season (weeks 1-26) games run


**Regular Season Games Run**
##Headline: "Week {week #} Upset Report"
- Criteria: List all games where (1) the winning team's entering-week `natl_rank` is **more than 29 spots worse** than the team it beat (`winner_rank - loser_rank > 29`), and (2) the **losing team** was ranked **1–64** (inclusive). If no games qualify, this news is not generated for that week.
- Content
    "#{winning team rank}. {winning team name} upset #{losing team rank}.{losing team name} by a score of {final score}.
    - list each game on its own line
    - list games in ascending order of the natl_rank of the losing team, starting with teh lowest

##Headline: "Practice Squad All-Stars"
- Criteria: create a list of all Practice Squad players who ahve a total attrbute gain > 4 for the week. If no PS players qualify, this news is not generated for that week.
- Content
    -"{PS Player Name} of {Player Team Name -- school only, no mascot} increased by {increase cumulative total} attribute points this week. His strongest gains were in {list full attribute handle of the highest gain, if there is a tie, list all that are tied using proper grammar of commas and "and" preceding the final attribute}. He's now a {RT value} rated {highest rated position abbreviation -- PG, SG, SF, PF, or C}.
-Limit the list to the top 10 by Cum Gain. if there is a tie that pushes the list beyond 10, list all that are in the tie then stop after that.

##Headline: Updated Recruiting Leans Announced
- Criteria: List lean announcement from all recruits with RT > 49 and list lean announcements for all teams in the user's conference -- in that order. If a recruit with RT > 49 announces a lean with a team from teh user's conference, he is listed in both places.
-Content
    "Top Rated Recruit Announcements"
    "{Recruit Name} who is a {recruit's RT} rated {recruit's archetype} has announced a lean twoard {team name}."
    (list all highly rated recrtuits in this manner)
    "  " (empty line)
    "Conference {User Conference} Lean Announcements" (ex: "Conference 1 Lean Announcements)
    "{Team Name}"
    "{Recruit Name} ({Recruit RT}), {Recruit Name} ({Recruit RT}), {Recruit Name} ({Recruit RT})"
    "{Team Name}"
    "{Recruit Name} ({Recruit RT}), {Recruit Name} ({Recruit RT}), {Recruit Name} ({Recruit RT})"
    "{Team Name}"
    "{Recruit Name} ({Recruit RT}), {Recruit Name} ({Recruit RT}), {Recruit Name} ({Recruit RT})"

    For user conferecne list teams from lowest natl_rank to highest. Only list recruits who have declared a lean to the team that week.


