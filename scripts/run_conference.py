#!/usr/bin/env python3
"""
Run a whole conference through the portrait pipeline (stage 1-3), resumably, with
per-team QC sheets and bad-frame detection. Does NOT upload — upload is a separate,
QC-gated step (stage_r2_upload.py + upload_player_images_to_r2.py).

Per team, in order (each stage is skip-if-done on its own):
  1. generate_player_portraits.py  (Nano Banana white-tank busts)   [needs GEMINI key]
  2. flag bad/blank NB frames for re-roll
  3. apply_team_uniforms.py         (recolor + designed wordmark)   [needs u2net]
  4. finish_portraits.py            (UUID masters -> assets_staging/players)
  5. per-team QC contact sheet -> tmp/portrait-pilot/qc/conf<N>_<slug>.png
  6. progress -> scripts/conf_status.csv

Run on your machine (GEMINI key + u2net). Resume anytime — it only does what's missing.

    python3 scripts/run_conference.py --conference 3
    python3 scripts/run_conference.py --team "Concord"          # one team
    python3 scripts/run_conference.py --conference 3 --qc-only  # just rebuild sheets
    python3 scripts/run_conference.py --conference 3 --no-generate   # busts already exist

Conference->team map: tmp/team-logo-pipeline/team-logo-manifest.json (clean, 8/conf).
"""
import os
import re
import csv
import sys
import json
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
MANIFEST = "tmp/team-logo-pipeline/team-logo-manifest.json"
ARCHETYPES = "scripts/players_archetypes.csv"
GEN_DIR = "tmp/portrait-pilot/generated"
UNI_DIR = "tmp/portrait-pilot/uniformed"
MASTERS = "assets_staging/players"
LIVE_MASTERS = "FrontEnd/static/images/players"     # Conf1 lives here; protects them
QC_DIR = "tmp/portrait-pilot/qc"
STATUS = "scripts/conf_status.csv"


def slug(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def teams_for_conference(n):
    mani = json.load(open(MANIFEST))
    return [m["team"] for m in mani if str(m.get("conference")) == str(n)]


def roster(team):
    return sorted((r for r in csv.DictReader(open(ARCHETYPES))
                   if slug(r["team"]) == slug(team)),
                  key=lambda r: int(r["jersey"]))


def master_exists(uid):
    return (os.path.exists(os.path.join(MASTERS, uid + ".png"))
            or os.path.exists(os.path.join(LIVE_MASTERS, uid + ".png")))


def run(script, team):
    """Shell one pipeline stage for one team; stream its output."""
    cmd = [PY, os.path.join("scripts", script), "--team", team]
    print(f"    $ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=os.getcwd())
    return r.returncode == 0


def bad_frames(team):
    """Return names whose generated bust looks blank/failed (near-uniform image)."""
    import numpy as np
    from PIL import Image
    bad = []
    for r in roster(team):
        p = os.path.join(GEN_DIR, f"{r['name']}.png")
        if not os.path.exists(p):
            continue
        a = np.asarray(Image.open(p).convert("RGB")).astype("float32")
        # a real portrait has strong local variation; a blank/error frame is flat
        if a.std() < 14 or (a.max(0).max(0) - a.min(0).min(0)).mean() < 30:
            bad.append(r["name"])
    return bad


def qc_sheet(team, conf, slug_):
    """12-player contact sheet from finished masters (final look)."""
    from PIL import Image, ImageDraw, ImageFont
    rs = roster(team)
    C, cols = 340, 4
    rows = (len(rs) + cols - 1) // cols
    hdr = 24
    sheet = Image.new("RGB", (C * cols, (C + hdr) * rows), (238, 238, 240))
    d = ImageDraw.Draw(sheet)
    fnt = ImageFont.load_default()
    for p in ("FrontEnd/static/fonts/LiberationSans-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        if os.path.exists(p):
            fnt = ImageFont.truetype(p, 15)
            break
    have = 0
    for i, r in enumerate(rs):
        x, y = (i % cols) * C, (i // cols) * (C + hdr)
        d.rectangle([x, y, x + C, y + hdr], fill=(28, 42, 68))
        d.text((x + 6, y + 5), f"#{r['jersey']} {r['name']}"[:34], fill=(200, 169, 81), font=fnt)
        mp = os.path.join(MASTERS, r["_id"] + ".png")
        if os.path.exists(mp):
            have += 1
            im = Image.open(mp).convert("RGBA"); im.thumbnail((C, C))
            bg = Image.new("RGBA", (C, C), (238, 238, 240, 255))
            bg.alpha_composite(im, ((C - im.width) // 2, 0))
            sheet.paste(bg.convert("RGB"), (x, y + hdr))
        else:
            d.text((x + C // 2 - 30, y + hdr + C // 2), "(missing)", fill=(150, 150, 150), font=fnt)
    os.makedirs(QC_DIR, exist_ok=True)
    out = os.path.join(QC_DIR, f"conf{conf}_{slug_}.png")
    sheet.save(out)
    return out, have


def process_team(team, conf, args):
    rs = roster(team)
    n = len(rs)
    done = sum(master_exists(r["_id"]) for r in rs)
    print(f"\n=== {team}  ({done}/{n} masters present) ===")
    if done == n and not args.force and not args.qc_only:
        print("    already complete — skipping (use --force to redo)")
        out, have = qc_sheet(team, conf, slug(team))
        return dict(team=team, total=n, finished=have, bad="", status="done", sheet=out)

    if not args.qc_only:
        if not args.no_generate:
            if not run("generate_player_portraits.py", team):
                print("    [warn] generate stage returned nonzero")
        bad = bad_frames(team)
        if bad:
            print(f"    [BAD FRAMES] {len(bad)} likely-failed NB busts: {', '.join(bad)}")
            print(f"      re-roll with:  {PY} scripts/generate_player_portraits.py --only \"<name>\" --force")
        else:
            bad = []
        run("apply_team_uniforms.py", team)
        run("finish_portraits.py", team)
    else:
        bad = []

    out, have = qc_sheet(team, conf, slug(team))
    status = "done" if have == n else ("partial" if have else "empty")
    print(f"    finished {have}/{n}  ->  QC sheet: {out}")
    return dict(team=team, total=n, finished=have, bad=",".join(bad), status=status, sheet=out)


def write_status(rows):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    existing = {}
    if os.path.exists(STATUS):
        for r in csv.DictReader(open(STATUS)):
            existing[r["team"]] = r
    for r in rows:
        existing[r["team"]] = {k: str(v) for k, v in r.items() if k != "sheet"}
    cols = ["conference", "team", "total", "finished", "bad", "status"]
    with open(STATUS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for t in sorted(existing, key=lambda t: (int(existing[t].get("conference", 0)), t)):
            row = existing[t]
            w.writerow({c: row.get(c, "") for c in cols})


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--conference", type=int)
    g.add_argument("--team")
    ap.add_argument("--no-generate", action="store_true",
                    help="skip stage 1 (busts already generated)")
    ap.add_argument("--qc-only", action="store_true",
                    help="only rebuild QC sheets + status, run no stages")
    ap.add_argument("--force", action="store_true",
                    help="reprocess teams even if all masters already exist")
    args = ap.parse_args()

    if args.conference is not None:
        teams = teams_for_conference(args.conference)
        conf = args.conference
        if not teams:
            sys.exit(f"no teams found for conference {conf}")
        print(f"Conference {conf}: {len(teams)} teams -> {', '.join(teams)}")
    else:
        teams = [args.team]
        mani = {m["team"]: m.get("conference") for m in json.load(open(MANIFEST))}
        conf = mani.get(args.team, "?")

    results = []
    for t in teams:
        r = process_team(t, conf, args)
        r["conference"] = conf
        results.append(r)
    write_status(results)

    print("\n================ CONFERENCE SUMMARY ================")
    for r in results:
        flag = "" if r["status"] == "done" else f"  <-- {r['status'].upper()}"
        badn = f" | bad-frames: {r['bad']}" if r["bad"] else ""
        print(f"  {r['team']:24} {r['finished']}/{r['total']}{badn}{flag}")
    ready = [r["team"] for r in results if r["status"] == "done"]
    print(f"\n{len(ready)}/{len(results)} teams complete. Review the QC sheets in {QC_DIR}/ .")
    if ready:
        print("When you're happy, upload the finished teams:")
        print(f'  {PY} scripts/stage_r2_upload.py --conference {conf}')
        print(f'  {PY} scripts/upload_player_images_to_r2.py --source assets_staging/_r2_batch --dry-run')
    print(f"Progress tracked in {STATUS}")


if __name__ == "__main__":
    main()
