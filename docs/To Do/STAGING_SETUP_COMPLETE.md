# Staging Environment Setup - Completion Summary

**Date Completed:** January 10, 2026  
**Status:** ✅ COMPLETE - Staging environment fully operational  
**Environment:** Staging (Railway + Netlify)

## Summary

Staging environment is now fully set up and operational. All critical issues have been resolved:
- ✅ Railway deployment working (port configuration fixed)
- ✅ CORS configured correctly
- ✅ Database connectivity established (`gob-staging`)
- ✅ Reference data cloned from production (133 documents)
- ✅ Team selection working end-to-end

## Issues Resolved

### 1. Railway Port Configuration (502 Errors)
**Issue:** All requests returned 502 "Application failed to respond"  
**Symptoms:**
- Health check failed (502)
- OPTIONS preflight requests failed (502)
- All endpoints returned 502
- App was running (startup logs appeared) but requests didn't reach it

**Root Cause:** Railway's "Target port" setting was 8000, but app was running on port 8080 (Railway's `$PORT` env var).

**Fix:**
- Railway Dashboard → Service → Settings → Networking
- Updated "Target port" from 8000 to 8080
- Requests immediately started working

**Lesson:** Always verify Railway target port matches actual app port (check logs: `PORT env var: 8080`)

### 2. Empty Staging Database (404 Team Not Found)
**Issue:** Team selection failed with 404 - `Available teams in database: []`  
**Root Cause:** `gob-staging` database was empty (new database, no reference data)

**Fix:**
```bash
source venv/bin/activate
echo "yes" | python scripts/clone_reference_data_to_staging.py
```

**Result:** 
- ✅ Cloned 96 players
- ✅ Cloned 8 teams
- ✅ Cloned 23 plays
- ✅ Cloned 4 defenses
- ✅ Cloned 1 fcp_skeletons document
- ✅ Cloned 1 hct_skeletons document
- **Total: 133 documents cloned**

**Lesson:** Staging database needs reference data populated before use. Cloning ensures consistency with production.

### 3. Team Name Lookup Case Sensitivity
**Issue:** Team lookup was case-sensitive, potentially failing with name mismatches  
**Fix:** Enhanced team lookup in `BackEnd/api/franchise_routes.py` with case-insensitive matching and multiple fallback strategies.

**Status:** Fixed but not tested (cloning resolved immediate issue)

## Current Configuration

### Railway Staging
- **Service:** `gob-simplified-staging`
- **URL:** `https://gob-simplified-staging.up.railway.app`
- **Port:** 8080 (verified in logs, configured in Railway)
- **Database:** `gob-staging` (via `MONGO_DB_NAME` env var)
- **Environment:** Staging (`ENVIRONMENT=staging`)

### Netlify Staging
- **Site:** `gob-test`
- **URL:** `https://gob-test.netlify.app`
- **API Backend:** `https://gob-simplified-staging.up.railway.app`

### Database
- **Staging DB:** `gob-staging` (MongoDB Atlas)
- **Production DB:** `gob` (MongoDB Atlas)
- **Reference Data:** Cloned from production ✅
- **Collections:** players, teams, plays, defenses, fcp_skeletons, hct_skeletons

## Verification Tests

✅ **Health Check:** `GET /health` returns 200 OK  
✅ **CORS:** OPTIONS preflight requests return 200 with proper CORS headers  
✅ **Team Selection:** POST `/franchise/select-team` works correctly  
✅ **Database:** Railway logs show `📊 [DB CONFIG] Using database: gob-staging`  
✅ **Environment Separation:** Staging uses `gob-staging`, production uses `gob`

## Files Modified

- `BackEnd/api/franchise_routes.py` - Enhanced team lookup (case-insensitive)
- `BackEnd/api/api.py` - CORS middleware and debug logging
- `BackEnd/db.py` - Configurable database name support
- `Procfile` - Railway startup command
- `railway.json` - Railway deployment configuration

## Next Steps

1. ✅ Staging backend verified and operational
2. ⏳ Verify staging frontend fully functional (team selection working ✅)
3. ⏳ Test end-to-end franchise flow in staging
4. ⏳ Prepare production deployment (clone staging config)

## Related Documentation

- `docs/To Do/setup_staging_database.md` - Complete staging database setup guide
- `docs/To Do/Task_1_1_Go_Live_Foundations_Verification.md` - Verification checklist
- `docs/Admin_Only_Docs/Go_Live_Plan.md` - Main go-live plan
- `scripts/clone_reference_data_to_staging.py` - Reference data cloning script

## Important Notes

**Railway Port Configuration:**
- Always check Railway logs for actual PORT: `PORT env var: XXXX`
- Update Railway Settings → Networking → Target port to match
- Common issue: App runs on 8080, Railway targets 8000 → 502 errors

**Database Cloning:**
- Run clone script when setting up new staging environment
- Clones reference data only (teams, players, plays, skeletons)
- Skips game-specific data (games, tournaments, franchises start fresh)
- Must be run from project root with venv activated

**CORS Configuration:**
- CORS middleware must be added BEFORE routers in FastAPI
- Explicitly include staging Netlify domain: `https://gob-test.netlify.app`
- Use `allow_origin_regex` for default Railway/Netlify domains
- Test with `curl -i -X OPTIONS` to verify CORS headers

