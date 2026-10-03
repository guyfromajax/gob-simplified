# Shared chrome on gob tokens + colour law (2026-10-01)

**Status: ready for review.** Branch `ux/shared-chrome-tokens`, pushed. Not merged. Batch 1 of `reports/ux-remaining-map-2026-10-01.md`.

**Visual only.** No auth, session or error-handling logic changed. In the three scripts the edits are style strings, class names and comments.

## Scope change during the task

`account.html` is **not in this branch.** The community pass (`ux/community-tokens`, now on develop) owns it. I discarded my edits with `git checkout -- FrontEnd/static/account.html` when told. Two consequences:

- The switch that page borrows from `auth-bar.css` (`.account-switch`) is kept on **literal** neutral values, so it paints whether or not the host page carries tokens.
- The spec keeps one small check on `account.html` (bar, switch and footer still paint). No account shots are committed. Four stale `*-account-1280/1920.png` files are still on disk in the shots folder, untracked (I cannot delete files).

## The one structural call (please confirm)

Tokens are scoped to `.gob`, but this chrome renders on pages that are not `.gob`. The homepage has the bar in static markup, and I was told not to touch the homepage.

| Change | Why |
|---|---|
| `gob-tokens.css` base selector is now `.gob, .gob-scope, .auth-bar, .site-footer` | `.gob-scope` = the custom properties and nothing else, for injected chrome. `.gob` on those elements would also match `gob-components.css` (`position: relative; overflow: hidden; background`). `.auth-bar` and `.site-footer` are named so static markup on non-gob pages has tokens at first paint, with no script and no homepage edit. |
| `auth-bar.css` starts with `@import url('/css/gob-tokens.css')` | Pages that load the bar sheet but not the tokens (homepage, community) still get them. |

Checked: the homepage bar resolves `--bg-chrome` (spec guard + before/after shot). Alternative if you dislike naming components in the token file: keep only `.gob-scope` and add that class to the bar markup on every host page, which means editing the homepage.

## What changed

| File | Change |
|---|---|
| `css/auth-bar.css` | Bar, tutorials alert, callout, logout, gear, account modal, toast, footer on tokens. Local `--auth-nav-*` palette removed. |
| `js/shared/authBarInit.js` | `gob-scope` on the account modal and toast roots; toast tick uses `currentColor`; one comment. |
| `js/shared/pageLoadOverlay.js` | All inline colours, fonts and sizes on tokens; overlay root gets `gob-scope`. |
| `js/shared/errorHandler.js` | The three error screens on tokens; root gets `gob-scope`. |
| `faqs.html` | `html.gob` + tokens; dark page. |
| `css/legal.css`, `privacy.html`, `terms.html` | Tokens via `body.gob-scope`. |
| `mode-select.css`, `mode-select.html` | Page frame and alpha banner on tokens; body and the static overlay get `gob-scope`. |
| `franchise-select-team.html` | One `<link>` to `gob-tokens.css` so the shared overlay resolves there. Page itself not migrated. |
| `css/gob-tokens.css` | Selector change above. |
| `team-builder.css` | 39 dead selectors removed (2,133 → 1,998 lines). |
| `scripts/check_ui_tokens.py` | `css/auth-bar.css`, `css/legal.css`, `mode-select.css` added to `NEW_DESIGN_CSS`. Every existing entry kept, including develop's `css/community.css`. |
| `UX_System.md` | New "Shared chrome" section; a Lessons bullet on `.gob-scope`. |
| `tests/e2e/shared-chrome-tokens.spec.js` | New, 4 tests. |

Checker counts (colour literals / type literals / law hits):

| File | Before | After |
|---|---|---|
| `css/auth-bar.css` | 90 / 51 / 13 | 43 / 19 / **0** |
| `js/shared/pageLoadOverlay.js` | 16 / 11 / 3 | **0 / 0 / 0** |
| `js/shared/errorHandler.js` | 44 / 26 / 12 | **0 / 0 / 0** |
| `faqs.html` | 5 / 6 / 1 | 0 / 2 / 0 |
| `css/legal.css` | 9 / 11 / 1 | 0 / 3 / 0 |
| `mode-select.css` | 35 / 31 / 2 | 23 / 21 / **0** |
| `css/coach-mark.css` | 11 / 8 / 2 | deleted |

Legacy law hits overall on this tree: **518** (new-design: 0).

## Colour-law choices

| Element | Was | Now | Why |
|---|---|---|---|
| Tutorials callout pill and alert glow | orange | white pill with `--bg` ink; white glow | An unread tutorial is not a save. |
| Account modal accent | orange | neutral | Decoration. |
| Switch on-state | orange gradient | brighter neutral + knob position | Choice control. Matches what the community pass did on its own page. |
| Account toast rail and tick | green | neutral | Same as `GOBToast`: no green, no orange. |
| Site footer link | orange | `--bg` ink on the white strip | Not a save. |
| Page-load pulse bar | green gradient | neutral gradient | A wait is not Advance and not positive data. |
| Error screen heading | orange (yellow on version mismatch) | `--text-100` | An error is not a save. The ❌ / ⚠️ mark stays. |
| Error screen primary button | orange | neutral plate | Same treatment as the in-app Retry. |
| FAQ and legal links | orange | neutral, underlined | Not a save. |
| Alpha banner rail and title | orange | neutral; alert label `--red` | A notice. |

Visible changes beyond colour, all a result of using tokens:

- **FAQ page went from light to dark.** Tokens only have dark surfaces; it now matches Privacy and Terms.
- **The bar is a shade darker** (`#12161c` → `--bg-chrome` `#0d1018`), the same as the shell top bar.
- **Error screens and the FAQ heading use Bebas Neue Pro** (the app display face) instead of Bebas Neue, so text is no longer all-caps.
- **The footer stays a white strip.** I kept it rather than choosing a dark one; say if you want it dark (one rule).

## What I left, on purpose

| Left | Where | Why |
|---|---|---|
| Feedback button, pulse and Feedback modal | `auth-bar.css` | Alpha-feedback surface; violet and the white modal are not law hits. Community pass. |
| Local modal system + Leaders By Team modal | `mode-select.css` | Community panels, as instructed. 23 literals remain there, 0 law hits. |
| `.gob-modal-*` mirror block | `auth-bar.css` | Must render on pages with no tokens. Only its accent changed: neutral at zero specificity (`:where()`), so `resource-pages.css` still wins where it loads. Other modals that rely on this mirror alone now get a neutral accent too. |
| `.account-switch` values | `auth-bar.css` | Literal, see scope change. |
| Static overlay markup in other pages | `court.html`, FCC, others | Their inline `rgba(0,0,0,0.92)` shows until the script restyles it. Not in this batch. |

## Deletes

| Item | Evidence | Done |
|---|---|---|
| `css/coach-mark.css`, `js/shared/coachMark.js` | Final grep: no import, link or class use anywhere; the only other mentions are comments in `set-lineup.js`, `attributeTour.js` and `attribute-tour.css`. | `git rm` |
| `runBaselineInboundTests.html` | Test harness under the published directory; no references. | `git mv` to `tests/harness/` |
| Dead `team-builder.css` rules | No script or markup emits `.footbar`, `.fb-*`, `.stub`, `.toast`, `.alert`, `.al-*`, `.uncapped`, `.commit`, `.c-txt`, `.local`, `.mdl-t/-s/-a/-b`, `.d-warn`, `.warn`. | 39 selectors removed; Team Builder spec still 3/3. |

Not touched, as instructed: homepage, `css/team-picker.css`, `play-builder.html`.

About the harness: it was already broken where it sat (it imports `./AnimationEngine.js`, which is one directory up). It is archived, not runnable, in `tests/harness/`. Its sibling `runFCPHCTTests.html` and 24 `*.test.js` files are still under `FrontEnd/static/js/phaser/animation/tests/`; I moved only the file the brief named.

## Found

1. **The account settings modal is unreachable.** `authBarInit.js` builds it on every page, but nothing calls `openAccountSettingsModal`; the gear opens the Settings panel. Its toast is unreachable too. I restyled both and opened them by hand in the spec. Removing them is a script change, so I left it.
2. **Trailer mode is still on.** `css/fonts.css` imports `css/trailer-mode.css` (added 2026-08-31), which hides the alpha badge, the Feedback button and the alpha banner app-wide. The banner shots un-hide it by force.
3. **`/privacy.html` is used as "the non-gob page" by `tutorials-fte-tokens.spec.js`.** Making it `html.gob` failed that spec, so the legal pages take tokens on `<body class="gob-scope">` instead.

## e2e spec

`tests/e2e/shared-chrome-tokens.spec.js`, 4 tests, computed styles only:

- Bar background is exactly `--bg-chrome` on a tutorial page, Team Builder and the **homepage**; bar and footer are `display: none` under the FCC shell.
- Callout, alert glow, logout, gear, modal accent, switch, toast, footer link, FAQ and legal links, alpha banner, overlay pulse bar and error headings and buttons have no green or orange in colour, background, border, gradient, shadow or filter.
- Overlay background is black at 0.92; FAQ, legal, Home Base and error pages are exactly `--bg`.

**Fails on the old code (verified):** with develop's copies of the 11 chrome files restored, 4 of 4 tests fail. With the migrated files back: 20/20 at `--repeat-each=5`.

Forced states, labelled in the spec: the tutorials callout, the account modal and the alpha banner are not reachable in a normal session today.

## Screenshots (`reports/shared-chrome-tokens/`, `page.screenshot` at scroll 0)

`before-*` from develop `4b1dccfbd`, `after-*` from this branch. 50 files.

| Surface | Stem | Sizes |
|---|---|---|
| Auth bar on a tutorial page | `bar-tutorial` | 1280, 1920 |
| Tutorials callout (forced) | `bar-tutorial-callout` | 1280 |
| Auth bar on Team Builder | `bar-team-builder` | 1280, 1920 |
| Auth bar on the homepage | `bar-homepage` | 1280, 1920 |
| FCC (bar hidden by the shell; unchanged) | `fcc` | 1280, 1920 |
| Account modal, toast (forced open) | `account-modal`, `account-toast` | 1280 |
| FAQ | `faqs` | 1280, 1920 |
| Privacy, Terms | `privacy`, `terms` | 1280, 1920 / 1280 |
| Home Base with alpha banner (forced visible) | `home-base-alpha` | 1280, 1920 |
| Page-load overlay | `overlay-spinner`, `overlay-pulse` | 1280, 1920 |
| Error screens | `error-missing-pointer`, `-missing-truth`, `-version-mismatch` | 1280 |

## Gates (all on `742391eea`: this work + develop `bfd66e649` merged in)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | exit 0. **4298 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (231s) |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** (no pipe). New-surface hits 0 / 0 / 0. |
| `scripts/ci/check_migration_gates.py` | **exit 0**. Gate A 0 / 0; Gate B 134 lines / 43 files. |
| Full Playwright, one run under `/tmp/gob-full-playwright.lock`, `--workers=1`, `CI` unset, port 8017 | exit 0. **816 passed, 7 skipped, 0 failed** of 823 (13.3m). Lock taken 11:55:54, released 12:09:11. |
| Failure re-runs at `--repeat-each=5` | none needed |

Not strictly foreground: the foreground limit is 10 minutes and the suite takes about 13, so it ran as one tracked job that took and released the lock itself while I blocked on it.

Merge: develop was merged once before the gates (one conflict, `UX_System.md`, both sides appended a section; kept both). `check_ui_tokens.py` merged cleanly with every `NEW_DESIGN_CSS` entry present. Develop had not moved again when I pushed.

XPASS (unchanged, not from this work): `test_leaders_view_scope_filters_to_user_conference`, `test_settings_loaded_and_applied_to_gameplay`.

## Leftovers in the worktree (not committed)

- `tests/e2e/zz-tb-debug.spec.js`: my scratch file, comments only, no tests. Delete it.
- Four stale `reports/shared-chrome-tokens/*-account-1280/1920.png` shots from before the scope change. Delete them.
- About 255 tracked `reports/**` images of other tasks show as modified from Playwright runs. `git checkout -- reports/` restores them.
