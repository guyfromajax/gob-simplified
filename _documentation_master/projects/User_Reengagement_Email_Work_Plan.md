# User Re-engagement Email — Work Plan

**Status:** Draft (script is dry-run-ready; needs final copy + mailing address before execute)
**Vendor:** Resend (same account as alpha access codes)
**Related:** [Resend_Project_Work_Plan.md](Resend_Project_Work_Plan.md) · [[project_resend_alpha_access]]

---

## Objective

One-time "come back and play" email to **existing registered users** (`users` collection), **excluding anyone we just emailed** in the alpha-code push, plus unsubscribes.

Audience snapshot (prod, 2026-06-14): 55 users, 3 overlap with recent alpha sends → ~52 after exclusion.

---

## Audience & exclusion (suppression)

Recipient = user in `users` with a non-empty `email`, **minus** any of:

| Suppress if… | Source |
|---|---|
| Got an alpha welcome email recently (default 7 days) | `access_code_requests` `status:sent`, `sent_at >= cutoff` |
| Has unsubscribed | `email_unsubscribes` collection |
| Already received this campaign | `reengagement_sends` collection (`campaign` field) — makes re-runs idempotent |

---

## Compliance (CAN-SPAM) — decided: include unsubscribe + address

- **Unsubscribe link** in every email → `GET /api/email/unsubscribe?e=<email>&t=<hmac>`; records to `email_unsubscribes`, returns a confirmation page. HMAC token (no per-user stored token).
- **List-Unsubscribe** + **List-Unsubscribe-Post** headers (RFC 8058) for one-click unsubscribe in Gmail/Apple Mail (`POST` to same endpoint).
- **Physical mailing address** in footer — from env `GOB_MAILING_ADDRESS` (**must be set before execute**).

---

## New files / changes

| File | Action |
|---|---|
| `BackEnd/utils/email_suppression.py` | New — HMAC token, record/verify unsubscribe, suppression sets |
| `BackEnd/utils/reengagement_email.py` | New — HTML builder (copy + unsubscribe + address) + sender |
| `BackEnd/utils/resend_sender.py` | Extend `send_resend_html_email` with optional `headers` |
| `BackEnd/api/email_routes.py` | New — `GET`/`POST /api/email/unsubscribe` |
| `BackEnd/api/api.py` | Register `email_router` |
| `scripts/send_user_reengagement_email.py` | New — `--dry-run`/`--execute`/`--db`, suppression, `--limit` batching |

New collections (created on first write): `email_unsubscribes`, `reengagement_sends`.

---

## Env vars

| Variable | Default | Notes |
|---|---|---|
| `EMAIL_UNSUB_SECRET` | falls back to `JWT_SECRET_KEY` | HMAC signing for unsubscribe tokens |
| `UNSUBSCRIBE_LINK_BASE_URL` | `https://www.geekedoutbasketball.com` | Origin for the unsubscribe link (must reach `/api`) |
| `GOB_MAILING_ADDRESS` | _(placeholder — REQUIRED before execute)_ | CAN-SPAM physical address |
| `RESEND_API_KEY`, `ALPHA_EMAIL_FROM` | (existing) | Reused |

---

## Run order

1. Set `GOB_MAILING_ADDRESS` (+ finalize copy in `reengagement_email.py`).
2. Deploy backend (so the unsubscribe endpoint is live) before any send.
3. `--dry-run --db production` → review recipient/suppression counts.
4. `--execute --db production --confirm-production-write` (use `--limit` if ever > 100/day on Resend free tier; 52 is fine in one batch).

---

## Open items

- Final email copy (subject + body) — placeholder in `reengagement_email.py`.
- Physical mailing address value.
- Confirm `EMAIL_UNSUB_SECRET` is stable across deploys (else old unsubscribe links break — fallback to `JWT_SECRET_KEY` is stable).
