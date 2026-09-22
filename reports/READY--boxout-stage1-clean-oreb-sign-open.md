# Box-out Stage 1 — clean, flag still OFF, one thing to settle before flipping

Gates all green: flag-off reproduces `equiv_v3_reference_70f7dd021_b1a.json` 40/40 on all four cells,
§8.1 = 0 across 160 games, suite 2841 passed / 0 failed / 0 XPASS both flag states, clairvoyance guard
untouched and proven with a live poison test.

Design behaves as specified: win rate 50 / 62 / 73 / 86% across ST-gap bands, tops out at 86% not 100%,
loser ends up behind the winner 92% of the time. Both constants derived from measured geometry
(radius 8.0 = pooled median pairing distance, which also equals PASS_LANE_DIST; pushback 0.5 = the
fraction whose mean equals the measured gap between a pair's two destinations).

OPEN: at SEED_DEFENSES=1 the OREB share moves in opposite directions on the two arms (sim +0.05,
played -1.80). They agree at =0. Every delta is inside its own CI at n=40. Stage 1.5 is a
higher-n re-measure of that one cell before flipping.

ALSO REPORTED, NOT RETUNED: pts/team down in all four cells (-0.96 to -1.80).
Tuning-pass item for Jamie's single pass at the end.
