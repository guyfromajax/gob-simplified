
**Franchise Init**
0. Add a new "Recruits" field to the FTD docs (this will be a dict with 1-10 key/value pairs wiht the keys being "1", "2", "3", an so on, values will init as None, and will hold FRD string ids in the future)
1. Add two new fields to each docment in the FRD collection, note these do not need to be retrofitted to any existing FRD documents
    - "Home Region" -- assign a random.randint(1,8) (this will be an integer field)
        - Note this will sync to the teams' regions
    -"Lean" (this will be a dict with 1-3 key/value pairs wiht the keys being "1", "2", "3")
        -if key 1 == "open", keys 2 and 3 each == "" or none
        -upon season init
            - each player's key 1 value is determined as follows:
                - 75% chance == "open"
                - 25% chance it's one of the 16 teams in their assigned region (represetned as a string value of the team's name)
            - if that player's key 1 value != "open"
                -80% chance key 2 == "" or none
                -20% chance key 2 is another team in the palyers assigned region, omitting the team that is their key 1 value from the random draw
            - all key 3 values == "" or None
2. Upon new franchise init and the start of each new season within a franchise instance, create 200 new recruits per our recruit generation logic.

**FCC Update**
-Remove the Recruits tab from the FCC
-Add a "Recruits" button to the Resources tab that links to the recruiting.html screen

**FCC Recruiting Button**
-Place a Recruiting button in the upper right of the FCC, below the Run Training / Play Next Game button -- give it a green fill with bold silver copy. When active, button takes the user to the recruiting.html page.
    -Weeks 1-19, this is a dead button. Pressing it has no effect and give it a reduced opacity or overlay that we use to indicate dead buttons in teh rest of our experience. Button copy reads "Recruiting Begins Week 20"
    -Weeks 20-26 -- button becomes active. Remove the overlay / reduced opacity. Pressing it takes the user to the recruiting-orders.html page.
    -Weeks 27-34 -- button is inactive and recruiting is not live.
    -Week 35 -- the main FCC CTA becomes `Recruiting`, and bold green copy below it reads `Recruiting Is Live`
    -Week 36 -- the main FCC CTA becomes `Go To Next Season`


**Recruiting.html Screen**
1. Display all 200 recruits, in descending order of their top RT value, from highest value to lowest
2. Use the same display that we use for the current Recruits tab in teh FCC that we're sunsetting in this task. Add the following columns:
    - After "Name" and before "Archetype" add "Home Region" and dispaly the recruit's home region
    - After "RT" add "Current Lean" and display all values associated with that recruit, separated by commas, in order of key 1, key 2, key 3. Do not display the key. If the recruit's key 1 value us "open", display open.
        - Example of recruit with key 1 == open: "open"
        - Exmaple of recruit with only a key 1 value: "Morristown"
        - Example of recruit with key 1 and key 2 values: "Morristown, Bentley-Truaman"
        - Example of recruit with key 1, key 2, and key 3 values: "Morristown, Bentley-Truman, Xavien"
3. Starting week 20, display a green fill button in teh top right wiht the copy "Recruiting Orders"
    -when the user presses that button it takes them to the recruiting-orders.html screen
4. In week `36`, this screen becomes the signed-results page
    - replace `Current Lean` with `Signed`
    - show all recruits
    - append walk-ons below the recruit pool


**Recruiting-Orders.html Screen**
0. Weeks 20-26 keep the visit-order flow. Week 35 uses `Save Orders` and `Run Recruiting` instead.
1. Top Grid witih teh following columms from left to right
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
5. When the user pressed "Submit Recruting Orders" button, save the recruit string ids to the "Recruits" field in the FTD doc for the user's team. Assiging eaach to the key in the FTD "Recruits" field according to the row in the Top Grid tha tthey occupy.
6. When a user presses Submit Recruiting Orders, they are taken back to the FCC. When they press Back, they are taken to screen they came from -- FCC or Recruits.html.

**Recruiting Logic**
-when the user presses "Submit Recruiting Orders"
    - run computer team recruiting orders (details below)
    - run that weeks' recruiting logic and process results (details below)
    - populate recruiting-results.html screen (details below)
    - change the copy on the Recruiting button on teh FCC and recruiting.html screens to read "Week ## Recruiting Results" and when pressed, take the user to the recruiting-results.html screen

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

##Weeks 1-10##
- same logic applies to user team and all computer teams
- if the team wins their game that week
    - 15% chance that a recruit with RT < 30 in their region will add them to their lean list. If the 10% chance hits, choose one recruit in their region who meets that criteria at random
    - 5% chance that a recruit with RT >= 30 in their region will add them to their lean list. If the 5% chance hits, choose one recruit in their region who meets that criteria at random. 

##Weeks 11-15##
- same logic applies to user team and all computer teams
- if the team wins their game that week
    - 40% chance that a recruit with RT < 30 in their region will add them to their lean list. If the 10% chance hits, choose one recruit in their region who meets that criteria at random
    - 10% chance that a recruit with RT >= 30 in their region will add them to their lean list. If the 5% chance hits, choose one recruit in their region who meets that criteria at random. 

##Weeks 16-19##
- same logic applies to user team and all computer teams
- if the team wins their game that week
    - 60% chance that a recruit with RT < 30 in their region will add them to their lean list. If the 10% chance hits, choose one recruit in their region who meets that criteria at random
    - 20% chance that a recruit with RT >= 30 in their region will add them to their lean list. If the 5% chance hits, choose one recruit in their region who meets that criteria at random. 


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
- if the team wins their game that week
    - 80% chance that a recruit with RT < 30 in their region will add them to their lean list. If the 10% chance hits, choose one recruit in their region who meets that criteria at random
    - 50% chance that a recruit with RT >= 30 in their region will add them to their lean list. If the 5% chance hits, choose one recruit in their region who meets that criteria at random. 
        

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
    - `scholarship`
    - `playing_time`

- recruiting-orders.html
  - top left = `Back`
  - top right buttons:
    - `Save Orders` (green)
    - `Run Recruiting` (orange)
  - if the user has unsaved changes and presses `Run Recruiting`, treat it as `Save Orders` first, then `Run Recruiting`
  - if the user has no saved orders and presses `Run Recruiting`, block and warn
  - top grid columns:
    - `Priority`, `Name`, `Home Region`, `Archetype`, `HT`, `WT`, `POS`, `RT`, `Current Lean`, `Scholarship`, `Playing Time`, `Adjust`, `Remove`
  - top grid preloads from saved `recruiting_orders_week_35`
  - if that field is empty, auto-fill with all recruits who currently have the user team in any lean slot, sorted RT descending
  - checkboxes default empty on preload and on fresh add
  - `Playing Time` cannot be checked unless `Scholarship` is checked
  - drag/drop uses insert-and-push behavior
  - row click and `+` both add/remove recruits
  - top grid length is uncapped

- save behavior
  - saves the user board to `FTD.recruiting_orders_week_35`
  - on the user's first save only, generate CPU week-35 boards for any CPU team whose `recruiting_orders_week_35` is still empty
  - confirmation modal copy:
    - `Recruiting orders are saved. You can now run recruiting.`

-computer teaam recruiting orders:
    - computer teams build out their ranking list in the following order:
        -all players who have tthe computer team on their lean list are the highest rated on their priorities (their version of a Top Grid ordering, even though we never need to see a Top Grid for a computer team in teh UI, their rankings are always  hidden from the user.). Then those players are prioritized from highest RT value to lowest.
        -Then the computer adds every remaining player from their region to their list, in order of highest RT to lowest. They offer all players with RT > 24 a scholarship. They offer no playing time promises.
        -Then, remove 7 players from their list at random. Only caveat is you cannot remove any players who have that team on their lean list.
        - scholarship offers are determined after those 7 removals
        - out-of-region players who are on that CPU team's lean list can still receive scholarship offers

-run recruiting assignments

    -sort all recruits in descednign order of RT, starting with the highest value. Then run recruiting assignements one by one starting with the highest RT value

    -assingment process:
        - teams earn "chances" based on the following criteria:
            - on the player's lean list:
                -1 = 7 chances, 2 = 3 chances, 3 = 1 chance
            - scholarship offer
                - if only one team makes a scholarship offer = 5 chances for that team
                - or is > 1 team makes a scholarship offer = 1 chance for each team making a scholarship offer
            - playing time offer
                - if only one or two teams makes a playing time offer = 7 chances per team
                - if > 2 teams make a playing time offer = 5 chances per team

        - choose the top 4 teams in terms of value
        - if there are ties / more than 4 teams with nonzero value, randomly choose among lower-ranked teams to fill the remaining top-4 slots
        - total value is the total number of chances of chosen team. Example:
            - for player A the following:
                - lean list: 1. Team 1, 2. Team 2, 3. null
                - scholarship offers: 12 (including Teams 1-12)
                - playing time offers: Team 1 and Team 7
                - chances per team:
                    - Team 1: 15
                    - Team 7: 8
                    - Team 2: 4
                    - randomly choose among teams 3-6 & teams 8-12 (Team 9 is chosen): 1
                -total value = 28 (Team 1, 15; Team 7, 8; Team 2, 4, Team 9, 1)
                - value = random.randint(1,28)
                    - Win ranges:
                        - Team 1: 1-15, Team 7: 16 - 23, Team 2: 24-27, Team 9: 28


    - team eligibility for recruits
        - once a team has reached 12 scholarships assigned, they are removed from all remining players for whom they've offered a scholarship
        - once a team has reached a roster of 15 players, they are removed from all remaining players
    - when run recruiting completes:
        - advance franchise week from `35` to `36`
        - persist signed results on the franchise doc in `week_35_recruiting_results`
        - redirect user to `recruiting.html`

- generate walkons
    - after recruiting has run, generate walks for all teams who do not have 15 players on their roster
        - walks do not receive scholarships or pt promises
        - the core 12 attribures (SC through FT) are assigned numbers random.randint(1,22), with a max of 3 attributes > 19
        - height = random.randint(66-72)
        - weight = random.randing(155 - 179)
        - year = freshman
        - archetype = `Walk On`
        - names use the same name generator as recruit generation
        - position ratings are derived from their generated attributes

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


