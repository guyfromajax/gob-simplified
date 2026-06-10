

**Starting Player Collection Counts**
- Senior: 576
- Junior: 418
- Sophomore: 285
- Freshman: 257

**User Franchise Season 1 - Walk Ons**
- When a user starts a new season, when they land on the FCC for the first time, we generate 3 walk ons for all 128 teams, including the user's team.
- During Training Camp, all teams need to reduce the roster to 12
- The three players who do not make the active roster will be palced on the training squad (instead of being cut -- and this applies to all future seasons, players are no longer cut. They are now placed on a training squad)
- User will now be required to assing three players to the training squad in season 1 of franchise, just liek the subsequent seasons.
- Change the language in the modal, action buttons, and other UI/UX from "You need to cut three players" to "You need to assign three palyers to the training squad. Note these players will be ineligible to play this season, but they will be available to you for traning camp next season."

- Note, when the user returns from their week 1 training (traning camp) in season 1, they should still be presented with the Team Attrkbutes Tutorial modal first upon landing on FCC. Once they either complet that tutorial or press "I'll Do This Later", then they should be presented with the Assing Players to TS modal.


**Post Training Camp Training Squad -- All Seasons**
- Players will be ineligible to play
- They will be displayed at the bottom of the team Roster tab in the FCC and at the bottom of each team's team roster page with teh header "Training Squad" and their attributes dispalyed. Note because these players are not active, they will not have season stats.

**In-Season Progression & Reporting**
- During weeks 1-26 evolve each PS player's attributes as follows:
    - CH > 79: + random.rantint(-1,4)
    - elif CH > 59: + random.rantint(-1,3)
    - elif CH > 39: + random.rantint(-2,3)
    - elif CH > 19: + random.rantint(-2,2)
    - else: + random.randint(-3,2)
**Note this applies to user and all computer teams

- After games complete in weeks 6, 11, 16, 21, and 26, publish a report  showing each PS player's cumulate gain to each attribute relative to the last report and current attribute values.
    - link this report in the Inbox of the FCC with the copy "Week #{week number} Practice Squad Development report {link}"
**Note report is only generated for the user team

**Cuts**
- In week 35, when the user presses the "Run Recruiting" action button in the FCC, present them with a modal that reads "Would you like to cut any players ahead of recuiting. Note any players cut will be lost forever, but you will open additinal slots for recruiting".
- Buttons "Cut Players / "No Cuts"
- If the user presses No Cuts, take them to the recruiting page
- If the user presses Cut Players, take them to our existing Cut Players page. Whichever players the user cuts, delete their FPD and remove them from all data linked to the team.
- Run the cut process for computer team as well, logic based on player RT
    - RT < 10: 100% chance cut
    - RT < 15: 50% chance cut
    - RT < 20: 25% chance cut