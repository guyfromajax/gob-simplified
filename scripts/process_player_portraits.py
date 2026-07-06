#!/usr/bin/env python3
"""
Turn raw AI-generated busts into upload-ready player masters.

Pipeline per image:
  1. Remove background  -> transparent RGBA (rembg, portrait model)
  2. Normalize framing  -> scale/center to match Conf1 (head near top,
                            shoulders bleeding off the bottom edge)
  3. Output             -> 3530 x 3412 RGBA PNG, named <uuid>.png

Matches the master spec in the brief:
  Format PNG RGBA · Dimensions 3530x3412 · R2 key players/master/<uuid>.png

Setup (run where you process images — your machine or a Cursor agent):
    pip install "rembg[cpu]" pillow

Usage:
    # inputs already named <uuid>.png:
    python3 scripts/process_player_portraits.py \
        --in tmp/portrait-pilot/raw --out assets_staging/players

    # inputs named by player (stanley.png ...) + a name->uuid map:
    python3 scripts/process_player_portraits.py \
        --in tmp/portrait-pilot/raw --out assets_staging/players \
        --map scripts/players_archetypes.csv --map-name-col name --map-id-col _id

The map lets you name files "Stanley Keith.png" / "stanley_keith.png" and have
them come out "86b911a5-...png". Basenames are matched loosely (case/space/
underscore-insensitive). Without --map, the input basename is kept.
"""
import os
import re
import csv
import sys
import argparse

CANVAS_W, CANVAS_H = 3530, 3412

# Framing (fractions of canvas height). Tune after eyeballing output vs Conf1.
TOP_MARGIN_FRAC = 0.05        # headroom above the top of the head
SUBJECT_HEIGHT_FRAC = 1.02    # subject spans this * canvas height (>1 => shoulders bleed off bottom)

# rembg models to try, best-for-people first.
REMBG_MODELS = ["birefnet-portrait", "u2net_human_seg", "u2net"]


def slug(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_map(path, name_col, id_col):
    m = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get(name_col) and row.get(id_col):
                m[slug(row[name_col])] = row[id_col]
    return m


def get_session():
    from rembg import new_session
    for name in REMBG_MODELS:
        try:
            s = new_session(name)
            print(f"[rembg] using model '{name}'")
            return s
        except Exception:
            continue
    print("[rembg] falling back to default session")
    return None


def normalize_framing(img):
    """Scale + center the cut-out subject onto the 3530x3412 canvas."""
    from PIL import Image
    bbox = img.getbbox()                       # bounds of non-transparent pixels
    if not bbox:
        raise ValueError("empty image after background removal")
    subj = img.crop(bbox)
    bw, bh = subj.size

    scale = (SUBJECT_HEIGHT_FRAC * CANVAS_H) / bh
    new_w, new_h = max(1, round(bw * scale)), max(1, round(bh * scale))
    subj = subj.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    x = (CANVAS_W - new_w) // 2                 # center horizontally
    y = round(TOP_MARGIN_FRAC * CANVAS_H)       # anchor top-of-head near top
    canvas.alpha_composite(subj, (x, y))
    return canvas


def process(in_path, out_path, session, alpha_matting):
    from PIL import Image
    from rembg import remove
    src = Image.open(in_path).convert("RGBA")
    kw = {}
    if session:
        kw["session"] = session
    if alpha_matting:
        kw.update(alpha_matting=True, alpha_matting_foreground_threshold=270,
                  alpha_matting_background_threshold=10, alpha_matting_erode_size=11)
    cut = remove(src, **kw)                      # -> RGBA, transparent bg
    out = normalize_framing(cut)
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
    ap.add_argument("--alpha-matting", action="store_true",
                    help="cleaner hair edges, slower")
    args = ap.parse_args()

    try:
        import PIL, rembg  # noqa: F401
    except ImportError:
        sys.exit('missing deps. Run:  pip install "rembg[cpu]" pillow')

    name_map = load_map(args.mapfile, args.map_name_col, args.map_id_col) \
        if args.mapfile else None
    os.makedirs(args.outdir, exist_ok=True)
    session = get_session()

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
            process(os.path.join(args.indir, f), out_path, session,
                    args.alpha_matting)
            print(f"[ok] {f} -> {out_name}")
            ok += 1
        except Exception as e:
            print(f"[fail] {f}: {e}")
    print(f"\n[done] {ok}/{len(files)} -> {args.outdir}  ({CANVAS_W}x{CANVAS_H} RGBA)")


if __name__ == "__main__":
    main()
