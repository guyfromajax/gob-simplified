#!/usr/bin/env python3
"""Publish the 71 walk-on portrait kits to R2.

Copies each retired-mover kit trio from
``portrait-kits/set_0001_retired_movers/<source_id>.{png,mask.png,json}``
to ``portrait-kits/walk_on_portraits/<new_image_id>.{png,mask.png,json}``
using ``BackEnd/data/walk_on_portraits_manifest.json`` (collision-free UUIDs).

HARD REQUIREMENT: the retired-mover archive must already exist on the target
bucket (see backup_retired_mover_kits.py). Do NOT copy from recruits/kit/ —
those keys hold regen art for the same source ids.

Usage:
    .venv/bin/python scripts/recruit_sets/publish_walk_on_portraits.py            # dry-run
    .venv/bin/python scripts/recruit_sets/publish_walk_on_portraits.py --commit   # copy
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MANIFEST = ROOT / "BackEnd" / "data" / "walk_on_portraits_manifest.json"
KIT_EXTS = (".png", ".mask.png", ".json")


def _load_env() -> None:
    for name in (".env.local", ".env", "scripts/.r2.env"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            v = line.strip()
            if v and not v.startswith("#") and "=" in v:
                k, raw = v.split("=", 1)
                os.environ.setdefault(k.strip(), raw.strip().strip('"').strip("'"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    _load_env()
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    src_prefix = str(data["source_archive_prefix"]).rstrip("/") + "/"
    dst_prefix = str(data["kit_prefix"]).rstrip("/") + "/"
    portraits = data.get("portraits") or []
    print(f"manifest portraits: {len(portraits)} (expected 71)")
    print(f"source {src_prefix}")
    print(f"dest   {dst_prefix}")

    from BackEnd.services import r2_images
    if not r2_images.is_configured():
        print("R2 not configured (need R2_* env).", file=sys.stderr)
        return 1
    s3, bucket = r2_images._s3()
    from botocore.exceptions import ClientError

    def exists(key: str) -> bool:
        try:
            s3.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False

    copied = already = missing = 0
    for row in portraits:
        src_id = row["source_retired_id"]
        dst_id = row["image_id"]
        for ext in KIT_EXTS:
            src_key = f"{src_prefix}{src_id}{ext}"
            dst_key = f"{dst_prefix}{dst_id}{ext}"
            if not exists(src_key):
                print(f"  MISS {src_key}")
                missing += 1
                continue
            if exists(dst_key):
                already += 1
                continue
            if args.commit:
                s3.copy_object(
                    Bucket=bucket,
                    CopySource={"Bucket": bucket, "Key": src_key},
                    Key=dst_key,
                )
            copied += 1

    verb = "copied" if args.commit else "would copy"
    print(f"\n{verb} {copied} | already {already} | missing-source {missing}")
    print(f"expected files: {len(portraits) * len(KIT_EXTS)}")
    if not args.commit:
        print("DRY-RUN — nothing written. Re-run with --commit.")
    if missing:
        print(
            "⚠️  missing retired-mover sources — run backup_retired_mover_kits.py "
            "--commit on this bucket before publishing walk-on portraits.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
