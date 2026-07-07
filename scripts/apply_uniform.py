#!/usr/bin/env python3
"""
Lock a team's jersey to exact colors + stamp the wordmark.

Takes a bust whose jersey has ALREADY been recolored to (approx) the team
color by a Nano Banana edit pass, and:
  1. Masks the jersey by hue (a colored jersey is trivial to isolate from skin
     and background — unlike a white tank).
  2. Recolors it to the EXACT team primary (body) and secondary (trim),
     preserving per-pixel fabric shading, so every player on the team is
     pixel-identical in color (removes generation drift).
  3. Stamps the wordmark (collegiate block font) in the secondary color.

Output feeds process_player_portraits.py (cutout + 3530x3412 framing).

    pip install pillow numpy scipy
    python3 scripts/apply_uniform.py \
        --in tmp/portrait-pilot/recolored --out tmp/portrait-pilot/uniformed \
        --primary 87b5e6 --secondary 1e2f5b --wordmark SKY

Colors are hex (with or without #). For scale, drive --primary/--secondary/
--wordmark per team from the team DB.
"""
import os
import re
import sys
import argparse

FONT_DEFAULT = "/mnt/skills/examples/canvas-design/canvas-fonts/BigShoulders-Bold.ttf"

# Jersey hue band to mask (degrees). Sky/navy are blue → ~190-260.
# For non-blue teams, pass --hue-lo/--hue-hi to match the edit color.
HUE_LO, HUE_HI = 185, 265
WORDMARK_Y_FRAC = 0.80   # vertical placement of wordmark (fraction of height)
WORDMARK_H_FRAC = 0.11   # font size as fraction of height


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hsv(arr):
    """arr float32 HxWx3 in 0..255 -> h(0..360), s(0..1), v(0..1)."""
    import numpy as np
    r, g, b = arr[..., 0]/255, arr[..., 1]/255, arr[..., 2]/255
    mx = arr.max(2)/255; mn = arr.min(2)/255; d = mx - mn
    h = np.zeros_like(mx)
    mask = d > 1e-6
    idx = (mx == r/1) & mask
    h[idx] = (60*((g[idx]-b[idx])/d[idx] % 6))
    idx = (mx == g/1) & mask
    h[idx] = (60*((b[idx]-r[idx])/d[idx] + 2))
    idx = (mx == b/1) & mask
    h[idx] = (60*((r[idx]-g[idx])/d[idx] + 4))
    s = np.where(mx > 0, d/np.where(mx == 0, 1, mx), 0)
    return h, s, mx


def recolor(img, primary, secondary):
    """Recolor the blue jersey to exact primary/secondary, keeping shading."""
    import numpy as np
    from scipy import ndimage
    from PIL import Image
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    h, s, v = rgb_to_hsv(arr)
    jersey = (h >= HUE_LO) & (h <= HUE_HI) & (s > 0.12)
    jersey = ndimage.binary_closing(jersey, iterations=3)
    jersey = ndimage.binary_opening(jersey, iterations=2)
    if jersey.sum() == 0:
        return img.convert("RGB"), 0
    # keep the largest jersey blob (drops stray blue speckles)
    lbl, n = ndimage.label(jersey)
    if n > 1:
        sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n+1))
        jersey = lbl == (1 + int(np.argmax(sizes)))
    # trim = darker jersey pixels; body = the rest
    trim = jersey & (v < 0.45)
    body = jersey & ~trim
    out = arr.copy()
    for mask, color in ((body, primary), (trim, secondary)):
        soft = ndimage.gaussian_filter(mask.astype(np.float32), 2.0)[..., None]
        # keep each pixel's brightness (folds), apply exact team hue
        tone = np.clip(v[..., None]*1.05, 0.15, 1.0)
        target = np.array(color, np.float32)[None, None, :] * tone
        out = out*(1-soft) + target*soft
    return Image.fromarray(np.clip(out, 0, 255).astype("uint8")), int(jersey.sum())


def stamp_wordmark(img, text, color, font_path):
    from PIL import ImageDraw, ImageFont
    W, H = img.size
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, int(H*WORDMARK_H_FRAC))
    tb = d.textbbox((0, 0), text, font=font)
    x = (W-(tb[2]-tb[0]))//2 - tb[0]
    y = int(H*WORDMARK_Y_FRAC)
    for ox, oy in [(-4, 0), (4, 0), (0, -4), (0, 4), (-3, -3), (3, 3), (-3, 3), (3, -3)]:
        d.text((x+ox, y+oy), text, font=font, fill=(255, 255, 255))
    d.text((x, y), text, font=font, fill=color)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="indir", required=True)
    ap.add_argument("--out", dest="outdir", required=True)
    ap.add_argument("--primary", required=True, help="jersey body hex e.g. 87b5e6")
    ap.add_argument("--secondary", required=True, help="trim/wordmark hex e.g. 1e2f5b")
    ap.add_argument("--wordmark", required=True)
    ap.add_argument("--font", default=FONT_DEFAULT)
    ap.add_argument("--hue-lo", type=float)
    ap.add_argument("--hue-hi", type=float)
    args = ap.parse_args()

    global HUE_LO, HUE_HI
    if args.hue_lo is not None:
        HUE_LO = args.hue_lo
    if args.hue_hi is not None:
        HUE_HI = args.hue_hi

    try:
        import PIL, numpy, scipy  # noqa: F401
    except ImportError:
        sys.exit("missing deps. Run:  pip install pillow numpy scipy")
    from PIL import Image

    primary, secondary = hex2rgb(args.primary), hex2rgb(args.secondary)
    os.makedirs(args.outdir, exist_ok=True)
    exts = (".png", ".jpg", ".jpeg", ".webp")
    files = [f for f in sorted(os.listdir(args.indir)) if f.lower().endswith(exts)]
    if not files:
        sys.exit(f"no images in {args.indir}")

    for f in files:
        img = Image.open(os.path.join(args.indir, f))
        colored, px = recolor(img, primary, secondary)
        colored = stamp_wordmark(colored, args.wordmark, secondary, args.font)
        out = os.path.join(args.outdir, os.path.splitext(f)[0]+".png")
        colored.save(out, "PNG")
        flag = "" if px > 5000 else "  [!] little/no jersey hue found — check --hue range"
        print(f"[ok] {f}  jersey_px={px}{flag}")
    print(f"\n[done] {len(files)} -> {args.outdir}")


if __name__ == "__main__":
    main()
