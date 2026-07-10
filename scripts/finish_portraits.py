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


def slug(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def detect_face(rgb, cv2, np):
    """(cx, cy, h) of the face, or None. Haar frontal; falls back to the alpha
    head-top if it can't find one."""
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    cc = cv2.CascadeClassifier(
        os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
    faces = cc.detectMultiScale(g, 1.1, 5, minSize=(120, 120))
    if len(faces):
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        return x + w / 2.0, y + h / 2.0, float(h)
    return None


def finish(in_path, out_path, face_frac=FACE_H_FRAC, cy_frac=FACE_CY_FRAC):
    import numpy as np
    import cv2
    from scipy import ndimage
    from PIL import Image

    im = Image.open(in_path).convert("RGBA")
    arr = np.asarray(im)
    rgb = arr[..., :3].copy()
    alpha = arr[..., 3]

    # --- locate the head ---
    face = detect_face(rgb, cv2, np)
    ys, xs = np.where(alpha > 20)
    if ys.size == 0:
        raise ValueError("empty image")
    if face is None:                                  # fallback: use alpha head-top
        top = ys.min()
        cx = (xs.min() + xs.max()) / 2.0
        head_h = (ys.max() - top) * 0.32              # approx face height
        fcx, fcy, fh = cx, top + head_h * 0.55, head_h
    else:
        fcx, fcy, fh = face

    scale = (face_frac * CANVAS_H) / fh

    # --- edge cleanup: erode + feather to remove the white halo ---
    a = (alpha > 20).astype(np.float32)
    a = ndimage.binary_erosion(a > 0.5, iterations=2).astype(np.float32)
    a = ndimage.gaussian_filter(a, 1.5)
    alpha = np.clip(a * 255, 0, 255).astype(np.uint8)

    src = Image.fromarray(np.dstack([rgb, alpha]), "RGBA")
    new_w, new_h = max(1, round(src.width * scale)), max(1, round(src.height * scale))
    src = src.resize((new_w, new_h), Image.LANCZOS)

    # place the face at its target spot on the canvas
    px = round(FACE_CX_FRAC * CANVAS_W - fcx * scale)
    py = round(cy_frac * CANVAS_H - fcy * scale)
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    canvas.alpha_composite(src, (px, py))
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
    ap.add_argument("--face-frac", type=float, default=FACE_H_FRAC,
                    help="face height / canvas height (bigger = tighter zoom)")
    ap.add_argument("--cy-frac", type=float, default=FACE_CY_FRAC,
                    help="vertical position of the face center")
    args = ap.parse_args()

    try:
        import cv2, numpy, scipy, PIL  # noqa: F401
    except ImportError:
        sys.exit("missing deps. Run:  pip install opencv-python-headless pillow numpy scipy")

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
    ok = miss = 0
    for r in sel:
        in_path = os.path.join(args.indir, f"{r['name']}.png")
        if not os.path.exists(in_path):
            miss += 1
            continue
        name = r["name"] if args.name_output else r["_id"]
        out_path = os.path.join(args.outdir, f"{name}.png")
        try:
            finish(in_path, out_path, args.face_frac, args.cy_frac)
            print(f"[ok] {r['name']} -> {name}.png")
            ok += 1
        except Exception as e:
            print(f"[fail] {r['name']}: {type(e).__name__}: {str(e)[:150]}")
    print(f"\n[done] {ok} finished, {miss} missing -> {args.outdir}  ({CANVAS_W}x{CANVAS_H})")


if __name__ == "__main__":
    main()
