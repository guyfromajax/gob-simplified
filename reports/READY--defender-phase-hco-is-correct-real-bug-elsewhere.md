# Defender phase — your eye was right, but the bug is on the OTHER turn types.

WHAT YOU NAMED (HCO step 1) IS CORRECT BEHAVIOUR. Nearest defender is 14.5 units vs 3.8 once
the possession settles, and 54% of HCO step 1s have nobody within 10. But 99.7% of HCO step 1s
are entry/transition steps and the ball handler is a mean 48.5 units from the rim he is
attacking, 41.4% still on his own half. He is bringing the ball up and the defense is retreating.
That is what transition looks like. H4 supported.

NOT A PHASE LAG ON HCO. Defenders at step N are closest to the ball handler at step N at every
step index, both arms, both footings. The agent caught and corrected its own first-pass error
here (an argmin that said "lagging" where magnitude says "in phase") -- worth trusting the
correction, the magnitude test is the right one.

THE REAL PHASE BUG IS ON NON-HCO TURNS, AND IT IS WORSE BY THE NUMBERS. At step 2 defenders are
14.08 from where the ball handler WAS and 16.89 from where he IS -- a step behind. At step 3 it
inverts to leading (12.32 at N+1 vs 15.97 at N). 59-67% of those steps are beyond 10 units,
against 54% for HCO step 1. Consistent across both arms and both footings. Inbounds, DREB, fast
breaks, trap/press. Jamie's eye probably caught THIS and attributed it to HCO.

SECOND DEFECT: guard_ball is essentially never tagged on HCO -- 100% of step 1s, 96-99.8% of all
HCO steps, including steps where a defender is 3.6 units away. transition_bridge.build_walk_up_step:350
tags all five defenders guard_offball unconditionally; there is no on-ball concept in that builder.
Separately _bh_defender_pos returns None on 55% of calls, all because roles["defender"] is None.

BEFORE BUILDING THE TAG FIX: nobody has checked what the FRONTEND does with guard_ball vs
guard_offball. The agent says so explicitly -- the claim that the missing tag is visible is an
inference from the payload, not an observation of the renderer. If the renderer draws them the
same, the tag fix changes nothing on screen. Check that first, it is minutes.

NO PARITY ISSUE. Both arms match within 1.6% on every row. Consistent with B1-A having put both
arms on the same emitter.

DESIGN QUESTION, NOT A BUG: is zero ball pressure on 54% of transition entries what we want? In
real basketball someone usually picks the ball handler up near half court. Correct is not the
same as desired.

All probes read-only, 40/40 on fingerprint and draws in every cell. No engine code changed, no
flags, nothing retuned, nothing built.
