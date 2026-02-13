# Weekly MongoDB backup schedule (Step 7.0)

The script `scripts/backup-mongodb.sh` runs mongodump, zips the dump with the date, and optionally copies the zip to a folder (e.g. Google Drive).

## One-time setup

1. **Env file**
   - Copy `.env.backup.example` to `.env.backup` in the repo root.
   - Set `MONGO_URI` to your full Atlas connection string (including username and password).
   - Optional: set `BACKUP_OUTPUT_DIR` to your Google Drive folder (e.g. `~/Google Drive/GOB backups`).

2. **Make script executable**
   ```bash
   chmod +x scripts/backup-mongodb.sh
   ```

3. **Test run**
   ```bash
   ./scripts/backup-mongodb.sh
   ```
   You should see a zip like `gob-backup-YYYY-MM-DD.zip` in the repo root (and in `BACKUP_OUTPUT_DIR` if set).

## Schedule weekly with launchd (macOS)

1. **Create a plist** (run once):

   ```bash
   # Replace YOUR_USERNAME with your Mac username
   cat > ~/Library/LaunchAgents/com.gob.mongodb-backup.plist << 'PLIST'
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
     <key>Label</key>
     <string>com.gob.mongodb-backup</string>
     <key>ProgramArguments</key>
     <array>
       <string>/Users/YOUR_USERNAME/gob-simplified/scripts/backup-mongodb.sh</string>
     </array>
     <key>StartCalendarInterval</key>
     <dict>
       <key>Weekday</key>
       <integer>0</integer>
       <key>Hour</key>
       <integer>2</integer>
       <key>Minute</key>
       <integer>0</integer>
     </dict>
     <key>StandardOutPath</key>
     <string>/Users/YOUR_USERNAME/gob-simplified/backup-mongodb.log</string>
     <key>StandardErrorPath</key>
     <string>/Users/YOUR_USERNAME/gob-simplified/backup-mongodb.log</string>
     <key>WorkingDirectory</key>
     <string>/Users/YOUR_USERNAME/gob-simplified</string>
   </dict>
   </plist>
   PLIST
   ```

   **Edit the plist** and replace both `YOUR_USERNAME` with your Mac username (e.g. `jamesdavies`). The example runs **every Sunday at 2:00 AM**.

2. **Load the job**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.gob.mongodb-backup.plist
   ```

3. **Check it’s loaded**
   ```bash
   launchctl list | grep com.gob.mongodb-backup
   ```

4. **Optional: run once now**
   ```bash
   launchctl start com.gob.mongodb-backup
   ```
   Then check `backup-mongodb.log` in the repo root.

**To stop or change schedule:** Edit the plist, then run:
```bash
launchctl unload ~/Library/LaunchAgents/com.gob.mongodb-backup.plist
launchctl load ~/Library/LaunchAgents/com.gob.mongodb-backup.plist
```

**Note:** The Mac must be on and awake at the scheduled time. If you need backups when the machine is off, run the script on a server or use a cron job in the cloud.
