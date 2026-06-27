# Screen Capture Tool — Implementation Brief (C+C)

**Purpose:** A staging-only, opt-in screen capture tool for producing marketing/thumbnail source imagery from GOB. It captures two surface types — the live court (Phaser canvas + DOM overlays, composited) and pure-DOM screens (FCC, stats, etc.) — at 2× resolution, as clean PNGs. Court gameplay captures fire automatically off a curated moment list; all screens also support a manual shutter key.

**Design lens:** Simple, Stable, Scalable. The tool is additive — one config flag in `bootGame.js`, everything else new modules. It must be invisible and inert in production.

**Status:** Directional brief. Implementation-risk items and open seams are flagged inline for C+C to scope against live code before building.

---

## 0. Environment gate (do this first — everything depends on it)

The entire tool is **staging-only**. It must not exist, render, arm, or fire in production.

- Production = `main` branch deploy (the live site real users hit).
- Staging = `develop` branch deploy + localhost (where Jamie plays to make content).

Gate every entry point (key listeners, indicator render, capture functions, the `preserveDrawingBuffer` flag) behind a single `isCaptureEnv()` check. Reuse the existing environment signal already in the codebase:
- `court.html` checks `window.location.hostname === 'localhost' || '127.0.0.1'`.
- `API_CONFIG` distinguishes environments.

**C+C task:** Confirm the exact hostname(s) of the develop/staging deploy and the correct `API_CONFIG` flag, and build `isCaptureEnv()` to return `true` only for localhost + the staging host, `false` for production. If the gate can't be cleanly determined, surface that before proceeding — do not ship a tool that could arm in production.

---

## 1. Architecture overview

Four trigger sources, three capture pipelines, one shared arm/disarm state.

| Capture pipeline | Lives in | Surface |
|---|---|---|
| **A. Court composite** | `FrontEnd/static/js/shared/captureCourt.js` | `court.html` — Phaser canvas + DOM overlays |
| **B. DOM region** | `FrontEnd/static/js/shared/captureDom.js` | Any pure-DOM screen (FCC, stats, lineup) |
| **C. Arm state + UI + keys** | `FrontEnd/static/js/shared/captureControls.js` | Global (staging only) |

Trigger sources feeding Pipeline A:
1. **Announcement hook** — wraps `window.showAnnouncementOverlay` (made-shot milestones, <60s non-makes).
2. **Secondary/ribbon hook** — wraps `window.showSecondaryAnnouncementOverlay` (Fast Break / Trap / Press).
3. **Turn-loop hook** — inside the animation loop (pure-action frames). *Implementation risk — see §6.*
4. **Game-over hook** — result modal mount (end-of-game capture).

Plus the separate **set-lineup screen** capture (§5, moment 6), which is its own pipeline on a different page.

---

## 2. Arm/disarm + manual shutter (`captureControls.js`)

State machine, staging only. Starts **disarmed on every page load**.

- **`Shift+C`** toggles armed ⇄ disarmed.
- **Armed** stays armed for the whole game (through quarters, timeouts, etc.) until `Shift+C` again, or page reload/leave (which resets to disarmed).
- **`c`** (plain) = manual shutter. Active **only when armed**. On `court.html` it calls Pipeline A; on every other page it calls Pipeline B against the current screen's main container. When disarmed, `c` does nothing.
- Both auto-capture and manual `c` are gated by armed state. **Disarmed = zero files produced, guaranteed.**

**Key-handler guards:**
- Bare `c` / `Shift+C` only — ignore if the event target is an `<input>`, `<textarea>`, or `contentEditable` (so typing a username doesn't fire it).
- Reset arm state to disarmed on `pageshow` / load.

---

## 3. "● REC" indicator (staging only)

A small status element, rendered only when `isCaptureEnv()` is true.

- **Position:** top-right corner. Must clear the scoreboard, announcement overlays, and playcall center. High `z-index` (above all game UI, e.g. above the `2000`-range overlays).
- **Disarmed:** hidden (or a dim grey dot).
- **Armed:** red **● REC** badge, optionally slow-pulsing to read as "live."
- **Must not appear in captures:** the capture functions hide the indicator for the frame they grab, then restore it. (One line; flagged so marketing shots come out clean.)
- **Optional per-capture confirmation:** a brief "✓ captured" flash or momentary frame-flash on each successful capture, so auto-captures during gameplay give visual feedback without checking Downloads.

---

## 4. Pipeline A — Court composite capture (`captureCourt.js`)

### 4.1 Preserve the WebGL buffer (`bootGame.js` change)

Phaser's WebGL canvas returns blank from `toDataURL()` unless the drawing buffer is preserved. Add to the game config, **gated so it's only on when capturing** (small perf cost):

```js
// bootGame.js — only when isCaptureEnv() (and ideally only when armed/intent present)
render: { preserveDrawingBuffer: true }
```

C+C: decide whether to enable this whenever `isCaptureEnv()` is true (simplest) or only when arming is possible. Do **not** ship it to production.

### 4.2 Composite function

Capture must combine the Phaser canvas (court/sprites/ball) **and** the DOM overlays (scoreboard, side panels, playcall center, announcements — the "IT'S GOOD!"/"TRAVEL!" text is DOM, not canvas). A bare `canvas.toDataURL()` loses every overlay.

Approach: draw the Phaser canvas to an output canvas, then snapshot the DOM (`#app-grid`) with the canvas temporarily hidden (so the DOM rasterizer renders transparent where the court is), then draw DOM on top.

```js
async function captureCourtScreen({ scale = 2 } = {}) {
  await document.fonts.ready;                  // Bebas Neue / Inter / Barlow must be loaded
  hideRecIndicator();                          // keep ● REC out of the shot
  const grid = document.getElementById('app-grid');
  const phaserCanvas = document.querySelector('#phaser-container canvas');
  if (!grid || !phaserCanvas) return;

  const rect = grid.getBoundingClientRect();
  const out = document.createElement('canvas');
  out.width = rect.width * scale;
  out.height = rect.height * scale;
  const ctx = out.getContext('2d');

  // (a) Phaser canvas, positioned within the grid
  const c = phaserCanvas.getBoundingClientRect();
  ctx.drawImage(phaserCanvas,
    (c.left - rect.left) * scale, (c.top - rect.top) * scale,
    c.width * scale, c.height * scale);

  // (b) DOM overlays with canvas hidden → transparent over court
  phaserCanvas.style.visibility = 'hidden';
  const domShot = await html2canvas(grid, {
    backgroundColor: null, scale, logging: false,
    ignoreElements: (el) => el.id === 'page-load-overlay'
  });
  phaserCanvas.style.visibility = '';

  // (c) DOM on top
  ctx.drawImage(domShot, 0, 0, out.width, out.height);
  restoreRecIndicator();
  saveCapture(out.toDataURL('image/png'), buildFilename('court', currentEventTag));
}
```

### 4.3 Gotchas specific to GOB markup

- **Fixed-position overlays:** `#scoreboard` and `#playcall-center` use `position: fixed`; DOM rasterizers handle fixed elements inconsistently. Verify they land in the right spot. If they drift, temporarily switch them to `position: absolute` during capture, or capture grid regions and stitch.
- **Fonts:** must be fully loaded or text renders in fallback — `await document.fonts.ready` before every court capture.
- **Library choice:** `html2canvas` is the default. If overlay fidelity is poor, evaluate `html-to-image` / `modern-screenshot` (better inline-SVG/filter handling — relevant for the FCC radar in Pipeline B).

---

## 5. Pipeline B — DOM region capture (`captureDom.js`)

Pure DOM, no canvas. Used by the manual `c` shutter on all non-court screens, and by the set-lineup capture (moment 6).

```js
async function captureDomRegion(selector, { scale = 2, tag = 'screen' } = {}) {
  await document.fonts.ready;
  hideRecIndicator();
  const el = document.querySelector(selector);
  if (!el) return;
  const shot = await html2canvas(el, {
    scale, backgroundColor: '#08080f', logging: false, useCORS: true
  });
  restoreRecIndicator();
  saveCapture(shot.toDataURL('image/png'), buildFilename(tag, ''));
}
```

- `backgroundColor: '#08080f'` = GOB base, so transparent corners don't go white.
- **FCC radar caveat:** the Team Measures radar is inline `<svg>` with `<filter>` glows (`buildTeamMeasuresRadarMarkup`). `html2canvas` rasterizes SVG filters inconsistently; the glow may drop. If radar fidelity matters, use `html-to-image`'s `toPng` for this pipeline, or accept flat (no-glow) radar.

---

## 6. Auto-capture moment list (Pipeline A + lineup)

> **EDIT THIS SECTION to tune which gameplay moments capture.** Each block is independent. Adding a moment later (e.g. dunks) is a one-line filter edit and needs no architecture change. All auto-captures fire **only when armed** and **only in the allowed environment**.

All court moments below are **Q4 only** unless stated. Quarter is read from `#quarter` (text "Q4"); clock from `#game-clock`. **If a target is never reached, no capture happens — no fallback, no "closest available."**

### Moment 1 — Made-shot milestones (announcement hook)
Capture the "IT'S GOOD" announcement moment on the **1st, 10th, and 15th** made shots of Q4.
- Hook: wrap `window.showAnnouncementOverlay`; detect a made-shot (`resolveAnnAccentTone(data) === 'ann-accent--made'` or `data.eventText` contains "IT'S GOOD" / "THREE" / "FREE THROW" per existing tone logic).
- Maintain `q4MadeCount`; capture when it equals 1, 10, 15.
- Delay ~120ms after the call so the `annCardIn` (250ms) entry animation paints near peak before grabbing.

### Moment 2 — Late non-makes (announcement hook)
The **first and second** non-"It's Good" announcements with **clock < 60s** (Q4).
- Same wrap; condition: NOT a made-shot, Q4, `#game-clock` < 60s.
- "Non-It's-Good" = any non-make announcement (fouls, steals, blocks, travels, misses). Counter caps at 2.

### Moment 3 — Special-situation ribbons (secondary hook)
The **first** secondary announcement of **Fast Break**, **Trap**, and **Press** — each, with **clock < 4:00** (Q4).
- Hook: wrap `window.showSecondaryAnnouncementOverlay`; match `data.eventText` for "Fast Break" / "Trap" / "Press".
- Three independent one-shot flags, gated on Q4 + clock < 4:00.

### Moment 4 — Pure-action frames (turn-loop hook) — **IMPLEMENTATION RISK**
The **first, second, and third** moments of pure gameplay (no announcement on screen), with **clock < 60s** (Q4), **each from a different turn**.
- This cannot hang off the announcement system (by definition nothing is announcing). It must hook the **turn/animation loop** (`playTurnAnimation()` driver per `agents.md`).
- Condition at capture time: a turn is animating, Q4, clock < 60s, AND both `#announcement-overlay` and `#announcement-overlay-secondary` carry `.hidden`. (Clean-screen check at the moment of grab — no need to track which turns produced announcements.)
- "Different turns": tag each capture with the current turn id; refuse a second capture within the same turn. Max 3.
- **C+C: locate the correct seam in the turn lifecycle** (per-turn or per-step) to run this check. This is the one moment that touches gameplay-loop code rather than wrapping a DOM function. Scope this against live code first.

### Moment 5 — End-of-game modal (game-over hook)
Capture when the end-of-game / result modal mounts.
- Hook the result popup appearing (`.result-popup` / the game-over state). C+C: confirm the exact mount signal (DOM insertion, event, or state flag) and fire one capture on it.

### Moment 6 — Q3→Q4 lineup screen (SEPARATE PIPELINE) — **IMPLEMENTATION RISK**
On the **set-lineup screen during the Q3→Q4 quarter break**, capture when there are **> 3 active players in the right-side lineup container**.
- **Not on `court.html`** — this is the set-lineup screen, a different file. Uses Pipeline B (`captureDomRegion`).
- Conditions: (a) the screen can tell it's the **Q3→Q4** break specifically (not any break), and (b) > 3 populated slots in the right lineup container.
- **C+C: confirm the set-lineup screen exposes which quarter break it is**, and identify the right-container selector + how to count populated/active slots. Scope before building.

---

## 7. Filenames + output

Each capture downloads immediately as its own PNG to the browser's Downloads folder (one file per capture, no end-of-game bundle).

- **Filename convention:** `gob_{tag}_{detail}_{timestamp}.png`, e.g. `gob_court_made3-15th_q4_2026-06-27_14-32-08.png`, `gob_court_pure-action-2_2026-06-27_14-33-10.png`, `gob_lineup_q3-q4_2026-06-27_14-30-00.png`. Descriptive tags so the Downloads folder is eyeball-sortable; default browser names (`download(1).png`) are unacceptable.
- **Sink:** client-side download via `<a download>` with the dataURL. No backend needed for the thumbnail workflow.
- **Known limitation:** browsers download to the one configured location; the tool can't force a `Downloads/GOB/` subfolder client-side. If auto-foldering is wanted later, that's a browser download-rule on Jamie's end or a future backend-upload route (out of scope here).

---

## 8. Open questions for C+C (resolve before/while building)

1. **Env gate (§0):** exact staging hostname + `API_CONFIG` flag for `isCaptureEnv()`.
2. **`preserveDrawingBuffer` scope (§4.1):** always-on in staging vs. only-when-armed.
3. **Fixed-overlay fidelity (§4.3):** does `html2canvas` place `#scoreboard` / `#playcall-center` correctly, or is the absolute-position-swap needed?
4. **Library (§4.3/§5):** `html2canvas` sufficient, or switch to `html-to-image` for SVG-filter fidelity (FCC radar)?
5. **Turn-loop seam (Moment 4):** correct hook point in `playTurnAnimation()` for the pure-action clean-screen check + turn-id tagging.
6. **Game-over signal (Moment 5):** exact mount/event for the result modal.
7. **Lineup screen (Moment 6):** does set-lineup know it's the Q3→Q4 break? Right-container selector + active-slot count method.

---

## 9. Build order (suggested)

1. `isCaptureEnv()` gate + `captureControls.js` (arm state, keys, ● REC indicator). Verify staging-only, disarmed-by-default, zero files when disarmed.
2. `captureDom.js` + manual `c` on non-court screens (lowest risk, validates the whole download/filename/indicator loop).
3. `bootGame.js` `preserveDrawingBuffer` + `captureCourt.js` composite + manual `c` on court.
4. Moments 1, 2, 3 (announcement + ribbon hooks — clean wraps).
5. Moment 5 (game-over hook).
6. Moment 4 (turn-loop hook — higher risk, do after the easy hooks prove the capture path).
7. Moment 6 (set-lineup pipeline — separate screen).
