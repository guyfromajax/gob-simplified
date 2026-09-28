# Shell: hide the legacy site footer (2026-09-28)

Branch: `fix/shell-hide-site-footer` (from origin/develop 5f720f19b). Commit: 875073f56.

## Result

The white "FAQs" footer (`<footer id="site-footer">`, injected by `js/shared/authBarInit.js`) no longer shows anywhere inside the shell (`html.gob-shell`), on browse or focus pages. It can no longer be moved into `#gob-main`, whatever the script timing. Pages outside the shell keep their footers exactly as before.

## Change

- **`FrontEnd/static/css/gob-shell.css`:** `html.gob-shell #site-footer` joins the existing hide rule, next to `#auth-bar`, `#alpha-badge` and friends (`display: none !important`).
- **`FrontEnd/static/js/shared/gobShell.js` `adoptMain`:** skips `#site-footer` the same way it skips `<script>`. If the footer is already in `<body>` when the shell mounts (the recruiting focus flow mounts late, after the command-center fetch), it now stays a direct child of `<body>`, outside `.app`, and is hidden by the CSS rule.
- If the footer is injected after the mount, it lands after `.app` as before, and the CSS hides it.

## Outside the shell (unchanged)

- **Public pages** (homepage, login, signup, reset-password, FAQs, privacy, terms): `authGuard.js` returns early for these paths and never loads `authBarInit.js`, so they never had the injected footer. They keep their own markup.
- **Homepage** (`/homepage.html`): verified that its own `<footer class="footer">` is still visible and the page is not a shell page.
- **FAQs page** (`/faqs.html`): verified that its static `#site-footer` is visible, white, and links to `/faqs.html`.
- **`/account.html`:** a signed-in page outside the shell. Verified that its static `#site-footer`, with the FAQs, Privacy and Terms links, is visible.

## FAQs reachable in-app

There is an existing path, but it's two steps and there's no direct FAQs item in the shell:

1. **Rail → Settings** (or the gear on focus pages) opens the Settings panel (`js/shared/gobSettings.js`).
2. **Account → "Account details"** (`gobSettings.js:273`) goes to `/account.html`.
3. **Its footer links FAQs** (`account.html:164`).

Offline, the Settings panel replaces the Account section with a note, so there's no path to FAQs from the shell while offline. The Tutorials hub and the Feedback item don't link FAQs. No link was added.

## Tests

New `tests/e2e/shell-site-footer.spec.js`:

- **Shell pages:** the recruiting focus flow at week 21 (unsaved board, `html.gob-shell.gob-focus`), the Office, and League › Standings (browse). On each, `#site-footer` is `display: none`, not inside `#gob-main`, has 0 visible pixels after scrolling `#gob-main` to the bottom, and no FAQs link is visible.
- **Timing guard:** each shell page again, with a footer planted in `<body>` at `DOMContentLoaded`, before the shell mounts. It must stay out of `#gob-main` and be hidden.
- **Outside the shell:** the homepage's own footer is visible; `/faqs.html` and `/account.html` show a visible white `#site-footer` with the FAQs link.

Against the old code (fix stashed), all 6 shell-page tests fail. On the recruiting focus flow the footer is inside `#gob-main`; on the others it's still `display: block`. With the fix, all 9 tests pass.

Runs (port 8157, workers=1, CI unset):

- `shell-site-footer`, `shell-1`, `shell-1b`, `shell-2`: 36 passed.
- Full suite (`tests/e2e`, run after waiting for another agent's full run to finish and re-checking `ps`): 527 passed, 2 skipped (environment-gated), 7.7 minutes. The server stopped afterwards; nothing is listening on 8157.

Regenerated report images were restored, and the untracked suite folders were removed.

STATUS: COMPLETE
