# Step 9 — Uptime Monitoring Walkthrough

A concise, first-time-friendly guide to basic uptime monitoring and alerts for alpha.

---

## 1. Pick an uptime service (≈5 min)

- **Recommended:** [UptimeRobot](https://uptimerobot.com) — free tier: 50 monitors, 5‑min checks, email alerts.
- **Alternatives:** Pingdom, Better Uptime (if you prefer Slack-first).
- **Action:** Sign up at uptimerobot.com (free account).

---

## 2. Add two monitors (frontend + API)

You need **two checks**: one for the site users see, one for the API your app calls.

| Monitor | URL to check | Purpose |
|--------|----------------|--------|
| **Frontend** | `https://www.geekedoutbasketball.com` (or your Netlify app URL) | Is the main site up? |
| **API** | `https://api.geekedoutbasketball.com/health` (or your Railway API URL + `/health`) | Is the backend up? |

**Important:** Use the `/health` path for the API. The backend exposes `GET /health` for exactly this; using the root URL can cause false downs (redirects, 404s, or platform quirks).

**In UptimeRobot:**

1. **Dashboard → Add New Monitor**
2. **Monitor Type:** HTTP(s)
3. **Friendly Name:** e.g. `GOB Frontend` / `GOB API`
4. **URL:** paste the URL above (use HTTPS)
5. **Monitoring Interval:** 5 minutes (fine for alpha)
6. **Alert Contacts:** add your email (see step 3)
7. Save. Repeat for the second URL.

**Tip:** The backend has `GET /health` (no auth). Use `https://api.geekedoutbasketball.com/health` — avoid the root or heavy endpoints.

---

## 3. Set up alert contacts

- **Dashboard → My Settings → Alert Contacts**
- **Add Alert Contact:** Email, enter your address, verify (they send a confirmation link).
- **Optional:** Add Slack (or another channel) if you want alerts there too.
- Attach these contacts to both monitors when creating/editing them.

---

## 4. Configure when to alert (avoid noise)

- When editing a monitor, look for **Alert Settings** / **Sensitivity**.
- **Recommendation:** “Alert after **2 consecutive failures**” (so one blip doesn’t spam you).
- Keep **5-minute** check interval for alpha.

---

## 5. Verify it works (important)

1. **Check status:** In UptimeRobot, confirm both monitors show “Up” (green) after a few minutes.
2. **Test alerts:** Temporarily use a wrong URL for one monitor (e.g. `https://api.geekedoutbasketball.com/wrong-path-404`) or pause the service if you can; wait for 2 checks to fail and confirm you get an email (and Slack if configured).
3. **Fix and confirm recovery:** Restore the correct URL; confirm you get a “back up” / “recovered” email so you know when things are healthy again.

---

## 6. "Possible IP Allowlist Issue" and API showing red

If the **API** monitor shows down (red) while the **frontend** (www) is up, try this order:

1. **Use the health URL**  
   Set the API monitor URL to `https://api.geekedoutbasketball.com/health` (see table in step 2). The app exposes `GET /health` for uptime checks; the root or other paths can behave differently and cause false downs.

2. **IP allowlist only if you have a firewall/proxy**  
   UptimeRobot’s message appears when checks fail. You only need to allowlist their IPs if something in front of your API blocks by IP, e.g.:
   - **Cloudflare** (e.g. "Under Attack" mode or IP Access Rules)
   - **Another WAF or firewall** in front of Railway
   - **Railway** does not restrict incoming traffic by IP by default, so if the API is only on Railway (no proxy), allowlisting usually isn’t the fix.

   **If you do use a firewall/proxy:**  
   - Get the current list: [UptimeRobot Locations and IPs](https://uptimerobot.com/help/locations) (or [JSON](https://api.uptimerobot.com/meta/ips), [IPv4 .txt](https://cdn.uptimerobot.com/api/IPv4.txt)).  
   - Add those IPs to your **allowlist** (not blocklist) for HTTP/HTTPS to your API host.

3. **Confirm from your side**  
   Open `https://api.geekedoutbasketball.com/health` in a browser or run `curl -s -o /dev/null -w "%{http_code}" https://api.geekedoutbasketball.com/health`. If you get `200`, the API is up and the monitor URL or allowlist is the likely cause of the red bar.

---

## 7. Optional later: performance and DB

- **Performance:** Use UptimeRobot’s response-time graphs, or Railway/Netlify logs, to spot slow requests. You can add a separate “keyword” monitor that fails if a health endpoint doesn’t return within a few seconds.
- **Database:** MongoDB Atlas (free tier) has its own monitoring and alerts; enable those in the Atlas UI for DB-specific issues.

---

## Checklist (matches alpha launch plan Step 9)

- [ ] Uptime service chosen and account created (e.g. UptimeRobot)
- [ ] Monitor 1: Frontend URL added, 5‑min interval, alert contact attached
- [ ] Monitor 2: API URL added (use `…/health`), 5‑min interval, alert contact attached
- [ ] Alert threshold: 2 consecutive failures
- [ ] Email (and optional Slack) verified
- [ ] Test: triggered one alert and one “recovered” notification

Once these are done, Step 9 is complete for alpha. You can add performance and DB monitoring later as needed.
