#!/usr/bin/env python3
"""
Finish uniformed busts into upload-ready masters (stage 3 — final).

Input busts are already cut out (transparent RGBA from the uniform stage). This
stage:
  1. FACE-ANCHORS the framing (detect the face, place the head near the top with
     a consistent eye-line, scale to a consistent face size so all portraits sit
     the same in the frame; build still reads via shoulder-to-head width).
  2. Cleans the alpha edge (erode + feather) to kill any white halo.
  3. Outputs 3530 x 3412 RGBA PNG named <uuid>.png.

    python3 scripts/finish_portraits.py --team "Durham"
    python3 scripts/finish_portraits.py --only "Ricky Chang"
    python3 scripts/finish_portraits.py --all

Inputs:  tmp/portrait-pilot/uniformed/<Name>.png  (RGBA, cut out)
         scripts/players_archetypes.csv            (name -> uuid, team)
Output:  assets_staging/players/<uuid>.png         (3530x3412 RGBA)
"""
import os
import re
import csv
import sys
import argparse

CANVAS_W, CANVAS_H = 3530, 3412

# Framing (fractions of canvas). Matched to Conf1: head near the top, face a
# consistent size, chest filling the bottom. Tunable.
FACE_H_FRAC = 0.26        # face height as a fraction of canvas height
FACE_CY_FRAC = 0.34       # vertical position of the face CENTER
FACE_CX_FRAC = 0.50       # horizontal position of the face center

# Wordmark: placed relative to the FINAL frame so only its top slice shows at
# the very bottom edge (rest reads as continuing below). Tunable knobs.
WORDMARK_VISIBLE_FRAC = 0.30   # fraction of letter HEIGHT visible above the edge
WORDMARK_WIDTH_FRAC = 0.72     # wordmark width as a fraction of jersey width
FONT = "FrontEnd/static/fonts/BebasNeuePro-Bold.otf"


def slug(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _lum(a):
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]


def _fit_font(draw, text, ImageFont, max_w, start=520):
    for size in range(start, 120, -12):
        f = ImageFont.truetype(FONT, size)
        b = draw.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= max_w:
            return f, b
    f = ImageFont.truetype(FONT, 130)
    return f, draw.textbbox((0, 0), text, font=f)


def stamp_wordmark(rgb, alpha, primary, secondary, wordmark, np, ndimage, Image,
                   ImageDraw, ImageFont, visible_frac, width_frac):
    """Stamp the team wordmark low in the FINAL frame so only its top slice
    shows at the exact bottom edge. Placement is relative to the canvas (same
    for every player). Clipped strictly to the jersey fabric; ink takes the
    fabric's fold shading and warps along its wrinkles."""
    H, W, _ = rgb.shape
    P = np.array(primary, np.float32)
    Sc = np.array(secondary, np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    # The jersey = the team PRIMARY. Detect it by hue direction relative to skin
    # instead of color distance (which grabs skin when team colors are warm).
    p_warm = primary[0] >= primary[2]           # is the primary red- or blue-leaning?
    if p_warm:                                   # warm primary (red/orange/gold)
        jersey = (r - b > 25) & (r > 70) & (alpha > 120)
    else:                                        # cool primary (navy/blue/teal/green)
        jersey = (b - r > 8) & (alpha > 120)
    jersey[:int(0.30 * H)] = False
    jersey = ndimage.binary_closing(jersey, iterations=4)
    lbl, n = ndimage.label(jersey)
    if n == 0:
        return rgb
    fabric = lbl == (1 + int(np.argmax(ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1)))))
    fabric = ndimage.binary_fill_holes(fabric)

    # Erase any prior INTERIOR wordmark (secondary-colored) back to the primary,
    # so this stamp is the only one. Trim near the edge is protected. No-op once
    # the uniform stage stops drawing wordmarks.
    interior = ndimage.binary_erosion(fabric, iterations=20)
    ds = np.sqrt(((rgb - Sc) ** 2).sum(2))
    oldmark = (ds < 70) & interior
    if oldmark.any():
        rgb[oldmark] = P

    ys, xs = np.where(fabric)
    low = ys > (ys.min() + 0.55 * (ys.max() - ys.min()))    # jersey width down low
    jx = xs[low] if low.any() else xs
    cx = int((jx.min() + jx.max()) / 2)
    jersey_w = int(jx.max() - jx.min())

    txt = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(txt)
    font, b = _fit_font(d, wordmark, ImageFont, int(jersey_w * width_frac))
    wm_h = b[3] - b[1]
    tx = cx - (b[2] - b[0]) // 2 - b[0]
    ty = int(CANVAS_H - visible_frac * wm_h) - b[1]         # top slice at the edge
    d.text((tx, ty), wordmark, fill=255, font=font)
    tmask = np.asarray(txt).astype(np.float32) / 255.0

    # fold-displacement: warp letters along the jersey's wrinkles
    heights = ndimage.gaussian_filter(_lum(rgb) * fabric, 9.0)
    gy, gx = np.gradient(heights)
    k = 2.2
    yy, xx = np.mgrid[0:H, 0:W]
    tmask = ndimage.map_coordinates(
        tmask, [np.clip(yy + k * gy, 0, H - 1), np.clip(xx + k * gx, 0, W - 1)],
        order=1, mode="constant")
    tmask = ndimage.gaussian_filter(tmask, 1.2)             # screen-print softness
    tm = (tmask * ndimage.binary_erosion(fabric, iterations=2))[..., None]

    # solid secondary ink with a subtle fold-shade (keeps it bold, not washed out)
    fold = np.clip(0.88 + (_lum(rgb) - 45.0) / 130.0, 0.72, 1.15)[..., None]
    ink = Sc[None, None, :] * fold
    out = rgb * (1 - 0.96 * tm) + ink * (0.96 * tm)
    return np.clip(out, 0, 255)


def finish(in_path, out_path, team=None, visible_frac=WORDMARK_VISIBLE_FRAC,
           width_frac=WORDMARK_WIDTH_FRAC):
    """Preserve the input's (already-consistent) framing: uniformly scale it to
    fill the canvas width, top-align (head near top), clean the alpha edge, then
    stamp the team wordmark low so only its top slice shows at the bottom edge.
    Every image gets the identical transform + placement -> consistent."""
    import numpy as np
    from scipy import ndimage
    from PIL import Image, ImageDraw, ImageFont

    im = Image.open(in_path).convert("RGBA")
    arr = np.asarray(im)
    rgb = arr[..., :3].copy()
    alpha = arr[..., 3]
    if (alpha > 20).sum() == 0:
        raise ValueError("empty image")

    # edge cleanup: erode + feather to kill the white halo
    a = ndimage.binary_erosion(alpha > 20, iterations=2).astype(np.float32)
    a = ndimage.gaussian_filter(a, 1.5)
    alpha = np.clip(a * 255, 0, 255).astype(np.uint8)

    src = Image.fromarray(np.dstack([rgb, alpha]), "RGBA")
    scale = CANVAS_W / src.width                        # fill width uniformly
    new_h = max(1, round(src.height * scale))
    src = src.resize((CANVAS_W, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    canvas.alpha_composite(src, (0, 0))                 # top-aligned (head near top)

    if team and team[1]:                                # (wordmark, primary, secondary)
        ca = np.asarray(canvas)
        rgb2 = ca[..., :3].astype(np.float32).copy()
        al2 = ca[..., 3]
        rgb2 = stamp_wordmark(rgb2, al2, team[1], team[2], team[0], np, ndimage,
                              Image, ImageDraw, ImageFont, visible_frac, width_frac)
        canvas = Image.fromarray(
            np.dstack([rgb2, al2]).astype("uint8"), "RGBA")
    canvas.save(out_path, "PNG")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--only")
    g.add_argument("--team")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--map", default="scripts/players_archetypes.csv")
    ap.add_argument("--in", dest="indir", default="tmp/portrait-pilot/uniformed")
    ap.add_argument("--out", dest="outdir", default="assets_staging/players")
    ap.add_argument("--name-output", action="store_true",
                    help="name outputs by player name instead of uuid (QC)")
    ap.add_argument("--visible-frac", type=float, default=WORDMARK_VISIBLE_FRAC,
                    help="fraction of wordmark letter height shown above the edge")
    ap.add_argument("--width-frac", type=float, default=WORDMARK_WIDTH_FRAC,
                    help="wordmark width as a fraction of jersey width")
    args = ap.parse_args()

    try:
        import numpy, scipy, PIL  # noqa: F401
    except ImportError:
        sys.exit("missing deps. Run:  pip install pillow numpy scipy")
    from apply_team_uniforms import team_info, hex2rgb

    rows = list(csv.DictReader(open(args.map)))
    if args.only:
        sel = [r for r in rows if slug(r["name"]) == slug(args.only)]
    elif args.team:
        sel = [r for r in rows if slug(r.get("team", "")) == slug(args.team)]
    else:
        sel = rows
    if not sel:
        sys.exit("no matching players")

    os.makedirs(args.outdir, exist_ok=True)
    team_cache = {}
    ok = miss = 0
    for r in sel:
        in_path = os.path.join(args.indir, f"{r['name']}.png")
        if not os.path.exists(in_path):
            miss += 1
            continue
        tname = r.get("team")
        if tname not in team_cache:
            mascot, tid, prim, sec = team_info(tname)
            team_cache[tname] = ((mascot or tname).upper(), hex2rgb(prim), hex2rgb(sec)) \
                if prim else None
        name = r["name"] if args.name_output else r["_id"]
        out_path = os.path.join(args.outdir, f"{name}.png")
        try:
            finish(in_path, out_path, team_cache[tname], args.visible_frac, args.width_frac)
            print(f"[ok] {r['name']} -> {name}.png")
            ok += 1
        except Exception as e:
            print(f"[fail] {r['name']}: {type(e).__name__}: {str(e)[:150]}")
    print(f"\n[done] {ok} finished, {miss} missing -> {args.outdir}  ({CANVAS_W}x{CANVAS_H})")


if __name__ == "__main__":
    main()
