#!/usr/bin/env python3
"""
Build recruit uniform KITS from a set manifest — Phase 2b.

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

The kit is the ONLY pre-sign asset: nothing in the game ever displays an
un-signed recruit's portrait (the recruiting board is a stats table, and
un-signed recruits sunset at week 35). A finished display master is produced
only at signing, by the recolor step (apply_recruit_uniform / sign_recruits),
which reads the kit and writes players/master/<recruit_id>.png.

Reuses the proven functions from generate_player_portraits / apply_team_uniforms
/ finish_portraits — this script is orchestration only.

Run on your machine (needs GEMINI_API_KEY + u2net, same as the league pipeline):
    # cheap end-to-end proof first — 15 recruits (~$1):
    python3 scripts/recruit_sets/build_recruit_images.py --set scripts/recruit_sets/set_0001.json --limit 15
    # then the whole set:
    python3 scripts/recruit_sets/build_recruit_images.py --set scripts/recruit_sets/set_0001.json

Idempotent: skips recruits whose kit already exists (unless --force).
Upload (recruits/kit -> R2) is the next step.
"""
import os
import sys
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, HERE)
sys.path.insert(0, SCRIPTS)

import generate_player_portraits as gen         # noqa: E402  (PROMPT, build_prompt, load_env, MODEL)
import apply_team_uniforms as uni               # noqa: E402  (person_alpha, _tank)
import finish_portraits as fin                  # noqa: E402  (CANVAS_W/H for kit geometry)

REF_DIR = gen.REF_DIR                            # tmp/portrait-pilot/reference_bodies/final/<frame>.png
OUT_KIT = "assets_staging/recruits/kit"


_WM_TEMPLATE = None


def _wm_template():
    """The Gemini sparkle glyph as a mean-subtracted matched filter (cached).
    Extracted once from a crisp dark-skin example; matched by SHAPE so skin tone
    doesn't affect localization. Lives beside this script as watermark_template.png."""
    global _WM_TEMPLATE
    if _WM_TEMPLATE is None:
        import numpy as np
        from PIL import Image
        t = np.asarray(Image.open(os.path.join(HERE, "watermark_template.png")).convert("L")).astype("float32")
        _WM_TEMPLATE = t - t.mean()
    return _WM_TEMPLATE


def strip_watermark(a, alpha, cx=0.95, cy=0.95, r=0.03,
                    score_min=0.50, precise_min=0.82, log=None):
    """Remove the Gemini bottom-right sparkle by LOCATING it with a shape template and
    inpainting only over skin. Three regimes by match confidence, so it never leaves the
    white-blob-over-the-arm the old fixed-disk version produced and never damages a bust:

    1. LOCATE by SHAPE, not brightness. Normalised cross-correlation of the sparkle glyph
       template over the bottom-right corner BAND (the star's x is stable ≈0.94, its y
       varies with arm pose) scores how confidently the star is placed. Brightness/top-hat
       methods miss faint sparkles on light skin and false-match skin highlights — the
       glyph shape does not.

       • score ≥ precise_min  → PRECISE: tight disk at the matched location (crisp,
         high-contrast sparkles — mostly medium/dark skin).
       • score_min ≤ score < precise_min → SWEEP: localisation is unreliable (faint
         low-contrast sparkles on light skin land the match off-target), so inpaint the
         whole bottom-right arm CORNER — a smooth-skin region where a broad fill is
         seamless — removing the star wherever it sits.
       • score < score_min → SKIP: no confident star; leave the bust untouched (a faint
         residual beats an artifact — and these are the least-visible sparkles anyway).

    2. FILL FROM SKIN ONLY. Every mask is intersected with the ERODED person mask, so cv2
       Telea fills from interior skin and never from the anti-aliased arm edge or the
       white background — the two sources that produced white smears. A mask that lands
       entirely off-person empties and we no-op (the star was on transparent bg → invisible).

    `a` = RGB float array (modified in place); `alpha` = 0-255 person mask (untouched).
    cx/cy/r retained for signature compatibility (unused). Returns `a`. Google's invisible
    SynthID is untouched. `log` (callable) receives a one-line status."""
    import numpy as np
    try:
        import cv2
    except ImportError:
        raise SystemExit("watermark strip needs OpenCV: pip install opencv-python-headless")
    H, W = a.shape[:2]
    tmpl = _wm_template()
    half = tmpl.shape[0] // 2
    lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]).clip(0, 255).astype(np.float32)

    y0, x0 = int(0.80 * H), int(0.88 * W)
    res = cv2.matchTemplate(lum[y0:, x0:], tmpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(res)
    if score < score_min:                                # uncertain → never damage, leave it
        if log:
            log(f"SKIP  score={score:.2f} (<{score_min}) — sparkle left untouched")
        return a

    person = cv2.erode((alpha > 128).astype(np.uint8),
                       cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    mask = np.zeros((H, W), np.uint8)
    if score >= precise_min:                             # confident placement → tight disk
        bx, by = x0 + loc[0] + half, y0 + loc[1] + half
        cv2.circle(mask, (bx, by), half + 6, 255, -1)
        mode = "PREC "
    else:                                                # unreliable loc → blind corner sweep over skin
        cv2.ellipse(mask, (int(0.955 * W), int(0.905 * H)),
                    (int(0.060 * W), int(0.075 * H)), 0, 0, 360, 255, -1)
        mode = "SWEEP"
    mask[person == 0] = 0
    if mask.max() == 0:                                  # landed off-person → invisible
        if log:
            log(f"BG    score={score:.2f} — off-person, no-op")
        return a
    rgb = np.clip(a[..., :3], 0, 255).astype(np.uint8)
    a[..., :3] = cv2.inpaint(rgb, mask, 7, cv2.INPAINT_TELEA).astype(a.dtype)
    if log:
        log(f"{mode} score={score:.2f}")
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
    ap.add_argument("--wm-cx", type=float, default=0.95, help="FALLBACK sparkle center x (frac of W), used only when auto-detect finds nothing")
    ap.add_argument("--wm-cy", type=float, default=0.95, help="FALLBACK sparkle center y (frac of H), used only when auto-detect finds nothing")
    ap.add_argument("--wm-r", type=float, default=0.03, help="FALLBACK sparkle inpaint radius (frac), used only when auto-detect finds nothing")
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
        kit_path = os.path.join(args.out_kit, f"{rid}.png")
        if os.path.exists(kit_path) and not args.force:
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
            resp = client.models.generate_content(model=args.model, contents=[prompt, ref_body(frame)])
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
            from mask_validation import assert_tank_mask_usable
            try:
                assert_tank_mask_usable(tank, source=rid)
            except RuntimeError as exc:
                print(f"[fail] {rec['name']} ({rid}): {exc} — re-run to re-roll")
                failed += 1
                os.remove(raw_tmp)
                continue
            ys, xs = np.where(tank)
            bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
            center = int((xs.min() + xs.max()) / 2)

            # erase the Gemini corner watermark before saving the kit
            if args.strip_watermark:
                strip_watermark(a, alpha, cx=args.wm_cx, cy=args.wm_cy, r=args.wm_r,
                                log=lambda m, _n=rec["name"]: print(f"    [wm] {_n:22} {m}"))

            # kit: pre-finish white RGBA bust (recolor input) + tank mask + geometry
            rgba = np.dstack([a, alpha]).astype("uint8")
            Image.fromarray(rgba, "RGBA").save(kit_path)
            Image.fromarray((tank * 255).astype("uint8"), "L").save(
                os.path.join(args.out_kit, f"{rid}.mask.png"))
            json.dump({"bbox": bbox, "center_x": center, "frame": frame,
                       "canvas": [fin.CANVAS_W, fin.CANVAS_H]},
                      open(os.path.join(args.out_kit, f"{rid}.json"), "w"))

            os.remove(raw_tmp)
            print(f"[ok] {rec['name']:22} ({frame}/{man['build']['definition']}, "
                  f"{man['portrait']['race']}) -> {rid}.png")
            ok += 1
        except Exception as e:
            print(f"[fail] {rec['name']} ({rid}): {type(e).__name__}: {str(e)[:160]}")
            failed += 1

    print(f"\n[done] {ok} built, {skipped} skipped, {failed} failed")
    print(f"  kits -> {args.out_kit}")
    if ok:
        print("Spot-check a few kits, then upload recruits/kit to R2 and recolor a proof team.")


if __name__ == "__main__":
    main()
