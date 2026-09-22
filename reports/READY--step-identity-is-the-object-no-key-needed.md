# Step identity: THERE IS NO KEY TO INVENT. The step object is the identity.

THE ANSWER IS THE SIMPLEST ONE. The grid already lives on the step dict (step["_step_state"]["defense"])
and every consumer already reads it OFF THE OBJECT, never by index. So write-once is a one-line
predicate -- does this step already carry a grid? -- with NO KEY SPACE. Nothing can be missing,
nothing can collide, and a mis-keyed freeze (the failure the scope report called worse than the
defect) is not reachable.

THE CAUTION WAS STILL CORRECT. Bare index moves for 5.3-5.6% of surviving steps; timestamp is
duplicated within a skeleton 23-27% of the time. Either as a key would mis-key a real fraction. Every
index move comes from ONE mutation -- a stamp pair that both drops and adds (the
skeleton["steps"] = list(output_steps) rebuild). Append alone never moves an index. So the answer is
not a better key, it is no key.

PROVEN, not asserted: 0 counterfeit objects across 197k steps, 0 grid losses across 13k truncations
and 1,551 index moves, 0 step objects shared between turns, no special-casing applied. Object identity
measured with id() while holding a strong reference to every step for the life of the process, so ids
cannot be recycled -- without that the measurement would be worthless.

BLAST RADIUS, AS A NUMBER: write-once blocks 41% of all stamp writes; 86% of those change the value;
4.2% cross the 11-unit contest radius; and ~18% of REALISED interceptions sit on a step the coverage
pass had already overwritten before the contest read it. Stage 2 must be flag-gated and measured on
outcomes, not just parity. 3x smaller at SD=0 -- measuring it on the empty catalogue would understate
it two- to threefold.

THE REAL FAILURE MODE IS THE OPPOSITE OF WHAT WE FEARED. A consumer reaching a step with no frozen
grid falls back to a SILENT legacy redraw (phase_resolution.py:5543 zone / :5560 man) -- the exact
defect Stage 2 removes, reintroduced invisibly. Rule 26b: it must announce, per occurrence, with a
counter. That counter reading ~0 after Stage 2 IS the stage's acceptance test.

SCOPE IS BIGGER THAN THE SCOPE REPORT SAID: six readers, three writers, four independent producers --
not four consumers. Two newly found and load-bearing: :4924 (shot-contest defender selection, falls
back to its own draw at :4928) and :5030 (the SIM ARM's coord write -- the site that makes "sim and
played read the same draw" true or false). Both must be in Stage 2's scope.

ONE DECISION NEEDED FROM JAMIE: phase_resolution.py:7683 pre-seeds a grid for post-subtle beats from
its OWN independent draw, so 7% of steps already carry a grid the first time the stamp sees them.
Under write-once that pre-seed wins permanently and "single producer" is false on day one. Either
bless :7683 as a legitimate first writer, or delete it and let the stamp own those beats. The agent
deliberately did not decide it.

No behaviour changed. git diff 0 lines at cb9082f73. 160 games, 0 errors, 40/40 fingerprint and draws
in all four cells.
