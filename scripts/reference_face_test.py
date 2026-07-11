#!/usr/bin/env python3
"""
Reference-face anchoring test. Answers three questions before we build the
facial-geometry gene system, using ONE fixed prompt (so any face variation is
NB's own, not attribute-driven):

  1. Is NB deterministic for identical (prompt, reference)?
       -> 3x onto the SAME original reference. If the 3 are identical, NB adds
          no per-call variation, so two players with the same attributes will
          clone -> we MUST drive diversity from the prompt (descriptors).
  2. Does the reference's baked FACE leak into the output?
       -> same prompt onto slight / broad / doughy originals (different ref
          faces). If the output faces resemble each reference's face, the ref
          is anchoring and we should paint onto the NEUTRALIZED references.
  3. Does neutralizing the reference face free up variation?
       -> 3x onto the face-blurred 'normal' reference. Compare spread vs (1).

Run on your machine (GEMINI key). ~9 images, a couple cents.

    python3 scripts/reference_face_test.py

Outputs: tmp/portrait-pilot/reftest/*.png  +  a labeled sheet reftest_sheet.png
"""
import os
import sys

MODEL = "gemini-3.1-flash-lite-image"
REF = "tmp/portrait-pilot/reference_bodies/final"
REF_N = "tmp/portrait-pilot/reference_bodies/final_neutralized"
OUT = "tmp/portrait-pilot/reftest"

# ONE fixed player spec — nothing varies between calls except the reference.
PROMPT = (
    "Using the attached image as the reference for the EXACT body build, frame, "
    "shoulder width, pose, plain white sleeveless tank top, camera framing and "
    "zoom, plain light neutral background, and semi-realistic illustrated art "
    "style, generate a DIFFERENT 16-17 year old male high-school basketball "
    "player. He is a Black teenager with a medium-brown skin tone. Give him a "
    "short afro and a neutral, calm expression. Render his skin tone consistently "
    "across his face, neck, shoulders and arms. Give him an average athletic "
    "build with normal muscle tone. Keep the body frame, shoulder width, pose, "
    "white tank, neckline, framing, background, and illustrated art style "
    "IDENTICAL to the reference — change ONLY the face, skin tone, hair, and "
    "muscle definition. Front-facing head-and-shoulders bust portrait."
)

# (label, reference path, repeats)
MATRIX = [
    ("normal_orig",    f"{REF}/normal.png",   3),   # Q1 determinism + baseline
    ("normal_neutral", f"{REF_N}/normal.png", 3),   # Q3 neutralized spread
    ("slight_orig",    f"{REF}/slight.png",   1),   # Q2 cross-reference face-leak
    ("broad_orig",     f"{REF}/broad.png",    1),
    ("doughy_orig",    f"{REF}/doughy.png",   1),
]


def load_env(path=".env"):
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY not set (checked env and .env).")
    try:
        from google import genai
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        sys.exit("missing deps. Run:  pip install google-genai pillow")

    for p in (f"{REF}/normal.png", f"{REF_N}/normal.png"):
        if not os.path.exists(p):
            sys.exit(f"missing reference: {p}  (pull the neutralized refs first)")

    os.makedirs(OUT, exist_ok=True)
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    made = []  # (label, idx, path)
    for label, refpath, reps in MATRIX:
        ref = Image.open(refpath)
        for i in range(reps):
            out_path = os.path.join(OUT, f"{label}_{i+1}.png")
            try:
                resp = client.models.generate_content(model=MODEL, contents=[PROMPT, ref])
                for part in resp.candidates[0].content.parts:
                    if getattr(part, "inline_data", None) and part.inline_data.data:
                        with open(out_path, "wb") as fh:
                            fh.write(part.inline_data.data)
                        made.append((label, i + 1, out_path))
                        print(f"[ok] {label} #{i+1}")
                        break
                else:
                    print(f"[fail] {label} #{i+1}: no image in response")
            except Exception as e:
                print(f"[fail] {label} #{i+1}: {type(e).__name__}: {str(e)[:140]}")

    # comparison sheet: one row per reference group, plus the reference thumb at left
    if not made:
        print("no images generated"); return
    from collections import OrderedDict
    groups = OrderedDict()
    for label, idx, path in made:
        groups.setdefault(label, []).append(path)
    refthumb = {"normal_orig": f"{REF}/normal.png", "normal_neutral": f"{REF_N}/normal.png",
                "slight_orig": f"{REF}/slight.png", "broad_orig": f"{REF}/broad.png",
                "doughy_orig": f"{REF}/doughy.png"}
    C = 300
    maxcols = 1 + max(len(v) for v in groups.values())
    sheet = Image.new("RGB", (C * maxcols, (C + 26) * len(groups)), (238, 238, 240))
    d = ImageDraw.Draw(sheet)
    try:
        fnt = ImageFont.truetype("FrontEnd/static/fonts/LiberationSans-Bold.ttf", 15)
    except Exception:
        fnt = ImageFont.load_default()
    for r, (label, paths) in enumerate(groups.items()):
        y = r * (C + 26)
        d.rectangle([0, y, C * maxcols, y + 26], fill=(28, 42, 68))
        d.text((6, y + 5), f"{label}  (ref at left | outputs -->)", fill=(200, 169, 81), font=fnt)
        rt = Image.open(refthumb[label]).convert("RGB"); rt.thumbnail((C, C))
        sheet.paste(rt, (0, y + 26))
        for c, p in enumerate(paths):
            im = Image.open(p).convert("RGB"); im.thumbnail((C, C))
            sheet.paste(im, ((c + 1) * C, y + 26))
    out = "tmp/portrait-pilot/qc/reftest_sheet.png"
    sheet.save(out)
    print(f"\n[sheet] -> {out}")
    print("Read it: row1 spread=NB randomness; row1 vs its ref & rows 3-5 vs their")
    print("refs=face leak; row2 (neutralized) spread vs row1=does blurring free it.")


if __name__ == "__main__":
    main()
