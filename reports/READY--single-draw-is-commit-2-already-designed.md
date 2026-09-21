# Single draw: most of it is ALREADY BUILT and pointed the wrong way round.

THE FINDING. StepState already exists, already holds a per-step defender grid, and its own docstring
already says "Option A -- share the emitter's one draw." The flow is just backwards: the EMITTER
produces and the engine consumes, via the _hco_render_animations stash
(skeleton_step_emitter.py:1636 sets it, step_state.py:49 reads and clears it). Reversing that is
"commit 2" from 20d3cd7c5 (6 Sep), whose own message says: "single producer consumed by contest and
render, stash deleted." It never landed. That is the whole job.

WHY THE DEFECT SURVIVED AN EARLIER FIX. The StepState workstream's Stage 2 hit a circular dependency
(contest runs pre-emit and truncates the skeleton the emit draws) and accepted an approximation,
documented as "~2px RNG, immaterial." The measurement says p90 3.0 grid units with a tail to 26 and a
4.8% contest flip. The assumption that made the circularity acceptable was quantitatively false.
phase_resolution.py:7285 carries the same error in one word -- "idempotent" -- for a fresh build with
fresh draws that differs 38% of the time.

TWO OF THE THREE SEAMS DISSOLVE. Seam C (render 7-9 units off) is NOT a stage -- most of its distance
is the moment, which is correct, and its draw component disappears when the emitter renders the frozen
grid. Seam B's posture fix becomes throwaway, because Stage 2 deletes the line it edits.

THE DESIGN RULE: append-only freeze, not compute-once. The skeleton grows and shrinks during
resolution (walk-time contest truncates, freelance beats append, shot-clock recalibration expands),
which is why the stamp runs 1-5 times. A step's grid is drawn the first time that step exists and is
never redrawn; later stamps fill only gaps. All four consumers already ask per-step questions, so no
new concept and no new store is needed -- step["_step_state"]["defense"] already exists.

THE ZONE COLLAPSE IS A REAL SEPARATE BUG. attack_drive_clearance.py:1002-1007 uses _zpos as a dict key
but never passes it into get_defender_coords, so every unmatched zone defender is placed with
identical arguments. 51.9% of zone drives put all five defenders on one coordinate; 0.0% of man
drives. It was fine as a proximity COUNT and became a bug when the same dict was read as a POSITION by
the drive contest. Passing posture does not fix it.

THE PERF FINDING IS THE SHARPEST 6e EXAMPLE YET. Defender placement is 20.1% of sim wall at SD=1
(production footing) and 2.0% at SD=0 -- same call count, ten times the cost, because zone placement
is the expensive path. Any perf work measured at SD=0 would have concluded placement was free.
Stage 3 (delete the redundant builds) is estimated at ~5.4% of sim wall, i.e. it plausibly gives back
most of B1-A's ~7%.

TIMING RECOMMENDATION. Stage 1 (pass posture, one argument, one flag, one re-cut) is doable before
1 Nov but is throwaway if Stage 2 lands -- so do it ONLY as timing insurance. Stage 2 should not be
rushed: its one hard property is step identity across truncation and expansion, and a mis-keyed freeze
is confidently wrong where today's redraw is merely noisy. Design the step-identity key first and
verify it with a probe before any behaviour changes.

Design only. git diff 0 lines at 0cd9c4c4f. Probes read-only, 40/40 both cells (and 8/8 for the
profiler), 0 errors across 96 games. Nothing built, nothing retuned.
