# GOB — Alpha Pre-Launch Checklist (Sequential Execution Order)

**How to use this doc:**  
Work top-to-bottom. Each step is ordered to minimize rework, reduce hotfix risk, and keep you protected (data, cost, stability) while shipping a real alpha.

---

## Step -1 — Verify Current State (Foundation Check)

### -1.1 Staging/Production Deployment Status
- [ ] Confirm staging backend deployed (Railway: `gob-simplified-staging`)
- [ ] Confirm staging frontend deployed (Netlify: `gob-test.netlify.app`)
- [ ] Confirm production backend deployed (Railway: `gob-simplified-gob-backend-prod`)
- [ ] Confirm production frontend deployed (Netlify: `gob-production.netlify.app`)

### -1.2 Existing Infrastructure
- [ ] CORS configured correctly (verify allowlist)
- [ ] Database connectivity verified (MongoDB Atlas)
- [ ] Health endpoints working (`/health`)
- [ ] Basic logging/monitoring available (Railway/Netlify logs)

### -1.3 Data Cleanup Plan
- [ ] Document which collections will be wiped at alpha launch:
  - [ ] `games` collection (wipe all)
  - [ ] `tournaments` collection (wipe all)
  - [ ] `franchises` collection (wipe all)
  - [ ] `users` collection (wipe all - new auth system)
- [ ] Document which collections will be preserved:
  - [ ] `teams` collection (universal reference data - keep)
  - [ ] `players` collection (universal reference data - keep)
  - [ ] `plays` collection (universal reference data - keep)
- [ ] Create wipe script and test in staging

---

## Step 0 — Lock Alpha Rules & Data Safety (Foundation)

### 0.1 Alpha Environment Flag
- [ ] Add `IS_ALPHA=true` to **production** environment variables
- [ ] Add an “ALPHA” badge in the UI (persistent and visible)
- [ ] Add alpha disclaimer copy on signup/login/home (at minimum)

### 0.2 Alpha Data Disclaimer
- [ ] Add copy: **“This is an alpha. Data may be wiped without notice.”**
- [ ] Add copy: **“Gameplay balance and features may change.”**

### 0.3 Data Versioning (Future-proof now)
- [ ] Add `version` field to user documents
- [ ] Add `version` field to game/tournament/franchise documents

### 0.4 Data Wipe Capability (You need this)
- [ ] Create a safe script/process to wipe alpha data (users + all dependent game data)
- [ ] Script should wipe: `games`, `tournaments`, `franchises`, `users` collections
- [ ] Script should preserve: `teams`, `players`, `plays` (universal reference data)
- [ ] Test wipe process in staging
- [ ] Document exactly how to run it

---

## Step 1 — Authentication (Core Access)

### 1.1 Auth Architecture Decisions
- [ ] Use email + password + JWT for alpha (keep it simple)
- [ ] Define user schema: `user_id`, `email`, `password_hash`, `created_at`, `role`, `version`
- [ ] **Standardize on `role` field** (values: `"user"`, `"admin"`) - not `is_admin` boolean

### 1.2 Signup Flow
- [ ] Create signup page (`/signup.html`)
- [ ] Create API endpoint (`POST /api/auth/signup`)
- [ ] Validate inputs (email format, password rules)
- [ ] Hash passwords securely (bcrypt or argon2)
- [ ] Create user doc in MongoDB
- [ ] Handle duplicate email errors gracefully

### 1.3 Login Flow
- [ ] Create login page (`/login.html`)
- [ ] Create API endpoint (`POST /api/auth/login`)
- [ ] Issue JWT on success
- [ ] Store session client-side safely (consistent approach)
- [ ] Implement logout

### 1.4 Protect Backend Endpoints
- [ ] Add auth middleware
- [ ] Protect endpoints that require auth
- [ ] Extract `user_id` from token and attach to request context
- [ ] Ensure unauthorized returns clean 401/403

### 1.5 Frontend Integration
- [ ] Add “Sign Up” / “Log In” links on homepage
- [ ] Hide authenticated-only features while logged out
- [ ] Show basic user state while logged in

### 1.6 Auth Testing
- [ ] Signup → login → access protected feature
- [ ] Refresh page → session persists
- [ ] Logout works
- [ ] Invalid login error messaging works

---

## Step 2 — Custom Domains (Critical for Launch)

> **Note:** Custom domains are critical for professional appearance and branding. Do this early so DNS has time to propagate (24-48 hours).

### 2.1 Frontend Domain
- [ ] Add `www.geekedoutbasketball.com` to Netlify production site
- [ ] Configure DNS at Namecheap (A record or CNAME)
- [ ] Wait for DNS propagation (24-48 hours)
- [ ] Verify domain resolves correctly
- [ ] Test HTTPS certificate (auto-provisioned by Netlify)

### 2.2 Backend Domain
- [ ] Add `api.geekedoutbasketball.com` to Railway production project
- [ ] Configure DNS at Namecheap (A record or CNAME)
- [ ] Wait for DNS propagation (24-48 hours)
- [ ] Verify domain resolves correctly
- [ ] Test HTTPS certificate (auto-provisioned by Railway)

### 2.3 CORS Updates
- [ ] Add custom domains to CORS allowlist in `BackEnd/api/api.py`
- [ ] Update `API_CONFIG` in frontend to detect custom domain
- [ ] Test CORS works with custom domains
- [ ] Keep default Railway/Netlify domains enabled for fallback

### 2.4 Verification
- [ ] End-to-end test using custom domains
- [ ] Verify frontend loads at `www.geekedoutbasketball.com`
- [ ] Verify API calls go to `api.geekedoutbasketball.com`
- [ ] Test full game flow with custom domains

---

## Step 3 — Analytics & Marketing Pixels (Day 1 Data)

> **Note:** Set up analytics early to capture data from day 1. Marketing pixels enable future campaigns.

### 3.1 Google Analytics 4 (GA4) Setup
- [ ] Create GA4 property for `geekedoutbasketball.com`
- [ ] Get Measurement ID (G-XXXXXXXXXX)
- [ ] Add GA4 script to all pages
- [ ] Test GA4 is receiving events

### 3.2 Track Core Events (Day 1)
- [ ] Signup event
- [ ] Login event
- [ ] Game started event
- [ ] Game completed event
- [ ] Quarter completed event (optional)

### 3.3 Marketing Pixels (Enable Future Campaigns)
- [ ] **Facebook Pixel** (if using Facebook Ads)
  - [ ] Create Facebook Pixel
  - [ ] Get Pixel ID
  - [ ] Add pixel code to all pages (or via GTM)
  - [ ] Set up conversion events (signups, game completions)
  - [ ] Test pixel fires correctly

- [ ] **LinkedIn Insight Tag** (if using LinkedIn Ads)
  - [ ] Create LinkedIn Insight Tag
  - [ ] Get Partner ID
  - [ ] Add tag code to all pages (or via GTM)
  - [ ] Test tag fires correctly

- [ ] **Consider Google Tag Manager (GTM)**
  - [ ] More flexible than adding pixels directly
  - [ ] Easier to add/remove tags without code changes
  - [ ] Recommended for managing multiple tracking pixels

---

## Step 4 — Error Tracking (Visibility Before You Ship)

### 4.1 Choose a Tool
- [ ] Pick error tracking service (Sentry recommended)

### 4.2 Backend Error Tracking
- [ ] Install SDK
- [ ] Capture unhandled exceptions
- [ ] Capture API errors (4xx/5xx where helpful)
- [ ] Attach user context (`user_id`) to events

### 4.3 Frontend Error Tracking
- [ ] Capture JS runtime errors
- [ ] Capture unhandled promise rejections
- [ ] Attach user context if available

### 4.4 Verification
- [ ] Trigger intentional test errors (backend + frontend)
- [ ] Confirm events appear with useful context

---

## Step 5 — Security Hardening (Essential Protection)

### 5.1 CORS Review
- [ ] Verify CORS allowlist is explicit (no wildcards in production)
- [ ] Confirm custom domains are in allowlist
- [ ] Test CORS works correctly with all domains

### 5.2 Environment Variables Security
- [ ] Verify no secrets in code (check git history)
- [ ] Verify all secrets in environment variables
- [ ] Verify staging and production use different secrets
- [ ] Document all required environment variables

### 5.3 Input Validation Review
- [ ] Audit all API endpoints for input validation
- [ ] Verify Pydantic models validate all request data
- [ ] Test invalid input handling (malformed JSON, wrong types, etc.)
- [ ] Verify error messages don't leak sensitive info

### 5.4 Password Security
- [ ] Use bcrypt or argon2 for password hashing (already in Step 1)
- [ ] Implement minimum password requirements (8+ chars, complexity)
- [ ] Consider account lockout after 5 failed login attempts (optional for alpha)

### 5.5 Security Headers (Basic)
- [ ] Add security headers to responses (CSP, HSTS, X-Frame-Options)
- [ ] Test headers are present in responses
- [ ] Verify headers don't break functionality

---

## Step 6 — Rate Limiting (Lite, But Must Exist)

### 6.1 Protect Authentication
- [ ] Rate limit login endpoint (per IP)
- [ ] Rate limit signup endpoint (per IP)

### 6.2 Protect High-Cost Endpoints
- [ ] Rate limit simulation endpoints (per IP and/or per user)

### 6.3 Verification
- [ ] Confirm limits trigger 429 responses
- [ ] Confirm 429 responses are user-friendly
- [ ] Confirm limits reset as expected

---

## Step 7 — Cost Guardrails (Prevent Surprise Bills)

### 7.0 Backup Strategy (Verify)
- [ ] Check MongoDB Atlas tier (free tier has automated backups)
- [ ] Verify backup retention period
- [ ] Document backup restoration process (if needed)
- [ ] **Note:** Free tier backups may be sufficient for alpha

### 7.1 Provider Alerts
- [ ] Configure MongoDB Atlas usage alerts
- [ ] Configure Railway spending alerts/caps
- [ ] Review Netlify bandwidth constraints

### 7.2 In-App Caps (Hard Stops)
- [ ] Max games per user per day
- [ ] Max tournaments per user
- [ ] Max sim requests per minute

### 7.3 Verification
- [ ] Confirm caps actually block usage
- [ ] Confirm messaging is clear when a cap is hit

---

## Step 8 — Legal & Compliance (Ship Simple, Ship Real)

### 8.1 Terms of Service
- [ ] Create `/terms.html`
- [ ] Add footer link on all pages
- [ ] Add signup checkbox: “I agree to the Terms”

### 8.2 Privacy Policy
- [ ] Create `/privacy.html`
- [ ] Include: data collected, cookies, analytics, retention

### 8.3 Cookie Consent (Only If Needed)
- [ ] Decide if you’ll serve users in jurisdictions requiring consent
- [ ] Implement banner if required (basic is fine)

---

## Step 9 — Basic Monitoring & Uptime Alerts

> **Note:** Railway and Netlify provide basic logging. This step adds external uptime monitoring.

### 9.1 Choose Uptime Service
- [ ] Pick service (UptimeRobot, Pingdom, Better Uptime, etc.)
- [ ] UptimeRobot recommended (free tier: 50 monitors)

### 9.2 Uptime Monitoring
- [ ] Add uptime check for frontend (`www.geekedoutbasketball.com` or Netlify default)
- [ ] Add uptime check for API (`api.geekedoutbasketball.com` or Railway default)
- [ ] Set check interval (5 minutes is fine for alpha)

### 9.3 Alerts
- [ ] Email alerts at minimum (Slack optional)
- [ ] Configure alert thresholds (alert after 2 consecutive failures)

### 9.4 Performance Monitoring (Optional)
- [ ] Monitor API response times (Railway logs or external service)
- [ ] Set alerts for slow endpoints (> 2 seconds for alpha)
- [ ] Monitor error rates

### 9.5 Verification
- [ ] Confirm alerts actually fire (simulate downtime if feasible)
- [ ] Test alert delivery (email/Slack)

---

## Step 10 — End-to-End “No Surprises” Testing (Go/No-Go)

> **Note:** See `Final_Testing_Checklist.md` for detailed test scenarios.

### 10.1 Full Flow Tests
- [ ] Signup → login → play game → save → reload → continue
- [ ] Test all supported game modes (those enabled by flags)

### 10.2 Failure Scenarios
- [ ] Network outage behavior (frontend)
- [ ] Invalid input handling (API)
- [ ] Unauthorized access attempts (API)

### 10.3 Quality Gate
- [ ] No known game-breaking bugs remain
- [ ] Performance feels acceptable for alpha
- [ ] Error tracking clean and functional
- [ ] Rate limits and caps working

---

## Step 11 — Minimal Email (Password Reset Only)

> **Note:** Start with password reset only. Full email service (verification, notifications, marketing) can be added post-launch.

### 11.1 Provider Setup
- [ ] Choose provider (SendGrid/Mailgun/Postmark/etc.)
  - [ ] SendGrid: Free tier (100 emails/day)
  - [ ] Mailgun: Free tier (5,000 emails/month)
  - [ ] Postmark: Free tier (100 emails/month)
- [ ] Create account and verify domain (if required)
- [ ] Add API key to production environment variables
- [ ] Send a test email successfully

### 11.2 Password Reset Implementation
- [ ] Create password reset request endpoint (`POST /api/auth/reset-request`)
- [ ] Generate secure reset token (store in database with expiration)
- [ ] Send reset email with token link
- [ ] Create password reset page (`/reset-password.html?token=...`)
- [ ] Create password reset endpoint (`POST /api/auth/reset-password`)
- [ ] Verify reset token and update password
- [ ] Invalidate token after use

### 11.3 Verification
- [ ] Test password reset flow end-to-end
- [ ] Verify reset token expires after 1 hour (or chosen duration)
- [ ] Verify reset token is invalidated after use
- [ ] Test error handling (invalid token, expired token)

---

## Step 12 — Admin / Support Tools (Post-Launch Friendly, High Leverage)

### 12.1 Admin Flag
- [ ] Add `role` field to user schema (values: `"user"`, `"admin"`)
- [ ] Set your account to `role: "admin"` in database

### 12.2 Minimum Admin Actions (Recommended)
- [ ] Reset broken user state
- [ ] Delete corrupted objects
- [ ] Impersonate user (optional)
- [ ] Grant resources (optional)

### 12.3 Support & Feedback
- [ ] Support email address visible
- [ ] “Report bug” link or button

---

# Launch Day Runbook (Final Sequence)

- [ ] Confirm all critical steps are complete (or consciously deferred)
- [ ] Confirm custom domains are working (`www.geekedoutbasketball.com`, `api.geekedoutbasketball.com`)
- [ ] Confirm production frontend loads
- [ ] Confirm production API is healthy
- [ ] Confirm auth works (signup, login, logout)
- [ ] Confirm error tracking is receiving events
- [ ] Confirm analytics is tracking events (GA4 dashboard)
- [ ] Confirm rate limiting and caps are active
- [ ] Confirm legal pages are live (`/terms.html`, `/privacy.html`)
- [ ] Wipe development data from production database (games, tournaments, franchises, users)
- [ ] Launch announcement
- [ ] Monitor logs + error dashboard for first 30–60 minutes
- [ ] Monitor analytics dashboard for first hour

---

## Notes

### Philosophy
- Alpha success = learning without breaking trust
- Visibility + control + cost protection > polish
- Keep default Railway/Netlify domains available as fallback

### Key Decisions Made
1. **Custom Domains:** Critical for launch (moved to Step 2)
2. **Analytics:** Day 1 data needed (moved to Step 3)
3. **Feature Flags:** Not needed - core features (Single Game, Tournament, Franchise, Sim Quarter) are stable and working. No flags required.
4. **Email Service:** Password reset only for alpha (full service post-launch)
5. **Security:** Essential items only (Steps 1, 5, 6). Advanced security post-launch.
6. **Data Wipe:** Will wipe `games`, `tournaments`, `franchises`, `users` at launch. Preserve universal reference data (`teams`, `players`, `plays`).

### Testing Reference
- See `Final_Testing_Checklist.md` for detailed test scenarios (Step 11 references this)
