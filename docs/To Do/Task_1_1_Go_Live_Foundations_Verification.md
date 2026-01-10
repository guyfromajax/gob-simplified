# Task 1.1: Go-Live Foundations Verification Checklist

**Date Created:** January 2026  
**Status:** ⏳ IN PROGRESS  
**Priority:** 🔴 CRITICAL - Blocks go-live  
**Related:** Task 1 (Persistence Foundation) from Go Live Plan

## Overview

This checklist verifies that staging and production environments are fully set up, independently functional, and ready for go-live. All items must be verified before proceeding to production deployment or Task 2.

## Completion Status

**Overall Progress:** ~14% (4/28 items verified) - Section 1 partially complete

### Staging Backend (Railway)
- Progress: 4/14 items verified (28%)
- Status: ⏳ IN PROGRESS - Basic endpoints verified, needs Railway dashboard checks

### Staging Frontend (Netlify)
- Progress: 0/5 items verified
- Status: ⏳ Not Verified

### Database Connectivity
- Progress: 0/4 items verified
- Status: ⏳ Not Verified

### Environment Separation
- Progress: 0/4 items verified
- Status: ⏳ Not Verified

### Production Readiness
- Progress: 0/5 items verified
- Status: ⏳ Not Verified

### End-to-End Verification
- Progress: 0/4 items verified
- Status: ⏳ Not Verified

---

## 1. Staging Backend (Railway) Verification

### 1.1 Deployment Status
- [x] **Backend is deployed to Railway STAGING** ✅ VERIFIED (January 2026)
  - Railway project name: `gob-simplified-staging` (inferred from URL)
  - Railway URL: `https://gob-simplified-staging.up.railway.app` ✅ VERIFIED
  - Branch connected: `develop` (or `main` if no develop branch) - ⏳ Needs manual verification in Railway dashboard
  - Last deployment: `_________________` - ⏳ Check Railway dashboard
  - Build status: [ ] Success | [ ] Failed | [ ] Unknown - ⏳ Check Railway dashboard

### 1.2 API Endpoints Verification
- [x] **Root endpoint works:** ✅ VERIFIED (January 2026)
  - URL: `GET /`
  - Expected: `{"message": "GOB Simulation API is live"}`
  - Actual: `{"message":"GOB Simulation API is live"}` ✅ MATCH
  - Response time: `243ms`
  - Status: ✅ Pass

- [x] **Teams endpoint works:** ✅ VERIFIED (January 2026)
  - URL: `GET /teams`
  - Expected: Array of team objects
  - Actual: Returns array with team objects (verified first team: Bentley-Truman)
  - Response time: `221ms`
  - Status: ✅ Pass

- [ ] **Game state endpoint works:**
  - URL: `GET /api/game/{game_id}?quarter=1`
  - Test game_id: `_________________` (needs valid game_id from staging database)
  - Expected: Game state object with teams, score, etc.
  - Status: ⏳ Not Tested (requires valid game_id - can test after creating a game)
  - Note: Endpoint responds correctly (404 for invalid game_id, which is expected)

- [ ] **Simulate quarter endpoint works:**
  - URL: `POST /api/simulate-quarter`
  - Test payload: (sample quarter simulation request)
  - Expected: Game state with turns array
  - Response time: `_________________` ms
  - Status: ⏳ Not Tested (requires full request payload - can test after creating a game)

### 1.3 Environment Variables
- [ ] **MONGO_URI is configured:**
  - Format: `mongodb+srv://...`
  - Database name: `_________________` (should be staging-specific, e.g., `gob-staging`)
  - Status: [ ] ✅ Configured | [ ] ❌ Missing | [ ] ⚠️ Wrong Format

- [ ] **ENVIRONMENT is set:**
  - Value: `staging` (should be exactly "staging")
  - Status: [ ] ✅ Correct | [ ] ❌ Missing | [ ] ⚠️ Wrong Value

- [x] **CORS_ORIGINS is configured:** ✅ VERIFIED (January 2026)
  - Value: Configured in code (allows `*.railway.app`, `*.netlify.app`, and explicitly `https://gob-test.netlify.app`)
  - Includes: [x] Default Railway domain | [x] Default Netlify domain | [ ] Custom domains
  - Verified: CORS headers present and working
  - `access-control-allow-origin`: `https://gob-test.netlify.app` ✅
  - `access-control-allow-methods`: `DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT` ✅
  - `access-control-max-age`: `3600` ✅
  - Status: ✅ Configured and Working

- [ ] **PORT is configured:**
  - Railway sets automatically via `$PORT`
  - Status: [ ] ✅ Working | [ ] ❌ Not Set

### 1.4 MongoDB Connection
- [ ] **MongoDB connection works from staging backend:**
  - Test: Create a test document, read it back, delete it
  - Test command/logs: `_________________`
  - Connection time: `_________________` ms
  - Status: [ ] ✅ Connected | [ ] ❌ Failed | [ ] ⏳ Not Tested

- [ ] **Database operations succeed:**
  - Test: Save a game document, read it back
  - Test game_id: `_________________`
  - Status: [ ] ✅ Working | [ ] ❌ Failed | [ ] ⏳ Not Tested

### 1.5 Build & Deployment
- [ ] **Build command works:**
  - Command: (auto-detected or specified)
  - Build logs: [ ] No errors | [ ] Errors found: `_________________`
  - Status: [ ] ✅ Success | [ ] ❌ Fail

- [ ] **Start command works:**
  - Command: `uvicorn BackEnd.api.api:app --host 0.0.0.0 --port $PORT`
  - Application starts: [ ] ✅ Yes | [ ] ❌ No
  - Status: [ ] ✅ Working | [ ] ❌ Failed

### 1.6 Logging & Monitoring
- [ ] **Railway logs are accessible:**
  - Logs URL: `_________________`
  - Can view logs: [ ] ✅ Yes | [ ] ❌ No
  - Status: [ ] ✅ Accessible | [ ] ❌ Not Accessible

- [ ] **No critical errors in logs:**
  - Review last 24 hours of logs
  - Critical errors found: [ ] None | [ ] Some: `_________________`
  - Status: [ ] ✅ Clean | [ ] ⚠️ Warnings | [ ] ❌ Errors

---

## 2. Staging Frontend (Netlify) Verification

### 2.1 Deployment Status
- [ ] **Frontend is deployed to Netlify STAGING**
  - Netlify site name: `_________________`
  - Netlify URL: `https://_________________.netlify.app`
  - Branch connected: `develop` (or `main` if no develop branch)
  - Last deployment: `_________________`
  - Build status: [ ] Success | [ ] Failed | [ ] Unknown

### 2.2 Site Accessibility
- [ ] **Homepage loads:**
  - URL: `https://_________________.netlify.app/`
  - Redirects to: `mode-select.html` (expected)
  - Load time: `_________________` ms
  - Status: [ ] ✅ Loads | [ ] ❌ Fails | [ ] ⏳ Not Tested

- [ ] **Mode select page loads:**
  - URL: `https://_________________.netlify.app/mode-select.html`
  - All buttons visible: [ ] ✅ Yes | [ ] ❌ No
  - Status: [ ] ✅ Working | [ ] ❌ Broken

### 2.3 API Integration
- [ ] **API calls route to staging backend:**
  - Open browser console on staging frontend
  - Check network tab for API calls
  - API base URL: `_________________` (should be Railway staging URL)
  - Status: [ ] ✅ Correct | [ ] ❌ Wrong | [ ] ⏳ Not Verified

- [ ] **CORS is working (no CORS errors):**
  - Open browser console
  - CORS errors found: [ ] None | [ ] Some: `_________________`
  - Status: [ ] ✅ No Errors | [ ] ❌ CORS Errors

- [ ] **API calls succeed:**
  - Test: Load mode-select page (should call `/teams`)
  - Test: Start a game (should call `/api/init-game`)
  - All API calls succeed: [ ] ✅ Yes | [ ] ❌ Some Fail
  - Status: [ ] ✅ Working | [ ] ❌ Issues Found

### 2.4 Build Configuration
- [ ] **Build settings are correct:**
  - Publish directory: `FrontEnd/static`
  - Build command: (none - static site)
  - Base directory: (root)
  - Status: [ ] ✅ Correct | [ ] ❌ Wrong

- [ ] **Static assets load correctly:**
  - Test: Load an image from `/images/...`
  - Test: Load a script from `/js/...`
  - All assets load: [ ] ✅ Yes | [ ] ❌ Some Fail
  - Status: [ ] ✅ Working | [ ] ❌ Issues Found

### 2.5 Environment Variables (if needed)
- [ ] **Environment variables configured (if using build-time injection):**
  - Variables: `_________________`
  - Note: Should not be needed if using runtime API config (preferred)
  - Status: [ ] ✅ Configured | [ ] ⏸️ Not Needed | [ ] ❌ Missing

---

## 3. Database Connectivity Verification

### 3.1 MongoDB Atlas Configuration
- [ ] **Staging database cluster exists:**
  - Cluster name: `_________________`
  - Region: `_________________`
  - Status: [ ] ✅ Exists | [ ] ❌ Missing

- [ ] **Network access configured:**
  - Current setting: `_________________`
  - Recommended for alpha: `0.0.0.0/0` (allow all IPs) - **TEMPORARY**
  - Documented as temporary: [ ] ✅ Yes | [ ] ❌ No
  - Status: [ ] ✅ Configured | [ ] ❌ Not Configured

### 3.2 Connection String
- [ ] **Staging connection string is valid:**
  - Format: `mongodb+srv://username:password@cluster.mongodb.net/database?retryWrites=true&w=majority`
  - Database name: `_________________`
  - Status: [ ] ✅ Valid | [ ] ❌ Invalid | [ ] ⏳ Not Tested

- [ ] **Connection string is stored securely:**
  - Stored in: Railway environment variables (not in code)
  - Status: [ ] ✅ Secure | [ ] ❌ Exposed

### 3.3 Connection Stability
- [ ] **Connection is stable:**
  - Test: Make 10 sequential API calls that hit database
  - All succeed: [ ] ✅ Yes (10/10) | [ ] ⚠️ Partial | [ ] ❌ No
  - Average response time: `_________________` ms
  - Status: [ ] ✅ Stable | [ ] ⚠️ Unstable | [ ] ❌ Failed

- [ ] **Connection handles load:**
  - Test: Simulate 5 concurrent requests
  - All succeed: [ ] ✅ Yes | [ ] ❌ Some Fail
  - Status: [ ] ✅ Handles Load | [ ] ❌ Issues

---

## 4. Environment Separation Verification

### 4.1 Database Separation
- [ ] **Staging uses staging database:**
  - Staging backend MONGO_URI points to: `_________________` database
  - Database name contains: `staging` or `test` (or clearly staging-specific)
  - Status: [ ] ✅ Separate | [ ] ❌ Shared with Production

- [ ] **Production database exists separately:**
  - Production database name: `_________________`
  - Production cluster: `_________________`
  - Status: [ ] ✅ Exists | [ ] ⏸️ Not Created Yet (OK for now)

### 4.2 Configuration Separation
- [ ] **Staging environment variables are staging-specific:**
  - MONGO_URI: Points to staging database
  - ENVIRONMENT: Set to `staging`
  - CORS_ORIGINS: Includes staging domains only
  - Status: [ ] ✅ Separate | [ ] ❌ Shared

- [ ] **No cross-environment variable leakage:**
  - Review all environment variables in Railway staging project
  - Production URLs in staging: [ ] None | [ ] Found: `_________________`
  - Status: [ ] ✅ No Leakage | [ ] ❌ Leakage Found

### 4.3 Code/Deployment Separation
- [ ] **Staging deploys from `develop` branch:**
  - Railway staging connected to: `develop` branch
  - Netlify staging connected to: `develop` branch
  - Status: [ ] ✅ Correct | [ ] ❌ Wrong Branch

- [ ] **Production will deploy from `main` branch:**
  - Plan: Production deploys from `main` branch
  - Status: [ ] ✅ Planned | [ ] ⏸️ Not Set Up Yet (OK for now)

---

## 5. Production Readiness Verification

### 5.1 Production Backend Preparation
- [ ] **Production Railway project can be created:**
  - Plan: Create `gob-backend-prod` project
  - Will clone settings from: Staging Railway project
  - Status: [ ] ✅ Ready to Create | [ ] ⏸️ Not Needed Yet

- [ ] **Production environment variables identified:**
  - Production MONGO_URI: `_________________` (different from staging)
  - Production ENVIRONMENT: `production`
  - Production CORS_ORIGINS: `_________________`
  - Status: [ ] ✅ Identified | [ ] ⏸️ Not Needed Yet

### 5.2 Production Frontend Preparation
- [ ] **Production Netlify site can be created:**
  - Plan: Create production Netlify site
  - Will clone settings from: Staging Netlify site
  - Status: [ ] ✅ Ready to Create | [ ] ⏸️ Not Needed Yet

- [ ] **Production will connect to production backend:**
  - API config will detect production domain: `_________________`
  - Will point to: Production Railway backend
  - Status: [ ] ✅ Planned | [ ] ⏸️ Not Needed Yet

### 5.3 Production Database Preparation
- [ ] **Production database cluster ready:**
  - Cluster name: `_________________`
  - Connection string: `_________________`
  - Network access configured: [ ] ✅ Yes | [ ] ⏸️ Not Yet
  - Status: [ ] ✅ Ready | [ ] ⏸️ Not Needed Yet

---

## 6. End-to-End Verification

### 6.1 Full Game Flow Test
- [ ] **Complete game flow works in staging:**
  - Navigate to: `https://_________________.netlify.app/mode-select.html`
  - Select game mode: [ ] Single Game | [ ] Tournament | [ ] Franchise
  - Create/start a game
  - Play through at least 1 quarter
  - Save game state
  - Refresh page
  - Load saved game state
  - All steps succeed: [ ] ✅ Yes | [ ] ❌ Some Fail
  - Status: [ ] ✅ Working | [ ] ❌ Issues Found

### 6.2 Persistence Verification (Already Verified ✅)
- [x] **Save Playbooks persistence:** ✅ VERIFIED on staging
- [x] **Save Game Plan persistence:** ✅ VERIFIED on staging
- [x] **Lineup persistence:** ✅ VERIFIED (working via URL params)

### 6.3 Performance Check
- [ ] **Page load times are acceptable:**
  - Mode select page: `_________________` ms
  - Lineup page: `_________________` ms
  - Gameplay (court.html): `_________________` ms
  - All under 3 seconds: [ ] ✅ Yes | [ ] ❌ Some Slow
  - Status: [ ] ✅ Acceptable | [ ] ⚠️ Slow

- [ ] **API response times are acceptable:**
  - `/teams` endpoint: `_________________` ms
  - `/api/simulate-quarter` endpoint: `_________________` ms
  - `/franchise/command-center/data` endpoint: `_________________` ms
  - Most under 2 seconds: [ ] ✅ Yes | [ ] ❌ Some Slow
  - Status: [ ] ✅ Acceptable | [ ] ⚠️ Slow

### 6.4 Error Handling
- [ ] **Error messages are user-friendly:**
  - Test: Disconnect from internet, try API call
  - Test: Use invalid game_id
  - Error messages clear: [ ] ✅ Yes | [ ] ❌ Unclear
  - Status: [ ] ✅ Good | [ ] ⚠️ Needs Improvement

- [ ] **Errors are logged:**
  - Check Railway logs for error entries
  - Check Netlify logs for error entries
  - Errors logged: [ ] ✅ Yes | [ ] ❌ Not Logged
  - Status: [ ] ✅ Logged | [ ] ❌ Not Logged

---

## Verification Results Summary

### Overall Status
- **Date Verified:** `_________________`
- **Verified By:** `_________________`
- **Overall Status:** [ ] ✅ PASS | [ ] ❌ FAIL | [ ] ⚠️ PARTIAL

### Critical Issues Found
- [ ] None
- [ ] Issues found (list below):

1. `_________________`
2. `_________________`
3. `_________________`

### Non-Critical Issues Found
- [ ] None
- [ ] Issues found (list below):

1. `_________________`
2. `_________________`

### Next Steps
- [ ] All critical items pass - ready to proceed to production deployment
- [ ] Critical items need fixing - fix before proceeding
- [ ] Some items need attention - review before proceeding

**Recommended Action:**
`_________________`

---

## Notes & Observations

### Staging Environment Notes:
`_________________`
`_________________`

### Production Preparation Notes:
`_________________`
`_________________`

### Issues to Address Post-Launch:
`_________________`
`_________________`

---

## Related Documents

- `docs/Admin_Only_Docs/Go_Live_Plan.md` - Main go-live plan
- `docs/To Do/team_structure_unification_performance_issues.md` - Performance issues (separate concern)

---

## Update History

- **January 2026:** Document created

