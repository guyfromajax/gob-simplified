#!/usr/bin/env python3
"""
Assign every player a body archetype for portrait generation.

Reads scripts/players_export.json (produced by export_players_for_portraits.py)
and writes scripts/players_archetypes.csv with a 9-grid archetype per player:

    height band  x  build class
    -----------     -----------
    Short  (<72")   Lean   (bottom BMI tertile)
    Normal (72-78") Normal (middle BMI tertile)
    Tall   (>=79")  Strong (top BMI tertile)

Build is height-adjusted (BMI), so a tall lean player is not misread as strong.
Run export first (or with no export, it falls back to the bundled Chapel Hill
pilot roster so you can see the output shape immediately).

    python3 scripts/classify_player_archetypes.py
"""
import os
import csv
import json

HERE = os.path.dirname(os.path.abspath(__file__))
EXPORT = os.path.join(HERE, "players_export.json")

# Height band cutoffs (inches). Locked.
SHORT_MAX = 71          # <72  -> Short
TALL_MIN = 79           # >=79 -> Tall ; 72-78 -> Normal

# Build (BMI) tertile cutoffs. PROVISIONAL — replace with the real cutoffs the
# export script prints once you run it against the full population.
BUILD_LEAN_MAX = 25.0   # BMI <  25.0        -> Lean
BUILD_STRONG_MIN = 26.8  # BMI >= 26.8       -> Strong ; between -> Normal

# Prompt fragment injected per build class (drives shoulder framing so one
# uniform template per build class lands cleanly on every bust in that class).
BUILD_PROMPT = {
    "Lean":   "lean slim build, narrow shoulders, slender neck",
    "Normal": "athletic average build, medium shoulders",
    "Strong": "strong powerful build, broad wide shoulders, thick neck",
}

# Chapel Hill pilot roster (from the project brief) — fallback if no export yet.
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


def classify(p):
    h, w = p.get("height_in"), p.get("weight_lb")
    if not h or not w:
        return None
    bmi = 703 * w / (h ** 2)
    hb, bc = height_band(h), build_class(bmi)
    code = {"Short": "S", "Normal": "N", "Tall": "T"}[hb] + "-" + bc
    return {**p, "bmi": round(bmi, 1), "height_band": hb,
            "build_class": bc, "archetype": code,
            "build_prompt": BUILD_PROMPT[bc]}


def main():
    if os.path.exists(EXPORT):
        players = json.load(open(EXPORT))
        source = f"players_export.json ({len(players)})"
    else:
        players = PILOT
        source = "bundled Chapel Hill pilot roster (no export found)"
        print("[note] no players_export.json — using pilot roster. "
              "Run export_players_for_portraits.py for the full population.\n")

    rows = [r for r in (classify(p) for p in players) if r]
    print(f"[source] {source}")
    print(f"[build cutoffs] Lean<{BUILD_LEAN_MAX} | "
          f"Normal | Strong>={BUILD_STRONG_MIN}  (BMI)\n")

    grid = {}
    for r in rows:
        grid[r["archetype"]] = grid.get(r["archetype"], 0) + 1
    print("[9-grid counts]")
    for hb in ("Short", "Normal", "Tall"):
        cells = "  ".join(
            f"{hb[0]}-{bc}:{grid.get(hb[0]+'-'+bc, 0):>4}"
            for bc in ("Lean", "Normal", "Strong"))
        print("  " + cells)

    out = os.path.join(HERE, "players_archetypes.csv")
    cols = ["_id", "name", "jersey", "year", "height_in", "weight_lb",
            "bmi", "height_band", "build_class", "archetype", "build_prompt"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"\n[done] wrote {out} ({len(rows)} players)")


if __name__ == "__main__":
    main()
