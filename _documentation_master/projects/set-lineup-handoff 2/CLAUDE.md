# GOB — project facts

Durable constraints for this project. These apply unless a specific task overrides them.

## The game

- **Rosters are 12 players.** Lineups are 5. Worst case for any lineup UI is an empty lineup: 5 slot placeholders + 12 bench = 17 rows.
- Player **RT** (rating) uses a **canonical brand ramp — blue / green / yellow / red — applied game-wide.** Never re-map it or restyle it on a single screen; a core encoding that means the same thing everywhere is worth more than local elegance.
- Player **energy** uses the brand **green / yellow / red** ramp.
- Player **momentum** is an integer scale of **−5…+5**, displayed without numerals.
- **Shot weight** displays have their own already-programmed color scaling and thresholds. Preserve them; don't re-map or substitute another ramp.

## Live-gameplay screens

- Screens the user hits mid-game (timeouts, quarter breaks) **must fit the viewport with nothing below the fold**, unless the user has shrunk the window themselves. Design against the worst-case row count, not the typical one.
- **Color the exception, not the default.** A screen where every value is bright green at rest has spent its alarm channel on the situation that needs no action.

## Color discipline

The brand ramp gets reused across several variables, so keep each on its own visual channel and use each channel once per row:

- hue in a **bar/fill** → energy
- hue on a **letter/glyph** → RT
- **luminance** (no hue) → supporting numerals
- **direction/position** → diverging values like momentum

Corollary: **blue belongs to RT.** Don't spend it on a second variable in the same view.

## Handoff to Claude Code

When writing an implementation prompt:

- Make C+C **report which files own the affected UI, and which data fields actually exist, before writing any code.**
- **Never invent, derive, or approximate a missing field** — stop and ask.
- Don't micromanage what already works: existing CTA copy, existing color scalings, existing column sets.
- Treat design-mock values (placeholder percentages, initials standing in for headshots, sample CTA labels) as illustrative, and say so explicitly in the prompt.
