# Loading Overlay System

Full-page loader shown on **initial navigation** to key gameplay and command surfaces so users do not briefly see stale defaults (wrong scores, timeouts, NG, missing buttons).

## Behavior

- **Overlay:** Dark, near-opaque full-viewport layer (`#page-load-overlay`, z-index 999999).
- **When:** Shown as early as possible on load; removed only after the page's primary data fetch and UI bind complete.
- **In-page navigation:** Switching tabs on FCC does **not** re-show the overlay (no full document load).
- **FCC cache rule:** FCC may restore `sessionStorage` shell data during init, but that render stays behind the overlay. The overlay is hidden only after authoritative `/franchise/command-center/data` has returned and current top-level FCC state has been applied, preventing stale cached content from flashing as current.

## Two variants

`PageLoadOverlay.show()` accepts a string (spinner variant) or an options object with `variant`:

1. **Spinner** (default) — centered `loader1.gif` + optional message line. The classic full-page loader.
2. **Pulse** — richer "loading moment" layout: team banner image (via `getTeamAssetPath`, defaults to the general banner), Bebas title, subtitle, optional eyebrow label, and an optional **rotating stat feed** (`statLines`, default 8s interval) above an animated green pulse bar. Used for longer waits (e.g. post-game transition, training run) where we show real content while the backend works. Pass `showBanner: false` to hide the banner and keep only the title (or subtitle) plus the green pulse bar — used by FCC while simming an eliminated-user EOS round.

Additional API:

- `PageLoadOverlay.updatePulseSubtitle(text)` — swap the pulse subtitle without re-running `show()`.
- `PageLoadOverlay.buildPostgameStatFeed(gameDoc, { userTeamSide })` — builds the rotating stat-line feed from a game doc's `box_score` (user team first, sorted by points then minutes; player lines like "Name (#5): 12 points, 4 rebounds, … DEF: 67%").
- Pulse option `showBanner: false` — hide the team banner; title (or subtitle) sits above the green pulse bar. FCC uses this for eliminated-user EOS sim-rest (weeks 28–34).

## Implementation

| Concern | Location |
|--------|----------|
| Shared show/hide API + pulse variant | `FrontEnd/static/js/shared/pageLoadOverlay.js` (`PageLoadOverlay.show` / `.hide` / `.updatePulseSubtitle` / `.buildPostgameStatFeed`) |
| Court | `FrontEnd/static/court.html` (overlay markup + init) |
| Set lineup | `FrontEnd/static/set-lineup.html` / `.js` |
| Franchise Command Center | `franchise-command-center.html` + `.js` (`hideFccLoadingOverlay`) |
| Training run | `training.js` (pulse variant with rotating highlights) |
| Box score | `box-score.html` / `.js` |
| Team select | `franchise-select-team.html` / `.js` |
| EOG transition | `js/phaser/utils/gameCompletionPopup.js` (postgame stat feed) |
| Access denied | `js/shared/accessDenied.js` |
| Tournament Command Center | `tournament.html` + `tournament.js` — **sunset mode**; wiring remains until the tournament code purge |

Loader asset: `FrontEnd/static/images/loader1.gif`.

## Related docs

- `_documentation_master/00_General_Systems/Page_Load_System.md` — standardized fetch/cache pattern for franchise resource pages.
- `_documentation_master/00_General_Systems/Deploy_To_Live_System.md` — maintenance and deploy flows (banner + hard maintenance page).
