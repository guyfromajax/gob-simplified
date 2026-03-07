
**Scope**
- This doc currently covers recruiting phases 1 and 2.
- Phase 1 includes:
    - generating 200 recruits for a franchise
    - displaying recruits on standalone recruiting pages
    - allowing the user to rank up to 20 recruits
    - saving those ranked FRD string ids into the user's FTD `Recruits` field
- Phase 2 adds:
    - one weekly recruit visit assignment per team during weeks `20-26`
    - computer-team recruiting order generation each week
    - one-submit-per-week recruiting lockout for the user
    - persistence of weekly team/recruit visit results
    - `recruiting-results.html`
    - post-submit button state changes on FCC and `recruiting.html`
- Out of scope for this task:
    - recruit commitments / signings
    - lean changes over time
    - tournament performance affecting recruiting
    - signed recruits being added to rosters
    - offseason roster turnover tied to recruiting
    - weeks `27-34` recruiting logic

**Franchise Init / New Season Init**
0. Add a new `Recruits` field to each FTD doc.
    - This will be a dict with potential keys `"1"` through `"20"`.
    - Values hold FRD string ids.
    - On init, keys `"1"` through `"20"` should exist and each value should be `None`.
1. Add two new fields to each new doc in the FRD collection.
    - Existing FRD docs do not need to be retrofitted because existing franchise instances will be deleted before implementation.
    - `Home Region`
        - Store as a string value, not an integer.
        - Upon init assign a random value from `[A, B, C, D, E, F, G, H]`.
    - `Lean`
        - This is a dict with keys `"1"`, `"2"`, `"3"`.
        - Values are either:
            - the literal string `"open"` for key `"1"`, or
            - a team id stored as a string, or
            - `None`
        - Upon season init:
            - each recruit's key `"1"` value is determined as follows:
                - 75% chance == `"open"`
                - 25% chance it is one of the 16 teams in the recruit's assigned home region
            - if key `"1"` == `"open"`, keys `"2"` and `"3"` must each == `None`
            - if key `"1"` != `"open"`:
                - 80% chance key `"2"` == `None`
                - 20% chance key `"2"` is another team in the recruit's assigned home region, omitting the team used in key `"1"` from the random draw
            - all key `"3"` values == `None`
2. Upon new franchise init and the start of each new season within a franchise instance, create 200 new recruits per our recruit generation logic.
3. At the start of each new season within a franchise instance:
    - reset every team's FTD `Recruits` field back to keys `"1"` through `"20"` with `None` values
    - delete that franchise's prior season FRD recruits
    - generate the new season's 200 FRD recruits

**Recruiting API**
- `GET /franchise/recruiting-data`
    - returns:
        - the user's team / team_id
        - current franchise week
        - `current_results_week` if the current week's recruiting visits have already been processed
        - current saved FTD `Recruits` order
        - all FRD recruits for that franchise
        - team id -> team name map for rendering `Lean`
- `GET /franchise/recruiting-results`
    - returns the persisted recruiting visit results for the requested week
- `POST /franchise/recruiting-orders`
    - accepts:
        - `franchise_id`
        - ordered array of recruit ids
    - validation rules:
        - allowed only during weeks `20-26`
        - maximum 20 recruit ids
        - duplicate recruit ids are rejected
        - recruit ids must belong to that franchise's FRD pool
        - the user can only submit once per week
    - save behavior:
        - writes compressed keys only (`"1"` through `"N"`) into FTD `Recruits`
        - generates fresh computer-team `FTD.Recruits` orders for that week
        - runs weekly recruiting visit resolution for all 128 teams
        - persists that week's final team/recruit visit pairings

**Recruiting Results Persistence**
- Persist recruiting visit results by week at the franchise level.
- Store only the final pairing output for each week:
    - team
    - recruit
- Example shape at a high level:
    - week 20: all team / recruit visit pairings
    - week 21: all team / recruit visit pairings
    - week 22: all team / recruit visit pairings
- Results persist to the FCC.
- At the start of each new recruiting week, every team begins with no assigned visit for that new week.
- Team `FTD.Recruits` top-20 bids persist week to week unless explicitly changed by the user or regenerated for CPU teams.

**FCC Update**
- Remove the Recruits tab from the FCC
- Add a `Recruits` button to the Resources tab that links to the `recruiting.html` screen

**FCC Recruiting Button**
- Place a Recruiting button in the upper right of the FCC, below the Run Training / Play Next Game button.
    - Give it a green fill with bold white copy.
    - Weeks 1-19:
        - this is a dead button
        - pressing it has no effect
        - give it the reduced opacity / overlay treatment that we use for dead buttons elsewhere in the experience
        - button copy reads `Recruiting Begins Week 20`
    - Weeks 20-26:
        - if the current week's recruiting has not been processed yet:
            - button becomes active
            - remove the dead-button overlay / reduced opacity
            - button copy reads `Recruiting`
            - pressing it takes the user to the `recruiting-orders.html` page
        - if the current week's recruiting has already been processed:
            - button becomes active
            - button copy reads `Week ## Recruiting Visits`
            - pressing it takes the user to `recruiting-results.html`
    - Weeks 27-34:
        - current implementation shows the button as dead with copy `Recruiting Returns Later`
        - weeks 27-34 logic will be implemented in a later phase


**Recruiting.html Screen**
1. Display all 200 recruits.
    - Default sort on page load is descending order of each recruit's top RT value, from highest value to lowest.
2. Use the same display that we use for the current Recruits tab in the FCC that we're sunsetting in this task.
    - The recruit list keeps the legacy `HT` and `WT` columns.
    - Columns displayed are:
        - `Name`, `Home Region`, `Archetype`, `HT`, `WT`, `POS`, `SC`, `SH`, `ID`, `OD`, `PS`, `BH`, `RB`, `AG`, `ST`, `ND`, `IQ`, `FT`, `RT`, `Current Lean`
    - Recruiting attributes display using the same bucketed format as the prior FCC recruits table.
        - Example: values `0-9` display as `0`, values `10-19` display as `1`, values `20-29` display as `2`, and so on.
    - Relative to the legacy table:
        - after `Name` and before `Archetype`, add `Home Region` and display the recruit's home region string (`A` through `H`)
        - after `RT`, add `Current Lean`
    - `Current Lean` display rules:
        - display all populated values associated with that recruit, separated by commas, in order of key `"1"`, key `"2"`, key `"3"`
        - do not display the key labels
        - if a lean value is a team id string, render the team name on the frontend
        - if key `"1"` value is `"open"`, display `open`
        - example with key `"1"` == `"open"`: `open`
        - example with only a key `"1"` team value: `Morristown`
        - example with key `"1"` and key `"2"` team values: `Morristown, Bentley-Truman`
        - example with key `"1"`, key `"2"`, and key `"3"` team values: `Morristown, Bentley-Truman, Xavien`
3. Make the header row clickable to sort.
    - This applies to all displayed columns except `Name`.
    - First click on a column sorts by that column highest-to-lowest.
    - Second click on that same column sorts lowest-to-highest.
    - Third click returns to highest-to-lowest, and so on.
    - For `Current Lean`, sort according to key `"1"` value only.
4. Starting week 20, display a green fill button in the top right with the copy `Recruiting Orders`.
    - button copy is white
    - if the current week's recruiting has not been processed yet:
        - button copy reads `Recruiting Orders`
        - when the user presses that button it takes them to the `recruiting-orders.html` screen
    - if the current week's recruiting has already been processed:
        - button copy reads `Week ## Recruiting Visits`
        - when the user presses that button it takes them to `recruiting-results.html`
    - in the current implementation, this button is hidden before week 20 and after week 26


**Recruiting-Orders.html Screen**
0. Top right: `Submit Orders` button, green fill with bold silver copy when active.
    - button copy is white
    - The button starts dead and becomes active when there is at least one recruit in the Top Grid.
    - Top left: orange back button.
1. Top Grid with the following columns from left to right:
    - `Priority`, `Recruit`, `Home Region`, `Archetype`, `Pos`, `RT`, `Current Lean`, `Adjust`, `Remove`
    - The grid starts empty if the user has not saved any recruiting orders.
    - If the user previously saved recruiting orders, preload those recruits into the grid and highlight those recruits in the lower recruits table immediately.
    - Give the grid drag-and-drop functionality, same as our lineup screen, so the user can swap assigned rows for recruits by using drag and drop.
        - Play `Click tiny` on this action.
        - Current implementation supports swapping between occupied rows; order is always compressed so filled rows remain contiguous from priority `1` through priority `N`.
    - Adjust column behavior:
        - provide up / down toggle buttons that move recruits up or down when pressed
        - if a recruit occupies the row the moving recruit goes to, those two recruits swap rows
        - there is no up button for row 1 and no down button for row 20
    - Remove column behavior:
        - display active red `x` buttons when there is a recruit in the row
        - if there is no recruit in the row it will be a grey fill button with no functionality on press
        - play `x-back` when a user removes a recruit
2. Display all recruits below the Top Grid, same as the `recruiting.html` screen.
    - All recruit-list columns except `Name` are sortable here as well.
    - `Current Lean` sorts according to key `"1"` value only.
3. Recruit row click behavior in the lower table:
    - if the recruit is not currently in the Top Grid:
        - highlight the row with a light green fill
        - add that recruit to the top available row in the Top Grid (`1` is the top row, then `2`, then `3`, and so on)
        - play `Click tiny`
    - if the recruit is already in the Top Grid:
        - remove that recruit from the Top Grid
        - remove the highlight from that recruit's row in the lower table
        - play `x-back`
4. If the grid is full and the user adds a new recruit, give the user a popup that says `All 20 rows are occupied. You must remove a recruit`.
5. If the user attempts to leave the page and there is at least one recruit in the Top Grid that was not previously saved, give the following popup:
    - `You have unsaved recruiting orders. Are you sure you want to leave?`
    - include an orange `Back To Recruiting` button and a blue `Leave` button
6. When a user presses `Submit Orders`, save the recruit string ids to the `Recruits` field in the FTD doc for the user's team.
    - Assign each recruit to the key that matches the row it occupies in the Top Grid.
    - Persist only occupied keys.
        - Example: if rows 1-18 are occupied and rows 19-20 are empty, persist keys `"1"` through `"18"` only.
    - If a user removes recruits before saving, compress the saved ranking so there are no gaps.
    - The user can only submit once per week. There are no redo's for that week.
7. When a user presses `Submit Orders`, they are taken back to the FCC.
8. When the user presses `Back`, take them to the screen they came from, either FCC or `recruiting.html`.
    - Use URL query-param source tracking as the single source of truth for this behavior.
    - Current query-param values are:
        - `from=fcc`
        - `from=recruiting`

**Recruiting Logic**
- When the user presses `Submit Orders` during weeks `20-26`:
    - save the user's `FTD.Recruits`
    - generate fresh computer-team recruiting orders for the other 127 teams for that week
    - run that week's recruiting logic and process results
    - persist that week's recruiting visit results at the franchise level
    - populate `recruiting-results.html`
    - change the copy on the Recruiting button on the FCC and `recruiting.html` screens to read `Week ## Recruiting Visits`
    - when pressed, that button takes the user to `recruiting-results.html`
- This visit logic applies only to weeks `20-26`.
- Weeks `27-34` recruiting logic will be defined in a later phase.

**Computer Team Recruiting Orders**
- Headline:
    - For weeks `20-26`, each team wins one recruit visit, and each recruit can only visit one team each week.
    - Assuming all 128 teams submit recruiting orders, there will be 128 recruiting visits each week for weeks `20-26`.
- For each CPU team, build that team's `FTD.Recruits` fresh each week with the following logic:
    - rank all recruits within each region according to their RT value, highest RT = 1, second highest RT = 2, etc
        - ties are broken randomly
        - `n = total number of recruits in the region`
    - each team ends with up to 20 ranked recruits
    - choose 15-20 recruits from the team's current region plus 0-5 recruits outside the region
    - first choose `random.randint(0,5)` to determine how many players from outside the region will be chosen
    - for recruits from outside the region:
        - choose outside regions at random
        - exclude the team's own region from those draws
        - the same outside region can be chosen multiple times
        - choose one of the recruits ranked `1-15` in that region at random
    - for the remaining in-region recruits:
        - choose 10 of the top 16 rated players at random
            - if there are fewer than 16 recruits in the region, choose from however many exist
            - if there are fewer than 10 recruits in that top bucket, choose as many as exist
        - choose the remaining 5-10 at random from the remaining in-region recruits
            - exclude recruits already chosen in the previous step
            - the remaining pool can include the top-16 recruits who were not selected in the first step
    - once the CPU team's recruit pool has been selected, rank that final board from highest RT to lowest RT before saving it into `FTD.Recruits`
        - ties are broken randomly

**Weekly Region Recruiting Resolution**
- Run each week's recruiting for weeks `20-26` after the user submits.
- Shuffle the order of the regions and run recruiting in whatever order we land on.
- For each region pass:
    - include all 16 teams in that region in the calculations
    - once a team receives a visit assignment, remove that team from all future calculations for that week, including other regions
    - get all recruits who received at least one bid from a team in that region and sort them by RT, highest to lowest
        - ties are broken randomly
        - being present in any team's `FTD.Recruits` = receiving a recruiting bid
    - start with the first recruit on the sorted list
        - narrow the eligible team list to the team or teams who gave that recruit the highest rating
            - the rating is the key position in each team's `FTD.Recruits` associated with that recruit's id
        - if any of those teams are on the recruit's `Lean` list, remove any teams that are not on the recruit's `Lean` list
        - if lean filtering produces no overlap, ignore lean filtering and continue with the original eligible team set
        - if the recruit's lean is `open`, apply no lean filtering
        - if more than one team remains tied at that point, resolve the winner with a prestige-weighted random draw
            - take the first two digits of each tied team's prestige value
                - Example: `745 -> 74`, `609 -> 60`, `450 -> 45`, `311 -> 31`
            - those values become the number of entries that team gets in the random draw
            - sum all tied-team entries, then draw `random.randint(1, total_entries)`
            - whichever team's numeric range contains that draw wins the visit
        - if only one team remains eligible, that team gets the visit
        - remove that team and that recruit from all calculations moving forward for that week
            - a team can receive at most one visit in a week
            - a recruit can receive at most one visit in a week
            - user team has no priority over CPU teams
        - edge case:
            - if a team gets a recruit assignment and that recruit is not the highest remaining recruit on that team's list, assign the highest remaining available recruit on that team's list to that team for that week
            - remove that reassigned recruit from all future calculations for that week
            - keep rerunning the original recruit's logic until he is either assigned within that region pass or there are no eligible teams from that region remaining
            - if a team runs out of available recruits on its list during this process, that team gets no visit for that week
    - note:
        - once a recruit is assigned, he is removed from all future region calculations for that week
        - this is relevant for in-region recruits who receive bids from out-of-region teams, and out-of-region recruits who receive bids from in-region teams
        - this is why the random region shuffle at the beginning is consequential

**Recruiting-Results.html Screen**
- After each week's recruiting has run, populate `recruiting-results.html` as follows:
    - change Recruiting button copy on FCC and `recruiting.html` to read `Week ## Recruiting Visits`
    - page header: `Week ## Recruiting Visits`
    - show all regions, leading with the user's region, then resume `A-H` order after that
        - Example if user region is `D`: `D, A, B, C, E, F, G, H`
    - within each region:
        - list teams conference by conference
        - within each conference, order teams alphabetically by team name
        - display one row per team
        - if a team received a visit, display:
            - `{Team Name}: Recruit Name  Home Region  Archetype  HT  WT  Pos  RT`
        - if a team did not receive a visit, display `no visit`
- Back button takes the user back to the screen they came from, FCC or `recruiting.html`
- Use the same query-param source tracking approach as the rest of recruiting:
    - `from=fcc`
    - `from=recruiting`

**Still Out Of Scope**
- This phase does not determine recruit lean updates.
    - Lean updates will happen during complete week.
- This phase does not determine final recruit choice / commitment.
    - Final recruiting season logic will run between the National Championship and the End of Season system.
