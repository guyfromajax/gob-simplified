# Pre-Launch Checklist for GOB Alpha

**Purpose:** Comprehensive checklist of items needed before announcing alpha launch  
**Goal:** Ensure nothing critical is missed before going live  
**Last Updated:** January 2025  

---

## 🔴 CRITICAL - Must Have Before Launch

### 1. User Authentication & Account System
**Status:** ❌ NOT IMPLEMENTED  
**Priority:** 🔴 CRITICAL - Blocks user access

- [ ] Design account system architecture
  - [ ] Choose authentication method (OAuth, email/password, magic links, etc.)
  - [ ] Design user data schema (user_id, email, created_at, etc.)
  - [ ] Plan password reset flow
  - [ ] Plan email verification flow (if needed)

- [ ] Build account creation tool/page
  - [ ] Create signup page (`FrontEnd/static/signup.html`)
  - [ ] Build signup API endpoint (`/api/auth/signup`)
  - [ ] Add validation (email format, password strength, etc.)
  - [ ] Store user credentials securely (hashed passwords)
  - [ ] Create user document in database
  - [ ] Handle errors gracefully

- [ ] Build login system
  - [ ] Create login page (`FrontEnd/static/login.html`)
  - [ ] Build login API endpoint (`/api/auth/login`)
  - [ ] Implement session management (JWT tokens, cookies, etc.)
  - [ ] Add "Remember me" functionality (if needed)
  - [ ] Handle errors gracefully

- [ ] Update homepage
  - [ ] Add "Sign Up" button/link
  - [ ] Add "Log In" button/link
  - [ ] Hide authenticated-only features when logged out
  - [ ] Show user account info when logged in

- [ ] Add authentication middleware to backend
  - [ ] Protect API endpoints that require authentication
  - [ ] Add user context to requests (user_id extraction)
  - [ ] Handle unauthorized requests

- [ ] Test authentication flow
  - [ ] Signup → Login → Access protected features
  - [ ] Verify sessions persist across page refreshes
  - [ ] Test logout functionality
  - [ ] Test password reset (if implemented)

---

### 2. DNS & Custom Domains
**Status:** ⏳ PLANNED (marked as optional, but should be done)  
**Priority:** 🔴 CRITICAL - Professional appearance and branding

- [ ] Configure custom domain for production frontend
  - [ ] Add `www.geekedoutbasketball.com` to Netlify production site
  - [ ] Configure DNS at Namecheap (A record or CNAME)
  - [ ] Wait for DNS propagation (24-48 hours)
  - [ ] Verify domain resolves correctly
  - [ ] Test HTTPS certificate (auto-provisioned by Netlify)

- [ ] Configure custom domain for production backend
  - [ ] Add `api.geekedoutbasketball.com` to Railway production project
  - [ ] Configure DNS at Namecheap (A record or CNAME)
  - [ ] Wait for DNS propagation (24-48 hours)
  - [ ] Verify domain resolves correctly
  - [ ] Test HTTPS certificate (auto-provisioned by Railway)

- [ ] Update CORS configuration
  - [ ] Add custom production domains to CORS allowlist
  - [ ] Update `API_CONFIG` in frontend to detect custom domain
  - [ ] Test CORS works with custom domains
  - [ ] Remove default Railway/Netlify domains from CORS (optional, can keep for staging)

- [ ] Update API configuration
  - [ ] Update `FrontEnd/static/js/config/api-config.js` to detect `www.geekedoutbasketball.com`
  - [ ] Test API calls work with custom domain
  - [ ] Verify all API endpoints accessible

- [ ] Test end-to-end with custom domains
  - [ ] Verify frontend loads at `www.geekedoutbasketball.com`
  - [ ] Verify API calls go to `api.geekedoutbasketball.com`
  - [ ] Test full game flow with custom domains

---

### 3. Google Analytics & Tracking
**Status:** ❌ NOT IMPLEMENTED  
**Priority:** 🔴 CRITICAL - Need analytics from day 1

- [ ] Set up Google Analytics 4 (GA4)
  - [ ] Create Google Analytics account
  - [ ] Create GA4 property for geekedoutbasketball.com
  - [ ] Get Measurement ID (G-XXXXXXXXXX)

- [ ] Add Google Analytics to frontend
  - [ ] Add GA4 script to all HTML pages (or base template)
  - [ ] Add Measurement ID to configuration
  - [ ] Test page views are tracked
  - [ ] Set up conversion events (signups, game completions, etc.)
  - [ ] Test events fire correctly

- [ ] Add Google Tag Manager (GTM) - Optional but Recommended
  - [ ] Create GTM container
  - [ ] Add GTM script to all pages
  - [ ] Add GA4 via GTM (more flexible for future tags)
  - [ ] Test tags fire correctly

- [ ] Plan custom events to track
  - [ ] User signup
  - [ ] User login
  - [ ] Game started
  - [ ] Game completed
  - [ ] Quarter simulated
  - [ ] Mode selection (Single/Tournament/Franchise)
  - [ ] Key feature usage

---

### 4. Legal & Compliance
**Status:** ❌ NOT IMPLEMENTED  
**Priority:** 🔴 CRITICAL - Legal requirement

- [ ] Create Terms of Service
  - [ ] Write or obtain Terms of Service document
  - [ ] Create `/terms.html` page
  - [ ] Add link to Terms in footer (all pages)
  - [ ] Add checkbox to signup form (users must agree to Terms)

- [ ] Create Privacy Policy
  - [ ] Write or obtain Privacy Policy document
  - [ ] Include data collection practices
  - [ ] Include cookie usage
  - [ ] Include third-party services (Google Analytics, etc.)
  - [ ] Include data retention policies
  - [ ] Create `/privacy.html` page
  - [ ] Add link to Privacy Policy in footer (all pages)

- [ ] Add Cookie Consent (if needed)
  - [ ] Check if required for your jurisdiction (GDPR, CCPA, etc.)
  - [ ] Implement cookie consent banner (if required)
  - [ ] Allow users to opt-out of non-essential cookies

---

## 🟡 HIGH PRIORITY - Should Have Before Launch

### 5. Error Tracking & Monitoring
**Status:** ❌ NOT IMPLEMENTED  
**Priority:** 🟡 HIGH - Need visibility into production errors

- [ ] Set up error tracking service
  - [ ] Choose service (Sentry, LogRocket, Rollbar, etc.)
  - [ ] Create account and project
  - [ ] Get API key/DNS

- [ ] Add error tracking to backend
  - [ ] Install error tracking SDK
  - [ ] Initialize error tracking with API key
  - [ ] Capture unhandled exceptions
  - [ ] Capture API errors (400, 500, etc.)
  - [ ] Add user context to errors (user_id, etc.)

- [ ] Add error tracking to frontend
  - [ ] Install error tracking SDK
  - [ ] Initialize error tracking with API key
  - [ ] Capture JavaScript errors
  - [ ] Capture unhandled promise rejections
  - [ ] Add user context to errors (user_id, etc.)

- [ ] Test error tracking
  - [ ] Trigger test error (intentionally)
  - [ ] Verify error appears in dashboard
  - [ ] Verify error includes helpful context

---

### 6. Monitoring & Observability
**Status:** ⚠️ PARTIAL (Railway/Netlify logs only)  
**Priority:** 🟡 HIGH - Need better visibility

- [ ] Set up application monitoring
  - [ ] Choose service (UptimeRobot, Pingdom, Better Uptime, etc.)
  - [ ] Set up uptime monitoring for API
  - [ ] Set up uptime monitoring for frontend
  - [ ] Configure alerts (email, Slack, etc.)

- [ ] Set up performance monitoring
  - [ ] Monitor API response times
  - [ ] Monitor database query performance
  - [ ] Set up alerts for slow endpoints (> 1 second)
  - [ ] Monitor error rates

- [ ] Set up database monitoring
  - [ ] Enable MongoDB Atlas monitoring (free tier)
  - [ ] Monitor database connection pool
  - [ ] Monitor query performance
  - [ ] Set up alerts for database issues

---

### 7. Security Hardening
**Status:** ⚠️ PARTIAL  
**Priority:** 🟡 HIGH - Security best practices

- [ ] Review and tighten CORS configuration
  - [ ] Remove wildcard origins (if any)
  - [ ] Use explicit allowlist (production + staging domains)
  - [ ] Test CORS works correctly

- [ ] Review environment variables
  - [ ] Verify no secrets in code (check git history)
  - [ ] Verify all secrets in environment variables
  - [ ] Verify staging and production use different secrets
  - [ ] Document all required environment variables

- [ ] Review input validation
  - [ ] Verify all API endpoints validate input
  - [ ] Test SQL/NoSQL injection prevention
  - [ ] Test XSS prevention (if user-generated content)
  - [ ] Test CSRF protection (if applicable)

- [ ] Review authentication security
  - [ ] Use HTTPS for all authentication endpoints
  - [ ] Hash passwords securely (bcrypt, argon2, etc.)
  - [ ] Implement rate limiting on login endpoints
  - [ ] Implement account lockout after failed attempts (if needed)

- [ ] Set up security headers
  - [ ] Add security headers (CSP, HSTS, X-Frame-Options, etc.)
  - [ ] Test headers are present in responses

---

### 8. Marketing Pixels & Tracking
**Status:** ❌ NOT IMPLEMENTED  
**Priority:** 🟡 HIGH - Enable future marketing campaigns

- [ ] Plan marketing integrations
  - [ ] Identify which platforms you'll use (Facebook, Twitter, LinkedIn, etc.)
  - [ ] Identify tracking pixels needed (conversion pixels, retargeting pixels, etc.)

- [ ] Add Facebook Pixel (if using Facebook Ads)
  - [ ] Create Facebook Pixel
  - [ ] Get Pixel ID
  - [ ] Add pixel code to all pages (or via GTM)
  - [ ] Set up conversion events (signups, game completions)
  - [ ] Test pixel fires correctly

- [ ] Add LinkedIn Insight Tag (if using LinkedIn Ads)
  - [ ] Create LinkedIn Insight Tag
  - [ ] Get Partner ID
  - [ ] Add tag code to all pages (or via GTM)
  - [ ] Test tag fires correctly

- [ ] Add Twitter Pixel (if using Twitter Ads)
  - [ ] Create Twitter Pixel
  - [ ] Get Pixel ID
  - [ ] Add pixel code to all pages (or via GTM)
  - [ ] Test pixel fires correctly

- [ ] Consider using Google Tag Manager
  - [ ] More flexible than adding pixels directly
  - [ ] Easier to add/remove tags without code changes
  - [ ] Recommended for managing multiple tracking pixels

---

## 🟢 MEDIUM PRIORITY - Nice to Have

### 9. Docker/Containerization
**Status:** ❓ NOT NEEDED (Railway uses NIXPACKS)  
**Priority:** 🟢 LOW - Not required for Railway deployment

**Note:** Railway uses NIXPACKS which auto-detects Python projects. Docker is not required for Railway deployment. However, if you want to use Docker:

- [ ] Create Dockerfile (optional)
- [ ] Create docker-compose.yml (optional, for local development)
- [ ] Test Docker build locally
- [ ] Update Railway to use Dockerfile (if desired)

**Recommendation:** Skip for now. Railway's NIXPACKS works well and is simpler.

---

### 10. Email Service Integration
**Status:** ❌ NOT IMPLEMENTED  
**Priority:** 🟢 MEDIUM - Needed for password resets, notifications

- [ ] Choose email service
  - [ ] Options: SendGrid, Mailgun, AWS SES, Postmark, etc.
  - [ ] Consider free tier availability
  - [ ] Create account and verify domain

- [ ] Set up email service
  - [ ] Get API key
  - [ ] Add to environment variables
  - [ ] Test email sending

- [ ] Implement email functionality
  - [ ] Password reset emails
  - [ ] Welcome emails (after signup)
  - [ ] Email verification (if required)
  - [ ] Transactional emails (game completions, etc.)

---

### 11. Backup & Disaster Recovery
**Status:** ⚠️ NEEDS VERIFICATION  
**Priority:** 🟢 MEDIUM - Good practice for alpha

**Important Context:**
- **MongoDB Atlas Backups:** Depends on your Atlas tier
  - **Free Tier (M0):** Manual backups only (via `mongodump` or MongoDB Compass export)
  - **Paid Tiers (M10+):** Automated continuous backups included (point-in-time restore, retention periods)
- **For Alpha:** Manual backups are probably sufficient if you're on free tier
- **Additional Tooling:** Not required for alpha - MongoDB Atlas backups (if on paid tier) are sufficient

**Action Items:**
- [ ] Check your MongoDB Atlas tier (free M0 or paid M10+)
- [ ] If on **paid tier (M10+):**
  - [ ] Verify automated backups are enabled (usually enabled by default)
  - [ ] Verify backup retention period (7 days minimum recommended)
  - [ ] Test backup restoration process (restore a test database)
  - [ ] Document how to restore from backup

- [ ] If on **free tier (M0):**
  - [ ] Set up manual backup process (weekly/monthly exports)
  - [ ] Document how to export database (`mongodump` command or MongoDB Compass)
  - [ ] Store exports in safe location (S3, local storage, etc.)
  - [ ] Test restoration process (restore from export)

- [ ] Document disaster recovery procedures
  - [ ] Document how to restore database from backup
  - [ ] Document how to redeploy if Railway fails (redeploy from GitHub)
  - [ ] Document how to switch to backup instance if needed
  - [ ] Document database migration procedures

**Recommendation for Alpha:**
- **If on free tier:** Manual weekly backups are sufficient (export database, store safely)
- **If on paid tier:** Automated backups are sufficient - just verify they're enabled
- **No additional tooling needed** - MongoDB Atlas provides the backup infrastructure
- **Documentation is key** - Make sure you know how to restore if needed

---

### 12. Rate Limiting & API Protection
**Status:** ❌ NOT IMPLEMENTED  
**Priority:** 🟢 MEDIUM - Protect against abuse

- [ ] Implement rate limiting on API endpoints
  - [ ] Use FastAPI rate limiting middleware
  - [ ] Set limits per endpoint (different limits for different endpoints)
  - [ ] Set limits per user/IP
  - [ ] Return appropriate error messages (429 Too Many Requests)

- [ ] Test rate limiting
  - [ ] Verify limits work correctly
  - [ ] Verify error messages are user-friendly
  - [ ] Verify limits reset correctly

---

### 13. Documentation & Onboarding
**Status:** ⚠️ PARTIAL (technical docs exist)  
**Priority:** 🟢 MEDIUM - Help users understand the product

- [ ] Create user-facing documentation
  - [ ] How to play guide
  - [ ] FAQ page
  - [ ] Tutorial/onboarding flow

- [ ] Add help/support system
  - [ ] Add "Help" or "Support" link to navigation
  - [ ] Create support email or contact form
  - [ ] Add "Feedback" button/modal

---

## 📋 Testing & Verification

### 14. Final Pre-Launch Testing
**Status:** ⏳ IN PROGRESS  
**Priority:** 🔴 CRITICAL

- [ ] Complete end-to-end testing (see `Final_Testing_Checklist.md`)
  - [ ] Test all game modes
  - [ ] Test authentication flow
  - [ ] Test data persistence
  - [ ] Test all critical bugs are fixed
  - [ ] Test performance is acceptable

- [ ] Test with custom domains (if implemented)
  - [ ] Verify frontend loads correctly
  - [ ] Verify API calls work correctly
  - [ ] Verify CORS works correctly

- [ ] Test error scenarios
  - [ ] Network failures
  - [ ] Invalid inputs
  - [ ] Unauthorized access attempts

---

## 📊 Launch Day Checklist

### 15. Launch Day Tasks
**Status:** ⏳ READY  
**Priority:** 🔴 CRITICAL

- [ ] Final code review
  - [ ] All critical items from this checklist complete
  - [ ] Code pushed to production branch
  - [ ] Environment variables set correctly

- [ ] Pre-launch verification
  - [ ] Production site accessible
  - [ ] Production API accessible
  - [ ] Authentication works
  - [ ] Game flow works
  - [ ] Analytics tracking works
  - [ ] No critical errors in logs

- [ ] Launch announcement
  - [ ] Prepare launch announcement
  - [ ] Post launch announcement
  - [ ] Monitor for first 30 minutes
  - [ ] Be ready to hotfix critical issues

- [ ] Post-launch monitoring
  - [ ] Monitor error tracking dashboard
  - [ ] Monitor performance metrics
  - [ ] Monitor user signups
  - [ ] Respond to user feedback

---

## 📝 Notes

### Items Already Complete
- ✅ Staging and production environments deployed
- ✅ Database connectivity verified
- ✅ API configuration working
- ✅ CORS configured
- ✅ Performance optimizations implemented
- ✅ Core game functionality working

### Items Deferred (Post-Launch)
- ⏸️ Frontend framework migration (React/Angular)
- ⏸️ Frontend design polish
- ⏸️ Payment integration
- ⏸️ Advanced analytics
- ⏸️ Custom domains for staging

---

## Priority Summary

**🔴 Must Have Before Launch:**
1. User Authentication & Account System
2. DNS & Custom Domains
3. Google Analytics & Tracking
4. Legal & Compliance (Terms, Privacy Policy)

**🟡 Should Have Before Launch:**
5. Error Tracking & Monitoring
6. Monitoring & Observability
7. Security Hardening
8. Marketing Pixels & Tracking

**🟢 Nice to Have (Can Add Post-Launch):**
9. Docker/Containerization (not needed for Railway)
10. Email Service Integration
11. Backup & Disaster Recovery
12. Rate Limiting & API Protection
13. Documentation & Onboarding

---

**Next Steps:** Review this checklist, prioritize items based on your timeline, and start working through the 🔴 CRITICAL items first.

