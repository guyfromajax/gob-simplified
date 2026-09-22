# Stage 1.5 — GREEN. Parity fine. But the box-out doesn't move the box score.

Verdict against the pre-registered rule: GREEN. The two arms' OREB-share deltas differ by
0.455 +/-1.963 (straddles zero) and the arm gap does not widen (-0.062 +/-1.096). Stage 1's
sign disagreement was noise: split into 40-seed blocks it REVERSES direction between b1 and b2,
and excluding one errored game flips the pooled sign. There is no sim-vs-played problem here.

The bigger finding, which the agent reports honestly against its own Stage 1 write-up:
at n=119 the four OREB-share cell means are 29.32 / 29.46 / 29.66 / 29.35 -- a spread of 0.34
with CIs of +/-1.0. THE BOX-OUT CONTEST DOES NOT MOVE OREB SHARE ON EITHER ARM. Stage 1's
pts/team drop (-1.66 to -1.80) and sim fouls drop (-3.50) were also noise: -0.59 / +0.04 and
-0.51 / -0.72 at n=119, all straddling zero.

So: 81 box-outs per game, 5.5 units of mean displacement, loser behind the winner 92% of the
time -- and the rebound split does not move. Open question for Stage 2, hypothesis worth
testing first: GOB_REBOUND_FROM_ARRIVAL caps travel by the post-shot window, so moving a
DESTINATION 5.5 units may move the ARRIVAL point far less, and what is left is swamped by the
composite and the dice.

ALSO FOUND, NOT FIXED: a real latent crash in shared_defense.assign_all_zone_defenders --
ball_handler_id is bound only inside the PG/SG/SF/PF/C loop (line 1312) but read outside it
(1483-84), so an empty zone_boundaries map raises UnboundLocalError. Flag ON re-phased the RNG
into that state on seed 8093; the box-out did not cause it and cannot reach that code. One-line
fix: bind ball_handler_id = None before the loop. Backlog.

Flag still OFF. Not flipped, not re-cut, not merged, nothing retuned, no engine code changed.
