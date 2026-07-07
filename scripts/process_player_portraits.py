#!/usr/bin/env python3
"""
Turn raw AI-generated busts into upload-ready player masters.

Pipeline per image:
  1. Segment the person   -> transparent RGBA (u2net human-seg via onnxruntime)
  2. Normalize framing    -> scale/center to match Conf1 (head near top,
                             shoulders bleeding off the bottom edge)
  3. Output               -> 3530 x 3412 RGBA PNG, named <uuid>.png

Uses onnxruntime directly (NOT rembg) so there is no numba/llvmlite build step
— installs cleanly on Python 3.13.

Setup (run where you process images — your machine or a Cursor agent):
    pip install onnxruntime pillow numpy

The human-segmentation model (~168 MB) auto-downloads on first run to
~/.cache/gob-portraits/. It keeps the person (white tank included) and removes
only the background — no holes, no neck-pockets.

Usage:
    python3 scripts/process_player_portraits.py \
        --in tmp/portrait-pilot/raw --out assets_staging/players \
        --map scripts/players_archetypes.csv --map-name-col name --map-id-col _id
"""
import os
import re
import csv
import sys
import argparse
import urllib.request

CANVAS_W, CANVAS_H = 3530, 3412

# Framing. Matched to Conf1: shoulders fill the FULL width (bleed off the
# sides), head near the top, upper chest at the bottom edge.
TOP_MARGIN_FRAC = 0.07        # headroom above the top of the head
WIDTH_FILL = 1.0              # subject width = this * canvas width (1.0 => shoulders span/bleed the frame)

# Human-segmentation model (keeps clothing, unlike generic bg removal).
MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx"
MODEL_PATH = os.path.expanduser("~/.cache/gob-portraits/u2net_human_seg.onnx")

_SESSION = None


def slug(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_map(path, name_col, id_col):
    m = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get(name_col) and row.get(id_col):
                m[slug(row[name_col])] = row[id_col]
    return m


def _get_session():
    global _SESSION
    if _SESSION is None:
        import onnxruntime as ort
        if not os.path.exists(MODEL_PATH):
            os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
            print(f"[model] downloading u2net_human_seg (~168 MB) to {MODEL_PATH} ...")
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        _SESSION = ort.InferenceSession(MODEL_PATH,
                                        providers=["CPUExecutionProvider"])
    return _SESSION


def segment_alpha(img):
    """Return a soft 0-255 alpha mask (PIL 'L') for the person in img."""
    import numpy as np
    from PIL import Image
    sess = _get_session()
    name = sess.get_inputs()[0].name

    # u2net preprocessing: 320x320, scale by max, normalize (ImageNet stats).
    im = np.array(img.convert("RGB").resize((320, 320), Image.LANCZOS)).astype(np.float32)
    mx = im.max() or 1.0
    im = im / mx
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    im = (im - mean) / std
    im = im.transpose(2, 0, 1)[None].astype(np.float32)   # 1,3,320,320

    pred = sess.run(None, {name: im})[0][0, 0]            # 320,320
    mi, ma = float(pred.min()), float(pred.max())
    pred = (pred - mi) / ((ma - mi) or 1.0)
    return Image.fromarray((pred * 255).astype("uint8")).resize(img.size, Image.LANCZOS)


def cutout(img):
    from PIL import Image
    rgba = img.convert("RGBA")
    rgba.putalpha(segment_alpha(img))
    return rgba


def normalize_framing(img):
    """Scale + center the cut-out subject onto the 3530x3412 canvas."""
    from PIL import Image
    bbox = img.getbbox()                       # bounds of non-transparent pixels
    if not bbox:
        raise ValueError("empty image after segmentation")
    subj = img.crop(bbox)
    bw, bh = subj.size

    scale = (WIDTH_FILL * CANVAS_W) / bw       # fill width -> shoulders span frame
    new_w, new_h = max(1, round(bw * scale)), max(1, round(bh * scale))
    subj = subj.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    x = (CANVAS_W - new_w) // 2                 # center horizontally
    y = round(TOP_MARGIN_FRAC * CANVAS_H)       # anchor top-of-head near top
    canvas.alpha_composite(subj, (x, y))
    return canvas


def process(in_path, out_path):
    from PIL import Image
    src = Image.open(in_path).convert("RGBA")
    out = normalize_framing(cutout(src))
    out.save(out_path, "PNG")


def resolve_name(basename, name_map):
    if not name_map:
        return basename
    uid = name_map.get(slug(basename))
    if not uid:
        print(f"[warn] no uuid mapping for '{basename}' — keeping original name")
        return basename
    return uid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="indir", required=True)
    ap.add_argument("--out", dest="outdir", required=True)
    ap.add_argument("--map", dest="mapfile")
    ap.add_argument("--map-name-col", default="name")
    ap.add_argument("--map-id-col", default="_id")
    args = ap.parse_args()

    try:
        import PIL, numpy, onnxruntime  # noqa: F401
    except ImportError:
        sys.exit("missing deps. Run:  pip install onnxruntime pillow numpy")

    name_map = load_map(args.mapfile, args.map_name_col, args.map_id_col) \
        if args.mapfile else None
    os.makedirs(args.outdir, exist_ok=True)

    exts = (".png", ".jpg", ".jpeg", ".webp")
    files = [f for f in sorted(os.listdir(args.indir))
             if f.lower().endswith(exts)]
    if not files:
        sys.exit(f"no images found in {args.indir}")

    ok = 0
    for f in files:
        base = os.path.splitext(f)[0]
        out_name = resolve_name(base, name_map) + ".png"
        out_path = os.path.join(args.outdir, out_name)
        try:
            process(os.path.join(args.indir, f), out_path)
            print(f"[ok] {f} -> {out_name}")
            ok += 1
        except Exception as e:
            print(f"[fail] {f}: {e}")
    print(f"\n[done] {ok}/{len(files)} -> {args.outdir}  ({CANVAS_W}x{CANVAS_H} RGBA)")


if __name__ == "__main__":
    main()
