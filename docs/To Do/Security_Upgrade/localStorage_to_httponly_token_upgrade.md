# Token Storage Upgrade: localStorage → HttpOnly Cookies

**Target:** Before alpha → beta transition  
**Effort:** ~Few hours  
**Rationale:** HttpOnly cookies are not readable by JavaScript; localStorage tokens are vulnerable to XSS theft.

---

## Current State (Alpha)

- Token stored in `localStorage.auth_token`
- Frontend sends `Authorization: Bearer ${token}` on API requests
- Auth guard checks `localStorage.getItem("auth_token")` for protected pages

---

## Target State (Beta)

- Token stored in HttpOnly cookie (set by backend)
- Browser sends cookie automatically with `credentials: 'include'`
- Auth guard calls `/api/auth/me` with credentials; 401 → redirect to login

---

## Backend Changes

| Area | Change |
|------|--------|
| Login/signup | Set `Set-Cookie: auth_token=...; HttpOnly; Secure; SameSite=Strict` in response; stop returning token in JSON body |
| Auth middleware | Read token from `request.cookies` instead of `Authorization` header |
| Logout | Add/update endpoint to clear cookie (`Set-Cookie` with `max-age=0`) |
| CORS | Enable `Access-Control-Allow-Credentials: true`; use explicit origins (no `*`) |

---

## Frontend Changes

| Area | Change |
|------|--------|
| Login/signup | Add `credentials: 'include'`; remove `localStorage.setItem("auth_token", ...)` |
| API fetches | Add `credentials: 'include'` to all requests; remove `Authorization` header |
| Auth guard | Replace localStorage check with fetch to `/api/auth/me`; 401 → redirect to login |
| Logout | Call logout endpoint; clear user info from localStorage |

---

## Notes

- Can support both Bearer and cookie during transition, then remove Bearer.
- Auth guard becomes async (fetch before redirect); UX impact minimal.
- See `BackEnd.utils.auth` and `FrontEnd/static/js/shared/authGuard.js` for current implementation.
