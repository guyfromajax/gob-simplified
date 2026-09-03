#!/usr/bin/env python3
"""Steam store capsules in the rivals-KV family.

Steam's Graphical Asset Rules split the set in two, and the split drives every layout here:

  CAPSULES  (header 920x430, small 462x174, main 1232x706, vertical 748x896,
             library capsule 600x900, library header 920x430)
            carry the logo, and their text is limited to the game name and official
            subtitle. No callouts, quotes, laurels or "Coming Soon" -- those need an
            Artwork Override, which is a separate submission and a separate rejection risk.

  HERO      (library hero 3840x1240) takes NO text of any kind. Steam draws the library
            logo over it at runtime. Pure image.

So a capsule is always: KV ground + figures + lockup. Nothing else may go in it.

This module builds the MAIN CAPSULE in two treatments so they can be compared rather
than argued about:

  A  pure KV      -- the trailer-thumbnail staging, logo left, players right
  B  KV + grid    -- the same, with the box-score numeral grid from the current capsule
                     surviving as a ground texture under everything

The grid is rebuilt procedurally rather than lifted, for three reasons: the original is
baked at one size and every capsule is a different aspect, its numerals are flattened into
the artwork so they cannot be moved out from under a face, and it is drawn in #F09018
rather than the brand #F79420. Measured off `03 main-capsule 1232x706.png`: cap height
17px, row pitch 48px, column pitch ~168px, glyph colour ~(35,39,49) over a (9,12,22)
ground -- i.e. a cool grey at roughly 15% alpha. Those are carried below as fractions of
width so they hold at any capsule size.
"""
import pathlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

from stage import (ground, put, put_slab, contact_shadow, save, fade_bottom,
                   BUCKLES_SLAB, BUCKLES_FIG,
                   COOL, WARM, INK, MASTER, CUT, LOGO, FONT, OUT)

ROOT = pathlib.Path(__file__).parent
SOUT = ROOT / "steam"; SOUT.mkdir(exist_ok=True)

# --- grid metrics, as fractions of frame width (measured off the current capsule) -------
CAP_H = 17 / 1232          # numeral cap height
ROW_P = 48 / 1232          # row pitch
COL_P = 168 / 1232         # column pitch
GRID_RGB = np.array([150, 162, 190], np.float32)   # cool slate, laid on at low alpha
GRID_A = 0.155

STAT_KINDS = ("pct", "rec", "avg", "tot", "int")


def _stat(rng, kind):
    if kind == "pct":
        return f".{rng.integers(280, 620):03d}"
    if kind == "rec":
        return f"{rng.integers(1, 22)}-{rng.integers(1, 22)}"
    if kind == "avg":
        return f"{rng.integers(2, 34)}.{rng.integers(0, 10)}"
    if kind == "tot":
        return str(rng.integers(88, 132))
    return str(rng.integers(11, 99))


def grid_layer(W, H, seed=7, alpha=GRID_A, jitter=True):
    """Columns of box-score figures, the register the current capsules are built in.

    Drawn in Bebas -- the brand face -- rather than the original's generic condensed
    grotesque, so the texture and the lockup come from the same type family.
    """
    rng = np.random.default_rng(seed)
    size = max(6, int(CAP_H * W * 1.42))          # Bebas cap height is ~0.70 of its em
    f = ImageFont.truetype(FONT, size)
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)

    pitch_x, pitch_y = COL_P * W, ROW_P * W
    ncol = int(W / pitch_x) + 2
    nrow = int(H / pitch_y) + 2
    for c in range(ncol):
        kind = STAT_KINDS[c % len(STAT_KINDS)]
        x = c * pitch_x + pitch_x * 0.12
        for r in range(nrow):
            y = r * pitch_y - pitch_y * 0.4
            s = _stat(rng, kind)
            # per-cell brightness variation: a perfectly even grid reads as a screen
            v = int(255 * (0.55 + 0.45 * rng.random())) if jitter else 255
            d.text((x, y), s, font=f, fill=v)

    a = np.array(im).astype(np.float32) / 255.0
    return a[..., None] * GRID_RGB[None, None, :] * alpha


def court_layer(W, H, alpha=0.09, cx=0.30, cy=1.16, scale=1.0):
    """Half-court geometry as thin line art: centre circle, arc, key. The current capsules
    use it as a watermark behind everything, and it is the one piece of their vocabulary
    that says 'basketball' without saying 'stock graphic'."""
    ss = 2
    im = Image.new("L", (W * ss, H * ss), 0)
    d = ImageDraw.Draw(im)
    R = W * 0.52 * scale * ss
    px, py = cx * W * ss, cy * H * ss
    lw = max(1, int(W * 0.0018 * ss))

    def circ(rad):
        d.ellipse([px - rad, py - rad, px + rad, py + rad], outline=255, width=lw)

    circ(R)                     # three-point arc
    circ(R * 0.30)              # free-throw circle
    key_w, key_h = R * 0.44, R * 0.62
    d.rectangle([px - key_w, py - key_h, px + key_w, py + key_h], outline=255, width=lw)
    d.line([px - R * 0.13, py + key_h * 0.86, px + R * 0.13, py + key_h * 0.86],
           fill=255, width=lw * 2)                       # backboard
    d.ellipse([px - R * 0.055, py + key_h * 0.70, px + R * 0.055, py + key_h * 0.80],
              outline=255, width=lw)                     # rim

    a = np.array(im.resize((W, H), Image.LANCZOS)).astype(np.float32) / 255.0
    return a[..., None] * np.array([150, 168, 205], np.float32)[None, None, :] * alpha


_PLATE = _SOLID = None


def master_plate(master):
    """The master's reconstructed background, and the figure-coverage mask that goes with
    it. Cached -- neither changes."""
    global _PLATE, _SOLID
    if _PLATE is None:
        from cutouts import clean_plate, matte
        a = np.array(master).astype(np.float32)
        _PLATE = clean_plate(a)
        _, _SOLID = matte(a, _PLATE)
    return _PLATE, _SOLID


def slab_ext(canvas, master, height, cx, bottom, feather=0.16, extend="right",
             fade=0.0, dim=1.0):
    """Place Buckles as a slab of the master, RE-GROUNDED onto the canvas it lands on.

    Buckles can never be matted -- his outer locs sit under 12 levels from the background,
    below any threshold that does not also key noise -- so he travels as a rectangle of the
    master. The rectangle brings the master's own dark ground with it, and feathering only
    softens its edges: the interior stays darker than the capsule's lit ground, so he ends
    up inside a visible dark box. Feather harder and the box just gets a softer edge.

    The fix is to subtract the ground he came from and add the one he is going to:

        out = canvas + (slab - master_plate)

    Where the slab is pure background the difference is ~0 and the result IS the canvas, so
    there is no rectangle to see at any feather width. Where he is, his departure from the
    plate is carried across intact. That deviation is then blended back toward the raw slab
    wherever it is large, so his lit fabric keeps the master's own values rather than being
    re-lit by a ground that was never behind him.

    Note this uses the difference as a SIGNAL, not as a matte. His locs sit in the
    ambiguous middle either way -- but there the blend is between his dark hair and a dark
    ground, so being wrong about which is which costs nothing. That is exactly why the same
    measurement cannot cut him out but can safely re-ground him.

    The slab is also extended to the frame edge by replicating its own end row and column.
    The extension begins with the pixels it continues, so it cannot mismatch; synthesising
    a matching gradient instead leaves a visible rectangle, which is the mistake the square
    and the banner both made first.
    """
    H, W, _ = canvas.shape
    sx0, sy0, sx1, sy1 = BUCKLES_SLAB
    fx0, fx1, fy0, fy1 = BUCKLES_FIG
    scale = (height * H) / (fy1 - fy0)
    sw, sh = int((sx1 - sx0) * scale), int((sy1 - sy0) * scale)

    box = (sx0, sy0, sx1, sy1)
    mplate, msolid = master_plate(master)
    slab = np.array(master.crop(box).resize((sw, sh), Image.LANCZOS)).astype(np.float32)
    plate = np.array(Image.fromarray(np.clip(mplate, 0, 255).astype(np.uint8))
                     .crop(box).resize((sw, sh), Image.LANCZOS)).astype(np.float32)
    diff = slab - plate

    # Coverage: is this pixel HIM, or the ground he was shot against?
    #
    # This is the matte's own solid mask, and using it here is safe in a way that cutting
    # him out with it is not. Inside it, the raw slab is used, so his face and fabric keep
    # the master's exact values. Outside it, `dest + diff` is used, which is the correct
    # composite for any partly-covered pixel -- for a half-covered hair pixel the difference
    # is alpha*(hair - plate), so adding it to the destination lays that hair over the new
    # ground exactly. The mask's known failure is his outer locs, which it slices off; but
    # there the answer it falls through to is the correct one, so the slice costs nothing.
    #
    # Two weaker signals were tried first and each broke something. A low magnitude
    # threshold handed w ~ 0.6 to the background between his locs, so those pixels took most
    # of their colour from the raw slab -- master ground and all -- and left a dark stain
    # beside his head, lapping over his temple. Raising the threshold instead pushed his
    # whole figure onto `dest + diff`, which tints him by (dest - plate): measured, +20
    # levels across his face and hair, washing him out against a warm capsule ground.
    cov = np.array(Image.fromarray((msolid * 255).astype(np.uint8))
                   .crop(box).resize((sw, sh), Image.LANCZOS)).astype(np.float32) / 255.0
    cov = ndimage.gaussian_filter(cov, max(1.0, sw * 0.0015))

    x0 = int(cx * W - ((fx0 + fx1) / 2 - sx0) * scale)
    y0 = int(bottom * H - (fy1 - sy0) * scale)

    fw = max(4, int(feather * sw))
    mask = np.ones((sh, sw), np.float32)
    mask[:, :fw] *= np.linspace(0, 1, fw)[None, :] ** 0.8
    mask[:int(fw * 0.9)] *= np.linspace(0, 1, int(fw * 0.9))[:, None] ** 0.8
    if fade:
        mask = fade_bottom(mask, fade)

    def grow(arr, axis, n, decay=False):
        """Extend by replicating the end row/column. `decay` ramps the copy out to zero.

        The difference layer must decay. Its value at the slab's edge is not signal, it is
        the master's own per-row noise, and repeating one column of that across a few
        hundred pixels turns it into horizontal streaks -- faint, but visible across the
        hero's dark right side. Ramped to zero, the extension resolves to the canvas ground
        exactly, which is what is wanted there anyway.
        """
        end = arr[:, -1:] if axis == 1 else arr[-1:]
        rep = np.repeat(end, n, axis=axis)
        if decay:
            # Short, and it has to be short. A ramp that holds full strength across the
            # first half of the extension keeps the noise coherent long enough to read as
            # banding; the join itself needs only a few dozen pixels to hide, because the
            # difference is already near zero where the slab ends.
            k = max(8.0, min(n, 0.012 * max(canvas.shape[:2])))
            r = np.clip(1.0 - np.arange(n) / k, 0, 1) ** 1.4
            rep = rep * (r[None, :, None] if axis == 1 else r[:, None, None])
        return np.concatenate([arr, rep], axis=axis)

    if extend == "right" and x0 + sw < W:
        n = W - (x0 + sw)
        slab = grow(slab, 1, n)
        diff = grow(diff, 1, n, decay=True)
        cov = grow(cov[..., None], 1, n)[..., 0]
        mask = grow(mask, 1, n)
        sw += n
    if sh < H - y0:                                  # and downward, the ground below him
        n = H - y0 - sh
        slab = grow(slab, 0, n)
        diff = grow(diff, 0, n, decay=True)
        cov = grow(cov[..., None], 0, n)[..., 0]
        mask = grow(mask, 0, n)
        sh += n

    xa, ya = max(0, x0), max(0, y0)
    xb, yb = min(W, x0 + sw), min(H, y0 + sh)
    if xb <= xa or yb <= ya:
        return
    sl = (slice(ya - y0, yb - y0), slice(xa - x0, xb - x0))
    s, dfr = slab[sl], diff[sl]
    dest = canvas[ya:yb, xa:xb]

    w = cov[sl][..., None]
    # `dim` fades the FIGURE toward the ground, never the ground itself. Multiplying the
    # whole composite darkened the capsule's own field along with him, which is not what a
    # dimmed figure means.
    src = w * (s * dim + dest * (1 - dim)) + (1 - w) * (dest + dfr * dim)

    al = mask[sl][..., None]
    canvas[ya:yb, xa:xb] = dest * (1 - al) + src * al


# JOHNNIES + 43 in master pixels, measured off the master by keying the mark greys
# against the orange fabric. Every capsule has to keep this rectangle visible: it is the
# only thing in frame that says which club the rival plays for, and a numeral sliced by a
# frame edge or by Rozier's arm reads as a production mistake rather than as depth.
MARK_BOX = (1853, 2254, 882, 1194)   # JOHNNIES top, 43 bottom -- glyphs, no padding


def mark_clear(W, H, height, cx, bottom, roz, r_h, r_cx, r_bottom, label=""):
    """What fraction of Buckles' chest marks survives this staging.

    Written after two rounds of arithmetic gave the wrong answer. Estimating the numeral
    as a share of his figure width is wrong twice over -- BUCKLES_FIG spans arm to arm,
    which is widest exactly at numeral height, and Rozier's bounding box is not his
    silhouette. So this measures instead: it maps the mark rectangle through the same
    transform the slab uses, then samples Rozier's actual alpha over it.
    """
    fx0, fx1, fy0, fy1 = BUCKLES_FIG
    sx0, sy0, sx1, sy1 = BUCKLES_SLAB
    sc = (height * H) / (fy1 - fy0)
    x0 = int(cx * W - ((fx0 + fx1) / 2 - sx0) * sc)
    y0 = int(bottom * H - (fy1 - sy0) * sc)
    mx0 = x0 + (MARK_BOX[0] - sx0) * sc
    mx1 = x0 + (MARK_BOX[1] - sx0) * sc
    my0 = y0 + (MARK_BOX[2] - sy0) * sc
    my1 = y0 + (MARK_BOX[3] - sy0) * sc

    grid_x = np.linspace(mx0, mx1, 90)
    grid_y = np.linspace(my0, my1, 60)
    gx, gy = np.meshgrid(grid_x, grid_y)
    inside = (gx >= 0) & (gx < W) & (gy >= 0) & (gy < H)

    rh = int(r_h * H)
    rw = max(1, int(roz.width * rh / roz.height))
    ra = np.array(roz.resize((rw, rh), Image.LANCZOS))[..., 3]
    rx0, ry0 = int(r_cx * W - rw / 2), int(r_bottom * H - rh)
    ix = np.round(gx - rx0).astype(int)
    iy = np.round(gy - ry0).astype(int)
    hit = (ix >= 0) & (ix < rw) & (iy >= 0) & (iy < rh)
    covered = np.zeros_like(inside)
    covered[hit] = ra[iy[hit], ix[hit]] > 120

    vis = float((inside & ~covered).mean())
    flag = "" if vis > 0.985 else ("   <-- CLIPPED" if vis < 0.97 else "   <-- tight")
    print(f"      {label:22s} rival marks visible {100*vis:5.1f}%{flag}")
    return vis


def clear(W, H, cx, cy, rad, depth=0.78):
    """A soft hole in a texture layer, so type laid over it keeps its air."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx / W - cx) * (W / H)) ** 2 + (yy / H - cy) ** 2) / rad
    return 1.0 - depth * np.exp(-(d ** 2) * 1.4)


# ---------------------------------------------------------------------------------------

def main_capsule(name, grid=False, W=2464, H=1412, out=SOUT):
    """1232x706 at 2x. Trailer-thumbnail staging: lockup left, rivals right.

    Using the thumbnail's own composition is deliberate -- the store page and the YouTube
    trailer then read as one campaign rather than two, and it is a layout already checked
    for the one thing that goes wrong here (Buckles' hair against the frame edge).
    """
    roz = Image.open(CUT / "rozier.png").convert("RGBA")
    master = Image.open(MASTER).convert("RGB")
    logo = Image.open(LOGO).convert("RGBA")

    c = ground(W, H, [(0.16, 0.46, 0.46, COOL, 0.42), (0.60, 0.40, 0.46, COOL, 0.68),
                      (0.94, 0.44, 0.44, WARM, 0.88)])
    if grid:
        g = court_layer(W, H) + grid_layer(W, H)
        # Knock the texture down behind the lockup. At full strength the numerals sit
        # hard against the wordmark's outline and the two compete at store-render size,
        # where the logo is only ~440px wide.
        c += g * clear(W, H, 0.215, 0.560, 0.30)[..., None]

    put_slab(c, master, height=0.90, cx=0.870, bottom=1.02)
    contact_shadow(c, roz, height=0.98, cx=0.585, bottom=1.05, strength=0.5)
    put(c, roz, height=0.98, cx=0.585, bottom=1.05)

    _logo(c, logo, 0.360, 0.215, 0.455)
    mark_clear(W, H, 0.90, 0.870, 1.02, roz, 0.98, 0.585, 1.05, name)

    im = Image.fromarray(np.clip(c, 0, 255).astype(np.uint8)).resize((1232, 706), Image.LANCZOS)
    im.save(out / f"{name}.png")
    print(f"  {name:28s} {im.size[0]} x {im.size[1]}")
    return im


def _stock():
    return (Image.open(CUT / "rozier.png").convert("RGBA"),
            Image.open(MASTER).convert("RGB"),
            Image.open(LOGO).convert("RGBA"))


def _logo(c, logo, width, cx, cy):
    """`cy` is the lockup's CENTRE, not its baseline. `put` positions by base, and taking
    cy as the base silently pushed the logo off the top of both portrait capsules -- at
    0.80 frame width the lockup is 24% of a 748x896 frame's height, so a base at 0.175
    started it at -0.06."""
    H, W, _ = c.shape
    lw = int(W * width)
    lg = logo.resize((lw, int(lw * logo.height / logo.width)), Image.LANCZOS)
    hf = lg.height / H
    assert cy - hf / 2 > 0.005, f"lockup clips the top edge: {cy:.3f} - {hf/2:.3f}"
    put(c, lg, hf, cx, cy + hf / 2)


def _out(c, name, size, out=SOUT):
    im = Image.fromarray(np.clip(c, 0, 255).astype(np.uint8)).resize(size, Image.LANCZOS)
    im.save(out / f"{name}.png")
    print(f"  {name:34s} {im.size[0]:>5} x {im.size[1]}")
    return im


def header_capsule(name="header_capsule_920x430", size=(920, 430), ss=2):
    """2.14:1. The main capsule's composition, tightened -- the frame is wider relative to
    its height, so the figures come down and the lockup takes a larger share of width."""
    roz, master, logo = _stock()
    W, H = size[0] * ss, size[1] * ss
    c = ground(W, H, [(0.15, 0.46, 0.46, COOL, 0.42), (0.60, 0.40, 0.46, COOL, 0.68),
                      (0.94, 0.44, 0.44, WARM, 0.88)])
    slab_ext(c, master, height=0.88, cx=0.855, bottom=1.02)
    contact_shadow(c, roz, height=0.96, cx=0.590, bottom=1.05, strength=0.5)
    put(c, roz, height=0.96, cx=0.590, bottom=1.05)
    _logo(c, logo, 0.400, 0.220, 0.455)
    mark_clear(W, H, 0.88, 0.855, 1.02, roz, 0.96, 0.590, 1.05, name)
    return _out(c, name, size)


def small_capsule(name="small_capsule_462x174", size=(462, 174), ss=4,
                  logo_w=0.780, glow=0.62):
    """2.66:1, and it auto-generates 184x69 and 120x45. Logo only, centred.

    An earlier version kept Buckles at the right, dimmed to 20%, so the frame would not
    be a bare gradient. That was the wrong trade and Jamie called it: at this size he
    does not resolve into a person, he resolves into a smudge -- and the cost of him
    being there is that the lockup has to sit at 40% width to make room. So the one
    element that must read is pushed off centre to accommodate an element that does not
    read at all. Nothing in, everything out.

    Logo only, dead centre. The brand still gets carried by the ground: the KV's cool
    field and warm field, balanced either side of a dark centre channel so the frame is
    symmetrical and the lockup sits in the middle of its own composition rather than
    beside a ghost. At 120x45 only the wordmark's silhouette survives anyway, which is
    the whole argument for giving it every pixel it can have.
    """
    roz, master, logo = _stock()
    W, H = size[0] * ss, size[1] * ss
    c = ground(W, H, [(0.10, 0.50, 0.46, COOL, glow),
                      (0.90, 0.50, 0.46, WARM, glow * 0.92)])
    _logo(c, logo, logo_w, 0.500, 0.500)
    return _out(c, name, size)


def vertical_capsule(name="vertical_capsule_748x896", size=(748, 896), ss=2,
                     fig=0.66, buc=0.86, roz_x=0.385, buc_x=0.700,
                     logo_w=0.82, logo_y=0.155):
    """Portrait. A crop cannot make this -- the master is 1.79:1 -- so the two are
    re-staged closed up, Rozier in front, dropped low enough to leave the top third as
    dark ground for the lockup.

    Buckles is sized off Rozier (`buc`) rather than set independently, because the
    binding constraint here is his NUMERAL, not his head: at the width these frames give,
    a Buckles scaled to look right runs his 43 through the right edge, and a numeral
    sliced to a bare "3" reads as a production mistake in a way a cropped shoulder never
    does. Smaller and slightly further back keeps it whole and reads as depth.

    The lockup goes at the top, not the bottom: at the bottom it lands on jersey and needs
    a plate behind it to stay legible, and a plate is exactly the kind of added furniture
    Steam's text rule is written to catch."""
    roz, master, logo = _stock()
    W, H = size[0] * ss, size[1] * ss
    c = ground(W, H, [(0.30, 0.62, 0.52, COOL, 0.78), (0.80, 0.60, 0.54, WARM, 0.80)])
    slab_ext(c, master, height=fig * buc, cx=buc_x, bottom=1.00, feather=0.30)
    contact_shadow(c, roz, height=fig, cx=roz_x, bottom=1.03, strength=0.5)
    put(c, roz, height=fig, cx=roz_x, bottom=1.03)
    _logo(c, logo, logo_w, 0.500, logo_y)

    mark_clear(W, H, fig * buc, buc_x, 1.00, roz, fig, roz_x, 1.03, name)
    return _out(c, name, size)


def library_hero(name="library_hero_3840x1240", size=(3840, 1240)):
    """NO TEXT OF ANY KIND -- Steam's rule, and it draws the library logo over this at
    runtime. So the two are pushed apart to open a dark channel through the centre for
    that logo to land in, which is also what the current hero does with its ball and
    clipboard. Built at 1x: the figures sit at ~85% of a 1240px frame, so the master is
    being reduced here, not upscaled.

    The centre 860x380 is the zone Steam never crops. Keeping the figures just outside it
    is deliberate -- content there would compete with the overlaid logo -- and both still
    survive a crop far narrower than the client ever applies."""
    roz, master, logo = _stock()
    W, H = size
    c = ground(W, H, [(0.26, 0.46, 0.40, COOL, 0.80), (0.50, 0.45, 0.30, COOL, 0.16),
                      (0.80, 0.46, 0.40, WARM, 0.86)])
    slab_ext(c, master, height=0.80, cx=0.775, bottom=1.03, feather=0.26)
    contact_shadow(c, roz, height=0.88, cx=0.248, bottom=1.06, strength=0.45)
    put(c, roz, height=0.88, cx=0.248, bottom=1.06)
    mark_clear(W, H, 0.80, 0.775, 1.03, roz, 0.88, 0.248, 1.06, name)
    return _out(c, name, size)


def page_background(name="page_background_1438x810", size=(1438, 810), ss=2):
    """Optional, no logo, and Steam dims and blurs it hard behind the page content. So it
    is the KV opened out and taken down -- atmosphere, not a picture. Anything with detail
    here fights the store page it sits behind."""
    roz, master, logo = _stock()
    W, H = size[0] * ss, size[1] * ss
    c = ground(W, H, [(0.20, 0.44, 0.46, COOL, 0.62), (0.86, 0.46, 0.46, WARM, 0.62)])
    slab_ext(c, master, height=0.80, cx=0.845, bottom=1.04, feather=0.34, dim=1.0)
    contact_shadow(c, roz, height=0.88, cx=0.205, bottom=1.08, strength=0.35)
    put(c, roz, height=0.88, cx=0.205, bottom=1.08)
    c *= 0.66                                   # it is a background, not an asset
    return _out(c, name, size)


SPEC = [("main_capsule_1232x706",    (1232, 706)),
        ("header_capsule_920x430",   (920, 430)),
        ("small_capsule_462x174",    (462, 174)),
        ("vertical_capsule_748x896", (748, 896)),
        ("library_capsule_600x900",  (600, 900)),
        ("library_header_920x430",   (920, 430)),
        ("library_hero_3840x1240",   (3840, 1240)),
        ("page_background_1438x810", (1438, 810))]


def build_all():
    main_capsule("main_capsule_1232x706", grid=False)
    header_capsule("header_capsule_920x430")
    small_capsule("small_capsule_462x174")
    vertical_capsule("vertical_capsule_748x896", (748, 896),
                     fig=0.58, buc=0.84, roz_x=0.285, buc_x=0.770,
                     logo_w=0.82, logo_y=0.225)
    # 600x900 is taller again (0.67:1 against 0.83:1), so the figures come down and the
    # lockup rides higher, rather than the whole layout simply being stretched.
    vertical_capsule("library_capsule_600x900", (600, 900),
                     fig=0.48, buc=0.84, roz_x=0.275, buc_x=0.760,
                     logo_w=0.86, logo_y=0.205)
    header_capsule("library_header_920x430")      # same frame, same job
    library_hero("library_hero_3840x1240")
    page_background("page_background_1438x810")


def verify():
    """Everything in Steam's rejection list that can be checked mechanically."""
    print("\n  spec check")
    ok = True
    for name, size in SPEC:
        p = SOUT / f"{name}.png"
        if not p.exists():
            print(f"    MISSING  {name}"); ok = False; continue
        im = Image.open(p)
        good = im.size == size
        ok &= good
        print(f"    {'ok ' if good else 'BAD'} {name:28s} {im.size[0]:>5} x {im.size[1]}"
              + ("" if good else f"   expected {size[0]} x {size[1]}"))
    # The hero's "no text" rule cannot be checked from pixels -- its peak luminance is
    # 255 either way, because Rozier's jersey carries a specular that bright. So check it
    # where it is actually decidable: the builder must not call the lockup or the type
    # setter at all. This is a real guard against a later edit quietly adding one.
    import inspect
    src = inspect.getsource(library_hero)
    clean = ("_logo(" not in src) and ("text(" not in src)
    ok &= clean
    print(f"    {'ok ' if clean else 'BAD'} library hero composites no logo and no type")
    return ok


if __name__ == "__main__":
    import sys
    if "--ab" in sys.argv:
        a = main_capsule("main_capsule_A_pureKV", grid=False)
        b = main_capsule("main_capsule_B_grid", grid=True)
        cur = Image.open("/mnt/user-data/uploads/Desktop/Steam Assets/"
                         "03 main-capsule 1232x706.png").convert("RGB")
        rows = [(cur, "CURRENT"), (a, "A   PURE KV"), (b, "B   KV + DATA GRID")]
        SW, SH = 1232, 706
        sheet = Image.new("RGB", (SW + 616 + 90, SH * 3 + 160), (18, 18, 22))
        d = ImageDraw.Draw(sheet)
        f = ImageFont.truetype(FONT, 34)
        for i, (im, lab) in enumerate(rows):
            y = 52 + i * (SH + 36)
            sheet.paste(im, (30, y))
            sheet.paste(im.resize((616, 353), Image.LANCZOS), (SW + 60, y))
            d.text((30, y - 40), lab, font=f, fill=(210, 214, 224))
            d.text((SW + 60, y - 40), "AS STEAM RENDERS IT", font=f, fill=(120, 124, 134))
        sheet.save(ROOT / "_steam_main_AB.png")
        print("  _steam_main_AB.png")
    else:
        build_all()
        verify()
