

##Objective##
Deisgn a playbook report page to summarize the user's settings after they save them.

**Layout**
Title: "Playbook Settings" 
Sub-head "Vs {opponent school name}"
*both are centered
*back button in top left takes user back to the page they visited from -- Lineup Screen durig gameplay or FCC when visiting from the FCC

Section 1 (2-column layout)
Offense play presets on left, defense play presets on right (example below)
Offense                         Defense
Base Post Play 20%              Man 50%
Pick & Roll Entry 20%           2-3 Zone 30%
Corner Three 20%                3-2 Zone 10%
...                             ...

Section 2 (2-column layout)
Fast Break play presets on left, Press/Trap presets on right (P/T plays to be added later, put placeholder copy for now)

Section 3 (2-column layout)
Offense playcall center settings on left, defense playcall center settings on right


**UI/UX in FCC**
If the user has not set playbook setting for that week's game, put a glow effect behind teh Playbooks button in the top of the FCC

When user presses Playbooks button in FCC it takes teh user to teh playbook-report page, with teh above layout. Place a button in the top right that reads "Edit Playbooks". When that button is pressed it takes the user to our current playbooks page where they can edit their playbook settings.

**UI/UX in Lineup Screen during gameplay**
Playbooks button takes the suer to the playbooks-report page. Remove the Edit Playbooks button as this will be a read only page during gameplay.