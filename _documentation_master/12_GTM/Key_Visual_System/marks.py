#!/usr/bin/env python3
"""Composite the real jersey marks onto the locked generated image.

No generation happens here and none should. The image below is final art -- every mark is
painted onto a copy of it, on its own layer, at a position and scale I control. That is
what makes Jamie's "how do we preserve this exact image" question answerable: we preserve
it by never sending it back to a generator. A mark that lands wrong is re-run with two
numbers changed; the faces, bodies, ball and light are untouched by construction.
"""
import pathlib, os
from PIL import Image, ImageFilter
import numpy as np
from scipy import ndimage

import digits

# Sampled off the locked image, not guessed. The jersey's own trim is nowhere near paper
# white -- Rozier's shoulder panels sit at 161 and Buckles' at 211 -- which is exactly why
# a pure-white numeral read as pasted on.
ROZIER_WHITE  = (161, 161, 167)   # his shoulder panel
BUCKLES_WHITE = (193, 177, 175)   # his outer-shoulder stripe (222,204,202), knocked back
                                  # ~13%: at full stripe value the numerals sat forward of
                                  # the fabric they are printed on
TRIM_BLUE     = (61, 78, 115)     # the blue on his outer shoulder
NECK_GREY     = (110, 110, 120)   # the grey around his v-neck
NUM_H_FRAC    = 0.175             # numeral height; both players share it

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "final"; OUT.mkdir(exist_ok=True)
BASE = ROOT / "source" / "nb_round5_generation.png"   # the raw generation; irreplaceable
WORDMARK = ROOT / "assets" / "johnnies_wordmark.png"


def place(base, mark, cx, cy, width, rot=0.0, light=(0.80, 1.10)):
    """Drop a mark onto the jersey and let the jersey's own shading show through it.

    A flat paste reads as a sticker. Multiplying by the fabric's local luminance carries
    the garment's folds and falloff across the mark, so it sits IN the cloth. The clamp
    range matters: an unclamped multiply drove the wordmark's whites to grey on the first
    attempt, so the floor is high and the ceiling is low -- broad falloff only, no detail.
    """
    m = mark.convert("RGBA")
    m = m.resize((width, max(1, int(width * m.height / m.width))), Image.LANCZOS)
    if rot:
        m = m.rotate(rot, resample=Image.BICUBIC, expand=True)
    x, y = int(cx - m.width / 2), int(cy - m.height / 2)

    patch = np.array(base.crop((x, y, x + m.width, y + m.height)).convert("RGB"))
    lo, hi = light
    shade = np.clip(lo + patch.astype(np.float32).mean(2) / 520.0, lo, hi)[..., None]
    a = np.array(m).astype(np.float32)
    a[..., :3] = np.clip(a[..., :3] * shade, 0, 255)
    lit = Image.fromarray(a.astype(np.uint8))
    base.paste(lit, (x, y), lit)
    return base


def jersey_mask(rgb, kind):
    """Which pixels are actually fabric.

    This is what lets a numeral sit BEHIND the ball and hands without me cutting a mask by
    hand: draw the mark only where the underlying pixel is jersey, and the ball, the arms
    and the fingers occlude it for free, correct to the pixel.

    Orange fabric and skin are the hard pair -- both have R well above B. They separate on
    the green channel instead: the jersey runs G/R near 0.45, skin near 0.66.
    """
    a = rgb.astype(np.float32)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    if kind == "blue":
        # Not "is it blue" -- "is it NOT an occluder". Requiring blue failed: the jersey's
        # own shadow is dark enough that B-R collapses there, so the rule punched ragged
        # holes through the middle of the digits. Ball and skin are the only warm things
        # in front of this jersey, so excluding warmth is both simpler and robust to shade.
        return (R - B) < 22
    # Orange fabric and skin are the hard pair -- both warm. They separate on green:
    # jersey runs G/R near 0.45, skin near 0.66. Note there is NO R-B test here: requiring
    # R-B>80 held on lit fabric but collapsed in the jersey's own shadow, which bit chunks
    # out of the 4's lower left and the 3's right edge once the numeral got bigger. The
    # green ratio survives shading; an absolute channel difference does not.
    return (G < 0.58 * R) & (R > 52) & (R - B > 26)


def place_masked(base, mark, cx, cy, height, kind,
                 shading=0.95, texture=0.55, light=(0.50, 1.22)):
    """Place a mark, clipped to the jersey fabric under it, and lit by that fabric.

    The shading is TRANSFERRED, not invented. Every pixel's brightness is divided by the
    median brightness of the fabric in the same patch, giving a relative falloff field --
    1.0 where the jersey is at its average, below 1 in the shadow running up his right
    side, above 1 on the lit fold. Multiplying the mark by that field makes the garment's
    own shadow continue straight across the numeral, which is what stops it reading as
    painted on top.

    The field is split in two. The low frequencies are the broad shadow; the high
    frequencies are the cloth's own grain and weave, applied at lower strength so the
    numeral picks up texture without picking up noise.

    Earlier versions clamped this to (0.80, 1.10), which is so narrow that almost none of
    the jersey's shading survived -- hence the flat, decal look.
    """
    m = mark.convert("RGBA")
    m = m.resize((max(1, int(height * m.width / m.height)), height), Image.LANCZOS)
    x, y = int(cx - m.width / 2), int(cy - m.height / 2)

    patch = np.array(base.crop((x, y, x + m.width, y + m.height)).convert("RGB")).astype(np.float32)
    fabric = jersey_mask(patch, kind)
    # pull the mask in a touch so the keyline never bleeds onto skin at the boundary
    fabric = ndimage.binary_erosion(fabric, np.ones((3, 3)), iterations=2)
    soft = np.array(Image.fromarray((fabric * 255).astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(1.1))).astype(np.float32) / 255.0

    lum = patch.mean(2)
    ref = np.median(lum[fabric]) if fabric.any() else max(lum.mean(), 1.0)
    broad = ndimage.gaussian_filter(lum, height * 0.10) / max(ref, 1.0)
    fine = (lum - ndimage.gaussian_filter(lum, 1.6)) / 255.0

    lo, hi = light
    shade = np.clip(1.0 + (broad - 1.0) * shading + fine * texture, lo, hi)[..., None]
    a = np.array(m).astype(np.float32)
    a[..., :3] = np.clip(a[..., :3] * shade, 0, 255)
    a[..., 3] *= soft
    lit = Image.fromarray(a.astype(np.uint8))
    base.paste(lit, (x, y), lit)
    return base


def torso_span(rgb, row, x0f=0.58, x1f=0.94):
    """Left and right edge of the orange jersey on one row, taking the longest unbroken
    run so a sliver of lit arm can't drag the centre sideways."""
    H, W, _ = rgb.shape
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    orange = (R - B > 80) & (G < 0.56 * R) & (R > 90)
    i = np.where(orange[row, int(W * x0f):int(W * x1f)])[0]
    if not len(i):
        return None
    seg = max(np.split(i, np.where(np.diff(i) > 1)[0] + 1), key=len)
    return int(W * x0f) + seg.min(), int(W * x0f) + seg.max()


def garment_centre(rgb, rows=(.50, .55, .60, .65, .70, .75), x0f=0.58, x1f=0.94):
    """Horizontal centre of the jersey including its white side stripes."""
    H, W, _ = rgb.shape
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    orange = (R - B > 80) & (G < 0.56 * R) & (R > 90)
    stripe = (rgb.mean(2) > 150) & ((rgb.max(2) - rgb.min(2)) < 40)
    garment = orange | stripe
    cs = []
    for f in rows:
        i = np.where(garment[int(H * f), int(W * x0f):int(W * x1f)])[0]
        if len(i):
            seg = max(np.split(i, np.where(np.diff(i) > 2)[0] + 1), key=len)
            cs.append(int(W * x0f) + (seg.min() + seg.max()) / 2)
    return int(np.mean(cs))


def erase_watermark(im, pad=4):
    """Paint out the generator's corner glyph.

    The ground behind it is a smooth gradient with no detail, so there is nothing to
    reconstruct -- interpolating each row straight across from the clean columns either
    side lands within a level or two of what was there.

    Worth knowing: this removes the VISIBLE mark only. Google also embeds SynthID
    invisible watermarking in these outputs, and that survives -- which is fine, and
    consistent with the AI disclosure already published on the Steam page.
    """
    a = np.array(im).astype(np.float32)
    H, W, _ = a.shape

    # Find the glyph itself, not a bounding box round it. It is near-white and desaturated;
    # a plain luminance threshold also catches his lit forearm, which is right beside it.
    y0c, x0c = int(H * .82), int(W * .88)
    c = a[y0c:, x0c:]
    glyph = (c.min(2) > 112) & ((c.max(2) - c.min(2)) < 26)   # measured: min-ch ~131, sat ~9
    if not glyph.any():
        print("no watermark found"); return im

    mask = np.zeros((H, W), bool)
    mask[y0c:, x0c:] = ndimage.binary_dilation(glyph, np.ones((3, 3)), iterations=pad)

    # Diffusion inpaint, not a straight interpolation across the box. The first attempt
    # interpolated each row from the columns either side, but his forearm passes through
    # that box, so it smeared the arm's edge sideways into a rectangular band. Relaxing to
    # a harmonic fill instead lets every boundary -- arm edge included -- pull its own
    # neighbourhood inwards.
    ys, xs = np.where(mask)
    for ch in range(3):
        f = a[..., ch].copy()
        f[mask] = f[~mask & ndimage.binary_dilation(mask, np.ones((3, 3)), iterations=3)].mean()
        for _ in range(320):
            blur = ndimage.uniform_filter(f, 3)
            f[ys, xs] = blur[ys, xs]
        a[..., ch] = f
    print(f"watermark erased: {int(mask.sum())}px inpainted")
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


SCALE = int(os.environ.get("SCALE", "1"))


if __name__ == "__main__":
    im = Image.open(BASE).convert("RGB")

    # Watermark first, at native size: the inpaint reads a smooth gradient and a clean arm
    # edge, and both are easier to reconstruct before an upscale has interpolated them.
    im = erase_watermark(im)

    if SCALE > 1:
        # Upscale the BASE, then composite. Marking first and enlarging afterwards would
        # enlarge the numerals too, which throws away the one part of this image that can
        # be drawn at any resolution for free. Painted art takes Lanczos well -- there is
        # no photographic grain for the unsharp to turn into noise.
        w, h = im.size
        im = im.resize((w * SCALE, h * SCALE), Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=2.2 * SCALE, percent=58, threshold=3))

    W, H = im.size
    base_rgb = np.array(im).astype(np.float32)

    # Buckles' marks centre on his TORSO, measured, not eyeballed. Both were sitting at
    # 0.727W against a torso centre of 0.745W -- 25px off, which is what read as uncentred.
    wm_row, num_row = int(H * 0.545), int(H * 0.700)
    NUM_H = int(H * NUM_H_FRAC)
    # Centre on the whole GARMENT, stripes included, not the orange field alone. The two
    # white side stripes are unequal in view because he is lit and turned slightly, so an
    # orange-only centre sits a few pixels off where the eye reads the middle.
    # Measure on a canonical 2752-wide copy and carry the answers as FRACTIONS, whatever
    # size we are actually writing. Measuring on the live pixels looked equivalent and was
    # not: the upscale-and-sharpen nudges pixels across the jersey mask's threshold, so the
    # 1x and 2x masters came out with the wordmark a few pixels apart.
    REF = 2752
    ref = im if W == REF else im.resize((REF, int(H * REF / W)), Image.LANCZOS)
    ref_rgb = np.array(ref).astype(np.float32)
    cx = int(garment_centre(ref_rgb) / REF * W)
    rl, rr_ = torso_span(ref_rgb, int(ref.height * 0.545))
    wm_l, wm_r = int(rl / REF * W), int(rr_ / REF * W)
    print(f"torso centre {cx/W:.4f} W; chest width at wordmark row {(wm_r-wm_l)/W:.4f} W")

    # The wordmark also shrank by accident: it was placed by WIDTH in the first pass and by
    # HEIGHT after, which cut it to 56% without my noticing. Size it off the chest instead.
    wordmark = Image.open(WORDMARK)
    wm_w = int((wm_r - wm_l) * 0.88)
    # Jamie asked for the wordmark to sit lower by "about 20% of the wordmark's size". Read
    # as 20% of its WIDTH -- 20% of its height would be 8px, which is not a note anyone
    # would bother making.
    place_masked(im, wordmark, cx=cx, cy=wm_row + int(wm_w * 0.20),
                 height=int(wm_w * wordmark.height / wordmark.width), kind="orange")
    # Same numeral height as Rozier's, so the two players' numbers match at full size even
    # though most of his is behind the ball.
    place_masked(im, digits.number("43", 340 * SCALE, ink=BUCKLES_WHITE, edge=(30, 22, 20)),
                 # +18 was hardcoded in pixels, so at 1x it pushed the numeral twice as far
                 # down the frame as at 2x -- the two masters disagreed. Fractional now,
                 # matched to the 2x placement Jamie picked.
                 cx=cx, cy=num_row + int(H * 0.0117), height=NUM_H, kind="orange",
                 shading=1.05, texture=0.65)

    # Rozier: 32 on the chest, deliberately placed so the ball and his hands cut across its
    # top. Only the lower part survives the fabric mask, which is exactly the read Jamie
    # asked for -- the bottom of a number showing below the ball.
    for tag, edge in (("blueline", TRIM_BLUE), ("greyline", NECK_GREY)):
        out = im.copy()
        # Rozier's was signed off before the shading transfer went in, so he gets a much
        # lighter touch of it -- enough to sit in the cloth, not enough to change what was
        # already approved.
        place_masked(out, digits.number("32", 340 * SCALE, ink=ROZIER_WHITE, edge=edge),
                     cx=int(W * 0.272), cy=int(H * 0.735), height=int(H * 0.175),
                     kind="blue", shading=0.40, texture=0.30, light=(0.72, 1.08))
        out.save(OUT / f"KV_marks_v3_{tag}{'_2x' if SCALE>1 else ''}.png")
        out.crop((int(W * .12), int(H * .40), int(W * .48), H)).resize(
            (740, int(740 * (H * .60) / (W * .36))), Image.LANCZOS).save(
            OUT / f"_zoom_roz_{tag}.png")
    print("wrote both outline variants")
