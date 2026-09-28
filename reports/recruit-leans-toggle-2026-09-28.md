# Recruiting pool: Leans toggle and the week-20+ default (2026-09-28)

Branch: `fix/recruit-pool-leans-toggle` (from origin/develop 649a75123). Commit: 0de0341fe.

## Result

- The pool's Views row is back to three buttons: **Leans · Watchlist · Unranked by me**. Leans uses the same `viewBtn` style and on/off behaviour as Watchlist, with a count of the recruits leaning to the user.
- From week 20 the pool lands on **all recruits in the user's region, with Leans off**, in both the focus flow (Edit / Review Recruit Invites) and the browse hub. Nothing jumps to Leans any more. The Leans toggle is the way in and out, including in the focus flow, where there is no underline row.
- The underline Leans tab (browse) and the toggle are the same state. There is no second copy that could disagree.
- Frontend only (`FrontEnd/static/recruiting-hub.js`). No backend or payload change. The board (`renderDock`), visits calendar, signing day and results bodies are untouched.

## Behaviour

**One view at a time.** I kept the existing single-view model. Leans, Watchlist and Unranked by me are mutually exclusive: turning one on turns the others off, and clicking the one that's on clears it. Each view still combines with the region, position, year and search filters. So in the user's region, Leans shows only that region's leaners; with All regions it shows every leaner.

**Leans is the hub's `leans` view.** The toggle doesn't add a new flag. Toggle on is `publishHub('leans')`, and toggle off is `publishHub('pool')`.
- In browse, turning the toggle on selects the underline Leans tab (URL `hub=leans`). Turning it off, or turning on Watchlist or Unranked, selects Pool.
- Clicking the Leans tab lights the toggle and clears Watchlist or Unranked. Clicking the Pool tab turns the toggle off.
- The URL still changes by `replaceState` only, so no history entries are added.

**Landing rules** (`applyLandingFilters`, when not coming back through browser history):

| Situation | Landing |
|---|---|
| URL has `?hub=pool` / `leans` / `visits` | That view, as before |
| Week 20 and later, wherever the pool shows (invite weeks 20–26, weeks 27–34) | Region = the user's region, Leans off. If the user's region is unknown, All regions. |
| Before week 20, someone leans to the user | Leans on, All regions (unchanged) |
| Before week 20, nobody leans to the user | Region = the user's region, Pool (unchanged) |

Signing day (35) and results (36+) have no pool.

**Back/forward restore.** The saved filters (`sessionStorage`, `filterStorageKey`) now store `view: 'leans'` whenever Leans is on, whether from the toggle or the tab. Before this change `view` only ever held the Watchlist/Unranked value, so the existing restore path for `saved.view === 'leans'` could never fire in the focus flow. Going back to the page restores Leans together with region, position, year and search. A fresh visit, not through history, lands on the default again.

**Counts.** "Showing N of M" is the filtered count, including Leans. The "· no filters" suffix only shows when nothing is active, and Leans counts as a filter.

## FAQs footer on the focus-flow page (report only, not fixed)

- **What injects it:** `js/shared/authBarInit.js`. `createFooterHTML` / `injectFooter` (lines 865–878) append `<footer id="site-footer">` with a white background (`css/auth-bar.css` `.site-footer`) to `<body>`. `authBarInit.js` is loaded by `js/shared/authGuard.js` (line 203) on every page not listed in `PAGES_WITHOUT_AUTH_BAR`. The shell hides `#auth-bar` (`gob-shell.css:62`) but not `#site-footer`.
- **Why it shows on the focus recruiting page:** the shell's `adoptMain` (`js/shared/gobShell.js:1081`) moves every body child into the scrolling `#gob-main` when it mounts. The recruiting focus flow mounts late, because it waits for the command-center data to decide focus (`GOBAdvance.ordersAreFocus`). By then the footer is usually already in the body, so it gets moved into `#gob-main` and appears as a full-width white bar at the end of the scroll.
  - Measured at 1280×720: the footer sits at y=2433 inside `#gob-main` and is fully visible (43px) after scrolling to the bottom.
  - The ordering is inferred from where the footer ends up; I didn't trace script timing.
- **Other focus pages** (same probe, 1280×720, scrolled to the bottom):
  - **cut-players, training-squad-report, playbook-report:** the footer is in the DOM but stays after `.app`, at y=720, so it never shows.
  - **training-playbooks:** no footer found.
  - **set-lineup:** no footer, because it's in `PAGES_WITHOUT_AUTH_BAR`.
  - **Browse recruiting:** the footer stays at y=720 and never shows.
- **Summary:** only the recruiting focus flow shows the bar. The likely fix is to have the shell remove or hide `#site-footer` (like `#auth-bar`), or have `adoptMain` skip it. Not done here.

## Tests

`tests/e2e/recruiting-tabs.spec.js`

- New test: "week 21 focus flow lands on the region pool, and Leans toggles to leaners and back". It runs at 1280×720 and 1920×1080 with 14 recruits over regions A–E, 10 of them leaning to the user.
  - The focus page has no underline tabs, and the views are ordered leans, watch, unranked.
  - It lands on region C with Leans off: 3 of 14 shown, and the Leans count reads 10.
  - With Leans on, only the 2 region-C leaners show ("Showing 2 of 14"). With All regions and Leans on, all 10 leaners show.
  - Watchlist and Leans switch each other off. With Leans off again, all 14 show with "· no filters".
  - Back-navigation restores Leans and All regions. A fresh visit lands on the default again.
- New test: "browse hub keeps the Leans tab and the Leans toggle in sync".
  - Turning the toggle on selects the Leans tab (`hub=leans`); the Pool tab turns the toggle off.
  - The Leans tab turns the toggle on and clears Watchlist; turning on Unranked selects the Pool tab.
  - Clicking the toggle on and off leaves Pool selected (`hub=pool`), and back-navigation restores the Leans tab and toggle.
- Updated tests:
  - The week-22 invite test now lands on Pool (2 rows), and the Leans tab narrows the pool to 1.
  - The week-21 processed-week test lands on Pool, then opens Leans for its existing screenshots.
- `tests/e2e/shell-1b.spec.js`: the week-7 landing still opens Leans. The assertion that there's no Leans button is replaced by one checking that the toggle is pressed.

Runs (port 8157, workers=1, CI unset):

- **Recruiting-related specs:** recruiting-tabs, recruits-pool, recruiting-draft, recruiting-button-state, recruit-visit-modal, fcc-recruiting-buttons, fcc-recruiting-layout, shell-1b, invite-board, invite-board-layout, invite-seed-modal, invite-visit-calendar and signing-day-hub. 172 passed.
- **Full suite** (`tests/e2e`, run after `ps` showed no other agent's Playwright): 518 passed, 2 skipped (environment-gated), 7.7 minutes. The server stopped afterwards; nothing is listening on 8157.

Screenshots in `reports/recruit-leans-toggle/`, scrolled to the pool filter bar:

- `focus-w21-default-1280x720.png`, `focus-w21-default-1920x1080.png`: region C, Leans off.
- `focus-w21-leans-1280x720.png`, `focus-w21-leans-1920x1080.png`: All regions, Leans on.

Regenerated report images, including `reports/recruiting-tabs/`, were restored, and the untracked suite folders were removed.

STATUS: COMPLETE
