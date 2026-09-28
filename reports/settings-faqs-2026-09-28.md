# Settings: FAQs link (2026-09-28)

Branch: `ux/settings-faqs-link` (from origin/develop 34c21aca8). Commit: 7a18a4d81.

## Result

The Settings panel now has a **FAQs** link, online and offline. It opens `/faqs.html` in a new tab or window (`target="_blank" rel="noopener"`), so the game stays where it was. Before this, FAQs was only reachable through Settings → Account details → the account page footer, and not at all offline.

## Where it sits, and why not a "Help" section

My first version added a small "Help" section (`h3` + `.lnk`) under Account. At 1280×720 online it didn't fit:

- The panel body (`.set-b`) has no scroll, and Audio, Coach stats and Account already fill it.
- Measured: the Account section ends at y=694, while the body's content area ends at y=660 (body bottom 676 minus 16px padding).
- A Help section landed at y=712–784, under the panel footer and partly off screen, and a click on it missed the link.

So the link sits in the **panel footer bar** (`.set-f`), left side, before the build label. The Online/Offline indicator stays on the right.

- **Always present:** the footer is rendered once in `build()`, and the offline profile only rewrites the Account section. So the link shows in both modes and costs no height.
- **Style:** the existing `.lnk` style (same as "Account details": `--text-60`, `--fs-12`, semibold, `→`, hover to `--text-100`). No new colours.
- **Focus:** the global `.gob a:focus-visible` ring (2px `--white`) shows it when tabbed to.
- **New CSS:** one rule, `.gob .set-f-l{display:flex;align-items:center;gap:var(--space-12);min-width:0}`, groups the link with the build label. Tokens only.

**Existing issue, not fixed:** at 1280×720 online, the Log Out button is already about 34px under the panel footer, because `.set-b` overflows and doesn't scroll. That's visible in `settings-online-1280x720.png`. It's outside this task; `overflow-y: auto` on `.set-b` would fix it.

## Offline (desktop / loopback)

- **Is `faqs.html` served by the loopback?** Yes. Verified against the real loopback server (`playwright.desktop.config.js`, `seed_and_serve_desktop.py`): `GET /faqs.html` returns 200. The desktop engine runs the backend from the repo checkout, so the static pages are all there.
- **Does a new window work in the desktop build?** Yes, according to `desktop/main.js`. `setWindowOpenHandler` returns `{ action: 'allow' }` for loopback URLs (`isLoopbackUrl`) and sends everything else to the system browser. `window.open('/faqs.html')` from the game resolves to `http://127.0.0.1:<port>/faqs.html`, so Electron opens it in a child window and the game window keeps its page.
  - Electron itself isn't installed in `desktop/` here, so I verified with Chromium against the loopback: the popup loads `faqs.html` from 127.0.0.1 and the game page URL doesn't change.
- **Caveats in the desktop child window** (report only):
  - `attachNavigationGuards` is attached only to the main window (`main.js:79`), not to child windows.
  - Inside the FAQs window, "← Back to home" goes to the marketing homepage in that same window. External links (YouTube, X) aren't handed to the system browser the way they are from the main window.
  - Closing the FAQs window returns the user to the game, which was never left.
- No same-window fallback was needed, so nothing about the flow changed for desktop.

The footer rules from `fix/shell-hide-site-footer` and the content of `faqs.html` are untouched.

## Tests

- `tests/e2e/foundation-settings.spec.js`: two new tests, "settings footer links FAQs in a new tab online" and "… offline" (desktop profile). Each checks that:
  - the link is visible and actually hit-testable (not covered, inside the viewport), with class `lnk`, `href="/faqs.html"`, `target="_blank"` and `rel` containing `noopener`;
  - it can be reached with Tab and matches `:focus-visible` with a 2px solid outline;
  - clicking opens a popup on `/faqs.html` with its `h1` visible, and the game page URL doesn't change;
  - offline, the offline note and the "Offline" label show alongside it.
- New `tests/e2e/desktop-settings-faqs.spec.js` (desktop config only; the main config ignores `desktop-*.spec.js`): against the real loopback on port 8157, `/faqs.html` returns 200, and the Settings link opens it from 127.0.0.1 in a new window while the game page stays put.

Runs (port 8157, workers=1, CI unset):

- `foundation-settings`: 7 passed.
- `desktop-settings-faqs` (`-c playwright.desktop.config.js`): 1 passed.
- `shell-1`, `shell-1b`, `shell-2`, `shell-site-footer`: 36 passed.
- Full suite (`tests/e2e`, run after `ps` showed no other agent's Playwright): 531 passed, 3 skipped, 7.7 minutes. All 3 skips are environment-gated: `t3-detail:633` needs the offline loopback, `office-frontend:814` needs a live digest dump, and `tournament-view:267` (new on develop with the tournament-view merge) needs `TOURNEY_OFFLINE_BASE`. The server stopped afterwards; nothing is listening on 8157.

Screenshots (1280×720, FAQs focused by keyboard):

- `reports/settings-faqs/settings-online-1280x720.png`
- `reports/settings-faqs/settings-offline-1280x720.png`

Regenerated report images were restored, and the untracked suite folders were removed.

STATUS: COMPLETE
