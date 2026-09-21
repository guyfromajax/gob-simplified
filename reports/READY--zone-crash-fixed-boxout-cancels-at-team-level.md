# Zone crash fixed (0 in normal play). Arrival-cap hypothesis WRONG. Box-out works per-player,
# cancels at team level.

TASK A. Zero occurrences across 160 reference games, flag OFF. Not a bug we ship. But a near-miss:
both component conditions fire constantly (loop skips the binding 17,195 times, post-loop read runs
34,146 times) and simply never coincided. Fix is right and better than the None bind the brief
proposed -- the agent showed the value is loop-invariant and hoisted the real scan above the loop,
so it returns the value the code always intended instead of a silently-missing guard credit.
Two premises in the brief were wrong and the agent corrected both: the trigger is NOT an empty
zone_boundaries (a synthetic empty-map test passes on pre-fix code) but the loop's SECOND continue,
the overlap-assignment skip, plus the ball handler being outside every defender's zone.
Proof: flag OFF 40/40 fingerprint AND draws all four cells; seed 8093 now completes both arms
(438 / 371 turns, was dying at 19); regression test raises on pre-fix, 7 passed on post-fix, plus
an AST structural guard; suite 2848 passed, 0 failed, 0 XPASS. Commit c79316c82, not merged.

TASK B. The travel-cap hypothesis is dead. Crashers essentially always arrive -- median travel
fraction 1.0, 85-90% reach the destination exactly -- and the attenuation ratio is 0.97, not 0.2.
The push-back survives into the arrival point intact.

THE FEATURE WORKS PER-PLAYER. Among paired players, P(gets the rebound) is 15.57% for box-out
winners vs 8.97% for losers on the sim arm (+6.60pp +/-1.59), 15.12% vs 9.36% played
(+5.76pp +/-1.60). Winning a box-out makes you ~1.7x more likely to get that board. Both arms agree.

WHY IT VANISHES AT TEAM LEVEL: the contest is symmetric. The defender wins only 47.3%, so 52.7% of
the time the DEFENDER is the one pushed back. Two opposing flows of near-equal size, each moving a
player from ~15.6% to ~9.0%, and they net out. That is exactly the zero Stage 1.5 measured.

OPEN DESIGN CALL FOR JAMIE, nothing built: make the contest one-directional (only the defender ever
boxes out; the offensive crasher is never displaced) and the offsetting flow disappears. Same draw
count, but different players displaced, so results move and the reference needs a re-cut -- and OREB
share drops materially. That is a balance decision, and Jamie tunes balance once at the end.
