# Alpha Access Runbook

Manual grants for the alpha list. Default product behavior is **request = join the list** and send the waitlist confirmation; a code is emailed only when you grant one (or when `ALPHA_AUTO_SEND_CODES=true`, which is the legacy auto-send path and should stay off).

Authorization and connection rules are the same as [`Environment_Operations.md`](Environment_Operations.md). Dry-run unless you pass `--apply`. Production writes need process-only `GOB_DB_ACCESS=write`. Never put that variable in a dotenv file.

Signup link to send with a code:

```text
https://geekedoutbasketball.com/signup.html?code=CODE
```

The page uppercases the code and auto-runs Continue.

Use `PYTHONPATH=. ./.venv/bin/python` from the repo root.

---

## Flag

| Variable | Default | Effect |
|---|---|---|
| `ALPHA_AUTO_SEND_CODES` | `false` | `false`: `POST /api/auth/request-access-code` upserts `alpha_access_requests` as `pending` and sends the waitlist confirmation (no code). `true`: emails a pool code when one is free, or the waitlist template when not. |

Keep this `false` on staging and production unless you are deliberately using the old auto-send path.

---

## List pending

Staging:

```bash
PYTHONPATH=. ./.venv/bin/python scripts/grant_alpha_access.py --db gob-staging --list-pending
```

Production (read-only):

```bash
GOB_DB_ACCESS=read \
MONGO_URI="$PROD_MONGO_URI" \
MONGO_DB_NAME=gob \
ENVIRONMENT=production \
PYTHONPATH=. ./.venv/bin/python scripts/grant_alpha_access.py --db gob --list-pending
```

Prints `pending` rows from `alpha_access_requests` (email, source, request_count, first/last requested).

---

## Grant a pool code

Claims one unused, unsent pool code (`sent=false`), emails the welcome template, and marks the queue doc `granted`.

Dry-run, then apply. Repeat `--email` for more than one address.

```bash
PYTHONPATH=. ./.venv/bin/python scripts/grant_alpha_access.py \
  --db gob-staging --email coach@example.com --granted-by jamie

PYTHONPATH=. ./.venv/bin/python scripts/grant_alpha_access.py \
  --db gob-staging --email coach@example.com --granted-by jamie --apply
```

Production apply uses `GOB_DB_ACCESS=write` and `--db gob`, same URI pattern as other production writes. Unset `PROD_MONGO_URI` and `GOB_DB_ACCESS` when finished.

If the welcome email fails, the code is released back to the pool. Skip if the email is already `granted` or `registered`.

Share the signup link with `?code=` as well as (or instead of) relying on the email body.

---

## Create a creator / vanity code

Created codes have `sent=true` so `grant_alpha_access.py` never hands them out from the pool. `max_uses` defaults to 1.

```bash
PYTHONPATH=. ./.venv/bin/python scripts/create_alpha_code.py \
  --db gob-staging --code HOOPSGUY --allocated-to creator:hoopsguy

PYTHONPATH=. ./.venv/bin/python scripts/create_alpha_code.py \
  --db gob-staging --code HOOPSGUY --allocated-to creator:hoopsguy --apply
```

Generate N random codes for one creator:

```bash
PYTHONPATH=. ./.venv/bin/python scripts/create_alpha_code.py \
  --db gob-staging --generate 5 --allocated-to creator:hoopsguy --apply
```

Send `https://geekedoutbasketball.com/signup.html?code=HOOPSGUY` (or the generated code). Raising `max_uses` later is out of scope for this runbook.

---

## Related

- [`User_Account_System.md`](../02_User_Account_Systems/User_Account_System.md)
- [`Database_System.md`](../00_Data_Systems/Database_System.md)
- [`Resend_System.md`](Resend_System.md)
- `scripts/migrate_alpha_otp_use_limits.py` backfills `max_uses` / `use_count` / `active` (staging already applied; do not run on prod until that migrate is explicitly approved)
