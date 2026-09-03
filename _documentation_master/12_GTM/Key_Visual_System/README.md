# GOB Rivals KV — build system

Everything needed to rebuild or extend the Geeked-Out Basketball rivals key visual, its
ten social formats and its eight Steam store capsules. Self-contained: no path outside
this folder, no network, no generator.

**This folder is the canonical copy.** `~/Desktop/GOB_KV_test/` on Jamie's Mac is a
working scratch directory and may be ahead or behind. If the two disagree, this wins —
and whatever is on the Desktop should be copied here and committed.

**Verified 2026-09-03:** a clean directory containing only the 20 tracked input files
below reproduces every one of the 18 deliverables **bit-identically** (max difference 0
levels), including `master/GOB_KV_rivals_2752x1536.png`.

---

## Rebuild everything

```bash
pip install -r requirements.txt

python3 assets.py                                     # wordmark + basketball
python3 plate2.py                                     # C3 plate (only to re-generate)
SCALE=2 python3 marks.py                              # jersey marks onto the generation
SRC=final/KV_marks_v3_blueline_2x.png python3 ball.py # leather on the basketball
cp final/KV_marks_v3_blueline_2x_ball.png master/GOB_KV_rivals_2752x1536.png
python3 cutouts.py                                    # figure mattes
python3 formats.py                                    # crops and resamples   -> formats/
python3 stage.py                                      # re-staged layouts     -> formats/
python3 steam.py                                      # Steam capsules        -> steam/
```

Three ordering constraints, each of which produces silently wrong output if broken:

- **`stage.py` after `formats.py`** — it overwrites the square, the Discord icon and the
  banner with re-staged versions, and adds the trailer thumbnail.
- **`steam.py` after `cutouts.py`** — it imports `clean_plate` and `matte` from it, and
  needs `cutouts/rozier.png` on disk.
- **`marks.py` before `ball.py`** — `ball.py` reads the marks output named in `SRC`.

`python3 steam.py --ab` rebuilds the main-capsule A/B comparison (pure KV against the
box-score grid treatment) instead of the delivery set. Kept because the question comes up.

---

## What is where

**Inputs — tracked, and the pipeline cannot run without them.**

| path | what |
|---|---|
| `source/nb_round5_generation.png` | **the raw Nano Banana output. Irreplaceable — everything derives from it.** A re-run is a different roll on the faces and bodies. |
| `source/C3_plate.png` | the plate that produced it, if it ever needs regenerating |
| `source/rozier_portrait_trimmed.png`, `..._buckles_...` | the two in-game portraits the plate was built from |
| `source/lancaster_team_banner.jpg` | the JOHNNIES wordmark is keyed off this |
| `source/orange_gp_bball.svg` | the game's own basketball (correct seams). Also at `FrontEnd/static/images/buttons/` |
| `source/BebasNeuePro-Bold.otf` | brand type. Also at `FrontEnd/static/fonts/` |
| `assets/gob_logo.png` | the GEEKED-OUT lockup. **An input, not generated** — no script produces it |
| `master/` | the locked KV, 2752×1536 and a 1376×768 reduction |

**Generated — safe to delete, rebuilt by the commands above.**

`assets/basketball.png`, `assets/johnnies_wordmark.png`, `assets/num_32.png`,
`assets/num_43.png`, `cutouts/`, `final/`, `plates/`, `formats/` (10 files),
`steam/` (8 files).

`master/` sits in the middle: it is generated, but it is tracked anyway because it is the
single source every delivery format resamples from, and because a rebuild depends on a
`source/` file that cannot be replaced.

---

## The rules that will bite you

Each of these was learned by getting it wrong.

**One master, everything resampled from it.** Never reprocess at another size. Three
separate bugs came from doing that: a hardcoded `+18px` numeral offset that meant
something different at each scale, a jersey mask that shifted when pixels were resampled,
and a keyline detector that under-performed at half resolution. Every dimension in every
script is a fraction of the frame for this reason.

**Never matte Buckles.** His outer locs sit less than 12 levels from the background —
below any threshold that does not also key noise. The difference matte runs a straight
vertical line down that side and slices them off, and it is invisible until he is
composited onto a brighter ground. He goes in as a **slab of the master**, re-grounded
(see `slab_ext` in `steam.py`). Only Rozier is matted.

**Despill by solving, never by borrowing.** Every edge pixel is `F·α + plate·(1−α)`, and
the plate is known, so `F` is solved for directly. Two borrowing versions each failed in
opposite directions: pulling from the nearest opaque pixel left a black rim; pulling from
7px in reached past the contamination into Rozier's white jersey trim and painted a white
halo down his arm. Reach too little and you copy the background, too far and you copy the
wrong material.

**Never send anything back to a generator.** The marks, the leather and the layouts are
all composited. That is what makes the KV stable — the faces and bodies are untouched by
construction. A mark that lands wrong is two numbers, not a new roll of the dice.

**If you do re-generate:** every prompt must describe the finished picture in absolute
terms. Never phrase one as a correction — the model sees the plate, not the last output.
A BUILD block saying "his arms are now correct" once made it return the plate plus a
spare basketball.

**Check flat-field joins with a contrast stretch.** Convert to luminance, rescale the
2nd–60th percentile to full range, gamma ~0.45. A slab edge or a banded extension that is
invisible on a dark capsule becomes an obvious box. Run it on any new layout that places
the slab — two shipped defects were found this way and one was found by Jamie first.

---

## Making common changes

**Move or resize a jersey mark** — `marks.py`, the `place_masked` calls at the bottom. All
positions are fractions of width/height. Re-run marks → ball → copy to master → cutouts →
formats → stage → steam.

**Change a numeral** — `digits.py` renders them; `marks.py` sets colour and size. Whites
are sampled from the garment, not chosen: Rozier's shoulder panel is 161,161,167, Buckles'
outer stripe 222,204,202 (used at 193,177,175). Paper white reads as pasted on.

**Add a social format** — `formats.py` for anything that is a crop or resample of the
master; `stage.py` if the players must move relative to each other. Three moves cover 1:1
through 3:1: crop vertically above 16:9, extend the ground by **edge replication** below
it, re-stage the cutouts when spacing must change. Do not synthesise a matching ground —
it leaves a visible rectangle; replicate the master's own edge pixels instead, and only
past an edge that is pure background (its top and sides are, its bottom is jersey).

**Add or change a Steam capsule** — `steam.py`. Each builder is a few lines: a `ground()`
call, a `slab_ext()` for Buckles, a `put()` for Rozier, a `_logo()`. `mark_clear()` will
tell you what fraction of Buckles' JOHNNIES + 43 survives the staging; anything under
about 98% reads as a cropping mistake. `verify()` checks every output's exact pixel
dimensions and asserts the library hero composites no type.

**Retune the ball** — `ball.py`. Pebble is a bump-mapped relight, not a texture overlay.
Do not divide the slope by the foreshortening; that amplifies the perturbation up to 8× at
the silhouette and throws a band of dark speckles down the edge.

---

## Platform constraints worth not rediscovering

- **YouTube banner:** desktop and mobile share the *same* 423px-tall band of the 1440
  frame — desktop is only wider. Everything that must be seen lives in 29% of the height,
  which forces the figures to about 41% of frame height. A 16:9 composition shows heads
  only.
- **Steam capsules:** text is limited to the game name and official subtitle. No callouts,
  quotes, laurels or "Coming Soon" without an Artwork Override. **The library hero takes no
  text at all** — Steam draws the library logo over it at runtime.
- **Nano Banana 2 Lite caps at 1K.** A model limit, not an account limit. A 2× Lanczos
  plus unsharp reaches 2752×1536 and covers every format. The bigger model is a
  *different* model, not a larger one — re-running through it is a fresh roll on the faces.
- The visible Gemini corner glyph is inpainted out. **SynthID's invisible watermark
  survives** and will read positive on any detector.

---

## The rest of the documentation

| file | what |
|---|---|
| `kv_start_here.md` | orientation for a thread picking this up cold. Read first. |
| `rivals-kv.md` | the narrative: every decision, the measurements, the failed approaches |
| `kv_capsules.md` | the Steam capsule set — rules, layouts, and the three defects found in review |
| `DELIVERY_MANIFEST.md` | which built file is live where, and what to re-upload after a rebuild |

Every script also carries its own failed approaches in its docstring. Before trying an
approach, check whether it is already documented there as a dead end — several are.
