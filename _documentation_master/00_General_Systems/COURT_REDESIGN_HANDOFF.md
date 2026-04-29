# GOB Court Screen Redesign — Cursor Implementation Handoff

## Overview

This document is the implementation brief for the `court.html` gameplay screen redesign. Unlike the shell redesign handoff, this document makes **surgical CSS changes only**. The Phaser canvas, all JS logic, and all element IDs must remain untouched.

**Read this document in full before making any changes.** Also read `_documentation_master/00_General_Systems/Styleguide.md` as the canonical design authority.

---

## Critical Constraints — Read First

`court.html` is a 185k file with deep JS dependencies. Before touching anything:

1. **Do not rename, reparent, or remove any element with an ID.** The following IDs are wired directly to `gameScene.js` and related scripts: `pause-btn`, `home-stats-body`, `away-stats-body`, `home-score`, `away-score`, `game-clock`, `quarter`, `shot-clock`, `offense-status-text`, `defense-status-text`, `playcall-center`, `offense-play-scroller`, `phaser-container`, `app-grid`, and many others. Changing these will break gameplay.

2. **Do not touch the Phaser canvas** (`#phaser-container canvas`). Do not change `#phaser-container` dimensions, scale mode, or positioning.

3. **Do not touch court images.** The team court images are precisely calibrated to the Phaser animation system. Court image paths, dimensions, and object-position values must not change.

4. **Do not touch any JS files.** This is a CSS-only change.

5. **The `#playcall-center` uses `position: fixed !important`** with JS-driven `top` positioning. Do not change this to relative or static — the layout will break.

6. **Player name color coding in box scores must be preserved.** Colors are driven by player NG (energy) values: `>89 green / 80–89 yellow / 70–79 orange / <70 red`. This is a design component, not legacy styling. Do not override or remove it.

---

## Scope

### In scope — these sections get the redesign:
- `#scoreboard` — visual treatment, typography scale, team color bleed
- `.player-stats-panel` (left and right) — momentum bar addition, tab styling, color bleed
- `#playcall-center` — layout rebalancing, override strip redesign, button hierarchy
- `#announcement-overlay` — cinematic upgrade for primary announcements
- New lower-third playcall announcement strip (new HTML element)

### Out of scope — do not touch:
- `#phaser-container` and its canvas
- All JS files
- Court image files
- Any element ID listed in the Critical Constraints section above
- `command-center-team-styles.css`

---

## Section 1 — Scoreboard (`#scoreboard`)

### Clock — make it the dominant element

**Before:**
```css
#scoreboard .center .clock {
  font-size: 52px;
}
```

**After:**
```css
#scoreboard .center .clock {
  font-size: 80px;
  line-height: 1;
  letter-spacing: 0.01em;
}
```

### Shot clock — color pulse when critical

Add this rule:
```css
#scoreboard .center .shot-clock.critical {
  color: #ff4444;
  animation: shotClockCritical 0.5s ease-in-out infinite alternate;
}

@keyframes shotClockCritical {
  from { opacity: 1; }
  to   { opacity: 0.5; }
}
```

Add the `.critical` class via JS when shot clock drops below 7 seconds. Remove it otherwise.

### Bottom border — gradient from away color to home color

**Before:**
```css
#scoreboard {
  border-bottom: 2px solid var(--home-vibrant-color);
}
```

**After:**
```css
#scoreboard {
  border-bottom: none;
  position: relative;
}

#scoreboard::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(
    to right,
    var(--away-vibrant-color) 0%,
    rgba(255,255,255,0.10) 48%,
    rgba(255,255,255,0.10) 52%,
    var(--home-vibrant-color) 100%
  );
}
```

### Team color atmospheric bleed on scoreboard sides

The scoreboard already has `::after` for the border above. Add bleed via the team logo containers:

```css
#away-logo-container {
  position: relative;
}
#away-logo-container::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(to right, rgba(var(--away-vibrant-rgb), 0.25) 0%, transparent 100%);
  pointer-events: none;
  z-index: 0;
}

#home-logo-container {
  position: relative;
}
#home-logo-container::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(to left, rgba(var(--home-vibrant-rgb), 0.25) 0%, transparent 100%);
  pointer-events: none;
  z-index: 0;
}
```

Note: You will need to add `--away-vibrant-rgb` and `--home-vibrant-rgb` CSS custom properties alongside the existing `--away-vibrant-color` and `--home-vibrant-color` vars (RGB values only, no `rgba()` wrapper), set via JS the same way the vibrant colors are currently set.

### Rank and record — stacked vertically in scoreboard

The current implementation shows team logos as `<img>` tags. Add rank/record as a small stacked text block adjacent to each logo container. This is new HTML:

```html
<!-- Away side — add after #away-logo-container -->
<div class="sb-team-meta sb-team-meta--away">
  <span class="sb-rank" id="away-rank">#--</span>
  <span class="sb-record" id="away-record">--</span>
</div>
```

```html
<!-- Home side — add after #home-logo-container -->
<div class="sb-team-meta sb-team-meta--home">
  <span class="sb-rank" id="home-rank">#--</span>
  <span class="sb-record" id="home-record">--</span>
</div>
```

CSS:
```css
.sb-team-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  justify-content: center;
}

.sb-rank {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 14px;
  letter-spacing: 0.06em;
  color: rgba(255,255,255,0.55);
  line-height: 1;
}

.sb-record {
  font-family: 'Inter', sans-serif;
  font-size: 11px;
  font-weight: 600;
  color: rgba(255,255,255,0.35);
  letter-spacing: 0.03em;
  line-height: 1;
}

.sb-team-meta--away { text-align: left; }
.sb-team-meta--home { text-align: right; }
```

Populate `#away-rank`, `#away-record`, `#home-rank`, `#home-record` via JS alongside the existing score/stats updates.

### Scoreboard layout order

**Away team** (left side, reading left to right): logo → rank/record → score → TOL/F

**Home team** (right side, reading left to right): TOL/F → score → logo → rank/record

The current grid column order already puts logo on the far left for away and far right for home. The rank/record block slots in between logo and score. Adjust grid column assignments accordingly.

---

## Section 2 — Side Panels (`.player-stats-panel`)

### Team color atmospheric bleed

```css
.player-stats-panel.away {
  border-right: 2px solid var(--away-vibrant-color);
  position: relative;
}

.player-stats-panel.away::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(to right, rgba(var(--away-vibrant-rgb), 0.10) 0%, transparent 60%);
  pointer-events: none;
  z-index: 0;
}

.player-stats-panel.home {
  border-left: 2px solid var(--home-vibrant-color);
  position: relative;
}

.player-stats-panel.home::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(to left, rgba(var(--home-vibrant-rgb), 0.10) 0%, transparent 60%);
  pointer-events: none;
  z-index: 0;
}
```

Ensure `.player-stats-panel > *` has `position: relative; z-index: 1` so content sits above the bleed layer.

### Momentum bar — new element, insert after `.stats-header`

Add this HTML inside each `.player-box-score` section, immediately after `.stats-header`:

```html
<div class="momentum-bar-wrap">
  <div class="momentum-bar-label">MOMENTUM</div>
  <div class="momentum-bar" id="home-momentum-bar"><!-- or away-momentum-bar -->
    <div class="momentum-center-tick"></div>
    <div class="momentum-fill-neg" id="home-momentum-neg" style="width:0%"></div>
    <div class="momentum-fill-pos" id="home-momentum-pos" style="width:0%"></div>
  </div>
</div>
```

CSS:
```css
.momentum-bar-wrap {
  padding: 5px 12px 4px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  flex-shrink: 0;
}

.momentum-bar-label {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 9px;
  letter-spacing: 0.18em;
  color: rgba(255,255,255,0.25);
  margin-bottom: 3px;
}

.momentum-bar {
  position: relative;
  height: 8px;
  background: rgba(255,255,255,0.07);
  border-radius: 999px;
  overflow: hidden;
}

.momentum-center-tick {
  position: absolute;
  left: 50%; top: 0; bottom: 0;
  width: 2px;
  background: rgba(255,255,255,0.25);
  transform: translateX(-50%);
  z-index: 2;
}

.momentum-fill-neg {
  position: absolute;
  right: 50%; top: 0; bottom: 0;
  background: #ff4444;
  border-radius: 999px 0 0 999px;
  transition: width 0.5s ease;
}

.momentum-fill-pos {
  position: absolute;
  left: 50%; top: 0; bottom: 0;
  background: #34EC27;
  border-radius: 0 999px 999px 0;
  transition: width 0.5s ease;
}
```

**JS update logic** — add to wherever momentum values are updated in `gameScene.js`:

```js
function updateMomentumBar(teamSide, value) {
  // value ranges from -50 to +50
  const negEl = document.getElementById(teamSide + '-momentum-neg');
  const posEl = document.getElementById(teamSide + '-momentum-pos');
  if (!negEl || !posEl) return;
  if (value < 0) {
    negEl.style.width = Math.abs(value) + '%'; // -50 = 50% fill leftward
    posEl.style.width = '0%';
  } else {
    posEl.style.width = value + '%'; // +50 = 50% fill rightward
    negEl.style.width = '0%';
  }
}
```

### Tab active state — use team color

**Before:**
```css
.toggle-btn.active {
  background: var(--home-vibrant-color);
  color: #fff;
  border-color: var(--home-vibrant-color);
}
.player-stats-panel.away .toggle-btn.active {
  background: var(--away-vibrant-color);
  border-color: var(--away-vibrant-color);
}
```

**After** — more refined, less saturated:
```css
.toggle-btn.active {
  background: rgba(var(--home-vibrant-rgb), 0.18);
  color: #ffffff;
  border-color: var(--home-vibrant-color);
}
.player-stats-panel.away .toggle-btn.active {
  background: rgba(var(--away-vibrant-rgb), 0.18);
  border-color: var(--away-vibrant-color);
}
```

### Player name NG color coding — PRESERVE EXACTLY

The existing color coding on player name cells based on NG (energy) values is a design component and must not be changed:
- NG > 89: green (`#34EC27` or equivalent)
- NG 80–89: yellow (`#FFD700` or equivalent)
- NG 70–79: orange (`#F79420` or equivalent)
- NG < 70: red (`#ff6d6d` or equivalent)

Do not override, remove, or generalize this styling.

---

## Section 3 — Playcall Center (`#playcall-center`)

### Remove playcall status row

The `#playcall-status-row` (showing "OFFENSE: [play] | DEFENSE: [play]") is being replaced by the new lower-third announcement strip on the court. Remove it from the DOM:

```html
<!-- REMOVE this entire element: -->
<div id="playcall-status-row">...</div>
```

**Important:** `#offense-status-text` and `#defense-status-text` are referenced by JS. Before removing the row, verify these IDs are not used for logic beyond display. If they are, keep the elements but hide them:
```css
#playcall-status-row { display: none; }
```

### Override stacks — convert from vertical columns to horizontal strips

The current three-column stack layout (`.pcc-stacks-zone` containing three `.pcc-stack` vertical columns) should be redesigned as three horizontal strips.

**Current structure:**
```
[TEMPO col]   [AGGRESSION col]   [PRESS-TRAP col]
[FAST btn]    [PASSIVE btn]      [PRESS btn]
[NORMAL btn]  [NORMAL btn]       [TRAP btn]
[SLOW btn]    [AGGR btn]         [NONE btn]
[✕ clear]     [✕ clear]          [✕ clear]
```

**New structure — three horizontal strips:**
```
TEMPO:      [●] [FAST] [NORMAL] [SLOW] [✕]
AGGRESSION: [●] [PASSIVE] [NORMAL] [AGGR] [✕]
PRESS/TRAP: [●] [PRESS] [TRAP] [NONE] [✕]
```

New CSS for the stacks zone and strips:

```css
#pcc-stacks-zone {
  flex: 0 0 400px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 5px;
  padding-left: 12px;
  border-left: 1px solid rgba(255,255,255,0.07);
  border-right: none; /* remove old border */
}

.pcc-stack {
  display: flex;
  flex-direction: row; /* was: column */
  align-items: center;
  gap: 6px;
  height: calc((100% - 10px) / 3);
  min-height: 28px;
}

/* Remove old ::before top bar — replace with left indicator */
.pcc-stack::before {
  content: '';
  width: 3px;
  align-self: stretch;
  border-radius: 2px;
  flex-shrink: 0;
  position: static; /* override old absolute */
  top: auto; left: auto; right: auto;
}

.pcc-stack-label {
  flex: 0 0 72px;
  font-size: 11px;
  letter-spacing: 0.13em;
  text-align: left; /* was: center */
  margin: 0; /* remove old margins */
}

/* Stack buttons — now horizontal, all same row */
.pcc-stack-btn {
  flex: 1;
  height: 100%;
  min-height: 26px;
  padding: 4px 6px;
  border-radius: 6px;
  font-size: 12px;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

/* Clear button — small and subtle */
.pcc-stack-x {
  width: 16px;
  height: 100%;
  min-height: 26px;
  border-radius: 4px;
  background: transparent;
  border: 1px solid rgba(244,67,54,0.18);
  color: rgba(244,67,54,0.45);
  font-size: 9px;
  flex-shrink: 0;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pcc-stack-x:hover {
  background: rgba(244,67,54,0.12);
  color: #F44336;
  border-color: rgba(244,67,54,0.40);
}
```

### Game controls — button hierarchy

The three controls (Game Speed, Pause, Timeout) should have clear visual hierarchy:

```css
/* PAUSE — dominant, orange, largest */
#pause-btn {
  height: 46px;
  font-size: 22px;
  background: #F79420;
  border: 1px solid rgba(247,148,32,0.45);
  color: #0a0b10;
  box-shadow: 0 4px 18px rgba(247,148,32,0.25);
  border-radius: 8px;
  width: 100%;
}

/* TIMEOUT — medium, green tint, shows remaining count */
#timeout-btn {
  height: 34px;
  font-size: 16px;
  background: rgba(52,236,39,0.09);
  border: 1px solid rgba(52,236,39,0.30);
  color: #34EC27;
  border-radius: 8px;
  width: 100%;
}

/* GAME SPEED — smallest, ghost */
#game-speed-btn {
  height: 26px;
  font-size: 12px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.10);
  color: rgba(255,255,255,0.45);
  border-radius: 8px;
  width: 100%;
}
```

Add remaining timeout count as pip dots inside `#timeout-btn`. These should be managed by JS — add/remove a `.used` class on each pip when a timeout is called:

```html
<!-- Inside #timeout-btn, after the label text -->
<span class="timeout-pips" id="timeout-pips">
  <span class="to-pip"></span>
  <span class="to-pip"></span>
  <span class="to-pip"></span>
  <span class="to-pip"></span>
</span>
```

```css
.timeout-pips { display: inline-flex; gap: 3px; align-items: center; margin-left: 8px; }
.to-pip { width: 7px; height: 7px; border-radius: 50%; background: #34EC27; }
.to-pip.used { background: rgba(52,236,39,0.20); }
```

### Play card scrollers — offensive and defensive

The existing offense scroller (`.pcc-play-card` / `#offense-play-scroller`) should be joined by a mirrored defense scroller. Stack them vertically within the offense/defense zone:

```css
/* Widen the offense/defense zone to fit stacked scrollers */
.pcc-card-zone {
  flex: 0 0 260px; /* was: 33% */
}

/* Stack offense above defense */
.pcc-card-zone .zone-inner {
  display: flex;
  flex-direction: column;
  gap: 5px;
  height: 100%;
}

/* Each scroller row */
.pcc-scroller-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-height: 0;
}

/* Zone label */
.pcc-zone-label {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 9px;
  letter-spacing: 0.18em;
  color: rgba(255,255,255,0.25);
  margin-bottom: 2px;
}

/* Scroller divider between offense and defense */
.pcc-scroller-divider {
  height: 1px;
  background: rgba(255,255,255,0.07);
  flex-shrink: 0;
}
```

**Player portrait in offense card — square, not rectangular:**
```css
.play-headshot {
  width: 44px;
  height: 44px; /* square */
  border-radius: 4px;
  object-fit: cover;
  object-position: top center;
  flex-shrink: 0;
}
```

**Player name label — remove from offense card.** The headshot alone is sufficient to identify the shooter. Remove the `.player-name-label` element or hide it:
```css
.play-name-label { display: none; }
```

**Defense card — text only, no portrait:**
The defense scroller shows scheme name only. No headshot needed. Ensure the defense card does not render a portrait slot.

### Nav buttons — smaller, more subtle

```css
.pcc-nav-btn {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.12);
  color: rgba(255,255,255,0.45);
  font-size: 8px;
}

.pcc-nav-x {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  background: rgba(244,67,54,0.07);
  border: 1px solid rgba(244,67,54,0.22);
  color: rgba(244,67,54,0.60);
  font-size: 9px;
}
```

---

## Section 4 — Announcement System

### Lower-third playcall strip — new element

Add this new HTML element inside `#phaser-container`, as a sibling to the canvas (not overlapping it — position it at the bottom of the container):

```html
<div id="playcall-strip" class="playcall-strip hidden">
  <div class="playcall-strip-inner">
    <span class="pcs-eyebrow" id="pcs-offense-label">OFFENSE</span>
    <div class="pcs-divider"></div>
    <span class="pcs-text" id="pcs-offense-play">--</span>
    <div class="pcs-divider"></div>
    <span class="pcs-target" id="pcs-offense-target">--</span>
    <div class="pcs-spacer"></div>
    <span class="pcs-eyebrow" id="pcs-defense-label">DEFENSE</span>
    <div class="pcs-divider"></div>
    <span class="pcs-text pcs-text--muted" id="pcs-defense-play">--</span>
  </div>
</div>
```

CSS:
```css
#playcall-strip {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  z-index: 60;
  pointer-events: none;
}

#playcall-strip.hidden {
  display: none;
}

.playcall-strip-inner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 20px;
  background: rgba(7,8,14,0.92);
  border-top: 2px solid #F79420;
}

.pcs-eyebrow {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 10px;
  letter-spacing: 0.20em;
  color: #F79420;
  flex-shrink: 0;
}

.pcs-divider {
  width: 1px; height: 18px;
  background: rgba(255,255,255,0.16);
  flex-shrink: 0;
}

.pcs-text {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 20px;
  letter-spacing: 0.04em;
  color: #ffffff;
}

.pcs-text--muted {
  color: rgba(255,255,255,0.60);
}

.pcs-target {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 20px;
  letter-spacing: 0.04em;
  color: #FFD700;
}

.pcs-spacer {
  flex: 1;
}
```

**JS show/hide logic** — show the strip at the start of each HCO turn, hide it when the turn ends:

```js
function showPlaycallStrip(offensePlay, offenseTarget, defensePlay) {
  const strip = document.getElementById('playcall-strip');
  document.getElementById('pcs-offense-play').textContent = offensePlay || '--';
  document.getElementById('pcs-offense-target').textContent = offenseTarget || '';
  document.getElementById('pcs-defense-play').textContent = defensePlay || '--';
  strip.classList.remove('hidden');
}

function hidePlaycallStrip() {
  document.getElementById('playcall-strip').classList.add('hidden');
}
```

### Primary announcement overlay — cinematic upgrade

The existing `#announcement-overlay` / `.ann-card` is the right approach. Enhance it:

```css
.ann-card {
  background: rgba(7, 8, 14, 0.90);
  box-shadow: 0 16px 64px rgba(0,0,0,0.80), 0 0 0 1px rgba(255,255,255,0.08);
  /* keep existing animation */
}

/* Accent bar — left edge, color reflects event type */
.ann-card::before {
  width: 5px; /* was: same, keep */
  background: #34EC27; /* made shot — green */
}

/* Portrait larger */
.ann-portrait-zone {
  width: 110px;
  height: 144px;
}

/* Event text — bigger */
.ann-event-zone .ann-text {
  font-size: 64px; /* increase from current */
  line-height: 1;
  letter-spacing: 0.02em;
}

/* Player name — small, muted, above event text */
.ann-jersey-name {
  font-size: 11px;
  color: rgba(255,255,255,0.45);
  letter-spacing: 0.09em;
  text-transform: uppercase;
  margin-bottom: 4px;
}
```

**Accent bar colors by event type** — set via JS on `ann-card`:
- Made shot (2pt, 3pt, FT): `#34EC27` green
- Foul: `#ff4444` red
- Block / Steal: `#4a90d9` blue
- Turnover: `#F79420` orange
- Neutral / other: `#F79420` orange (default)

---

## Section 5 — CSS Variables to Add

Add these to the existing `:root` block alongside `--home-vibrant-color` and `--away-vibrant-color`. Set them via JS the same way the vibrant colors are set:

```css
:root {
  --home-vibrant-rgb: 58, 140, 46;   /* RGB values only, no rgba() */
  --away-vibrant-rgb: 74, 144, 217;  /* RGB values only, no rgba() */
}
```

Set via JS:
```js
document.documentElement.style.setProperty('--home-vibrant-rgb', '58, 140, 46');
document.documentElement.style.setProperty('--away-vibrant-rgb', '74, 144, 217');
```

---

## What Does NOT Change

- All button shapes and colors except those explicitly listed above
- All modal designs (pre-game modal, sim quarter popup, functional modals)
- The `#announcement-overlay` animation timing and entrance keyframes
- The Phaser canvas scaling and container
- Court image files and paths
- All element IDs
- Player NG color coding in box scores
- The `clip-path` parallelogram shape on tab buttons (if present on this page)
- Auth bar

---

## Files to Modify

| File | Change |
|------|--------|
| `FrontEnd/static/court.html` | New HTML elements: rank/record spans, momentum bars, playcall strip, timeout pips |
| `FrontEnd/static/court.html` (inline `<style>`) | All CSS changes above |
| `FrontEnd/static/js/phaser/gameScene.js` | Add: `updateMomentumBar()`, `showPlaycallStrip()`, `hidePlaycallStrip()`, shot clock `.critical` class toggle, timeout pip `.used` class management, `--home-vibrant-rgb` / `--away-vibrant-rgb` CSS var setting |

| File | Status |
|------|--------|
| `command-center-team-styles.css` | **DO NOT TOUCH** |
| All other JS files | **DO NOT TOUCH** |
| Court image files | **DO NOT TOUCH** |
