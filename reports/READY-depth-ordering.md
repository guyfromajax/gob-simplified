# READY — depth-ordering.md (verified, with one material correction to the coverage table)

Verified 2026-09-24. **Accepted with a caveat.** Nothing merged. `USE_DEPTH_ORDERING` default FALSE.

## Gates — passed
- Flag OFF: all ten containers at depth 1, measured via `window.__GOB_DEPTH_REPORT()` and captured
  in gate-flag-off.json, not asserted. Ball above every player.
- `git diff --stat`: ZERO `BackEnd/` paths. 5 FrontEnd files modified, 4 new FrontEnd files.
- equiv-v3 (cheap insurance, since no backend file changed): 240/240 fp AND draws, 480/480 checks,
  0 mismatches. Seed 8000 played SD=1 = fp `0c3389cd41d0bbef`, draws `75363` ✓
- python 3,662 passed / 0 failed; node --test 16/0; playwright 4/0.
- Suite count moved 3,651 -> 3,662 and the agent explained it unprompted: 11 previously-skipped
  tests now execute because node_modules was installed to capture frames. Environment, not code.
  No test changed pass/fail status. Accepted.
- Rule 6e correctly scoped to the equiv-v3 row only. No other number here is a sim number.

## Verified independently (not taken from the report)
- Depth formula from merge-depths.json: `100 + (50 - gridY)*10 + 3 if offence + owner bias`,
  canvas height 768. Arithmetic re-derived on o_C (pixelY 276.48 -> gridY 32.0 -> 283) and
  o_PF (259.584 -> 33.1 -> 272).
- ORIENTATION CORRECT. `gridToPixels` gives pixelY = ((50 - y)/50)*height, so lower grid y sits
  lower on screen, nearer the viewer, and takes the higher depth. Confirmed on three pairs.
- Band arithmetic: max unpromoted = 100 + 500 + 3 + 5 = 608 = `DEPTH_BAND_MAX`. Promoted band
  650–675. 608 < 650 < 675 < 1000 (`BALL_DEPTH`). The inequalities hold.
- The harness loads the REAL `createPhaserPlayer`, which with `USE_HEADSHOT_MARKER=true` and
  `USE_MARKER_V2_FEATURES=true` routes to `createHeadshotMarkerV2`. The marker under test is the
  live one, mask included.
- I looked at the three frames myself. flag-off: insertion-order stacking. tie-break: the
  o_C/o_PF and o_SG/d_SG pairs flip to nearest-wins. hard-promotion: the ball owner comes forward
  with his strip fully legible and the ball on him.

## THE CAVEAT — the coverage table is overstated, and it splits in two
The table marks all nine paths "covered per-frame" on the grounds that
`scene.events.on("update")` is a universal funnel. The funnel claim is true. The coverage claim
is not uniformly true, because `installDepthOrdering` is called from exactly ONE app site —
`turnAnimation.js:4686` — and `scene.__depthContext` is written at ONE site, the very next line.
Grepped directly; there are no other callers in FrontEnd/.

That splits the feature:
- **Y-SORTING IS GENUINELY UNIVERSAL once installed.** The tick reads each container's live
  pixel y every frame and inverts it through the court mapping, so it needs no context and is
  correct during any system's tweens, including mid-tween crossings.
- **THE ROLE TERMS ARE NOT.** `DEPTH_OFFENCE_BIAS` and, critically, the hard-promotion of the
  ball owner are computed from `scene.__depthContext`, which only `turnAnimation.js` refreshes.
  During a sequence driven by PassAnimationSystem, ShotAnimationSystem, ReboundAnimationSystem,
  FreeThrowAnimationSystem, HCOAnimationSystem or AnimationEngine, that context holds whatever
  turnAnimation last wrote — stale `animations` and `stepIndex` — so sub-mode (ii) can promote
  the WRONG player during exactly the sequences where knowing who has the ball matters most.
- **Installation is also conditional**: if a scene's first animated sequence is not driven by
  turnAnimation.js, the hook is never installed and nothing is ordered until one is.

This does not invalidate the work — the mechanism is sound and the y-sort carries most of the
legibility benefit. It means the coverage table should read "y-sort: all paths; role terms:
turnAnimation-driven turns only", and closing it means refreshing `__depthContext` from each
system (or deriving the owner inside the tick from the scene's own ball state).

## Corrections to what I told Jamie earlier — I was wrong three times
1. I said tie-break mode "does not fix the complaint" and blamed my own `DEPTH_BALL_OWNER_BIAS`
   of 5 for being too small. WRONG. In that fixture pair the defender (grid y 44.8) genuinely is
   nearer the viewer than the ball handler (46.0), so keeping him in front is correct depth, not
   a failure. The report calls it the control case and it is right. The bias being smaller than
   `DEPTH_PER_GRID_Y` is deliberate — it stops a tie-break reordering players a full grid unit
   apart — not an error.
2. I said the mask check and the ball-visibility check had no independent evidence because the
   PNGs are byte-identical across filenames. WRONG on the substance. The harness deliberately
   places the ball on the FURTHEST player (o_PG, grid y 46, the lowest depth at 148 in tie-break),
   so the "ball visible above a low-depth carrier" condition IS exercised in those very frames.
   The duplicate files are one frame that legitimately demonstrates several things at once.
3. I said the fixture was "plain circle markers, not the live headshot path, so there is no mask."
   WRONG. It is the real v2 marker with the fallback texture; the mask is present.

The duplicate-filename observation itself stands and is worth tightening — eight names for three
images invites exactly the misreading I made — but it was a naming problem, not an evidence gap.

## Recorded as a separate finding (blocks the eye test tooling, not this change)
`/api/init-game` resolves the away team by its real NAME (`Four Corners`) while `/roster/` only
answers to the hyphenated slug (`Four-Corners`) and 500s on a space; passing `home_id`/`away_id`
does not help because init-game derives the key from the name, failing with
`documents must have only string keys, key was None`. Bridging the spellings then hit
`TypeError: Cannot read properties of null (reading 'replace')`. The agent stopped rather than
patch around it — correct call. This is why no frame comes from a live game, and it will block
any future live-game capture until fixed.

## Self-reported defect, caught and fixed by the agent
Hard promotion was first an additive `+1000`, putting the ball owner at 1508 — above `BALL_DEPTH`,
so the carrier occluded the ball he was holding. Replaced with the bounded 650–675 band and
pinned by a unit test asserting both inequalities. Exactly the class of bug the brief's ball-depth
section was aimed at; found without being told.

## Untouched, as briefed
GOB_COLLISION_*, GOB_SCREEN_*, SCRA/SCRS, calculate_screen_score, Stage 3 cold-path defects, the
uncached find_one, and all posture / tolerance / cap constants. Nothing merged, nothing retuned,
no value recommended.

## Open for Jamie
- Sub-mode (i) tie-break vs (ii) hard promotion — his pick, in the single tuning pass.
- Eye test via the live override: `window.__GOB_DEPTH_ORDERING = true`,
  `window.__GOB_DEPTH_MODE = "hard_promotion" | "tie_break"`, no rebuild needed.
- `PIN_OFFENCE_AT_AUTHORED_LOCATION` still unanswered from the tolerance sweep.
