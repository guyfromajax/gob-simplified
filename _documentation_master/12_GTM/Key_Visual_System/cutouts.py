#!/usr/bin/env python3
"""Cut the two figures out of the master so they can be re-staged.

The square and the trailer thumbnail both need the players moved relative to each other --
closer together, Rozier overlapping Buckles -- which a crop cannot do. That needs a matte.

Keying on colour is hopeless here: Rozier's jersey is the same navy as the ground behind
him, and both men have near-black hair against a near-black centre. So this uses a
DIFFERENCE MATTE instead. The background is a smooth separable gradient, and the master
still carries pure background along its top rows and both side columns, so a clean plate
can be reconstructed and subtracted. Anything that differs from the reconstruction by more
than a threshold is a figure.
"""
import pathlib
from PIL import Image, ImageFilter
import numpy as np
from scipy import ndimage

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "cutouts"; OUT.mkdir(exist_ok=True)
MASTER = ROOT / "master" / "GOB_KV_rivals_2752x1536.png"


def clean_plate(a):
    """Rebuild the background the figures are sitting on.

    Separable by construction -- it was generated as a horizontal colour ramp times a
    vertical falloff -- so the top rows give the colour across the frame and the side
    columns give the brightness down it.
    """
    H, W, _ = a.shape
    hprof = ndimage.gaussian_filter1d(a[:26].mean(0), W * 0.01, axis=0)      # (W,3)
    edge = np.concatenate([a[:, :36], a[:, -36:]], axis=1).mean(1)           # (H,3)
    vmul = ndimage.gaussian_filter1d(edge.mean(1), H * 0.012)
    vmul = vmul / max(vmul[:26].mean(), 1e-6)
    return hprof[None, :, :] * vmul[:, None, None]


def matte(a, plate, lo=6.0, hi=17.0, tex=2.6):
    """Alpha from how far each pixel departs from the clean plate.

    Colour distance ALONE loses hair. Rozier's fade and Buckles' locs are near-black
    against a near-black centre, so the first pass flat-topped Rozier's hair and ate holes
    through Buckles' locs and brow. Hair is dark but it is not SMOOTH, and the background
    is: a local standard deviation separates them where colour cannot. The metric is the
    larger of the two signals, so either one alone is enough to hold a pixel.
    """
    d = np.linalg.norm(a - plate, axis=-1)
    lum = a.mean(2)
    var = ndimage.uniform_filter(lum ** 2, 5) - ndimage.uniform_filter(lum, 5) ** 2
    d = np.maximum(d, np.sqrt(np.clip(var, 0, None)) * tex)
    al = np.clip((d - lo) / (hi - lo), 0, 1)

    solid = al > 0.55
    solid = ndimage.binary_closing(solid, np.ones((17, 17)))
    solid = ndimage.binary_fill_holes(solid)
    solid = ndimage.binary_opening(solid, np.ones((5, 5)))
    # keep only substantial blobs -- the two men -- and drop sensor-level noise in the ground
    lab, n = ndimage.label(solid)
    if n:
        sizes = ndimage.sum(solid, lab, range(1, n + 1))
        keep = [i + 1 for i, s in enumerate(sizes) if s > 0.004 * a.shape[0] * a.shape[1]]
        solid = np.isin(lab, keep)
    # Keep the soft edge INSIDE the solid mask, not dilated past it. Dilating carried a
    # ring of the master's own dark background out with each figure, which showed as a pale
    # fringe once they were composited onto a brighter ground.
    al = np.minimum(al, solid.astype(np.float32))
    al = ndimage.gaussian_filter(al, 1.0)
    return al, solid


def split(solid, W):
    """Separate the two figures. They never touch, so a vertical gap in the mask is the cut."""
    cols = solid.any(0)
    runs, s = [], None
    for x, v in enumerate(cols):
        if v and s is None:
            s = x
        if not v and s is not None:
            runs.append((s, x)); s = None
    if s is not None:
        runs.append((s, W))
    runs.sort(key=lambda r: r[1] - r[0], reverse=True)
    return sorted(runs[:2])


if __name__ == "__main__":
    m = Image.open(MASTER).convert("RGB")
    a = np.array(m).astype(np.float32)
    H, W, _ = a.shape
    plate = clean_plate(a)

    # how good is the reconstruction where we KNOW there is only background?
    for name, sl in (("top rows", (slice(0, 40), slice(None))),
                     ("left cols", (slice(None), slice(0, 40))),
                     ("right cols", (slice(None), slice(W - 40, W)))):
        err = np.abs(a[sl] - plate[sl]).mean()
        print(f"clean-plate error over {name:11s}: {err:5.2f} levels")

    al, solid = matte(a, plate)
    print(f"matte covers {100*(al>0.5).mean():.1f}% of the frame")

    spans = split(solid, W)
    print("figure spans:", spans)

    # Despill by UNPREMULTIPLY, not by borrowing a neighbour's colour.
    #
    # Every edge pixel is a blend of the figure and the ground it was shot against:
    #
    #     observed = F*alpha + plate*(1 - alpha)
    #
    # and we have the plate, so F can simply be solved for. That is exact, and it is local:
    # each pixel recovers its OWN colour rather than being handed one from somewhere else.
    #
    # Two earlier versions borrowed instead, and each failed in the opposite direction. The
    # first pulled from the nearest opaque pixel and left a black rim, because near the
    # silhouette the nearest opaque pixel is often contaminated too. The second pulled from
    # 7px in, which reached past the contamination and straight into whatever was brightest
    # nearby -- along Rozier's shoulder that is his white jersey trim, so it painted a white
    # halo from below his ear down to his elbow, and a second one down his other tricep.
    # Borrowing cannot win: reach too little and it copies the background, reach too far and
    # it copies the wrong material. Solving needs no reach at all.
    #
    # Below alpha 0.12 the division is unstable (dividing a near-zero blend by a near-zero
    # weight amplifies noise), and those pixels contribute almost nothing to any composite,
    # so they take the nearest opaque colour from close by instead.
    A = al[..., None]
    solved = np.where(A > 0.12, (a - plate * (1 - A)) / np.maximum(A, 1e-3), a)

    core = ndimage.binary_erosion(solid, np.ones((3, 3)), iterations=3)
    _, idx = ndimage.distance_transform_edt(~core, return_indices=True)
    faint = (al <= 0.12)[..., None]
    rgb = np.clip(np.where(faint, a[idx[0], idx[1]], solved), 0, 255)

    band = al > 0.02
    print(f"despill: solved {int(((al > 0.12)).sum())} edge px, "
          f"pulled {int((al[band] <= 0.12).sum())} faint px")

    rgba = np.dstack([rgb, al * 255]).astype(np.uint8)
    full = Image.fromarray(rgba, "RGBA")
    for tag, (x0, x1) in zip(("rozier", "buckles"), spans):
        pad = 12
        sub = full.crop((max(0, x0 - pad), 0, min(W, x1 + pad), H))
        arr = np.array(sub)
        ys = np.where(arr[..., 3].max(1) > 8)[0]
        sub = sub.crop((0, max(0, ys.min() - pad), sub.width, min(H, ys.max() + pad)))
        sub.save(OUT / f"{tag}.png")
        print(f"  {tag}: {sub.size}")

    # visual check on mid-grey
    chk = Image.new("RGB", (W // 2, H // 2), (120, 124, 132))
    chk.paste(full.resize((W // 2, H // 2), Image.LANCZOS),
              (0, 0), full.resize((W // 2, H // 2), Image.LANCZOS))
    chk.save(OUT / "_matte_check.png")
