## User Account System ✅ **COMPLETE** (February 2025)

**Base Constants**

1. **Endpoints**:
   - **POST /api/auth/signup** – Create account (OTP required when `IS_ALPHA=true`)
   - **POST /api/auth/login** – Login and get JWT token
   - **GET /api/auth/me** – Current user info (requires auth)
   - **GET /api/auth/config** – Auth config (IS_ALPHA, OTP required)
   - **POST /api/auth/set-username** – Set username (requires auth)
   - **POST /api/auth/reset-request** – Request password reset email (body: `email`)
   - **POST /api/auth/reset-password** – Set new password with token (body: `token`, `new_password`)

2. **Data**:
   - **Users collection**: `user_id` (ObjectId), `email`, `password_hash`, `role`, `username` (optional), `username_lower` (for uniqueness), `created_at`, `last_login_at`, `version`
   - **password_reset_tokens collection**: `token`, `user_id`, `expires_at`, `created_at` (tokens expire in 1 hour, deleted after use)
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
| POST | /api/auth/set-username | Yes | Set or update username |
| POST | /api/auth/reset-request | No | Request reset email (generic 200 response) |
| POST | /api/auth/reset-password | No | Set new password with token; invalidates token |

### Password Reset (Step 11)

- **Flow:** User goes to `/reset-password.html` (or "Forgot password?" on login). Without token: enters email → `POST /api/auth/reset-request` → if user exists, a reset link is emailed (SendGrid). With token in URL: user sets new password → `POST /api/auth/reset-password` → token invalidated, password updated.
- **Email:** SendGrid v3 API. If `SENDGRID_API_KEY` is not set, reset-request still returns 200 but no email is sent.
- **Env vars:** `SENDGRID_API_KEY`, `RESET_EMAIL_FROM` (default `noreply@geekedoutbasketball.com`), `RESET_LINK_BASE_URL` (default `https://www.geekedoutbasketball.com`).
- **Files:** `BackEnd/utils/email_sender.py`, `BackEnd/api/auth_routes.py`, `FrontEnd/static/reset-password.html`, `BackEnd/db.py` (`password_reset_tokens_collection`).

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

### Key Files

- **BackEnd/api/auth_routes.py** – All auth endpoints (signup, login, me, config, set-username)
- **BackEnd/utils/auth.py** – Password hashing, JWT creation, `get_current_user`, `get_user_by_email`
- **BackEnd/utils/otp_validator.py** – Alpha OTP validation and consumption
- **BackEnd/utils/rate_limiter.py** – Rate limit config; auth endpoints use `AUTH_RATE_LIMIT`
- **BackEnd/db.py** – `users_collection`, `alpha_otps_collection`, `password_reset_tokens_collection`
- **BackEnd/utils/email_sender.py** – SendGrid password-reset email (Step 11)
