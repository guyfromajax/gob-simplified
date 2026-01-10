# Setting Up Staging Database (gob-staging)

**Date:** January 2026  
**Status:** ✅ COMPLETE - Staging database setup and initialization successful  
**Priority:** 🔴 CRITICAL - Required for environment separation  
**Approach:** ✅ Option B (Clone Reference Data) - Reference data cloned from production

## Overview

We need to create a separate `gob-staging` database for staging environment to ensure clean environment separation. The current `gob` database will be used for production.

**✅ APPROACH USED: Option B (Clone Reference Data)** - Database was created with reference data cloned from production. This ensures staging has the same core data (teams, players, plays, skeletons) as production for accurate testing.

## Database Roles

### `gob` Database (Production)
- **Purpose:** Live production data
- **Usage:** Production environment only
- **Protection:** Must be protected - never use for testing/development
- **Data:** Real user data, production games, tournaments, franchises

### `gob-staging` Database (Staging)
- **Purpose:** Staging/testing environment
- **Usage:** Staging deployments, testing, development
- **Protection:** Can be reset/cleared as needed
- **Data:** Test data, staging games, tournaments, franchises
- **Reference Data:** Should have same core reference data (players, teams, plays, skeletons) as production for testing accuracy

## Implementation Approach

### Option A: Start Fresh (Recommended for Alpha)

**Pros:**
- Clean slate - no stale data
- Faster setup
- Tests app's initialization code

**Cons:**
- Reference collections (players, teams, plays, skeletons) need to be populated
- Might be missing test data

**Steps:**
1. Update Railway staging `MONGO_URI` to point to `gob-staging` database (see below)
2. Deploy staging backend - database will be created automatically on first write
3. Reference collections will be populated by app code or initial seed scripts
4. Test data can be created through normal app usage

### Option B: Clone Reference Data

**Pros:**
- Staging has exact same reference data as production (players, teams, plays, skeletons)
- More realistic testing (same core data)
- Can test with known data sets

**Cons:**
- Requires running clone script
- Need to keep reference data in sync manually if production reference data changes

**Steps:**
1. ✅ Update Railway staging `MONGO_DB_NAME` environment variable to `gob-staging`
2. ✅ Run clone script: `python scripts/clone_reference_data_to_staging.py` (from project root with venv activated)
   - Script clones reference collections: players, teams, plays, defenses, fcp_skeletons, hct_skeletons
   - Script skips game-specific collections: games, tournaments, franchises (start fresh)
   - ✅ Successfully cloned 133 documents across 6 collections (January 2026)
3. ✅ Deploy staging backend - uses cloned reference data
4. ✅ Verify teams are accessible (test franchise team selection)

**Actual Execution (January 2026):**
- ✅ Database cloning completed successfully
- ✅ Cloned collections: players (96 docs), teams (8 docs), plays (23 docs), defenses (4 docs), fcp_skeletons (1 doc), hct_skeletons (1 doc)
- ✅ Total: 133 documents cloned
- ✅ Team selection now works correctly in staging

## Code Changes Made

### ✅ Updated `BackEnd/db.py` to Support Configurable Database Name

**Changes:**
- Added `_get_database_name()` function that:
  1. Checks `MONGO_DB_NAME` environment variable (explicit override)
  2. Extracts database name from `MONGO_URI` path if present
  3. Defaults to `"gob"` for backward compatibility
- Database name is now configurable: `db = client[DB_NAME]`
- Added logging: `📊 [DB CONFIG] Using database: {DB_NAME}`

**Backward Compatibility:**
- Defaults to `"gob"` if no database name specified (existing behavior)
- Existing local development and production won't break
- Only staging needs explicit configuration

## Setting Up gob-staging Database

## Issues Encountered and Resolved

### Issue 1: Railway Port Configuration (502 Errors)
**Problem:** All requests returned 502 "Application failed to respond" even though app was running.  
**Root Cause:** Railway's "Target port" was set to 8000, but the app was running on port 8080 (from Railway's `$PORT` env var).  
**Solution:** Updated Railway Settings → Public Networking → Target port from 8000 to 8080.  
**Lesson:** Always verify Railway's target port matches the actual port your app is listening on (check via startup logs: `PORT env var: 8080`).

### Issue 2: Empty Staging Database (404 Team Not Found)
**Problem:** Team selection failed with 404 "Team not found in database" - `Available teams in database: []`  
**Root Cause:** `gob-staging` database was empty (no teams, players, or reference data).  
**Solution:** Ran `scripts/clone_reference_data_to_staging.py` to clone reference collections from production.  
**Result:** ✅ Successfully cloned 133 documents (teams, players, plays, defenses, skeletons).  
**Lesson:** Staging database needs reference data populated before it can be used. Cloning from production ensures consistency.

### Issue 3: Team Name Case Sensitivity
**Problem:** Team lookup was case-sensitive, potentially failing if team names didn't match exactly.  
**Solution:** Enhanced team lookup in `BackEnd/api/franchise_routes.py` to use case-insensitive matching with multiple fallback strategies:
  - Strategy 1: Exact match
  - Strategy 2: Case-insensitive regex
  - Strategy 3: Hyphen/underscore normalization (e.g., "Bentley-Truman" → "Bentley Truman")
  - Strategy 4: Full collection search with case-insensitive comparison
**Result:** More robust team matching (though cloning fixed the immediate issue).

## Setting Up gob-staging Database

### Step 1: Update Railway Staging Environment Variables

**✅ COMPLETED: Option B (Clone Reference Data)** - Reference data cloned from production.

**Option 2a: Set Database Name in Connection String**
```
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/gob-staging?retryWrites=true&w=majority
```
- Note the `/gob-staging` in the path (before the `?`)
- The code will extract `gob-staging` from the URI path

**Option 2b: Set Explicit Database Name Environment Variable (Recommended)**
```
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=gob-staging
```
- Database name not in URI (cleaner)
- Explicit `MONGO_DB_NAME` env var takes priority
- More explicit and easier to change

**Recommendation:** Use Option 2b (explicit `MONGO_DB_NAME`) - clearer intent, easier to verify

### Step 2: Clone Reference Data to Staging

**✅ COMPLETED (January 2026):**

1. ✅ Activated virtual environment: `source venv/bin/activate`
2. ✅ Ran clone script: `echo "yes" | python scripts/clone_reference_data_to_staging.py`
3. ✅ Script output confirmed:
   - Cloned 96 players
   - Cloned 8 teams  
   - Cloned 23 plays
   - Cloned 4 defenses
   - Cloned 1 fcp_skeletons document
   - Cloned 1 hct_skeletons document
   - **Total: 133 documents cloned**

### Step 3: Verify Staging Database Connection

**✅ COMPLETED:**

1. ✅ Railway logs show: `📊 [DB CONFIG] Using database: gob-staging`
2. ✅ Tested team selection in staging - works correctly
3. ✅ Verified database in MongoDB Atlas - `gob-staging` database exists with cloned collections
4. ✅ Verified environment separation - staging uses `gob-staging`, production uses `gob`

### Step 4: Verify Environment Separation

**Check Production Database:**
- Production `MONGO_URI` should still point to `gob` database
- Production should continue using `gob` database
- No changes to production needed

**Check Staging Database:**
- Staging `MONGO_URI` points to `gob-staging` database (via `MONGO_DB_NAME` env var)
- Staging uses `gob-staging` database
- Staging and production databases are separate

## Testing Checklist

- [x] ✅ Staging backend logs show: `📊 [DB CONFIG] Using database: gob-staging`
- [x] ✅ Production backend logs show: `📊 [DB CONFIG] Using database: gob`
- [x] ✅ Create test franchise in staging - appears in `gob-staging` database (not `gob`)
- [x] ✅ Verify reference collections exist in `gob-staging` (cloned successfully: 133 documents)
- [x] ✅ Test team selection in staging works (uses cloned teams from `gob-staging`)
- [ ] Create test tournament in staging - should appear in `gob-staging` database (not `gob`)
- [ ] Verify `gob` database unchanged (production data intact)
- [ ] Test game creation in staging works (uses `gob-staging` database)

**Note:** Railway port configuration must match app's actual port. Check startup logs for `PORT env var: XXXX` and update Railway target port accordingly.

## MongoDB Atlas Setup

### Network Access
- Already configured: `0.0.0.0/0` (allow all IPs) for alpha
- Both `gob` and `gob-staging` databases use same cluster
- Same network access rules apply to both databases

### Database User
- Same database user for both `gob` and `gob-staging` databases
- User has read/write access to cluster (can access any database on cluster)
- Connection string is the same (only database name changes)

## Future Considerations

### Post-Launch Database Security
- [ ] Tighten MongoDB Atlas network access (remove `0.0.0.0/0`)
- [ ] Set up IP whitelist for Railway static IPs (if available)
- [ ] Consider separate database users for staging vs production
- [ ] Consider separate clusters for staging vs production (better isolation)

### Reference Data Sync
- If reference data (plays, teams, players) changes in production:
  - Option A: Manually clone updated reference collections to staging
  - Option B: Create automated sync script (run periodically)
  - Option C: Both environments use same reference data source (shared collection or seed scripts)

## Notes

- **Database Creation:** MongoDB creates databases automatically on first write - no manual creation needed
- **Same Cluster:** Both `gob` and `gob-staging` can exist on same MongoDB Atlas cluster (they're separate databases)
- **Connection String:** Only the database name differs - same cluster, same user, same connection method
- **Environment Variables:** Railway environment variables are environment-specific - staging and production have separate env vars

## Related Files

- `BackEnd/db.py` - Database connection and configuration
- `BackEnd/api/franchise_routes.py` - Team lookup logic (case-insensitive matching)
- `scripts/clone_reference_data_to_staging.py` - Reference data cloning script (✅ Used successfully)
- `docs/Admin_Only_Docs/Go_Live_Plan.md` - Main go-live plan
- `docs/To Do/Task_1_1_Go_Live_Foundations_Verification.md` - Verification checklist
- `railway.json` - Railway deployment configuration
- `Procfile` - Railway startup command

## Command Reference

**Clone reference data to staging:**
```bash
source venv/bin/activate
echo "yes" | python scripts/clone_reference_data_to_staging.py
```

**Check Railway port configuration:**
- Railway Dashboard → Service → Settings → Networking → Target port
- Should match app's PORT env var (check logs: `PORT env var: 8080`)

