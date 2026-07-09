#!/usr/bin/env python3
"""
Assign every player a body archetype for portrait generation.

TWO INDEPENDENT AXES:

  FRAME  (skeleton width + size)      -> the reference BODY (5 of them)
  DEFINITION (muscle vs fat)          -> a prompt-only MODIFIER (3 levels)

  FRAME comes from height + weight (BMI); DEFINITION comes from attributes
  (ST/AG/RT). Weight tells you mass; the attributes tell you whether that mass
  is muscle or fat. The two axes are orthogonal — a Broad frame can be Cut,
  Toned, or Soft — EXCEPT Doughy, which is defined by fat and is therefore
  pinned to Soft (you cannot be round-with-fat AND cut-with-no-fat).

  FRAME (reference body)          DEFINITION (prompt modifier)
  --------------------            ----------------------------
  Slight  small/short frame       Cut    defined muscle, low fat
  Lean    slim wiry               Toned  average tone (default)
  Normal  average athletic        Soft   undefined, carrying fat
  Broad   wide, powerful
  Doughy  soft rounded  (Soft only, terminal type)

Only 5 reference bodies are generated. DEFINITION is applied per-player at
generation time as a prompt tweak on top of the frame's reference body.

Routing:
  DEFINITION: Cut if rt>=75 or (st>=65 & ag>=45); Soft if rt<=45 & ag<=30; else Toned
  FRAME base (BMI): Lean<25.5 | Broad>=26.5 | Normal between
    -> Doughy  if Soft AND bmi>=26.5 AND st<55   (heavy + soft + not strong = fat, not powerful)
    -> Slight  if height<=69 AND base build is Lean/Normal (short broad guys stay Broad)
    -> else the base build

    python3 scripts/classify_player_archetypes.py
Reads scripts/players_export.json if present (needs st/ag/rt); otherwise falls
back to the bundled Chapel Hill pilot roster (no attributes -> DEFINITION n/a).
"""
import os
import csv
import json
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
EXPORT = os.path.join(HERE, "players_export.json")

# --- FRAME cutoffs ----------------------------------------------------------
SHORT_MAX = 69           # <=69" (<=5'9") + lean/normal build -> Slight
BUILD_LEAN_MAX = 25.5    # BMI tertiles from the 1,536-player population
BUILD_BROAD_MIN = 26.5
DOUGHY_STRENGTH_MAX = 55  # heavy+soft below this ST reads fat (not powerful)
# Mass override: BMI under-rates very tall players (a 7'0" 260 lb monster reads
# Normal by BMI). Force Broad for anyone genuinely huge + strong, regardless.
BROAD_WEIGHT_MIN = 235   # lb
BROAD_STRENGTH_MIN = 65


# --- DEFINITION axis (muscle vs fat), from ST/AG/RT ------------------------
def definition(st, ag, rt):
    if st is None or ag is None or rt is None:
        return None
    if rt >= 75 or (st >= 65 and ag >= 45):
        return "Cut"
    if rt <= 45 and ag <= 30:
        return "Soft"
    return "Toned"


# FRAME descriptor -> drives the reference body silhouette.
FRAME_PROMPT = {
    "Slight": "small slight frame, narrow shoulders, thin neck, youthful build, "
              "head slightly large for the frame",
    "Lean":   "lean slim wiry frame, narrow athletic shoulders",
    "Normal": "average athletic frame, medium shoulders",
    "Broad":  "big powerful frame, very broad wide shoulders filling the width "
              "of the frame, thick neck",
    "Doughy": "soft rounded heavyset frame, sloping shoulders, full torso, "
              "thick soft neck, fuller rounder face",
}
# DEFINITION descriptor -> muscle-vs-fat modifier layered on the frame.
DEFINITION_PROMPT = {
    "Cut":   "cut and defined, visible muscle tone, low body fat, in shape",
    "Toned": "average muscle tone, athletic but not chiseled",
    "Soft":  "soft and undefined, carrying some extra body fat, fuller face",
}

# Expression pool (weighted; neutral/friendly common, extremes rare). Distilled
# from a 29-face Conf1 reference set — 10 distinct expressions from a big
# beaming grin all the way to a menacing glare. Picked deterministically per
# player from their UUID -> stable across runs, natural roster-wide mix.
EXPRESSIONS = [
    ("a calm neutral expression, relaxed", 4),
    ("a warm friendly smile, slight teeth, relaxed eyes", 3),
    ("a subtle pleasant closed-mouth smile", 3),
    ("a cheerful open smile with teeth, bright happy eyes", 2),
    ("a confident one-sided smirk, self-assured", 2),
    ("a composed stoic expression, mouth closed, no smile", 2),
    ("a big beaming open-mouth grin, teeth showing, joyful", 1),
    ("a stern hard expression, slight scowl, intense", 1),
    ("an intense focused game-face, locked-in wide eyes", 1),
    ("a menacing hostile glare, furrowed brow, cold hard stare", 1),
]
_EXPR_POOL = [phrase for phrase, w in EXPRESSIONS for _ in range(w)]


def pick_expression(pid):
    if not pid:
        return _EXPR_POOL[0]
    seed = int(hashlib.md5(str(pid).encode()).hexdigest(), 16)
    return _EXPR_POOL[seed % len(_EXPR_POOL)]


# Chapel Hill pilot roster (from brief). No attributes here -> DEFINITION n/a;
# the real values come from the export.
PILOT = [
    {"_id": "86b911a5-c022-4041-aefd-175a0e1f2acf", "name": "Stanley Keith",    "jersey": 4,  "height_in": 73, "weight_lb": 206, "year": "sophomore"},
    {"_id": "ac26dbe2-e590-49aa-9bde-745584e548f9", "name": "Landon Turley",    "jersey": 10, "height_in": 70, "weight_lb": 167, "year": "junior"},
    {"_id": "f8b7f7b5-bd62-420a-a31e-08ae8c95fb93", "name": "Brice Monroe Jr",  "jersey": 11, "height_in": 73, "weight_lb": 192, "year": "freshman"},
    {"_id": "da3e79a7-5fec-46d4-b847-bdf2870e1fe8", "name": "Otis Nixon",       "jersey": 17, "height_in": 68, "weight_lb": 159, "year": "junior"},
    {"_id": "5a27f1b1-ba4a-417e-bd83-45abd8ef5829", "name": "Nathan Randolph",  "jersey": 25, "height_in": 72, "weight_lb": 200, "year": "junior"},
    {"_id": "99f962c5-3624-4082-a420-916f7999241f", "name": "Colt Robles",      "jersey": 27, "height_in": 70, "weight_lb": 167, "year": "sophomore"},
    {"_id": "e297fdab-a3da-45d0-af00-1742e371915d", "name": "Dale Butler",      "jersey": 30, "height_in": 68, "weight_lb": 175, "year": "sophomore"},
    {"_id": "d5e6f137-86ff-4c0b-9e5b-5afd094826d5", "name": "Shorty Holmstrom", "jersey": 31, "height_in": 74, "weight_lb": 205, "year": "senior"},
    {"_id": "d8b1e862-fbee-44f7-b8b9-160531c0b8df", "name": "Thanh Small",      "jersey": 32, "height_in": 77, "weight_lb": 235, "year": "freshman"},
    {"_id": "c642adfa-692a-4f3f-8e3a-6401543c7a45", "name": "Dayton Weber",     "jersey": 34, "height_in": 70, "weight_lb": 169, "year": "sophomore"},
    {"_id": "eb149eb8-bb89-4d90-8779-e02f1bd6d6d5", "name": "Eugene Johnston",  "jersey": 46, "height_in": 79, "weight_lb": 238, "year": "freshman"},
    {"_id": "05f93933-514a-4a4e-805e-c76ba8c12dfa", "name": "Darren Parrish",   "jersey": 55, "height_in": 73, "weight_lb": 200, "year": "senior"},
]


def build_class(bmi):
    if bmi < BUILD_LEAN_MAX:
        return "Lean"
    if bmi >= BUILD_BROAD_MIN:
        return "Broad"
    return "Normal"


def frame_of(height, weight, bmi, defi, st):
    """Resolve the FRAME (reference body) from size + definition."""
    base = build_class(bmi)
    # Mass override: genuinely huge + strong players are Broad even if their
    # BMI reads low (tall players get under-rated by BMI). Catches 7-footers.
    if weight is not None and st is not None \
            and weight >= BROAD_WEIGHT_MIN and st >= BROAD_STRENGTH_MIN:
        return "Broad"
    # Doughy: heavy + soft + not strong reads as fat, not powerful.
    if defi == "Soft" and bmi >= BUILD_BROAD_MIN and (st is not None and st < DOUGHY_STRENGTH_MAX):
        return "Doughy"
    # Slight: short lean/normal frame reads small (short broad guys stay Broad).
    if height <= SHORT_MAX and base in ("Lean", "Normal"):
        return "Slight"
    return base


def classify(p):
    h, w = p.get("height_in"), p.get("weight_lb")
    if not h or not w:
        return None
    bmi = 703 * w / (h ** 2)
    defi = definition(p.get("st"), p.get("ag"), p.get("rt"))
    frame = frame_of(h, w, bmi, defi, p.get("st"))
    # Doughy is a terminal type: pinned to Soft regardless of the raw axis.
    if frame == "Doughy":
        defi = "Soft"
    body_prompt = FRAME_PROMPT[frame]
    if defi and frame != "Doughy":
        body_prompt = f"{body_prompt}, {DEFINITION_PROMPT[defi]}"
    archetype = frame if frame == "Doughy" else f"{frame}-{defi or 'Toned'}"
    return {**p, "bmi": round(bmi, 1), "frame": frame,
            "definition": defi or "n/a", "archetype": archetype,
            "template": frame, "body_prompt": body_prompt,
            "expression": pick_expression(p.get("_id"))}


def main():
    if os.path.exists(EXPORT):
        players = json.load(open(EXPORT))
        source = f"players_export.json ({len(players)})"
    else:
        players = PILOT
        source = "bundled Chapel Hill pilot roster (no attributes -> DEFINITION n/a)"
        print("[note] no players_export.json — using pilot roster. Run "
              "export_players_for_portraits.py to get ST/AG/RT and real DEFINITION.\n")

    rows = [r for r in (classify(p) for p in players) if r]
    print(f"[source] {source}")
    print(f"[frame cutoffs] Slight: h<={SHORT_MAX} & lean/normal | "
          f"Lean<{BUILD_LEAN_MAX} BMI | Broad>={BUILD_BROAD_MIN} BMI | "
          f"Doughy: soft & BMI>={BUILD_BROAD_MIN} & ST<{DOUGHY_STRENGTH_MAX}")
    print(f"[definition] Cut: RT>=75 or (ST>=65 & AG>=45) | "
          f"Soft: RT<=45 & AG<=30 | else Toned\n")

    frames = {}
    for r in rows:
        frames[r["frame"]] = frames.get(r["frame"], 0) + 1
    print("[FRAME counts]")
    for fr in ("Slight", "Lean", "Normal", "Broad", "Doughy"):
        n = frames.get(fr, 0)
        print(f"  {fr:<7} {n:>4}  ({100*n/len(rows):4.1f}%)")

    defs = {}
    for r in rows:
        defs[r["definition"]] = defs.get(r["definition"], 0) + 1
    print(f"\n[DEFINITION counts] {defs}")

    print("\n[FRAME x DEFINITION grid]")
    print(f"  {'':<8}{'Cut':>6}{'Toned':>7}{'Soft':>6}")
    for fr in ("Slight", "Lean", "Normal", "Broad", "Doughy"):
        cells = {d: sum(1 for r in rows if r["frame"] == fr and r["definition"] == d)
                 for d in ("Cut", "Toned", "Soft")}
        print(f"  {fr:<8}{cells['Cut']:>6}{cells['Toned']:>7}{cells['Soft']:>6}")

    out = os.path.join(HERE, "players_archetypes.csv")
    cols = ["_id", "name", "jersey", "year", "height_in", "weight_lb", "bmi",
            "st", "ag", "rt", "frame", "definition", "archetype", "template",
            "expression", "body_prompt"]
    with open(out, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n[done] wrote {out} ({len(rows)} players)")


if __name__ == "__main__":
    main()
