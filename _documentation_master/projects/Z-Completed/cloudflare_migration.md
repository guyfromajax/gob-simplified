# Cloudflare DNS Migration — Work Plan

**Domain:** `geekedoutgames.com`  
**Registrar:** Namecheap (stays)  
**DNS:** Namecheap BasicDNS → **Cloudflare**  
**Status:** Planned — study before executing  
**Blocks:** Resend domain verification (Namecheap free Email Forwarding cannot add any MX records, even on subdomains)

---

## Why

Namecheap confirmed: **no MX records are allowed while Free Email Forwarding is enabled** — including subdomain `send` for Resend.

Switching to Custom MX broke `jamie@` receiving (`554 Relay access denied`). Reverting to Email Forwarding restored receive.

**Cloudflare DNS** gives full record control. **Cloudflare Email Routing** (free) replaces Namecheap forwarding for `jamie@` → Gmail without the MX lock-in.

---

## Goal

1. Keep **`jamie@geekedoutgames.com` receiving** at `games.geekedout@gmail.com`
2. Keep **Gmail “Send mail as”** working (unchanged — uses Gmail SMTP, not MX)
3. Enable **Resend DNS** (MX on `send`, DKIM, SPF) OR **SendGrid-only** path — see [Email provider after migration](#email-provider-after-migration)
4. Preserve **website**, **SendGrid**, and any other existing DNS

---

## What changes vs stays

| Item | Action |
|------|--------|
| Domain registration | Stays at Namecheap |
| Nameservers | Change to Cloudflare (`*.ns.cloudflare.com`) |
| Email forwarding | Move from Namecheap → **Cloudflare Email Routing** |
| Host / Mail records | Recreate in Cloudflare DNS |
| Gmail “Send mail as” | No change |

---

## Current DNS (export from Namecheap before starting)

Document everything in **Advanced DNS** before touching nameservers.

### Host Records (known)

| Type | Host | Value | Purpose |
|------|------|-------|---------|
| CNAME | `em8559` | `u59583713.wl214.sendgrid.net` | SendGrid link/branding |
| CNAME | `www` | `geekedoutgames.com` | www → apex |
| TXT | `resend._domainkey` | `(DKIM key from Resend)` | Resend DKIM |
| TXT | `send` | `v=spf1 include:amazonses.com ~all` | Resend SPF |

### Mail Settings (Namecheap — Email Forwarding mode)

| Type | Host | Value | Priority |
|------|------|-------|----------|
| MX | `@` | `eforward1.registrar-servers.com` | 10 |
| MX | `@` | `eforward2.registrar-servers.com` | 10 |
| MX | `@` | `eforward3.registrar-servers.com` | 10 |
| MX | `@` | `eforward4.registrar-servers.com` | 15 |
| MX | `@` | `eforward5.registrar-servers.com` | 20 |
| TXT | `@` | `v=spf1 include:spf.efwd.registrar-servers.com ~all` | — |

**Note:** No root `A` record was visible in public DNS at time of audit. Confirm where `geekedoutgames.com` should resolve (hosting, redirect, etc.) before migration.

### Email Forwarding rule (Namecheap dashboard)

| Alias | Forwards to |
|-------|-------------|
| `jamie` | `games.geekedout@gmail.com` |

---

## Risks

| Risk | Mitigation |
|------|------------|
| Incoming mail breaks | Set up Cloudflare Email Routing **before** switching NS |
| Website down | Inventory all records; confirm apex `A`/`CNAME`/redirect |
| SendGrid auth breaks | Copy `em8559` CNAME exactly; re-verify in SendGrid if needed |
| Propagation gap | Configure Cloudflare fully first; switch NS only when zone is ready |
| Wrong record copied | Screenshot Namecheap Advanced DNS + Email Forwarding tab |

**Rollback:** Point nameservers back to Namecheap (`dns1.registrar-servers.com`, `dns2.registrar-servers.com`). Propagation may take up to 24–48 hours.

---

## Execution plan

### Phase 0 — Prep (do not switch NS yet)

- [ ] Screenshot **all** Namecheap Advanced DNS (Host Records + Mail Settings)
- [ ] Screenshot **Email Forwarding** tab (`jamie` → Gmail)
- [ ] Confirm where **website** should point (apex + www)
- [ ] Create free **Cloudflare** account if needed
- [ ] Pick low-traffic window (evening/weekend)

### Phase 1 — Add domain to Cloudflare

- [ ] **Add site** → `geekedoutgames.com` → Free plan
- [ ] Let Cloudflare **scan/import** existing records
- [ ] Compare imported records against Phase 0 export; fix gaps

### Phase 2 — Cloudflare Email Routing (before NS switch)

- [ ] Enable **Email Routing** for `geekedoutgames.com`
- [ ] Add route: `jamie@geekedoutgames.com` → `games.geekedout@gmail.com`
- [ ] Cloudflare will add its own MX/TXT records — **do not** add Namecheap `eforward*` records
- [ ] Complete any **destination verification** Cloudflare requires (email to Gmail)

### Phase 3 — Recreate app DNS in Cloudflare

Copy from export; adjust as noted:

- [ ] `www` CNAME (or update if site host differs)
- [ ] Apex `A` / `CNAME` / redirect — **confirm target first**
- [ ] `em8559` CNAME → SendGrid
- [ ] `resend._domainkey` TXT → Resend DKIM
- [ ] `send` TXT → Resend SPF
- [ ] **Resend MX:** host `send`, priority `10`, value `feedback-smtp.us-east-1.amazonses.com`

Set all records to **DNS only** (grey cloud) unless you intentionally want Cloudflare proxy on web records.

### Phase 4 — Switch nameservers

- [ ] Cloudflare shows assigned NS (e.g. `ada.ns.cloudflare.com`, `bob.ns.cloudflare.com`)
- [ ] Namecheap → **Domain** → **Nameservers** → Custom DNS → paste Cloudflare NS
- [ ] Save; wait for Cloudflare to show **Active**
- [ ] **Do not** change Mail Settings on Namecheap after switch — DNS is now on Cloudflare

### Phase 5 — Verify

- [ ] **Receive:** Send test email **to** `jamie@geekedoutgames.com` → arrives in Gmail
- [ ] **Send as:** Send test **from** `jamie@` via Gmail → delivers
- [ ] **Website:** `geekedoutgames.com` and `www` load correctly
- [ ] **Resend:** Dashboard → **Verify DNS** on `geekedoutgames.com` (all green)
- [ ] **SendGrid:** Send password reset test on staging (if applicable)

### Phase 6 — Cleanup

- [ ] Disable/remove Namecheap Email Forwarding (optional once CF routing confirmed)
- [ ] Update this doc status to **Complete**
- [ ] Resume [Resend_Project_Work_Plan.md](Resend_Project_Work_Plan.md) Phase 0 (Railway env vars, badge deploy)

---

## Email provider after migration

Once Cloudflare DNS is live, either path works:

| Path | Pros | Cons |
|------|------|------|
| **A — Resend** (original plan) | Resend free tier; already partially configured | Two email vendors (SendGrid + Resend) |
| **B — SendGrid only** | One vendor; already used for password reset | Resend work abandoned; extend `email_sender.py` |

**Long-term scale recommendation:** Cloudflare DNS + **one** outbound provider. If staying on two vendors short-term, Resend is fine after this migration.

---

## Quick reference — Resend records in Cloudflare

| Type | Name | Content | Priority |
|------|------|---------|----------|
| TXT | `resend._domainkey` | `(from Resend dashboard)` | — |
| TXT | `send` | `v=spf1 include:amazonses.com ~all` | — |
| MX | `send` | `feedback-smtp.us-east-1.amazonses.com` | 10 |

---

## When to ask for help

Stop and ask before switching NS if:

- Imported Cloudflare records don’t match your export
- Email Routing verification fails
- You’re unsure where the website apex should point
- Resend verify fails after 30+ minutes post-migration
