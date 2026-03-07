
**Scope**
- This doc covers recruiting phase 1 only.
- Phase 1 includes:
    - generating 200 recruits for a franchise
    - displaying recruits on standalone recruiting pages
    - allowing the user to rank up to 10 recruits
    - saving those ranked FRD string ids into the user's FTD `Recruits` field
- Out of scope for this task:
    - recruit commitments / signings
    - weekly recruiting simulation / resolution
    - lean changes over time
    - recruiting outcomes tied to week advancement
    - tournament performance affecting recruiting
    - signed recruits being added to rosters
    - offseason roster turnover tied to recruiting

**Franchise Init / New Season Init**
0. Add a new `Recruits` field to each FTD doc.
    - This will be a dict with potential keys `"1"` through `"10"`.
    - Values hold FRD string ids.
    - On init, keys `"1"` through `"10"` should exist and each value should be `None`.
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
    - reset every team's FTD `Recruits` field back to keys `"1"` through `"10"` with `None` values
    - delete that franchise's prior season FRD recruits
    - generate the new season's 200 FRD recruits

**FCC Update**
- Remove the Recruits tab from the FCC
- Add a `Recruits` button to the Resources tab that links to the `recruiting.html` screen

**FCC Recruiting Button**
- Place a Recruiting button in the upper right of the FCC, below the Run Training / Play Next Game button.
    - Give it a green fill with bold silver copy.
    - Weeks 1-19:
        - this is a dead button
        - pressing it has no effect
        - give it the reduced opacity / overlay treatment that we use for dead buttons elsewhere in the experience
        - button copy reads `Recruiting Begins Week 20`
    - Weeks 20-34:
        - button becomes active
        - remove the dead-button overlay / reduced opacity
        - pressing it takes the user to the `recruiting-orders.html` page


**Recruiting.html Screen**
1. Display all 200 recruits.
    - Default sort on page load is descending order of each recruit's top RT value, from highest value to lowest.
2. Use the same display that we use for the current Recruits tab in the FCC that we're sunsetting in this task.
    - Add the following columns:
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
    - When the user presses that button it takes them to the `recruiting-orders.html` screen.


**Recruiting-Orders.html Screen**
0. Top right: `Submit Orders` button, green fill with bold silver copy when active.
    - The button starts dead and becomes active when there is at least one recruit in the Top Grid.
    - Top left: orange back button.
1. Top Grid with the following columns from left to right:
    - `Priority`, `Recruit`, `Home Region`, `Archetype`, `Pos`, `RT`, `Current Lean`, `Adjust`, `Remove`
    - The grid starts empty if the user has not saved any recruiting orders.
    - If the user previously saved recruiting orders, preload those recruits into the grid and highlight those recruits in the lower recruits table immediately.
    - Give the grid drag-and-drop functionality, same as our lineup screen, so the user can swap assigned rows for recruits by using drag and drop.
        - Play `Click tiny` on this action.
    - Adjust column behavior:
        - provide up / down toggle buttons that move recruits up or down when pressed
        - if a recruit occupies the row the moving recruit goes to, those two recruits swap rows
        - there is no up button for row 1 and no down button for row 10
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
4. If the grid is full and the user adds a new recruit, give the user a popup that says `All 10 rows are occupied. You must remove a recruit`.
5. If the user attempts to leave the page and there is at least one recruit in the Top Grid that was not previously saved, give the following popup:
    - `You have unsaved recruiting orders. Are you sure you want to leave?`
    - include an orange `Back To Recruiting` button and a blue `Leave` button
6. When a user presses `Submit Orders`, save the recruit string ids to the `Recruits` field in the FTD doc for the user's team.
    - Assign each recruit to the key that matches the row it occupies in the Top Grid.
    - Persist only occupied keys.
        - Example: if rows 1-8 are occupied and rows 9-10 are empty, persist keys `"1"` through `"8"` only.
    - If a user removes recruits before saving, compress the saved ranking so there are no gaps.
7. When a user presses `Submit Orders`, they are taken back to the FCC.
8. When the user presses `Back`, take them to the screen they came from, either FCC or `recruiting.html`.
    - Use URL query-param source tracking as the single source of truth for this behavior.
