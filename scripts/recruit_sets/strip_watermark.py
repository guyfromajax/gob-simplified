#!/usr/bin/env python3
"""
Strip the Gemini bottom-right sparkle from finished recruit WHITE masters, in place.

Non-destructive method: extends the content directly ABOVE the corner box downward
(RGB + alpha), so the arm stays arm and transparent background stays transparent —
it can never pull the side background in (no white block). Operates on the finished
masters (the coordinate system we measured the sparkle in), so what you verify is
exactly what ships.

    # clean all white masters
    python3 scripts/recruit_sets/strip_watermark.py
    # one file
    python3 scripts/recruit_sets/strip_watermark.py --recruit-id <uuid>
    # nudge the box if it misses/over-covers (fractions of W/H, top-left of the box)
    python3 scripts/recruit_sets/strip_watermark.py --x-frac 0.87 --y-frac 0.88

Shares the removal logic with build_recruit_images.strip_watermark. Once verified,
the same box is applied at generation time (build_recruit_images --strip-watermark),
and re-run apply_recruit_uniform to refresh signed masters.
"""
import os
import sys
import glob
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)

import build_recruit_images as bri          # noqa: E402  (shared strip_watermark)

WHITE_DIR = "assets_staging/recruits/white"


def main():
    ap = argparse.ArgumentParser(description="Strip Gemini watermark from finished white masters.")
    ap.add_argument("--white-dir", default=WHITE_DIR)
    ap.add_argument("--recruit-id", help="one recruit uuid (default: all)")
    ap.add_argument("--cx", type=float, default=0.94, help="sparkle center x (frac of W)")
    ap.add_argument("--cy", type=float, default=0.95, help="sparkle center y (frac of H)")
    ap.add_argument("--r", type=float, default=0.055, help="sparkle inpaint radius (frac)")
    ap.add_argument("--suffix", default="", help="write to <id><suffix>.png instead of in place (e.g. _clean)")
    args = ap.parse_args()

    import numpy as np
    from PIL import Image

    if args.recruit_id:
        paths = [os.path.join(args.white_dir, f"{args.recruit_id}.png")]
    else:
        paths = sorted(glob.glob(os.path.join(args.white_dir, "*.png")))
    ok = fail = 0
    for p in paths:
        if not os.path.exists(p):
            print(f"[skip] not found: {p}")
            continue
        try:
            arr = np.asarray(Image.open(p).convert("RGBA")).astype(np.float32)
            a, alpha = arr[..., :3].copy(), arr[..., 3].copy()
            bri.strip_watermark(a, alpha, cx=args.cx, cy=args.cy, r=args.r)
            out = np.dstack([np.clip(a, 0, 255), alpha]).astype("uint8")
            base, ext = os.path.splitext(p)
            outp = f"{base}{args.suffix}{ext}"
            Image.fromarray(out, "RGBA").save(outp)
            print(f"[ok] {os.path.basename(outp)}")
            ok += 1
        except Exception as e:
            print(f"[fail] {os.path.basename(p)}: {type(e).__name__}: {str(e)[:120]}")
            fail += 1
    print(f"\n[done] {ok} cleaned, {fail} failed (fade @ {args.cx},{args.cy} r={args.r})")


if __name__ == "__main__":
    main()
