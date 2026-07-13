#!/usr/bin/env python3
"""
Upload recruit assets to Cloudflare R2 (bucket: gob-player-images) — Phase 2c.

Two local staging folders map to two R2 key prefixes:

    assets_staging/recruits/kit/     -> recruits/kit/<id>.{png,json} (sign-time recolor input)
    assets_staging/recruits/signed/  -> players/master/<id>.png      (post-sign; game resolves this)

There is no display master for un-signed recruits: the recruiting board is a
stats table and un-signed recruits sunset at week 35, so only the kit (recolor
input) and the post-sign master are ever uploaded.

Reuses the league uploader's helpers (credentials, sha256 idempotency, dry-run),
so behavior + conventions match exactly. Idempotent: re-running only pushes
new/changed objects.

Typical use:
    # at set bake time — push kits:
    python3 scripts/recruit_sets/upload_recruit_images_to_r2.py --stage kit --dry-run
    python3 scripts/recruit_sets/upload_recruit_images_to_r2.py --stage kit
    # at signing — push the uniformed masters:
    python3 scripts/recruit_sets/upload_recruit_images_to_r2.py --stage signed

Credentials: scripts/.r2.env (gitignored), same as the league uploader.
See _documentation_master/00_Operations/Recruit_Image_System.md.
"""
import os
import sys
import csv
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)

import upload_player_images_to_r2 as up   # noqa: E402  (load_env, sha256_of, remote_sha256)

# stage -> (local dir, R2 key prefix)
STAGES = {
    "kit":    ("assets_staging/recruits/kit",    "recruits/kit/"),
    "signed": ("assets_staging/recruits/signed", "players/master/"),
}
CONTENT_TYPE = {".png": "image/png", ".json": "application/json"}
CACHE_CONTROL = "public, max-age=86400"
MANIFEST_PATH = "scripts/recruit_r2_upload_manifest.csv"


def main():
    ap = argparse.ArgumentParser(description="Upload recruit white/kit/signed assets to R2.")
    ap.add_argument("--stage", nargs="+", choices=list(STAGES) + ["all"], default=["all"],
                    help="which folders to upload (default: all)")
    ap.add_argument("--dry-run", action="store_true", help="preview without uploading")
    args = ap.parse_args()
    stages = list(STAGES) if "all" in args.stage else args.stage

    env = up.load_env(up.ENV_FILE)
    import boto3
    s3 = boto3.client("s3", endpoint_url=env["R2_ENDPOINT"],
                      aws_access_key_id=env["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"], region_name="auto")
    bucket = env["R2_BUCKET"]

    mode = "DRY RUN — nothing will be uploaded" if args.dry_run else "UPLOADING"
    rows = []
    uploaded = skipped = failed = 0
    for stage in stages:
        src, prefix = STAGES[stage]
        if not os.path.isdir(src):
            print(f"[skip stage] {stage}: {src} not found")
            continue
        files = sorted(f for f in os.listdir(src)
                       if os.path.splitext(f)[1].lower() in CONTENT_TYPE)
        print(f"\n[{mode}] {stage}: {len(files)} file(s) {src} -> s3://{bucket}/{prefix}")
        for i, fname in enumerate(files, 1):
            local_path = os.path.join(src, fname)
            key = prefix + fname
            ext = os.path.splitext(fname)[1].lower()
            digest = up.sha256_of(local_path)
            try:
                if up.remote_sha256(s3, bucket, key) == digest:
                    status = "skipped (unchanged)"; skipped += 1
                elif args.dry_run:
                    status = "would upload"
                else:
                    s3.upload_file(local_path, bucket, key, ExtraArgs={
                        "ContentType": CONTENT_TYPE[ext],
                        "CacheControl": CACHE_CONTROL,
                        "Metadata": {"sha256": digest},
                    })
                    status = "uploaded"; uploaded += 1
            except Exception as e:  # noqa: BLE001
                status = f"FAILED: {e}"; failed += 1
            print(f"  [{i:>4}/{len(files)}] {fname:<44} {status}")
            rows.append({"stage": stage, "filename": fname, "asset_key": key,
                         "remote_url": f"https://assets.geekedoutgames.com/{key}",
                         "sha256": digest, "status": status})

    if rows:
        with open(MANIFEST_PATH, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    print(f"\nSummary: {uploaded} uploaded, {skipped} skipped, {failed} failed")
    print(f"Manifest -> {MANIFEST_PATH}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
