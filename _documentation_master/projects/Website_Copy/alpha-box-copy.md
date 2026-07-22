# Alpha Box Copy (Mode Select)

Use this file as the source of truth for the "ALPHA RELEASE" box copy shown on the Mode Select screen.

## Current Copy (As Of `FrontEnd/static/mode-select.html`)

Title:
- ALPHA RELEASE

Body (single paragraph in `.alpha-disclaimer-text`):
- **July 22 Update** Improved sim speed times for training and CPU simmed games. Significant overhaul to recruiting logic and UX. Added two new man defenses (Deny Man and Loose Man - to pair with Base Man). Add defender distance calc to shot attempts, pass interceptions, and help defense on drives -- thus magnifying the impact of each defense play.

NOTE -- if you are mid-season, in order to get the full effect of the recruiting overhaul we suggest you delete and start a new season.

Source:
- `FrontEnd/static/mode-select.html`
- Bump `ALPHA_DISCLAIMER_VERSION` in `FrontEnd/static/mode-select.js` whenever this copy changes so returning users see the box again until they dismiss it.
