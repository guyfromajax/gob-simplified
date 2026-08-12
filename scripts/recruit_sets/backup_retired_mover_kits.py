"""Back up the retired 71 mover kits to a neutral archive prefix BEFORE regen.

The 71 reused-but-rebuilt recruits ("movers") get NEW art at their existing keys
(recruits/kit/<recruit_id>.{png,mask.png,json}) — the same keys the new art will
OVERWRITE. This copies the full recolorable kit trio to a neutral, collision-free
archive prefix first, so the old art is never lost and can later be adopted into a
builder_set_0002 / headshot library once that design is decided.

  source  recruits/kit/<recruit_id>.{png,mask.png,json}
  dest    portrait-kits/set_0001_retired_movers/<recruit_id>.{png,mask.png,json}

Neutral prefix on purpose: it makes NO builder-namespace claim. Do NOT target
portrait-kits/builder_set_0001/ — that pool already exists (150 kits, its own
uuids); writing here would collide with and pollute it.

HARD ORDERING RULE: run this (and verify 71/71) BEFORE any mover kit is
regenerated/uploaded. Run it where R2 is reachable (Railway / prod creds) — local
dev R2 is a different/absent bucket.

Usage:
    python scripts/recruit_sets/backup_retired_mover_kits.py --keys-file mover_kit_backup_keys.txt --dry-run
    python scripts/recruit_sets/backup_retired_mover_kits.py --keys-file mover_kit_backup_keys.txt --commit
    # or derive the ids from the movers CSV instead of a keys file:
    python scripts/recruit_sets/backup_retired_mover_kits.py --movers-csv set0001_reused_movers.csv --commit
"""
import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from script_secrets import ScriptSecretError, load_r2_credentials

SRC_PREFIX = "recruits/kit/"
DEST_PREFIX = "portrait-kits/set_0001_retired_movers/"
KIT_EXTS = (".png", ".mask.png", ".json")   # full recolorable kit trio


def _rid_from_key(key):
    """recruits/kit/<id>.png -> <id> (strips any kit extension)."""
    base = key.strip().split("/")[-1]
    for ext in (".mask.png", ".png", ".json"):
        if base.endswith(ext):
            return base[: -len(ext)]
    return base


def load_ids(args):
    if args.keys_file:
        with open(args.keys_file) as f:
            ids = [_rid_from_key(line) for line in f if line.strip()]
    else:
        with open(args.movers_csv, newline="") as f:
            rows = list(csv.DictReader(f))
        ids = [r["recruit_id"] for r in rows
               if str(r.get("crossed", "")).strip() in ("1", "true", "True", "yes")]
    # de-dupe, preserve order
    seen, out = set(), []
    for i in ids:
        if i and i not in seen:
            seen.add(i); out.append(i)
    return out


def main():
    ap = argparse.ArgumentParser(description="Archive retired mover kits before regen.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--keys-file", help="text file of source keys (recruits/kit/<id>.png per line)")
    src.add_argument("--movers-csv", help="reused-movers CSV; rows with crossed==1 are the retired 71")
    ap.add_argument("--dest-prefix", default=DEST_PREFIX, help=f"archive prefix (default {DEST_PREFIX})")
    ap.add_argument("--commit", action="store_true", help="actually copy (default: dry-run)")
    args = ap.parse_args()

    if "builder_set_" in args.dest_prefix:
        sys.exit("refusing: dest-prefix must not write into an existing builder_set pool namespace.")

    ids = load_ids(args)
    print(f"retired movers to archive: {len(ids)}  (expected 71)")

    try:
        os.environ.update(load_r2_credentials())
    except ScriptSecretError as exc:
        sys.exit(f"R2 not configured: {exc}")

    from BackEnd.services import r2_images
    if not r2_images.is_configured():
        sys.exit("R2 not configured (need R2_* env). Run where prod/Railway R2 creds are set.")
    s3, bucket = r2_images._s3()
    from botocore.exceptions import ClientError

    def exists(key):
        try:
            s3.head_object(Bucket=bucket, Key=key); return True
        except ClientError:
            return False

    copied = missing = already = 0
    for rid in ids:
        for ext in KIT_EXTS:
            src_key = f"{SRC_PREFIX}{rid}{ext}"
            dst_key = f"{args.dest_prefix}{rid}{ext}"
            if not exists(src_key):
                print(f"  MISS source {src_key}")
                missing += 1
                continue
            if exists(dst_key):
                already += 1
                continue
            if args.commit:
                s3.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": src_key}, Key=dst_key)
            copied += 1
    verb = "copied" if args.commit else "would copy"
    print(f"\n{verb} {copied} | already-archived {already} | missing-source {missing}")
    print(f"expected files: {len(ids) * len(KIT_EXTS)} ({len(ids)} movers x {len(KIT_EXTS)} kit files)")
    if not args.commit:
        print("DRY-RUN — nothing written. Re-run with --commit.")
    if missing:
        print("⚠️  missing sources above — investigate before regenerating those movers (do not overwrite un-archived art).")


if __name__ == "__main__":
    main()
