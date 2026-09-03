#!/usr/bin/env python3
"""Brand assets for the KV: the JOHNNIES wordmark, keyed off its banner, and a basketball.

Round 1 established that Nano Banana cannot reproduce graphic detail -- it replaced the
Sterling Knight crest with an invented cat, wiped the JOHNNIES wordmark to a blank white
box, and set both numbers in a generic font. So the marks stop being something we ask a
generator to preserve and become something we composite. These are the pieces.
"""
import pathlib, math
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
from scipy import ndimage

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "assets"; OUT.mkdir(exist_ok=True)
BANNER = str(ROOT / "source" / "lancaster_team_banner.jpg")

# the JOHNNIES band inside the 1920x679 team banner, found by eye and verified below
BAND = (380, 310, 1540, 540)


def wordmark():
    """Key the JOHNNIES band off its patterned ground.

    Not by flood fill from the border -- tried that, and it leaked through a gap in the
    keyline and ate the band's black ground and the orange letter outlines, leaving white
    letters floating. The keyline is a CLOSED LOOP, so the robust move is to fill its
    holes: everything the loop encloses is the mark, whatever colour it happens to be.
    Colour-keying is hopeless here because the banner's background uses the mark's exact
    orange and black.
    """
    im = Image.open(BANNER).convert("RGB")
    a = np.array(im).astype(np.int16)

    # Work on the WHOLE banner, not a crop. The band's keyline is its own closed loop, but
    # cropping first risks clipping it open, and an open loop fills to nothing.
    keyline = a.min(2) > 200                        # every near-white pixel
    lab, n = ndimage.label(keyline)
    objs = ndimage.find_objects(lab)
    band = None
    for i, sl in enumerate(objs):                   # the band: wide, short, near-centre
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if w > 900 and h < 260:
            band = (i + 1, sl); break
    if band is None:
        raise SystemExit("JOHNNIES band not found — check the near-white threshold")
    idx, sl = band

    # Two dead ends before this worked, both worth not repeating:
    #   binary_fill_holes needs a watertight loop, and the basketball passing behind the
    #   band breaks the keyline -- it returned the outline plus crumbs.
    #   Span-filling that one COMPONENT failed too, because the band's left and right end
    #   strokes label as separate components, so most rows had no outer pixels to span to.
    # Span-fill the whole near-white mask inside the band's bounding box instead. Every row
    # then runs end stroke to end stroke, and the band is horizontally convex, so this
    # reconstructs the silhouette exactly -- angled ends and all.
    # Pad the row range before filling: the component's own bbox stops at the letter
    # baseline and clips the band's bottom keyline off. Rows past the band contribute
    # nothing unless they contain near-white, and inside the band's x-range they do not.
    y0, y1 = sl[0].start, min(keyline.shape[0], sl[0].stop + 22)   # no top pad: it caught
                                                                    # the LANCASTER bar
    # Widen the x-range past the keyline component's own bbox. The J's left stem and the
    # S's right bowl are separate white components that stick out beyond it, so filling only
    # within 412:1506 sliced both letters off at the edges.
    xa, xb = max(0, sl[1].start - 40), min(keyline.shape[1], sl[1].stop + 40)
    filled = np.zeros_like(lab, dtype=bool)
    for y in range(y0, y1):
        xs = np.where(keyline[y, xa:xb])[0]
        if len(xs):
            filled[y, xa + xs.min(): xa + xs.max() + 1] = True

    # The pad also catches the top of the basketball sitting behind the lockup. Jamie wants
    # the wordmark alone on the jersey, no ball. Ball rows span a few hundred px where band
    # rows span the full width, so drop every row narrower than 80% of the widest.
    span = filled.sum(1)
    filled[span < 0.8 * span.max()] = False

    # Reach back up for the lockup's top edge. Above the band's white bar sit a black
    # border (rows 300-306 in the banner) and an orange rule (308-310), and the crop was
    # starting at 312, below both. They carry no white, so the span-fill finds nothing
    # there -- extend upward using the span of the first filled row instead. Stop at 12
    # rows: two more and the LANCASTER bar's own white underside comes with it.
    TOP_EXTRA = 12
    top = int(np.argmax(filled.any(1)))
    filled[top - TOP_EXTRA:top] = filled[top]

    alpha = np.array(Image.fromarray(filled.astype(np.uint8) * 255)
                     .filter(ImageFilter.GaussianBlur(0.6)))
    out = Image.merge("RGBA", (*im.split(), Image.fromarray(alpha)))
    ys, xs = np.where(alpha > 10)
    out = out.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))

    # Trim the stepped ends. In the full lockup the LANCASTER bar overhangs the JOHNNIES
    # band, so the band's left and right ends are notched to receive it. Lifted on its own
    # that notch reads as a broken tick floating above the J. Drop the columns where the
    # band is not at full height.
    A = np.array(out)[..., 3] > 10
    cov = A.sum(0)
    full = cov > 0.30 * np.median(cov[cov > 0])
    lo, hi = int(np.argmax(full)), len(full) - int(np.argmax(full[::-1]))
    out = out.crop((lo, 0, hi, out.height))
    out.save(OUT / "johnnies_wordmark.png")
    print(f"wordmark {out.size}  kept {100*(alpha>10).mean():.1f}% of the crop, "
          f"from {n} white components")
    return out


BALL_SVG = str(ROOT / "source" / "orange_gp_bball.svg")


def basketball(size=1600):
    """The game's own basketball, off orange_gp_bball.svg -- vector, so any size we want.

    Two procedural attempts failed before this. The second was geometrically defensible --
    a basketball read as an equator plus four meridians, side curves at r*sin(45)=0.707r --
    and it still looked like a globe, because that model is simply not how a basketball is
    panelled. Real seams are the asymmetric S-curve pattern in this asset. The lesson is
    the same one the jerseys taught: when the real artwork exists, use it, do not
    reconstruct it. Jamie flagged the seams as a must-have for the KV and he was right to.

    The ball goes in the PLATE, where its job is to give the generator correct geometry to
    wrap hands around instead of inventing a sphere and two hands at once -- and, now,
    correct seams to copy rather than my wrong ones.
    """
    import cairosvg
    png = OUT / "_ball_raw.png"
    cairosvg.svg2png(url=BALL_SVG, write_to=str(png),
                     output_width=size * 2, output_height=size * 2)
    im = Image.open(png).convert("RGBA")
    a = np.array(im).astype(np.int16)

    # The asset is a button: the ball sits inside a heavy black disc. Keep only the ball,
    # found as the pixels that are actually orange (R clearly above B).
    ballpx = (a[..., 3] > 40) & (a[..., 0] - a[..., 2] > 30)
    ys, xs = np.where(ballpx)
    im = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))

    # circular alpha, so no black ring survives at the edge
    n = max(im.size)
    im = im.resize((n, n), Image.LANCZOS)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    rr = np.sqrt((xx - n / 2) ** 2 + (yy - n / 2) ** 2) / (n / 2)
    mask = np.clip((1.0 - rr) * n / 6, 0, 1)
    arr = np.array(im).astype(np.float32)
    arr[..., 3] = np.minimum(arr[..., 3], mask * 255)
    im = Image.fromarray(arr.astype(np.uint8)).resize((size, size), Image.LANCZOS)
    png.unlink()

    # The vector asset is flat cel art, and flat is what the generator copied -- the ball
    # came back reading cartoonish against painted figures. Give it material: pebble grain,
    # spherical falloff and one soft specular, all modulated by the sphere's own normal so
    # the texture wraps instead of sitting on top as a flat pattern.
    n = size
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    nx, ny = (xx - n / 2) / (n / 2), (yy - n / 2) / (n / 2)
    nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0, 1))

    rng = np.random.default_rng(7)
    grain = rng.normal(0, 1, (n // 10, n // 10))   # ~10px cells = pebble scale
    grain = np.array(Image.fromarray(((grain - grain.min()) /
                                      (grain.max() - grain.min() + 1e-6) * 255).astype(np.uint8))
                     .resize((n, n), Image.BICUBIC)).astype(np.float32) / 255.0
    pebble = 1.0 + (grain - 0.5) * 0.17 * nz          # fades out at the silhouette

    lam = 0.70 + 0.46 * np.clip(-0.42 * nx - 0.52 * ny + 0.74 * nz, 0, 1)
    # a basketball is MATTE. The first pass used a broad 0.55 specular and came out
    # looking like polished plastic. Barely any, and tight.
    spec = 0.07 * np.clip(-0.45 * nx - 0.58 * ny + 0.68 * nz, 0, 1) ** 26

    a = np.array(im).astype(np.float32)
    a[..., :3] = np.clip(a[..., :3] * (lam * pebble)[..., None] + spec[..., None] * 255, 0, 255)
    im = Image.fromarray(a.astype(np.uint8))
    im.save(OUT / "basketball.png")
    print(f"basketball {im.size}  from the game's own vector asset")
    return im


def basketball_drawn(size=1400):
    """Kept only as a record of what did NOT work -- see basketball() above."""
    S = size * 4                                    # supersample, then down
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pad = int(S * 0.02)
    d.ellipse([pad, pad, S - pad, S - pad], fill=(214, 106, 38, 255),
              outline=(26, 18, 12, 255), width=int(S * 0.022))

    lw = int(S * 0.028)
    ink = (26, 18, 12, 255)
    c, r = S / 2, (S - 2 * pad) / 2

    # A basketball is 8 panels: one equator plus four meridians spaced 45 degrees apart.
    # Seen face-on from the equator, a meridian at longitude phi projects to an ellipse of
    # half-width r*sin(phi). So phi=0 is the straight centre seam, phi=90 IS the ball's own
    # outline, and phi=45 and 135 both project to the SAME ellipse at r*sin45 = 0.707r.
    # That is the whole visible seam set, and 0.707 is the number -- my first pass used
    # 0.55, which pinched the side curves inward and made it read as a globe.
    d.line([(c, pad), (c, S - pad)], fill=ink, width=lw)              # centre meridian
    d.line([(pad, c), (S - pad, c)], fill=ink, width=lw)              # equator
    ew = r * 0.7071
    d.ellipse([c - ew, c - r, c + ew, c + r], outline=ink, width=lw)  # the 45 deg pair

    # simple spherical shading so it reads as a ball, not a disc
    y, x = np.mgrid[0:S, 0:S].astype(np.float32)
    nx, ny = (x - c) / r, (y - c) / r
    d2 = nx ** 2 + ny ** 2
    nz = np.sqrt(np.clip(1 - d2, 0, 1))
    lam = np.clip(0.55 + 0.75 * (-0.45 * nx - 0.55 * ny + 0.65 * nz), 0.25, 1.35)
    a = np.array(im).astype(np.float32)
    a[..., :3] *= lam[..., None]
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    # Tilt the whole thing. A pole-up, dead-symmetrical seam pattern reads as a diagram of
    # a ball rather than a ball; every photograph of one is caught at some angle. The
    # silhouette is a circle, so rotating cannot change it.
    im = im.rotate(-17, resample=Image.BICUBIC)

    im = im.resize((size, size), Image.LANCZOS)
    im.save(OUT / "basketball.png")
    print(f"basketball {im.size}")
    return im


if __name__ == "__main__":
    wordmark()
    basketball()
