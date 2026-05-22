choose_rebounder vs determine_rebounder
choose_rebounder(lineup, bounce_spot, exclude, penalize) — the per-team primitive.

Input: ONE lineup (a single team's 5 players).
Output: the player from that lineup closest to the bounce spot (Euclidean distance, with optional 20% distance penalty for excluded/penalized players).
Pure geography. No weighted scoring, no off-vs-def comparison.
determine_rebounder(game, bounce_spot, exclude, penalize, max_x_delta_from_bounce) — the whole-game wrapper.

It does three things in sequence:

Optionally pre-filters each lineup by max_x_delta_from_bounce (used for FT and OREB cases).
Calls choose_rebounder twice — once for the offensive lineup, once for the defensive lineup. Gets one closest-player per team.
Runs the weighted off-vs-def selection between those two candidates: a probabilistic decision based on each candidate's rebound score (player attributes), team rebound modifiers, zone-defense penalty, etc. Returns the actual rebounder + their team + the stat (DREB / OREB).
The key distinction:

choose_rebounder answers "who's closest in this one lineup."
determine_rebounder answers "who actually rebounds, considering both teams and the weighted attributes."

Why the existing HCO/HCT/FCP/FB paths inline the logic instead of calling determine_rebounder:

They each apply their own custom prefilter (e.g., HCO uses offense_rebounders/defense_rebounders to exclude get-back/release; FB uses the x ≥ 50 frontcourt filter). Once filtered, they call choose_rebounder per team and run their own copy of the weighted selection inline.

determine_rebounder only supports the max_x_delta_from_bounce filter — not the custom prefilters HCO and FB need. So those paths bypass the wrapper.

Functionally identical when the parameters line up. A cleanup could consolidate everything onto determine_rebounder by extending it to support the custom prefilters, but today the two paths exist in parallel.

In the user's grid: "rebounder selection: choose_rebounder" for HCO/HCT/FCP/FB means the inline pattern (call choose_rebounder × 2 + weighted selection). "rebounder selection: determine_rebounder" for FT/OREB means the wrapper is called directly. The end result is the same closest-to-bounce + weighted selection across both teams.