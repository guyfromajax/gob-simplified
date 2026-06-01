# Resend System

Transactional HTML email via [Resend](https://resend.com) for alpha access and in-app feedback. No queue — synchronous send with logging; failures are non-fatal to the user flow.

---

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `RESEND_API_KEY` | API bearer token | unset → skip send, log warning |
| `ALPHA_EMAIL_FROM` | From address for alpha welcome | `FEEDBACK_FROM_EMAIL` |
| `FEEDBACK_FROM_EMAIL` | From for feedback notifications | `jamie@geekedoutgames.com` |
| `FEEDBACK_TO_EMAIL` | Feedback recipient | `jamie@geekedoutgames.com` |
| `SIGNUP_LINK_BASE_URL` | Link in alpha welcome body | `https://www.geekedoutbasketball.com/signup.html` |
| `ALPHA_BADGE_URL` | Optional inline image override | derived from signup origin + `/images/gob-alpha-badge.png` |

Set `RESEND_API_KEY` in Railway/Netlify env for staging and production.

---

## Code paths

| Flow | Module | Behavior |
|---|---|---|
| Generic HTML send | [`BackEnd/utils/resend_sender.py`](../../BackEnd/utils/resend_sender.py) | `send_resend_html_email()` → `POST https://api.resend.com/emails` (10s timeout) |
| Alpha welcome OTP | [`BackEnd/utils/alpha_access_email.py`](../../BackEnd/utils/alpha_access_email.py) | `build_alpha_welcome_html`, `send_alpha_welcome_email` |
| Feedback form | [`BackEnd/utils/resend_sender.py`](../../BackEnd/utils/resend_sender.py) | `send_feedback_email()` — escaped HTML body + context fields |
| Auth / alpha routes | [`BackEnd/api/auth_routes.py`](../../BackEnd/api/auth_routes.py) | wires welcome send after code issuance |

**Failure handling:** missing key or non-2xx response → `False` + `logger.warning` / `logger.exception`; callers should not block UX on email success.

---

## Security

- User-supplied feedback fields are HTML-escaped before embedding.
- Do not commit API keys; rotate via Resend dashboard if leaked.
