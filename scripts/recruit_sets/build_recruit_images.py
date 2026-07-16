#!/usr/bin/env python3
"""
Build recruit uniform KITS + finished WHITE MASTERS from a set manifest — Phase 2b.

For each recruit in a set's manifest, this:
  1. GENERATES a fresh white-tank bust via Nano Banana using the recruit's
     portrait genes (skin/face/hair/expression/accessories) body-locked onto his
     projected-build reference body — the exact generate_player_portraits path,
     just fed recruit genes instead of a league-player CSV row.
  2. CUTS OUT the person (u2net / fallback) and precomputes the TANK MASK + bbox,
     so the future sign-time recolor needs no segmentation (portable / offline).
  3. Writes:
       assets_staging/recruits/kit/<recruit_id>.png      pre-finish white RGBA bust (recolor input)
       assets_staging/recruits/kit/<recruit_id>.mask.png tank mask (which pixels the recolor paints)
       assets_staging/recruits/kit/<recruit_id>.json     bbox/center for wordmark placement
       assets_staging/recruits/white/<recruit_id>.png    finished white DISPLAY master (weeks 1-34 UI)

The KIT is the sign-time recolor input; the WHITE master is the finished,
canvas-cropped portrait the recruiting UI shows before a recruit signs (same
framing as rostered players). At signing, the recolor step
(apply_recruit_uniform / sign_recruits) reads the kit and writes the uniformed
master to players/master/<recruit_id>.png.

The white master is just the kit bust run through finish_portraits (no NB, no
u2net) — so if a kit ALREADY exists, this backfills its white master cheaply
without re-rolling the (expensive) NB generation.

Reuses the proven functions from generate_player_portraits / apply_team_uniforms
/ finish_portraits — this script is orchestration only.

Run on your machine (needs GEMINI_API_KEY + u2net, same as the league pipeline):
    # cheap end-to-end proof first — 15 recruits (~$1):
    python3 scripts/recruit_sets/build_recruit_images.py --set scripts/recruit_sets/set_0001.json --limit 15
    # then the whole set (existing kits are just finished into white masters, no re-roll):
    python3 scripts/recruit_sets/build_recruit_images.py --set scripts/recruit_sets/set_0001.json

Idempotent: skips recruits whose kit AND white master already exist; if only the
kit exists, finishes the white master (no NB call); re-rolls only with --force.
Upload (recruits/kit + recruits/white -> R2) is the next step.
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
import finish_portraits as fin                  # noqa: E402  (CANVAS_W/H for kit geometry)

REF_DIR = gen.REF_DIR                            # tmp/portrait-pilot/reference_bodies/final/<frame>.png
OUT_KIT = "assets_staging/recruits/kit"
OUT_WHITE = "assets_staging/recruits/white"      # finished display masters (weeks 1-34 UI)


def strip_watermark(a, alpha, cx=0.95, cy=0.95, r=0.055):
    """Remove the Gemini bottom-right sparkle by CONTENT-AWARE INPAINTING: mask a
    small disk over the sparkle and fill it from the surrounding pixels (cv2 Telea).
    A sparkle-on-skin fills with skin — no seam, no hole. ALPHA is left untouched,
    so the arm silhouette and transparent background are preserved. `a` = RGB float
    array (modified in place). cx/cy/r = sparkle center + radius as fractions of the
    larger dimension. Google's invisible SynthID is untouched."""
    import numpy as np
    try:
        import cv2
    except ImportError:
        raise SystemExit("watermark strip needs OpenCV: pip install opencv-python-headless")
    H, W = a.shape[:2]
    mask = np.zeros((H, W), np.uint8)
    cv2.circle(mask, (int(cx * W), int(cy * H)), max(1, int(r * max(H, W))), 255, -1)
    rgb = np.clip(a[..., :3], 0, 255).astype(np.uint8)
    a[..., :3] = cv2.inpaint(rgb, mask, 10, cv2.INPAINT_TELEA).astype(a.dtype)
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
    ap = argparse.ArgumentParser(description="Generate recruit uniform kits.")
    ap.add_argument("--set", required=True, help="path to a set_<id>.json (its .manifest.json sits beside it)")
    ap.add_argument("--limit", type=int, help="only build the first N (cheap proof run)")
    ap.add_argument("--force", action="store_true", help="rebuild even if the kit exists")
    ap.add_argument("--model", default=gen.MODEL,
                    help="NB image model (try gemini-3.1-flash-image to test if it skips the sparkle)")
    ap.add_argument("--strip-watermark", action="store_true",
                    help="erase the Gemini corner sparkle (off by default)")
    ap.add_argument("--wm-cx", type=float, default=0.94, help="sparkle center x (frac of W)")
    ap.add_argument("--wm-cy", type=float, default=0.95, help="sparkle center y (frac of H)")
    ap.add_argument("--wm-r", type=float, default=0.055, help="sparkle inpaint radius (frac)")
    ap.add_argument("--out-kit", default=OUT_KIT)
    ap.add_argument("--out-white", default=OUT_WHITE)
    args = ap.parse_args()

    gen.load_env()
    # Only PIL/numpy/scipy are needed to finish kits into white masters; the
    # cloud SDK (google-genai) loads lazily in get_client() when actually baking.
    try:
        from PIL import Image
        import numpy as np
        from scipy import ndimage
    except ImportError as e:
        sys.exit(f"missing deps ({e}). Run: pip install pillow numpy scipy")

    set_doc, entries = load_manifest(args.set)
    recruits = set_doc["recruits"]
    if args.limit:
        recruits = recruits[:args.limit]

    os.makedirs(args.out_kit, exist_ok=True)
    os.makedirs(args.out_white, exist_ok=True)

    # NB client is created lazily — only when we actually bake a NEW kit. A run
    # that only backfills white masters over existing kits needs no API key.
    _client = {}
    def get_client():
        if "c" not in _client:
            if not os.environ.get("GEMINI_API_KEY"):
                sys.exit("GEMINI_API_KEY not set — needed to bake new kits "
                         "(existing kits finish to white without it).")
            try:
                from google import genai
            except ImportError as e:
                sys.exit(f"missing dep google-genai ({e}). Run: pip install google-genai")
            _client["c"] = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        return _client["c"]
    _ref_cache = {}

    def ref_body(frame):
        key = (frame or "normal").lower()
        if key not in _ref_cache:
            path = os.path.join(REF_DIR, f"{key}.png")
            if not os.path.exists(path):
                sys.exit(f"reference body not found: {path}")
            _ref_cache[key] = Image.open(path)
        return _ref_cache[key]

    ok = whited = skipped = failed = 0
    for rec in recruits:
        rid = rec["recruit_id"]
        kit_path = os.path.join(args.out_kit, f"{rid}.png")
        white_path = os.path.join(args.out_white, f"{rid}.png")
        # Kit already baked: never re-roll NB. Just ensure the finished white
        # display master exists (cheap: finish the kit bust, no API call). This
        # backfills white masters for kits baked before white was produced.
        if os.path.exists(kit_path) and not args.force:
            if not os.path.exists(white_path):
                fin.finish(kit_path, white_path)
                whited += 1
            else:
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
            resp = get_client().models.generate_content(model=args.model, contents=[prompt, ref_body(frame)])
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

            # erase the Gemini corner watermark before saving the kit
            if args.strip_watermark:
                strip_watermark(a, alpha, cx=args.wm_cx, cy=args.wm_cy, r=args.wm_r)

            # kit: pre-finish white RGBA bust (recolor input) + tank mask + geometry
            rgba = np.dstack([a, alpha]).astype("uint8")
            Image.fromarray(rgba, "RGBA").save(kit_path)
            Image.fromarray((tank * 255).astype("uint8"), "L").save(
                os.path.join(args.out_kit, f"{rid}.mask.png"))
            json.dump({"bbox": bbox, "center_x": center, "frame": frame,
                       "canvas": [fin.CANVAS_W, fin.CANVAS_H]},
                      open(os.path.join(args.out_kit, f"{rid}.json"), "w"))

            os.remove(raw_tmp)

            # finished white DISPLAY master (weeks 1-34 UI) from the kit bust
            fin.finish(kit_path, white_path)

            print(f"[ok] {rec['name']:22} ({frame}/{man['build']['definition']}, "
                  f"{man['portrait']['race']}) -> {rid}.png (+white)")
            ok += 1
        except Exception as e:
            print(f"[fail] {rec['name']} ({rid}): {type(e).__name__}: {str(e)[:160]}")
            failed += 1

    print(f"\n[done] {ok} baked, {whited} white-only backfilled, {skipped} skipped, {failed} failed")
    print(f"  kits          -> {args.out_kit}")
    print(f"  white masters -> {args.out_white}")
    if ok or whited:
        print("Upload with: upload_recruit_images_to_r2.py --stage kit white")


if __name__ == "__main__":
    main()
