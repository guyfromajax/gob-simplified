

**News Process**
-whenever a piece of news is developed, it is added to the News container in the Coach's Office tab on the FCC. 
-Latest news is placed at the top and prevous news is pushed down
-Show a max of 5 news headlines in the News container
-Have an always-present link at the bottom of the container wiht the copy "See All News". Upon click this takes the user to the standalone news page.

**Stadalone News Page**
- Headlines and links to news stories are categorized by release moment and kept present throughout the entire season. 
- When a new season is complete, the news page clears and starts to repopulate upon init of the next season.

**News Moments**
- Season init (week 1)
- Regular Season (weeks 1-26) games run


**Season Init**
##Headline: "{Team Name} Walk Ons Announced"
- Criteria: the user team's walk-ons for the season. Written every season — at franchise creation for season 1, at `finish_season` for season 2+. Not generated when a full signing class left no walk-ons to add.
- Content: a `player_table` rich line — the roster-format table (name, pos, year, height, weight, the 12 attributes, RT), same columns and display rules as the roster page.
- Seasons 2+ additionally get the Walk-On Welcome modal on the first FCC landing; the story is the permanent record that outlives dismissing it. Full rules: `Season_Init_System.md` → Walk-On Announcement.


**Regular Season Games Run**
##Headline: "Week {week #} Upset Report"
- Criteria: List all games where (1) the winning team's entering-week `natl_rank` is **more than 29 spots worse** than the team it beat (`winner_rank - loser_rank > 29`), and (2) the **losing team** was ranked **1–64** (inclusive). If no games qualify, this news is not generated for that week.
- Content
    "#{winning team rank}. {winning team name} upset #{losing team rank}.{losing team name} by a score of {final score}.
    - list each game on its own line
    - list games in ascending order of the natl_rank of the losing team, starting with teh lowest
- Coach's Office: Upset Reports are **excluded** from the News container (still on the standalone news page / News tab).

##Headline: "Practice Squad All-Stars"
- Criteria: create a list of all Practice Squad players who ahve a total attrbute gain > 4 for the week. If no PS players qualify, this news is not generated for that week.
- Content
    -"{PS Player Name} of {Player Team Name -- school only, no mascot} increased by {increase cumulative total} attribute points this week. His strongest gains were in {list full attribute handle of the highest gain, if there is a tie, list all that are tied using proper grammar of commas and "and" preceding the final attribute}. He's now a {RT value} rated {highest rated position abbreviation -- PG, SG, SF, PF, or C}.
-Limit the list to the top 10 by Cum Gain. if there is a tie that pushes the list beyond 10, list all that are in the tie then stop after that.

##Headline: "Updated Recruiting Leans Announced"
- *(Merged into the weekly Recruiting Report — see Recruiting Reports below. Standalone story is no longer published.)*


**Coach's Office News container**
- Shows up to 5 newest headlines from `season_news`.
- **Excludes** Upset Reports (those remain on the standalone news page / News tab).
- Weekly **Recruiting Report** (combined rankings + leans) is included.


**Recruiting Reports**

##Headline: "Week {N} Recruiting Report"
- Cadence: **Week 1** at season init (franchise create / `finish_season` rollover, after initial leans are written). Then on each week completion for completed weeks **1–34**, titled for the **current** week after advance (`Week {completed + 1}`), so the report sits one week ahead of that week's Upset Report. Lean movement (including postseason performance leans) runs through week **34**, so title weeks go through **35**.
- Criteria: publish when rankings have any team with lean-share points > 0 **and/or** the completed week produced qualifying lean announcements. National omits **0-point** teams (list may be shorter than 25). Region lists **all 16** region teams (0-point teams included at the bottom).
- Scoring (pre–Week 35 signings): each recruit's value is **current RT** (`max` position rating). Teams on the lean list accrue:
  - slot 1 → 100% of RT
  - slot 2 → 50% of RT
  - slot 3 → 25% of RT  
  All values are **rounded integers**.
- Ranking: strict sequential ranks `1..N`; ties broken **randomly**. National Top **25** (two columns: **13** left / **12** right). User **region** lists **all 16** teams (two columns of **8**), including 0-point teams, labeled `Region {letter}` (e.g. `Region A`). National still omits 0-point teams.
- **Durable FTD ranks** (same scores, separate from the news Top-25 cut): every team gets
  `recruiting_rank` (national 1–128, zeros included), `recruiting_region_rank` (1–16 within
  region), and `recruiting_score`. Written at Week-1 init, each weekly report recompute
  (through title week 35), and frozen after Week-35 Results until next season. Roster /
  other surfaces read FTD — they do not rescan lean lists.
- Content (top to bottom):
  1. `ranking_table` rich lines under `National Recruit Rankings` and `Region {letter}` (when points exist).
  2. Section heading **Recruiting Leans Announced**, then the former leans story body:
     - `Top Rated Recruit Announcements` — recruits with RT > 49 who added a lean that week
     - `Conference {N} Lean Announcements` — new leans toward teams in the user's conference (teams by ascending natl_rank; a recruit can appear in both sections)
- `story_id`: `w{N}-recruiting-report`. Skipped if already present when prepending.

##Headline: "Your Recruiting Board Moved"
- Personal lean gains and drops for the user's board (completed week). Separate from the league-wide leans section on the Recruiting Report.

##Headline: "Season {N} Recruiting Results"
- Moment: after **Run Recruiting** completes in week 35 (franchise advances to week 36; user returns to FCC at week 36). No week number in the headline.
- Scoring: signing team only receives **100%** of each signed recruit's RT. No other team scores for that recruit.
- Same ranking / rich-table rules as the weekly report rankings (National Top 25 in 13+12 columns + full Region 16 in 8+8). No leans section.
- Also writes the durable FTD recruiting ranks from Results scoring and **freezes** them until next season Week 1.
- `story_id`: `s{N}-recruiting-results`.

