#!/usr/bin/env python3
"""
Strip the Gemini corner watermark from already-generated recruit kits — no NB re-spend.

Loads each recruit kit bust (assets_staging/recruits/kit/<id>.png, pre-finish
RGBA), erases the bottom-right sparkle (reflect adjacent content over person
pixels), saves the cleaned kit back, and re-derives the finished white display
master. The SIGNED uniform master is regenerated when you next run
apply_recruit_uniform (it reads the now-clean kit), so nothing else is needed.

    # clean every kit + white master
    python3 scripts/recruit_sets/strip_watermark.py
    # tune the corner-box size if it clips a shoulder or misses the sparkle
    python3 scripts/recruit_sets/strip_watermark.py --wm-frac 0.20
    # one recruit
    python3 scripts/recruit_sets/strip_watermark.py --recruit-id <uuid>

The removal logic is shared with build_recruit_images.strip_watermark, so future
generation and this cleanup pass stay identical.
"""
import os
import sys
import glob
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)

import finish_portraits as fin              # noqa: E402  (finish -> crop to canvas)
import build_recruit_images as bri          # noqa: E402  (shared strip_watermark)

KIT_DIR = "assets_staging/recruits/kit"
WHITE_DIR = "assets_staging/recruits/white"


def main():
    ap = argparse.ArgumentParser(description="Strip Gemini watermark from existing recruit kits.")
    ap.add_argument("--kit-dir", default=KIT_DIR)
    ap.add_argument("--white-dir", default=WHITE_DIR)
    ap.add_argument("--recruit-id", help="one recruit uuid (default: all kits)")
    ap.add_argument("--wm-frac", type=float, default=0.16)
    args = ap.parse_args()

    import numpy as np
    from PIL import Image

    if args.recruit_id:
        ids = [args.recruit_id]
    else:
        ids = [os.path.basename(p)[:-4] for p in glob.glob(os.path.join(args.kit_dir, "*.png"))
               if not p.endswith(".mask.png")]
    os.makedirs(args.white_dir, exist_ok=True)

    ok = fail = 0
    for rid in ids:
        kit_p = os.path.join(args.kit_dir, f"{rid}.png")
        if not os.path.exists(kit_p):
            print(f"[skip] {rid}: kit not found")
            continue
        try:
            arr = np.asarray(Image.open(kit_p).convert("RGBA")).astype(np.float32)
            a, alpha = arr[..., :3].copy(), arr[..., 3]
            bri.strip_watermark(a, alpha, frac=args.wm_frac)
            rgba = np.dstack([a, alpha]).astype("uint8")
            Image.fromarray(rgba, "RGBA").save(kit_p)                    # cleaned kit
            tmp = kit_p + ".prefinish.png"
            Image.fromarray(rgba, "RGBA").save(tmp)
            fin.finish(tmp, os.path.join(args.white_dir, f"{rid}.png"))  # re-finished white master
            os.remove(tmp)
            print(f"[ok] {rid}")
            ok += 1
        except Exception as e:
            print(f"[fail] {rid}: {type(e).__name__}: {str(e)[:120]}")
            fail += 1

    print(f"\n[done] {ok} cleaned, {fail} failed. Re-run apply_recruit_uniform to refresh signed masters.")


if __name__ == "__main__":
    main()
