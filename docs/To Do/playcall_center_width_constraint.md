# Playcall center width constraint (optional / revisit later)

**Goal:** Ensure the Playcall Center container width always stays consistent with the court container and is limited to the center column (no full-width bar under the side panels).

**Current state:** When the grid wins, `#app-grid #playcall-center` already has `grid-column: 2`, `position: relative !important`, `width: 100%`, `max-width: 100%`. In some environments the base `#playcall-center` rule (position fixed + left/right) may still win and make the bar full width.

**Proposed hardening (only if needed after testing):**

- Rely solely on the grid override for layout when inside `#app-grid`; treat the fixed rule as legacy/fallback.
- Under `#app-grid #playcall-center`, add:
  - `overflow-x: hidden` so no inner content can extend the bar horizontally.
  - Optionally `min-width: 0` so the grid cell can shrink and never force the bar wider than the center column.

**Note:** May be over-engineering if the current override is sufficient. Revisit after verifying behavior in target environments.
