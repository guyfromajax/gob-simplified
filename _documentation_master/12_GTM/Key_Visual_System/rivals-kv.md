# Rivals key visual — LOCKED

**Master:** `master/GOB_KV_rivals_2752x1536.png` (plus a 1376×768 reduction of it).
**Deliverables:** `formats/` (10 social) and `steam/` (8 capsules) — see
`DELIVERY_MANIFEST.md` for where each one is live.
**Build system:** this folder — self-contained, see `README.md`.

Ronnie Rozier #32, Bentley-Truman Sterling Knights, holding a ball at chest, against
Cedric Buckles #43, Lancaster Johnnies. Cold blue left, burnt orange right, near-black
centre channel.

Pipeline: `plate2.py` → `assets.py` → `digits.py` → `marks.py` (`SCALE=2`) → `ball.py` →
`cutouts.py` → `formats.py` → `stage.py` → `steam.py`.

## The method, and the rule that made it work

Two stages, kept strictly separate:

1. **Nano Banana generates bodies** from a plate that fixes who, where and what the light
   is doing. Google AI Studio, Nano Banana 2 Lite, 1K, temp 1.
2. **Everything graphic is composited afterwards.** The model never sees a logo.

That came from round 1, where the model was asked to preserve real jersey art and instead
invented a cat mascot, wiped JOHNNIES to a blank white box, and re-set both numbers in a
generic font. Once the plates went in with **blank jerseys**, every later round was clean.

**Corollary that cost a round:** because every run starts from the plate, no prompt may be
phrased as a correction. A BUILD block reading "his arms are now correct, don't change the
other player's body" described a previous *output*; the model was looking at a plate with
no bodies, read "don't change his body" as "don't build one", and returned the plate plus a
spare basketball. Every prompt describes the finished picture in absolute terms.

## The build ladder, measured

Shoulder width in head widths:

| | r2 | r3 | r4 | r5 |
|---|---|---|---|---|
| Rozier | 2.39 | 2.24 | **2.35** ✓ | held |
| Buckles | 2.26 | **2.48** ✓ | 2.80 | back to ~2.5 ✓ |

- **"Too bulky" and "head too large" are different variables.** Bulk is arm mass and
  definition; head-looks-big is frame width. Round 3 fixed the arms and narrowed the frame
  at once, swapping one complaint for the other.
- **Never tie the two figures to each other.** "Give them the SAME shoulder width" was
  aimed at widening Rozier; the model applied the match in both directions and inflated
  Buckles from 2.48 to 2.80. Describe each man on his own terms with an explicit ceiling
  ("basketball player, NOT a bodybuilder, no veins, no striations").
- Absolute ratio targets did **not** land literally. Descriptive and relational language
  did the work.

## Compositing technique

- **Fabric-keyed marks.** Drawn only where the pixel underneath is jersey, so the ball and
  fingers occlude Rozier's 32 exactly with no hand-cut mask. Blue keys on "not warm";
  orange keys on the green ratio (G/R ≈ 0.45 fabric vs 0.66 skin). Absolute channel
  differences collapse in the jersey's own shadow — they bit chunks out of the digits.
- **Shading is transferred, not invented.** Each pixel's brightness divided by the median
  fabric brightness nearby gives a relative falloff field; multiplying the mark by it
  continues the garment's shadow across the numeral. Split low frequency (shadow) from high
  (cloth grain). An early clamp of (0.80, 1.10) passed no shading through — the decal look.
- **Every white is sampled.** Rozier's shoulder panel 161,161,167; Buckles' outer stripe
  222,204,202 (used at 193,177,175). Paper white reads as pasted on.
- **Numerals** are a heavy grotesque stretched to jersey proportions. No numeral in any of
  the 98 portraits is complete — all cut by the portrait crop — and there is no jersey font
  in the repo. Hand-built varsity polygons were tried first and came out crude.

## The basketball

Real seams came from the game's own `orange_gp_bball.svg`. Two procedural balls failed
first; the second was geometrically defensible (equator plus four meridians, side curves at
r·sin45) and still looked like a globe, because that is not how a basketball is panelled.

Leather is a **bump-mapped relight**, not a texture overlay: a height field of discrete
domes on a jittered lattice, converted to a normal perturbation and lit by the scene key.

- Filtered noise gives soft irregular blobs — reads as felt. Pebble is separate round domes.
- **Do not divide the slope by the foreshortening.** Meaning to compress grain toward the
  silhouette, I divided by `nz`, which amplifies the perturbation up to 8× where the surface
  turns away and threw a band of hard dark speckles down the left edge.
- The dark keyline on the ball's lower edge (inherited from the plate's vector outline) is
  separated from the seams **by width** — the keyline is a few px, seams three times that,
  so a morphological opening keeps seams and drops the rim. An earlier radial pull smeared
  the tangential bottom seam away entirely.

## One master, every size resampled from it

Three separate bugs came from reprocessing at each size independently: a hardcoded `+18px`
numeral offset (2.3% of frame height at 1×, 1.2% at 2×), a jersey mask that shifted when
pixels were resampled, and a keyline detector that under-performed at half resolution. The
2752×1536 master is now the only source; everything else is a resample of it.

## Figure cutouts

`cutouts.py` separates the two men by **difference matte** against a reconstructed clean
plate (the ground is separable, and the master keeps pure background along its top rows and
both side columns — the reconstruction is accurate to 0.7–2.0 levels).

**Colour distance alone eats hair.** Rozier's fade and Buckles' locs are near-black on a
near-black centre; the first matte flat-topped Rozier's hair and punched holes through
Buckles' brow. Hair is dark but not *smooth* — a local standard deviation separates it
where colour cannot, and the metric takes the larger of the two signals.

**Buckles is never matted.** Even with the texture term, his outer locs sit under 12 levels
from the background — below any threshold that does not also key noise — so the matte runs
a straight vertical line down that side and slices them off. It is invisible against the
master's own dark ground and obvious on a brighter one. He is the rear figure in every
layout, so he goes in as a **slab of the master**, re-grounded. Only Rozier is matted.

### Despill: solve, never borrow

This took three attempts and two of them shipped before being caught.

Every edge pixel is a blend of the figure and the ground it was shot against:

    observed = F·α + plate·(1 − α)

The plate is reconstructed, so **F is simply solved for**. Exact, and local: each pixel
recovers its own colour rather than being handed one from somewhere else. Below α 0.12 the
division is unstable, and those pixels take the nearest opaque colour from close by.

The two borrowing versions failed in opposite directions:

- **Nearest opaque pixel → a black rim.** The matte's texture term keys on local standard
  deviation, which peaks *at the silhouette itself*, so a ring about 5px wide of pure
  background was handed α = 1.0 and the alpha test never saw it. Measured: luminance 22
  against an interior of 92. Invisible on the master's dark ground, a black outline the
  moment Rozier sits over Buckles' orange jersey.
- **Pulling from 7px in → a white halo.** Reaching past the contamination landed on
  whatever was brightest nearby, which along Rozier's shoulder is his white jersey trim. It
  painted a halo from below his ear to his elbow, and a second down his other tricep. Jamie
  described both spans exactly, which is what identified the cause.

**Reach too little and you copy the background; reach too far and you copy the wrong
material.** Solving needs no reach at all.

Verified by compositing the rebuilt cutout onto the master's own ground beside the master
itself: identical. The bright line that remains on his arm is the game art's own rim light.

## Delivery

Ten social formats and eight Steam capsules, all resampled or re-staged from the one
master. `DELIVERY_MANIFEST.md` lists every file, its destination and what a change
propagates to. `kv_capsules.md` covers the Steam set in detail — Valve's text rules, why
each layout is what it is, and the three defects caught in review.

Three moves cover 1:1 through 3:1: **crop vertically** above 16:9, **extend the ground by
edge replication** below it, and **re-stage the cutouts** where the players must move
relative to each other. Synthesising a matching ground instead of replicating edges leaves
a visible rectangle — the real background is not perfectly separable and the join has
nowhere to hide. Only extend past an edge that is pure background; the master's bottom is
jersey, so those layouts fill or overflow the frame.

**The YouTube banner is its own problem.** Desktop and mobile share the *same* 423px-tall
band of the 1440 frame — desktop is only wider, not taller. Everything that must be seen
lives in 29% of the height, which forces the figures to about 41% of frame height; a normal
16:9 composition shows heads and nothing else. It is built as ONE slab of the whole master
(both players at their own spacing, no matting, no internal join), scaled so head-top to
ball-bottom is 400px, with the frame filled by replicating the master's own edges and the
figures dissolved to black within ~200px of their base. A gentle dissolve is not enough —
at half strength the repeated jersey rows read as vertical streaks to the bottom of frame.

## Provenance

The visible Gemini corner glyph is inpainted out by diffusion. Google's **invisible SynthID
watermark survives** and will read positive on any detector — consistent with the AI
disclosure already on the Steam page, but worth knowing before anyone is surprised.

## Open

- Commercial-use terms for AI Studio output on the current tier — Jamie to confirm with
  Google, not something to guess at.
