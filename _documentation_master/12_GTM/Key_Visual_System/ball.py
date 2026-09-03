#!/usr/bin/env python3
"""Give the basketball real leather.

The ball came out of the generator as a smooth painted sphere with seams drawn on it. What
makes a real basketball read as one, in Jamie's reference photo and in the app icon both, is
not colour -- it is that the surface is covered in thousands of tiny raised pebbles, each
catching the key light on one side and shadowed on the other, and that the seams are
recessed channels rather than lines.

So this does not paint texture on. It builds a height field over the ball, converts it to a
normal perturbation, and relights it with the scene's own key. Pebbles then brighten on
their lit side and darken on the other by exactly as much as their slope warrants, and the
effect falls off toward the silhouette on its own because the surface turns away there.

Everything is expressed as a fraction of image width, so it runs identically on the 1x
image and the 2x master.
"""
import pathlib, os
from PIL import Image, ImageFilter
import numpy as np
from scipy import ndimage

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "final"; OUT.mkdir(exist_ok=True)

# circle fitted to the ball in the locked image, as fractions of width
BALL = dict(cx=770 / 2752, cy=942 / 1536, r=211 / 2752)

# The scene keys both players from the outside edge of frame; Rozier's is upper LEFT.
LIGHT = np.array([-0.52, -0.58, 0.63], dtype=np.float32)
LIGHT /= np.linalg.norm(LIGHT)


def value_noise(shape, cell, rng):
    """Smooth random field with features about `cell` px across."""
    h, w = shape
    small = rng.random((max(2, int(h / cell) + 2), max(2, int(w / cell) + 2))).astype(np.float32)
    return np.array(Image.fromarray((small * 255).astype(np.uint8))
                    .resize((w, h), Image.BICUBIC)).astype(np.float32) / 255.0


def pebble_field(shape, cell, rng, radius=0.40, jitter=0.34):
    """Discrete round bumps on a jittered lattice -- an actual pebble pattern.

    Filtered noise was the wrong model. Blurred noise gives soft irregular blobs, which
    read as felt or towelling; a basketball's grain is thousands of SEPARATE round domes
    with clean gaps between them. So each lattice cell gets one dome, offset randomly so
    the grid never shows, and the height is a smooth cap rather than a cone.
    """
    h, w = shape
    ny, nx = int(h / cell) + 2, int(w / cell) + 2
    jx = (rng.random((ny, nx)).astype(np.float32) - 0.5) * 2 * jitter
    jy = (rng.random((ny, nx)).astype(np.float32) - 0.5) * 2 * jitter

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32) / cell
    i, j = np.floor(xx).astype(np.int32), np.floor(yy).astype(np.int32)
    np.clip(i, 0, nx - 1, out=i); np.clip(j, 0, ny - 1, out=j)

    best = np.zeros((h, w), np.float32)
    for di in (-1, 0, 1):                       # neighbours too, or seams show at cell walls
        for dj in (-1, 0, 1):
            ii = np.clip(i + di, 0, nx - 1); jj = np.clip(j + dj, 0, ny - 1)
            cxx = ii + 0.5 + jx[jj, ii]
            cyy = jj + 0.5 + jy[jj, ii]
            d2 = (xx - cxx) ** 2 + (yy - cyy) ** 2
            cap = np.clip(1.0 - d2 / (radius ** 2), 0, 1) ** 0.55
            np.maximum(best, cap, out=best)
    return best - best.mean()


def texture_ball(im, cx, cy, r, pebble_px=4.4, bump=0.17, seam=0.16,
                 limb=0.10, contact=0.30, seed=11):
    """Relight the ball with a pebbled surface, deepen its seams, and seat it on the chest."""
    a = np.array(im).astype(np.float32)
    H, W, _ = a.shape
    rng = np.random.default_rng(seed)

    y0, y1 = max(0, int(cy - r) - 8), min(H, int(cy + r) + 8)
    x0, x1 = max(0, int(cx - r) - 8), min(W, int(cx + r) + 8)
    sub = a[y0:y1, x0:x1]
    h, w, _ = sub.shape

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx - (cx - x0)) / r
    ny = (yy - (cy - y0)) / r
    rr2 = nx ** 2 + ny ** 2
    inside = rr2 <= 1.0
    nz = np.sqrt(np.clip(1.0 - rr2, 0, 1))

    R, G, B = sub[..., 0], sub[..., 1], sub[..., 2]
    # Fingers cross the ball. Measured inside the circle, B/R is cleanly bimodal: leather
    # below 0.30, skin between 0.40 and 0.55. My first pass used 0.60, which classified the
    # fingers as leather and pebbled his hands.
    skin = B > 0.34 * R
    ball = inside & ~ndimage.binary_dilation(skin, np.ones((3, 3)), iterations=2)
    ball = ndimage.binary_opening(ball, np.ones((5, 5)))
    soft = ndimage.gaussian_filter(ball.astype(np.float32), 1.4)

    # ---- strip the dark keyline off the ball's silhouette --------------------------
    # The generated ball carries a hard dark outline hugging its lower edge -- inherited
    # from the outline on the vector ball in my plate -- while the top edge has none. The
    # top is the authentic one: a lit sphere has no keyline.
    #
    # First attempt pulled leather radially outward across a wide band. That smears
    # TANGENTIAL features, and the seam curving round the bottom runs tangentially, so it
    # erased it and left a dark streak behind.
    #
    # Separate them by WIDTH instead. The keyline is a few pixels thick; the seams are
    # three times that. A morphological opening with a disk wider than the keyline keeps
    # the seams and drops the rim, so the rim is what the opening removes.
    rr = np.sqrt(rr2)
    lum0 = sub.mean(2)
    lev = np.median(lum0[ball]) if ball.any() else lum0.mean()
    dark = (lev - lum0 > 30) & inside & (~skin)

    rad = max(2, int(round(r * 0.030)))                 # ~6px at 2752, half that at 1376
    disk = np.hypot(*np.mgrid[-rad:rad + 1, -rad:rad + 1]) <= rad
    seams_thick = ndimage.binary_opening(dark, disk)    # survives = real seam
    not_seam = dark & ~ndimage.binary_dilation(seams_thick, np.ones((3, 3)), iterations=2)
    rim = not_seam & (rr > 0.86)

    # Isolated dark specks away from the edge -- fragments of the same keyline, and a
    # couple of stray marks the generator left on the leather. Only small blobs qualify,
    # so nothing that is actually part of a seam can be caught by this.
    lab_s, n_s = ndimage.label(not_seam & (rr <= 0.86))
    if n_s:
        area = ndimage.sum(np.ones_like(lab_s), lab_s, range(1, n_s + 1))
        small = np.isin(lab_s, [i + 1 for i, a in enumerate(area) if a < (r * 0.10) ** 2])
        rim |= small & (lab_s > 0)

    if rim.any():
        # replace only those pixels, sampling from just inside along the same ray
        scale = np.where(rr > 1e-6, np.clip(rr - 0.055, 0.05, 1) / np.maximum(rr, 1e-6), 1.0)
        srcx = np.clip((nx * scale) * r + (cx - x0), 0, w - 1)
        srcy = np.clip((ny * scale) * r + (cy - y0), 0, h - 1)
        pulled = np.stack([ndimage.map_coordinates(sub[..., c], [srcy, srcx], order=1)
                           for c in range(3)], -1)
        # Rim pixels take a radial pull; interior specks take a local median, because a
        # radial pull far from the edge would drag a seam's colour across the leather.
        med = np.stack([ndimage.median_filter(sub[..., c], size=max(3, int(r * 0.06)))
                        for c in range(3)], -1)
        edge_w = ndimage.gaussian_filter((rim & (rr > 0.86)).astype(np.float32), 1.2)[..., None]
        spec_w = ndimage.gaussian_filter((rim & (rr <= 0.86)).astype(np.float32), 1.2)[..., None]
        sub[:] = sub * (1 - edge_w - spec_w) + pulled * edge_w + med * spec_w
        R, G, B = sub[..., 0], sub[..., 1], sub[..., 2]
        print(f"  keyline removed: {int(rim.sum())}px  (seams kept: {int(seams_thick.sum())}px)")

    # ---- pebble height field -------------------------------------------------------
    # Discrete domes for the grain, plus a slow swell so it is not mechanically even.
    height = pebble_field((h, w), pebble_px, rng)
    height = height + (value_noise((h, w), pebble_px * 14, rng) - 0.5) * 0.30

    # Slopes -> perturbed normal -> relight.
    # NOT divided by the foreshortening. I tried that, meaning to compress the pebbles
    # toward the silhouette, but dividing the SLOPE by nz amplifies the perturbation by up
    # to 8x where the surface turns away -- which threw a band of hard dark speckles down
    # the ball's left edge that read as dirt. The geometry already handles falloff: a
    # perturbed normal near the limb points away from the key on its own.
    gy, gx = np.gradient(height)
    n = np.stack([nx + gx * bump, ny + gy * bump, nz], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-6
    base = np.stack([nx, ny, nz], -1)
    base /= np.linalg.norm(base, axis=-1, keepdims=True) + 1e-6

    delta = (n @ LIGHT) - (base @ LIGHT)
    shade = 1.0 + delta * 1.25     # 2.2 gave an orange golf ball; 1.1 with noise gave felt

    # ---- seams: they are already drawn, just not recessed --------------------------
    lum = sub.mean(2)
    dark = np.clip((np.median(lum[ball]) - lum) / 60.0, 0, 1) if ball.any() else np.zeros_like(lum)
    seams = ndimage.gaussian_filter(dark, 1.2) * ball
    # darken the groove, and put a thin lit lip on its upper-left edge
    lip = np.clip(-ndimage.correlate(seams, np.array([[-1, -1, 0], [-1, 0, 1], [0, 1, 1]],
                                                     dtype=np.float32)), 0, 1)
    shade *= (1.0 - seams * seam)
    shade += lip * seam * 0.55

    # ---- limb darkening: real balls fall off hard at the silhouette ----------------
    shade *= 1.0 - limb * (1.0 - nz ** 0.7)

    # Normalise so the treatment changes the SURFACE, not the exposure. Without this the
    # pebble's lit sides outnumber its shadowed ones and the whole ball drifts brighter.
    if ball.any():
        shade[ball] /= max(shade[ball].mean(), 1e-6)
    shade = np.where(ball, shade, 1.0)
    shade = ndimage.gaussian_filter(shade, 0.5)
    shade = 1.0 + (shade - 1.0) * soft
    sub[:] = np.clip(sub * shade[..., None], 0, 255)

    # ---- contact shadow: the ball is resting against his chest ---------------------
    # An ambient-occlusion ring just outside the ball, strongest below where it meets the
    # jersey and absent at the top where the gap is open.
    ring = np.clip((np.sqrt(rr2) - 1.0) / 0.16, 0, 1)
    ao = (1.0 - ring) * (np.sqrt(rr2) > 0.985)
    ao *= np.clip(ny + 0.35, 0, 1) ** 1.4                 # bottom-weighted
    ao = ndimage.gaussian_filter(ao, r * 0.05)
    jersey = (B > R) & ~inside                            # only darken cloth, never skin
    sub[:] = np.clip(sub * (1.0 - contact * ao * jersey)[..., None], 0, 255)

    a[y0:y1, x0:x1] = sub
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


if __name__ == "__main__":
    src = os.environ.get("SRC", "final/KV_marks_v3_blueline_2x.png")
    im = Image.open(ROOT / src).convert("RGB")
    W, H = im.size
    # pebble size scales with the image, so the grain looks identical at 1x and 2x
    out = texture_ball(im, BALL["cx"] * W, BALL["cy"] * H, BALL["r"] * W,
                       pebble_px=4.4 * W / 2752)
    name = pathlib.Path(src).stem + "_ball.png"
    out.save(OUT / name)

    r = BALL["r"] * W
    cx, cy = BALL["cx"] * W, BALL["cy"] * H
    box = (int(cx - r - 40), int(cy - r - 40), int(cx + r + 40), int(cy + r + 40))
    before = Image.open(ROOT / src).convert("RGB").crop(box)
    after = out.crop(box)
    cmp = Image.new("RGB", (before.width * 2 + 24, before.height), (24, 24, 28))
    cmp.paste(before, (0, 0)); cmp.paste(after, (before.width + 24, 0))
    cmp.save(OUT / "_ball_before_after.png")
    print(f"wrote {name}  {out.size}")
