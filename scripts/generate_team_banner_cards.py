#!/usr/bin/env python3
"""
Generate picker-grid banner derivatives for all 128 teams.

Convention (Team Builder Task B):
  Source : {slug}_banner_primary.jpg  (1920×679)
  Card   : {slug}_banner_card.webp    (400px wide, proportional height ≈141)
  Use    : TeamPicker grid only. Detail / loading screens keep banner_primary.

Usage:
  .venv/bin/python scripts/generate_team_banner_cards.py
  .venv/bin/python scripts/generate_team_banner_cards.py --force
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEAMS_DIR = ROOT / "FrontEnd" / "static" / "images" / "teams"
CARD_WIDTH = 400
WEBP_QUALITY = 80


def convert_one(src: Path, dest: Path, force: bool) -> str:
    if dest.exists() and not force:
        return "skip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    # magick: resize width, preserve aspect, write webp
    cmd = [
        "magick",
        str(src),
        "-resize",
        f"{CARD_WIDTH}x",
        "-quality",
        str(WEBP_QUALITY),
        str(dest),
    ]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return "wrote"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    sources = sorted(TEAMS_DIR.glob("*/*_banner_primary.*"))
    if not sources:
        print("No banner_primary sources found", file=sys.stderr)
        return 1

    wrote = skipped = failed = 0
    for src in sources:
        slug = src.parent.name
        dest = src.parent / f"{slug}_banner_card.webp"
        try:
            result = convert_one(src, dest, args.force)
            if result == "wrote":
                wrote += 1
            else:
                skipped += 1
        except Exception as exc:
            failed += 1
            print(f"FAIL {src.name}: {exc}", file=sys.stderr)

    # Also ensure general has a card derivative if a primary exists.
    general_src = TEAMS_DIR / "general" / "general_banner_primary.jpg"
    if general_src.exists():
        try:
            convert_one(general_src, TEAMS_DIR / "general" / "general_banner_card.webp", args.force)
        except Exception as exc:
            print(f"FAIL general: {exc}", file=sys.stderr)
            failed += 1

    print(f"banner_card done: wrote={wrote} skipped={skipped} failed={failed} width={CARD_WIDTH}q={WEBP_QUALITY}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
