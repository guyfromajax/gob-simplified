#!/usr/bin/env python3
"""
Inspect Chapel Hill player art in two places and build contact sheets to compare:
  1. R2  (players/master/<uuid>.png) — what's currently live/uploaded
  2. local staging (assets_staging/players/<uuid>.png) — what's cued to upload

Run on your machine (needs scripts/.r2.env with the R2 creds; never printed).
Outputs two small sheets under tmp/portrait-pilot/ that you can open or push:
    tmp/portrait-pilot/chapel_hill_R2.png
    tmp/portrait-pilot/chapel_hill_staging.png

    python3 scripts/inspect_chapel_hill.py
    python3 scripts/inspect_chapel_hill.py --team "Chapel Hill"   # any team
"""
import os
import io
import csv
import argparse

ENV_FILE = "scripts/.r2.env"
KEY_PREFIX = "players/master/"
STAGING = "assets_staging/players"
OUT = "tmp/portrait-pilot"


def load_env(path):
    env = {}
    if not os.path.exists(path):
        raise SystemExit(f"R2 env not found: {path}")
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def a_font(size):
    from PIL import ImageFont
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc",
              "FrontEnd/static/fonts/BebasNeuePro-Bold.otf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def build_sheet(rows, getter, title, fname):
    from PIL import Image, ImageDraw
    C, cols, rn, hdr = 430, 4, 3, 34
    sheet = Image.new("RGB", (C * cols, (C + hdr) * rn), (238, 238, 240))
    d = ImageDraw.Draw(sheet)
    fb = a_font(22)
    found = 0
    for i, r in enumerate(rows):
        x, y = (i % cols) * C, (i // cols) * (C + hdr)
        d.rectangle([x, y, x + C, y + hdr], fill=(28, 42, 68))
        d.text((x + 6, y + 6), f"#{r['jersey']} {r['name']}", fill=(200, 169, 81), font=fb)
        im = getter(r["_id"])
        if im is not None:
            found += 1
            im = im.convert("RGBA").resize((C, C))
            bg = Image.new("RGBA", (C, C), (238, 238, 240, 255))
            bg.alpha_composite(im)
            sheet.paste(bg.convert("RGB"), (x, y + hdr))
        else:
            d.text((x + C // 2 - 34, y + hdr + C // 2), "(none)", fill=(150, 150, 150), font=fb)
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, fname)
    sheet.save(out, quality=90)
    print(f"[{title}] {found}/{len(rows)} found -> {out}")
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", default="Chapel Hill")
    args = ap.parse_args()

    try:
        import boto3
        from botocore.exceptions import ClientError
        from PIL import Image  # noqa: F401
    except ImportError:
        raise SystemExit("missing deps. Run:  pip install boto3 pillow")

    rows = [r for r in csv.DictReader(open("scripts/players_archetypes.csv"))
            if r["team"] == args.team]
    rows = sorted(rows, key=lambda r: int(r["jersey"]))
    if not rows:
        raise SystemExit(f"no players found for team '{args.team}'")

    env = load_env(ENV_FILE)
    s3 = boto3.client("s3", endpoint_url=env["R2_ENDPOINT"],
                      aws_access_key_id=env["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
                      region_name="auto")
    bucket = env["R2_BUCKET"]

    def r2_get(uid):
        from PIL import Image
        try:
            o = s3.get_object(Bucket=bucket, Key=f"{KEY_PREFIX}{uid}.png")
            return Image.open(io.BytesIO(o["Body"].read()))
        except ClientError:
            return None

    def staging_get(uid):
        from PIL import Image
        p = os.path.join(STAGING, f"{uid}.png")
        return Image.open(p) if os.path.exists(p) else None

    print(f"Checking {len(rows)} {args.team} players...\n")
    n_r2 = build_sheet(rows, r2_get, "R2 live", "chapel_hill_R2.png")
    n_st = build_sheet(rows, staging_get, "local staging", "chapel_hill_staging.png")
    print(f"\nR2 has {n_r2}/{len(rows)} ; staging has {n_st}/{len(rows)}.")
    print("Open the two sheets above (or push them) to compare.")


if __name__ == "__main__":
    main()
