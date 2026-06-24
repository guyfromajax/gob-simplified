# GOB Auth — Branded "Front Door" Handoff

**Goal:** bring login / signup / reset-password into the GOB brand without losing the calm, uncluttered feel. Approachability comes from *restraint* (one task, lots of space), not from being light/generic. Auth is a **Front Door** surface — a peer of `homepage-v3.html` and `mode-select.html`, not a data-dense command center.

**The big win:** all three auth screens already share **one stylesheet, `/auth.css`, and identical class names** (`.auth-container`, `.auth-title`, `.form-group`, `.auth-button`, `.auth-footer`, `.back-link`, …). Restyle that one file and **every auth screen updates at once**. The new `auth.css` in this folder is a drop-in replacement — no HTML changes required to adopt the look.

---

## 1. Drop-in: replace the stylesheet

Replace `FrontEnd/static/auth.css` with `Auth Redesign/auth.css` from this project. That alone rebrands login, signup, and reset-password. Class names are unchanged.

Then do the two small, optional polish edits below (logo + arrow on back link). Everything else is free.

---

## 2. Token map (legacy → brand)

| Thing | Legacy value | Brand value |
|---|---|---|
| Page background | `#f5f5f5` (light) | `#0b0d14` + navy `#27408E` atmosphere glow |
| Card surface | `#fff` | `rgba(14,16,24,0.94)` + soft white border, 18px radius |
| Action button | `#ff9800` | `#F79420` (real brand orange, non-gating action color) |
| Button text | `#fff` | `#15181f` (ink on orange) |
| Button shape | 6px radius, no border | 10px radius, `1px rgba(255,255,255,0.28)`, inset highlight (universal GOB shape) |
| Input border / focus | grey / **blue-ish** ring | `rgba(255,255,255,0.14)` / **orange** ring `rgba(247,148,32,0.18)` |
| Display font | `Bebas Neue` | `Bebas Neue Pro`, `Bebas Neue` fallback |
| Title color | `#333` | `#fff` |
| Error / success | light red / green boxes | same semantics, dark translucent fills |

**Note on button color:** orange is correct here. Per the style guide, green `#34EC27` is reserved for *gating* actions that advance game state. Logging in / signing up are **non-gating** → orange `#F79420`. Don't switch auth buttons to green.

---

## 3. Front-door rules (what to keep vs avoid)

**Keep (this is the "less intimidating" quality):**
- One card, one task, generous whitespace.
- No tabs, no nested panels, no dense data.
- Brand atmosphere stays subtle: navy glow + faint diagonal banding only.

**Avoid:**
- Don't add the FCC shell container, diagonal-heavy textures, or stat surfaces here.
- Don't introduce a second accent color. Orange is the only action color.
- Don't use green anywhere on auth.
- Don't reintroduce the blue focus ring — focus is always orange.

---

## 4. Two optional HTML polish edits

These are the only HTML touches, and both are cosmetic. Styles already ship in the new `auth.css`.

**a) Real logo instead of the text placeholder.** Add one line directly *above* `<div class="auth-container">` on each auth page:
```html
<img class="auth-logo" src="/images/<your-logo>.png" alt="Geeked Out Basketball">
```
(The mock used a styled text wordmark as a stand-in. Use the real logo asset — there's already brand art under `/images/`.) If the element is absent, nothing breaks.

**b) Left arrow on the Back link** (style-guide Back/Return treatment). The link already exists on login + reset; just prepend an arrow to the copy:
```html
<a href="/mode-select.html" class="back-link">← Back to Game</a>
```

---

## 5. Per-screen checklist

All three inherit the new `auth.css`. Verify each:

**login.html** — `WELCOME BACK` title, email + password, "Forgot password?", `LOG IN` button, "Sign up" footer, "Back to Game". ✅ No structural change. Optional: add logo + arrow.

**signup.html** — `CREATE ACCOUNT`, email / password / confirm, alpha access-code field (alpha mode), `SIGN UP`, "Log in" footer, **Request Access Code thanks modal**. The modal now uses the Functional-Modal treatment (dark surface, orange accent bar) automatically. **Declutter the alpha messaging (first-touch screen — keep it focused):**
- **Remove** the `<div id="alpha-disclaimer" class="alpha-disclaimer">…</div>` box entirely from the markup.
- On the access-code field, replace the standalone `.request-access-link` with a field hint that folds the CTA in: `<div class="form-hint">Don't have one? <a href="#" id="request-access-link">Request access</a></div>` (keep the `id="request-access-link"` so the existing JS handler still binds). Placeholder becomes `Enter your code`.
- **Preserve the data-wipe warning** as one quiet line after the form: `<p class="auth-warnline">Alpha build — your data may be wiped during testing.</p>`. Styles ship in `auth.css`. Show/hide it with the same `config.isAlpha` check that previously toggled the disclaimer (and the OTP block).
- Do **not** put the requirement in the placeholder only (accessibility) — the label + required attr + hint carry it.

Optional: add logo. (No back link on signup today — leave as is unless you want one.)

**reset-password.html** — two states in one page: `FORGOT PASSWORD` (request) and `SET NEW PASSWORD` (token present). Both use `.success-message` / `.error-message` — both restyled. ✅ No structural change. Optional: add logo + arrow.

---

## 6. What "done" looks like

- All three screens read unmistakably as GOB the moment they load (same dark base, orange action, Bebas Pro headers as the rest of the product).
- Still calm and single-task — no added density.
- No blue focus rings, no `#ff9800`, no bare `Bebas Neue` where Pro is available.
- Alpha badge, alpha disclaimer, OTP field, and the thanks modal all themed.

If you only do one thing: **swap `auth.css`.** Everything above #4 is automatic.
