# App router — Rankings pilot

League › Rankings is a module view inside `franchise-command-center.html`. The sub-tab switches in place. `rankings.html` redirects and keeps the old query.

## View system

`js/shared/gobViews.js` is a registry of view id → `{ section, subtab, title, module, mount, unmount }`. `module` is a lazy `import()`. `mount(container, ctx)` receives `franchiseId`, `teamId`, `GOBStore`, and `GOBNav`, and returns `{ unmount, revalidate }`.

In-page tabs are unchanged. A module view loads the first time it opens, stays mounted, and is shown again from that panel. The URL is `franchise-command-center.html?tab=<view-id>`, the same rule as today's tabs. Rail clicks still push. Sub-tabs still replace. Back restores the view and the scroll `GOBNav` already stores.

First open paints a neutral skeleton in the view (no spinner) and reads `GOBStore.get`. Re-open shows the mounted panel and calls `GOBStore.revalidate` (`cache: 'no-store'`, `If-None-Match`). The table re-renders only when the rankings body changed. A failed or unknown module paints a quiet error card with Retry in that panel.

How to add the next view is in `UX_System.md` §14: move the read onto a browse GET the store already caches, add `js/shared/views/<name>View.js`, register it, add an empty tab panel and a shell sub-tab, redirect the old page, update the section map, and cover navigation, skeleton, failure, history, and a week-advance refresh.

## Rankings

View id `rankings-view`. Same card as the old page: National Rankings, Top 25 / All 128, Team / W-L / Last Week / Next, conference-1 color, team links to `team-roster-view.html` with `return_tab=rankings-view` and `data-return`. The user's team row is highlighted. The All 128 choice is kept in `sessionStorage` so Back after a full load still has a tall page. Data is the command-center `rankings` array already in `GOBStore`. No new endpoint.

The League sub-tab Rankings calls `CommandCenterTabs.show('rankings-view', 'replace')`. `rankings.html` copies the query, sets `tab=rankings-view`, and `location.replace`s.

The command center now measures `--gob-stick-top` the way standalone browse pages already did, and the rankings header uses that offset so it pins under the League sub-tabs.

## Files

- `FrontEnd/static/js/shared/gobViews.js` — registry, skeleton, error card
- `FrontEnd/static/js/shared/views/rankingsView.js` — Rankings module
- `FrontEnd/static/css/gob-views.css` — skeleton, error card, rankings table inside `.main`
- `FrontEnd/static/css/gob-components.css` — page head stacks above scrolled `.main` children
- `FrontEnd/static/franchise-command-center.html` — `#rankings-view` panel, stylesheet, script
- `FrontEnd/static/js/shared/commandCenterTabs.js` — known tabs include registered views
- `FrontEnd/static/js/shared/gobShell.js` — League Rankings is in-page; command center measures the sticky offset
- `FrontEnd/static/js/shared/gobStore.js` — `revalidate`
- `FrontEnd/static/js/shared/gobNav.js` — Back/Forward restore scroll when the load is not from the back-forward cache
- `FrontEnd/static/rankings.html` — redirect
- `_documentation_master/11_Design_Systems/UX_System.md` — §7, §9, §14
- `tests/e2e/app-router.spec.js`, `tests/e2e/shell-1b.spec.js`, `tests/e2e/shell-2.spec.js`

## Timings

Click to the rankings table, then the second open of the same view. The office load had already filled the store, so the first open did not fetch another command-center body. The second open sent no command-center response.

| Viewport | First open | Second open | Revalidate |
| --- | --- | --- | --- |
| 1280×720 | 146 ms | 8 ms | none |
| 1920×1080 | 116 ms | 8 ms | none |

## History

Document identity (stamp and navigation-entry count) stayed the same for every in-page switch.

1. Office (`tab=home-tab`).
2. Rail League: push. URL `tab=standings-tab`. `gobIdx` increases.
3. Rankings: replace. URL `tab=rankings-view`. `gobIdx` unchanged. 25 rows, Lancaster highlighted.
4. Standings: replace. No command-center request.
5. Rankings: replace. Second open, no new body.
6. All 128, scroll, team link: document navigation to `team-roster-view.html` with `return_tab=rankings-view`.
7. Back: Rankings view, scroll within 2 px of the saved position, same `gobIdx` as the League push.
8. Back: Office (`tab=home-tab`). Rankings had replaced the League entry.
9. Forward: `tab=rankings-view`.

`rankings.html?franchise_id&team_id&return_url&return_tab` lands on the command center with those params and `tab=rankings-view`. A team page whose `return_url` is `/rankings.html?...` goes Back to that same view with both ids.

Week advance: `POST /franchise/complete-week` drops the franchise cache through `GOBStore.mutate`. The next load of `?tab=rankings-view` shows the new week's rankings (fixture first row Beta State).

One vertical scroller (`.main`). No horizontal overflow of `.main` at 1280×720 or 1920×1080. Throttled first module load shows the skeleton and no spinner. A forced module 500 shows the error card; Retry loads the module.

## Tests

- `app-router.spec.js`: 4 passed (history, skeleton, failed module + Retry, redirect and return params).
- Required suite on the in-page Rankings contract, before the command center measured the sticky offset: 76 passed, 1 failed. The failure was shell-2 sticky headers on `rankings.html`, which now opens inside the command center, and that mount path never set `--gob-stick-top`.
- After that measure, and after the rankings header used it: shell-2 sticky passed; office-frontend six states fit passed; `shell-1`, `shell-1b`, `shell-2`: 26 passed; `app-router.spec.js`: 4 passed.
- `store-client`, `navigation-history`, `navigation-fixes-3`, `game-start-sequence`, and `foundation-settings` passed in the 76. They were not re-run after the sticky-offset change.

## Flagged

- The second open was instant and produced no command-center response in this Chromium (`none`, not a 304). `revalidate` still sends `cache: 'no-store'` and `If-None-Match`.
- A same-document revalidate of a command-center URL this browser had already stored did not reach the test route, so the week-advance fixture is the store write plus the next load, matching `store-client`'s week-advance test.
- The rankings card keeps the current look. The T1 template restyle is later.
- The command center now classifies tables and sets the sticky offset, which standalone browse pages already did.

## Pre-merge

Re-ran the suites that had not run since the command center started measuring `--gob-stick-top`: `store-client`, `navigation-history`, `navigation-fixes-3`, `game-start-sequence`, `foundation-settings`. 36 passed, 1 failed. The failure was `navigation-fixes-3` "end-of-game box score exit returns to the locker room": Back landed on `franchise-command-center.html?tab=home-tab` instead of mode-select. The same test passed alone in 33.6s. No code change.

Merged `origin/develop` into `app/router` (`6b84b213d`). The only conflict was `UX_System.md`. Leader qualification stays §13, with its text unchanged. The view system is §14. The §13 mentions in this report now point at §14. No code comment referred to the view section by number.

After the merge, `app-router.spec.js`, `shell-1`, `shell-1b`, and `shell-2`: 30 passed.

STATUS: COMPLETE
