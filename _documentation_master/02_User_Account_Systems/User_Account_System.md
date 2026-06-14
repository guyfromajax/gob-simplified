## User Account System ✅ **COMPLETE** (February 2025)

**Base Constants**

1. **Endpoints**:
   - **POST /api/auth/signup** – Create account (OTP required when `IS_ALPHA=true`)
   - **POST /api/auth/login** – Login and get JWT token
   - **POST /api/auth/logout** – Logout (client discards token)
   - **GET /api/auth/me** – Current user info incl. `account_settings`, `tutorial_state`, `record`, `archetypes`, `lead_archetype`, `archetype_reveal_seen`, `archetype_evolution_pending`, alpha-feedback gating (`alpha_feedback_submitted`, `alpha_feedback_games`, `alpha_feedback_prompt_level`), tutorial-alert state (`tutorial_alerts_franchise_id`, `tutorial_alerts_dismissed`, `tutorial_alerts_games`, `tutorial_alerts_training_returns`), plus account-page fields `subscription`, `geek_points`, `geek_points_by_team`, `championships_total` (requires auth)
   - **GET /api/auth/config** – Auth config (IS_ALPHA, OTP required)
   - **POST /api/auth/request-access-code** – Request alpha access code (body: `email`); stores request for admin to process manually
   - **POST /api/auth/set-username** – Set username (requires auth)
   - **PATCH /api/auth/account-settings** – Update account settings, e.g. `display_color` (requires auth)
   - **PATCH /api/auth/archetype-reveal-seen** – Mark the one-time first-archetype reveal modal seen (requires auth)
   - **PATCH /api/auth/archetype-evolution-seen** – Clear `archetype_evolution_pending` after the evolution modal is shown or skipped (requires auth)
   - **PATCH /api/auth/alpha-feedback-prompt-seen** – Record the alpha-feedback prompt threshold shown (`$max` on `alpha_feedback_prompt_level`, so each variant fires once) (requires auth)
   - **PATCH /api/auth/tutorial-alert-dismiss** – Mark a tutorial alert (coach card) shown; `$addToSet` on `tutorial_alerts_dismissed` (requires auth)
   - **PATCH /api/auth/tutorial-alerts-enroll** – Lock tutorial-alert progress to the user's first franchise (`tutorial_alerts_franchise_id`, set-once) (requires auth)
   - **PATCH /api/auth/tutorial-alerts-increment** – Forward-only counters (`tutorial_alerts_games` / `tutorial_alerts_training_returns`) on the locked franchise (requires auth)
   - **GET /api/auth/leaderboard** – Alpha leaderboard (geek-points + franchise-rank views); each coach row includes `lead_archetype` (requires auth)
   - **POST /api/auth/fte-complete** – Mark legacy first-time experience complete (requires auth)
   - **POST /api/auth/tutorial-advance** – Advance the FTE v2 tutorial step (requires auth)
   - **POST /api/auth/tutorial-complete** – Complete the FTE v2 tutorial (requires auth)
   - **POST /api/auth/reset-request** – Request password reset email (body: `email`)
   - **POST /api/auth/reset-password** – Set new password with token (body: `token`, `new_password`)
   - Also: **GET /api/leaderboard/by-team** (`BackEnd/api/leaderboard_routes.py`) – top coaches per A1 team; rows include `lead_archetype`

2. **Data**:
   - **Users collection**:
     - *Auth core:* `_id` (ObjectId), `email`, `password_hash`, `role`, `subscription`, `username` (optional), `username_lower` (for uniqueness), `created_at`, `updated_at`, `last_login_at`, `version`
     - *Geek points:* `geek_points` (int total), `geek_points_by_team` (optional dict: canonical `team_id` → int; lazy-created on first award per team)
     - *Profile / UX:* `account_settings` (`{ display_color }`), `fte` (bool, legacy FTE flag), `fte_v2_complete` (bool), `tutorial_state` (`{ step, team_pick, started_at, completed_at }`)
     - *Coaching-archetype tracking:* `record` (`{ wins, losses, total_games, win_rate, discount_wins, discount_losses }`), `archetypes` (18 per-archetype counters + `total`), `lead_archetype` (string key, `""` when no games), `archetype_reveal_seen` (bool), `archetype_evolution_pending` (string archetype key, `""` when consumed). Shapes are the single source of truth in `BackEnd/utils/user_tracking.py` — see [`00_General_Systems/Coaching_Archetype_System.md`](Coaching_Archetype_System.md).
     - *Alpha feedback gating:* `alpha_feedback_submitted` (bool), `alpha_feedback_games` (int), `alpha_feedback_prompt_level` (int, `$max`-advanced threshold of the last feedback prompt shown)
     - *Tutorial alerts:* `tutorial_alerts_dismissed` (array of alert ids), `tutorial_alerts_franchise_id` (set-once lock to the user's first franchise), `tutorial_alerts_games` / `tutorial_alerts_training_returns` (forward-only counters on the locked franchise)
     - *Titles / championships:* `championships_total` (dict: `kind` → int count) and `championships_by_team` (dict: canonical `team_id` → `kind` → int). The four title `kind` keys:
       - `conf_rs` — regular-season conference championship (1-seed at week 26)
       - `conf_t` — conference tournament title
       - `region` — region tournament title
       - `national` — national title
       - **Lazy:** these fields do not exist on a fresh user — they're `$inc`-created the moment a coach wins their first title, by `maybe_award_conference_rs_championship` / `maybe_award_franchise_eos_title_championship` in `BackEnd/utils/franchise_championships.py` (called from the franchise game-completion flow in `franchise_routes.py`). **No backfill needed** — readers default each kind to `0` when absent (`/api/auth/me` and the account page). Source of truth: `BackEnd/utils/franchise_championships.py`.
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
**Scope:** Signup, login, logout, JWT, protected endpoints, username, account settings, FTE/tutorial state, and coaching-archetype tracking surfaced on the user doc

### User Game Record Tracking

User win/loss tracking lives on `users.record`.

Fields:

- `wins` — completed user franchise games won
- `losses` — completed user franchise games lost
- `total_games` — derived as `wins + losses`
- `win_rate` — derived as `round(100 * wins / total_games)` when `total_games > 0`, else `0`
- `discount_wins` — completed wins where the game used **Sim Full Game** or **Sim Rest of Game**
- `discount_losses` — completed losses where the game used **Sim Full Game** or **Sim Rest of Game**

Every completed user franchise game increments either `wins` or `losses`. If the completed game has `games.bulk_sim_used = true`, the same outcome also increments either `discount_wins` or `discount_losses`.

`games.bulk_sim_used` is set by `/api/simulate-quarter` when the user advances via Sim Full Game or Sim Rest of Game. It is sticky once true, so later played quarters cannot clear the discount marker.

Geek Points use the same marker: bulk-sim games receive the base Geek Points award, while non-bulk games receive 2x the final base award. See [`Geek_Points_System.md`](Geek_Points_System.md).

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/auth/config | No | Returns `is_alpha`, `otp_required` |
| POST | /api/auth/signup | No | Create user; OTP required when alpha |
| POST | /api/auth/login | No | Email + password → JWT + user |
| POST | /api/auth/logout | No | Logout (client discards token) |
| GET | /api/auth/me | Yes | Current user profile (settings, tutorial_state, record, archetypes, lead_archetype, archetype_reveal_seen, subscription, geek_points, geek_points_by_team, championships_total) |
| POST | /api/auth/request-access-code | No | Request alpha access code (body: email); stores in DB for admin |
| POST | /api/auth/set-username | Yes | Set or update username |
| PATCH | /api/auth/account-settings | Yes | Update account settings (e.g. `display_color`) |
| PATCH | /api/auth/archetype-reveal-seen | Yes | Mark the one-time first-archetype reveal modal seen |
| PATCH | /api/auth/archetype-evolution-seen | Yes | Clear pending archetype-evolution modal (shown or skipped) |
| PATCH | /api/auth/alpha-feedback-prompt-seen | Yes | Record alpha-feedback prompt threshold shown (forward-only) |
| PATCH | /api/auth/tutorial-alert-dismiss | Yes | Mark a tutorial alert (coach card) shown |
| PATCH | /api/auth/tutorial-alerts-enroll | Yes | Lock tutorial-alert progress to first franchise (set-once) |
| PATCH | /api/auth/tutorial-alerts-increment | Yes | Increment games / training-returns tutorial-alert counters |
| GET | /api/auth/leaderboard | Yes | Alpha leaderboard (geek-points + rank views); rows include `lead_archetype` |
| POST | /api/auth/fte-complete | Yes | Mark legacy first-time experience complete |
| POST | /api/auth/tutorial-advance | Yes | Advance FTE v2 tutorial step |
| POST | /api/auth/tutorial-complete | Yes | Complete FTE v2 tutorial |
| POST | /api/auth/reset-request | No | Request reset email (generic 200 response) |
| POST | /api/auth/reset-password | No | Set new password with token; invalidates token |
| GET | /api/leaderboard/by-team | Yes | Top coaches per A1 team; rows include `lead_archetype` (separate router) |

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

- **BackEnd/api/auth_routes.py** – All `/api/auth/*` endpoints (signup, login, logout, me, config, set-username, account-settings, archetype-reveal-seen, leaderboard, fte-complete, tutorial-advance/complete, reset)
- **BackEnd/api/leaderboard_routes.py** – `/api/leaderboard/by-team` (coach leaderboards; rows carry `lead_archetype`)
- **BackEnd/utils/user_tracking.py** – single source of truth for the `record` / `archetypes` / `lead_archetype` shapes on the user doc (see `00_General_Systems/Coaching_Archetype_System.md`)
- **BackEnd/utils/auth.py** – Password hashing, JWT creation, `get_current_user`, `get_user_by_email`
- **BackEnd/utils/otp_validator.py** – Alpha OTP validation and consumption
- **BackEnd/utils/rate_limiter.py** – Rate limit config; auth endpoints use `AUTH_RATE_LIMIT`
- **BackEnd/db.py** – `users_collection`, `alpha_otps_collection`, `access_code_requests_collection`, `password_reset_tokens_collection`
- **BackEnd/utils/email_sender.py** – SendGrid password-reset email (Step 11)
- **FrontEnd/static/js/shared/accessDenied.js** – 401/403 UX + redirect; clears `auth_token` on 401
- **FrontEnd/static/set-lineup.js** – lineup/gameplay fetches fail closed on 401/403


### User Access Surfaces (implemented)

**Account modal** (gear icon in the top nav bar; built in `FrontEnd/static/js/shared/authBarInit.js`):

- Username row — avatar, username, lead-archetype badge, LOCKED indicator (display-only)
- Scouting Ambience toggle (instant-apply switch; persists via `PATCH /api/auth/account-settings`)
- "Account Details" link to `/account.html`

**Full account page** (`FrontEnd/static/account.html`):

- Identity header — avatar circle, username, lead-archetype badge
- Geek Points total + per-team breakdown (`geek_points`, `geek_points_by_team`)
- Titles section — the four `championships_total` kinds (national, region, conference tournament, regular-season conference), zero-count rows dimmed
- Scouting Ambience toggle
- In-Game Display toggle ("Pos" / "#") — **placeholder**: rendered disabled with "coming soon"; feature not yet built
- Coaching Archetypes board — all archetypes with non-zero counts, ranked descending, multi-column grid (via `archetypeBadge.js` / `GOBArchetype`)
- "Season History" link — **dead link** (`aria-disabled`); the user-history page is not yet built
- Link to `/coaching-archetypes.html` explainer page
