

**News Process**
-whenever a piece of news is developed, it is added to the News container in the Coach's Office tab on the FCC. 
-Latest news is placed at the top and prevous news is pushed down
-Show a max of 5 news headlines in the News container
-Have an always-present link at the bottom of the container wiht the copy "See All News". Upon click this takes the user to the standalone news page.

**Stadalone News Page**
- Headlines and links to news stories are categorized by release moment and kept present throughout the entire season.
- At rollover, the feed clears except for the exact prior-season `Season {N} Recruiting Results` headline and content, which is republished as a Week 1 carryover. The rest of the new season's stories then populate normally.

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
  1. `ranking_table` rich lines under `National Recruit Rankings` and `Region {letter}` (when points exist). Each table is named (`table`: `national` / `region`). Stored with the story, so an old story keeps its own week:
     - **Rank movement**: each row's `move` (places gained since last week's same table; 0 = unchanged) or `new: true` (not in last week's table). Computed from the previous week's stored report (`w{N-1}-recruiting-report`), national against national and region against region. Week 1, or a week with no report the week before, stores none.
     - **`user_row`** on the national table when the user's team is outside the top 25: its real rank (its place among every team with points; the durable `recruiting_rank` when it has none), score, and `move` when last week's rank is known.
     - **`caption`** on the national table: what Score is, in plain words (`WEEKLY_SCORE_CAPTION`; the Results story uses `RESULTS_SCORE_CAPTION`). The scoring is not hidden.
  2. The lean announcements, under their own two sub-headings (no outer "Recruiting Leans Announced" heading):
     - `Top Rated Recruit Announcements` — recruits with RT > 49 who added a lean that week, as `text` lines
     - `Conference {label} Lean Announcements` — the conference as the rest of the app names it (`A2`, not `2`). New leans toward teams in the user's conference (teams by ascending natl_rank; a recruit can appear in both sections). One `team_recruits` rich line per team: `{type, team_id, team_name, recruits: [{recruit_id, name, rt}]}`, recruits by descending RT, `rt` the raw number.
- Rendering (`newsStory.js`, `newsView.js`):
  - No "Week N" line under the headline (the headline names the week). Other story types keep it.
  - Headings are the app's heading styles (Styleguide › Type), never bold body text: a `heading` line is a section (`h3.gob-news-heading`, heading-col); `level: 2`, and a team over its recruits, is a sub-section (`h4.gob-news-sub`, heading-card).
  - A heading followed by a `ranking_table` is one `.gob-news-rank` section; consecutive ones are a `.gob-news-ranks` group. They stack, and from 1600px sit side by side with the story at full width. The lean sections follow beneath.
  - Ranking rows: the team is a team link (logo mark and name) to its page; the user's team is the navy "yours" row; `user_row` is the last row of the national table, set off by a rule. Movement is a small neutral mark beside the rank ("▲3" t87, "▼2" and "NEW" t60, nothing when unchanged), the Office's rank-movement treatment. A story stored without movement, caption or `user_row` shows none.
  - A `team_recruits` block is the team as a sub-heading (logo mark and name in the shared team style, linking to the team page) over its recruits, one per row, name then RT in the canonical ramp. Recruit names are text: no story links a recruit.
- Stories stored before this (the lean section as plain `text` lines, team and recruits alike) render as before, with the old conference name. Only the outer heading is not drawn. They are not upgraded on read: the old lines hold the RT letter only, and the page does not re-map the ramp from a letter.
- `story_id`: `w{N}-recruiting-report`. Skipped if already present when prepending.

##Headline: "Your Recruiting Board Moved"
- Personal lean gains and drops for the user's board (completed week). Separate from the league-wide leans section on the Recruiting Report.

##Headline: "Season {N} Recruiting Results"
- Moment: after **Run Recruiting** completes in week 35 (franchise advances to week 36; user returns to FCC at week 36). No week number in the headline.
- Scoring: signing team only receives **100%** of each signed recruit's RT. No other team scores for that recruit.
- Same ranking / rich-table rules as the weekly report rankings (National Top 25 in 13+12 columns + full Region 16 in 8+8). No leans section.
- Also writes the durable FTD recruiting ranks from Results scoring and **freezes** them until next season Week 1.
- `story_id`: `s{N}-recruiting-results`.
- **Season 2+ carryover:** `finish_season` snapshots the exact published story before clearing recruiting and news state, retains its `story_id`, headline, and rich content, and inserts it into the next season's `season_news` as a Week 1 release. `source_week: 36`, `carried_from_season`, and `carried_into_season` preserve provenance. Because the FCC News tab, Coach's Office News container, and standalone News page all read `season_news`, the carryover appears on all three without separate copies or frontend logic.
