**Instance Types**
1. Non-Account (NA)
2. General Account (GA)
3. Game Mode Only (GMO)
4. Gameplay (GP)

**Abbreviations & Notes**
-TBD: To Be Developed -- this doesn't exist yet and we'll add in the future
-Gameplay Screen = court.html
-TCC: Tournament Command Center
-FCC: Franchise Command Center

**Top Nav Bar (NA, GA, GMO)**
Notes: Alwasy present with links
Links To:
-Mode Select
-GOB Youtube
-GOB X Page
-User Account Information (TBD)

**Homepage (NA)**
Notes: currently homepage.html
Links To:
-Account Creation
-Account Login
-Mode Select

**Account Creation (NA)**
Notes: General Account Creation Process (TBD)
Links To:
-Mode Select

**Account Login (NA)**
Notes: General Account Login Process (TBD)
Links To:
-Mode Select

**Mode Select (NA, GA)**
Links To:
-Single Game Select (currently index.html)
-Tournament Select
-Franchise Select
-Each Team's General Roster

**Each Team's General Roster Page (NA, GA)**
Notes: 
-Display Players and Attriburtes from Univesal Players Collection
-Each team has their own roster page (8 current total, more in the future as we add more teams)
Links To:
-Mode Select

**Single Game Select (GMO)**
Links To:
-Lineup Select Experience

**Lineup Select Experience (GP)**
Lineup Screen Links To:
-Game Plan
-Box Score
-Gameplay Screen

Game Plan Links To:
-Lineup Screen
-Playbooks Page
-Gameplay Screen

Box Score Links To:
-Lineup Screen

Playbooks Page Links To:
-Game Plan

**Tournament Select (GMO)**
Links To:
-Tournament Command Center

**Franchise Select (GMO)**
Links To:
-Franchise Command Center

**Tournament Command Center (GMO)**
Links To:
-Bracket (tab)
-Roster (tab)
-Team (tab)
-Stats (tab)
-Schedule (tab)
  -links to completed Training Reports
-Game Plan (button)
  -Playbooks (note when the user goes from TCC to Game Plan to Playbooks back to Game Plan, upon return from Playbooks, the Game Plan is wired with Return to Lineup, which causes errors, it shoudl be wired with Back To Locker room taking teh user back to TCC)
  -Back to TCC if visited from TCC
-Playbooks (button)
  -Back to TCC if visited from TCC
  -Back to Game Plan if visited from Game Plan (note, when the user goes from TCC to Game Plan to Playbooks back to Game Plan, the Game Plan is wired to with Back to Lineup instead of Back to Locker Room in this flow, which is causing errors )
-Traning Screen (Run Training button)
  -Note when user runs training, if they select Current Playbook radio button, latest Game Plan and Playbook settings should apply
-Lineup Select Experience (Play Next Game button)
-Coaching Grid (TBD)
-Mode Select Screen (TBD -- to add an "Back To Account" button in upper left corner)

**Franchise Command Center (GMO)**
Links To:
-Stadings (tab)
-Roster (tab)
-Team (tab)
-Stats (tab)
-Schedule (tab)
  -links to completed Training Reports
-Recruits (tab)
-Game Plan (button)
  -Playbooks (note when the user goes from TCC to Game Plan to Playbooks back to Game Plan, upon return from Playbooks, the Game Plan is wired with Return to Lineup, which causes errors, it shoudl be wired with Back To Locker room taking teh user back to TCC)
  -Back to TCC if visited from TCC
-Playbooks (button)
  -Back to TCC if visited from TCC
  -Back to Game Plan if visited from Game Plan (note, when the user goes from TCC to Game Plan to Playbooks back to Game Plan, the Game Plan is wired to with Back to Lineup instead of Back to Locker Room in this flow, which is causing errors )
-Traning Screen (Run Training button)
  -Note when user runs training, if they select Current Playbook radio button, latest Game Plan and Playbook settings should apply
-Lineup Select Experience (Play Next Game button)
-Coaching Grid (TBD)
-Mode Select Screen (TBD -- to add an "Back To Account" button in upper left corner)

**Traning Screen (GMO)**
Links To:
-Team Report Screen (TBD)
-Traning Report Screen

**Traning Report Screen (GMO)**
-Links To:
1. TCC (Tournament Mode)
2. FCC (Franchise Mode)

**Team Report Screen (GMO)** (TBD)
-Traning Screen

**Coaching Grid (GMO)** TBD
Links To:
1. TCC (Tournament Mode)
2. FCC (Franchise Mode)



**Game Plan & Playbooks Persistence**
1. Single Game Mode
-User settings from Lineup Select Experience persist across the entire current game instance -- all Lineup Select Experience and Game Play experience
-User settings per team persist by team across Single Game instances. Example: if user finishes a game as Lancaster, the next time they play as Lancaster, the Game Plan and Playbook settings from the end of the previous Lancaster game will persist. If they play their next game as Morristown, then their previous game plan and playbook settings from their last game as Morristown will persist. If this is their first game as a team, we'll start with default settings (defined below)

2. Tournament and Franchise Modes
-- User settings from accessing Game Plan and Playbook settings from either the Command Center page or Lineup Select Experience will persist across all instances until they're changed. So they will persist into training, lineup select experience, gameplay, and non-gameplay instances. 

**Default Game Plan and Playbooks Settings**
-All Game Plan Settings = 2
-Playbook Settings = First play in each section gets 100%, all other plays get 0%
-Sections are:
1. Motion Offense (first motion play = 100%, others = 0%)
2. Set Play Inside (first play = 100%, second = 0%)
3. Set Play Attack (first play = 100%, second = 0%)
4. Set Play Outside (first play = 100%, second = 0%)
5. Man Defense (first play = 100%, others = 0%) - Note: Currently only "Man" exists, so it gets 100%
6. Zone Defense (first play = 100%, others = 0%)
-Slot Assignments = Empty object {} (user must explicitly assign plays to slots 1-6)
-Motion Dropdowns = Empty object {} (user must explicitly select Inside/Attack/Outside for each motion play)
Playcall Center plays (when user assigns them):
1. 3-2 Motion (Inside)
2. 4-1 Motion (Attack)
3. 5-0 Motion (Outside)
4. Base Post Play
5. Pick & Roll (Lower Wing)
6. Double Screen for SG

**Gameplay Data Persistence**
Gameplay data must persist through the entire game instance in all game modes.
1. Timeout Navigaiton System
-Game Start
-Quarter Breaks
-Timeouts
-Player Foul Out Process
-Transistion to end of game

**Franchise & Tournament Mode Data Persistence**
-Game Plan and Playbooks changes & data to persist across the entire mode instance
-Changes to player attributes, team attributes, playcall attributes, player stats, team stats, and playcall stats to persist across the entire mode instance

