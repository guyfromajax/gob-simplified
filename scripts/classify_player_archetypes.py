#!/usr/bin/env python3
"""
Assign every player a body archetype for portrait generation.

Two independent signals drive the body:

  SIZE  (from height + weight)            -> frame: Short/Normal/Tall x Lean/Normal/Big
  SHAPE (from attributes ST / AG / RT)    -> muscle-vs-fat: Cut / Solid / Soft

Weight tells you mass; the attributes tell you whether that mass is muscle or
fat. Two 240 lb bigs can be a chiseled athlete (high ST/RT) or a doughy backup
(low ST/AG/RT) — SHAPE separates them.

  height band     build (BMI)      athleticism (ST/AG/RT)
  -----------     -----------      ----------------------
  Short  (<72")   Lean  (BMI Q1)   Cut   (in shape, defined muscle)
  Normal (72-78") Normal(BMI mid)  Solid (average tone)          <- default
  Tall   (>=79")  Big   (BMI Q3)   Soft  (out of shape, carrying fat)

Uniform templates key on the BUILD axis only (~3). Athleticism is a prompt-only
modifier (it changes muscle definition / face fullness, not shoulder width), so
it gives body-composition variety without multiplying templates.

    python3 scripts/classify_player_archetypes.py
Reads scripts/players_export.json if present (needs st/ag/rt); otherwise falls
back to the bundled Chapel Hill pilot roster (no attributes -> SHAPE = n/a).
"""
import os
import csv
import json
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
EXPORT = os.path.join(HERE, "players_export.json")

# --- Height band cutoffs (inches). Locked. ---------------------------------
SHORT_MAX = 71          # <72  -> Short
TALL_MIN = 79           # >=79 -> Tall ; 72-78 -> Normal

# --- Build (BMI) tertile cutoffs. From the real 1,536-player population -----
# (export_players_for_portraits.py, gob-staging.players)
BUILD_LEAN_MAX = 25.5
BUILD_STRONG_MIN = 26.5

# --- Athleticism thresholds (ST/AG/RT). From Conf1 quartiles ---------------
# ST/AG ~ Q1 18 / Q3 65-71 ; RT ~ Q1 41 / Q3 79.
def athleticism(st, ag, rt):
    if st is None or ag is None or rt is None:
        return None                                   # no attributes exported
    if rt >= 75 or (st >= 65 and ag >= 45):
        return "Cut"
    if rt <= 45 and ag <= 30:
        return "Soft"
    return "Solid"

# Frame descriptor per build class (drives shoulder framing -> template fit).
FRAME_PROMPT = {
    "Lean":   "lean slim wiry frame, narrow athletic shoulders",
    "Normal": "average athletic frame, medium shoulders",
    "Big":    "big powerful frame, very broad wide shoulders filling the width of the frame, thick neck",
}
# Shape descriptor per athleticism class (muscle vs fat).
SHAPE_PROMPT = {
    "Cut":   "muscular cut physique, defined muscle, lean and in shape",
    "Solid": "average athletic build, some muscle tone",
    "Soft":  "soft doughy out-of-shape build, carrying extra body fat, undefined muscle, rounder fuller face",
}

# Expression pool (weighted; neutral/friendly common, intense rare). Picked
# deterministically per player from their UUID, so it's stable across runs but
# the roster gets a natural mix.
EXPRESSIONS = [
    ("calm neutral expression", 3),
    ("warm friendly smile", 3),
    ("confident slight smirk", 2),
    ("serious stoic expression", 2),
    ("relaxed easygoing look", 1),
    ("intense focused game-face", 1),
]
_EXPR_POOL = [phrase for phrase, w in EXPRESSIONS for _ in range(w)]


def pick_expression(pid):
    if not pid:
        return _EXPR_POOL[0]
    seed = int(hashlib.md5(str(pid).encode()).hexdigest(), 16)
    return _EXPR_POOL[seed % len(_EXPR_POOL)]

# Chapel Hill pilot roster (from brief). No attributes in the brief/backup, so
# SHAPE is left n/a here — the real values come from the export.
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


def height_band(h):
    if h <= SHORT_MAX:
        return "Short"
    if h >= TALL_MIN:
        return "Tall"
    return "Normal"


def build_class(bmi):
    if bmi < BUILD_LEAN_MAX:
        return "Lean"
    if bmi >= BUILD_STRONG_MIN:
        return "Strong"
    return "Normal"


# Map internal build class -> frame key (Strong build == Big frame).
_FRAME_KEY = {"Lean": "Lean", "Normal": "Normal", "Strong": "Big"}


def classify(p):
    h, w = p.get("height_in"), p.get("weight_lb")
    if not h or not w:
        return None
    bmi = 703 * w / (h ** 2)
    hb, bc = height_band(h), build_class(bmi)
    ath = athleticism(p.get("st"), p.get("ag"), p.get("rt"))
    code = {"Short": "S", "Normal": "N", "Tall": "T"}[hb] + "-" + bc
    frame = FRAME_PROMPT[_FRAME_KEY[bc]]
    if ath == "Soft" and bc == "Lean":
        # skinny + low-rated: soft/undefined, NOT carrying fat
        shape = "skinny and soft, undefined muscle, not athletic, soft facial features"
    elif ath:
        shape = SHAPE_PROMPT[ath]
    else:
        shape = "average athletic build, some muscle tone"
    body_prompt = f"{frame}, {shape}"
    return {**p, "bmi": round(bmi, 1), "height_band": hb, "build_class": bc,
            "athleticism": ath or "n/a", "archetype": code,
            "template": _FRAME_KEY[bc], "body_prompt": body_prompt,
            "expression": pick_expression(p.get("_id"))}


def main():
    if os.path.exists(EXPORT):
        players = json.load(open(EXPORT))
        source = f"players_export.json ({len(players)})"
    else:
        players = PILOT
        source = "bundled Chapel Hill pilot roster (no attributes -> SHAPE n/a)"
        print("[note] no players_export.json — using pilot roster. Run "
              "export_players_for_portraits.py to get ST/AG/RT and real SHAPE.\n")

    rows = [r for r in (classify(p) for p in players) if r]
    print(f"[source] {source}")
    print(f"[build cutoffs] Lean<{BUILD_LEAN_MAX} | Strong>={BUILD_STRONG_MIN} (BMI)")
    print(f"[shape cutoffs] Cut: RT>=75 or (ST>=65 & AG>=45) | "
          f"Soft: RT<=45 & AG<=30 | else Solid\n")

    grid = {}
    for r in rows:
        grid[r["archetype"]] = grid.get(r["archetype"], 0) + 1
    print("[size grid counts]")
    for hb in ("Short", "Normal", "Tall"):
        print("  " + "  ".join(
            f"{hb[0]}-{bc}:{grid.get(hb[0]+'-'+bc, 0):>4}"
            for bc in ("Lean", "Normal", "Strong")))
    shp = {}
    for r in rows:
        shp[r["athleticism"]] = shp.get(r["athleticism"], 0) + 1
    print(f"\n[athleticism counts] {shp}")

    out = os.path.join(HERE, "players_archetypes.csv")
    cols = ["_id", "name", "jersey", "year", "height_in", "weight_lb", "bmi",
            "st", "ag", "rt", "height_band", "build_class", "athleticism",
            "archetype", "template", "expression", "body_prompt"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"\n[done] wrote {out} ({len(rows)} players)")


if __name__ == "__main__":
    main()
