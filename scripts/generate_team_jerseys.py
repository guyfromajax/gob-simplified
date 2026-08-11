#!/usr/bin/env python3
"""
Paint team jerseys onto approved busts via Nano Banana (Gemini image API).

For each player on a team, it edits the approved white-tank bust into the
team's jersey (colors + trim + wordmark), using the team's BANNER as the
branding reference — so the design matches real team branding. Output feeds
process_player_portraits.py (cutout -> color-lock -> crop).

Setup (run where you have the paid Gemini key + open network — your machine):
    pip install google-genai pillow
    # In AI Studio: "Get API key", then supply GEMINI_API_KEY in the invoking process.

    # ALWAYS test one player first to confirm the API call works:
    python3 scripts/generate_team_jerseys.py --team "Chapel Hill" --only "Stanley Keith"
    # then the whole team:
    python3 scripts/generate_team_jerseys.py --team "Chapel Hill"

Inputs (all in-repo):
  busts    tmp/portrait-pilot/raw/<Player Name>.<png|jpg>
  banner   FrontEnd/static/images/teams/<team_id>/<team_id>_banner_primary.jpg
  team     teams/128_teams.txt  (mascot -> wordmark, team_id -> banner folder)
Output:
  tmp/portrait-pilot/designed/<Player Name>.png
"""
import os
import re
import sys
import glob
import hashlib
import argparse

MODEL = "gemini-3.1-flash-lite-image"   # Nano Banana 2 Lite
INVERT_PCT = 10   # % of teams that render body=secondary for variety (seeded)

PROMPT = (
    "Two images are attached. The FIRST is a basketball player portrait. "
    "The SECOND is the team's branding banner (colors and wordmark reference). "
    "Redesign the player's jersey in the FIRST image so the MAIN JERSEY BODY is "
    "{primary_name}, with {secondary_name} trim around the neckline and "
    "armholes. Paint the team wordmark \"{wordmark}\" across the chest in "
    "{secondary_name}, in the same font and style as shown in the banner, "
    "screen-printed onto the fabric so it follows the folds and wrinkles. Do "
    "not add any number. Keep the player's face, skin tone, hair, body, and "
    "expression exactly the same. Plain light background."
)


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def color_name(hexstr):
    """A plain-English color name NB can act on (image models ignore hex)."""
    import colorsys
    r, g, b = hex2rgb(hexstr)
    h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
    hue = h * 360
    if s < 0.15:
        return "white" if v > 0.8 else "black" if v < 0.3 else "gray"
    fam = ("red" if hue < 15 or hue >= 345 else "orange" if hue < 45 else
           "gold" if hue < 70 else "green" if hue < 170 else "teal" if hue < 200
           else "blue" if hue < 255 else "purple" if hue < 290 else "magenta")
    mod = "light " if (v > 0.7 and s < 0.65) else "dark " if v < 0.45 else ""
    return f"{mod}{fam}"


def slug(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def team_info(team_name):
    """Return (mascot, team_id) for a team from 128_teams.txt."""
    want = slug(team_name)
    for line in open("teams/128_teams.txt"):
        parts = [p for p in re.split(r"\t+|\s{2,}", line.strip()) if p]
        if len(parts) < 4 or parts[1].lower() == "team":
            continue
        # columns: id, team, mascot, team_id, primary, secondary, ...
        name = parts[1]
        if slug(name) == want:
            mascot = parts[2]
            team_id = next((p for p in parts if re.match(r"[A-Z][A-Z_]+$", p)), None)
            hexes = [p for p in parts if re.match(r"#?[0-9a-fA-F]{6}$", p)]
            primary = hexes[0] if hexes else None
            secondary = hexes[1] if len(hexes) > 1 else None
            return mascot, team_id, primary, secondary
    return None, None, None, None


def load_body_overrides(path="scripts/jersey_body_overrides.txt"):
    """Return (force_swap, force_noswap) team_id sets.
       'TEAM_ID' forces body=secondary; '!TEAM_ID' forces body=primary."""
    force_swap, force_no = set(), set()
    if not os.path.exists(path):
        return force_swap, force_no
    for line in open(path):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("!"):
            force_no.add(line[1:].strip().upper())
        else:
            force_swap.add(line.upper())
    return force_swap, force_no


def should_swap(team_id, cli_swap):
    """Decide if a team's jersey body uses the SECONDARY color.
       Order: explicit overrides > CLI flag > deterministic INVERT_PCT roll."""
    tid = team_id.upper()
    force_swap, force_no = load_body_overrides()
    if tid in force_no:
        return False, "override:primary"
    if tid in force_swap:
        return True, "override:secondary"
    if cli_swap:
        return True, "--swap-colors"
    roll = int(hashlib.md5(tid.encode()).hexdigest(), 16) % 100
    return (roll < INVERT_PCT), f"seeded {roll}<{INVERT_PCT}"


def team_players(team_name):
    import json
    data = json.load(open("scripts/players_export.json"))
    return [p for p in data if slug(p.get("team", "")) == slug(team_name)]


def find_bust(name, raw_dir):
    for f in glob.glob(os.path.join(raw_dir, "*")):
        if slug(os.path.splitext(os.path.basename(f))[0]) == slug(name):
            return f
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True)
    ap.add_argument("--only", help="one player name, to test the API call first")
    ap.add_argument("--raw", default="tmp/portrait-pilot/raw")
    ap.add_argument("--out", default="tmp/portrait-pilot/designed")
    ap.add_argument("--swap-colors", action="store_true",
                    help="use the team's SECONDARY color as the jersey body")
    args = ap.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY not set in the invoking process. Get one in AI Studio.")
    try:
        from google import genai
        from PIL import Image
    except ImportError:
        sys.exit("missing deps. Run:  pip install google-genai pillow")

    mascot, team_id, primary_hex, secondary_hex = team_info(args.team)
    if not team_id:
        sys.exit(f"team '{args.team}' not found in teams/128_teams.txt")
    wordmark = (mascot or args.team).upper()
    swap, why = should_swap(team_id, args.swap_colors)
    if swap:
        primary_hex, secondary_hex = secondary_hex, primary_hex
        print(f"[note] jersey body = team SECONDARY color ({why})")
    primary_name = color_name(primary_hex)
    secondary_name = color_name(secondary_hex)
    banner = f"FrontEnd/static/images/teams/{team_id.lower()}/{team_id.lower()}_banner_primary.jpg"
    if not os.path.exists(banner):
        sys.exit(f"banner not found: {banner}")
    print(f"[team] {args.team}  wordmark={wordmark}  "
          f"body={primary_name} ({primary_hex})  trim={secondary_name} ({secondary_hex})")

    players = team_players(args.team)
    if args.only:
        players = [p for p in players if slug(p["name"]) == slug(args.only)]
    if not players:
        sys.exit("no matching players found")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    os.makedirs(args.out, exist_ok=True)
    banner_img = Image.open(banner)
    prompt = PROMPT.format(wordmark=wordmark, primary_name=primary_name,
                           secondary_name=secondary_name)

    ok = 0
    for p in players:
        name = p["name"]
        bust = find_bust(name, args.raw)
        if not bust:
            print(f"[skip] {name}: no bust in {args.raw}")
            continue
        try:
            resp = client.models.generate_content(
                model=MODEL, contents=[prompt, Image.open(bust), banner_img])
            saved = False
            for part in resp.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    out = os.path.join(args.out, f"{name}.png")
                    with open(out, "wb") as fh:
                        fh.write(part.inline_data.data)
                    print(f"[ok] {name} -> {out}")
                    saved = True
                    ok += 1
                    break
            if not saved:
                print(f"[fail] {name}: no image in response")
        except Exception as e:
            print(f"[fail] {name}: {type(e).__name__}: {str(e)[:200]}")
    print(f"\n[done] {ok}/{len(players)} designed -> {args.out}")


if __name__ == "__main__":
    main()
