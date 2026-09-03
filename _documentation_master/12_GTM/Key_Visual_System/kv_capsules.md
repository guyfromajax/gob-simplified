Steam capsules, rebuilt in the rivals-KV family

Supersedes the flat-vector capsule set for the eight graphical assets below. The logotype asset (09 library-logo 1280x455 -transparent-.png) is unchanged and does not belong to this rebuild — it is the logotype alone on transparency, by rule.

Built by: BUILD/steam.py in ~/Desktop/GOB_KV_test/. Run python3 steam.py after cutouts.py; it prints a spec check and a per-asset staging check and writes to steam/. Delivered to: ~/Desktop/Steam Assets/KV rebuild/, using Jamie's own numbering so each file sits next to the one it replaces. Live on the store page since 2026-09-02.

Treatment chosen: pure KV. The alternative — the existing box-score numeral grid kept as a ground texture under the figures — was built and compared at full size and at the 616px the store actually renders, and rejected. steam.py still carries grid_layer() and court_layer(), and python3 steam.py --ab rebuilds the comparison, if that call is ever revisited.

What Steam's rules actually constrain

The set splits in two, and the split is what drives every layout.

asset	size	logo	text rule
Header capsule	920×430	yes	game name + official subtitle only
Small capsule	462×174	logo only	same; auto-generates 184×69 and 120×45
Main capsule	1232×706	yes	same
Vertical capsule	748×896	yes	same
Library capsule	600×900	yes	same
Library header	920×430	yes	same
Library hero	3840×1240	no	no text of any kind
Page background	1438×810	no	optional asset; Steam dims it hard

"Game name and official subtitle only" is the rule that gets pages rejected: no callouts, review quotes, laurels, "Coming Soon" or "Early Access" burned into capsule art. Those need an Artwork Override, a separate submission.

Assets can be swapped at any time without re-review. Valve's approval email says so outright: "You are free to continue developing your product and iterating on your product page, which you can also do any time after you release."

Layouts, and why each is what it is

Every capsule uses the launch-trailer thumbnail's staging — lockup left, rivals right. Deliberate: the store page and the YouTube trailer then read as one campaign, and it is a composition already checked for the thing that goes wrong here (Buckles' hair against a frame edge).

The library hero pushes the two apart to open a dark channel through the centre. Steam draws the library logo over the hero at runtime, so the centre has to stay quiet — which is also what the outgoing hero did with its ball and clipboard. The centre 860×380 is the zone Steam never crops; keeping the figures just outside it is intentional, and both still survive a crop far narrower than the client applies. Built at 1×: the figures sit at 80–88% of a 1240px frame, so the master is reduced here, never upscaled.

The portrait capsules are re-staged, not cropped — the master is 1.79:1. Both are sized by one binding constraint: Buckles' numeral, not his head. At the width a 0.83:1 or 0.67:1 frame gives, a Buckles scaled to look right runs his 43 through the right edge, and a "43" sliced to a bare "3" reads as a production mistake in a way a cropped shoulder never does. So both figures come down until the marks are whole, and the space that buys goes to the lockup. The lockup sits at the top, not the bottom: at the bottom it lands on jersey and needs a plate behind it, and a plate is exactly the added furniture the text rule catches.

The small capsule is the lockup alone, centred (revised 2026-09-02). The first version kept Buckles at the right dimmed to 20%, so the frame would not be a bare gradient. Wrong trade, and Jamie called it: at 462px he does not resolve into a person, he resolves into a smudge — and the cost of his being there is that the lockup has to sit at 40% width to make room for him. The one element that must read gets pushed off centre to accommodate an element that does not read at all. Nothing in, everything out.

Logo only, dead centre, at 78% of frame width. Three sizes were compared at 462, 184 and 120 wide: 70% gave away legibility for margin it did not need; 86% brought the shield's points almost to the frame edge, which reads as an error rather than as confidence. The brand is still carried by the ground — the KV's cool and warm fields balanced either side of a dark centre channel, so the frame is symmetrical and the lockup sits in the middle of its own composition. At 120×45 only the wordmark's silhouette survives anyway, which is the whole argument for giving it every pixel it can have.

Two guards that live in the code

Both were written after getting the same thing wrong twice by arithmetic.

mark_clear() reports what fraction of JOHNNIES + 43 survives each staging. It maps the mark rectangle (master px 1853–2254 × 882–1194, keyed off the master) through the slab transform and samples Rozier's actual alpha over it. Estimating the numeral as a share of his figure width is wrong twice over: BUCKLES_FIG spans arm to arm, which is widest exactly at numeral height, and Rozier's bounding box is not his silhouette.
The library hero's no-text rule cannot be checked from pixels — peak luminance is 255 either way, because Rozier's jersey carries a specular that bright. So verify() checks it where it is decidable: the builder's source must not call the lockup or the type setter at all.
The rectangle around Buckles

Jamie caught this on the header, vertical, library capsule and library header: a dark rectangle framing Buckles. Rozier never showed it.

Cause is structural. Buckles can never be matted — his outer locs sit under 12 levels from the background, below any threshold that does not also key noise — so he travels as a rectangular slab of the master. The slab brings the master's own dark ground with it, and feathering only softens the box's edges: its interior stays darker than the capsule's lit field. Feathering harder just gives the rectangle a softer edge. Rozier is matted, which is exactly why he was clean.

The fix is to subtract the ground he came from and add the one he is going to:

out = canvas + (slab − master_plate)

Where the slab is pure background the difference is ~0 and the result is the canvas, so there is no rectangle to see at any feather width. cutouts.clean_plate() supplies the plate; it is cached.

The figure/ground weight must be the matte's coverage mask, not a magnitude threshold. Two weaker signals were tried and each broke something visible:

A low magnitude threshold plus an outward blur handed w ≈ 0.6 to the background between Buckles' wispy locs, so those pixels took most of their colour from the raw slab — master ground and all — leaving a soft dark stain beside his head that lapped over his temple on both portrait capsules. The master has no such stain; the blend manufactured it.
Raising the threshold instead pushed his whole figure onto dest + diff, which tints him by (dest − plate): measured, +20 levels across his face and hair, washing him out against a warm ground.

The coverage mask is safe here in a way that cutting him out with it is not. Inside it, the raw slab keeps his exact master values. Outside it, dest + diff is the correct composite for any partly-covered pixel — for a half-covered hair pixel the difference is α·(hair − plate), so adding it to the destination lays that hair over the new ground exactly. The mask's known failure is his outer locs; there the answer it falls through to is the right one, so the slice costs nothing.

The extension past the slab must decay, not replicate. slab_ext extends to the frame edge by repeating the end row and column, which is right for image content and wrong for a difference layer — the value there is the master's per-row noise, and repeating one column of it across a few hundred pixels turns it into horizontal banding down the hero's dark right side. A first attempt held full strength across the first half of the extension and kept the banding; the ramp now falls to zero within about 1.2% of frame width.

dim fades the figure toward the ground, never the ground itself. Multiplying the whole composite darkened the capsule's own field along with him — which is why Buckles read as "shadowed out" in the page background. That asset now applies none.

The cutout's edge: despill by solving, not borrowing

cutouts.py. Every edge pixel is a blend of the figure and the ground it was shot against:

observed = F·α + plate·(1 − α)

and the plate is known, so F is simply solved for. Exact, and local: each pixel recovers its own colour rather than being handed one from somewhere else. Below α 0.12 the division is unstable and those pixels take the nearest opaque colour from close by.

Two earlier versions borrowed instead, and each failed in the opposite direction:

Pulling from the nearest opaque pixel left a black rim — near the silhouette the nearest opaque pixel is often contaminated too. The matte's texture term keys on local standard deviation, which peaks at the silhouette itself, so a ring about 5px wide of pure background gets handed α = 1.0. Measured, luminance 22 against an interior of 92. Invisible on the master's dark ground; a black rim the moment Rozier sits over Buckles' orange jersey.
Pulling from 7px in reached past the contamination and straight into whatever was brightest nearby. Along Rozier's shoulder that is his white jersey trim, so it painted a white halo from below his ear to his elbow and a second down his other tricep — exactly the two spans Jamie reported.

Borrowing cannot win: reach too little and it copies the background, reach too far and it copies the wrong material. Solving needs no reach at all.

Verified by compositing the rebuilt cutout onto the master's own ground beside the master itself: identical. The bright line remaining on his arm is the game art's own rim light.

Because this changes the cutout, it also changes the three delivery formats that composite it — square_1080x1080, discord_icon_512x512 and both trailer thumbnails. All rebuilt and re-committed. The master is untouched and verified bit-identical.

How to see a seam like this before shipping it

None of these artifacts survives a contrast stretch. Convert to luminance, rescale the 2nd–60th percentile to full range, gamma ~0.45. A flat-field join that is invisible on a dark capsule becomes an obvious box. Run it on any new layout that places the slab.

Open
10 sub-mark 2432x576 -transparent-.png is not a Steam upload slot. Fine as a secondary lockup used inside other artwork; it goes nowhere on its own.
The three icons in the folder (gob_app_icon_184.jpg, gob_shortcut_icon_256/512.png) are client/shortcut icons, not store graphical assets, and are outside this rebuild.
Provenance is unchanged from the KV: the visible Gemini corner glyph is inpainted out, but SynthID's invisible watermark survives and will read positive on any detector. Consistent with the AI disclosure already on the store page.