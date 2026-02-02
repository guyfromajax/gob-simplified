#!/usr/bin/env bash
# Weekly MongoDB backup for GOB (Step 7.0)
# 1. Run mongodump using MONGO_URI from .env.backup
# 2. Zip dump with date (gob-backup-YYYY-MM-DD.zip)
# 3. Copy zip to BACKUP_OUTPUT_DIR if set (e.g. Google Drive folder)
#
# Setup: Copy .env.backup.example to .env.backup, fill in MONGO_URI.
# Schedule: Use launchd (see docs/To Do/backup_schedule.md) for weekly run.

set -e

# launchd runs with minimal PATH; ensure mongodump (Homebrew) is found
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Load backup env (MONGO_URI, optional BACKUP_OUTPUT_DIR)
if [[ -f "$REPO_ROOT/.env.backup" ]]; then
  set -a
  source "$REPO_ROOT/.env.backup"
  set +a
else
  echo "Missing .env.backup. Copy .env.backup.example to .env.backup and set MONGO_URI." >&2
  exit 1
fi

if [[ -z "$MONGO_URI" ]]; then
  echo "MONGO_URI is not set in .env.backup." >&2
  exit 1
fi

DATE=$(date +%Y-%m-%d)
ZIP_NAME="gob-backup-${DATE}.zip"
DUMP_DIR="$REPO_ROOT/dump"
ZIP_PATH="$REPO_ROOT/$ZIP_NAME"

# Clean previous dump so we don't zip old + new
rm -rf "$DUMP_DIR"
mkdir -p "$DUMP_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting mongodump..."
mongodump --uri "$MONGO_URI" --out "$DUMP_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Creating $ZIP_NAME..."
cd "$REPO_ROOT"
zip -r -q "$ZIP_PATH" dump/

# Optional: copy to Google Drive (or other folder)
# When run by launchd, copy may fail with "Operation not permitted" (CloudStorage).
# If so, zip stays in repo root only.
COPY_OK=0
if [[ -n "$BACKUP_OUTPUT_DIR" && -d "$BACKUP_OUTPUT_DIR" ]]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Copying to $BACKUP_OUTPUT_DIR..."
  if cp "$ZIP_PATH" "$BACKUP_OUTPUT_DIR/" 2>/dev/null; then
    COPY_OK=1
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Skipped copy (not writable by this process, e.g. launchd). Zip is in repo root."
  fi
fi

# Remove dump folder (zip is the backup)
rm -rf "$DUMP_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done. Backup: $ZIP_PATH"
if [[ $COPY_OK -eq 1 ]]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Also copied to: $BACKUP_OUTPUT_DIR/$ZIP_NAME"
fi
