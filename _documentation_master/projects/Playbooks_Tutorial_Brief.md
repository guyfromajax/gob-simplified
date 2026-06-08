

**Playbooks Viewing & Access**
- Command Center: current playbook settings (read only)
- Playbooks Page (accessed via Edit Playbook button in FCC)
    - Edit playbooks
- Lineup Screen, during live gameplay (read only)

**Reading The Play Capsule**
- Top Left: Play Name
    - Focuse in parentheses for Motion Plays
    - Target Shooter in parentheses for Set Plays
- Top Right: % usage currently set
- Bottom Left: Team's Command score
- Bottom Right: Top Scorer (for the current season)

**Editing Playbooks Settings (playbooks.html page)**
- Usage Percentages
    - Offense %'s set according to Play Type
        - Motion
        - Set Plays
    - Defense %'s set according to Play Type
        - Man Defense
        - Zone Defense
    - Fast Breaks %'s set holistically
    - All must equal 100%
    - These percentages are the presets the sim uses to call plays for each turn during live or simmed gameplay
- Playcall Center Behavior
    - Offense and Defense can each have 8 plays added to the Playcall Center
    - These are the plays that the user can call in real-time to override usage percentage presets
    - Offense playcall overrides are for one turn only
    - Defense playcall overrides persist until the user changes it or they enter a timeout/quarter break/player foul out scenario
    - Press/Trap, Tempo, and Aggression overrides also persist until the user changes them or enters a timeout/quarter break/player foul out scenario
- Setting Playcall Center Plays
    - In the playbooks.html page, the user clicks the button in the plays row in the containers on the left of the page to add it to the playcall center.
    - Current Playcall Center settings are displayed on the right of the page
    - The user can drag and drop plays on the right to adjust the order that they appear in the Playcall Center during live gameplay
    - Note a play can have 0% usage set for presets and still be added to the Playcall Center
-Expected Shot Distribution
    - When the user saves their playbooks settings, they will see the expected shot districtuion by position for their usage preset and their playcall center plays
    - These will also be displayed on the Command Center Playbooks tab and on the Lineup Screen during live gameplay.

**Plays' Command Scores**
- Represents the team's command level of each play.
- Scale: 0-100
    - 100+ has benefits, but at diminishing returns
- Changes
    - Command increases as the team practices it during Training
    - Command decreases the more the play is called during live gameplay (this is meant to simulate the fact that they are putting the play on tape more often for opponents to scout)
- Teams with better command of plays will execute those plays more effectively during gameplay
