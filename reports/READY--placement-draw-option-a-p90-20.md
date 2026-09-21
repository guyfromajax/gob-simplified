# Placement draw divergence: OPTION A. p90 20.0 against a 2.0 line. Not close.

VERDICT against the pre-registered rule: one authoritative draw. p90 per-defender spread is 20.0 in
all four cells -- ten times the 2.0 threshold Jamie set.

IT SURVIVES EVERY STRICTER CUT. Drop RENDER (it is the end-of-turn moment, so some distance is legit
movement): p90 still 17-18. The tightest control available -- two STAMP builds, same step, same
skeleton, offense in the IDENTICAL grid position, so every difference is the redraw and nothing
else: p90 3.00 (SD=1) / 2.00 (SD=0). At or above the line even there.

SECTION 5 DOES NOT OVERTURN IT -- IT CONFIRMS IT. The shot contest has a hard threshold
(CONTEST_EUCLIDEAN_RADIUS = 11). SHOT vs STAMP -- the most conservative pair, no moment confound,
mean separation barely one unit -- disagrees about whether a defender contests 4.8% of the time.
10-23% once the drive reconstruction is involved, ~31% vs RENDER. Not cosmetic.

THE ONE TO READ: seed 8000 turn 145, SF. STAMP build 1 puts him at (24,14), 11.70 from the shot --
NO CONTEST. STAMP build 2, same consumer, same turn, same code, puts him at (17,16), 9.49 -- CONTEST.
Whether he contests depends on which of two calls to the same function you read.

MY HYPOTHESIS WAS WRONG AGAIN. The no-posture drive reconstruction is NOT the whole story. Posture-
fired turns are only marginally worse (mean 2.76 vs 2.25). The cause is four consumers running
separate computations. The posture term itself is large (3.25 units mean), and its jitter is tiny
(sag spans 0.27-0.33) -- so it is not jitter, it is different computations.

THE MATRIX HAS A SHAPE, which matters for scoping:
  SHOT vs STAMP     p50 0.00   -- nearly the same answer; damage is a redraw tail
  DRIVE vs either   p50 2-4    -- systematically off; no posture passed
  RENDER vs all     p50 7-9    -- different draw AND different moment

THE REPO ALREADY KNEW. animator.py:1265-1268 docstring: the "ONE identical computation" claim is
"aspirational ... both draw from sim_rng. That is what commit 2 fixes." Commit 2 never landed.

No parity finding: arms are identical up to first divergence (p50 turn 12), different games after.
The 33.5 post-divergence delta is meaningless and should not be quoted.

The agent could not find the kickoff doc -- it lives in the claude.ai Project, not the repo. My
brief pointed at a path that does not exist on disk. It worked from the brief's restatement.

Read-only, 40/40 fingerprint and draws in all four cells, 0 errors, git diff 0 lines. Refactor NOT
designed or scoped, per the brief.
