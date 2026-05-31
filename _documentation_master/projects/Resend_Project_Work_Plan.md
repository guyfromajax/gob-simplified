# Resend / Alpha Access Code — Work Plan

**Companion:** [Resend_Project_Brief.md](Resend_Project_Brief.md)  
**Status:** Ready for implementation  
**Vendor:** [Resend](https://resend.com) (transactional API; password reset stays on SendGrid)

---

## Objective

Automate alpha access code delivery for:

1. **Backfill** — ~36 pending docs in production `gob.access_code_requests`
2. **Live path** — `POST /api/auth/request-access-code` sends welcome or waitlist email automatically

Rollout: **staging first** (one real test user at a time) → **production backfill** → production live path.

---

## Decisions (locked)

| Topic | Decision |
|-------|----------|
| OTP tracking | MongoDB source of truth: `sent` + `used` on `alpha_otps` (not `used_otp_codes.md` at runtime) |
| Capacity | Count of `alpha_otps` where `sent: false` and `used: false` |
| De-dupe (backfill) | One row per email; **oldest** `created_at` wins |
| OTP reservation | On send: set `sent: true`, `sent_to_email`, `sent_at`; reserved until signup sets `used: true` |
| Send failure | **Rollback** `sent` if Resend fails (OTP returns to pool) |
| Already registered | **Skip** if email exists in `users` (backfill + live path where applicable) |
| Repeat request, OTP unused | **Resend same code** (same OTP doc) |
| Repeat request, OTP used | Trigger existing **`POST /api/auth/reset-request`** internally (SendGrid) |
| No capacity | Send “coming soon” email; `access_code_requests.status = waitlisted`; FIFO = `created_at` |
| Rate limits | Existing `AUTH_RATE_LIMIT` on endpoint **+ light per-email cap** (e.g. 3/hour) |
| From address | `jamie@geekedoutgames.com` |
| Badge asset | `FrontEnd/static/images/gob-alpha-badge.png` → hosted URL in HTML |
| Password reset | **Keep SendGrid** — do not migrate to Resend |
| Historical codes | One-time migration: mark `sent: true` from `_documentation_master/projects/used_otp_codes.md` |
| Eligibility (migration only) | Codes listed in `used_otp_codes.md` treated as already sent during migration |

### Resend pricing (brief Q&A)

- **Free tier:** 3,000 emails/month, **100 emails/day** — sufficient for backfill (~36) + staging tests.
- **Paid ($20/mo Pro):** Only needed if same-day volume exceeds 100 or you want no daily cap.
- **Required regardless:** Verified sending domain for `geekedoutgames.com` (or From domain) in Resend dashboard.

---

## Schema changes

### `alpha_otps` collection

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `otp_code` | string | (existing) | Unique code |
| `used` | bool | `false` | Redeemed at signup |
| `used_by_email` | string \| null | (existing) | Set on signup |
| `used_at` | datetime \| null | (existing) | Set on signup |
| `created_at` | datetime | (existing) | Generated at |
| **`sent`** | bool | `false` | **NEW** — Emailed to a user |
| **`sent_to_email`** | string \| null | `null` | **NEW** — Recipient |
| **`sent_at`** | datetime \| null | `null` | **NEW** — When emailed |

**Eligible OTP for assignment:** `used: false`, `sent: false`.

### `access_code_requests` collection

| Field | Type | Meaning |
|-------|------|---------|
| `email` | string | Requester (lowercase) |
| `created_at` | datetime | Request time (waitlist order) |
| `status` | string | `pending` \| `sent` \| `waitlisted` \| `skipped` \| `failed` |
| **`otp_code`** | string \| null | **NEW** — Assigned when sent |
| **`sent_at`** | datetime \| null | **NEW** — When welcome email sent |

**Backfill skip reasons:** `skipped` + reason (e.g. `already_registered`, `duplicate_email`, `no_otp_capacity`).

---

## Email templates (in repo, not Resend dashboard)

Implement in `BackEnd/utils/resend_sender.py` (or `BackEnd/utils/alpha_email.py`):

### 1. Alpha welcome (code included)

Content matches manual sends (user-provided copy):

- Greeting: “Hey Coach,”
- Welcome + patience / feature updates / Coach’s Leaderboard / Geek Points
- Link to signup site (`SIGNUP_LINK_BASE_URL`)
- **Access Code:** `{otp_code}` (styled prominently)
- Sign-off: Jamie
- PS: reply for feedback
- Signature: `<img src="{BADGE_URL}" alt="GOB Alpha" width="300" />`

**Badge URLs (after deploy):**

- Production: `https://www.geekedoutbasketball.com/static/images/gob-alpha-badge.png`
- Staging: `https://gob-test.netlify.app/static/images/gob-alpha-badge.png` (confirm Netlify URL)

Asset path in repo: `FrontEnd/static/images/gob-alpha-badge.png` (300×171 PNG).

### 2. Waitlist (“coming soon”)

- Acknowledge request
- No code; explain capacity / code coming soon
- Same signature/badge optional

### 3. Not via Resend

- Password reset — existing SendGrid flow when user already registered (`used: true` on their OTP or `users` doc exists).

---

## Environment variables

| Variable | Staging | Production | Notes |
|----------|---------|------------|-------|
| `MONGO_DB_NAME` | `gob-staging` | `gob` | Existing |
| `RESEND_API_KEY` | Required | Required | Same Resend account OK |
| `ALPHA_EMAIL_FROM` | `jamie@geekedoutgames.com` | Same | New; or reuse `FEEDBACK_FROM_EMAIL` |
| `SIGNUP_LINK_BASE_URL` | Staging Netlify signup URL | `https://www.geekedoutbasketball.com/signup.html` | New |
| `ALPHA_BADGE_URL` | Optional override | Optional override | Default from `SIGNUP_LINK_BASE_URL` origin + `/static/images/gob-alpha-badge.png` |
| `SENDGRID_*`, `RESET_*` | Unchanged | Unchanged | Password reset only |

**Railway checklist (staging first):**

1. Resend dashboard: domain verified, API key created
2. Set `RESEND_API_KEY`, `ALPHA_EMAIL_FROM`, `SIGNUP_LINK_BASE_URL` on staging service
3. Deploy frontend so badge PNG is live at static URL
4. Repeat for production before backfill

Update `_documentation_master/ENV_VARIABLES.md` during Phase 7.

---

## Implementation phases

### Phase 0 — Prerequisites (James + deploy badge)

- [ ] Verify `geekedoutgames.com` (or From domain) in Resend
- [ ] Commit & deploy `FrontEnd/static/images/gob-alpha-badge.png`
- [ ] Confirm badge loads in browser at production/staging static URL
- [ ] Add Resend env vars to Railway **staging**

### Phase 1 — Schema & migration scripts

**Files (new):**

- `scripts/migrate_alpha_otp_sent_fields.py` — backfill `sent: false` on all OTPs missing field
- `scripts/sync_sent_otps_from_markdown.py` — read `used_otp_codes.md`, set `sent: true` on matching `otp_code` (dry-run / execute)

**Run order:**

1. Staging: migrate fields → sync from markdown → verify counts
2. Production: same, before backfill

**Tests:** Unit tests for markdown parser (codes only, ignore section headers like “April 26 Codes Emailed”).

### Phase 2 — Email & OTP helpers

**Files:**

- Extend `BackEnd/utils/resend_sender.py` or add `BackEnd/utils/alpha_access_email.py`:
  - `send_alpha_welcome_email(email, otp_code) -> bool`
  - `send_alpha_waitlist_email(email) -> bool`
  - HTML builders with escaped user content
- Add `BackEnd/utils/alpha_otp_service.py` (or similar):
  - `count_available_otps() -> int`
  - `find_otp_for_email(email) -> Optional[doc]` — existing reservation for resend
  - `claim_otp_for_email(email) -> Optional[str]` — atomic pick + set `sent`; **rollback on send failure**
  - `release_otp_claim(otp_code)` — rollback helper

**Claim / rollback flow (Q13-B):**

```
1. claim_otp_for_email(email)  → sets sent=true, sent_to_email, sent_at
2. resend send                 → if fail: release_otp_claim(otp_code); status=failed
3. on success                  → update access_code_requests
```

Use Mongo `findOneAndUpdate` on `alpha_otps` with filter `{ used: false, sent: false }` for atomic claim.

### Phase 3 — Live API path (staging)

**File:** `BackEnd/api/auth_routes.py` — `request_access_code`

**Logic:**

```
email = normalize(body.email)

if per_email_rate_limit_exceeded(email): return 429

if users.find(email):
    trigger reset-request internally (SendGrid); return 200 generic message

existing = access_code_requests.find pending/sent for email
if existing.sent and otp still used=false:
    resend welcome with same otp_code; return 200

if count_available_otps() == 0:
    insert/update waitlisted; send waitlist email; return 200

otp = claim → send welcome → on fail rollback → on success update request sent
return 200 (same user-facing message as today)
```

**Also:**

- Per-email rate limit helper (e.g. in-memory or Mongo sliding window; 3 requests/email/hour suggested)
- Wire tests in `tests/test_alpha_access_email.py` / extend auth route tests

**Deploy:** staging Railway + staging frontend URL in `SIGNUP_LINK_BASE_URL`.

### Phase 4 — Staging validation

James provides test email(s), **one at a time**:

| # | Test | Expected |
|---|------|----------|
| 1 | New request, capacity available | Welcome email, OTP works on signup, `sent` then `used` |
| 2 | Repeat request before signup | Same code resent |
| 3 | Request after signup with same email | Reset email (SendGrid), no new OTP |
| 4 | Drain staging OTPs (or mock count=0) | Waitlist email, `status: waitlisted` |
| 5 | Badge image visible in email clients | Loads from static URL |

Fix issues on develop → redeploy staging until green.

### Phase 5 — Production backfill

**File:** `scripts/backfill_access_code_emails.py`

```
--dry-run   List: email, action (send/skip), otp_code, skip reason
--execute   Send + update DB (respect Resend 100/day if on free tier)
```

**Algorithm:**

1. Load all `access_code_requests` where `status: pending` (or all 36 if none marked yet)
2. Group by `email`; keep **oldest** `created_at`
3. Skip if `users` contains email → `skipped` / `already_registered`
4. Skip if no OTP capacity → log (do not partial-send without approval)
5. For each remainder: claim OTP → send welcome → rollback on failure
6. Update request doc: `sent`, `otp_code`, `sent_at`

**Approval:** James reviews `--dry-run` output before `--execute`.

### Phase 6 — Production live path

- Merge develop → main (or release branch)
- Set production Railway env vars
- Deploy backend + confirm frontend badge URL
- Monitor first live requests

### Phase 7 — Documentation

- [ ] Update `_documentation_master/ENV_VARIABLES.md`
- [ ] Update `_documentation_master/00_General_Systems/User_Account_System.md` (request-access-code flow)
- [ ] Optional: note in `Resend_Project_Brief.md` that implementation is complete

---

## Out of scope (v1)

- Personal recap / broadcast emails
- Auto-fulfill waitlist when new OTPs are generated
- Migrating password reset from SendGrid to Resend
- Runtime reads of `used_otp_codes.md` (migration script only)
- Resend Audiences / Marketing Broadcasts

---

## File checklist (implementation)

| File | Action |
|------|--------|
| `FrontEnd/static/images/gob-alpha-badge.png` | Done — deploy with frontend |
| `BackEnd/utils/alpha_otp_service.py` | New |
| `BackEnd/utils/resend_sender.py` or `alpha_access_email.py` | Extend |
| `BackEnd/api/auth_routes.py` | Extend `request_access_code` |
| `scripts/migrate_alpha_otp_sent_fields.py` | New |
| `scripts/sync_sent_otps_from_markdown.py` | New |
| `scripts/backfill_access_code_emails.py` | New |
| `tests/test_alpha_access_email.py` | New |
| `_documentation_master/ENV_VARIABLES.md` | Update (Phase 7) |

---

## Test plan summary

**Automated:**

- OTP claim + rollback on failed send
- Capacity counting
- De-dupe logic (oldest wins)
- Markdown sync (codes extracted, sections ignored)
- Per-email rate limit
- Repeat request resends same OTP

**Manual (staging → prod):**

- End-to-end email delivery and signup
- Badge renders in Gmail / Apple Mail
- Backfill dry-run review before execute

---

## Order of operations (summary)

```
Phase 0  Resend domain + env + deploy badge
    ↓
Phase 1  Schema migration (staging → prod)
    ↓
Phase 2  Email + OTP helpers
    ↓
Phase 3  Live API on staging
    ↓
Phase 4  James tests one user at a time on staging
    ↓
Phase 5  Production backfill (36 docs, dry-run first)
    ↓
Phase 6  Production live path
    ↓
Phase 7  Docs
```

---

## Open items during implementation

- Confirm exact staging Netlify URL for `SIGNUP_LINK_BASE_URL` and badge
- Final “coming soon” email copy (welcome copy from manual email is reference)
- Per-email rate limit numeric cap (default proposal: **3/hour**)
- Whether backfill marks duplicate request docs as `skipped` or deletes them
