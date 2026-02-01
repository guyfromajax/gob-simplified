# Auth Manual Verification Checklist

**Purpose:** Verify user auth and ownership controls prevent unauthorized access to franchise/tournament data.

**Environment:** Use your dev deployment (e.g. gob-test.netlify.app + gob-simplified-staging.up.railway.app) or localhost.

---

## Test 1: Unauthenticated Access (Different Computer, Not Logged In)

**Goal:** Confirm a user without a token cannot access another user's franchise.

1. **Computer A (logged in):**
   - Log in to the app
   - Create or select a franchise
   - Note the URL (e.g. `franchise-command-center.html?franchise_id=697f56af5da48ceaff428c1c`)
   - Copy the full URL including `franchise_id`

2. **Computer B (or incognito window):**
   - Do **not** log in
   - Paste the franchise command center URL and navigate to it

**Expected:**
- Auth guard redirects to `/login.html?redirect=...` before the page loads, **or**
- Page loads but API calls return 401 and the UI shows an error / empty state (no franchise data displayed)

---

## Test 2: Cross-User Access (Different Account)

**Goal:** Confirm User B cannot access User A's franchise or tournament.

1. **User A (Computer A):**
   - Log in as User A
   - Create a franchise, note the `franchise_id` from the URL

2. **User B (Computer B or incognito):**
   - Log in as User B (different account)
   - Try to open: `franchise-command-center.html?franchise_id=<User A's franchise_id>`

**Expected:**
- API returns 403 Forbidden or 404 Not Found
- No franchise data is displayed; user sees an error or empty state

---

## Test 3: Same Pattern for Tournament

Repeat Test 1 and Test 2 using tournament URLs, e.g.:
- `tournament.html?tournament_id=<id>`

---

## Quick Reference: Protected Endpoints

| Endpoint | Expects |
|----------|---------|
| `POST /franchise/select-team` | 401 if no token |
| `POST /franchise/play-next-game` | 401 if no token; 403/404 if wrong user |
| `GET /franchise/command-center/data` | 401 if no token; 403/404 if wrong user |
| `GET /api/game/{game_id}` | 401 if no token; 403/404 if wrong user |
| `POST /tournament/start` | 401 if no token |

---

## Notes

- Auth guard runs in the browser; direct API calls (e.g. via curl) will bypass it and should return 401 from the backend
- For local testing: ensure backend and frontend use the same base URL (e.g. both localhost or both staging)
