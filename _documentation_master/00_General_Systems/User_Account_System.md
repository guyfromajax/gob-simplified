## User Account System ✅ **COMPLETE** (February 2025)

**Base Constants**

1. **Endpoints**:
   - **POST /api/auth/signup** – Create account (OTP required when `IS_ALPHA=true`)
   - **POST /api/auth/login** – Login and get JWT token
   - **GET /api/auth/me** – Current user info (requires auth)
   - **GET /api/auth/config** – Auth config (IS_ALPHA, OTP required)
   - **POST /api/auth/request-access-code** – Request alpha access code (body: `email`); stores request for admin to process manually
   - **POST /api/auth/set-username** – Set username (requires auth)
   - **POST /api/auth/reset-request** – Request password reset email (body: `email`)
   - **POST /api/auth/reset-password** – Set new password with token (body: `token`, `new_password`)

2. **Data**:
   - **Users collection**: `user_id` (ObjectId), `email`, `password_hash`, `role`, `subscription`, `geek_points` (int total), `geek_points_by_team` (optional dict: canonical `team_id` → int; lazy-created on first award per team), `username` (optional), `username_lower` (for uniqueness), `created_at`, `last_login_at`, `version`
   - **role**: `"user"` (default) or `"admin"`. New signups get `role: "user"`. To set admin: run `python scripts/set_admin_user.py <email>` (or `set_admin_user_production.py` for production DB). Admin status is read from the DB when needed: `/api/auth/me` and builder API checks use the DB role so promoting a user to admin works without re-login.
   - **subscription**, **geek_points**: New signups get `subscription: "alpha"` (string) and `geek_points: 0` (integer). `geek_points_by_team` is not set until the user earns franchise points by team. Existing users were backfilled via `scripts/add_user_subscription_geek_points.py`.
   - **password_reset_tokens collection**: `token`, `user_id`, `expires_at`, `created_at` (tokens expire in 1 hour, deleted after use)
   - **access_code_requests collection**: `email`, `created_at`, `status` ("pending"). Used when user clicks "Request Access Code" on signup; admin checks collection and sends codes manually (no transactional email until configured).
   - **JWT**: Stored client-side; sent in `Authorization: Bearer <token>` for protected endpoints
   - **Alpha OTP**: When `IS_ALPHA=true`, signup requires valid unused OTP from `alpha_otps` collection

3. **Password rules**: 8–128 characters, at least one letter and one number. Hashed with bcrypt.

**User Account System Flow (4 Steps)**

1. **Signup** – Validate email, password, OTP (if alpha); create user doc; return JWT and user payload
2. **Login** – Find user by email; verify password; issue JWT; update `last_login_at`; return JWT and user payload
3. **Protected routes** – `get_current_user` dependency validates JWT and loads user; 401 if invalid/missing
4. **Username** – Optional; set via `/api/auth/set-username`; uniqueness is case-insensitive (`username_lower`)

**Long Form Documentation**

### Overview

The User Account System handles signup, login, JWT-based authentication, and optional usernames. When the app is in alpha mode (`IS_ALPHA=true`), signup requires a one-time access code (OTP). Auth endpoints are rate-limited per IP to prevent brute force.

**Location:** `BackEnd/api/auth_routes.py`, `BackEnd/utils/auth.py`, `BackEnd/utils/otp_validator.py`  
**Status:** ✅ Implemented with rate limiting and alpha OTP  
**Scope:** Signup, login, JWT, protected endpoints, username

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/auth/config | No | Returns `is_alpha`, `otp_required` |
| POST | /api/auth/signup | No | Create user; OTP required when alpha |
| POST | /api/auth/login | No | Email + password → JWT + user |
| GET | /api/auth/me | Yes | Current user profile |
| POST | /api/auth/request-access-code | No | Request alpha access code (body: email); stores in DB for admin |
| POST | /api/auth/set-username | Yes | Set or update username |
| POST | /api/auth/reset-request | No | Request reset email (generic 200 response) |
| POST | /api/auth/reset-password | No | Set new password with token; invalidates token |

### Request Access Code (alpha signup)

- **Flow:** On the signup page (when `IS_ALPHA=true`), a "Request Access Code" link appears below the Alpha Access Code field. User must enter a valid email above (password can be blank). On click, the frontend validates the email; if valid, it calls **POST /api/auth/request-access-code** with `{ "email": "..." }`. The backend stores a document in **access_code_requests** with `email`, `created_at`, and `status: "pending"`. No email is sent. The user sees a popup: "Thanks Coach, we'll send your access code shortly." Admin checks the `access_code_requests` collection (e.g. daily) and sends codes manually. When transactional email is added later, the same collection can drive automated "send code to user" flows.
- **Rate limit:** Same as other auth endpoints (10/minute per IP).
- **Files:** `BackEnd/api/auth_routes.py`, `BackEnd/db.py` (`access_code_requests_collection`), `FrontEnd/static/signup.html`, `FrontEnd/static/auth.css`.

### Password Reset (Step 11)

- **Flow:** User goes to `/reset-password.html` (or "Forgot password?" on login). Without token: enters email → `POST /api/auth/reset-request` → if user exists, a reset link is emailed (SendGrid). With token in URL: user sets new password → `POST /api/auth/reset-password` → token invalidated, password updated.
- **Email:** SendGrid v3 API. If `SENDGRID_API_KEY` is not set, reset-request still returns 200 but no email is sent.
- **Env vars:** `SENDGRID_API_KEY`, `RESET_EMAIL_FROM` (default `noreply@geekedoutbasketball.com`), `RESET_LINK_BASE_URL` (default `https://www.geekedoutbasketball.com`).
- **Files:** `BackEnd/utils/email_sender.py`, `BackEnd/api/auth_routes.py`, `FrontEnd/static/reset-password.html`, `BackEnd/db.py` (`password_reset_tokens_collection`).

### Admin role (live from DB)

- **`/api/auth/me`** returns the user’s `role` from the database when the user doc is loaded, so the frontend admin guard sees up-to-date admin status.
- **Builder API** (`require_admin_for_builder` in `BackEnd/utils/auth.py`): if the JWT does not contain `role: "admin"`, the backend checks the user document in the DB; if the DB has `role: "admin"`, the request is allowed. No re-login required after promoting a user to admin.

### Rate Limiting and Response Type Fix ✅ **FIX** (February 2025)

**Issue:**  
Login (and signup) returned **500 Internal Server Error** in production (Railway). Logs showed:

```text
Exception: parameter `response` must be an instance of starlette.responses.Response
```

**Root cause:**  
Auth endpoints use **SlowAPI** for rate limiting (`@limiter.limit(AUTH_RATE_LIMIT)`). The limiter wraps the endpoint and injects rate-limit headers into the **return value**. It expects a Starlette `Response` (e.g. `JSONResponse`). The login and signup handlers were returning a **Pydantic model** (`AuthResponse`) directly. FastAPI would normally convert that to a response later, but SlowAPI sees the raw return value and raises if it is not a `Response`.

**Fix:**  
- **Login** and **signup** no longer return `AuthResponse` directly and no longer use `response_model=AuthResponse`.
- They build the same `AuthResponse` payload, call `.model_dump()`, and return **`JSONResponse(content=payload, status_code=200)`**.
- SlowAPI then receives a proper `Response` and can inject headers; the 500 is resolved and login/signup succeed.

**Key detail:** Any endpoint decorated with `@limiter.limit(...)` must return a `starlette.responses.Response` (e.g. `JSONResponse`), not a plain dict or Pydantic model.

**Key files:**
- `BackEnd/api/auth_routes.py` – login/signup return `JSONResponse(content=AuthResponse(...).model_dump(), status_code=200)`
- `BackEnd/utils/rate_limiter.py` – `AUTH_RATE_LIMIT` (10/minute per IP)

### Token Validation on Page Load ✅ **FIX** (February 2025)

**Issue:**  
Stale/invalid tokens in `localStorage` caused UI to show "logged in" state even when token was expired. User would see username on homepage/mode-select, but API calls (e.g., `/tournament/start`) would fail with 401 "Invalid or expired token", leaving user stuck.

**Root cause:**  
- `authBarInit.js` showed logged-in state based on localStorage presence without validating token
- `mode-select.js` called `/api/auth/me` but didn't handle 401 responses
- No token cleanup on page load

**Fix:**  
- **`authBarInit.js`**: Validates token via `/api/auth/me` before showing logged-in state. On 401, clears localStorage and shows "Log In"
- **`mode-select.js`**: Handles 401 from `/api/auth/me` and clears localStorage/updates UI
- **`tournament-select.js`**: Handles 401 from `/tournament/start` and redirects to login with redirect param

**Key files:**
- `FrontEnd/static/js/shared/authBarInit.js` – validates token on init
- `FrontEnd/static/mode-select.js` – handles 401 from `/api/auth/me`
- `FrontEnd/static/tournament-select.js` – handles 401 and redirects to login

### Set lineup & gameplay APIs (401/403) ✅ **FIX** (March 2025)

**Issue:**  
`authGuard.js` only checks that `localStorage.auth_token` exists before allowing protected pages (e.g. `set-lineup.html`). It does **not** prove the JWT is still valid. If the token is expired or invalid, roster and game fetches could return **401** while the page still rendered “in game” UI with **default energy/stats** (merge from `GET /api/game/...` skipped), which was easy to miss because failures were mostly `console.warn`.

**Root cause:**  
- Lineup roster fetch did not send `Authorization` headers.  
- `GET /api/game/{id}`, `POST /api/init-game`, `POST /api/autoset-lineup`, and related calls did not use the shared access-denied handler on 401/403.

**Fix:**  
- **`set-lineup.html`** loads **`accessDenied.js`** (after `api-config.js`).  
- **`set-lineup.js`**: `abortIfAccessDenied(response)` wraps `AccessDenied.checkAccessDenied` for roster (`/roster/...` with `API_CONFIG.getAuthHeaders()`), franchise command-center prefetch, `init-game`, `GET /api/game/...`, `autoset-lineup`, and the Game Plan / Playbooks / Play Game init paths. On **401** or **403**, the user sees a full-screen message and is redirected (401 → login with `?redirect=...`, 403 → mode-select).  
- **`accessDenied.js`**: On **401**, clears **`auth_token`** from `localStorage` before redirect (aligned with `authBarInit.js`).

**Key files:**  
- `FrontEnd/static/set-lineup.html` – includes `js/shared/accessDenied.js`  
- `FrontEnd/static/set-lineup.js` – `abortIfAccessDenied`, auth headers on roster, all protected fetches  
- `FrontEnd/static/js/shared/accessDenied.js` – shared handler; clears token on 401  
- `FrontEnd/static/js/shared/authGuard.js` – presence-only gate (still required; API layer enforces real session)

### Key Files

- **BackEnd/api/auth_routes.py** – All auth endpoints (signup, login, me, config, set-username)
- **BackEnd/utils/auth.py** – Password hashing, JWT creation, `get_current_user`, `get_user_by_email`
- **BackEnd/utils/otp_validator.py** – Alpha OTP validation and consumption
- **BackEnd/utils/rate_limiter.py** – Rate limit config; auth endpoints use `AUTH_RATE_LIMIT`
- **BackEnd/db.py** – `users_collection`, `alpha_otps_collection`, `access_code_requests_collection`, `password_reset_tokens_collection`
- **BackEnd/utils/email_sender.py** – SendGrid password-reset email (Step 11)
- **FrontEnd/static/js/shared/accessDenied.js** – 401/403 UX + redirect; clears `auth_token` on 401
- **FrontEnd/static/set-lineup.js** – lineup/gameplay fetches fail closed on 401/403
