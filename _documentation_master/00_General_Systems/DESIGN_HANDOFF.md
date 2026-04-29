# GOB Shell Redesign — Cursor Implementation Handoff

## Overview

This document is the implementation brief for the GOB in-game shell redesign. It covers every file that needs to change, exact CSS values to apply, per-screen notes, and explicit do-not-touch boundaries.

**Read this document in full before making any changes.** Also read the updated styleguide at `_documentation_master/00_General_Systems/Styleguide_updated.md` — it is the canonical design authority for the product.

---

## Scope

### In scope — these screens get the new shell
Every in-game management screen that currently uses the navy gradient body background and the `fcc-brand-page-shell` rounded container. This includes but is not limited to:

- `franchise-command-center.html`
- `set-lineup.html`
- `standings.html`
- `leaders.html`
- `recruiting.html`
- `game-plan.html`
- `box-score.html`
- `training.html` (if it uses the shell)
- Any other page that uses `body { background: linear-gradient(...navy...) }` and `.fcc-brand-page-shell`
- `mode-select.html` — body background only (no shell container on this page — see Mode Select section below)

### Explicitly out of scope — do not touch these files
- `homepage-v3.html` and `homepage-v3.css` — the marketing homepage has its own design system. Do not change it.
- `court.html` and any court-specific CSS — the gameplay screen is out of scope entirely.
- Any JS files — this is a CSS/HTML visual change only. No logic changes.
- Modal CSS inside `resource-pages.css` (`.gob-modal-*` classes) — the modal system is unchanged.
- Toast notification CSS — unchanged.
- Data grid CSS (`.gob-data-grid`, `.gob-data-grid-shell`, etc.) — the table system is unchanged.
- Button CSS (`.gob-action-btn`) — the button system is unchanged.
- Auth bar CSS (`/css/auth-bar.css`) — unchanged.

---

## Visual Spec References

Three POC (proof-of-concept) HTML files live in the same folder as this document (`_documentation_master/00_General_Systems/`). Use these as the visual ground truth — not the old navy shell.

- `_documentation_master/00_General_Systems/GOB FCC Shell POC.html` — FCC Coach's Office tab, showing the new shell, tabs, and home grid cards
- `_documentation_master/00_General_Systems/GOB Mode Select POC.html` — Mode Select page with franchise card, leaderboard, and community highlights
- `_documentation_master/00_General_Systems/GOB Set Lineup POC.html` — Set Lineup page with banner strip, context bar, roster table, and lineup slots

Open each file in a browser and inspect the CSS before implementing. The POC CSS is the implementation reference.

---

## Core Token Changes

These are the fundamental values that change everywhere. Apply these first, then handle per-screen overrides.

### Body background (ALL in-scope pages)

**Before:**
```css
body {
  background: linear-gradient(180deg, #263d7a 0%, #1e3068 42%, #141f4a 100%);
  background-attachment: fixed;
}
```

**After:**
```css
body {
  background: #0b0d14;
}
```

Remove `background-attachment: fixed` entirely. No gradient. No navy.

### Shell container (`.fcc-brand-page-shell`)

The `::before` pseudo-element handles the glass layer. The `::after` pseudo-element handles diagonal banding only — the SVG ellipse texture is removed.

**`::before` — Before:**
```css
background:
  linear-gradient(125deg, transparent 0 10%, rgba(255,255,255,0.05) 10% 18%, transparent 18% 34%, rgba(255,255,255,0.04) 34% 42%, transparent 42% 58%, rgba(255,255,255,0.035) 58% 66%, transparent 66% 100%),
  linear-gradient(180deg, rgba(255,255,255,0.05), transparent 28%),
  rgba(7,13,36,0.16);
border: 1px solid rgba(255,255,255,0.08);
border-radius: 28px;
box-shadow: var(--fcc-shadow, 0 18px 36px rgba(0,0,0,0.26));
```

**`::before` — After:**
```css
background:
  linear-gradient(160deg, rgba(255,255,255,0.028) 0%, rgba(255,255,255,0.014) 18%, transparent 40%),
  rgba(14, 16, 24, 0.96);
border: 1px solid rgba(255,255,255,0.09);
border-radius: 24px;
box-shadow: 0 20px 48px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.07);
```

**`::after` — Before (the entire SVG ellipse block):**
```css
background:
  repeating-linear-gradient(132deg, transparent 0 2px, rgba(39,64,142,0) 2px 4px, transparent 4px 104px),
  repeating-linear-gradient(132deg, transparent 0 34px, rgba(39,64,142,0) 34px 36px, transparent 38px 104px),
  repeating-linear-gradient(132deg, transparent 0 68px, rgba(39,64,142,0) 68px 70px, transparent 70px 104px),
  url("data:image/svg+xml,..."); /* the entire SVG ellipse data URI */
background-repeat: repeat, repeat, repeat, repeat;
background-size: auto, auto, auto, 416px 40px;
```

**`::after` — After (diagonal banding only, no SVG):**
```css
background: repeating-linear-gradient(
  132deg,
  transparent 0 102px,
  rgba(255, 255, 255, 0.012) 102px 103px,
  transparent 103px 208px
);
```

### CSS custom properties to update in `:root`

In `franchise-command-center.css`:

```css
/* Before */
--fcc-primary: #27408e;
--fcc-primary-top: #263d7a;
--fcc-primary-mid: #1e3068;
--fcc-primary-deep: #141f4a;
--fcc-panel: rgba(39, 64, 142, 0.26);

/* After */
--fcc-primary: #27408e;        /* keep — still used for accent moments */
--fcc-primary-top: #263d7a;    /* keep — still used for accent moments */
--fcc-primary-mid: #1e3068;    /* keep — still used for accent moments */
--fcc-primary-deep: #141f4a;   /* keep — still used for accent moments */
--fcc-panel: rgba(255,255,255,0.04); /* updated — neutral glass panel */
```

In `resource-pages.css`:
```css
/* Before */
--fcc-primary: #27408E;
--fcc-primary-top: #3551A5;
--fcc-primary-mid: #1E3068;
--fcc-primary-deep: #1C2D60;

/* After — keep all values, they are still used for accent contexts */
/* Only the body background and shell ::before/::after change */
```

---

## Per-Screen Implementation Notes

### Franchise Command Center (`franchise-command-center.css`)

**Tabs — this is the most significant visual change on this screen.**

Current tab treatment uses a heavy steel gradient and 24px font at 44px height. Replace with:

```css
#franchise-container .tab-buttons button {
  min-height: 40px;                          /* reduced from 44px */
  font-size: 16px;                           /* reduced from 24px */
  letter-spacing: 0.04em;
  background: rgba(255,255,255,0.06);        /* flat, no gradient */
  border: 1px solid rgba(255,255,255,0.10);
  color: rgba(255,255,255,0.55);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
  clip-path: polygon(10px 0, 100% 0, calc(100% - 10px) 100%, 0 100%); /* keep */
  transition: transform 0.15s, background 0.15s, border-color 0.15s, color 0.15s;
}

#franchise-container .tab-buttons button::before {
  /* Replace full-area gradient with thin top edge only */
  content: '';
  position: absolute;
  top: 0; left: 10px; right: 10px;
  height: 2px;
  background: transparent;
  transition: background 0.15s;
  pointer-events: none;
}

#franchise-container .tab-buttons button:hover {
  background: rgba(255,255,255,0.11);
  color: rgba(255,255,255,0.90);
  transform: translateY(-1px);
  /* remove old gradient */
}

#franchise-container .tab-buttons button.active {
  background: rgba(255,255,255,0.09);
  border-color: rgba(255,255,255,0.18);
  color: #ffffff;
  transform: translateY(-2px);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.10);
}

#franchise-container .tab-buttons button.active::before {
  background: rgba(255,255,255,0.70);  /* white top edge on active tab */
}
```

**Inbox tab — replace gold with badge:**

Remove the permanent gold treatment on the Inbox tab. Replace with:

```css
/* Inbox tab: neutral resting state, same as all other tabs */
#franchise-container .tab-buttons button[data-tab="tutorials-tab"] {
  background: rgba(255,255,255,0.06);
  border-color: rgba(255,255,255,0.10);
  color: rgba(255,255,255,0.55);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
}

#franchise-container .tab-buttons button[data-tab="tutorials-tab"]::before {
  background: transparent; /* no gradient */
}

/* Badge dot — shown only when inbox has unread messages */
/* Add this element via JS when unread count > 0: */
/* <span class="inbox-badge"></span> inside the button */
.inbox-badge {
  position: absolute;
  top: 6px;
  right: 14px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #F79420;
  box-shadow: 0 0 6px rgba(247,148,32,0.7);
  animation: inboxBadgePulse 2.5s infinite;
}

@keyframes inboxBadgePulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: 0.6; transform: scale(0.85); }
}
```

**FCC home grid cards — remove any blue tint from card backgrounds.**

Current cards use `rgba(40, 46, 56, 0.92)` which has a blue tint. Update to a neutral dark:

```css
.fcc-home-card {
  background:
    linear-gradient(180deg, rgba(255,255,255,0.05), transparent 18%),
    linear-gradient(180deg, rgba(26,30,42,0.95), rgba(18,21,32,0.97));
}
```

**Tab content panel:**
```css
#franchise-container .tab-content {
  background:
    linear-gradient(180deg, rgba(255,255,255,0.05), transparent 16%),
    rgba(14, 16, 26, 0.90);
}
```

---

### Set Lineup (`set-lineup.css`)

**Body background:** Apply the core token change — `#0b0d14`, no gradient.

**Banner strip:** Keep existing implementation. Update object-position to `center 35%` if not already set.

**Shell `::before` and `::after`:** Apply core token changes above. The banner strip sits inside the shell's rounded top — ensure `border-radius: 24px 24px 0 0` on the banner container.

**Left panel (roster):** Slightly darker than the shell interior:
```css
.lineup-left-panel {
  background: rgba(13, 16, 24, 0.97);
}
```

**Right panel (lineup slots):**
```css
.lineup-right-panel {
  background: rgba(16, 19, 30, 0.98);
  border-left: 1px solid rgba(255,255,255,0.08);
}
```

**Filled slots** — keep the existing orange tint treatment:
```css
.slot.filled {
  border-style: solid;
  border-color: rgba(247,148,32,0.22);
  background: rgba(247,148,32,0.04);
}
```

---

### Mode Select (`mode-select.css`)

**Body background only** — no shell container on this page.

```css
body.mode-select-page {
  background: #0b0d14;
  /* remove: background: #0d1124 */
}
```

**Franchise card (active state):**
The card uses a team banner image as background with a heavy gradient overlay. Keep existing implementation but ensure:
- `background-size: cover`
- `background-position: center center` (crop, not letterbox)
- Gradient overlay: `linear-gradient(to bottom, rgba(11,13,20,0.15) 0%, rgba(11,13,20,0.55) 50%, rgba(11,13,20,0.95) 80%, rgba(11,13,20,0.99) 100%)`

**Community and highlights panels** — update card background to match new neutral dark system:
```css
body.mode-select-page .community-panel,
body.mode-select-page .franchise-home-card,
body.mode-select-page .community-highlights-panel {
  background:
    linear-gradient(180deg, rgba(255,255,255,0.05), transparent 14%),
    rgba(22, 26, 36, 0.97);
  border: 1px solid rgba(255,255,255,0.10);
}
```

**Community highlight rows** — keep the existing team-color gradient row treatment. This is intentional and correct.

---

### All other resource pages (`resource-pages.css`)

Apply the core token changes to `.fcc-brand-page-shell::before` and `::after`. The body background change applies via page-specific CSS files (standings, leaders, recruiting, etc.) — update each body background declaration to `#0b0d14`.

For pages that set `body { background: linear-gradient(...navy...) }` inline or in page-specific CSS, find and replace with `background: #0b0d14`.

---

## What Does NOT Change

To be absolutely explicit — these design elements are preserved exactly as-is:

- All button shapes, colors, and behaviors (green gating / orange non-gating)
- All modal designs (Functional, Action-Only, Moment, Strategic)
- All toast notification designs
- All data grid / table CSS
- The attribute bar color scale (0–40 red / 41–60 yellow / 61–80 green / 81+ blue)
- The parallelogram tab clip-path shape
- The auth bar
- All JS logic
- `court.html` and everything related to gameplay
- `homepage-v3.html` and `homepage-v3.css`
- The gold/yellow Inbox tab hover treatment only — this becomes neutral + badge (see above)

---

## Implementation Order

Recommended sequence to minimize visual breakage:

1. Update `resource-pages.css` — shell `::before` and `::after` changes
2. Update `franchise-command-center.css` — body background, tab treatment, Inbox badge, card surfaces
3. Update `mode-select.css` — body background only, franchise card overlay, panel surfaces
4. Update `set-lineup.css` — body background, panel differentiation
5. Update remaining page-specific CSS files — body background declarations only

Test after each step by loading the page in a browser and comparing against the POC files.

---

## Files Summary

| File | Change type |
|------|-------------|
| `resource-pages.css` | Shell `::before` / `::after` token update |
| `franchise-command-center.css` | Body bg, tabs, Inbox badge, card surfaces |
| `mode-select.css` | Body bg, panel surfaces |
| `set-lineup.css` | Body bg, panel differentiation |
| `standings.css` (if exists) | Body bg only |
| `leaders.css` (if exists) | Body bg only |
| `recruiting.css` (if exists) | Body bg only |
| `game-plan.css` | Body bg only |
| `homepage-v3.css` | **DO NOT TOUCH** |
| `court.html` / court CSS | **DO NOT TOUCH** |
| Any JS files | **DO NOT TOUCH** |
