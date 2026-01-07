A unified system that handles rebound logic for all missed shot instances.

-HCO Shots
-Fast Break Shots
-OREB Putback Shots
-Free Throw Shots

**Note - we need to animate rebounders into position during shot attempt**

**Rebound Resolution Flow (8 Steps)**
1. Calculdate the mised shot bounce spot
    -bounce spot has wider variance on longer shots
        shot: x range 2-6, y range +-6
        medium x range 2-8, y range +- 8
        high x range 2-10, y rane +- 10
2. Filter Eligible players
    -Remove fast break get back players from both teams
3. Discount shooter / putback attempt player
    -Increase their distance score +20% (this makes them 20% less likely to be chosen, lowest distance score from each team is chosen)
4. Find closest player to bounce spot from each team
5. Handle edge cases (no rebounders available, use player who is closest to the bounce spot)
6. Calculate rebound scores for the two closest players -- uses function calculdate_rebound_score()
7. Apply team bias, modifiers, and zone penalty
    -bias = def_mod - off_mod
    -def_prob = min(0.95, max(0.55, 0.75 + bias))  
    -zone penelty, def_weight *= 0.9 (if defense playing zone)
8. Weighted random selection between the two closest players
    -o_score, d_score calculated using calculate_rebound_score()
    **(need to account for distance here)**
    -total_score = d_score + o_score 
    -d_weight = (d_score / total_score)
    -d_weight += (def_prob - 0.5)
    -d_weight = min(0.95, max(0.05, d_weight)) 
    -radom_value = random.random()
    -if random_value < d_weight:
        rebound_team = DEFENSE
        rebounder = d_rebounder
    -else:
        rebound_team = OFFENSE
        rebounder = o_rebounder

