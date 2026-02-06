# Front End Architecture

**Scope:** Court page (`court.html`) layout. Single source of truth: CSS Grid in `#app-grid`. Post-alpha, user feedback may drive further frontend tightening.

---

## 1. Layout: Single CSS Grid

All major regions are defined by one grid container.

**Container:** `#app-grid` in `FrontEnd/static/court.html`.

```css
#app-grid {
  display: grid;
  grid-template-rows:
    var(--scoreboard-height)     /* Row 1: scoreboard */
    1fr                          /* Row 2: court + stats panels */
    clamp(160px, 25vh, 300px);   /* Row 3: playcall */
  grid-template-columns:
    var(--player-stats-width) 1fr var(--player-stats-width);
  grid-template-areas:
    "scoreboard scoreboard scoreboard"
    "left-stats court right-stats"
    "left-stats playcall right-stats";
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}
```

**Row 3:** `left-stats playcall right-stats` — side panels (Team Box Score) span the full height (rows 2 and 3); playcall is center column only.

---

## 2. Grid Areas → Elements

| Grid area    | Element(s)                      | Notes |
|-------------|----------------------------------|-------|
| `scoreboard`| `#scoreboard`                    | Top bar; grid positioning when inside `#app-grid`. |
| `left-stats`| `.player-stats-panel.away`       | Left team stats; scrollable. |
| `court`     | `#phaser-container`              | Phaser canvas container; `min-height: 0`, `min-width: 0`. |
| `right-stats`| `.player-stats-panel.home`      | Right team stats; scrollable. |
| `playcall`  | `#playcall-center`               | Center column only (`grid-column: 2`); overrides base `position: fixed` when inside `#app-grid`. |

---

## 3. CSS Variables (`:root`)

| Variable               | Value   | Purpose |
|------------------------|---------|---------|
| `--scoreboard-height`  | 100px   | Row 1 height. |
| `--player-stats-width`  | 280px   | Left/right column width. |
| `--side-padding`       | 10px    | Horizontal padding (e.g. scoreboard). |
| `--pbp-height`         | 120px   | Play-by-play (if used). |
| `--court-bg`           | #1e1e1e| Court background. |
| `--scoreboard-gap`     | 20px   | Scoreboard internal spacing. |
| `--home-vibrant-color` / `--away-vibrant-color` | #ff6200 | Team accent. |

---

## 4. Canvas (Phaser)

- **Sizing:** DOM controls size. `#phaser-container` gets space from the grid; canvas uses `width: 100%; height: 100%` to fill it. Phaser must match container dimensions.
- **ResizeObserver:** Intended to observe `#phaser-container` (not window) and pass dimensions to Phaser when the grid allocates new space. No JS sets layout `top`/`left`/`width`/`height` for layout-critical elements when `#app-grid` is present.
- **Legacy:** `updatePlaycallPosition()` still exists but returns immediately if `#app-grid` exists; layout is grid-driven.

---

## 5. Invariants (Layout Rules)

1. **Single layout system:** Major regions come from `#app-grid` only. No Flexbox for primary structure; no `position: fixed` for layout (scoreboard, playcall use grid when inside `#app-grid`).
2. **No JS layout positioning:** JS must not set `top`/`left`/`width`/`height` for layout-critical elements. Overlays (modals, tooltips, HUD) may stay `position: fixed`.
3. **Shrinking:** Grid/flex children that must shrink have `min-height: 0` and/or `min-width: 0` (e.g. court, stats panels, playcall).
4. **Playcall width:** Playcall lives in center column only; side panels extend to bottom of viewport.

---

## 6. Responsive

- **Desktop:** Full 3-column layout as above. Tablet/mobile breakpoints (e.g. 1024px, 768px) are specified in the Refactor Plan but not yet implemented; to be revisited after alpha and user feedback.

---

## 7. Reference

- **Refactor plan (history + exit criteria):** `docs/Frontend_Layout_Refactor_Plan.md`
- **Optional hardening (playcall width):** `docs/To Do/playcall_center_width_constraint.md`
