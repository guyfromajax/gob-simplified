#!/usr/bin/env python3
"""
Build recruit WHITE MASTERS + uniform KITS from a set manifest — Phase 2b.

For each recruit in a set's manifest, this:
  1. GENERATES a fresh white-tank bust via Nano Banana using the recruit's
     portrait genes (skin/face/hair/expression/accessories) body-locked onto his
     projected-build reference body — the exact generate_player_portraits path,
     just fed recruit genes instead of a league-player CSV row.
  2. CUTS OUT the person (u2net / fallback) and precomputes the TANK MASK + bbox,
     so the future sign-time recolor needs no segmentation (portable / offline).
  3. Writes:
       assets_staging/recruits/white/<recruit_id>.png   finished display master (weeks 1-34)
       assets_staging/recruits/kit/<recruit_id>.png      pre-finish white RGBA bust (recolor input)
       assets_staging/recruits/kit/<recruit_id>.mask.png tank mask (which pixels the recolor paints)
       assets_staging/recruits/kit/<recruit_id>.json     bbox/center for wordmark placement

Reuses the proven functions from generate_player_portraits / apply_team_uniforms
/ finish_portraits — this script is orchestration only.

Run on your machine (needs GEMINI_API_KEY + u2net, same as the league pipeline):
    # cheap end-to-end proof first — 15 recruits (~$1):
    python3 scripts/recruit_sets/build_recruit_images.py --set scripts/recruit_sets/set_0001.json --limit 15
    # then the whole set:
    python3 scripts/recruit_sets/build_recruit_images.py --set scripts/recruit_sets/set_0001.json

Idempotent: skips recruits whose white master already exists (unless --force).
Upload (recruits/white + recruits/kit -> R2) is the next step.
"""
import os
import sys
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

import generate_player_portraits as gen         # noqa: E402  (PROMPT, build_prompt, load_env, MODEL)
import apply_team_uniforms as uni               # noqa: E402  (person_alpha, _tank)
import finish_portraits as fin                  # noqa: E402  (finish -> crop to canvas)

REF_DIR = gen.REF_DIR                            # tmp/portrait-pilot/reference_bodies/final/<frame>.png
OUT_WHITE = "assets_staging/recruits/white"
OUT_KIT = "assets_staging/recruits/kit"


def strip_watermark(a, alpha, frac=0.16):
    """Erase the Gemini/Nano-Banana corner sparkle by reflecting adjacent content
    into the bottom-right corner box, only over person pixels (alpha>0). `a` = RGB
    float array (modified in place), `alpha` = 0-255 person mask. `frac` = corner
    box size as a fraction of each dimension — tune if it clips a shoulder or
    misses the mark. Google's invisible SynthID is untouched; only the visible
    sparkle is removed."""
    import numpy as np
    H, W, _ = a.shape
    bw = max(1, int(W * frac))
    bh = max(1, int(H * frac))
    x0, y0 = W - bw, H - bh
    if x0 - bw < 0:
        return a
    src = a[y0:H, x0 - bw:x0][:, ::-1, :]          # reflect the strip just left of the box
    box = a[y0:H, x0:W]
    m = (alpha[y0:H, x0:W] > 0)[..., None]          # only overwrite the person, not background
    box[:] = np.where(m, src[:box.shape[0], :box.shape[1], :], box)
    return a


def gene_row(record, manifest_entry):
    """Assemble a generate_player_portraits-compatible 'row' from recruit genes."""
    import player_ethnicity as pe
    p = manifest_entry["portrait"]
    skin_prompt = p.get("skin_prompt") or pe.SKIN_PROMPT.get(p.get("skin"), "")
    return {
        "skin_prompt": skin_prompt,
        "face_prompt": p.get("face_prompt", ""),
        "hair": p["hair"],
        "expression": p["expression"],
        "accessories": p.get("accessories", ""),
        "definition": manifest_entry["build"]["definition"],
    }


def load_manifest(set_path):
    set_doc = json.load(open(set_path))
    man_path = set_path.replace(".json", ".manifest.json")
    if not os.path.exists(man_path):
        sys.exit(f"manifest not found next to set: {man_path}")
    entries = {e["recruit_id"]: e for e in json.load(open(man_path))["entries"]}
    return set_doc, entries


def main():
    ap = argparse.ArgumentParser(description="Generate recruit white masters + uniform kits.")
    ap.add_argument("--set", required=True, help="path to a set_<id>.json (its .manifest.json sits beside it)")
    ap.add_argument("--limit", type=int, help="only build the first N (cheap proof run)")
    ap.add_argument("--force", action="store_true", help="rebuild even if the white master exists")
    ap.add_argument("--strip-watermark", action="store_true",
                    help="(EXPERIMENTAL) erase the Gemini corner sparkle — off by default")
    ap.add_argument("--wm-frac", type=float, default=0.16,
                    help="corner-box size (fraction of each dim) for watermark removal")
    ap.add_argument("--out-white", default=OUT_WHITE)
    ap.add_argument("--out-kit", default=OUT_KIT)
    args = ap.parse_args()

    gen.load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY not set (checked env and .env).")
    try:
        from google import genai
        from PIL import Image
        import numpy as np
        from scipy import ndimage
    except ImportError as e:
        sys.exit(f"missing deps ({e}). Run: pip install google-genai pillow numpy scipy")

    set_doc, entries = load_manifest(args.set)
    recruits = set_doc["recruits"]
    if args.limit:
        recruits = recruits[:args.limit]

    os.makedirs(args.out_white, exist_ok=True)
    os.makedirs(args.out_kit, exist_ok=True)
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    _ref_cache = {}

    def ref_body(frame):
        key = (frame or "normal").lower()
        if key not in _ref_cache:
            path = os.path.join(REF_DIR, f"{key}.png")
            if not os.path.exists(path):
                sys.exit(f"reference body not found: {path}")
            _ref_cache[key] = Image.open(path)
        return _ref_cache[key]

    ok = skipped = failed = 0
    for rec in recruits:
        rid = rec["recruit_id"]
        white_path = os.path.join(args.out_white, f"{rid}.png")
        if os.path.exists(white_path) and not args.force:
            skipped += 1
            continue
        man = entries.get(rid)
        if not man:
            print(f"[skip] {rid}: no manifest entry")
            failed += 1
            continue
        frame = man["build"]["frame"]
        prompt = gen.build_prompt(gene_row(rec, man))

        try:
            # 1. generate raw white-tank bust
            resp = client.models.generate_content(model=gen.MODEL, contents=[prompt, ref_body(frame)])
            raw = None
            for part in resp.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    raw = part.inline_data.data
                    break
            if not raw:
                print(f"[fail] {rec['name']} ({rid}): no image in NB response")
                failed += 1
                continue
            raw_tmp = os.path.join(args.out_kit, f"{rid}.raw.png")
            with open(raw_tmp, "wb") as fh:
                fh.write(raw)

            # 2. cut out person + precompute tank mask/bbox (no recolor)
            src = Image.open(raw_tmp).convert("RGB")
            a = np.asarray(src).astype(np.float32)
            alpha = uni.person_alpha(src, np, ndimage)          # 0-255
            person = alpha > 128
            tank = uni._tank(a, person, np, ndimage)            # bool
            ys, xs = np.where(tank)
            if len(ys) == 0:
                print(f"[fail] {rec['name']} ({rid}): no tank found (bad bust) — re-run to re-roll")
                failed += 1
                os.remove(raw_tmp)
                continue
            bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
            center = int((xs.min() + xs.max()) / 2)

            # erase the Gemini corner watermark before saving (kit + white both clean)
            if args.strip_watermark:
                strip_watermark(a, alpha, frac=args.wm_frac)

            # kit: pre-finish white RGBA bust (recolor input) + tank mask + geometry
            rgba = np.dstack([a, alpha]).astype("uint8")
            Image.fromarray(rgba, "RGBA").save(os.path.join(args.out_kit, f"{rid}.png"))
            Image.fromarray((tank * 255).astype("uint8"), "L").save(
                os.path.join(args.out_kit, f"{rid}.mask.png"))
            json.dump({"bbox": bbox, "center_x": center, "frame": frame,
                       "canvas": [fin.CANVAS_W, fin.CANVAS_H]},
                      open(os.path.join(args.out_kit, f"{rid}.json"), "w"))

            # 3. finished white display master (crop to canvas) from the cutout
            cut_tmp = os.path.join(args.out_kit, f"{rid}.cut.png")
            Image.fromarray(rgba, "RGBA").save(cut_tmp)
            fin.finish(cut_tmp, white_path)

            os.remove(raw_tmp)
            os.remove(cut_tmp)
            print(f"[ok] {rec['name']:22} ({frame}/{man['build']['definition']}, "
                  f"{man['portrait']['race']}) -> {rid}.png")
            ok += 1
        except Exception as e:
            print(f"[fail] {rec['name']} ({rid}): {type(e).__name__}: {str(e)[:160]}")
            failed += 1

    print(f"\n[done] {ok} built, {skipped} skipped, {failed} failed")
    print(f"  white masters -> {args.out_white}")
    print(f"  kits          -> {args.out_kit}")
    if ok:
        print("Eyeball a few white masters, then upload recruits/white + recruits/kit to R2.")


if __name__ == "__main__":
    main()
