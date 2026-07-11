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
import re
import csv
import json
import hashlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from player_ethnicity import assign_ethnicity   # noqa: E402

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


# Muscle-tone "re-roll": mostly stat-driven, but a UUID-seeded 10% nudges it for
# variety. Single seeded check (not an actual double roll). Cut<->Toned swap;
# Soft eases to Toned. Doughy is exempt (its Soft is part of the body, pinned).
DEF_REROLL = {"Cut": "Toned", "Toned": "Cut", "Soft": "Toned"}
DEF_REROLL_PCT = 10


def reroll_definition(defi, pid):
    if not defi:
        return defi
    seed = int(hashlib.md5(f"{pid}|muscle".encode()).hexdigest(), 16)
    if seed % 100 < DEF_REROLL_PCT:
        return DEF_REROLL[defi]
    return defi


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


# --- HAIR (race-correlated, UUID-seeded) -----------------------------------
HAIR = {
    "black": [("a short black fade", 4), ("a short buzz cut", 2),
              ("a short afro", 3), ("a rounded medium afro", 2),
              ("short dreadlocks", 2), ("shoulder-length dreadlocks", 1),
              ("cornrows", 2), ("box braids", 1), ("short twists", 1),
              ("a high-top fade", 1), ("a taper fade with a line-up", 2),
              ("a curly sponge top", 1), ("waves with a low fade", 2),
              ("an afro with a fade", 1), ("flat twists", 1),
              ("a mini afro puff top", 1), ("a clean-shaved bald head", 2),
              ("a temple fade with short curls", 1),
              ("a big voluminous curly top", 2),
              ("a tall boxy hi-top fade", 1),
              ("a high skin fade shaved to the base with a thick block of hair on top", 2)],
    "white": [("short brown hair", 3), ("a short buzz cut", 1),
              ("wavy brown hair", 2), ("curly brown hair", 2),
              ("messy medium brown hair", 2), ("short blonde hair", 1),
              ("wavy blonde hair", 1), ("spiky brown hair", 1),
              ("slicked-back dark hair", 1), ("short auburn hair", 1),
              ("a textured crop with fringe", 2), ("a modern undercut", 2),
              ("a mid-length wavy mop", 1), ("tousled sandy-blond hair", 1),
              ("a side-part with short sides", 1), ("a crew cut", 1),
              ("shaggy light-brown hair", 1), ("short ginger hair", 1),
              ("a side-swept blond quiff with tapered sides", 2),
              ("a side-swept dark-brown quiff with tapered sides", 2),
              ("a side-swept ginger quiff with tapered sides", 1),
              ("short neatly side-parted dark-brown hair", 2),
              ("a brown mullet, short on top and long in the back", 1),
              ("a blond mullet, short on top and long in the back", 1),
              ("a modern mullet with faded sides", 1),
              ("a clean-shaved bald head", 1),
              ("a high skin fade with a thick block of hair on top", 1)],
    "asian": [("short straight black hair", 3), ("a black undercut", 2),
              ("spiky black hair", 1), ("medium straight black hair", 1),
              ("a neat black bowl cut", 1), ("a textured fringe crop", 2),
              ("a two-block cut", 2), ("a middle-part curtain cut", 1),
              ("a short black crew cut", 1), ("a soft-perm short cut", 1),
              ("a slicked-back undercut", 1),
              ("a high skin fade shaved to the base with a thick block of hair on top", 2),
              ("a clean-shaved bald head", 1)],
    "hispanic": [("a short black fade", 3), ("a short black crop", 2),
                 ("wavy black hair", 2), ("curly black hair", 2),
                 ("slicked-back black hair", 1), ("a textured crop with fringe", 2),
                 ("a mid fade with curls on top", 2), ("a taper fade with a line-up", 1),
                 ("short wavy dark-brown hair", 1), ("a comb-over fade", 1),
                 ("a clean-shaved bald head", 1),
                 ("a high skin fade with a thick block of hair on top", 1),
                 ("a side-swept dark quiff with tapered sides", 1)],
    "ambiguous": [("a short fade", 2), ("short curly brown hair", 2),
                  ("wavy dark hair", 2), ("a short crop", 1),
                  ("a textured crop with fringe", 1), ("a taper fade", 1),
                  ("medium curly dark hair", 1), ("a short afro-textured cut", 1),
                  ("a big voluminous curly top", 1), ("a clean-shaved bald head", 1),
                  ("a high skin fade with a thick block of hair on top", 1)],
}
# pale/Scandinavian players lean blonde/fair.
HAIR_PALE = [("short blonde hair", 3), ("wavy blonde hair", 2),
             ("short light-brown hair", 2), ("short red hair", 1),
             ("a short buzz cut", 1), ("a tousled blond crop", 2),
             ("a blond undercut", 1), ("strawberry-blond waves", 1),
             ("a blond side-part", 1),
             ("a side-swept blond quiff with tapered sides", 2),
             ("a blond mullet, short on top and long in the back", 1),
             ("a clean-shaved bald head", 1)]


def _weighted(pool, seed):
    flat = [x for x, w in pool for _ in range(w)]
    return flat[seed % len(flat)]


def pick_hair(pid, race, skin):
    seed = int(hashlib.md5(f"{pid}|hair".encode()).hexdigest(), 16)
    if skin == "white-pale":
        return _weighted(HAIR_PALE, seed)
    if race == "other":
        return _weighted(HAIR[skin], seed)          # asian / hispanic / ambiguous
    return _weighted(HAIR[race], seed)              # black / white


# --- FACIAL GEOMETRY (the identity driver) ---------------------------------
# Structural features are race-INDEPENDENT; the ethnicity-linked ones (eyes /
# nose / lips) are PROBABILISTICALLY weighted by race — the typical feature is
# more likely but not guaranteed, so real within-group variation survives. We
# emit ~5 strong descriptors (NB averages away over-specification), which is what
# pushes each player into a DIFFERENT face rather than a per-attribute clone.
FACE_SHAPE = [("an oval", 4), ("a round", 3), ("a square", 3), ("a long oval", 3),
              ("a rectangular", 2), ("a heart-shaped", 2), ("a diamond-shaped", 1)]
JAW = [("a strong wide jaw", 3), ("a soft rounded jaw", 3), ("a narrow tapered jaw", 3),
       ("a sharp angular jaw", 3), ("a broad square jaw", 2), ("a slightly weak jaw", 1)]
CHEEKS = [("high prominent cheekbones", 3), ("flat cheeks", 3), ("full round cheeks", 3),
          ("wide cheekbones", 2), ("hollow cheeks", 2)]

# race-weighted (probabilistic, not absolute)
EYES = {
    "black": [("almond-shaped eyes", 3), ("round eyes", 2), ("wide-set eyes", 2),
              ("deep-set eyes", 1), ("hooded eyes", 1)],
    "white": [("almond-shaped eyes", 2), ("round eyes", 2), ("deep-set eyes", 2),
              ("hooded eyes", 2), ("close-set eyes", 1), ("downturned eyes", 1)],
    "asian": [("monolid eyes", 4), ("almond-shaped eyes", 2), ("round eyes", 1),
              ("slightly hooded eyes", 1)],
    "hispanic": [("almond-shaped eyes", 3), ("round eyes", 2), ("deep-set eyes", 2),
                 ("hooded eyes", 1)],
    "ambiguous": [("almond-shaped eyes", 3), ("round eyes", 2), ("hooded eyes", 1),
                  ("monolid eyes", 1)],
}
NOSE = {
    "black": [("a broad nose", 3), ("a wide-bridged nose", 2), ("a rounded nose", 2),
              ("a straight nose", 1)],
    "white": [("a straight narrow nose", 3), ("a straight nose", 2),
              ("an aquiline nose", 1), ("a small upturned nose", 1)],
    "asian": [("a straight nose", 2), ("a small button nose", 2),
              ("a low-bridged nose", 2), ("a broad nose", 1)],
    "hispanic": [("a straight nose", 2), ("a broad nose", 1), ("an aquiline nose", 1),
                 ("a straight narrow nose", 1)],
    "ambiguous": [("a straight nose", 2), ("a broad nose", 1), ("a rounded nose", 1)],
}
LIPS = {
    "black": [("full lips", 3), ("wide lips", 2), ("well-defined lips", 1)],
    "white": [("thin lips", 2), ("medium lips", 3), ("well-defined lips", 1),
              ("full lips", 1)],
    "asian": [("medium lips", 3), ("thin lips", 1), ("full lips", 1)],
    "hispanic": [("full lips", 2), ("medium lips", 2), ("well-defined lips", 1)],
    "ambiguous": [("medium lips", 2), ("full lips", 1), ("thin lips", 1)],
}
# distinctive marks — always-visible imperfections, ~1 in 3 players gets one
MARKS = [("a light spray of freckles across the nose and cheeks", 3),
         ("a small mole on one cheek", 2), ("a faint scar through one eyebrow", 2),
         ("slightly protruding ears", 2), ("a subtly crooked nose", 2),
         ("a strong prominent brow", 2), ("faint under-eye shadows", 1),
         ("mild facial asymmetry", 1), ("a small beauty mark near the lip", 1)]
MARK_PCT = 33


def _race_key(race, skin):
    if race == "other":
        return skin if skin in EYES else "ambiguous"
    return race if race in EYES else "ambiguous"


def pick_face(pid, race, skin):
    """Assemble ~5 strong facial-geometry descriptors, seeded per player."""
    rk = _race_key(race, skin)

    def g(pool, salt):
        return _weighted(pool, int(hashlib.md5(f"{pid}|{salt}".encode()).hexdigest(), 16))

    shape = g(FACE_SHAPE, "faceshape")
    jaw = g(JAW, "jaw")
    cheeks = g(CHEEKS, "cheeks")
    eyes = g(EYES[rk], "eyes")
    nose = g(NOSE[rk], "nose")
    lips = g(LIPS[rk], "lips")
    face = (f"He has {shape} face with {jaw}, {cheeks}, {nose}, {eyes}, and {lips}.")
    mseed = int(hashlib.md5(f"{pid}|mark".encode()).hexdigest(), 16)
    if mseed % 100 < MARK_PCT:
        face += f" He has {g(MARKS, 'markpick')}."
    return face


# --- ACCESSORIES (sparse, each rolled independently) -----------------------
# Eyewear is a single either/or slot; headband / earring / tattoo roll
# independently and can stack. Headband color can key off team colors, so the
# classifier resolves the team's hex to a color name (below).
HEADBAND = [("black", 3), ("white", 3), ("team-primary", 2), ("team-secondary", 2)]
EYEWEAR = [("clear sports goggles", 3), ("black-framed sports goggles", 2),
           ("smoke-tinted sports goggles", 1), ("thin black-framed glasses", 2),
           ("clear-framed glasses", 1)]
EARRING = [("a small diamond stud earring", 3), ("a large diamond stud earring", 1),
           ("a small hoop earring", 2)]
ACC_RATES = {"headband": 10, "eyewear": 8, "earring": 3,
             "tattoo_sleeve": 3, "tattoo_neck": 0.3}

_NAMED_COLORS = [
    ("black", (0, 0, 0)), ("white", (255, 255, 255)), ("navy", (26, 42, 74)),
    ("royal blue", (36, 90, 190)), ("light blue", (135, 181, 230)),
    ("red", (200, 30, 45)), ("maroon", (110, 30, 45)), ("orange", (230, 120, 30)),
    ("gold", (200, 165, 70)), ("yellow", (240, 215, 60)), ("green", (20, 120, 60)),
    ("dark green", (15, 60, 45)), ("teal", (0, 140, 145)), ("purple", (90, 45, 140)),
    ("gray", (150, 150, 150)), ("silver", (200, 200, 205)), ("brown", (90, 58, 27)),
    ("cream", (240, 230, 210)),
]


def _hex_to_name(h):
    if not h:
        return "team-colored"
    h = h.lstrip("#")
    try:
        rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return "team-colored"
    return min(_NAMED_COLORS, key=lambda c: sum((a - b) ** 2 for a, b in zip(rgb, c[1])))[0]


def pick_accessories(pid, year, primary_hex=None, secondary_hex=None):
    out = []

    def roll(salt, pct):
        return int(hashlib.md5(f"{pid}|{salt}".encode()).hexdigest(), 16) % 1000 < pct * 10

    # noun-form phrases so they read cleanly after "He has ..." in the prompt
    if roll("headband", ACC_RATES["headband"]):
        choice = _weighted(HEADBAND, int(hashlib.md5(f"{pid}|hbcolor".encode()).hexdigest(), 16))
        color = {"team-primary": _hex_to_name(primary_hex),
                 "team-secondary": _hex_to_name(secondary_hex)}.get(choice, choice)
        out.append(f"a {color} headband")
    if roll("eyewear", ACC_RATES["eyewear"]):
        out.append(_weighted(EYEWEAR, int(hashlib.md5(f"{pid}|eyewear".encode()).hexdigest(), 16)))
    if roll("earring", ACC_RATES["earring"]):
        out.append(_weighted(EARRING, int(hashlib.md5(f"{pid}|earring".encode()).hexdigest(), 16)))
    if roll("tattoo_sleeve", ACC_RATES["tattoo_sleeve"]):
        out.append("a tattoo sleeve on one arm")
    if roll("tattoo_neck", ACC_RATES["tattoo_neck"]):
        out.append("a small neck tattoo")
    # light facial hair only for older players (juniors/seniors); no face piercings
    if str(year).lower() in ("junior", "senior"):
        seed = int(hashlib.md5(f"{pid}|facialhair".encode()).hexdigest(), 16)
        if seed % 100 < 15:
            out.append(_weighted([("light stubble", 3), ("a thin mustache", 1)], seed))
    return ", ".join(out)


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


_TEAM_COLORS = None


def team_colors(team):
    """(primary_hex, secondary_hex) for a team from teams/128_teams.txt."""
    global _TEAM_COLORS
    if _TEAM_COLORS is None:
        _TEAM_COLORS = {}
        path = os.path.join(HERE, "..", "teams", "128_teams.txt")
        if os.path.exists(path):
            for line in open(path):
                parts = [p for p in re.split(r"\t+|\s{2,}", line.strip()) if p]
                if len(parts) < 6 or parts[1].lower() == "team":
                    continue
                hexes = [p for p in parts if re.match(r"#?[0-9a-fA-F]{6}$", p)]
                if hexes:
                    key = re.sub(r"[^a-z0-9]", "", parts[1].lower())
                    _TEAM_COLORS[key] = (hexes[0], hexes[1] if len(hexes) > 1 else None)
    return _TEAM_COLORS.get(re.sub(r"[^a-z0-9]", "", str(team).lower()), (None, None))


def build_class(bmi):
    if bmi < BUILD_LEAN_MAX:
        return "Lean"
    if bmi >= BUILD_BROAD_MIN:
        return "Broad"
    return "Normal"


def frame_of(height, weight, bmi, defi, st):
    """Resolve the FRAME (reference body) from size + definition."""
    base = build_class(bmi)
    short = height is not None and height <= SHORT_MAX
    # Mass override: genuinely huge + strong players are Broad even if their BMI
    # reads low (tall players get under-rated by BMI). Catches 7-footers. But
    # ONLY for tall players — a short + strong guy reads compact/cut, not broad,
    # so his strength shows up as a Cut build on a smaller frame instead.
    if not short and weight is not None and st is not None \
            and weight >= BROAD_WEIGHT_MIN and st >= BROAD_STRENGTH_MIN:
        return "Broad"
    # Doughy: heavy + soft + not strong reads as fat, not powerful.
    if defi == "Soft" and bmi >= BUILD_BROAD_MIN and (st is not None and st < DOUGHY_STRENGTH_MAX):
        return "Doughy"
    if short:
        # short + would-be-Broad (heavy/strong) -> compact Normal, not broad.
        if base == "Broad":
            return "Normal"
        # short + genuinely strong reads as a compact Normal build; short +
        # not-strong (or lean) stays a small Slight frame. Either way high ST
        # still shows through as a Cut definition.
        strong = st is not None and st >= BROAD_STRENGTH_MIN
        if base == "Normal" and strong:
            return "Normal"
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
    # (Its Soft is part of the body, so it's exempt from the re-roll.)
    if frame == "Doughy":
        defi = "Soft"
    else:
        defi = reroll_definition(defi, p.get("_id"))
    body_prompt = FRAME_PROMPT[frame]
    if defi and frame != "Doughy":
        body_prompt = f"{body_prompt}, {DEFINITION_PROMPT[defi]}"
    archetype = frame if frame == "Doughy" else f"{frame}-{defi or 'Toned'}"
    # Race / skin tone (name-override + weighted random; names drive the mix).
    eth = assign_ethnicity(p.get("first_name"), p.get("last_name"), p.get("_id"))
    prim, sec = team_colors(p.get("team"))
    hair = pick_hair(p.get("_id"), eth["race"], eth["skin"])
    # very rare (0.1%): hair dyed the team's primary color (e.g. Antoine Ellington)
    if int(hashlib.md5(f"{p.get('_id')}|hairdye".encode()).hexdigest(), 16) % 1000 < 1:
        hair = f"{hair}, dyed {_hex_to_name(prim)}"
    return {**p, "bmi": round(bmi, 1), "frame": frame,
            "definition": defi or "n/a", "archetype": archetype,
            "template": frame, "body_prompt": body_prompt,
            "expression": pick_expression(p.get("_id")),
            "race": eth["race"], "skin": eth["skin"],
            "ethnicity": eth["ethnicity_label"], "skin_prompt": eth["skin_prompt"],
            "hair": hair,
            "face_prompt": pick_face(p.get("_id"), eth["race"], eth["skin"]),
            "accessories": pick_accessories(p.get("_id"), p.get("year"), prim, sec)}


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
    cols = ["_id", "name", "team", "jersey", "year", "height_in", "weight_lb", "bmi",
            "st", "ag", "rt", "frame", "definition", "archetype", "template",
            "race", "skin", "ethnicity", "expression", "hair", "face_prompt",
            "accessories", "body_prompt", "skin_prompt"]
    with open(out, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(rows)
    print(f"\n[done] wrote {out} ({len(rows)} players)")


if __name__ == "__main__":
    main()
