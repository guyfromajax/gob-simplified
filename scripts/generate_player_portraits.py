#!/usr/bin/env python3
"""
Generate raw white-tank player busts (stage 1 of the portrait pipeline).

For each player it BODY-LOCKS onto their archetype's reference body
(reference_bodies/final/<frame>.png) and asks Nano Banana to swap in the face
per the player's spec — skin tone, hair, expression, accessories, muscle
definition — keeping the body/frame/pose/tank/framing/art-style identical. This
yields a consistent white-tank bust; uniforms + finishing come later.

Idempotent & resumable: skips any player who already has a finished master
(FrontEnd/static/images/players/<uuid>.png — protects all of Conf1) and, unless
--force, any raw bust already generated.

Setup (run where you have the paid Gemini key + open network — your machine):
    pip install google-genai pillow
    # .env:  GEMINI_API_KEY=...   (auto-loaded, never printed)

    # ALWAYS start with one player, then a full team, then scale:
    python3 scripts/generate_player_portraits.py --only "Stanley Keith"
    python3 scripts/generate_player_portraits.py --team "Chapel Hill"
    # everything not yet done (the ~1,440):
    python3 scripts/generate_player_portraits.py --all

Inputs:  scripts/players_archetypes.csv  +  reference_bodies/final/<frame>.png
Output:  tmp/portrait-pilot/generated/<Player Name>.png   (raw bust, feeds finishing)
"""
import os
import re
import csv
import sys
import argparse

MODEL = "gemini-3.1-flash-lite-image"          # Nano Banana 2 Lite
REF_DIR = "tmp/portrait-pilot/reference_bodies/final"
MASTERS_DIR = "FrontEnd/static/images/players"  # existing finished art (skip these)

DEF_CLAUSE = {
    "Cut":   "a cut, defined, muscular build with visible muscle tone",
    "Toned": "an average athletic build with normal muscle tone",
    "Soft":  "a soft, undefined build carrying a little extra weight",
}

PROMPT = (
    "Using the attached image as the reference for the EXACT body build, frame, "
    "shoulder width, pose, plain white sleeveless tank top, camera framing and "
    "zoom, plain light neutral background, and semi-realistic illustrated art "
    "style, generate a DIFFERENT 16-17 year old male high-school basketball "
    "player with a distinctive, unique face. He is {skin}. {face} Give him "
    "{hair} and {expression}. {acc}"
    "Render his skin tone consistently across his face, neck, shoulders and "
    "arms. Give him {definition}. Keep the body frame, shoulder width, pose, "
    "white tank, neckline, framing, background, and illustrated art style "
    "IDENTICAL to the reference — change ONLY the face, skin tone, hair, and "
    "muscle definition, and follow the specified facial features closely so he "
    "is clearly a different individual. Front-facing head-and-shoulders bust "
    "portrait."
)


def load_env(path=".env"):
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def slug(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def build_prompt(row):
    acc = row.get("accessories", "").strip()
    acc = f"He has {acc}. " if acc else ""
    return PROMPT.format(
        skin=row["skin_prompt"], face=row.get("face_prompt", ""),
        hair=row["hair"], expression=row["expression"],
        acc=acc, definition=DEF_CLAUSE.get(row["definition"], DEF_CLAUSE["Toned"]))


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--only", help="one player name (first test)")
    g.add_argument("--team", help="one team name")
    g.add_argument("--all", action="store_true", help="every player not yet done")
    ap.add_argument("--map", default="scripts/players_archetypes.csv")
    ap.add_argument("--out", default="tmp/portrait-pilot/generated")
    ap.add_argument("--limit", type=int, help="cap number generated (testing)")
    ap.add_argument("--force", action="store_true",
                    help="regenerate even if a raw bust already exists")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.map)))
    if args.only:
        rows = [r for r in rows if slug(r["name"]) == slug(args.only)]
    elif args.team:
        rows = [r for r in rows if slug(r.get("team", "")) == slug(args.team)]
    if not rows:
        sys.exit("no matching players in the archetype map")

    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY not set (checked env and .env).")
    try:
        from google import genai
        from PIL import Image
    except ImportError:
        sys.exit("missing deps. Run:  pip install google-genai pillow")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    os.makedirs(args.out, exist_ok=True)
    _ref_cache = {}

    def ref_body(frame):
        key = (frame or "normal").lower()
        if key not in _ref_cache:
            path = os.path.join(REF_DIR, f"{key}.png")
            if not os.path.exists(path):
                sys.exit(f"reference body not found: {path}")
            _ref_cache[key] = Image.open(path)
        return _ref_cache[key]

    ok = skipped = 0
    for r in rows:
        name, uid = r["name"], r["_id"]
        # skip finished masters (Conf1 + anything already published)
        if os.path.exists(os.path.join(MASTERS_DIR, f"{uid}.png")):
            skipped += 1
            continue
        out_path = os.path.join(args.out, f"{name}.png")
        if os.path.exists(out_path) and not args.force:
            skipped += 1
            continue
        if args.limit and ok >= args.limit:
            break
        frame = (r.get("template") or r.get("frame") or "normal").lower()
        prompt = build_prompt(r)
        try:
            resp = client.models.generate_content(
                model=MODEL, contents=[prompt, ref_body(frame)])
            saved = False
            for part in resp.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    with open(out_path, "wb") as fh:
                        fh.write(part.inline_data.data)
                    print(f"[ok] {name}  ({frame}/{r['definition']}, {r['ethnicity']})")
                    saved = True
                    ok += 1
                    break
            if not saved:
                print(f"[fail] {name}: no image in response")
        except Exception as e:
            print(f"[fail] {name}: {type(e).__name__}: {str(e)[:160]}")
    print(f"\n[done] {ok} generated, {skipped} skipped -> {args.out}")


if __name__ == "__main__":
    main()
