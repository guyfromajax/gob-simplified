# Setting Up Staging Database (gob-staging)

**Date:** January 2026  
**Status:** ✅ APPROACH SELECTED - Ready for Railway Setup  
**Priority:** 🔴 CRITICAL - Required for environment separation  
**Approach:** ✅ Option A (Start Fresh) - Database auto-created on first write

## Overview

We need to create a separate `gob-staging` database for staging environment to ensure clean environment separation. The current `gob` database will be used for production.

**✅ CHOSEN APPROACH: Option A (Start Fresh)** - Database will be created automatically on first write. Reference data will be populated by app code.

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
1. Run clone script: `python scripts/clone_reference_data_to_staging.py`
2. Script clones reference collections: players, teams, plays, defenses, fcp_skeletons, hct_skeletons
3. Script skips game-specific collections: games, tournaments, franchises (start fresh)
4. Update Railway staging `MONGO_URI` to point to `gob-staging` database
5. Deploy staging backend - will use cloned reference data

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

### Step 1: Update Railway Staging Environment Variables

**✅ APPROACH CHOSEN: Option A (Start Fresh)** - No cloning needed. Database will be created automatically.

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

### Step 2: Verify Staging Database Connection

**Note:** With Option A (Start Fresh), the `gob-staging` database will be created automatically when the app first writes to it. No manual creation or cloning needed.

After updating Railway environment variables:

1. **Redeploy staging backend** (or restart if already deployed)
2. **Check Railway logs** for database connection message:
   ```
   📊 [DB CONFIG] Using database: gob-staging
   ```
3. **Test database connection** by creating a test game/tournament/franchise
4. **Verify database** in MongoDB Atlas - should see `gob-staging` database created (if starting fresh) or populated (if cloned)

### Step 3: Verify Environment Separation

**Check Production Database:**
- Production `MONGO_URI` should still point to `gob` database
- Production should continue using `gob` database
- No changes to production needed

**Check Staging Database:**
- Staging `MONGO_URI` points to `gob-staging` database (via `MONGO_DB_NAME` env var)
- Staging uses `gob-staging` database
- Staging and production databases are separate

## Testing Checklist

- [ ] Staging backend logs show: `📊 [DB CONFIG] Using database: gob-staging`
- [ ] Production backend logs show: `📊 [DB CONFIG] Using database: gob`
- [ ] Create test franchise in staging - appears in `gob-staging` database (not `gob`)
- [ ] Create test tournament in staging - appears in `gob-staging` database (not `gob`)
- [ ] Verify `gob` database unchanged (production data intact)
- [ ] Verify reference collections exist in `gob-staging` (if cloned) or can be populated
- [ ] Test game creation in staging works (uses `gob-staging` database)

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
- `scripts/clone_reference_data_to_staging.py` - Reference data cloning script
- `docs/Admin_Only_Docs/Go_Live_Plan.md` - Main go-live plan
- `docs/To Do/Task_1_1_Go_Live_Foundations_Verification.md` - Verification checklist

