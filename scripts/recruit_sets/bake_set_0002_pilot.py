#!/usr/bin/env python3
"""
§6.5a Step 2 pilot — 20 developed-player extension images.

  12 Broad-Toned + 8 Doughy-Soft, split teen vs developed age prompts so the
  anatomy-vs-style tension is visible on one contact sheet.

Uses the same pipeline as build_recruit_images.py (NB body-lock + cutout kit).
Reference bodies: tmp/portrait-pilot/reference_bodies/final/<frame>.png
(restored from the locked set_0001 finals — not regenerated).

    python3 scripts/recruit_sets/bake_set_0002_pilot.py
    python3 scripts/recruit_sets/bake_set_0002_pilot.py --contact-sheet-only
"""
import os
import sys
import csv
import json
import uuid
import argparse
import hashlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

import generate_player_portraits as gen  # noqa: E402
import apply_team_uniforms as uni        # noqa: E402

OUT_DIR = "tmp/portrait-pilot/set_0002_pilot"
KIT_DIR = os.path.join(OUT_DIR, "kit")
META_PATH = os.path.join(OUT_DIR, "pilot_meta.json")
SHEET_PATH = os.path.join(OUT_DIR, "contact_sheet_unlabelled.png")
SET_0001_KIT = "/Users/jamesdavies/gob-portraits/assets_staging/recruits/kit"

# Stock teen prompt (matches set_0001 bake). Developed variant swaps age only —
# same reference body, same DEF_CLAUSE — so the A/B isolates the age tension.
TEEN_AGE = (
    "a DIFFERENT 16-17 year old male high-school basketball player"
)
DEVELOPED_AGE = (
    "a DIFFERENT 21-22 year old male college basketball senior — a developed "
    "adult athlete, not a teenager"
)

# Pilot cell plan: 12 Broad-Toned, 8 Doughy-Soft. Skins favour high league demand.
# age_mode cycles teen/developed within each body so both acceptance tests get evidence.
PILOT_CELLS = [
    # Broad-Toned × 12 (6 teen / 6 developed)
    ("Broad", "Toned", "black-normal", "teen"),
    ("Broad", "Toned", "black-normal", "developed"),
    ("Broad", "Toned", "black-light", "teen"),
    ("Broad", "Toned", "black-light", "developed"),
    ("Broad", "Toned", "white-normal", "teen"),
    ("Broad", "Toned", "white-normal", "developed"),
    ("Broad", "Toned", "hispanic", "teen"),
    ("Broad", "Toned", "hispanic", "developed"),
    ("Broad", "Toned", "black-dark", "teen"),
    ("Broad", "Toned", "white-tan", "developed"),
    ("Broad", "Toned", "asian", "teen"),
    ("Broad", "Toned", "white-pale", "developed"),
    # Doughy-Soft × 8 (4 teen / 4 developed) — weighted; furthest from recruit refs
    ("Doughy", "Soft", "black-normal", "teen"),
    ("Doughy", "Soft", "black-normal", "developed"),
    ("Doughy", "Soft", "black-light", "teen"),
    ("Doughy", "Soft", "white-normal", "developed"),
    ("Doughy", "Soft", "white-tan", "teen"),
    ("Doughy", "Soft", "hispanic", "developed"),
    ("Doughy", "Soft", "black-dark", "teen"),
    ("Doughy", "Soft", "white-pale", "developed"),
]


def build_prompt_aged(row, age_mode):
    """Like gen.build_prompt but with an explicit age clause."""
    base = gen.build_prompt(row)
    age = TEEN_AGE if age_mode == "teen" else DEVELOPED_AGE
    old = "a DIFFERENT 16-17 year old male high-school basketball player"
    if old not in base:
        raise SystemExit("PROMPT template changed — update age swap in bake_set_0002_pilot.py")
    return base.replace(old, age)


def stable_uuid(frame, definition, skin, age_mode, n):
    """Deterministic UUID so re-runs don't mint new ids / collide with set_0001."""
    h = hashlib.md5(f"set_0002_pilot|{frame}|{definition}|{skin}|{age_mode}|{n}".encode()).hexdigest()
    return str(uuid.UUID(h))


def load_league_genes():
    by = defaultdict(list)
    for p in csv.DictReader(open(os.path.join(ROOT, "scripts/players_archetypes.csv"))):
        by[(p["frame"], p["definition"], p["skin"])].append(p)
    return by


def pick_gene(pool_map, frame, definition, skin, salt):
    pool = pool_map.get((frame, definition, skin)) or []
    if not pool:
        # fall back: same frame+def any skin, then same frame
        pool = [p for (fr, de, sk), ps in pool_map.items() if fr == frame and de == definition for p in ps]
    if not pool:
        pool = [p for (fr, de, sk), ps in pool_map.items() if fr == frame for p in ps]
    if not pool:
        raise SystemExit(f"no league genes for {frame}/{definition}/{skin}")
    i = int(hashlib.md5(salt.encode()).hexdigest(), 16) % len(pool)
    return pool[i]


def build_pilot_meta():
    set0001 = {r["recruit_id"] for r in json.load(open(os.path.join(HERE, "set_0001.json")))["recruits"]}
    genes = load_league_genes()
    slots = []
    counts = defaultdict(int)
    for frame, definition, skin, age_mode in PILOT_CELLS:
        counts[(frame, definition, skin, age_mode)] += 1
        n = counts[(frame, definition, skin, age_mode)]
        rid = stable_uuid(frame, definition, skin, age_mode, n)
        if rid in set0001:
            raise SystemExit(f"pilot id collides with set_0001: {rid}")
        src = pick_gene(genes, frame, definition, skin, rid)
        slots.append({
            "image_id": rid,
            "frame": frame,
            "definition": definition,
            "skin": skin,
            "age_mode": age_mode,
            "source_player": src["name"],
            "source_hw": f"{src['height_in']}in/{src['weight_lb']}lb",
            "row": {
                "skin_prompt": src["skin_prompt"],
                "face_prompt": src["face_prompt"],
                "hair": src["hair"],
                "expression": src["expression"],
                "accessories": src.get("accessories", ""),
                "definition": definition,
            },
        })
    return slots


def bake(slots, force=False):
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY not set in the invoking process")
    from google import genai
    from PIL import Image
    import numpy as np
    from scipy import ndimage

    os.makedirs(KIT_DIR, exist_ok=True)
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    ref_cache = {}

    def ref_body(frame):
        key = frame.lower()
        if key not in ref_cache:
            path = os.path.join(ROOT, gen.REF_DIR, f"{key}.png")
            if not os.path.exists(path):
                sys.exit(f"reference body not found: {path}")
            ref_cache[key] = Image.open(path)
        return ref_cache[key]

    ok = skip = fail = 0
    for s in slots:
        rid = s["image_id"]
        kit_path = os.path.join(KIT_DIR, f"{rid}.png")
        if os.path.exists(kit_path) and not force:
            print(f"[skip] {s['frame']}-{s['definition']}/{s['skin']} ({s['age_mode']})")
            skip += 1
            continue
        prompt = build_prompt_aged(s["row"], s["age_mode"])
        import time
        last_err = None
        for attempt in range(5):
            try:
                resp = client.models.generate_content(
                    model=gen.MODEL, contents=[prompt, ref_body(s["frame"])])
                raw = None
                for part in resp.candidates[0].content.parts:
                    if getattr(part, "inline_data", None) and part.inline_data.data:
                        raw = part.inline_data.data
                        break
                if not raw:
                    last_err = "no image in response"
                    time.sleep(2 ** attempt)
                    continue
                raw_tmp = os.path.join(KIT_DIR, f"{rid}.raw.png")
                with open(raw_tmp, "wb") as fh:
                    fh.write(raw)
                src = Image.open(raw_tmp).convert("RGB")
                a = np.asarray(src).astype(np.float32)
                alpha = uni.person_alpha(src, np, ndimage)
                person = alpha > 128
                tank = uni._tank(a, person, np, ndimage)
                ys, xs = np.where(tank)
                if len(ys) == 0:
                    last_err = "no tank"
                    os.remove(raw_tmp)
                    time.sleep(2 ** attempt)
                    continue
                rgba = np.dstack([a, alpha]).astype("uint8")
                Image.fromarray(rgba, "RGBA").save(kit_path)
                os.remove(raw_tmp)
                print(f"[ok] {s['frame']}-{s['definition']}/{s['skin']} "
                      f"age={s['age_mode']} src={s['source_player']} ({s['source_hw']})")
                ok += 1
                last_err = None
                break
            except Exception as e:
                last_err = f"{type(e).__name__}: {str(e)[:160]}"
                wait = 2 ** attempt
                print(f"[retry {attempt+1}/5] {rid}: {last_err[:80]}  sleep {wait}s")
                time.sleep(wait)
        if last_err:
            print(f"[fail] {rid}: {last_err}")
            fail += 1
    print(f"\n[done] ok={ok} skip={skip} fail={fail} -> {KIT_DIR}")
    return ok, fail


def pick_set_0001_tiles(n=20, seed=42):
    """White kits from set_0001 for the mixed contact sheet (prefer Broad/Doughy/Normal)."""
    import random
    man = {e["recruit_id"]: e for e in json.load(open(os.path.join(HERE, "set_0001.manifest.json")))["entries"]}
    have = []
    for fn in os.listdir(SET_0001_KIT):
        if not fn.endswith(".png") or fn.endswith(".mask.png") or ".raw." in fn:
            continue
        rid = fn[:-4]
        e = man.get(rid)
        if not e:
            continue
        path = os.path.join(SET_0001_KIT, fn)
        have.append((e["build"]["frame"], path, rid))
    rng = random.Random(seed)
    # Prefer underrepresented frames so the sheet isn't 65% Lean
    prefer = [x for x in have if x[0] in ("Broad", "Doughy", "Normal", "Slight")]
    lean = [x for x in have if x[0] == "Lean"]
    rng.shuffle(prefer)
    rng.shuffle(lean)
    picked = (prefer[:14] + lean[:6])[:n]
    rng.shuffle(picked)
    return [{"path": p, "origin": "set_0001", "frame": fr, "id": rid} for fr, p, rid in picked]


def contact_sheet(slots, seed=7):
    """Unlabelled mixed sheet: pilot kits + set_0001 kits. Key in sidecar JSON only."""
    from PIL import Image
    import random

    tiles = []
    for s in slots:
        path = os.path.join(KIT_DIR, f"{s['image_id']}.png")
        if os.path.exists(path):
            tiles.append({
                "path": path,
                "origin": "pilot",
                "age_mode": s["age_mode"],
                "frame": s["frame"],
                "definition": s["definition"],
                "skin": s["skin"],
                "id": s["image_id"],
            })
    tiles.extend(pick_set_0001_tiles(n=len(tiles) or 20, seed=seed))
    rng = random.Random(seed)
    rng.shuffle(tiles)

    C, cols = 280, 8
    n = len(tiles)
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (C * cols, C * rows), (236, 236, 238))
    key = []
    for i, t in enumerate(tiles):
        x, y = (i % cols) * C, (i // cols) * C
        im = Image.open(t["path"]).convert("RGBA")
        im.thumbnail((C - 8, C - 8))
        bg = Image.new("RGBA", (C, C), (236, 236, 238, 255))
        bg.alpha_composite(im, ((C - im.width) // 2, (C - im.height) // 2))
        sheet.paste(bg.convert("RGB"), (x, y))
        key.append({"index": i, "row": i // cols, "col": i % cols, **{k: t[k] for k in t if k != "path"}})

    os.makedirs(OUT_DIR, exist_ok=True)
    sheet.save(SHEET_PATH)
    key_path = os.path.join(OUT_DIR, "contact_sheet_key.json")
    json.dump({"sheet": SHEET_PATH, "tiles": key}, open(key_path, "w"), indent=2)
    print(f"[sheet] {SHEET_PATH}  ({n} tiles)  key -> {key_path}")
    return SHEET_PATH


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--contact-sheet-only", action="store_true")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    slots = build_pilot_meta()
    with open(META_PATH, "w") as fh:
        json.dump({"slots": slots}, fh, indent=2)
        fh.write("\n")
    print(f"pilot meta: {len(slots)} slots -> {META_PATH}")
    print(f"  Broad-Toned={sum(1 for s in slots if s['frame']=='Broad')}  "
          f"Doughy-Soft={sum(1 for s in slots if s['frame']=='Doughy')}  "
          f"teen={sum(1 for s in slots if s['age_mode']=='teen')}  "
          f"developed={sum(1 for s in slots if s['age_mode']=='developed')}")

    if not args.contact_sheet_only:
        bake(slots, force=args.force)
    contact_sheet(slots)


if __name__ == "__main__":
    main()
