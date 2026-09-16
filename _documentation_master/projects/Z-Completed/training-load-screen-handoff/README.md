# Training Load Screen — prototype reference

Design reference for the league-news training load screen. **Not production code** —
it is a React + Babel prototype standing in for a vanilla `PageLoadOverlay` variant.
Read it for layout, type, motion and data shape; implement per the brief.

## Files

| File | What it is |
| --- | --- |
| `CURSOR BRIEF - Training Load Screen.md` | The implementation spec. Start here. |
| `Training Load Screen.html` | Shell + all CSS. Every value in the brief is lifted from here. |
| `training-newswire.jsx` | Card renderers, rotation clock, crossfade, asset fallbacks. |
| `training-newswire-data.js` | **The proposed payload shape** (documented at the top) + fixture data. |
| `tweaks-panel.jsx` | Prototype-only control panel. Do not port. |

## Running it

Asset paths are repo-ready (`/images/teams/{slug}/{slug}_banner_card.webp`), so drop the
folder anywhere under `FrontEnd/static/` and open the HTML from the dev server. Opened
from the filesystem the team art will 404 to the general fallback.

Player headshots resolve to a stubbed R2 host in `headshotUrl()` and will always fall back
to the silhouette. Point it at `API_CONFIG.getPlayerImageUrl(id, { size: 'card' })` to see
the real state.

## Prototype-only, ignore when porting

- React, Babel, `tweaks-panel.jsx`, and the `WIRE_DEFAULTS` block.
- Keyboard nav (← → step, space pause) and the bottom-right hint.
- The Tweaks panel's alternate options — logo-only team rows, team-logo player marks,
  footer pulse, slide/cut transitions. The **defaults as shipped in this file are the
  agreed design**; the alternates are there for comparison only.
- All records, stat lines, matchups and conference numbers are fixtures.

## Carry over verbatim

- Every CSS value in `Training Load Screen.html`.
- The payload contract at the top of `training-newswire-data.js`.
- The 6000ms clock, 260ms fade-out / 340ms fade-in, and the sweep line.
- The pulse bar gradient and `pageLoadOverlayPulseBar` keyframes — already shipped in
  `js/shared/pageLoadOverlay.js`, unchanged here except for dimensions.
