
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
    - `Z = 20 - currently assigned recruiting points`
    - `Points Remaining` updates in real time as the user edits point inputs, including unsaved edits
  - top grid columns:
    - `Priority`, `Name`, `Home Region`, `Archetype`, `HT`, `WT`, `POS`, `RT`, `Current Lean`, `Points`, `Playing Time`, `Adjust`, `Remove`
  - top grid preloads from saved `recruiting_orders_week_35`
  - if that field is empty, auto-fill with all recruits who currently have the user team in any lean slot, sorted RT descending
  - point inputs default to `0`
  - revisits preload saved point values
  - teams have a 20-point total budget in week `35`
  - point inputs only accept integers and block keystrokes that would push the board above 20 total points
  - checkboxes default empty on preload and on fresh add
  - `Playing Time` can be checked independently; scholarship is dormant and always saved as `false`
  - drag/drop uses insert-and-push behavior
  - row click and `+` both add/remove recruits
  - top grid is capped at 20 rows
  - trying to add a 21st recruit is blocked with a modal

- save behavior
  - saves the user board to `FTD.recruiting_orders_week_35`
  - on the user's first save only, generate CPU week-35 boards for any CPU team whose `recruiting_orders_week_35` is still empty
  - backend rejects boards whose assigned recruiting points exceed 20 total
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
            - choose one random player from the <= 24 group and assign him 1 point
            - choose one random player from the >= 25 list and assign him random amount of 1-3 points
            - if one of those groups has no qualifying player on the board, skip that step
            - assign all remaining points to players on the lean list. if only one player is on the lean list, he gets all of the points. If 2-3 players are on the lean list, give the highest RT 80% of remaining points and distrubute the remaining evenly. Otherewise assign 60% of teh points to oen of the 3 highest RT players on the lean list and distribure the rest evenly among the players on the lean list. If there are not enough points to give every player at least one, distribute points to random players on the lean list until you run out of points and the remaining players will receive 0.
            - if there are no lean-list players on the board, fallback to the top 5 RT in-region players on the board and split the remaining points evenly among them
        - out-of-region players who are on that CPU team's lean list can receive points assignments

-run recruiting assignments

    -sort all recruits in descednign order of RT, starting with the highest value. Then run recruiting assignements one by one starting with the highest RT value

    -assingment process:
        - teams allocate points to each recruit based on the following criteria:
            - on the player's lean list receive multipliers:
                -1 = 5x, 2 = 3x, 3 = 2x 
            - playing time offer
                - if only one or two teams makes a playing time offer = 7 points per team
                - if > 2 teams make a playing time offer = 4 points per team
            - teams receive one point for having the player on their Top Grid list
            - teams receive points for the number of points they assign in their recruiting orders
            - subtotal = top-grid point + assigned recruiting points + playing-time points
            - the lean-list multiplier applies to that subtotal
            - teams not on the player's lean list use a 1x multiplier

        - choose the top 4 teams in terms of points value
        - if there are ties / more than 4 teams with nonzero value, randomly choose among lower-ranked teams to fill the remaining top-4 slots
        - total value is the total number of points of chosen teams. Example:
            - for player A the following:
                - lean list: 1. Team 1, 2. Team 2, 3. null
                - playing time offers: Team 1 and Team 7
                - points per team:
                    - Team 1 (assigned 10 of their points in recruiting orders): 18 points x 5 multiplier = 90
                    - Team 7 (assigned 2 of their points in recruiting orders): 10 points x 1 = 10
                    - Team 2 (assigned 5 of their points in recruiting orders): 6 points x 3 multiplier = 18
                    - Team 9 (assigned 5 of their points in recruiting orders): 6 points x 1 = 6
                    - total points = 124
                - value = random.randint(1,124)
                    - Win ranges:
                        - Team 1: 1-90, Team 7: 91-100, Team 2: 101-118, Team 9: 119-124


    - team eligibility for recruits
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
