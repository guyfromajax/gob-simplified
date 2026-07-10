#!/usr/bin/env python3
"""
Apply team uniforms to raw white-tank busts (stage 2 of the pipeline).

Recolor-in-place: recolor each player's OWN white tank to the team's exact
colors (body = primary, trim = secondary) preserving the fabric folds, then
stamp the team wordmark (Bebas Neue Pro) across the chest in the secondary
color. Every player on a team is locked to the SAME exact hex, so the team is
perfectly consistent. Input = stage-1 busts; output feeds finishing (crop).

    python3 scripts/apply_team_uniforms.py --team "Durham"
    python3 scripts/apply_team_uniforms.py --only "Ricky Chang"
    python3 scripts/apply_team_uniforms.py --all

Inputs:  tmp/portrait-pilot/generated/<Name>.png
         teams/128_teams.txt  (mascot -> wordmark, primary/secondary hex)
         scripts/players_archetypes.csv  (team lookup)
         FrontEnd/static/fonts/BebasNeuePro-Bold.otf
Output:  tmp/portrait-pilot/uniformed/<Name>.png
"""
import os
import re
import csv
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FONT = "FrontEnd/static/fonts/BebasNeuePro-Bold.otf"
IN_DIR = "tmp/portrait-pilot/generated"
OUT_DIR = "tmp/portrait-pilot/uniformed"


def slug(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def team_info(team_name):
    """(mascot, team_id, primary_hex, secondary_hex) from 128_teams.txt."""
    want = slug(team_name)
    for line in open("teams/128_teams.txt"):
        parts = [p for p in re.split(r"\t+|\s{2,}", line.strip()) if p]
        if len(parts) < 6 or parts[1].lower() == "team":
            continue
        if slug(parts[1]) == want:
            mascot = parts[2]
            team_id = next((p for p in parts if re.match(r"[A-Z][A-Z_]+$", p)), None)
            hexes = [p for p in parts if re.match(r"#?[0-9a-fA-F]{6}$", p)]
            return mascot, team_id, hexes[0], hexes[1] if len(hexes) > 1 else "#ffffff"
    return None, None, None, None


def team_of(name, rows):
    for r in rows:
        if slug(r["name"]) == slug(name):
            return r.get("team")
    return None


# --- segmentation ----------------------------------------------------------
def person_alpha(src, np, ndimage):
    """Soft 0-255 person mask. Primary: u2net human-seg (semantic — robust to
    the white-tank-vs-light-background problem). Falls back to a flood-fill bg
    remover only if u2net is unavailable (proxy-blocked sandboxes)."""
    try:
        import process_player_portraits as fin
        return np.asarray(fin.segment_alpha(src))            # u2net, 0-255
    except Exception:
        a = np.asarray(src.convert("RGB")).astype(np.float32)
        c = 40
        cor = np.concatenate([a[:c, :c].reshape(-1, 3), a[:c, -c:].reshape(-1, 3),
                              a[-c:, :c].reshape(-1, 3), a[-c:, -c:].reshape(-1, 3)])
        bg = np.median(cor, 0)
        bgsim = np.sqrt(((a - bg) ** 2).sum(2)) < 38
        lbl, n = ndimage.label(bgsim)
        border = set(np.unique(lbl[0, :])) | set(np.unique(lbl[-1, :])) \
            | set(np.unique(lbl[:, 0])) | set(np.unique(lbl[:, -1]))
        border.discard(0)
        background = np.isin(lbl, list(border)) if border else np.zeros_like(bgsim)
        person = ndimage.binary_fill_holes(~background)
        return (person * 255).astype("uint8")


def _tank(a, person, np, ndimage):
    """White tank = the largest bright, low-saturation region inside the person,
    below the neck."""
    H = a.shape[0]
    bright = (a.min(2) > 168) & (a.max(2) - a.min(2) < 46)
    tank = bright & person
    tank[:int(0.42 * H)] = False
    tank = ndimage.binary_opening(tank, iterations=2)
    tank = ndimage.binary_closing(tank, iterations=5)        # bridge fold shadows
    lbl, n = ndimage.label(tank)
    if n >= 1:
        tank = lbl == (1 + int(np.argmax(
            ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1)))))
    return ndimage.binary_fill_holes(tank)


def _lum(a):
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]


def fit_font(draw, text, ImageFont, max_w, start=170):
    for size in range(start, 40, -6):
        f = ImageFont.truetype(FONT, size)
        b = draw.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= max_w:
            return f, b
    f = ImageFont.truetype(FONT, 46)
    return f, draw.textbbox((0, 0), text, font=f)


def apply_uniform(in_path, out_path, wordmark, primary, secondary):
    import numpy as np
    from scipy import ndimage
    from PIL import Image, ImageDraw, ImageFont

    src = Image.open(in_path).convert("RGB")
    a = np.asarray(src).astype(np.float32)
    H, W, _ = a.shape
    alpha = person_alpha(src, np, ndimage)                    # 0-255 person mask
    person = alpha > 128
    tank = _tank(a, person, np, ndimage)
    ys, xs = np.where(tank)
    if len(ys) == 0:
        raise ValueError("no tank found")
    top, bot = ys.min(), ys.max()
    cx = int((xs.min() + xs.max()) / 2)
    tone = np.clip(_lum(a) / 238.0, 0.55, 1.12)[..., None]     # preserve folds
    P = np.array(primary, np.float32)
    S = np.array(secondary, np.float32)

    out = a.copy()
    soft = ndimage.gaussian_filter(tank.astype(np.float32), 1.2)[..., None]
    out = out * (1 - soft) + (P[None, None, :] * tone) * soft

    # trim ring: collar + armholes (not the cropped bottom)
    rim = tank & ~ndimage.binary_erosion(tank, iterations=8)
    rim[int(bot - 6):] = False
    rimS = ndimage.gaussian_filter(rim.astype(np.float32), 0.6)[..., None]
    out = out * (1 - rimS) + (S[None, None, :] * tone) * rimS

    # wordmark across the chest, secondary color, tone-modulated onto fabric
    txt = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(txt)
    tank_w = xs.max() - xs.min()
    font, b = fit_font(d, wordmark, ImageFont, int(tank_w * 0.78))
    tx = cx - (b[2] - b[0]) // 2 - b[0]
    ty = top + int(0.34 * (bot - top)) - b[1]
    d.text((tx, ty), wordmark, fill=255, font=font)
    tm = (np.asarray(txt).astype(np.float32) / 255.0)[..., None]
    out = out * (1 - tm) + (S[None, None, :] * np.clip(tone * 1.05, 0.5, 1.15)) * tm

    # Output RGBA: recolored person on a transparent background (cutout done —
    # only cropping remains). Alpha is the u2net person mask.
    rgba = np.dstack([np.clip(out, 0, 255), alpha]).astype("uint8")
    Image.fromarray(rgba, "RGBA").save(out_path)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--only", help="one player name")
    g.add_argument("--team", help="one team")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--map", default="scripts/players_archetypes.csv")
    ap.add_argument("--in", dest="indir", default=IN_DIR)
    ap.add_argument("--out", dest="outdir", default=OUT_DIR)
    args = ap.parse_args()

    try:
        import numpy, scipy, PIL  # noqa: F401
    except ImportError:
        sys.exit("missing deps. Run:  pip install pillow numpy scipy")
    if not os.path.exists(FONT):
        sys.exit(f"font not found: {FONT}")

    rows = list(csv.DictReader(open(args.map)))
    if args.only:
        sel = [r for r in rows if slug(r["name"]) == slug(args.only)]
    elif args.team:
        sel = [r for r in rows if slug(r.get("team", "")) == slug(args.team)]
    else:
        sel = rows
    if not sel:
        sys.exit("no matching players")

    os.makedirs(args.outdir, exist_ok=True)
    team_cache = {}
    ok = miss = 0
    for r in sel:
        team = r.get("team")
        if team not in team_cache:
            mascot, tid, prim, sec = team_info(team)
            team_cache[team] = (mascot, prim, sec)
        mascot, prim, sec = team_cache[team]
        if not prim:
            print(f"[skip] {r['name']}: team '{team}' not in 128_teams.txt")
            continue
        in_path = os.path.join(args.indir, f"{r['name']}.png")
        if not os.path.exists(in_path):
            print(f"[miss] {r['name']}: no raw bust in {args.indir}")
            miss += 1
            continue
        out_path = os.path.join(args.outdir, f"{r['name']}.png")
        wordmark = (mascot or team).upper()
        try:
            apply_uniform(in_path, out_path, wordmark, hex2rgb(prim), hex2rgb(sec))
            print(f"[ok] {r['name']}  {team} ({wordmark}, {prim}/{sec})")
            ok += 1
        except Exception as e:
            print(f"[fail] {r['name']}: {type(e).__name__}: {str(e)[:150]}")
    print(f"\n[done] {ok} uniformed, {miss} missing -> {args.outdir}")


if __name__ == "__main__":
    main()
