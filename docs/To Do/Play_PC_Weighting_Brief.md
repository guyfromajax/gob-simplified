**Objective**
Assign a value to each position (PG, SG, SF, PF, C) based on the user's Offense Playbook Settings and Offense Playcall Center assignments.

Note that the players themselves will have no impact on these value. These are purely weighted values that show the likelihood a position will take a shot based on the playbook and palycall center settings.

There will be two sets of value, one for Playbook settings and one for Playcall Center settings.

**Value Determination Logic**
Values are calculatec by identifying the acutal shooter in all potential animation skeletons in each play's db entry.

Points Logic
-Target Shooter = 60% 
-take all skeletons other than the success skeletons (because the target shooter is always teh success skeletons shooter and the 60% above accounts for that), count the nmber of times each position is the shooter in the remaining skeletons, and weight accordingly. Then from those weights we distriburte teh remaining 40%.
    -Example: SG is target shooter and Non-success instance shooter count (PG: 1, SG: 3, SF: 0, PF: 5, C: 1)
    PG = 4%, SG = 72% (60% + 12%), SF = 0%, PF = 20%, C = 4%
    -then let's assume that this play has a 20% weighting in the playbooks and is one of 8 offense plays in the Playcall Center. We then weight each position's Playbooks Setting by a value of 20% of the values above, and each position's Playcall Center setting by a value of 12.5% to the values above. and that becomes each psotions value for htat play.
    -we then run this for every play with % > 0 in playbooks and every offense play in the Playcall Center, aggregate the values and we hae a final value for each position in each Value (Playbooks and Playall Center)

-The final output is two items as follow:
Playbooks
PG: 22%, SG: 48%, SF: 4%, PF: 11%, C: 15%
Playcall Center
PG: 20%, SG: 15%, SF: 19%, PF: 18%, C: 28%

Question:
1. Is this clear? Plese ask any quesitons that you need to so we can implment and you don't need to guess or assume
2. How do you suggest we store these values? in the db? locally? do we calculate each tie we visit a page that uses these? (Note we will display these on the set-lineup screen, playbooks tab on FCC, playbooks page, and other areas as need -- which tells me we need to store these somewhere, I think it would not be ideal to run calcualtons on every page load)
3. These need to be dynamic, able to change as the user chagnes playbook and playcall center settings. How do you suggest we accomplish this?
4. They also need to be dynamic as we add more skeletons to playbooks and the percentages for positions relative to teh playbooks changes in the db. How doyou suggest we accomplish this?
