# Loading Overlay System

Full-page loader shown on **initial navigation** to key gameplay and command surfaces so users do not briefly see stale defaults (wrong scores, timeouts, NG, missing buttons).

## Behavior

- **Overlay:** Dark, near-opaque full-viewport layer with centered `loader1.gif`.
- **When:** Shown as early as possible on load; removed only after the page’s primary data fetch and UI bind complete.
- **In-page navigation:** Switching tabs on FCC/TCC does **not** re-show the overlay (no full document load).

## Implementation

| Concern | Location |
|--------|----------|
| Shared show/hide API | `FrontEnd/static/js/shared/pageLoadOverlay.js` (`PageLoadOverlay.show` / `.hide`) |
| Court | `FrontEnd/static/court.html` (overlay markup + init) |
| Set lineup | `FrontEnd/static/set-lineup.html` |
| Franchise Command Center | `FrontEnd/static/franchise-command-center.html` + `franchise-command-center.js` (`hideFccLoadingOverlay`) |
| Tournament Command Center | `FrontEnd/static/tournament.html` + `tournament.js` |

Loader asset: `FrontEnd/static/images/loader1.gif`.

## Related docs

- `docs/docs_1_systems/00_General_Systems/UX_Page_Load_System.md` — broader UX/page-load patterns where applicable.
- Maintenance and deploy flows (banner + hard maintenance page): `docs/docs_1_systems/00_General_Systems/Deploy_To_Live_System.md`.
