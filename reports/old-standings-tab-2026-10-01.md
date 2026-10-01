# Old `#standings-tab` panel (2026-10-01)

**Status: ready for review.** Branch `chore/old-standings-tab`, pushed. Not merged.

**Verdict: unreachable through the app, so it is deleted.** One thing I added beyond your list, and one thing I kept; both are flagged below.

## Can a real user reach `#standings-tab` today?

On develop (the build this would ship in): **no rail item, nav control, link or redirect leads to it, online or offline.**

| Route | Result | Evidence |
|---|---|---|
| Rail / sub-tabs | No | `gobShell.js` `SECTIONS` lists `standings-view` under League. `standings-tab` is only in `TAB_SECTION` (a lookup, not a control). |
| Old tab bar button | No | The button exists, but `franchise-command-center.html` is `class="gob gob-shell"` in static markup and `gob-shell.css:69` sets `html.gob-shell #franchise-container .tab-buttons { display: none !important }`. Nothing removes `gob-shell`. |
| Links in the app | No | Every link that sets `tab=` uses a live id (`standings-view`, `rankings-view`, …). `standings.html` redirects to `tab=standings-view`. No file writes `standings-tab` into a URL. |
| `return_tab` round trips | No | Every producer passes a live id. The old panel's own links passed `standings-view`. |
| Scripts | No | No `CommandCenterTabs.show('standings-tab')` anywhere in `FrontEnd`. The only caller was the spec. |
| Backend redirects, moment links | No | `BackEnd` builds `tab=tournament-view` and `tab=news-view` only. |
| Desktop / offline | No | Same html and same shell. `desktop/` builds no command-center tab link. Desktop reads the tab from the session context instead of the URL, which matters for the caveat below. |
| Default tab | No | `initCommandCenterTabs` falls back to `standings-tab` only when no default is passed. Its one caller passes `home-tab`. |

```
$ git grep -n 'standings-tab' 365546436 -- FrontEnd BackEnd desktop scripts
FrontEnd/static/franchise-command-center.html:93:        <button data-tab="standings-tab">Standings</button>
FrontEnd/static/franchise-command-center.html:123:      <div id="standings-tab" class="tab-content">
FrontEnd/static/js/shared/commandCenterTabs.js:27: * @param {string} options.defaultTab - Tab id to show when URL has no tab param (e.g. 'standings-ta
FrontEnd/static/js/shared/commandCenterTabs.js:31:  var defaultTab = options.defaultTab || 'standings-tab';
FrontEnd/static/js/shared/gobShell.js:79:    'standings-tab': 'league',
FrontEnd/static/js/shared/views/detailBar.js:13:  'standings-tab': 'Standings',
FrontEnd/static/team-roster-view.js:31:const returnTab = urlParams.get('return_tab'); // 'standings-tab' or 'schedule-tab'
```
```
$ git grep -n -E "show\('standings-tab'|tab=standings-tab|'standings-tab'\)" 365546436 -- FrontEnd BackEnd desktop scripts   # anything that navigates to it
(no output)
```
```
$ git grep -n 'tab-buttons' 365546436 -- FrontEnd/static/css/gob-shell.css FrontEnd/static/franchise-command-center.html
FrontEnd/static/css/gob-shell.css:69:html.gob-shell #franchise-container .tab-buttons {
FrontEnd/static/franchise-command-center.html:2:<html lang="en" class="gob gob-shell">
FrontEnd/static/franchise-command-center.html:85:      <div class="tab-buttons">
```

### The caveat: stale addresses

The only way in is an address that already says `tab=standings-tab`. That is not hypothetical:

| Fact | Evidence |
|---|---|
| Production still serves the old tab bar | `origin/main` (last merge 2026-09-23) does not contain the shell commit `47fd0cb02` (2026-09-25). Its `franchise-command-center.html` has no `gob-shell` and has a visible `<button data-tab="standings-tab">Standings</button>`. |
| Clicking it writes the tab into the address | `commandCenterTabs.js` on main does `bag.set('tab', tabName)` and pushes it. |
| So after the shell deploys | A reload, a bookmark, browser history or the desktop session context (it stores every URL key, `tab` included) can carry `standings-tab` into the new build. Before this branch that showed the old panel inside the new shell. |

That is a stale address, not a route through the app, so I treated the panel as unreachable. But deleting it without handling those addresses would have dropped them on the Office (or on a blank page while the hidden button still existed). Hence the remap below.

## What changed

| File | Change | Lines |
|---|---|---|
| `franchise-command-center.js` | `buildTeamLink`, `buildStandingsCard`, `bindStandingsRegionButtons` (it had no caller and no `.standings-region-btn` exists) and the two lines that set `#standings-full-link` removed. `renderStandings(data)` keeps only the record label and the id → name map; its two callers lose the unused region argument. | +5 / −136 |
| `franchise-command-center.html` | The `#standings-tab` panel (6 lines) removed. | −6 |
| `recruiting-common.js` | `recruitRtClass` and its export removed (still unused, grep below). | −8 |
| `js/shared/commandCenterTabs.js` | **Added, not on your list:** `standings-tab` → `standings-view` in `canonicalTab`, next to the ten other old tab ids. | +1 |
| `tests/e2e/navigation-fixes-3.spec.js` | The back-navigation test now runs on League › Standings: opens `standings-view`, clicks `#standings-view a.gob-team`, asserts in-app Back and browser Back both return to `tab=standings-view`. Same checks, same fixture. | |
| `tests/e2e/shell-1.spec.js` | The "old tab query opens the new section" row for `standings-tab` now expects `standings-view`, like its neighbours. | |

Before and after:

```
$ git grep -n -E 'buildTeamLink|buildStandingsCard|renderStandings|bindStandingsRegionButtons|standings-region-btn|standings-by-region|standings-full-link|recruitRtClass' 365546436 -- FrontEnd tests
FrontEnd/static/css/button-font.css:1:button:not([data-tab]):not([role="tab"]):not(.tab-button):not(.stab):not(.tb):not(.sbtn):not(.mi):not(.stats-sco
FrontEnd/static/franchise-command-center.css:1220:.standings-region-btn {
FrontEnd/static/franchise-command-center.css:1230:.standings-region-btn:hover {
FrontEnd/static/franchise-command-center.css:1233:.standings-region-btn.active {
FrontEnd/static/franchise-command-center.css:1237:.standings-by-region {
FrontEnd/static/franchise-command-center.css:1338:.fcc-standings-full-link {
FrontEnd/static/franchise-command-center.css:1348:.fcc-standings-full-link:hover {
FrontEnd/static/franchise-command-center.css:1352:/* Tournament tab (week 27+): bracket mount + footer links (inherits .fcc-standings-full-link) */
FrontEnd/static/franchise-command-center.html:124:        <div id="standings-by-region" class="standings-by-region"></div>
FrontEnd/static/franchise-command-center.html:126:          <a id="standings-full-link" class="fcc-standings-full-link" href="#">View Full National St
FrontEnd/static/franchise-command-center.html:199:          <a id="team-stats-full-link" class="fcc-standings-full-link" href="#">See all teams' stats
FrontEnd/static/franchise-command-center.html:211:          <a id="leaders-full-link" class="fcc-standings-full-link" href="#">See all leaders here</a
FrontEnd/static/franchise-command-center.js:921:function buildTeamLink(t) {
FrontEnd/static/franchise-command-center.js:937:function buildStandingsCard(titleText, teams) {
FrontEnd/static/franchise-command-center.js:967:    teamCell.appendChild(buildTeamLink(t));
FrontEnd/static/franchise-command-center.js:1002:function renderStandings(data, selectedRegion) {
FrontEnd/static/franchise-command-center.js:1008:  const container = document.getElementById('standings-by-region');
FrontEnd/static/franchise-command-center.js:1021:      container.appendChild(buildStandingsCard(label, teams));
FrontEnd/static/franchise-command-center.js:1040:    container.appendChild(buildStandingsCard(`Conference ${selectedRegion}${confNum}`, teams));
FrontEnd/static/franchise-command-center.js:1043:  document.querySelectorAll('.standings-region-btn').forEach(btn => {
FrontEnd/static/franchise-command-center.js:1156:function bindStandingsRegionButtons() {
FrontEnd/static/franchise-command-center.js:1157:  document.querySelectorAll('.standings-region-btn').forEach(btn => {
FrontEnd/static/franchise-command-center.js:1162:      if (standingsDataCache) renderStandings(standingsDataCache, region);
FrontEnd/static/franchise-command-center.js:1224:  const standingsFullLink = document.getElementById('standings-full-link');
FrontEnd/static/franchise-command-center.js:1535:    if (standingsDataCache) renderStandings(standingsDataCache, 'A');
FrontEnd/static/franchise-command-center.js:1695:  renderStandings(standingsData, 'A');
FrontEnd/static/franchise-tournament-brackets-render.js:249:    link.className = 'fcc-standings-full-link';
FrontEnd/static/recruiting-common.js:61:  function recruitRtClass(rt, year) {
FrontEnd/static/recruiting-common.js:387:    recruitRtClass: recruitRtClass,
tests/e2e/navigation-fixes-3.spec.js:445:  const teamLink = page.locator('#standings-by-region a').first();
tests/e2e/navigation-fixes-3.spec.js:461:  await page.locator('#standings-by-region a').first().click();
```
```
$ same grep on this branch (HEAD)
FrontEnd/static/css/button-font.css:1:button:not([data-tab]):not([role="tab"]):not(.tab-button):not(.stab):not(.tb):not(.sbtn):not(.mi):not(.stats-sco
FrontEnd/static/franchise-command-center.css:1220:.standings-region-btn {
FrontEnd/static/franchise-command-center.css:1230:.standings-region-btn:hover {
FrontEnd/static/franchise-command-center.css:1233:.standings-region-btn.active {
FrontEnd/static/franchise-command-center.css:1237:.standings-by-region {
FrontEnd/static/franchise-command-center.css:1338:.fcc-standings-full-link {
FrontEnd/static/franchise-command-center.css:1348:.fcc-standings-full-link:hover {
FrontEnd/static/franchise-command-center.css:1352:/* Tournament tab (week 27+): bracket mount + footer links (inherits .fcc-standings-full-link) */
FrontEnd/static/franchise-command-center.html:193:          <a id="team-stats-full-link" class="fcc-standings-full-link" href="#">See all teams' stats
FrontEnd/static/franchise-command-center.html:205:          <a id="leaders-full-link" class="fcc-standings-full-link" href="#">See all leaders here</a
FrontEnd/static/franchise-command-center.js:923:function renderStandings(data) {
FrontEnd/static/franchise-command-center.js:1404:    if (standingsDataCache) renderStandings(standingsDataCache);
FrontEnd/static/franchise-command-center.js:1564:  renderStandings(standingsData);
FrontEnd/static/franchise-tournament-brackets-render.js:249:    link.className = 'fcc-standings-full-link';
```

## Two things to confirm

| # | Item | What I did | Alternative |
|---|---|---|---|
| 1 | **The remap line.** Not in your list. Without it an old `?tab=standings-tab` address lands on the Office. With it, it opens League › Standings. `shell-1.spec.js` proves it: the row fails with the line removed. | Added. | Drop the line and the `shell-1` row; old addresses then open the Office. |
| 2 | **The hidden `<button data-tab="standings-tab">` stays.** I removed it first and `tests/test_player_development_grid.py::test_tab_order_is_training_then_recruiting_then_news` failed: it uses that button as its anchor into the tab bar. You named the `#standings-tab` panel markup, not the button, so I put it back. It is hidden, and a click would now go to the live view. The other old buttons (`roster-tab`, `coaches-tab`, `schedule-tab`, …) sit in that bar the same way. | Kept. | Remove it and re-anchor that Python test. |

A second spec depended on the old panel, not only `navigation-fixes-3`: the `shell-1` row above asserted that `?tab=standings-tab` shows `#standings-tab`. My last report missed it.

## Not done (follow-ups)

| Item | Why |
|---|---|
| Dead rules in the frozen `franchise-command-center.css` | Now with no html or js user: `.standings-region-btn` (3 rules), `.standings-by-region`, `.fcc-standings-card`, `-card-title`, `-card-body`, `.fcc-standings-row` (2), `-row-header`, `.fcc-standings-col-team` / `-stat` / `-next`, `.fcc-standings-footer-link-wrap`. Not on your list, and removing them means lowering the freeze ceilings. `.fcc-standings-full-link` is still used (two links and the bracket renderer). |
| `'standings-tab'` entries in `gobShell.js` `TAB_SECTION` and `detailBar.js` `PAGES` | Kept on purpose: a stale `return_tab=standings-tab` on a team or player page still lights League and reads "Standings". |
| `defaultTab \|\| 'standings-tab'` fallback in `commandCenterTabs.js` | Never taken; shared-module default. Left. |
| `tests/e2e/zz-tb-debug.spec.js` | Still on disk. `rm` is denied to me. Untracked, comment-only. |

## Gates (on `cba704394`: this work + develop `46d1891f9` merged in)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | exit 0. **4298 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (231s). First run on my first commit: 1 failed (item 2 above), fixed, re-run green. |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** (no pipe). New-surface hits 0 / 0 / 0. Legacy 446. |
| `scripts/ci/check_migration_gates.py` | **exit 0**. Gate A 0 / 0; Gate B 134 lines / 43 files. |
| Full Playwright, one run under `/tmp/gob-full-playwright.lock`, `--workers=1`, `CI` unset, port 8017 | exit 0. **825 passed, 7 skipped, 0 failed** of 832 (13.8m). Lock taken 14:17:24, released 14:31:14. |
| Failure re-runs at `--repeat-each=5` | none needed |

Targeted before the gates: `navigation-fixes-3`, `shell-1`, `standalone-roster`, `navigation-history` 24/24; the two changed tests 10/10 at `--repeat-each=5`.

The Playwright run was one tracked job that took and released the lock itself while I blocked on it (the foreground limit is 10 minutes; the suite takes about 14).

Merge: develop moved once while I worked (design-rulings docs and a brand chapter, no overlap). Merged before the gates, no conflicts; it had not moved again when I pushed.
