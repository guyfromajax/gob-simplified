# READY — depth-ordering-fix.md (verified)

Verified 2026-09-25. **Accepted.** Branch `feature/depth-ordering-fix` off develop (8d6d8252d).
Not merged. `USE_DEPTH_ORDERING` still default false. Nothing retuned.

## The bug is genuinely fixed — verified by my own grep, not the report's claim
`installDepthOrdering` is now called from `gameScene.js:2349`, immediately after
`this.playerSprites = loadPhaserPlayers(...)` — scene setup. The old site inside
`playTurnAnimation` (turnAnimation.js:4686) is REMOVED, not supplemented. Confirmed by grepping
every call site: the only non-test callers are the export itself and gameScene.

`tests/e2e/depth-install-site.spec.js` fails if installation moves back into any of nine handler
files, and fails if none lands in scene setup. **It failed on first run** because the agent had
added the scene call but not yet removed the old one — the test catching the exact regression it
was written for.

## The live evidence is real — I staged the frames and looked at them
Real court, Johnnies branding, headshot markers, scoreboard, playcall strip, possession meters.
720x450. `live-evidence.json` carries gameId 6ab65445e3057866ea164a43, LANCASTER vs FOUR_CORNERS,
real player UUIDs, and a merge at **1.41 grid units** — inside the 2.5 pinned band, so a pair the
separation pass will never touch. Categorically different from the previous round's 1229x768
fixture of plain circles on black.

Depths cross-checked against the JSON myself: OFF = all ten at depth 1; tie-break = ten distinct
depths, ball owner at 208; hard promotion = identical to tie-break **except one player**,
`b2487884` (FOUR_CORNERS, y 153.6 — the FURTHEST from camera), lifted 208 -> 655.

## What Jamie found, which the report does not capture
Jamie compared the frames and judged the C/SG overlap WORSE with ordering on. Cross-checking the
depths: that change is present in BOTH modes, so it is the y-sort, not the promotion. The honest
reading is that correct depth ordering made that particular pair less legible — with everything at
depth 1 the draw order was arbitrary, and arbitrary happened to favour that pair. Sorting by
distance is correct; correctness does not guarantee legibility. The report's claim that chips
become "readable" is true for some pairs and false for others, and it does not say so.

Separately the depths confirm hard promotion's worst case: it takes the player furthest from the
camera and draws him in front of all nine nearer players. That is an argument against that mode
independent of taste.

## Genuinely good work in here
- **Ball owner DERIVED, not published** — `BallControllerAdapter.getCurrentOwner(scene)`, the
  field `attachToPlayer` already maintains, so no handler has to cooperate. The brief's preference,
  taken for the stated reason.
- **Two self-caught errors, both documented rather than hidden**: the first derivation read
  `scene.gameState.ballHolder`, measured null through an entire possession; and the first cut
  synthesised a one-entry list so only the ball owner got a depth and the other nine stayed at 1 —
  worse than not ordering at all, caught by a live assertion.
- **The `.replace` blocker is explained and fixed.** Palette resolution was
  `snap ? {...snap.colors} : fallback`, which prefers a truthy snapshot whose `primary_color` is
  null over a roster that has a real one. The null reaches
  `createHeadshotMarkerV2.js:32 → HexStringToColor(null)` and throws out of `GameScene.create`
  BEFORE any marker is built — empty court, no scene hooks. Same pattern in BOTH `bootGame.js` and
  `gameScene.js`, gameScene running second, so fixing only bootGame changed nothing — found by
  measuring after the first fix appeared to do nothing. Committed separately as `c2da44e7d`.
  **This is a real app fragility worth keeping**: one null colour field takes out the whole scene
  with no fallback and no actionable error.

## Honest limitations, volunteered by the agent
- Only `OPENING_TIP` positively identified in the payload capture. The report explicitly REFUSES
  to repeat the previous round's reasoning-based per-handler coverage claim. Correct discipline.
- Not loaded against the Netlify deploy — all local against seeded mongomock.
- Headshot photos are a 1x1 stub (external CDN); geometry, chips, borders and ball are real.
- No mid-tween crossing sequence captured.

## One discrepancy I found
The prose says the captured possession's playcall strip reads "PICK & ROLL (LOWER WING) / ATTACK"
and "5-0 MOTION / OUTSIDE". The committed frames read **"BASE POST PLAY / INSIDE"**. The report is
describing runs other than the ones it links. Minor, but the frames and the narration are not the
same possession.

## Gates — all passed
equiv-v3 240/240 fp AND draws, 480/480 checks, 0 mismatches; seed 8000 played SD=1 = fp
`0c3389cd41d0bbef` / draws `75363`. `git diff --stat` shows **0 BackEnd/ paths** (5 FrontEnd, 1
tests/e2e helper). Flag off = every container at depth 1, asserted live on the real court. Python
3,651 passed / 0 failed. Node 16. Playwright 9. Rule 6e correctly scoped to the equiv-v3 row only.

## Untouched
GOB_COLLISION_*, GOB_SCREEN_*, GOB_COLLISION_TOLERANCE, GOB_STRICT_EXCEPTIONS, SCRA/SCRS,
calculate_screen_score, Stage 3 cold-path defects, the uncached find_one, all posture/tolerance/cap
constants, and `feature/flag-registry`.

## Where this leaves the thread
The engineering is done and correct. The open question is product, not code: the improvement is
marginal on a four-player pile, and by Jamie's own eye at least one pair reads worse. Jamie is now
exploring a different framing — simulating collision and movement AROUND each other during
traversal rather than avoiding overlap at endpoints — which attacks the path between stamped
coordinates, something nothing in this workstream has touched.

## Still open
- PIN_OFFENCE_AT_AUTHORED_LOCATION, unanswered from the tolerance sweep.
- `feature/flag-registry` merge, parked under Operations.
- The palette-null fragility exists on develop too and is only fixed on this branch.
