#!/usr/bin/env python3
"""
Recruit QC proof sheets — paginated contact sheets of a set's kit busts.

Tiles the WHITE kit busts (assets_staging/recruits/kit/<id>.png) so you can
eyeball generation quality across a whole set: missing limbs, off skin tints,
bad frames, the NB corner sparkle, etc. Each tile is labeled with the recruit's
name + frame/definition/race (from the set + manifest) so build/face mismatches
jump out. The uniform recolor is deterministic and separately proven, so QC is
on the white bust, not the recolored master.

300 recruits don't fit one readable page, so this PAGINATES: with the default
--per-sheet 60 you get 5 sheets of 60. Works on a PARTIAL bake — it tiles
whatever kits exist and marks the rest "(missing)", so you can spot-check early
batches while the rest are still baking.

    # all sheets for set_0001 (run any time after kits start landing):
    python3 scripts/recruit_sets/proof_sheet.py --set scripts/recruit_sets/set_0001.json
    # bigger tiles, fewer per page:
    python3 scripts/recruit_sets/proof_sheet.py --per-sheet 40 --cols 5

Output -> tmp/portrait-pilot/qc/recruit_<set_id>_pNN.png (one PNG per page).
"""
import os
import sys
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_KIT_DIR = "assets_staging/recruits/kit"
QC_DIR = "tmp/portrait-pilot/qc"


def load_font(size):
    from PIL import ImageFont
    for p in ("FrontEnd/static/fonts/LiberationSans-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def labels_from_manifest(set_path):
    """recruit_id -> 'Frame/Def race' from the manifest sidecar (if present)."""
    man_path = set_path.replace(".json", ".manifest.json")
    if not os.path.exists(man_path):
        return {}
    out = {}
    for e in json.load(open(man_path)).get("entries", []):
        b = e.get("build", {})
        p = e.get("portrait", {})
        tag = f"{b.get('frame', '?')}/{b.get('definition', '?')} {p.get('race', '?')}"
        out[e["recruit_id"]] = tag
    return out


def build_sheet(rows, kit_dir, C, cols, hdr, fnt, sub):
    """One page: `rows` = list of (recruit_id, name, tag)."""
    from PIL import Image, ImageDraw
    n_rows = (len(rows) + cols - 1) // cols
    tile_h = C + hdr
    sheet = Image.new("RGB", (C * cols, tile_h * n_rows), (238, 238, 240))
    d = ImageDraw.Draw(sheet)
    have = 0
    for i, (rid, name, tag) in enumerate(rows):
        x, y = (i % cols) * C, (i // cols) * tile_h
        d.rectangle([x, y, x + C, y + hdr], fill=(28, 42, 68))
        d.text((x + 6, y + 4), str(name)[:32], fill=(200, 169, 81), font=fnt)
        if tag:
            d.text((x + 6, y + 4 + sub), tag[:34], fill=(150, 170, 200), font=fnt)
        kp = os.path.join(kit_dir, f"{rid}.png")
        if os.path.exists(kp):
            have += 1
            im = Image.open(kp).convert("RGBA")
            im.thumbnail((C, C))
            bg = Image.new("RGBA", (C, C), (238, 238, 240, 255))
            bg.alpha_composite(im, ((C - im.width) // 2, 0))
            sheet.paste(bg.convert("RGB"), (x, y + hdr))
        else:
            d.text((x + C // 2 - 34, y + hdr + C // 2), "(missing)", fill=(150, 150, 150), font=fnt)
    return sheet, have


def main():
    ap = argparse.ArgumentParser(description="Paginated recruit QC proof sheets.")
    ap.add_argument("--set", default=os.path.join(HERE, "set_0001.json"),
                    help="set_<id>.json (its .manifest.json is read for labels if present)")
    ap.add_argument("--kit-dir", default=DEFAULT_KIT_DIR)
    ap.add_argument("--out-dir", default=QC_DIR)
    ap.add_argument("--per-sheet", type=int, default=60, help="recruits per page (default 60 -> 5 pages)")
    ap.add_argument("--cols", type=int, default=6, help="columns per page")
    ap.add_argument("--tile", type=int, default=320, help="tile size in px")
    args = ap.parse_args()

    if not os.path.exists(args.set):
        sys.exit(f"set not found: {args.set}")
    recruits = json.load(open(args.set))["recruits"]
    set_id = json.load(open(args.set)).get("set_id", "set")
    tags = labels_from_manifest(args.set)

    hdr, sub = 40, 18
    fnt = load_font(15)
    os.makedirs(args.out_dir, exist_ok=True)

    all_rows = [(r["recruit_id"], r.get("name", "--"), tags.get(r["recruit_id"], "")) for r in recruits]
    pages = [all_rows[i:i + args.per_sheet] for i in range(0, len(all_rows), args.per_sheet)]

    total_have = 0
    written = []
    for pi, page in enumerate(pages, 1):
        sheet, have = build_sheet(page, args.kit_dir, args.tile, args.cols, hdr, fnt, sub)
        out = os.path.join(args.out_dir, f"recruit_{set_id}_p{pi:02d}.png")
        sheet.save(out)
        total_have += have
        written.append((out, have, len(page)))
        print(f"[ok] page {pi}/{len(pages)}: {have}/{len(page)} kits -> {out}")

    missing = [name for rid, name, _ in all_rows if not os.path.exists(os.path.join(args.kit_dir, f"{rid}.png"))]
    print(f"\n[done] {total_have}/{len(all_rows)} kits tiled across {len(pages)} page(s) -> {args.out_dir}")
    if missing:
        preview = ", ".join(missing[:8]) + (" ..." if len(missing) > 8 else "")
        print(f"[missing] {len(missing)} recruit(s) have no kit yet: {preview}")
        print("          (re-run build_recruit_images.py to bake them, then re-run this)")


if __name__ == "__main__":
    main()
