# Auth hardening + rate-limiter fix: 2026-09-30

Branch `fix/auth-hardening` @ `cb3666ac9` (based on develop `6f0bbcf18`), pushed. Not merged. **Ready for review.** Backend only; no FrontEnd files touched.

## ⚠️ Before merging to staging / production
1. **Set `JWT_SECRET_KEY` on staging** if it isn't already set. The app will not boot without it. All sessions signed with the old (dev) secret are logged out; that is intended.
2. **Run the duplicates script** on staging and prod (see §8) before the deploy that creates the unique indexes.
3. **Run the curl check** in §3 on staging after deploy.

## Railway variables Jamie must verify
| Var | Staging | Production | Why |
|---|---|---|---|
| `JWT_SECRET_KEY` | **must be set**, private, long random value | **must be set**, and different from staging | App refuses to boot otherwise (any `RAILWAY_*` var marks the runtime as hosted) |
| `ENVIRONMENT` | `staging` | `production` | Docs toggle, builder admin gate, secret check message |
| `EMAIL_UNSUB_SECRET` | recommended | recommended | Unsubscribe-link HMAC falls back to `JWT_SECRET_KEY`. Setting or rotating the JWT secret changes old unsubscribe links unless this is set |
| `RATE_LIMIT_GENERAL` | optional (default `300/minute`) | optional | Default per-IP limit |
| `RATE_LIMIT_WEEK_ADVANCE`, `RATE_LIMIT_CPU_SIMS`, `RATE_LIMIT_FINISH_SEASON` | optional | optional | Per-user heavy-route limits (below) |

`RAILWAY_ENVIRONMENT` is injected by Railway automatically. Don't set it by hand.

## What changed, per item
**1. JWT secret** (`BackEnd/utils/jwt_config.py`, new, no DB imports)
- **The rule:** `resolve_jwt_secret()` returns `JWT_SECRET_KEY` when it's a private value. It returns the public dev fallback only when ENVIRONMENT/ENV/RAILWAY_ENVIRONMENT is one of `"", dev, development, local, test` **and** no `RAILWAY_*` var exists. Otherwise it raises `JwtSecretNotConfigured`. Setting the secret to the literal dev value counts as unset.
- **Where it's enforced:**
  - `_bootstrap.py` calls it at import. It must run there, not in `auth.py`: `api.py`'s big `try` would swallow the error and leave the app serving only `/health` and `/startup-error`, and `/startup-error` would publish the message.
  - `auth.py` resolves it per call for sign/verify. Scripts that import `auth` for other helpers on a staging env don't crash, but still can't mint or accept dev-secret tokens.
- **Boot check (uvicorn):**
  - `RAILWAY_ENVIRONMENT=staging ENVIRONMENT=staging` with no secret: **exit 1**, `JwtSecretNotConfigured: JWT_SECRET_KEY must be set to a private value (environment='staging', hosted=True)...`.
  - `ENVIRONMENT=test GOB_DB_MODE=mongomock` with no secret: **starts**. `/health` is 200 and `/startup-error` is 404 (the full app loaded).
- **Desktop:** loopback sets `ENVIRONMENT=development` and has no `RAILWAY_*` vars, so it's unaffected.

**2. Token revocation + DB role** (`auth.py`)
- **Claims:** new tokens carry `tv`, which is the user's `token_version` (missing field = 0). Old tokens without `tv` count as 0, so every existing session keeps working until the first bump.
- **What's rejected:** `get_current_user` returns 401 "Invalid or expired token", and `_optional` returns None, when `tv` doesn't match the user's current `token_version` or the user doc no longer exists.
- **Cache:** `{token_version, role}` is cached per user for 60 seconds (`USER_AUTH_CACHE_TTL_SECONDS`), so it's one DB read per user per minute. A bump invalidates the entry immediately in this process.
  - If the lookup itself fails (DB down), the response is **503** "Authentication temporarily unavailable", not 401, so nobody is logged out by an outage.
- **What bumps `token_version`:**
  - `/reset-password`, in the same update as the new hash.
  - `/logout` **when the request carries a valid bearer token**. This is **sign out everywhere**: every session on every device.
- **Role:** it comes from the user doc (cached), not the token.
  - `get_admin_user` uses that role.
  - `require_admin_for_builder` now refuses a token claiming admin for a non-admin user. It used to trust `role=admin` in the token.
- **Desktop:** loopback overrides `get_current_user` with its local user, so none of this runs there.

**3. Rate limiter** (`rate_limiter.py`, `api.py`, `franchise_routes.py`)
- **Key:** `X-Real-IP`, else the **rightmost** `X-Forwarded-For` entry, else the socket peer. Never the leftmost entry.
- **Default limit:** `GENERAL_RATE_LIMIT` = `300/minute` (env `RATE_LIMIT_GENERAL`), applied by `SlowAPIASGIMiddleware`:
  - It's the pure-ASGI variant; `BaseHTTPMiddleware` breaks streaming and contextvars.
  - It's installed **innermost**, so a 429 still gets CORS headers. `add_middleware` would have wrapped it outside CORS.
  - Routes with their own `@limiter.limit` (sim, turn, auth) keep only their explicit limit, which is slowapi's rule.
  - Exempt: `/health` (GET and HEAD). OPTIONS preflights never match a route handler, so they're never counted. Static mounts are also exempt.
  - Desktop (loopback) keeps omitting rate limiting entirely.
- **Per-user limits:** keyed on the bearer token's `sub`, else the IP. They're a FastAPI dependency, not `@limiter.limit`, because tests and code call these route functions directly.

| Route | Limit | Reasoning |
|---|---|---|
| `/franchise/complete-week` (legacy), `/complete-week/phase-a`, `/phase-b` | **10/min** (`RATE_LIMIT_WEEK_ADVANCE`) | UI calls each once per played game (a game takes minutes); clients are single-flight (`franchisePhaseBClient`); phase-a retries once on `stale_game_id`; box-score and FCC recovery can re-fire phase-b. 10 covers retries and a second tab |
| `/complete-week/start-cpu-sims` | **6/min** (`RATE_LIMIT_CPU_SIMS`) | Once per week, single-flight (`franchiseStartCpuSimsClient`), and each call is 2+ minutes of CPU. A duplicate is idempotent-skipped by the claim anyway |
| `/franchise/finish-season` | **3/min** (`RATE_LIMIT_FINISH_SEASON`) | Once per season (a consumed transition token makes repeats 409). 3 allows a retry after a network error |

- **Not limited per user:** `sim-rest-of-tournament` and `sim-championship` are also heavy but weren't in the brief. They still fall under the 300/min default. They're easy to add.

**4. Reset tokens**
- Only `token_hash = sha256(token)` is stored, and lookups use the hash; the email link still carries the raw token.
- **Tokens issued before deploy (plaintext) stop working.** Users get "Invalid or expired reset link" and must request a new one. They expire within `RESET_TOKEN_EXPIRY_HOURS` anyway.

**5. Signup enumeration** (alpha mode)
- The code is checked read-only (`inspect_code`) **before** the email-exists check. A bad code gives the same `Invalid alpha access code` / `All spots on this code are claimed.` error it always did.
- "An account with this email already exists" (400) now only appears after a valid code, and doesn't spend a use of the code. `reserve_code` still does the atomic claim afterwards.
- **Non-alpha mode** has no code to check first, so the exists message is unchanged there.

**6. Login timing:** an unknown email runs `burn_password_check()`, one bcrypt verify against a fixed dummy hash (generated once, lazily), so it costs the same as a wrong password.

**7. bcrypt 72 bytes** (installed bcrypt is 5.0.0, which **raises** on >72 bytes instead of truncating)
- **Signup and reset:** a password over 72 UTF-8 bytes gets **400** "Password must be at most 72 bytes (shorter, or fewer non-ASCII characters)."
  - This check is in the route body, because pydantic validator errors surface as 422.
  - `hash_password` also refuses more than 72 bytes as a backstop.
- **Login:** `verify_password` truncates to 72 bytes exactly as old bcrypt did, so legacy long passwords still work. Characters beyond byte 72 never mattered, and still don't.

**8. Unique indexes**
- **The indexes:** `users.email` (`email_unique`, emails are stored lower-cased by signup) and `alpha_otps.otp_code` (`otp_code_unique`, codes are stored upper-cased).
- **Where:** `persistence/indexes.py`, wired through `MongoStore`, the `db.py` facade and `protocol.py`.
- **SQLite:** no-op. Both are **remote** collections on desktop (hosted Mongo owns them), the same as `ensure_users_username_index` there.
- **Startup:** each runs in its own `try`. A duplicate-key failure (E11000) logs `WARNING [DB] unique index users.email NOT created: duplicate values exist. Run scripts/ops/check_auth_dupes.py ...` and the app carries on. An index-options conflict (an existing non-unique `email_1`) also warns.
- **`scripts/ops/check_auth_dupes.py --db <name>`:** read-only (`connect_script_database(access="read")`). It reports:
  - exact dupes (these block the index)
  - case or whitespace variants
  - documents missing the field (more than one also blocks)
  - existing indexes

  It exits 0 if clean, 1 if something blocks, 2 if it can't connect. Emails are redacted unless `--show-values` is passed.
  ```bash
  ../gob-simplified/.venv/bin/python scripts/ops/check_auth_dupes.py --db gob-staging
  GOB_DB_ACCESS=read ../gob-simplified/.venv/bin/python scripts/ops/check_auth_dupes.py --db gob
  ```

## Curl check (staging): spoofed X-Forwarded-For must not dodge the login limit
```bash
API=https://api-staging.geekedoutbasketball.com
# 1) Rotate a fake LEFTMOST X-Forwarded-For. Expect 401 x10, then 429.
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code} " -X POST "$API/api/auth/login" \
    -H 'Content-Type: application/json' -H "X-Forwarded-For: 6.6.6.$i" \
    -d '{"email":"nobody@example.com","password":"Password1"}'
done; echo
# 2) Wait 60s, then rotate a fake X-Real-IP. Expect 401 x10, then 429 as well.
#    If this one never hits 429, Railway is passing a client-sent X-Real-IP through
#    (not overwriting it) — tell Claude; the key must then drop X-Real-IP.
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code} " -X POST "$API/api/auth/login" \
    -H 'Content-Type: application/json' -H "X-Real-IP: 6.6.6.$i" \
    -d '{"email":"nobody@example.com","password":"Password1"}'
done; echo
```

## Frontend follow-ups (not done: FrontEnd is off-limits)
- **Logout never sends the token.** `mode-select.js:1264`, `js/shared/gobSettings.js:216` and `js/shared/authBarInit.js:999` all POST `/api/auth/logout` with no `Authorization` header, and the `gobStore` fetch wrapper doesn't add one. Until they send `API_CONFIG.getAuthHeaders()`, **logout still doesn't revoke anything server-side**. Password reset does.
- **429 handling on heavy routes:** these return `{"detail": "Rate limit exceeded. Please try again in N seconds."}` plus `Retry-After`. The single-flight clients should treat a 429 like the existing 503 "retry" path.
- **Password rules copy:** the signup and reset forms could mention the 72-byte limit. The server message is already clear.

## Tests
`tests/test_auth_hardening.py`, 39 tests, with **no dependency override** (the fixture removes it):

| Area | Covered |
|---|---|
| JWT secret | Allowed: test/dev/local/empty. Refused: staging, production, prod, `RAILWAY_*`-hosted even with a dev name, and the dev value set literally. A private secret is accepted. A token forged with the dev secret gets 401 when a real secret is set |
| Revocation | Logout with a token makes **both** of that user's sessions 401, and a fresh login works. Logout without a token is still 200. A legacy token with no `tv` works until a bump, then 401. A deleted user's token gets 401. Auth state is cached (5 requests, 1 DB read) |
| Role | An admin claim in the token for a DB non-admin gets 403 on `/api/admin/reset-user-state`; after the DB role is set, it passes the gate. Same on the builder route `/api/plays` in production |
| Reset | The stored doc has `token_hash` only (no raw token anywhere). A reset makes the old JWT 401 and the new password logs in. A legacy plaintext token is rejected |
| Enumeration | An existing email with a bad code gets "Invalid alpha access code"; with a good code, "already exists", and no code use is spent |
| Timing | An unknown email calls `burn_password_check` once, and the dummy hash is real bcrypt |
| 72 bytes | Signup rejects 80 ASCII bytes and 43 chars / 83 bytes with 400. Reset rejects too. A legacy long-password user logs in (with truncation semantics preserved) |
| Rate limit | Leftmost XFF is ignored (unit). Rotating the fake leftmost XFF still hits 429 on login after 10. The default limit (swapped to 3/min) applies to `/app-config`; `/health` GET and HEAD are exempt; preflights aren't counted; a 429 keeps CORS headers. The finish-season limit is per user (user A is blocked on the 4th call; user B is unaffected) |
| Indexes | A clean collection gets the unique index. Dupes give False plus a WARNING naming the script. The dupes script reports exact and variant dupes and writes nothing |

**Harness changes:**
- `tests/conftest.py` and `tests/e2e/helpers/seed_and_serve.py` set `RATE_LIMIT_GENERAL=1000000/minute` (setdefault).
- Why: every TestClient request without a forwarding header shares the key `testclient`, and parallel Playwright workers share 127.0.0.1, so a real 300/min would trip mid-run. The default-limit tests swap in 3/min explicitly.
- `conftest` still overrides auth for all other tests. This change touches auth, which is why the new file removes the override.

| Run | Result |
|---|---|
| New file | 39 passed |
| Existing auth-adjacent tests (alpha access and email, home base, FTE contract, persistence adapter, finish-season, complete-week, trophy log, career data, browse_rev, tb-leak, user data exposure) | 282 passed |
| SQLite mode (no documented suite-wide switch; spot check with `GOB_PERSISTENCE=sqlite` on `test_auth_hardening.py` + `test_alpha_access.py`) | 50 passed |
| Full suite (default config, once) | 4168 passed, 20 skipped, 109 xfailed, 1 xpassed, 0 failed, 0 errors (the same pre-existing leaders-view XPASS) |

## Unsure / notes
- **`X-Real-IP` trust:** this assumes Railway's edge **sets or overwrites** `X-Real-IP`. The curl step 2 verifies it.
  - Prod `api.geekedoutbasketball.com` resolves as a CNAME to `*.up.railway.app` (not Cloudflare-proxied), so Railway sees the real client.
  - `api-staging` didn't resolve from this machine.
  - If a CDN is ever put in front, the key must change (for example to `CF-Connecting-IP`).
- **Deleted users:** their tokens now get 401 (before, they worked until expiry). Deliberate.
- **Cache staleness:** a role change or revocation made by **another process** takes up to 60 seconds to be seen. Railway runs one web process, so it's immediate in practice.
- **Red check:** I didn't run the new tests against the pre-change code, because the file imports the new helpers, so it wouldn't even collect. The assertions target behaviour the old code didn't have: leftmost XFF, token-only admin, plaintext reset lookup, no `tv`.
- **Out of scope:** `complete-week` and the other franchise routes have no auth dependency at all (the per-user key falls back to IP when no token is sent). That's pre-existing.

---
Gate: `Migration gates passed.` (Gate A: 0 imports in 0 files; Gate B: 138 lines in 46 files)
Full suite: `= 4168 passed, 20 skipped, 109 xfailed, 1 xpassed, 4031 warnings in 207.84s (0:03:27) =`
