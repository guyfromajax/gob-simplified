# Marketing Pixels Setup Guide

Add Facebook/Meta, X (Twitter), and TikTok pixels via Google Tag Manager. **No code changes required** — GTM is already on all pages.

---

## Prerequisites

- GTM container created and added to site (GTM-K69GQK3D)
- Pixel IDs from each platform (you'll get these in Steps 1–3)

---

## Step 1 — Facebook / Meta Pixel

### 1.1 Create the pixel

1. Go to [Meta Events Manager](https://business.facebook.com/events_manager)
2. **Data sources** → **Add new data source** → **Web**
3. Choose **Meta Pixel** → **Connect**
4. Name it (e.g. "Geeked Out Basketball") → **Create pixel**
5. Copy the **Pixel ID** (numeric, e.g. `1234567890123456`)

### 1.2 Add to GTM

1. In GTM: **Tags** → **New** → **Tag Configuration**
2. Search for **"Facebook Pixel"** (built-in tag type)
3. **Pixel ID:** Your pixel ID
4. **Trigger:** Start with **All Pages** (Initialization)
5. Save as `Meta Pixel - Base`
6. **Submit** (or add more tags first — see 1.3)

### 1.3 Conversion events (optional)

To send `signup` and game completions to Meta as conversions:

1. **Tags** → **New** → **Tag Configuration** → **Facebook Pixel**
2. **Pixel ID:** Same as base
3. **Event Name:** `CompleteRegistration` (for signup) or `Lead` (alternative)
4. **Trigger:** **Custom Event** → Event name = `signup`
5. Save as `Meta Pixel - Signup`
6. Repeat for `login`, `single_game_completed`, `tournament_game_completed`, `franchise_game_completed` if desired (use event names like `Purchase` or custom)

---

## Step 2 — X (Twitter) Pixel

### 2.1 Create the pixel

1. Go to [X Ads Manager](https://ads.x.com/) → **Tools** → **Conversion tracking**
2. **Create a new website tag**
3. Name it (e.g. "Geeked Out Basketball")
4. Copy the **Pixel ID** (e.g. `o0000`)

### 2.2 Add to GTM

1. In GTM: **Tags** → **New** → **Tag Configuration**
2. Search for **"X (Twitter) Pixel"** or **"Twitter Universal Website Tag"**
3. If available: use built-in tag, add Pixel ID
4. If not: use **Custom HTML** tag:
   - Paste the pixel script X provides (replace `pixel_id` with your ID)
   - Trigger: **All Pages**
5. Save as `X Pixel - Base`

### 2.3 Conversion events (optional)

- X conversions typically fire on custom events
- Add **Custom HTML** or X event tags that trigger on `signup`, `login`, game completion events
- Use the same Custom Event triggers as GA4 (event names: `signup`, `login`, etc.)

---

## Step 3 — TikTok Pixel

### 3.1 Create the pixel

1. Go to [TikTok Events Manager](https://ads.tiktok.com/i18n/events_manager)
2. **Manage** → **Web Events** → **Set up web events**
3. **Manual setup** → **Install with a website builder/code** → **Google Tag Manager**
4. Copy the **Pixel ID** (e.g. `C2X1Y2Z3A4B5C6D7E8F9G0`)

### 3.2 Add to GTM

1. In GTM: **Tags** → **New** → **Tag Configuration**
2. Search for **"TikTok"** — there is a built-in **TikTok Pixel** tag
3. **Pixel ID:** Your TikTok Pixel ID
4. **Trigger:** **All Pages**
5. Save as `TikTok Pixel - Base`

### 3.3 Conversion events (optional)

1. **Tags** → **New** → **TikTok Pixel**
2. **Pixel ID:** Same as base
3. **Event:** Choose `CompleteRegistration` (signup) or `SubmitForm`
4. **Trigger:** **Custom Event** → `signup`
5. Save as `TikTok Pixel - Signup`
6. Add similar tags for login, game completions if desired

---

## Step 4 — Verify

### Per platform

- **Meta:** [Meta Pixel Helper](https://chrome.google.com/webstore/detail/meta-pixel-helper) Chrome extension
- **X:** X Ads Manager → Tools → Conversion tracking → Test your tag
- **TikTok:** TikTok Events Manager → Test events

### In GTM Preview

1. GTM → **Preview** → enter your site URL
2. Navigate, sign up, play a game
3. In GTM debug panel, confirm pixel tags fire

---

## dataLayer events (for conversion triggers)

These events are already pushed by `analytics.js` — use them as Custom Event triggers:

| Event name                     | When it fires              |
|--------------------------------|----------------------------|
| `signup`                       | User completes registration |
| `login`                        | User logs in               |
| `single_game_started`          | User starts a single game  |
| `single_game_completed`        | User completes single game |
| `tournament_entered`           | User opens tournament      |
| `tournament_game_started`      | User starts tournament game|
| `tournament_game_completed`    | User completes tournament game |
| `franchise_entered`            | User opens franchise       |
| `franchise_game_started`       | User starts franchise game |
| `franchise_game_completed`     | User completes franchise game |
| `quarter_advance`              | User advances quarter (has `action` param) |

---

## Checklist

- [ ] Meta Pixel: Created, added to GTM, fires on All Pages
- [ ] Meta Pixel: Optional conversion tags for signup/login/game completions
- [ ] X Pixel: Created, added to GTM, fires on All Pages
- [ ] X Pixel: Optional conversion tags
- [ ] TikTok Pixel: Created, added to GTM, fires on All Pages
- [ ] TikTok Pixel: Optional conversion tags for signup/game completions
- [ ] All pixels verified with platform tools or GTM Preview
- [ ] GTM container published
