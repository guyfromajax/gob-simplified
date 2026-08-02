# Recruiting System (**verified 2026-06-13**)

> Hybrid spec + implemented-system doc. Core generation/lean/RT logic verified against code: `RecruitManager` (`_select_archetype`, `_generate_recruit_profile`, `_generate_weight`, `generate_recruits_list`) and `FranchiseManager._build_recruit_lean` in `BackEnd/models/franchise_manager.py`; complete-week lean updates in `BackEnd/api/franchise_routes.py` (`_apply_performance_based_recruiting_lean_updates`, `_apply_complete_week_recruiting_lean_updates`); RT buckets in `FrontEnd/static/js/shared/rtBucket.js`. Some UI/flow bullets are written in build-spec voice; treat code-cited items as authoritative.
>
> **⚠️ Recruit *generation* was rewritten by the Player Attribute Recalibration (2026-07).** The "Recruit Init Attribute Logic" section below is SUPERSEDED — the 20-archetype machinery (`_select_archetype`, `YEAR_TIER_RANGES`, archetype configs, weight-by-height bands) was **removed**. Generation is now position-intent-first; see that section's current-flow note and `10_Players_Systems/Player_Attribute_System.md`. The lean/flow/RT-bucket content elsewhere in this doc is unaffected.

**Franchise Init**
0. Add a new "Recruits" field to the FTD docs (this will be a dict with 1-10 key/value pairs wiht the keys being "1", "2", "3", an so on, values will init as None, and will hold FRD string ids in the future)
1. Add two new fields to each docment in the FRD collection, note these do not need to be retrofitted to any existing FRD documents
    - "Home Region" -- a **region letter** `A`–`H` (stored as a string; one letter matching franchise geography), same convention as team `region` in the teams collection
    - "Lean" (dict with keys `"1"`, `"2"`, `"3"`; values are **`None`**, the literal **`"open"`**, or a **team id string** — the string form of that team’s MongoDB `ObjectId`, **not** the display name)
        - If key `1` == `"open"`, keys `2` and `3` are `None` (or empty, normalized to `None`).
        - **Upon season init (matches `FranchiseManager._build_recruit_lean`):**
            - **75%** key `1` == `"open"`
            - **25%** key `1` == random team id from the 16 teams whose `region` matches the recruit’s **Home Region**
            - If key `1` != `"open"`: **80%** key `2` is `None`; **20%** key `2` == random **other** team id from that same region (never the same id as key `1`)
            - Key `3` is always `None` at init
2. Upon new franchise init and the start of each new season within a franchise instance, create **300** new recruits per recruit generation (`generate_recruits_list(count=300)`). (The method's default param is `count=40`; the season-init / new-franchise call sites pass `300` — `franchise_manager.py:430`, `franchise_routes.py:12332`.)

**Recruit Distribution By Year**
Junior = random.randint(5,15)
Sophomore = random.randint(5,15)
Freshman = random.randint(10,30)
JH = 300 - (junior + sophomore + freshman)
- Year is stored as the full string: `"JH"`, `"Freshman"`, `"Sophomore"`, `"Junior"`; table columns display the abbreviation: `JH` / `FR` / `SO` / `JR`.
- **Year carry-through & aging:** signed recruits (and signed walk-ons) keep their rolled year through `week_35_recruiting_results`; at season transition they enter the roster advanced one step: JH → Freshman, Freshman → Sophomore, Sophomore → Junior, Junior → Senior. JH therefore never appears on an active roster. Unsigned recruits are wiped at season init and a fresh 300 generated.
**Macro UI note, we'll need to add a year column to all pages taht dispaly comprehensive recruit data
    - Recruits tab in teh FCC, recruits page, recruiting orders page, recruiting invites page, invites results page, and please do a sweep to see if you find any others. Rule -- if we're showing all of the recruits' attributes we should also show the year otherwise no year
        - so teh Recruits container in the Coach's Office tab on the FCC would be excluded, as would the Tranining Report invte result.
    - Exception to the rule: the recruiting-orders **top grids** (weeks 20-26 and week 35) also get a Year column even though they don't show full attributes (the user is committing roster spots, so year matters).
    - Column position: Year sits **after `POS`**, before the attribute columns (mirrors roster tables). In top grids it sits after `POS`/`RT` equivalent position.

**Recruit RT color scale (UI display)**
Note this scale applies to JH recruits only. Freshamn, sophomore and junior recruits will use the standard color scale.

Recruit RT text uses `/js/shared/rtBucket.js` → `getRecruitRtBucketClass(rt)` with `/css/rt-buckets.css` (same class names and hex colors as the player Attribute Bar Scale, recruit-specific breakpoints). The year switch (JH → recruit scale; FR/SO/JR → player scale) is handled by the wrapper `getRecruitRtBucketClassForYear(rt, year)`:

| RT range | Color | Class |
|----------|-------|-------|
| 0–29 | `#ff6d6d` red | `.rt-low` |
| 30–39 | `#FFD700` yellow | `.rt-mid` |
| 40–49 | `#34EC27` green | `.rt-high` |
| 50+ | `#4A90D9` light blue | `.rt-elite` |

Applied on: FCC Recruits tab (and home-card RT column), `recruiting.html`, `recruiting-orders.html`, `recruiting-results.html`, training-report recruiting meta line (`{Name} - RT: n`). **Player** roster/lineup RT continues to use `getRtBucketClass` (0–40 / 41–60 / 61–80 / 81+).

**FCC Recruiting Tab**
-Place copy at the top of the Recruiting tab in the FCC, in smaller copy than the recurits list below.
    -Weeks 1-18: `Recruiting Invites Begin Week 20`
    -Week 19: `Recruiting Invites Begin Next Week`
    -Weeks 20-26: `Recruiting Invites Active`
    -Weeks 20-26 after that week's training/recruiting processing is complete, show an active link with copy `Week ## Recruiting Visits`. Pressing it takes the user to the recruiting-results.html page.
    -Weeks 27-34: same live copy as other post–regular-season weeks before week 35: `Recruiting Runs After National Tourney` (see FCC recruiting button logic in `franchise-command-center.js`)
    -Week 35 -- the main FCC CTA becomes `Recruiting`, and the copy in the Recruiting tab reads`Recruiting Is Live`
    -Week 36 -- the main FCC CTA becomes `Go To Next Season`, and teh copy in the Recruiting tab reads `Recruiting Is Complete`


**Recruiting.html Screen** (current implementation: `FrontEnd/static/recruiting.html`, `FrontEnd/static/recruiting.js`, shared table/sort/lean helpers in `FrontEnd/static/recruiting-common.js`; data from `GET /franchise/recruiting-data`)

1. **Layout:** Eight stacked **region cards** (`Region A` … `Region H`). Each card holds a scrollable table of recruits whose **`Home Region`** value resolves to that letter (first character of the stored home-region label, uppercased). There is **no** separate “Home Region” column—the region is implied by the card title.
2. **Row count:** All recruits returned for the franchise in `recruiting-data` are shown (canonical pool size **300** per season init / new season).
3. **Default ordering:** Within each region, recruits are sorted by **RT descending** by default. **Clickable column headers** reorder rows (per region table) and apply the same sort key across all eight tables on re-render.
4. **Columns (weeks ≠ 36), left to right:** `Name`, `Archetype`, `HT`, `WT`, `POS`, the twelve attributes `SC` … `FT` (display values are raw recruit attributes **floor-divided by 10**), **`RT`** (colored via recruit RT scale — see **Recruit RT color scale** above), **`Current Lean`**.
5. **`Current Lean` cell:** Built from the recruit’s `Lean` map keys `"1"`, `"2"`, `"3"` in order. Empty slots are skipped. Literal `"open"` stays `open`; otherwise values are resolved through the global **team id → team name** map when the stored value is an id, else shown as-is. Multiple values are comma-separated (same rules as the examples in the prior spec: e.g. `open`; `Morristown`; `Morristown, Bentley-Truman`; etc.).
6. **Header / chrome:** Center title **“Recruiting”**; **Back** link returns to the FCC locker room (via `buildFccUrl` / query context). **No** Recruiting Orders button on this page.
7. **Status line:** Subtitle under the header explains grouping/sorting for non–week-36 (`Recruits are grouped by home region and sorted by RT by default. Click any header to reorder all regions.`).
8. **Week 36 (signed results):** Franchise `week === 36` triggers results mode: page title **“Recruiting Results”**, subtitle **“Signed recruits are grouped below by home region.”**, last column header **`Signed`** instead of **`Current Lean`**. Signed text comes from `week_35_recruiting_results.signed_by_recruit_id` (team name, plus ` (walk on)` when applicable); unsigned recruits show **`--`**. Walk-on rows from `signed_players` are merged into the same sort pipeline as recruits; they use the same column layout. **Implementation note:** walk-ons are currently normalized with `homeRegion: '--'`, which does not bucket into `A`–`H`; confirm whether a dedicated “Walk-ons” section or a real region letter is required so all rows appear in a card.


**Recruiting-Orders.html Screen**
0. Weeks 20-26 keep the visit-order flow. Week 35 uses `Save Orders` and `Run Recruiting` instead.
1. Top Grid witih the following columms from left to right
    a. header row "Priority", "Recruit", "Home Region", "Archetype, "Pos", "RT", "Current Lean", "Adjust", "Remove"
    b. the grid start empty if the user has not saved any recruiting orders, adding players will is detailed below. 
    c. give the grid drag & drop functionality, same as our lineup screen, so the user can swap assigned rows for recruits by using the D&D functioality. Play Click tiny on this action
    d. when a row has a player in it, add a red x colum
    e. Adjust column will ahve up/down toggle buttons that move palyers up or down hen pressed. If a recruit occupies the row the player mvove to, those two recruits will flip rows. there will be no up button for row 1 and now down button for row 10. 
    f. the "Remove" column will display active red "x" buttons when there is a recruit in the row. If there is no recruit in teh row it will be a grey fill button with no functionality on press. Play x-back when a user removes a player
2. Display all Recruits, same as the recruiting.html screen
    a. when the user clicks a recruit's row, highlight the row with a light green fill and add that player to the Top Grid, the top available row in the Grid (1 is considered the top row, then 2, then 3, and so on). Play Click tiny on this action
3. If the grid is full and the user adds a new recruit, give teh user a pop up that says "All 10 rows are occupied. You must remove a recruit".
4. If the user attempts to leave the page and there is at least one recruit in the Top Grid that was not previously saved, give the following pop up "You have unsaved recruiting orders. Are you sure you want to leave?". With an orange "Back To Recruiting" button and a blue "Leave" button.
5. Weeks 20-26 use `Save Orders`, not `Submit Orders`.
    - pressing `Save Orders` saves the recruit string ids to the `Recruits` field in the FTD doc for the user's team, assigning each to the key according to the row they occupy in the Top Grid.
    - after saving, keep the user on recruiting-orders.html and show a confirmation pop up.
6. Weeks 20-26 recruiting visits are no longer processed from recruiting-orders.html.
    - recruiting invite processing now runs when the user presses `Submit Training` on training.html.
    - once that week's training/recruiting processing is complete, recruiting-orders.html should redirect to recruiting-results.html for that week.
7. When they press Back, they are taken to the screen they came from -- FCC, Recruits.html, or Training.html.

**Recruiting Logic**
-Weeks 20-26:
    - when the user presses `Save Orders`, only save the user's recruiting orders for that week
    - when the user presses `Submit Training`, run computer team recruiting orders, run that week's recruiting invite logic, process results, and populate recruiting-results.html
    - if the user does not change recruiting orders in a later week, the previously saved `FTD.Recruits` settings persist and are used again
    - special case: week 20, if the user has never saved recruiting orders and presses `Submit Training`, block training and show a modal telling the user they must save recruiting orders first
    - after processing, change FCC copy to `Week ## Recruiting Visits`

**Computer Team Recruiting Orders**
HEADLINE: For Week's 20-26, each team wins one recruit visit, and each recruit can only visit one team each week. So assuming all 128 teams submit recruiting order, there will be 128 recruiting visits each week for weeks 20-26
-for each team, builed their FTD.Recruits with the following logic
    - rank all recruits within each region according to their RT value, highest RT = 1, second highest RT = 2, etc
        - n = total number of recruits in the region (i.e. if Region B has 28 recruits, its n=28)
    - 15-20 players from the teams current region + 0-5 players outside the region
    - first step, choose random.randint(0,5) to determine how many players from outside the region will be chosen
    - for players from outside the region, choose the regions at random, and choose one of the recruits ranked 1-15 in that region at random. Note the same region can be chosen multiple times.
    - for the other 15-20 players wihtin the team's region, choose them at random with teh follwing logic
        - choose 10 of the top 16 rated players at random
        - choose the remaing 5-10 at random of all remaining players in the region (including the 5 top 10 players who were not chosen in the previous step)
-run each region's recruiting
    - shuffule the order of the regions and run recruiting in whatever order we land on
    - get all of teh recruits who received at least one bid from a team in that region and sort them by RT, highest to lowest
        - being present in any team's FTD.Recruits = receiving a recruiting bid
    - start with the first recruit on the sorted list
        - narrow the list of eligible teams to all teams or single team who gave him the highest rating. The rating is determined by key each team's FTD.Recruits associated with that recruit's id
        - if any of the teams are on the recruit's leans list, remove any teams that are not on the recruit's leans list
        - randomly choose one of the remaining teams and assign that recruit for that week's visit. Remove that team and that recruit from all calculations moving forward for that week
            -edge case if a team gets a recruit assingment, and that recruit is not the highest rated recruit on that team's list, assign the highest remaining recruit on that team's list to that team for that week. remove that recruit from all future calculations for that week.
            - then keep re-running the logic for the originally chosen recruit until he's either assigned a team within that region or there are no teams from that region remaining. 
            - note that once a player is assigned, he is removed from all future region calculatoins for that week. this is relevant for in-region players who receive bids from out of region teams, and out of region players who receive bids from in-region teams. this is why the random shuffle at the beginning is so consequential.
- after each region's recruiting has run, populate the recruiting-results.html screen as follows
    - Change copy on Recruiting buttons on FCC and recruits.html screen to read "Week ## Recruiting Visits"
    - Page Header "Week ## Recruiting Visits"
    - "Region A" (list all Regions, leading with teh user's Region, then A-H order after)
        -"{Team Name}: Recruit Name  Home Region  Archetype  HT  WT  Pos  RT"
        -- list all 16 teams, conference by conference
- Back button takes user back to page they came from, FCC or recruits.html

Note, this does not determine updates to recruits leans (we'll udpate those during complete week), or final choice (we'll update those during recruiting season, which will run between the National Championshp and End of Season system)


**Complete Week Recruiting Logic**

- **Code:** Weeks **1–19** and **27–34** (this section’s win / quality-loss rolls) run in `BackEnd/api/franchise_routes.py` as `_apply_performance_based_recruiting_lean_updates` from `_complete_week_finish_cpu_and_persist` (before visit-week lean logic). Idempotency: `franchise.recruiting_performance_lean_applied[<week>]`. Weeks **20–26** visit-based lean updates remain in `_apply_complete_week_recruiting_lean_updates` with `recruiting_lean_updates_applied`.

##Weeks 1-10##
- same logic applies to user team and all computer teams
- **Teams that do not play a game that week (bye):** no lean updates from this block.
- **National rank:** lower `natl_rank` is better (#1 is best). A **better-ranked opponent** means the opponent’s `natl_rank` is **less than** the team’s.
- **Quality loss margin:** “loss by 8 points or less” means the team’s score is **8 or fewer** points below the opponent’s (i.e. **inclusive** of an 8-point loss).
- if the team wins their game that week
    - 50% chance that a recruit with RT < 30 in their region will add them to their lean list. If the 60% chance hits, choose one recruit in their region who meets that criteria at random
    - 25% chance that a recruit with RT >= 30 in their region will add them to their lean list. If the 40% chance hits, choose one recruit in their region who meets that criteria at random. 
- if the team **loses** to a **better-ranked** opponent (`opponent.natl_rank < team.natl_rank`) **and** the loss margin is **at most 8 points** (inclusive):
    - 40% chance that a recruit with RT < 30 in their region will add them to their lean list. If the 40% chance hits, choose one recruit in their region who meets that criteria at random
    - 20% chance that a recruit with RT >= 30 in their region will add them to their lean list. If the 20% chance hits, choose one recruit in their region who meets that criteria at random.

##Weeks 11-15##
- same logic applies to user team and all computer teams
- **Bye weeks:** no lean updates from this block.
- **Quality loss** uses the same rank and margin rules as weeks 1–10.
- if the team wins their game that week
    - 60% chance that a recruit with RT < 30 in their region will add them to their lean list. If the 70% chance hits, choose one recruit in their region who meets that criteria at random
    - 40% chance that a recruit with RT >= 30 in their region will add them to their lean list. If the 50% chance hits, choose one recruit in their region who meets that criteria at random. 
- if the team loses to a better-ranked opponent and the loss margin is at most 8 points (inclusive):
    - 40% chance that a recruit with RT < 30 in their region will add them to their lean list. If the 40% chance hits, choose one recruit in their region who meets that criteria at random
    - 25% chance that a recruit with RT >= 30 in their region will add them to their lean list. If the 25% chance hits, choose one recruit in their region who meets that criteria at random.

##Weeks 16-19##
- same logic applies to user team and all computer teams
- **Bye weeks:** no lean updates from this block.
- **Quality loss** uses the same rank and margin rules as weeks 1–10.
- if the team wins their game that week
    - 80% chance that a recruit with RT < 30 in their region will add them to their lean list. If the 80% chance hits, choose one recruit in their region who meets that criteria at random
    - 60% chance that a recruit with RT >= 30 in their region will add them to their lean list. If the 60% chance hits, choose one recruit in their region who meets that criteria at random. 
- if the team loses to a better-ranked opponent and the loss margin is at most 8 points (inclusive):
    - 50% chance that a recruit with RT < 30 in their region will add them to their lean list. If the 50% chance hits, choose one recruit in their region who meets that criteria at random
    - 30% chance that a recruit with RT >= 30 in their region will add them to their lean list. If the 30% chance hits, choose one recruit in their region who meets that criteria at random. 

##Weeks 20-26##
- identify the recruiting visit for each team
    - if the player is in Region
        - if the team is not already on the player's lean list
            - determine percent chance
                - if there is a null value on the player's lean list, 95% if team wins, 75% if team loses
                - if there is not a null value on the player's lean list, 75% chance if the team wins, 40% chance if the team loses
            - percent chance based on W/L the team is added to the players lean list if there is a null value in the player's lean list. If added, the team will occupy the highest rated opening on the player's list. 1 if it's null, or 2 if it's null, or 3 if it's null
            - percent chance the team is added to the player's lean list if there is not a null value in the player's lean list. If the team is added it replaces the current #3 team on the palyer's lean list.
        -if the team is already on the player's lean list
            - if the team is currently ranked #1, it remains #1. If thera are other teams on the palyer's lean list, the lowest rated team is dropped from the lean list.
            - if the team is ranked 2 or 3, it moves up one ranking, flipping spots with the team direclty in front of it.
    -if the player is not in Region
         - if the team is not already on the player's lean list
            - determine percent chance
                    - if there is a null value on the player's lean list, 80% if team wins, 50% if team loses
                    - if there is not a null value on the player's lean list, 60% chance if the team wins, 30% chance if the team loses
            - percent chance the team is added to the players lean list if there is a null value in the player's lean list. If added, the team will occupy the highest rated opening on the player's list. 1 if it's null, or 2 if it's null, or 3 if it's null
            - percent chance the team is added to the player's lean list if there is not a null value in the player's lean list. If the team is added it replaces the current #3 team on the palyer's lean list.
        -if the team is already on the player's lean list
            - if the team is currently ranked #1, it remains #1. If thera are other teams on the palyer's lean list, the lowest rated team is dropped from the lean list.
            - if the team is ranked 2 or 3, it moves up one ranking, flipping spots with the team direclty in front of it.

##Weeks 27-34##
- same logic applies to user team and all computer teams
- **Bye weeks:** no lean updates from this block.
- **Quality loss** uses the same rank and margin rules as weeks 1–10 (better opponent = lower `natl_rank`; margin **≤ 8** inclusive).
- if the team wins their game that week
    - 90% chance that a recruit with RT < 30 in their region will add them to their lean list. If the 90% chance hits, choose one recruit in their region who meets that criteria at random
    - 75% chance that a recruit with RT >= 30 in their region will add them to their lean list. If the 75% chance hits, choose one recruit in their region who meets that criteria at random. 
- if the team loses to a **better-ranked** opponent and the loss margin is at most 8 points (inclusive):
    - 60% chance that a recruit with RT < 30 in their region will add them to their lean list. If the 60% chance hits, choose one recruit in their region who meets that criteria at random
    - 50% chance that a recruit with RT >= 30 in their region will add them to their lean list. If the 50% chance hits, choose one recruit in their region who meets that criteria at random. 
        

##Weeks 1-19 & 27-34 Player Lean List Additon Logic##
-if a player adds a team to their lean list during that week
    - if that team is already on their lean list, they advance one spot repalcing the team ahead of them (2 moves to 1, and 1 becomes 2, or 3 moves to 2 and 2 becomes 3). If the team is already 1 on the list, the lowest rated team on the player's lean list is dropped. If no other teams on the player's lean list, then no effect.
    - if that team is not already on their lean list, the team occupies the lowest rating with a null value. If all three ratings for that player are occupied, the team replaces the 3 rated team

**Week 35 Recruiting**
- week `35` is the actual commitment / signing phase
- week `35` uses a separate field on FTD:
  - `recruiting_orders_week_35`
  - dict keys are row numbers as strings: `"1"`, `"2"`, `"3"`, etc
  - values are dicts:
    - `id`
    - `points`
    - `scholarship`
    - `playing_time`

- recruiting-orders.html
  - top left = `Back`
  - top right buttons:
    - `Save Orders` (green)
    - `Run Recruiting` (orange)
  - if the user has unsaved changes and presses `Run Recruiting`, treat it as `Save Orders` first, then `Run Recruiting`
  - if the user has no saved orders and presses `Run Recruiting`, block and warn
  - page header copy = `Recruiting Focus List`
  - sub-head copy under the header:
    - `Available Roster Spots: X, Points Remaining: Z`
    - `X = 15 - returning_non_graduating_player_count`
    - `Z = 50 - currently assigned recruiting points`
    - `Points Remaining` updates in real time as the user edits point inputs, including unsaved edits
  - top grid columns:
    - `Priority`, `Name`, `Home Region`, `Archetype`, `HT`, `WT`, `POS`, `RT`, `Current Lean`, `Points`, `Playing Time`, `Adjust`, `Remove`
  - top grid preloads from saved `recruiting_orders_week_35`
  - if that field is empty, auto-fill with all recruits who currently have the user team in any lean slot, sorted RT descending
  - point inputs default to `0`
  - revisits preload saved point values
  - teams have a 50-point total budget in week `35`
  - point inputs only accept integers and block keystrokes that would push the board above 50 total points
  - checkboxes default empty on preload and on fresh add
  - `Playing Time` can be checked independently; scholarship is dormant and always saved as `false`
  - drag/drop uses insert-and-push behavior
  - row click and `+` both add/remove recruits
  - top grid is capped at 20 rows
  - trying to add a 21st recruit is blocked with a modal

- save behavior
  - saves the user board to `FTD.recruiting_orders_week_35`
  - on the user's first save only, generate CPU week-35 boards for any CPU team whose `recruiting_orders_week_35` is still empty
  - backend rejects boards whose assigned recruiting points exceed 50 total
  - confirmation modal copy:
    - `Recruiting orders are saved. You can now run recruiting.`

-computer teaam recruiting orders:
    - computer teams build out their ranking list in the following order:
        -Lean List Players: all players who have tthe computer team on their lean list.
        -Then the computer adds remaining players from their region to their list according to this logic:
            - Remaining slots = 20 - Lean List Players
            - 50% of remaining slots go to players with RT >= 25
                - choose these at random
            - 50% of remaining slots go to players with RT <= 24
                - choose these at random
            - if one RT pool cannot fill its share, roll the unused slots over to the other pool
            - no playing time promises
        - Points assignments
            - choose one random player from the <= 24 group and assign him 3 points
            - choose one random player from the >= 25 list and assign him random amount of 5-7 points
            - if one of those groups has no qualifying player on the board, skip that step
            - assign all remaining points to players on the lean list:
                - if only one player is on the lean list, he gets all of the remaining points.
                - if 2-3 players are on the lean list, give the highest RT 80% of remaining points and distribute the remainder evenly.
                - if 4+ players are on the lean list:
                    - (a) assign a random amount between 40-60% of the remaining points to one of the 4 highest RT players on the lean list (chosen at random)
                    - (b) if the roll in (a) was < 50%, assign a random amount between 40-60% of the still-remaining points to one of the 3 highest RT players remaining on the lean list (chosen at random)
                    - (c) then shuffle all remaining players on the team's lean list, and assign each a random amount of 1-4 recruiting points until all points are assigned. If you reach the end of the lean list and still have points remaining, assign all remaining points to one random player from the lean list -- incrementally adding them to his existing value. If you run out of points before reaching the end of the lean list, all remaining players get 0.
            - if there are no lean-list players on the board, fallback to the top 5 RT in-region players on the board and split the remaining points evenly among them
        - out-of-region players who are on that CPU team's lean list can receive points assignments

-run recruiting assignments

    -sort all recruits in descednign order of RT, starting with the highest value. Then run recruiting assignements one by one starting with the highest RT value

    -assingment process:
        - teams allocate points to each recruit based on the following criteria:
            - on the player's lean list receive multipliers:
                -1 = 5x, 2 = 3x, 3 = 2x 
            - playing time offer
                - if only one or two teams makes a playing time offer = 15 points per team
                - if > 2 teams make a playing time offer = 7 points per team
            - teams receive one point for having the player on their Top Grid list
            - teams receive points for the number of points they assign in their recruiting orders
            - subtotal = top-grid point + assigned recruiting points + playing-time points
            - the lean-list multiplier applies to that subtotal
            - teams not on the player's lean list use a 1x multiplier

        - choose the top 4 teams in terms of points value
        - if there are ties / more than 4 teams with nonzero value, randomly choose among lower-ranked teams to fill the remaining top-4 slots
        - total value is the total number of points of chosen teams. Example (using the 15-point playing-time value, since only two teams made PT offers):
            - for player A the following:
                - lean list: 1. Team 1, 2. Team 2, 3. null
                - playing time offers: Team 1 and Team 7
                - points per team (subtotal = 1 top-grid point + assigned points + PT points):
                    - Team 1 (assigned 10 of their points in recruiting orders): (1 + 10 + 15) = 26 points x 5 multiplier = 130
                    - Team 7 (assigned 2 of their points in recruiting orders): (1 + 2 + 15) = 18 points x 1 = 18
                    - Team 2 (assigned 5 of their points in recruiting orders): (1 + 5) = 6 points x 3 multiplier = 18
                    - Team 9 (assigned 5 of their points in recruiting orders): (1 + 5) = 6 points x 1 = 6
                    - total points = 172
                - value = random.randint(1,172)
                    - Win ranges:
                        - Team 1: 1-130, Team 7: 131-148, Team 2: 149-166, Team 9: 167-172


    - team eligibility for recruits
        - once a team has reached a roster of 15 players, they are removed from all remaining players
    - when run recruiting completes:
        - advance franchise week from `35` to `36`
        - persist signed results on the franchise doc in `week_35_recruiting_results`
        - redirect user to the FCC, displaying the modal that announces the user team's recruiting results.

- generate walkons
    - after recruiting has run, generate walks for all teams who do not have 15 players on their roster
        - walks do not receive pt promises
        - walk on year 
            - JH: 60%
            - Freshman: 20%
            - Sophomore: 10%
            - Junior: 10%
        - the core 12 attribures (SC through FT) are assigned numbers based on year
            - JH: random.randint(1,32), with a max of 3 attributes > 29, height = random.randint(66-72), weight = random.randing(155 - 179)
            - Freshman: random.randint(1,42), with a max of 3 attributes > 39, height = random.randint(66-74), weight = random.randing(155 - 189)
            - Sophmore: random.randint(1,52), with a max of 3 attributes > 44, height = random.randint(67-75), weight = random.randing(165 - 199)
            - Junior: random.randint(1,62), with a max of 3 attributes > 49, height = random.randint(68-77), weight = random.randing(175 - 209)
        - year = the rolled year above; signed walk-ons advance one step at season transition like recruits (JH → Freshman, ..., Junior → Senior)
        - archetype = `Walk On`
        - names use the same name generator as recruit generation
        - position ratings are derived from their generated attributes

- season 1 init walk-ons (franchise init, 3 per team)
    - use this same walk-on generation logic (year roll + year-based attributes/height/weight)
    - because these players land directly on an active season-1 roster, **instantly upgrade the rolled year one step** at generation: JH → Freshman, Freshman → Sophomore, Sophomore → Junior, Junior → Senior
    - attributes/height/weight are rolled from the **pre-upgrade** year's ranges (same as a signed walk-on entering next season)
    - net effect: season-1 walk-on year distribution is Freshman 60%, Sophomore 20%, Junior 10%, Senior 10%; JH never appears on a roster

- jersey numbers
    - all recruits and walkons receive a jeresey number at random according to their highest RT position. Jersey numbers already assinged to a teammate are excluded. 
        - PG: 0-36
        - SG & SF: 0-45, 77 
        - PF & C: 0-55, 88, 91, 99 excluding (20-29)

**Week 36 Recruiting State**
- recruiting is closed
- `recruiting.html` becomes the signed-results page
- display all recruits with `Signed` replacing `Current Lean`
- signed display rules:
  - signed recruit -> signed team name
  - walk-on -> signed team name + ` (walk on)`
  - unsigned recruit -> `--`
- `Run Recruiting` is the catalyst that advances week `35` -> `36`

**Recruit Init Attribute Logic**

> **SUPERSEDED by the Player Attribute Recalibration (2026-07).** The 20-archetype attribute machinery below (`_select_archetype`, `_generate_recruit_profile`, `YEAR_TIER_RANGES`, per-archetype strong/secondary/height tables, `_generate_weight`) was **removed**. It is retained below only as **historical reference**; do not treat it as current. The tier→RT frequencies, position profiles, and grow-into-frame height now live in `10_Players_Systems/Player_Attribute_System.md` (generation) and `Position_Ratings_System.md` (RT).

**Current generation (`RecruitManager.generate_recruits_list` → `BackEnd/utils/player_generation.py`):** position-intent-first.
1. **Tier** — `draw_tier()` from `TIER_FREQUENCY` (Poor 7 / BelowAverage 20 / Average 40 / Good 20 / Great 11 / Elite 2) → sets the JH RT anchor (`JH_ANCHOR_BY_TIER` 20/25/30/35/40/50).
2. **Position intent** — `draw_position_intent()` (~20% each of PG/SG/SF/PF/C).
3. **Height** — `draw_height(intent, year)` grows-into-frame: adult draw minus the remaining share of the career HT gain (a JH lands ~3.2in below frame).
4. **Attributes** — `generate_player` draws the position's profile (`position_profile`) scaled to hit `target_rt(tier, year)`, writes both `anchor_` and live, CH = flat `randint(1,100)`.
5. **Stamped:** `entry_tier`, `position_intent`, `development` — and these are **persisted through signing → FPD** (the pass-2 fix; a dropped `entry_tier` previously down-classified recruits). **Archetype is now a cosmetic derived label** (`_recruit_display_archetype` from intent+tier), NOT a generation input.

---

**HISTORICAL (removed code — do not use):**

- **Code:** `RecruitManager` in `BackEnd/models/franchise_manager.py` — `_select_archetype()`, `_generate_recruit_profile(archetype, year="JH")`, `_generate_weight(height)`, with post-processing in `generate_recruits_list()`. Year-tier ranges live in the `YEAR_TIER_RANGES` class constant. Expected ranges are encoded in `tests/test_recruit_archetypes.py`.

1. **Archetype selection** (`_select_archetype`) — weighted random choice (`random.choices`):

| Archetype | Weight |
|-----------|--------|
| Five-Star | 1 |
| Four-Star | 4 |
| Average | 13.6 |
| Below Average | 13.6 |
| All other archetypes (each) | 3.6 |

Other archetypes: Defensive Wizard, All-Around Scorer, Classic PG, Classic SG, Classic SF, Classic PF, Classic C, Pure Shooter, Intangibles, Athlete, Inside Defender, Outside Defender, Outside Dual Threat, Driver, Outside C, Three & D.

2. **Attribute range tiers** — every attribute is rolled with `random.randint` from one of four tiers:

-JH
| Tier | Range |
|------|-------|
| STRONG | 20-80 |
| SECONDARY | 10-60 |
| STANDARD | 1–40 |
| WEAK | 1–20 |

-Freshman
| Tier | Range |
|------|-------|
| STRONG | 30-80 |
| SECONDARY | 20-60 |
| STANDARD | 10–40 |
| WEAK | 10–20 |

-Sophomore
| Tier | Range |
|------|-------|
| STRONG | 40-85 |
| SECONDARY | 30-70 |
| STANDARD | 10–50 |
| WEAK | 10–30 |

-Junior
| Tier | Range |
|------|-------|
| STRONG | 60-95 |
| SECONDARY | 40-80 |
| STANDARD | 10–60 |
| WEAK | 10–50 |

The 12 profile attributes: `SC, SH, ID, OD, PS, BH, RB, AG, ST, ND, IQ, FT`. Each archetype defines strong attrs, secondary attrs, and a height range; all profile attributes not listed roll STANDARD (except Below Average, where everything rolls WEAK). **`CH` is rolled separately** (see post-processing).

| Archetype | Strong | Secondary | Height (in) |
|-----------|--------|-----------|-------------|
| Five-Star | all 12 profile attrs | — | 69–80 |
| Four-Star | — | all 12 profile attrs | 66–78 |
| Defensive Wizard | ID, OD | ST, AG | 66–75 |
| All-Around Scorer | SH, SC | ST, AG | 66–75 |
| Classic PG | BH, PS | OD, IQ | 66–72 |
| Classic SG | SH | OD | 66–74 |
| Classic SF | SC, OD | AG | 69–75 |
| Classic PF | RB | ST | 70–76 |
| Classic C | ID, ST | RB, SC | 72–78 |
| Pure Shooter | SH, FT | — | 66–73 |
| Intangibles | IQ, ND | — | 66–75 |
| Athlete | AG, ST, ND | — | 66–75 |
| Inside Defender | ST, ID | — | 71–80 |
| Outside Defender | AG, OD | — | 66–74 |
| Average | — | — | 66–75 |
| Below Average | all WEAK | — | 66–74 |
| Outside Dual Threat | SH, AG | — | 66–75 |
| Driver | SC, AG | — | 66–75 |
| Outside C | ST, SH | — | 72–77 |
| Three & D | SH | ID, OD | 69–75 |

3. **Height & weight** — height rolls uniformly within the archetype's range; weight derives from height (`_generate_weight`):

| Height | Weight (lbs) |
|--------|--------------|
| < 72 | 150–181 |
| 72–75 | 170–194 |
| 76–80 | 195–231 |
| > 80 | 209–260 |

4. **Post-processing** (in `generate_recruits_list`, after the profile roll):
- `_roll_recruit_character(archetype, year)` sets `CH`:
  - **Intangibles:** `random.randint(year STRONG minimum, 100)` using `YEAR_TIER_RANGES` (JH 20, Freshman 30, Sophomore 40, Junior 60).
  - **All other archetypes:** `random.randint(1, 100)`.
- `Player.randomize_game_attributes(attributes, preserve_character=True)` sets `NG = 1.0`, `MO = 0`, `EM = random.randint(1, 100)`, and **preserves** the recruit `CH` / `anchor_CH`.
- Signed recruits keep `CH` through `_normalize_new_franchise_player_attributes` (`preserve_character=True` on the same helper).
- `compute_position_ratings(recruit, profile="recruit")` derives position ratings from the final attributes + height.
- `year` comes from the **Recruit Distribution By Year** roll (see top of doc) and selects which tier table applies; `created_at` timestamped; names come from the franchise name generator (`choose_franchise_first_name` + random last name).

---

## UI Redesign — Recruiting Hub (in progress, started 2026-07-18)
The recruiting UI is being rebuilt into a single phase-aware **Hub** that takes over `recruiting.html`. Backend data model (this doc) is unchanged. Spec + prompt-by-prompt status: [`projects/Recruiting_Hub_Redesign/recruiting_hub_implementation_spec.md`](../projects/Recruiting_Hub_Redesign/recruiting_hub_implementation_spec.md).
- **Prompt 0 (foundation) shipped:** shared vanilla spine — `FrontEnd/static/recruiting-spine.{js,css}` (`window.RecruitingSpine`), QA gallery `recruiting-spine-gallery.html`. Reuses `rtBucket.js` + `playerYear.js`; the `Lean` ranked-ladder consumes the existing `{"1","2","3"}` `Lean` object verbatim.
- **Deferred backend item (Prompt 2):** the hub must own the invite loop end-to-end — currently invites save on the recruiting page but execute from Training's *Submit Training* (`franchise_routes.py` `_process_weekly_recruiting_invites`).
