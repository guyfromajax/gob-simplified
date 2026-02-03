# GOB — Alpha Pre-Launch Checklist (Sequential Execution Order)

**How to use this doc:**  
Work top-to-bottom. Each step is ordered to minimize rework, reduce hotfix risk, and keep you protected (data, cost, stability) while shipping a real alpha.

---

## 📋 Executive Summary

**Quick reference for each step. Detailed implementation below.**

| Step | Task | Key Deliverables |
|------|------|------------------|
| **-1** | **Verify Current State** | Confirm staging/production deployed, infrastructure working, data cleanup plan documented |
| **0** | **Lock Alpha Rules & Data Safety** | `IS_ALPHA=true` flag, alpha badge/disclaimers, OTP system setup, data wipe script |
| **1** | **Authentication** | Signup/login pages, JWT auth, OTP validation (when `IS_ALPHA=true`), protected endpoints |
| **2** | **Custom Domains** | `www.geekedoutbasketball.com` + `api.geekedoutbasketball.com`, DNS configured, CORS updated |
| **3** | **Analytics & Marketing Pixels** | GA4 setup, core events tracked, GTM + pixels (Facebook/Meta, Instagram, X, TikTok) |
| **4** | **Error Tracking** | Sentry (or similar) configured, backend + frontend error capture, user context attached |
| **5** | **Security Hardening** | CORS, user data exposure prevention, env vars, input validation, passwords, security headers |
| **6** | **Rate Limiting** | Login/signup rate limits, simulation endpoint limits, 429 responses |
| **7** | **Cost Guardrails** | MongoDB/Railway alerts, in-app caps (max games/tournaments per user), backup verification |
| **8** | **Legal & Compliance** | Terms of Service (`/terms.html`), Privacy Policy (`/privacy.html`), cookie consent (if needed) |
| **9** | **Basic Monitoring** | Uptime monitoring (UptimeRobot), email alerts, performance monitoring (optional) |
| **10** | **End-to-End Testing** | Full flow tests, failure scenarios, quality gate (no game-breaking bugs) |
| **11** | **Minimal Email** | Email provider setup (SendGrid/Mailgun/Postmark), password reset flow only |
| **12** | **Admin/Support Tools** | Admin role system, admin-only pages (play-builder, HCT/FCP builders), support email/feedback |

**Launch Day:** Wipe dev data, verify all systems, launch announcement, monitor first hour

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
  - [ ] `fcp_skeletons` collection (universal reference data - keep)
  - [ ] `hct_skeletons` collection (universal reference data - keep)
  - [ ] `defenses` collection (universal reference data - keep)
- [ ] Create wipe script and test in staging

---

## Step 0 — Lock Alpha Rules & Data Safety (Foundation)

### 0.1 Alpha Environment Flag
- [ ] Add `IS_ALPHA=true` to **production** environment variables
- [ ] Add an "ALPHA" badge in the UI (persistent and visible)
- [ ] Add alpha disclaimer copy on signup/login/home (at minimum)
- [ ] **Note:** `IS_ALPHA` flag controls whether one-time passwords (OTPs) are required for signup

### 0.2 Alpha Data Disclaimer
- [ ] Add copy: **"This is an alpha. Data may be wiped without notice."**
- [ ] Add copy: **"Gameplay balance and features may change."**

### 0.3 Data Versioning (Future-proof now)
- [ ] Add `version` field to user documents
- [ ] Add `version` field to game/tournament/franchise documents

### 0.4 Data Wipe Capability (You need this)
- [ ] Create a safe script/process to wipe alpha data (users + all dependent game data)
- [ ] Script should wipe: `games`, `tournaments`, `franchises`, `users` collections
- [ ] Script should preserve: `teams`, `players`, `plays`, `fcp_skeletons`, `hct_skeletons`, `defenses` (universal reference data)
- [ ] **OTP Collection:** Decide whether to wipe `alpha_otps` collection or preserve for tracking
- [ ] Test wipe process in staging
- [ ] Document exactly how to run it

### 0.5 One-Time Password (OTP) System Setup
- [ ] Create `alpha_otps` collection in MongoDB
- [ ] OTP schema: `otp_code` (unique string), `used` (boolean), `used_by_email` (string, nullable), `used_at` (timestamp, nullable), `created_at` (timestamp)
- [ ] Create script to generate **50 OTP codes** (8-12 character alphanumeric codes) - limits alpha to 25-50 users
- [ ] Insert OTPs into database (all marked as `used: false`)
- [ ] Store OTP list securely (for distribution to alpha testers)
- [ ] **Note:** OTPs are only validated when `IS_ALPHA=true`
- [ ] **Access Tracking:** Each OTP is permanently linked to an email when used (`used_by_email` field). Query `alpha_otps` collection to see who has access and when they signed up (`used_at` timestamp)

---

## Step 1 — Authentication (Core Access)

### 1.1 Auth Architecture Decisions
- [ ] Use email + password + JWT for alpha (keep it simple)
- [ ] Define user schema: `user_id`, `email`, `password_hash`, `created_at`, `role`, `version`
- [ ] **Standardize on `role` field** (values: `"user"`, `"admin"`) - not `is_admin` boolean
- [ ] **Alpha OTP Requirement:** When `IS_ALPHA=true`, signup requires valid, unused OTP code
- [ ] **OTP Validation:** Check `IS_ALPHA` env var to determine if OTP validation is required

### 1.2 Signup Flow
- [ ] Create signup page (`/signup.html`)
  - [ ] Add OTP input field (only visible when `IS_ALPHA=true`)
  - [ ] Add helper text: "Alpha access code required" when in alpha mode
- [ ] Create API endpoint (`POST /api/auth/signup`)
  - [ ] Validate inputs (email format, password rules)
  - [ ] **If `IS_ALPHA=true`:**
    - [ ] Require `otp_code` in request body
    - [ ] Validate OTP exists in `alpha_otps` collection
    - [ ] Verify OTP is unused (`used: false`)
    - [ ] Verify OTP hasn't been used by another email (check `used_by_email` is null)
    - [ ] Mark OTP as used: set `used: true`, `used_by_email: email`, `used_at: timestamp`
    - [ ] Return error if OTP is invalid, already used, or used by different email
  - [ ] **If `IS_ALPHA=false`:**
    - [ ] Skip OTP validation (normal signup flow)
- [ ] Hash passwords securely (bcrypt or argon2)
- [ ] Create user doc in MongoDB
- [ ] Handle duplicate email errors gracefully
- [ ] Handle invalid/used OTP errors gracefully

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
- [ ] Add "Sign Up" / "Log In" links on homepage
- [ ] Hide authenticated-only features while logged out
- [ ] Show basic user state while logged in

### 1.6 Auth Testing
- [ ] Signup → login → access protected feature
- [ ] Refresh page → session persists
- [ ] Logout works
- [ ] Invalid login error messaging works
- [ ] **OTP Testing (when `IS_ALPHA=true`):**
  - [ ] Valid OTP allows signup
  - [ ] Invalid OTP rejects signup
  - [ ] Used OTP rejects signup (cannot reuse)
  - [ ] Same OTP cannot be used by different email
  - [ ] OTP field hidden when `IS_ALPHA=false`

### 1.7 Username Feature (Post-Alpha Enhancement)
> **Not required for alpha launch.** Email display works fine initially.

- [ ] Add optional `username` field to user schema
- [ ] Create "Set Username" UI (profile page or modal after signup)
- [ ] Username validation rules:
  - [ ] Unique (case-insensitive) — store lowercase version for uniqueness check
  - [ ] No spaces allowed
  - [ ] Length limits (e.g., 3-20 characters)
  - [ ] Alphanumeric + underscores only (optional)
- [ ] Display username (if set) instead of email in auth bar
- [ ] Handle username changes (allow or disallow?)

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
- [ ] Single game started event (one-off; no save/resume)
- [ ] Single game completed event
- [ ] Tournament entered event (fires each time user opens tournament — new or returning)
- [ ] Tournament game started event
- [ ] Tournament game completed event
- [ ] Franchise entered event (fires each time user opens franchise — new or returning)
- [ ] Franchise game started event
- [ ] Franchise game completed event
- [ ] Quarter/Game advance event — capture which button was used:
  - [ ] Property: `action` = `play_quarter` | `sim_quarter` | `sim_full_game` (or `sim_rest_of_game`)
  - [ ] Fires on each quarter advance or full-game sim

**Implementation (Jan 2026):** GTM snippet added to all HTML pages. Analytics helper (`/js/shared/analytics.js`) pushes events to `dataLayer`. **GTM setup required:** Create GA4 Event tags in GTM that fire on Custom Event triggers for each event name (`signup`, `login`, `single_game_started`, etc.). For `quarter_advance`, add Event Parameter `action` (Data Layer Variable `action`).

### 3.3 Marketing Pixels (Enable Future Campaigns)

> **Setup guide:** See `docs/To Do/marketing_pixels_setup.md` for step-by-step instructions.

- [ ] **Google Tag Manager (GTM)**
  - [x] Create GTM container
  - [x] Add GTM script to all pages
  - [ ] Use GTM to manage all pixels (add/remove without code changes)

- [ ] **Facebook Pixel** (Meta)
  - [ ] Create Facebook Pixel in Meta Events Manager
  - [ ] Get Pixel ID
  - [ ] Add via GTM
  - [ ] Set up conversion events (signups, game completions)
  - [ ] Test pixel fires correctly

- [ ] **Instagram**
  - [ ] Uses same Meta Pixel as Facebook — no separate pixel. Facebook Pixel covers Instagram Ads.

- [ ] **X Pixel** (formerly Twitter)
  - [ ] Create X Pixel in X Ads Manager
  - [ ] Get Pixel ID
  - [ ] Add via GTM
  - [ ] Test pixel fires correctly

- [ ] **TikTok Pixel**
  - [ ] Create TikTok Pixel in TikTok Events Manager
  - [ ] Get Pixel ID
  - [ ] Add via GTM
  - [ ] Set up conversion events
  - [ ] Test pixel fires correctly

---

## Step 4 — Error Tracking (Visibility Before You Ship)

> **Setup guide:** See `docs/To Do/sentry_setup.md` for Sentry configuration.

### 4.1 Choose a Tool
- [x] Pick error tracking service (Sentry recommended)

### 4.2 Backend Error Tracking
- [x] Install SDK
- [x] Capture unhandled exceptions
- [x] Capture API errors (5xx via FastAPI integration)
- [x] Attach user context (`send_default_pii=True`)

### 4.3 Frontend Error Tracking
- [x] Capture JS runtime errors
- [x] Capture unhandled promise rejections
- [x] Attach user context if available (from `auth_user`)

### 4.4 Verification
- [x] Trigger intentional test errors (frontend verified with `Sentry.captureException`)
- [x] Confirm events appear with useful context

---

## Step 5 — Security Hardening (Essential Protection)

### 5.1 CORS Review
- [x] Verify CORS allowlist is explicit (no wildcards in production) — regex disabled
- [x] Confirm custom domains are in allowlist (geekedoutbasketball.com, www, gob-test, gob-production)
- [ ] Test CORS works correctly with all domains

### 5.2 User Data Exposure Prevention (Priority)
Prevent user data leakage via broken authorization, misconfigured DB access, and accidental logging.

- [x] **Map data and endpoints**
  - [x] Inventory: user data fields stored (email, etc.)
  - [x] Inventory: endpoints that read/write user-specific data
  - [x] Document: where auth is enforced (middleware/dependencies)
- [x] **Standardize auth checks**
  - [x] Every user-data endpoint requires authenticated user (pattern in place; key endpoints done)
  - [x] Reject unauthenticated requests
  - [x] Single reusable pattern (Depends(get_current_user)) so endpoints can't forget
- [x] **Enforce ownership checks**
  - [x] For every endpoint referencing objects by id (game, save, franchise, etc.): verify object belongs to current user before return/update/delete (helpers in BackEnd.utils.ownership)
  - [x] Add tests: "try another user's id" → must return 403/404
- [x] **Logging redaction**
  - [x] Identify logging of request bodies, headers, exceptions, DB documents
  - [x] Redact: Authorization headers, tokens, emails, personal identifiers (BackEnd.utils.log_redact)
  - [ ] Ensure production logging level excludes debug dumps
- [ ] **Database access hardening**
  - [ ] Confirm DB not publicly reachable except from backend
  - [ ] Confirm DB credentials server-side only, rotated if exposed
- [x] **Deliverable:** `docs/docs_1_systems/SECURITY_BASELINE.md` documenting auth pattern, ownership pattern, logging rules, DB rules
- [x] **Minimal tests:** unauthenticated access blocked, cross-user access blocked (tests/test_user_data_exposure.py)

### 5.3 Environment Variables Security
- [x] Verify no secrets in code (check git history)
- [x] Verify all secrets in environment variables
- [x] Verify staging and production use different secrets (JWT and DB confirmed)
- [x] Document all required environment variables — see `docs/docs_1_systems/ENV_VARIABLES.md`

### 5.4 Input Validation Review
- [x] Audit all API endpoints for input validation
- [x] Verify Pydantic models validate all request data (auth has validators; IDs validated via ObjectId in ownership)
- [x] Test invalid input handling (malformed JSON, wrong types) — tests added
- [x] Verify error messages don't leak sensitive info (500 responses use generic "Internal server error")
- [x] Test NoSQL injection prevention — `re.escape()` on all user input in `$regex`; no `$where`
- [x] XSS prevention — API returns JSON (escaped); auth bar uses `textContent` for email

### 5.5 Password Security
- [x] Use bcrypt for password hashing (BackEnd.utils.auth)
- [x] Minimum password requirements: 8–128 chars, letter, number
- [ ] Account lockout after 5 failed logins — deferred to post-alpha (Step 6 rate limiting helps)

### 5.6 Security Headers (Basic)
- [x] Add security headers: X-Frame-Options, X-Content-Type-Options, Referrer-Policy, HSTS
- [ ] Test headers are present (curl -I or browser devtools)
- [ ] CSP deferred — add after testing; inline scripts require careful policy

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
- [ ] **If on free tier (M0):**
  - [ ] Set up manual backup process (weekly/monthly exports)
  - [ ] Document how to export database (`mongodump` command or MongoDB Compass)
  - [ ] Store exports in safe location
  - [ ] Test restoration process
- [ ] **If on paid tier (M10+):**
  - [ ] Verify automated backups are enabled (usually enabled by default)
  - [ ] Verify backup retention period (7 days minimum recommended)
  - [ ] Test backup restoration process
  - [ ] Document how to restore from backup
- [ ] Document disaster recovery procedures (database restore, redeploy process)

### 7.1 Provider Alerts
- [ ] Configure MongoDB Atlas usage alerts
- [ ] Configure Railway spending alerts/caps
- [ ] Review Netlify bandwidth constraints

### 7.2 In-App Caps (Hard Stops)
- [ ] **One Franchise per user** - Each user can only have one active franchise instance
- [ ] **One Tournament per user** - Each user can only have one active tournament instance
- [ ] Max games per user per day (optional - evaluate need)
- [ ] Max sim requests per minute (optional - evaluate need)

> **Implementation Note:** When user starts a new franchise/tournament, check if they already have one. If so, either:
> - Block creation with message: "You already have an active [mode]. Delete it first to start a new one."
> - Or prompt: "Starting a new [mode] will replace your existing one. Continue?"

### 7.3 Verification
- [ ] Confirm caps actually block usage
- [ ] Confirm messaging is clear when a cap is hit

---

## Step 8 — Legal & Compliance (Ship Simple, Ship Real)

### 8.1 Terms of Service
- [ ] Create `/terms.html`
- [ ] Add footer link on all pages
- [ ] Add signup checkbox: "I agree to the Terms"

### 8.2 Privacy Policy
- [ ] Create `/privacy.html`
- [ ] Include: data collected, cookies, analytics, retention

### 8.3 Cookie Consent (Only If Needed)
- [ ] Decide if you'll serve users in jurisdictions requiring consent
- [ ] Implement banner if required (basic is fine)

---

## Step 9 — Basic Monitoring & Uptime Alerts

> **Note:** Railway and Netlify provide basic logging. This step adds external uptime monitoring.
> **Walkthrough:** See `step9_uptime_monitoring_walkthrough.md` for a concise first-time setup guide.

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
- [ ] **Database Monitoring (Optional):**
  - [ ] Enable MongoDB Atlas monitoring (free tier)
  - [ ] Monitor database connection pool
  - [ ] Monitor query performance
  - [ ] Set up alerts for database issues

### 9.5 Verification
- [ ] Confirm alerts actually fire (simulate downtime if feasible)
- [ ] Test alert delivery (email/Slack)

---

## Step 10 — End-to-End "No Surprises" Testing (Go/No-Go)

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
  - [ ] **SendGrid:** Free tier (100 emails/day)
  - [ ] **Mailgun:** Free tier (5,000 emails/month)
  - [ ] **Postmark:** Free tier (100 emails/month)
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
- [ ] "Report bug" link or button
- [ ] **User Documentation (Optional):**
  - [ ] How to play guide
  - [ ] FAQ page
  - [ ] Tutorial/onboarding flow (can be post-launch)

### 12.4 Admin-Only Pages (Production Only)
> **Note:** Restrict these builder tools to admin users. Apply only in production; staging/develop remain open for testing.

- [ ] **play-builder** — Admin-only (non-admins redirected or blocked)
- [ ] **HCT skeleton builder** — Admin-only
- [ ] **FCP skeleton builder** — Admin-only
- [ ] Auth guard: check `role: "admin"` before allowing access (client + API)
- [ ] Non-admins see 403 or redirect to mode-select (or homepage)

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
6. **Data Wipe:** Will wipe `games`, `tournaments`, `franchises`, `users` at launch. Preserve universal reference data (`teams`, `players`, `plays`, `fcp_skeletons`, `hct_skeletons`, `defenses`).
7. **Alpha Access Control:** One-time passwords (OTPs) required for signup when `IS_ALPHA=true`. 50 OTPs generated (limits alpha to 25-50 users), each usable once by one email. Each OTP is permanently linked to the email that uses it (`used_by_email` field) for access tracking. OTP validation disabled when `IS_ALPHA=false`.
8. **Instance Limits:** Each user limited to **one active Franchise** and **one active Tournament** at a time. Prevents runaway data growth and simplifies UX during alpha. Users must delete existing instance to start a new one.
9. **Admin-Only Pages:** play-builder, HCT skeleton builder, and FCP skeleton builder are restricted to admin users. Applied in **production only**; staging/develop remain open for testing.

### Testing Reference
- See `Final_Testing_Checklist.md` for detailed test scenarios (Step 10 references this)

### OTP Implementation Reference
- See `OTP_Implementation_Guide.md` for detailed implementation guide for one-time passwords
