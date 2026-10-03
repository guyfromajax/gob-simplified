# Settings panel body scroll — 2026-09-28

Branch: `fix/settings-panel-scroll` (from origin/develop 747bb57f8). Fix commit 677dd7f04.

## Outcome

The Settings body (`.set-b`) is now the panel's own scroll area. At 1280×720 online, Log Out
scrolls into view inside the body. It is hit-testable and sits fully above the footer, and clicking it
logs out (POST `/api/auth/logout`, then `/mode-select.html`). The header and the `.set-f` footer
(FAQs link, Online/Offline) stay pinned. When content fits there is no visual change: the section
positions match the old CSS at every size checked.

## Change (gob-components.css, tokens only)

- `.gob .set-b` adds `overflow-y:auto; overscroll-behavior:contain`. It already had `flex:1; min-height:0`
  in the `.settings` flex column, so it can shrink below its content and scroll.
- `.gob .set-h` and `.gob .set-f` add `flex:none`, so the 56px header and 44px footer never shrink when
  the body overflows.
- `.gob .set-b::-webkit-scrollbar*` copies the existing `.main.scroll` scrollbar (10px, `--line-strong`
  thumb, `--radius-6`, transparent track), so the only scrollbar style in the app is reused.
  `overflow-y:auto` shows no scrollbar when content fits.

No markup or JS change.

## Measurements (mode-select, Settings open)

"overflow" is `scrollHeight - clientHeight` of `.set-b`. The before value excludes the bottom
padding (no scroll container then); after, the 16px bottom padding is part of the scroll range.

| Case | Overflow before → after | Header / footer | Sections vs before |
|---|---|---|---|
| online 1280×720 | 18 → 34 | 57–113 / 676–720 | identical |
| online 1920×1080 | 0 → 0 | 57–113 / 1036–1080 | identical |
| online 1280×600 | 138 → 154 | 57–113 / 556–600 | identical |
| offline 1280×720 | 0 → 0 | 57–113 / 676–720 | identical |
| offline 1920×1080 | 0 → 0 | 57–113 / 1036–1080 | identical |
| offline 1280×600 | 0 → 1 | 57–113 / 556–600 | identical |

Notes:
- Offline at 1280×600 the content plus bottom padding is 1px taller than the body, so a real
  browser will allow a 1px scroll there. Nothing is hidden: the offline note is fully visible.
- Headless Chromium hides scrollbars (gutter measured 0). In a desktop browser the 10px themed
  scrollbar appears only in the overflow cases (online 1280×720, online 1280×600, and the 1px offline case).

## Tests (tests/e2e/foundation-settings.spec.js)

- **the settings body scrolls so Log Out is reachable at 1280x720, footer pinned** (online):
  - `.set-b` has `overflow-y:auto`, and the content overflows.
  - After `scrollIntoViewIfNeeded` and scrolling to the bottom, Log Out passes the `elementFromPoint`
    hit test, lies inside the `.set-b` box and above `.set-f`, and is at least 24px tall.
  - `scrollTop` equals the overflow.
  - The header and footer boxes are unchanged after scrolling.
  - The FAQs link stays hit-testable inside the footer.
  - Takes the screenshot, then clicks Log Out and asserts the logout POST and the `/mode-select.html` landing.
- **the settings panel keeps its frame online and offline at three sizes**: at 1280×720, 1920×1080 and
  1280×600, both online and offline:
  - the header is at the panel top and the footer at the panel bottom, with the body exactly
    between them (56px header, 44px footer);
  - the FAQs link is hit-testable;
  - there's no scrollbar gutter when content fits;
  - after scrolling to the bottom, the last item is inside the body.

  It writes `reports/settings-scroll/after-metrics.json`. `SETTINGS_PHASE=before` records without
  asserting, which gave `before-metrics.json` against the old CSS.

Runs (UX §8, workers=1, port 8157, CI unset):
- foundation-settings + shell-1 + shell-1b + shell-2 + shell-site-footer: **45 passed**.
- Full suite (run when `ps` showed no other Playwright): **533 passed, 3 skipped**. The skips are
  the known environment-gated ones (t3-detail, office-frontend, tournament-view).
- Server on 8157 stopped (no listener). Regenerated report images restored; the tree is clean.

## SELF-CHECK (screenshots opened)

- `reports/settings-scroll/settings-online-1280x720-bottom.png`: the body is scrolled to the bottom (the
  Audio heading is clipped at the top under the header). Visible: Coach stats (12-5, 3 titles),
  Account (username, email, "Account details →") and the **Log Out** button fully visible, with a
  gap above the footer. The footer shows **"FAQs →"** on the left and **"● Online"** on the right. The
  "Settings" header is intact.
- `reports/settings-scroll/settings-online-1280x600-bottom.png`: scrolled further (it starts at Sound
  Effects). Log Out is fully visible above the footer, and the FAQs/Online footer is pinned at the bottom.
- `reports/settings-scroll/settings-offline-1280x600-bottom.png`: Audio, Coach stats and Account with
  the offline note "Playing offline. Account settings return when you're back online." All
  visible, with no Log Out (as designed). The footer shows "FAQs →" and "○ Offline".
- The icon buttons render as blank squares because the icon font doesn't load in the test
  environment. This was already the case before this change.

STATUS: COMPLETE
