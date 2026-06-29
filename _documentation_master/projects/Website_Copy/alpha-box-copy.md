# Alpha Box Copy (Mode Select)

Use this file as the source of truth for the "ALPHA RELEASE" box copy shown on the Mode Select screen.

## Current Copy (As Of `FrontEnd/static/mode-select.html`)

Title:
- ALPHA RELEASE

Body (single paragraph in `.alpha-disclaimer-text`):
- **June 29 Update** Added deeper step-by-step execution logic and outcomes for half-court offense, half-court traps, and full-court presses. Improved end-of-quarter logic. Reduced the number of offensive rebounds. Added better computer team logic for blowout situations. Built the mid-game resume system. Deepened the impact of aggression settings for all turn types.

Source:
- `FrontEnd/static/mode-select.html`
- Bump `ALPHA_DISCLAIMER_VERSION` in `FrontEnd/static/mode-select.js` whenever this copy changes so returning users see the box again until they dismiss it.
