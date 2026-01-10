# GOB Alpha Launch Plan - 2-3 Day Timeline

**Target Launch Date:** 2-3 days from start  
**Goal:** Get alpha live with full functionality  
**Focus:** Functionality first, design polish later  
**Strategy:** Staging first, then quick production clone

---

## Overview

This plan prioritizes getting the application live and functional. Frontend design improvements and framework migrations (React/Angular) are explicitly deferred until after alpha launch.

**Current Status:**
- ✅ MongoDB Atlas account (already connected locally)
- ✅ Domain ownership (geekedoutbasketball.com)
- ✅ Codebase ready for deployment
- ✅ Phase 3 (Code Updates) - COMPLETE
- ✅ Task 0 (Button Updates) - COMPLETE
- ✅ Task 1.3 (Persistence Correctness) - COMPLETE (Verified on staging)
- ⏳ Task 1.1 (Go-live Foundations - Staging/Production Environments) - IN PROGRESS
- ⏳ Task 1.2 (Frontend ↔ Backend Contract) - VERIFIED (API config working)
- ⏳ Task 2 (Database Optimization) - PENDING

---

## Revised Work Plan Structure

### Task 0: Button Updates (COMPLETE ✅)
**Priority:** 🔴 HIGH - Streamlines UI for persistence system  
**Estimated Time:** 1-2 hours  
**Status:** ✅ COMPLETE

**Scope:**
- Playbooks page: Change "Submit Playbooks" → "Save Playbooks"
- Game Plan page: 
  - Remove "Playbooks" button
  - Add "Save Game Plan" button (only button that saves to DB)
  - Make "Back To Lineup" and "Play Game" nav-only (comment out save logic)
  - Add unsaved changes warning popup (reuse Playbooks pattern)
- Lineup Selection page: Add "Playbooks" button (vertically stacked between "Game Plan" and "Box Score")

**Dependencies:** None

---

### Task 1: Persistence Foundation + Go-Live Functionality (MUST-HAVE)
**Priority:** 🔴 CRITICAL - Blocks go-live  
**Estimated Time:** 4-6 hours  
**Status:** ⏳ IN PROGRESS (Persistence Correctness ✅ COMPLETE)

**Goal:** The application exists reliably on the internet (staging + production), and persistence behaves correctly enough that two weeks of testing and polish produce trustworthy results.

**Scope:**
1. **Go-live foundations:**
   - Staging and production environments exist and are independently functional
   - Frontend and backend are correctly wired in each environment
   - Database connectivity is verified and stable
   - Environment separation is clean (no accidental cross-talk)

2. **Frontend ↔ backend contract:**
   - Single, centralized mechanism for frontend to determine which backend to communicate with
   - All frontend→backend communication flows through that mechanism
   - Backend access controls (CORS) configured to match actual domains

3. **Persistence correctness:** ✅ **COMPLETE** (Verified on staging - January 2026)
   - ✅ Save Playbooks commits changes durably (survives refresh, logout, re-login) - **VERIFIED ON STAGING**
   - ✅ Save Game Plan commits changes durably (survives refresh, logout, re-login) - **VERIFIED ON STAGING**
   - ✅ Lineup persistence: **NO CHANGES NEEDED** (current flow works perfectly - URL params → gameplay → periodic saves)

**Definition of Done:**
- ✅ **Persistence Correctness:** Staging supports end-to-end usage with reliable persistence (save → refresh → data intact) - **COMPLETE (January 2026)**
- ⏳ **Go-live Foundations:** Staging and production environments exist and are independently functional
- ✅ **Frontend ↔ Backend Contract:** Verified (API config working, CORS configured)
- ✅ **Persistence Verification:** Save Playbooks and Save Game Plan verified working on staging
- ⏳ **Production Readiness:** Production can be cloned from staging via configuration, not rework
- ✅ **Error Signaling:** No silent persistence failures (clear success/error signaling)
- ✅ **Testing Confidence:** Can run two weeks of testing without uncertainty about deployment or data correctness

**Dependencies:** Task 0 must be complete ✅

**Completion Status:**
- [x] **3. Persistence Correctness** - COMPLETE (Verified on staging)
  - [x] Save Playbooks persistence verified on staging
  - [x] Save Game Plan persistence verified on staging
  - [x] Lineup persistence confirmed working (no changes needed)
- [x] **1. Go-live Foundations** - ✅ COMPLETE (January 2026)
  - [x] ✅ Staging backend deployed and verified (Railway: `gob-simplified-staging.up.railway.app`)
  - [x] ✅ Staging frontend deployed and verified (Netlify: `gob-test.netlify.app`)
  - [x] ✅ Database connectivity verified and stable (`gob-staging` database created and populated)
  - [x] ✅ Environment separation verified (staging uses `gob-staging`, production uses `gob`)
  - [x] ✅ Railway port configuration fixed (target port updated from 8000 to 8080)
  - [x] ✅ Reference data cloned to staging (133 documents: teams, players, plays, defenses, skeletons)
  - [x] ✅ Team selection working in staging (CORS and routing verified)
  - [ ] Production backend ready (can clone from staging)
  - [ ] Production frontend ready (can clone from staging)
  - **📋 Detailed Checklist:** See `docs/To Do/Task_1_1_Go_Live_Foundations_Verification.md`
  - **📋 Setup Notes:** See `docs/To Do/setup_staging_database.md` for Railway port fix and database cloning process
- [x] **2. Frontend ↔ Backend Contract** - COMPLETE
  - [x] Centralized API config mechanism in place
  - [x] All API calls use centralized config
  - [x] CORS configured for staging/production domains

---

### Task 2: Database Calls + Macro Persistence System (PERFORMANCE & SCALE)
**Priority:** 🟡 MEDIUM - Performance optimization  
**Estimated Time:** 8-12 hours  
**Status:** ⏳ PENDING (Waiting on Task 1)

**Goal:** Reduce query explosion and establish sustainable data access patterns so the app performs well and costs remain controlled under concurrent usage.

**Scope:**
- Identify and prioritize worst query offenders (pages/endpoints triggering dozens of DB calls)
- Reduce database calls per request through: batching, aggregation, projections, composite read patterns
- Introduce macro-level persistence patterns only where justified (settings snapshots, pre-computed summaries, materialized read models)
- Add measurement and visibility (query counts, response times)

**Definition of Done:**
- Highest-impact page/endpoint drops from ~35-40 DB calls to single digits
- Response times materially improve and remain stable under expected concurrency
- Data access patterns are efficient, predictable, and cost-aware

**Dependencies:** Task 1 must be complete

**Note:** Advanced patterns (CQRS, background workers, caching layers) should be treated as tools, not defaults, and introduced incrementally where they clearly move the needle.

---

## Timeline Breakdown

### Day 1: Code Fixes & Staging Backend (4-6 hours)

#### Phase 3 - Code Updates (COMPLETE ✅)
**Priority:** 🔴 CRITICAL - Blocks everything else  
**Estimated Time:** 2-3 hours  
**Status:** ✅ COMPLETE

**Tasks:**
1. Create `FrontEnd/static/js/config/api-config.js`
   - Centralized API base URL configuration
   - Environment detection (local/staging/production)
   - **CRITICAL:** Must handle default Railway/Netlify domains (e.g., `your-app.railway.app`, `your-app.netlify.app`)
   - Override capability for testing
   - **Note:** This is runtime config (not build-time) since frontend is plain static JS

2. Update all frontend API calls
   - Find all `fetch()` calls in frontend code
   - Replace relative URLs with `API_CONFIG.getBaseUrl()`
   - Test each updated endpoint locally

3. Fix CORS configuration in `BackEnd/api/api.py`
   - Replace `allow_origin_regex=".*"` with environment-based allow list
   - **CRITICAL:** Include default Railway/Netlify domains initially (e.g., `*.railway.app`, `*.netlify.app`)
   - Add production and staging custom domains
   - Keep localhost for development
   - **Note:** CORS must match actual testing domains, not just final ideal. Tighten to custom domains only after DNS is configured.

4. Conditionally disable static file serving
   - Only serve static files in development
   - Disable in production (Netlify handles this)

5. Test locally
   - Verify all API calls work with new config
   - Test CORS with different origins
   - Ensure no regressions

**Deliverables:**
- ✅ API config file created
- ✅ All API calls updated
- ✅ CORS properly configured
- ✅ Local testing complete

**Dependencies:** None - can start immediately

---

#### Phase 1 - Backend Deployment to STAGING (Railway) - Day 1 (2-3 hours)
**Priority:** 🔴 HIGH - STAGING FIRST, NOT PRODUCTION  
**Estimated Time:** 2-3 hours  
**Status:** ⏳ Ready to start

**⚠️ CRITICAL PRINCIPLE:** Staging is the first real deployment. Production should be a clone of proven staging, not where things are first tested.

**Tasks:**
1. Create Railway account
   - Sign up at railway.app
   - Connect GitHub account

2. Create new Railway project for STAGING
   - Name: `gob-backend-staging` (NOT production)
   - Connect to GitHub repository
   - Select `develop` branch (or create `develop` branch from `main`)

3. **CRITICAL: MongoDB Atlas Networking Setup**
   - **Problem:** Railway's outbound IPs may not be static, making IP whitelisting unreliable
   - **Solution for Alpha (2-3 day timeline):**
     - **Use 0.0.0.0/0 (allow all IPs)** in Atlas network access - **ACCEPTABLE FOR ALPHA**
     - Document this is temporary, plan to tighten post-launch
     - This is the #1 silent failure risk - test connection FIRST
   - **Action:** Configure Atlas network access BEFORE deploying backend
   - Get staging MongoDB connection string (use existing Atlas cluster or create staging cluster)

4. Configure environment variables for STAGING
   - `MONGO_URI` - **Staging** MongoDB Atlas connection string
   - `ENVIRONMENT=staging`
   - `CORS_ORIGINS` - Leave empty initially (default Railway/Netlify domains handled by regex)
   - `PORT` - Railway sets this automatically (read via `$PORT`)

5. Configure build settings
   - Build command: (auto-detected, or specify if needed)
   - Start command: `uvicorn BackEnd.api.api:app --host 0.0.0.0 --port $PORT`
   - Python version: (Railway auto-detects from requirements.txt)

6. Deploy and test STAGING
   - Trigger initial deployment
   - Check build logs for errors
   - Test API endpoints using Railway's default domain (e.g., `https://gob-backend-staging.railway.app`)
   - **CRITICAL:** Verify MongoDB connection works (this is the #1 silent failure risk)
   - Test all API endpoints end-to-end
   - Document any issues

7. **SKIP custom domain for now** - use default Railway domain (e.g., `gob-backend-staging.railway.app`)
   - Custom domains can be added later (not blocking for alpha)

**Deliverables:**
- ✅ Backend deployed to Railway STAGING
- ✅ API endpoints accessible via default Railway domain
- ✅ **MongoDB connection verified** (critical - test this first!)
- ✅ Environment variables configured
- ✅ Atlas network access configured (documented as temporary for alpha)

**Dependencies:** Phase 3 must be complete

**Testing Checklist:**
- [ ] **MongoDB connection works** (test FIRST - this is #1 failure risk)
- [ ] `/api/teams` endpoint works
- [ ] `/api/simulate-quarter` endpoint works
- [ ] Database queries succeed
- [ ] CORS headers present in responses
- [ ] No errors in Railway logs

---

### Week 2: Frontend Deployment & Integration (Days 8-14)

#### Phase 4 - Frontend Deployment to STAGING (Netlify) - Day 1-2 (1-2 hours)
**Priority:** 🔴 HIGH - STAGING FIRST  
**Estimated Time:** 1-2 hours  
**Status:** ⏳ Waiting on Phase 1 (staging backend)

**Tasks:**
1. Create Netlify account
   - Sign up at netlify.com
   - Connect GitHub account

2. Create new site for STAGING
   - Connect to GitHub repository
   - Select `develop` branch (matching staging backend)
   - Name: `gob-frontend-staging` (or similar)

3. Configure build settings
   - Base directory: (root)
   - Publish directory: `FrontEnd/static`
   - Build command: (none - static files, no build needed)
   - Python version: (not needed for static site)

4. Configure environment variables (if needed)
   - Only if using build-time injection
   - Otherwise, API config handles runtime detection (preferred)

5. Deploy and test STAGING
   - Trigger initial deployment
   - Check deployment logs
   - Test site using Netlify's default domain (e.g., `https://gob-frontend-staging.netlify.app`)
   - **CRITICAL:** Verify API calls work (pointing to staging Railway backend)
   - Test all frontend features end-to-end
   - Verify CORS works (frontend on Netlify default domain → backend on Railway default domain)

6. **SKIP custom domain for now** - use default Netlify domain (e.g., `gob-frontend-staging.netlify.app`)
   - Custom domains can be added later (not blocking for alpha)

**Deliverables:**
- ✅ Frontend deployed to Netlify STAGING
- ✅ Site accessible via default Netlify domain
- ✅ API calls working (staging backend)
- ✅ Environment variables configured (if needed)
- ✅ Full end-to-end testing complete in staging

**Dependencies:** Phase 1 (staging backend) must be complete

**Testing Checklist:**
- [ ] Homepage loads on default Netlify domain
- [ ] API calls succeed (check browser console - verify staging backend URL)
- [ ] No CORS errors (default Netlify → default Railway)
- [ ] Game simulation works end-to-end (test one full game)
- [ ] Data persistence works (create game, save, reload)

---

#### Phase 2 - Database Setup & Staging Verification - Day 2 (1-2 hours)
**Priority:** 🔴 HIGH - Must verify staging works before production  
**Estimated Time:** 1-2 hours  
**Status:** ⏳ After staging deployment complete (can run in parallel with frontend)

**Tasks:**
1. **CRITICAL: Verify MongoDB Atlas networking for staging**
   - Confirm staging backend can connect to Atlas
   - Test database operations from staging backend
   - Document actual Railway outbound IPs (if using IP whitelist)
   - **If connection fails:** This is the #1 silent failure - fix before proceeding

2. Verify MongoDB Atlas setup
   - Confirm staging cluster exists and works
   - Verify connection string format
   - Test connection from local environment

3. Configure Atlas security (staging)
   - Create database user with appropriate permissions
   - **Network access:** Use 0.0.0.0/0 for alpha (documented as temporary)
   - OR: Configure IP whitelist if Railway IPs are static (verify first!)

4. **CRITICAL: Full staging integration testing**
   - Test full game flow (create → play → save)
   - Test franchise mode
   - Test tournament mode
   - Test training system
   - Verify data persistence
   - Test all features end-to-end
   - **DO NOT proceed to production until staging is fully verified**

**Deliverables:**
- ✅ Staging database configured and verified
- ✅ MongoDB connection confirmed working from staging backend
- ✅ Full staging integration tests passing
- ✅ All features working end-to-end in staging
- ✅ **Staging verified as production-ready**

**Dependencies:** Phase 1 (staging backend) and Phase 4 (staging frontend) must be complete

**Testing Checklist:**
- [ ] **MongoDB connection works from staging backend** (test FIRST - #1 failure risk)
- [ ] Can create and simulate a game
- [ ] Can save and load game state
- [ ] Data persists across sessions
- [ ] **Staging is production-ready** (critical gate - do not proceed to production until this passes)

---

### Week 3: Staging Environment & Production Launch Prep (Days 15-23)

#### Phase 5 - Production Deployment (Clone of Verified Staging) - Day 2-3 (2-3 hours)
**Priority:** 🔴 HIGH - But only after staging is proven  
**Estimated Time:** 2-3 hours  
**Status:** ⏳ Waiting on staging verification (Phase 2)

**⚠️ CRITICAL PRINCIPLE:** Production is a clone of proven staging. Do not deploy to production until staging is fully verified and working.

**Tasks:**
1. Create production Railway project
   - Create new project: `gob-backend-prod`
   - Connect to `main` branch
   - **Clone all settings from verified staging project**
   - Only difference: Use production MongoDB connection string

2. Configure environment variables for PRODUCTION
   - `MONGO_URI` - **Production** MongoDB Atlas connection string
   - `ENVIRONMENT=production`
   - `CORS_ORIGINS` - Include default Railway domain AND default Netlify domain AND custom production domains (when ready)
   - `PORT` - Railway sets this automatically

3. Deploy production backend
   - Trigger deployment
   - Verify it matches staging behavior
   - Test API endpoints using Railway's default domain
   - Verify MongoDB connection

4. Create production Netlify site
   - Create new site from `main` branch
   - **Clone all settings from verified staging site**
   - Configure same build settings
   - Deploy and test

5. Test production deployment
   - Test site using Netlify's default domain
   - Verify API calls work (production backend)
   - Test all features end-to-end
   - Compare production vs staging (should be identical)

6. **DO NOT** set up custom domains yet - use default domains for production initially

**Deliverables:**
- ✅ Production backend deployed (clone of staging)
- ✅ Production frontend deployed (clone of staging)
- ✅ Production verified working (matches staging)
- ✅ Both environments using default domains

**Dependencies:** Staging must be fully verified and working (Phase 2 complete)

**Testing Checklist:**
- [ ] Production backend matches staging behavior
- [ ] Production frontend matches staging behavior
- [ ] Core game flow works in production (create → play → save)
- [ ] Production and staging are isolated (different databases)
- [ ] MongoDB connection works in production

---

#### Optional: Custom Domains & DNS Configuration - Day 3+ (if time permits)
**Priority:** 🟢 LOW - Can be done post-launch  
**Estimated Time:** 1-2 hours  
**Status:** ⏳ Optional - not blocking for alpha

**Tasks (Optional - can defer):**
1. Configure custom domains for PRODUCTION
   - Add `www.geekedoutbasketball.com` → Netlify production site
   - Add `api.geekedoutbasketball.com` → Railway production project
   - Configure DNS at Namecheap
   - Wait for DNS propagation (24-48 hours)
   - Update CORS to include custom production domains
   - Update API config to detect production custom domain

2. (Optional) Configure custom domains for STAGING
   - Can be done later if needed

3. (Optional) Tighten CORS configuration
   - Remove default Railway/Netlify domains from CORS
   - Keep only custom domains
   - Can be done post-launch

2. SSL certificate verification
   - Verify HTTPS works on all domains
   - Check certificate validity
   - Test mixed content (no HTTP resources)

3. Performance testing
   - Test page load times
   - Test API response times
   - Identify bottlenecks
   - Optimize if needed (defer if not critical)

4. Security audit
   - Review CORS configuration
   - Review environment variables
   - Check for exposed secrets
   - Verify input validation

5. Error handling review
   - Test error scenarios
   - Verify error messages are user-friendly
   - Check error logging

**Deliverables:**
- ✅ Custom domains configured
- ✅ SSL certificates verified
- ✅ Performance acceptable
- ✅ Security review complete

**Dependencies:** All previous phases complete

**Testing Checklist:**
- [ ] All domains resolve correctly
- [ ] HTTPS works on all domains
- [ ] No mixed content warnings
- [ ] Page load times acceptable
- [ ] API response times acceptable
- [ ] No security vulnerabilities
- [ ] Error handling works correctly

---

#### Final Testing & Launch - Day 3 (1-2 hours)
**Priority:** 🔴 CRITICAL  
**Estimated Time:** 1-2 hours  
**Status:** ⏳ Launch day

**Tasks:**
1. Quick end-to-end testing
   - Test core game flow (create → play → save)
   - Test one game mode (Single Game is fine)
   - Verify no critical errors

2. Basic monitoring
   - Check Railway logs for errors
   - Check Netlify logs for errors
   - Verify API is responding

3. Launch checklist
   - [ ] Core game flow works
   - [ ] No critical errors in logs
   - [ ] MongoDB connection stable
   - [ ] Ready to launch

4. Launch
   - Announce alpha launch
   - Monitor for first 30 minutes
   - Be ready to hotfix if needed

**Deliverables:**
- ✅ All tests passing
- ✅ Documentation complete
- ✅ Monitoring configured
- ✅ Alpha launched

**Dependencies:** All previous phases complete

**Launch Checklist:**
- [ ] Production site accessible (default domains OK)
- [ ] Core game flow works
- [ ] No critical errors
- [ ] Ready to launch

---

## Risk Mitigation

### High-Risk Items
1. **MongoDB Atlas Networking** - #1 silent failure risk
   - **Problem:** Railway outbound IPs may not be static
   - **Mitigation:** Use 0.0.0.0/0 for alpha (documented as temporary)
   - **Test:** Verify connection FIRST before proceeding

2. **CORS Configuration** - Could block all API calls
   - **Mitigation:** ✅ Already fixed - includes default Railway/Netlify domains
   - **Test:** Verify CORS works with default domains

3. **API URL Configuration** - Could break all API calls
   - **Mitigation:** ✅ Already fixed - all calls use centralized config
   - **Test:** Verify API calls work in staging

### Medium-Risk Items
1. **Environment Variable Mismatch** - Could cause runtime errors
   - **Mitigation:** Document all required variables, test in staging first

2. **Build/Deploy Failures** - Could delay deployment
   - **Mitigation:** Test build process locally, have rollback plan

3. **Performance Issues** - Could impact user experience
   - **Mitigation:** Monitor performance, optimize critical paths only

---

## Success Criteria

### Must Have (Alpha Launch)
- ✅ Core game flow works (create → play → save)
- ✅ Game simulation works end-to-end
- ✅ Data persists correctly
- ✅ No critical errors
- ✅ Site accessible (default domains OK)
- ✅ API accessible (default domains OK)

### Nice to Have (Can Defer)
- ⏸️ Custom domains (default Railway/Netlify domains work fine)
- ⏸️ Performance optimizations (can optimize after launch)
- ⏸️ Advanced monitoring (basic monitoring is fine)
- ⏸️ Error tracking service (can add after launch)
- ⏸️ All game modes tested (Single Game is sufficient for alpha)

### Explicitly Deferred
- ❌ Frontend framework migration (React/Angular)
- ❌ Frontend design polish
- ❌ Authentication system
- ❌ Payment integration
- ❌ Advanced analytics

---

## Dependencies & Prerequisites

### Required Accounts
- ✅ MongoDB Atlas account (already have)
- ⏳ Railway account (need to create)
- ⏳ Netlify account (need to create)
- ✅ Domain ownership (already have)

### Required Knowledge
- Basic understanding of environment variables
- Basic understanding of DNS (or willingness to follow instructions)
- Ability to test API endpoints (Postman or browser)

### Required Access
- GitHub repository access
- Namecheap DNS access
- MongoDB Atlas cluster access

---

## Notes

### Timeline Flexibility
- This is an aggressive 23-day timeline
- Some tasks can be done in parallel
- Buffer time built into final days
- Can extend timeline if needed (functionality > speed)

### Communication
- Update this document as tasks complete
- Note any blockers immediately
- Document any deviations from plan

### Post-Launch
- Monitor for first 48 hours closely
- Be ready to hotfix critical issues
- Collect user feedback
- Plan next iteration

---

## Status Tracking

**Last Updated:** January 2026  
**Current Phase:** ⏳ Task 1 (Persistence Foundation) - IN PROGRESS  
**Progress:**
- ✅ Task 1.3 (Persistence Correctness) - COMPLETE - Verified on staging (Game Plan & Playbooks)
- ⏳ Task 1.1 (Go-live Foundations) - Need to verify staging/production environments fully deployed
- ✅ Task 1.2 (Frontend ↔ Backend Contract) - COMPLETE (API config working, CORS configured)

**Blockers:** None  
**Next Action:** Verify staging/production environments are fully set up and functional, then proceed to Task 2 (Database Optimization) or production launch preparation

---

## Decisions Made

1. **Staging Environment Priority**
   - ✅ **Decision:** Staging is FIRST deployment (not optional)
   - **Rationale:** Production should be a clone of proven staging, not where things are first tested

2. **Custom Domains Priority**
   - ✅ **Decision:** Use default Railway/Netlify domains for alpha
   - **Rationale:** Faster setup, no DNS delays, can add custom domains post-launch

3. **MongoDB Atlas Networking**
   - ✅ **Decision:** Use 0.0.0.0/0 (allow all IPs) for alpha
   - **Rationale:** Railway IPs may not be static, this is #1 failure risk. Document as temporary.

4. **Data Migration**
   - ✅ **Decision:** Only migrate if there's important test data
   - **Rationale:** Can start fresh for alpha

---

## Quick Start Guide

**You're ready to proceed!** Phase 3 (Code Updates) is complete. Next steps:

1. **Test locally** (15 minutes)
   - Start backend: `cd BackEnd && uvicorn api.api:app --reload`
   - Open frontend: `http://localhost:8000/static/homepage.html`
   - Test a game flow
   - Verify API calls work

2. **Set up Railway staging** (1-2 hours)
   - Create account, connect GitHub
   - Create staging project from `develop` branch
   - Set environment variables
   - Deploy and test

3. **Set up Netlify staging** (1 hour)
   - Create account, connect GitHub
   - Create staging site from `develop` branch
   - Deploy and test

4. **Verify staging works** (30 minutes)
   - Test full game flow
   - Verify MongoDB connection
   - Fix any issues

5. **Clone to production** (1-2 hours)
   - Create production Railway project from `main` branch
   - Create production Netlify site from `main` branch
   - Test and launch

**Total Time:** 4-6 hours of focused work over 2-3 days

