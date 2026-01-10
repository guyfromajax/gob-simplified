# Staging Database Setup - Next Steps (Option A: Start Fresh)

**Date:** January 2026  
**Status:** ✅ APPROACH SELECTED - Ready for Implementation  
**Approach:** Option A (Start Fresh) - Database auto-created on first write

## Quick Summary

✅ **Code changes complete** - `BackEnd/db.py` now supports configurable database name  
✅ **Approach selected** - Option A (Start Fresh) - no cloning needed  
⏳ **Next step** - Update Railway staging environment variables

## What's Done

1. ✅ Updated `BackEnd/db.py` to support configurable database name:
   - Checks `MONGO_DB_NAME` environment variable first (recommended)
   - Or extracts database name from `MONGO_URI` path
   - Defaults to `"gob"` for backward compatibility
   - Logs: `📊 [DB CONFIG] Using database: {DB_NAME}`

2. ✅ Created cloning script (if needed later):
   - `scripts/clone_reference_data_to_staging.py` (for Option B - not needed now)

3. ✅ Documentation created:
   - `docs/To Do/setup_staging_database.md` (full guide)
   - `docs/To Do/STAGING_DATABASE_SETUP_NEXT_STEPS.md` (this file)

## What Needs to Be Done

### Step 1: Update Railway Staging Environment Variables

Go to Railway dashboard → `gob-simplified-staging` project → Environment Variables

**Option A (Recommended):** Add explicit database name environment variable

1. Keep existing `MONGO_URI` (should NOT have database name in path):
   ```
   MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority
   ```
   - If it currently has `/gob` in the path, remove it (or the explicit env var will override)

2. **Add new environment variable:**
   - **Variable name:** `MONGO_DB_NAME`
   - **Value:** `gob-staging`
   - **Description:** Database name for staging environment

**Option B (Alternative):** Update MONGO_URI path

If you prefer to include database name in the connection string:
```
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/gob-staging?retryWrites=true&w=majority
```
- Note: `/gob-staging` in the path (before the `?`)

**Recommendation:** Use Option A (explicit `MONGO_DB_NAME`) - clearer intent, easier to verify and change

### Step 2: Redeploy/Restart Staging Backend

After updating environment variables:

1. **Redeploy staging backend** (or restart if already deployed)
   - Railway should auto-redeploy if watching git branch
   - Or manually trigger redeploy from Railway dashboard

2. **Check Railway logs** for database configuration message:
   - Look for: `📊 [DB CONFIG] Using database: gob-staging`
   - Should appear in logs after deployment/restart

### Step 3: Verify Database Creation

**Option A (Start Fresh) - Database auto-created:**

1. **Test database connection** by creating a test game/tournament/franchise:
   - Go to staging frontend: `https://gob-test.netlify.app`
   - Create a new franchise or tournament
   - This will trigger the first write to `gob-staging` database

2. **Verify in MongoDB Atlas:**
   - Go to MongoDB Atlas dashboard
   - Navigate to your cluster
   - Click "Browse Collections"
   - You should see `gob-staging` database appear (may take a moment)
   - New database will have collections: `franchises`, `tournaments`, `games`, etc.

3. **Verify database name in logs:**
   - Check Railway logs for: `📊 [DB CONFIG] Using database: gob-staging`
   - If you see `gob` instead, the environment variable wasn't set correctly

### Step 4: Verify Environment Separation

**Production Database (should remain unchanged):**
- Production `MONGO_URI` should still point to `gob` database (or not have `MONGO_DB_NAME` set)
- Production logs should show: `📊 [DB CONFIG] Using database: gob`
- Production data in `gob` database should remain intact

**Staging Database (new):**
- Staging `MONGO_DB_NAME=gob-staging` (or `MONGO_URI` path includes `/gob-staging`)
- Staging logs should show: `📊 [DB CONFIG] Using database: gob-staging`
- Staging data in `gob-staging` database (separate from production)

## Testing Checklist

After completing setup, verify:

- [ ] Railway staging backend logs show: `📊 [DB CONFIG] Using database: gob-staging`
- [ ] MongoDB Atlas shows `gob-staging` database exists (after first write)
- [ ] Create test franchise in staging - appears in `gob-staging` database (check MongoDB Atlas)
- [ ] Create test tournament in staging - appears in `gob-staging` database (check MongoDB Atlas)
- [ ] Verify `gob` database unchanged (production data intact - check MongoDB Atlas)
- [ ] Production backend (if deployed) still uses `gob` database (check production logs)

## Troubleshooting

### Issue: Logs show `gob` instead of `gob-staging`

**Possible causes:**
1. `MONGO_DB_NAME` environment variable not set in Railway
2. `MONGO_URI` path extraction not working (use explicit `MONGO_DB_NAME` instead)
3. Environment variable not saved/not deployed yet

**Fix:**
- Double-check Railway environment variables
- Ensure `MONGO_DB_NAME=gob-staging` is set
- Redeploy backend after setting environment variable

### Issue: Database not appearing in MongoDB Atlas

**Possible causes:**
1. First write hasn't happened yet (database created on first write)
2. Wrong cluster/connection string
3. Network access issues

**Fix:**
- Create a test game/franchise/tournament in staging to trigger first write
- Verify connection string is correct
- Check MongoDB Atlas network access settings (should allow `0.0.0.0/0` for alpha)

### Issue: Still connecting to `gob` database

**Possible causes:**
1. Environment variable not propagated to running instance
2. Code changes not deployed
3. Cached connection (unlikely but possible)

**Fix:**
- Redeploy backend (force new deployment)
- Check Railway logs immediately after redeploy
- Verify `BackEnd/db.py` changes are in the deployed code

## Reference Data (Option A - Start Fresh)

With Option A, reference collections (players, teams, plays, skeletons) will be:
- Populated by app code when needed (if app has seed/init scripts)
- Created on first write (if app creates them dynamically)
- May need manual seeding if app doesn't auto-populate

**If reference data is missing:**
- Option A doesn't clone reference data - it starts fresh
- App code should populate reference data as needed
- If you need reference data, you can:
  - Run clone script: `python scripts/clone_reference_data_to_staging.py` (Option B approach)
  - Or manually seed reference collections via app initialization

**For now (alpha):** Start fresh and see if app populates reference data automatically. If not, we can clone later.

## Related Files

- `BackEnd/db.py` - Database connection and configuration (✅ Updated)
- `scripts/clone_reference_data_to_staging.py` - Clone script (available if needed)
- `docs/To Do/setup_staging_database.md` - Full setup guide
- `docs/To Do/Task_1_1_Go_Live_Foundations_Verification.md` - Verification checklist

## Next Steps After Setup

Once staging database is verified:
1. Continue with Task 1.1 verification checklist
2. Test persistence in staging (Game Plan, Playbooks)
3. Verify all staging functionality works with `gob-staging` database
4. Document any issues or needed reference data seeding

