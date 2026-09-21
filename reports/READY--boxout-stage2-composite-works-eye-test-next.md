# Stage 2 — composite works. Per-player effect grew. Compounding risk did NOT materialise.
# Ready for Jamie's eye test.

BOXOUT_SCORE_WEIGHTS in BackEnd/utils/boxout_contest.py, sums to 1.0 -- the one place the
tuning pass edits. Only the score changed; pairing, push-back, two-directional and the d6
are untouched. Flag still defaults "0".

PER-PLAYER EFFECT HELD AND GREW on the primary cell: P(rebound | winner) vs loser is now
16.07% vs 8.10% = 1.98x on sim SD=1, against 1.74x under pure ST. 1.69-1.98x across all four
cells vs 1.58-1.81x before. Per-cell CIs overlap, so the honest claim is "at least as strong,"
not "better."

COMPOUNDING DID NOT HAPPEN. Top-RB-quartile share of rebounds moves -0.19 to +0.56 pp against
CIs of +/-2.0-3.0. Top rebounder's count moves -0.42 to +0.72 and changes sign across cells.
The mechanical reason is sound: the contest is two-directional and near a coin flip, so a good
rebounder is about as often the defensive crasher who wins as the offensive one. RE-CHECK THIS
FIRST if the model ever goes one-directional.

WIN RATE BY GAP BAND: 57.3 / 63.2 / 73.0 / 87.5%. Monotonic in 3 of 4 cells, tops out at
84-88%. The <5 band's apparent jump from 50.2% is a measurement artefact the agent diagnosed
correctly: integer ST scores tied often (61 gap-0 pairs in 508), and gap-0 pairs sat in the
denominator but could never enter the numerator. Floats barely tie (7 in 621), so the artefact
cleared.

CONSEQUENCE WORTH KNOWING: the tie-to-defender rule is now near-dead. It gave the defence a
58.3% floor at equal ST and fired constantly; it now almost never fires. If a defender edge is
wanted later, the tie rule is no longer where to put it.

SEPARATE FINDING, NOT INVESTIGATED: the defensive crasher pool is systematically weaker than
the offensive one -- composite 44.90 vs 46.49, consistent across all four cells. That is why
the defence wins only 48.5% under either score. It is about WHO crashes, not about the contest.

OREB SHARE STILL UNRESOLVED at n=120 paired (sim +0.654 +/-1.367, played -0.978 +/-1.666,
difference +1.631 +/-2.143). Expected: the contest is symmetric, so per-player effects cancel
at team level regardless of the score. One-directional remains the live lever.

GATES GREEN: flag OFF 40/40 all four cells; §8.1 = 0; clairvoyance guard untouched (git diff
empty, 14 passed); 0 errors across 640 games; suite 2850 passed / 0 failed / 0 XPASS. Test
changes are strengthenings, not relaxations -- the old score test used equal attributes and
could not have caught a wrong weight.

NEXT: eye test with GOB_BOXOUT_CONTEST=1 in the local backend env. Flip + double re-baseline
is the separate step after Jamie likes what he sees.
