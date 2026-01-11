# Phase 5: Production Deployment Checklist

**Date Created:** January 11, 2026  
Date Completed: January 11, 2026
Status: ✅ COMPLETE
**Related:** Phase 5 from Go Live Plan

## Overview

This checklist guides the production deployment process. Production should be a clone of verified staging, with only the database connection string and environment variables differing.

**⚠️ CRITICAL PRINCIPLE:** Production is a clone of proven staging. All settings should match staging except for:
- Database name (`gob` instead of `gob-staging`)
- Environment variable (`ENVIRONMENT=production`)

---

## Completion Status

**Overall Progress:** 5/5 tasks complete (100%) ✅

### 1. Production Railway Backend
- Status: ✅ COMPLETE (January 11, 2026)
- Progress: 4/4 items

### 2. Production Environment Variables
- Status: ✅ COMPLETE (January 11, 2026)
- Progress: 4/4 items

### 3. Production Backend Deployment
- Status: ✅ COMPLETE (January 11, 2026)
- Progress: 3/3 items

### 4. Production Netlify Frontend
- Status: ✅ COMPLETE (January 11, 2026)
- Progress: 4/4 items

### 5. Production Testing
- Status: ✅ COMPLETE (January 11, 2026)
- Progress: 5/5 items

---

## 1. Production Railway Backend Setup

### 1.1 Create Production Railway Project
- [ ] **Navigate to Railway dashboard:** https://railway.app
- [ ] **Create new project:**
  - Click "New Project"
  - Select "Deploy from GitHub repo"
  - Select repository: `gob-simplified` (or your repo name)
  - Project name: `gob-backend-prod`
  - Status: [ ] ✅ Created | [ ] ❌ Failed

### 1.2 Configure Git Branch
- [ ] **Connect to `main` branch:**
  - Go to project settings → Source
  - Set branch to: `main`
  - Status: [ ] ✅ Connected | [ ] ❌ Failed
  - **Note:** Staging uses `develop` branch, production uses `main` branch

### 1.3 Configure Build Settings
- [ ] **Verify build settings match staging:**
  - Root Directory: (root, empty/default)
  - Build Command: (auto-detected or empty)
  - Start Command: (auto-detected or empty)
  - **Reference:** Staging uses default Railway Python detection
  - Status: [ ] ✅ Matches | [ ] ⚠️ Different (note differences)

### 1.4 Configure Port Settings
- [ ] **Set target port:**
  - Go to Settings → Network
  - Set "Target port" to: `8080`
  - **Reference:** Staging uses port 8080 (fixed in Task 1.1)
  - Status: [ ] ✅ Set to 8080 | [ ] ❌ Not Set

---

## 2. Production Environment Variables

### 2.1 MongoDB Connection String
- [ ] **Set MONGO_URI:**
  - Go to project → Variables tab
  - Add variable: `MONGO_URI`
  - Value: Same connection string as staging ✅
  - **Note:** Production uses same cluster, different database name
  - Status: [ ] ✅ Set | [ ] ❌ Not Set

### 2.2 Database Name
- [ ] **Set MONGO_DB_NAME:**
  - Variable: `MONGO_DB_NAME`
  - Value: `gob` (production database name)
  - **Note:** Staging uses `gob-staging`, production uses `gob`
  - Status: [ ] ✅ Set to `gob` | [ ] ❌ Not Set

### 2.3 Environment Identifier
- [ ] **Set ENVIRONMENT:**
  - Variable: `ENVIRONMENT`
  - Value: `production`
  - **Note:** Staging uses default "development" or not set
  - Status: [ ] ✅ Set to `production` | [ ] ❌ Not Set

### 2.4 CORS Origins (Verify)
- [ ] **CORS_ORIGINS variable:**
  - **Note:** CORS is configured in code (not via env var)
  - Code includes regex for `*.netlify.app` and `*.railway.app`
  - This should work with default domains automatically
  - Status: [ ] ✅ Not Needed (configured in code) | [ ] ⚠️ May need to add env var

### 2.5 Verify All Variables
- [ ] **Production variables match plan:**
  - MONGO_URI: ✅ (same cluster as staging)
  - MONGO_DB_NAME: `gob` ✅ (different from staging)
  - ENVIRONMENT: `production` ✅
  - PORT: ✅ (auto-set by Railway)
  - Status: [ ] ✅ All Set | [ ] ❌ Missing Variables

---

## 3. Production Backend Deployment

### 3.1 Trigger Initial Deployment
- [ ] **Deploy production backend:**
  - Railway should auto-deploy from `main` branch
  - Or trigger manual deployment if needed
  - Monitor deployment logs
  - Status: [ ] ✅ Deployed | [ ] ❌ Failed
  - Deployment URL: `https://_________________.up.railway.app`

### 3.2 Verify Deployment Success
- [ ] **Check deployment logs:**
  - Open Railway project → Deployments tab
  - Latest deployment status: [ ] ✅ Success | [ ] ❌ Failed
  - Build logs show: Application started successfully
  - No errors in logs
  - Status: [ ] ✅ Successful | [ ] ❌ Errors Found

### 3.3 Test Production Backend
- [ ] **Test root endpoint:**
  - URL: `GET https://_________________.up.railway.app/`
  - Expected: 200 OK or redirect
  - Actual: `_________________`
  - Status: [ ] ✅ Working | [ ] ❌ Failed

- [ ] **Test health endpoint:**
  - URL: `GET https://_________________.up.railway.app/health`
  - Expected: `{"status": "healthy", "port": 8080}`
  - Actual: `_________________`
  - Status: [ ] ✅ Working | [ ] ❌ Failed

- [ ] **Test /teams endpoint:**
  - URL: `GET https://_________________.up.railway.app/teams`
  - Expected: Array of team objects
  - Actual: `_________________`
  - Status: [ ] ✅ Working | [ ] ❌ Failed

- [ ] **Verify MongoDB connection:**
  - Check Railway logs for: `✅ [DB] MongoDB client created successfully`
  - Check logs for: `📊 [DB CONFIG] Using database: gob`
  - Status: [ ] ✅ Connected | [ ] ❌ Connection Failed

---

## 4. Production Netlify Frontend Setup

### 4.1 Create Production Netlify Site
- [ ] **Navigate to Netlify dashboard:** https://app.netlify.com
- [ ] **Create new site:**
  - Click "Add new site" → "Import an existing project"
  - Select "Deploy with GitHub"
  - Select repository: `gob-simplified` (or your repo name)
  - Site name: `gob-production` (or similar)
  - Status: [ ] ✅ Created | [ ] ❌ Failed

### 4.2 Configure Git Branch
- [ ] **Set branch to `main`:**
  - Go to Site settings → Build & deploy
  - Production branch: `main`
  - **Reference:** Staging uses `develop` branch
  - Status: [ ] ✅ Set to `main` | [ ] ❌ Not Set

### 4.3 Configure Build Settings
- [ ] **Set publish directory:**
  - Base directory: (root, empty/default)
  - Publish directory: `FrontEnd/static`
  - Build command: (empty - static files, no build needed)
  - **Reference:** Matches staging settings
  - Status: [ ] ✅ Matches Staging | [ ] ❌ Different

### 4.4 Deploy Production Frontend
- [ ] **Trigger deployment:**
  - Netlify should auto-deploy from `main` branch
  - Or trigger manual deployment if needed
  - Monitor deployment logs
  - Status: [ ] ✅ Deployed | [ ] ❌ Failed
  - Site URL: `https://_________________.netlify.app`

---

## 5. Production Testing

### 5.1 Frontend Accessibility
- [ ] **Test production frontend:**
  - Navigate to: `https://_________________.netlify.app/mode-select.html`
  - Page loads: [ ] ✅ Yes | [ ] ❌ No
  - No console errors: [ ] ✅ Yes | [ ] ❌ Errors Found
  - Status: [ ] ✅ Accessible | [ ] ❌ Issues Found

### 5.2 API Integration
- [ ] **Verify API calls work:**
  - Open browser DevTools → Network tab
  - Navigate through frontend (e.g., select a team)
  - API calls point to: Production Railway backend ✅
  - All API calls succeed: [ ] ✅ Yes | [ ] ❌ Some Fail
  - No CORS errors: [ ] ✅ Yes | [ ] ❌ CORS Errors
  - Status: [ ] ✅ Working | [ ] ❌ Issues Found

### 5.3 Database Isolation
- [ ] **Verify production uses `gob` database:**
  - Check Railway logs for: `📊 [DB CONFIG] Using database: gob`
  - Production database is separate from staging: [ ] ✅ Yes | [ ] ❌ No
  - Status: [ ] ✅ Isolated | [ ] ❌ Not Isolated

### 5.4 End-to-End Test (Basic)
- [ ] **Test basic game flow:**
  - Create a game (any mode)
  - Play at least 1 quarter
  - Verify game state saves
  - All steps succeed: [ ] ✅ Yes | [ ] ❌ Some Fail
  - Status: [ ] ✅ Working | [ ] ❌ Issues Found

### 5.5 Compare Production vs Staging
- [ ] **Production matches staging behavior:**
  - Same features work: [ ] ✅ Yes | [ ] ❌ No
  - Same API endpoints: [ ] ✅ Yes | [ ] ❌ No
  - Same frontend behavior: [ ] ✅ Yes | [ ] ❌ No
  - Status: [ ] ✅ Matches | [ ] ❌ Differences Found

---

## Verification Summary

### Overall Status
- **Date Completed:** `_________________`
- **Completed By:** `_________________`
- **Overall Status:** [ ] ✅ PASS | [ ] ❌ FAIL | [ ] ⚠️ PARTIAL

### Critical Issues Found
- [x] ✅ None

### Next Steps
- [x] ✅ All tasks complete - Production is ready
- [ ] Custom domains can be configured (optional, post-launch)

---

## Notes

### Production URLs
- Backend: `https://gob-simplified-gob-backend-prod.up.railway.app`
- Frontend: `https://gob-production.netlify.app`

### Environment Variables Summary
- MONGO_URI: Same cluster as staging
- MONGO_DB_NAME: `gob` (production)
- ENVIRONMENT: `production`
- PORT: Auto-set by Railway (8080)

### Differences from Staging
- Branch: `main` (staging uses `develop`)
- Database: `gob` (staging uses `gob-staging`)
- ENVIRONMENT: `production` (staging uses default "development")
- All other settings should match staging exactly

