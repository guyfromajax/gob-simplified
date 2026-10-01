# FCC dead code (2026-10-01)

**Status: ready for review.** Branch `chore/fcc-dead-code`, pushed. Not merged.

**Two of the three items are removed. The third, `buildTeamLink`, is not dead, so I left it.** Details below.

## Result

| Item | Done | Lines |
|---|---|---|
| `showDevSimPopup` + its commented-out call block (`franchise-command-center.js`) | Removed | −360 |
| `RecruitingCommon.renderRecruitTableRows` + its export + the two private helpers only it used, `posChipHtml` and `rtLockupHtml` (`recruiting-common.js`) | Removed | −104 |
| `buildTeamLink` + the old `#standings-tab` renderer | **Not removed** | 0 |

No behaviour change. No backend, sim, finalize, `cpu_week_pool` or `sim_rng` file touched. No css touched.

## 1. `showDevSimPopup`: dead

```
$ git grep -n -E 'showDevSimPopup\(|dev-sim-regular-season|dev_sim_regular_season' origin/develop -- FrontEnd BackEnd tests desktop scripts
BackEnd/api/franchise_routes.py:20377:# @router.post("/franchise/dev-sim-regular-season")
BackEnd/api/franchise_routes.py:20378:# def dev_sim_regular_season(req: DevSimRegularSeasonRequest):
FrontEnd/static/franchise-command-center.js:1708:    // showDevSimPopup(topData);
FrontEnd/static/franchise-command-center.js:2563:function showDevSimPopup(topData) {
FrontEnd/static/franchise-command-center.js:2698:        const response = await fetch(API_CONFIG.buildUrl('/franchise/dev-sim-regular-season'), {
```

| Fact | Evidence |
|---|---|
| The only call is commented out | line 1708 above |
| The endpoint it posts to does not exist | the route decorator and function in `franchise_routes.py` are commented out too, so the popup could only get a 404 |
| Nothing declared inside it is used outside | every name in the block is a local of the function; checked by script |

Removed: the function with its banner comments (343 lines) and the 15-line commented-out call block in `init`. The commented-out backend route is still there (backend was out of scope).

## 2. `renderRecruitTableRows`: dead

```
$ git grep -n -E 'renderRecruitTableRows|posChipHtml|[^.]rtLockupHtml' origin/develop -- FrontEnd BackEnd tests desktop scripts
FrontEnd/static/js/shared/views/scoutingView.js:117:function rtLockupHtml(rt, potentialRt) {
FrontEnd/static/js/shared/views/scoutingView.js:236:    body += '<td class="c">' + rtLockupHtml(r.rt, r.potential_rt_ratcheted) + '</td>';
FrontEnd/static/recruiting-common.js:350:  function posChipHtml(pos) {
FrontEnd/static/recruiting-common.js:355:  function rtLockupHtml(rt, potentialRt, year) {
FrontEnd/static/recruiting-common.js:369:  function renderRecruitTableRows(tbody, recruits, options) {
FrontEnd/static/recruiting-common.js:412:        '<td class="c-rt">' + rtLockupHtml(recruit.rt, recruit.potentialRt, recruit.year) + '</td>',
FrontEnd/static/recruiting-common.js:413:        '<td>' + posChipHtml(recruit.pos) + '</td>',
FrontEnd/static/recruiting-common.js:492:    renderRecruitTableRows: renderRecruitTableRows,
```

| Fact | Evidence |
|---|---|
| No caller anywhere | the only hits are its definition and its export |
| `posChipHtml` and `rtLockupHtml` in `recruiting-common.js` were used only by it | lines 412 and 413 are inside the removed function. They are private to the file's closure, so nothing outside could call them. |
| `rtLockupHtml` in `scoutingView.js` is a different function | separate file, own definition, still used |

Still exported and now unused, **not removed** (public names on `RecruitingCommon`, not in the brief): `recruitRtClass`. Its only users were the removed helpers.

## 3. `buildTeamLink`: not dead, left in place

```
$ git grep -n -E 'buildTeamLink|buildStandingsCard|renderStandings\(|standings-by-region' origin/develop -- FrontEnd tests
FrontEnd/static/franchise-command-center.css:1237:.standings-by-region {
FrontEnd/static/franchise-command-center.html:124:        <div id="standings-by-region" class="standings-by-region"></div>
FrontEnd/static/franchise-command-center.js:921:function buildTeamLink(t) {
FrontEnd/static/franchise-command-center.js:937:function buildStandingsCard(titleText, teams) {
FrontEnd/static/franchise-command-center.js:967:    teamCell.appendChild(buildTeamLink(t));
FrontEnd/static/franchise-command-center.js:1002:function renderStandings(data, selectedRegion) {
FrontEnd/static/franchise-command-center.js:1008:  const container = document.getElementById('standings-by-region');
FrontEnd/static/franchise-command-center.js:1021:      container.appendChild(buildStandingsCard(label, teams));
FrontEnd/static/franchise-command-center.js:1040:    container.appendChild(buildStandingsCard(`Conference ${selectedRegion}${confNum}`, teams));
FrontEnd/static/franchise-command-center.js:1162:      if (standingsDataCache) renderStandings(standingsDataCache, region);
FrontEnd/static/franchise-command-center.js:1535:    if (standingsDataCache) renderStandings(standingsDataCache, 'A');
FrontEnd/static/franchise-command-center.js:1695:  renderStandings(standingsData, 'A');
tests/e2e/navigation-fixes-3.spec.js:445:  const teamLink = page.locator('#standings-by-region a').first();
tests/e2e/navigation-fixes-3.spec.js:461:  await page.locator('#standings-by-region a').first().click();
```

My peel-2 note said it "only feeds the old `#standings-tab` panel". That is true, but the panel is live:

| Fact | Evidence |
|---|---|
| `standings-tab` is a real, known tab | `<div id="standings-tab" class="tab-content">` is in `franchise-command-center.html`; `CommandCenterTabs.canonicalTab` remaps ten old ids and `standings-tab` is not one of them |
| It is shown on request | `?tab=standings-tab` or `CommandCenterTabs.show('standings-tab')` |
| A passing spec depends on the link | `navigation-fixes-3.spec.js:440` "standings team page returns instantly…" opens `standings-tab`, clicks `#standings-by-region a` (the link `buildTeamLink` builds) twice, and asserts Back returns to `tab=standings-tab` |
| The renderer also does live work | `renderStandings` calls `updateTopRecordLabel()` and fills `teamIdNameMap` before it draws the panel |

No in-app control opens that tab under the shell (League opens `standings-view`), so it is reachable only by an old link or by script. Removing it would change what an old `?tab=standings-tab` link shows and would mean rewriting that spec. That is a behaviour change and your call, so I stopped there.

If you want it gone, the change is:

| Step | What |
|---|---|
| 1 | Remap `standings-tab` → `standings-view` in `canonicalTab` (and `gobShell.currentTab`) |
| 2 | Delete `buildTeamLink`, `buildStandingsCard`, the drawing half of `renderStandings` (keep the record label and name map), the region-button handler, the `#standings-tab` markup |
| 3 | Delete the `.fcc-standings-*` / `.standings-*` rules in the frozen FCC sheet and lower the ceilings |
| 4 | Point `navigation-fixes-3.spec.js:440` at the League view's team link |

## After

```
$ git grep -n -E 'showDevSimPopup|dev-sim-|renderRecruitTableRows|posChipHtml' HEAD -- FrontEnd tests desktop scripts
(no output)
```

## Follow-ups this removal creates (not done)

| Item | Why it is now dead |
|---|---|
| `.fcc-newlean-badge` and `--fcc-newlean-accent` in `franchise-command-center.css` | The removed renderer was the only thing that emitted the class. Removing them would shrink the frozen sheet by 2 rules. `fcc-peel-2.spec.js` builds the badge by hand and would need that check dropped. |
| `RecruitingCommon.recruitRtClass` | See item 2. |
| Commented-out `dev-sim-regular-season` route in `franchise_routes.py` | Its only client is gone. |

## Setup notes

- `git checkout -- reports/` done at the start and again before committing (Playwright rewrites tracked shots).
- **`tests/e2e/zz-tb-debug.spec.js` is still on disk.** `rm` is denied to me in this session. It is untracked, comment-only and not committed. Delete it by hand.

## Files

| File | Change |
|---|---|
| `FrontEnd/static/franchise-command-center.js` | −360 |
| `FrontEnd/static/recruiting-common.js` | −104 |

## Gates (on `4daf089ed`; develop had not moved, so the merge was a no-op)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | exit 0. **4298 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (229s) |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** (no pipe). New-surface hits 0 / 0 / 0. Legacy 446. |
| `scripts/ci/check_migration_gates.py` | **exit 0**. Gate A 0 / 0; Gate B 134 lines / 43 files. |
| Full Playwright, one run under `/tmp/gob-full-playwright.lock`, `--workers=1`, `CI` unset, port 8017 | exit 0. **826 passed, 7 skipped, 0 failed** of 833 (13.9m). Lock taken 13:29:56, released 13:43:48. |
| Failure re-runs at `--repeat-each=5` | none needed |

The Playwright run was one tracked job that took and released the lock itself while I blocked on it (the foreground limit is 10 minutes; the suite takes about 14).

No new test: a deletion with no behaviour change has nothing new to assert. The existing suite is the check. Targeted run before the gates: `fcc-peel-2`, `recruiting-tabs`, `fcc-recruiting-layout`, 14/14.
