# Migration gates re-baseline: 2026-09-29

Branch `chore/migration-gates-rebaseline` (based on develop `5f2cb1de8`). Not merged. **Ready for review.**

`check_migration_gates.py` went from **53 violations** (3 Gate A + 50 Gate B; develop had moved on from the 51 in the brief) to **exit 0**.

## Gate A: real fix (3 files)
| File | Before | After |
|---|---|---|
| `BackEnd/utils/browse_cache.py` | `franchise_collection()` did a lazy `from BackEnd.db import db` and returned `db.franchises` | Lazy `from BackEnd.persistence import get_store`; returns `get_store().franchises_collection` |
| `BackEnd/utils/franchise_last_played.py` | Same | Same |
| `BackEnd/utils/schedule_browse.py` | `from BackEnd.db import db, franchise_team_data_collection` | `from BackEnd.persistence import get_store`, then `_store = get_store()`, `db = _store.db`, `franchise_team_data_collection = _store.franchise_team_data_collection`. The module keeps its names, so no query lines changed |

**Why behaviour is identical:**
- `BackEnd/db.py` is a facade: `db = get_store().db`.
- `get_store()` is the process-wide singleton, and both stores bind each `<name>_collection` attribute to the same object as `db[name]` (`mongo.py _bind_collections`, `sqlite.py` L306).
- The two lazy imports stay lazy, so their import ordering is unchanged.
- No test or script monkeypatches these modules' `db` / `franchise_team_data_collection` attributes. The one patch point, `browse_cache.franchise_collection`, is kept.

**Gate A allowlist:** it was already empty and is now clean at 0 imports in 0 files.

## Gate B: classification (144 lines in 50 files)
**Method:** every matching line in the 50 failing files was classified by reading the surrounding code and following the params variable to its `.get` / `.has` / `forEach` calls.

**Classes:**
- **IDENTITY:** reads `franchise_id` / `team_id` / `user_team_id` / `runtime` / `game_id` / `mode` / FranchiseContext-owned keys.
- **UI:** tab, view, return_url, filters and similar only.
- **NONE:** builds an outbound query, logs, or compares strings; reads nothing from the page URL.

**Desktop risk:** on desktop, `SessionContextProvider` keeps identity in localStorage merged with the inbound URL at load. Its `commitParams` never writes the URL, and `runtime` defaults to `'local'` without being in the URL. So a raw URL read misbehaves when a key is session-only or stale in the URL.

**Totals:** 67 UI · 41 NONE · 36 IDENTITY (4 High, 29 Low, 3 None).

| file | line | pattern | params read | class | desktop risk | reason |
|---|---|---|---|---|---|---|
| js/shared/gobNav.js | 74 | location.search | * (copies all), tab | UI | n/a | currentUrl(): full URL used as a stack/scroll key; adds the FCC tab |
| js/shared/gobNav.js | 79 | .searchParams | tab | UI | n/a | currentUrl(): skips adding the tab if one is already there |
| js/shared/gobNav.js | 82 | .searchParams | — (outbound build) | NONE | n/a | sets tab on the currentUrl copy |
| js/shared/gobNav.js | 83 | .searchParams | — (outbound build) | NONE | n/a | serializes the currentUrl copy |
| js/shared/gobNav.js | 155 | URLSearchParams(location.search) | return_url | UI | n/a | returnUrlFromQuery() |
| js/shared/gobNav.js | 165 | URLSearchParams(location.search) | franchise_id | IDENTITY | Low | defaultFallback(): no FC fallback; absent sends to /mode-select; franchise_id is on almost every href |
| js/shared/gobNav.js | 200 | URLSearchParams(location.search) | return_tab | UI | n/a | mergeReturnTab() |
| js/shared/gobNav.js | 204 | .searchParams | tab (of target url) | UI | n/a | reads the passed URL, not the current one |
| js/shared/gobNav.js | 205 | .searchParams | — (outbound build) | NONE | n/a | sets tab on the target URL |
| js/shared/gobNav.js | 206 | .searchParams | — (outbound build) | NONE | n/a | serializes the target URL |
| js/shared/gobNav.js | 228 | URLSearchParams(location.search) | tab | UI | n/a | currentFccTab() |
| js/shared/gobNav.js | 245 | .searchParams | tab (of referrer) | UI | n/a | rememberFlowTabFromReferrer() |
| js/shared/gobNav.js | 251 | .searchParams | — (outbound build) | NONE | n/a | forceTab() sets tab |
| js/shared/gobNav.js | 252 | .searchParams | — (outbound build) | NONE | n/a | forceTab() serializes |
| js/shared/gobNav.js | 259 | .searchParams | tab (of hubUrl) | UI | n/a | resolveExitTab() |
| js/shared/gobNav.js | 292 | location.search | * (copies all) | NONE | n/a | stampIdx(): replaceState with the unchanged same URL; nothing read |
| js/shared/gobNav.js | 499 | URLSearchParams(location.search) | franchise_id | IDENTITY | Low | hubUrlFromExit(): only used without landing.url; absent means the exit recovery is skipped |
| js/shared/gobNav.js | 578 | location.search | * (copies all), tab | UI | n/a | applyExitTab(): replaceState plus absorbLocation, which diffs only tab |
| js/shared/gobNav.js | 579 | .searchParams | tab | UI | n/a | applyExitTab() |
| js/shared/gobNav.js | 580 | .searchParams | — (outbound build) | NONE | n/a | sets tab |
| js/shared/gobNav.js | 581 | .searchParams | — (outbound build) | NONE | n/a | serializes |
| js/shared/gobNav.js | 621 | .searchParams | * (copies all), has(name=action) | UI | n/a | stripParam(): check step; the hazard is at line 625 |
| js/shared/gobNav.js | 622 | .searchParams | — (delete) | NONE | n/a | removes the param from the copy |
| js/shared/gobNav.js | 623 | .searchParams | — (outbound build) | NONE | n/a | builds the next URL (web path only) |
| js/shared/gobNav.js | 625 | .searchParams → commitParams | * (copies all) | IDENTITY | High | Desktop commitParams replaces the session with URL keys, dropping session-only identity. URL never stripped. |
| js/shared/gobNav.js | 702 | .searchParams | — (outbound build) | NONE | n/a | applyReturnUrl() sets return_url on a link href |
| js/shared/gobNav.js | 796 | URLSearchParams(location.search) | game_id, franchise_id | IDENTITY | High | guardClosedFranchiseGame(): no FC fallback; session-only game_id means the guard silently never fires |
| js/shared/gobShell.js | 149 | URLSearchParams(location.search) | tab | UI | n/a | tabFromUrl() |
| js/shared/gobShell.js | 254 | URLSearchParams(location.search) | franchise_id, team_id, mode | IDENTITY | Low | fallbackHref(): no FC fallback, but absent keys are omitted and the target's session merge fills them |
| js/shared/gobShell.js | 255 | new URLSearchParams() | — (outbound build) | NONE | n/a | fallbackHref() builds the output |
| js/shared/gobShell.js | 265 | URLSearchParams(location.search) | franchise_id, team_id, user_team_id | IDENTITY | Low | fccHref(): no FC fallback; absent keys omitted, target session fills; URL value may be stale |
| js/shared/gobShell.js | 266 | new URLSearchParams() | — (outbound build) | NONE | n/a | fccHref() builds the output |
| js/shared/gobShell.js | 309 | URLSearchParams(location.search) | hub | UI | n/a | hubFromUrl() |
| js/shared/gobShell.js | 320 | URLSearchParams(location.search) | * (copies all); sets hub | UI | n/a | recruitingHubHref(): replaceState; absorbLocation diffs only hub |
| js/shared/gobShell.js | 332 | location.search | — (string compare only) | NONE | n/a | replaceRecruitingHub() compares with the current URL |
| js/shared/gobShell.js | 439 | URLSearchParams(location.search) | origin | UI | n/a | detailOrigin() |
| js/shared/gobShell.js | 451 | URLSearchParams(location.search) | return_tab | UI | n/a | detailMark() |
| js/shared/gobShell.js | 687 | .searchParams | tab (navigation entry URL) | UI | n/a | resumePending |
| js/shared/gobShell.js | 938 | URLSearchParams(location.search) | return_tab, return_url, team_id, user_team_id | IDENTITY | Low | sectionFromReturn(): only picks the rail section; defaults to 'team' |
| js/shared/gobShell.js | 957 | URLSearchParams(location.search) | return_url, action, resume_from_timeout, mode | IDENTITY | Low | resolvePage(): mode/resume_from_timeout only choose the focus layout |
| js/shared/gobShell.js | 1431 | URLSearchParams(location.search) | tab | UI | n/a | boot(): prepTab is read but never used |
| js/shared/officeHome.js | 108 | .searchParams | tab (of target url) | UI | n/a | inAppView() |
| js/shared/officeHome.js | 133 | new URLSearchParams() | — (outbound build) | NONE | n/a | href() helper |
| js/shared/officeHome.js | 143 | URLSearchParams(location.search) | franchise_id, team_id, user_team_id | IDENTITY | Low | franchiseHref(): no FC fallback; absent keys omitted, target session fills |
| js/shared/officeHome.js | 159 | URLSearchParams(location.search) | franchise_id, team_id | IDENTITY | Low | playerHref(): only the stub path uses these; GOBTables.viewHref copies the FCC URL |
| js/shared/officeHome.js | 173 | URLSearchParams(location.search) | franchise_id, team_id, user_team_id | IDENTITY | High | teamHref(): with no team_id in URL, team_id becomes the viewed team, overwriting session identity |
| js/shared/officeHome.js | 436 | URLSearchParams(location.search) | franchise_id, team_id, user_team_id | IDENTITY | Low | trainingReportHref(): no FC fallback; absent keys omitted |
| js/shared/officeHome.js | 854 | URLSearchParams(location.search) | franchise_id, team_id, user_team_id | IDENTITY | Low | weeklyHref(): fills gaps only; absent means omitted |
| js/shared/officeHome.js | 857 | .searchParams | franchise_id (current + target) | IDENTITY | Low | weeklyHref() gap check |
| js/shared/officeHome.js | 858 | .searchParams | franchise_id | IDENTITY | Low | weeklyHref() copies franchise_id into the item href |
| js/shared/officeHome.js | 861 | .searchParams | team_id | IDENTITY | Low | weeklyHref() copies team_id into the item href |
| js/shared/officeHome.js | 1086 | URLSearchParams(location.search) | franchise_id, team_id, user_team_id | IDENTITY | Low | standingsHref(): no FC fallback; absent keys omitted |
| js/shared/authGuard.js | 20 | `new URLSearchParams(search)` in shellFocusNavigation | return_url, action, resume_from_timeout, mode | IDENTITY | Low | Only toggles view-transition CSS. mode/resume_from_timeout ride on inbound game-plan hrefs. |
| js/shared/authGuard.js | 117 | `window.location.search` passed to shellFocusNavigation | return_url, action, resume_from_timeout, mode (via line 20) | IDENTITY | Low | Same as line 20. Cosmetic effect only. |
| js/shared/gobAdvance.js | 148 | `new URLSearchParams()` emptyParams fallback | — (outbound build) | NONE | n/a | Empty bag, used only when FranchiseContext is missing. |
| js/shared/gobAdvance.js | 153 | `location.pathname + location.search` currentRelativeUrl | — (outbound build: return_url string) | NONE | n/a | Builds return_url. The session keeps keys that are not in the URL. |
| js/shared/gobAdvance.js | 158 | `new URLSearchParams(location.search).get(name)` queryId | franchise_id, team_id, user_team_id, action | IDENTITY | High | No FranchiseContext fallback. load() gives up without URL franchise_id on every shell page. |
| js/shared/gobAdvance.js | 575 | `window.location.search` in console.log | — (log only) | NONE | n/a | Diagnostic log only. |
| js/shared/gobAdvance.js | 656 | `.get('cc_profile')` | cc_profile | UI | n/a | Debug profiling flag. |
| js/shared/gobStore.js | 70 | `parsed.searchParams.forEach` in canonical() | all keys of the fetch request URL (not the page URL) | NONE | n/a | Builds a cache key from the API request URL. |
| js/shared/gobStore.js | 74 | `new URLSearchParams()` in canonical() | — (outbound build) | NONE | n/a | Rebuilds the sorted cache-key query. |
| js/shared/gobStore.js | 76 | `parsed.searchParams.getAll(key)` in canonical() | all keys of the fetch request URL | NONE | n/a | Request URL, not the page location. |
| js/shared/gobStore.js | 243 | `new URL(url).searchParams.get('franchise_id')` | franchise_id (of the fetch request URL) | IDENTITY | None | Reads the outbound API URL, which callers build with franchise_id. Falls back to the body. |
| js/shared/gobTables.js | 131 | `.get('tab')` currentTab | tab | UI | n/a | Tab routing only. |
| js/shared/gobTables.js | 246 | `new URLSearchParams()` in viewHref (off-FCC branch) | — (outbound build) | NONE | n/a | Empty base when not on the FCC. Changes are set explicitly. |
| js/shared/gobTables.js | 248 | `new URLSearchParams(location.search)` in viewHref | * (copies all) | UI | n/a | Copies the FCC query forward. Same-document nav, so the session keeps absent keys. |
| js/shared/gobTables.js | 249 | catch fallback `new URLSearchParams()` in viewHref | * (copies all), same variable as 248 | UI | n/a | Error fallback of line 248. |
| js/shared/gobTables.js | 269 | `new URLSearchParams(location.search)` in rosterHref | team_id, user_team_id | IDENTITY | Low | Falls back to GOBViews.userTeamId() (URL, then FranchiseContext/FranchiseLS). |
| js/shared/gobTutorialAlerts.js | 549 | `.get('tab')` officeIsCurrent | tab | UI | n/a | Tab check only. Also checks the DOM. |
| js/shared/gobViews.js | 16 | `new URLSearchParams()` init in readParams | franchise_id, team_id, user_team_id (same variable) | IDENTITY | Low | pick() falls back to FranchiseContext.toSearchParams(). The URL wins when present. |
| js/shared/gobViews.js | 18 | `new URLSearchParams(location.search)` readParams | franchise_id, team_id, user_team_id | IDENTITY | Low | Explicit FranchiseContext fallback. The URL takes precedence over the session. |
| js/shared/gobViews.js | 19 | catch fallback `new URLSearchParams()` readParams | franchise_id, team_id, user_team_id (same variable) | IDENTITY | Low | Error fallback. The context still supplies the values. |
| js/shared/gobViews.js | 119 | `new URL(url).searchParams.get('tab')` in open() | tab (of the URL being opened) | UI | n/a | Reads the target URL's tab, not the current location. |
| js/shared/gobViews.js | 376 | `url.searchParams` (clicked link href) in drillUrl | mode, ps_team_id, roster_team_id, recruit_id, player_id, id, return_tab, origin, from, tab (of the link href) | UI | n/a | Parses the clicked href. mode here is the page kind (practice_squad/recruit). |
| js/shared/gobViews.js | 407 | `new URLSearchParams(location.search)` in drillUrl | * (copies all) | UI | n/a | Current query plus the href keys, pushed in place. The session keeps absent keys. |
| js/shared/gobViews.js | 408 | catch fallback `new URLSearchParams()` in drillUrl | * (copies all), same variable as 407 | UI | n/a | Error fallback of line 407. |
| js/shared/views/awardsView.js | 42 | `new URLSearchParams(location.search)` playerHref | * (copies all) | UI | n/a | Drill href that copies the query forward. No keys read. |
| js/shared/views/awardsView.js | 55 | `new URLSearchParams(location.search)` teamHref | * (copies all) | UI | n/a | Drill href that copies the query forward. No keys read. |
| js/shared/views/detailBar.js | 25 | `new URLSearchParams(location.search)` query() | * (copies all) + up, return_tab, origin, pager, return_url, tab, view_team_id, roster_team_id, player_id | UI | n/a | view_team_id/roster_team_id are the viewed team, not the user's identity. |
| js/shared/views/detailBar.js | 26 | catch fallback in query() | same as line 25 | UI | n/a | Error fallback of line 25. |
| js/shared/views/leadersView.js | 36 | `.get('leader')` | leader | UI | n/a | Expanded stat panel. |
| js/shared/views/leadersView.js | 67 | `new URLSearchParams(location.search)` setLeader + replaceState | * (copies all) | UI | n/a | Sets or deletes leader in place. |
| js/shared/views/leadersView.js | 170 | `new URLSearchParams(location.search)` playerHref | * (copies all) | UI | n/a | Drill href that copies the query forward. |
| js/shared/views/leagueScheduleView.js | 16 | `.get('week')` weekFromUrl | week | UI | n/a | Browse week for the schedule display, not the franchise week. |
| js/shared/views/leagueScheduleView.js | 56 | `url.searchParams.set('tab')` on a copy of location.href | * (copies all) | UI | n/a | writeWeek replaceState. Writes only. |
| js/shared/views/leagueScheduleView.js | 57 | `url.searchParams.set('week')` | * (copies all) | UI | n/a | Writes the browse week into the URL (see note). |
| js/shared/views/leagueScheduleView.js | 59 | `location.search` equality check | — (no read) | NONE | n/a | Compares strings to skip a no-op replaceState. |
| js/shared/views/leagueScheduleView.js | 66 | `new URLSearchParams(location.search)` teamHref | * (copies all) | UI | n/a | Drill href that copies the query forward. |
| js/shared/views/newsView.js | 31 | `.get('story')` | story | UI | n/a | Selected story. |
| js/shared/views/newsView.js | 36 | `new URLSearchParams(location.search)` feedUrl | * (copies all) | UI | n/a | Deletes story and sets tab. |
| js/shared/views/newsView.js | 44 | `new URLSearchParams(location.search)` storyUrl | * (copies all) | UI | n/a | Sets tab and story. |
| js/shared/views/playerStatsView.js | 179 | `new URLSearchParams(location.search)` playerHref | * (copies all) | UI | n/a | Drill href that copies the query forward. |
| js/shared/views/practiceSquadView.js | 38 | `.get('ps_week')` | ps_week | UI | n/a | Practice-squad browse week. |
| js/shared/views/practiceSquadView.js | 47 | `.get('ps_tier')` | ps_tier | UI | n/a | Tier selector. |
| js/shared/views/practiceSquadView.js | 68 | `url.searchParams.set('tab')` on a copy of location.href | * (copies all) | UI | n/a | writeParam replaceState. Writes only. |
| js/shared/views/practiceSquadView.js | 69 | `url.searchParams.set(key)` | * (copies all) | UI | n/a | Writes ps_week or ps_tier. |
| js/shared/views/practiceSquadView.js | 71 | `location.search` equality check | — (no read) | NONE | n/a | Guard against a no-op replaceState. |
| js/shared/views/practiceSquadView.js | 78 | `pathname + location.search` rosterHref | — (outbound build: return_url) | NONE | n/a | franchise_id/team_id come from ctx. The URL is used only as return_url. |
| js/shared/views/practiceSquadView.js | 87 | `pathname + location.search` boxHref | — (outbound build: return_url) | NONE | n/a | Same as line 78. |
| js/shared/views/prepEmbed.js | 66 | `.get('franchise_id')` ensureFranchiseMode | franchise_id | IDENTITY | None | Read only after FranchiseContext.get('franchise_id') misses. The session already absorbed the URL. |
| js/shared/views/rankingsView.js | 10 | `.get('cc_profile')` | cc_profile | UI | n/a | Debug profiling flag. |
| js/shared/views/rosterView.js | 44 | `new URLSearchParams(location.search)` params() | return_url, roster_team_id | UI | n/a | roster_team_id is the viewed team and falls back to userId from ctx. |
| js/shared/views/rosterView.js | 45 | catch fallback in params() | return_url, roster_team_id | UI | n/a | Error fallback of line 44. |
| js/shared/views/rosterView.js | 350 | `new URLSearchParams(location.search)` playerHref | * (copies all) | UI | n/a | Drill href that copies the query forward. |
| js/shared/views/scoutingView.js | 42 | `.get('franchise_id')` franchiseIdFrom | franchise_id | IDENTITY | None | Read only when ctx.franchiseId (URL, then FranchiseContext) is empty. |
| js/shared/views/teamScheduleView.js | 55 | `new URLSearchParams(location.search)` teamHref | * (copies all) | UI | n/a | Drill href that copies the query forward. |
| js/shared/views/tournamentView.js | 25 | `.get('tournament_phase')` | tournament_phase | UI | n/a | Phase tab. Not tournament_id. |
| js/shared/views/tournamentView.js | 32 | `new URLSearchParams(location.search)` writePhase | * (copies all) | UI | n/a | replaceState with tab and phase. It passes a state of {} (drops history.state). |
| js/shared/views/trainingReportView.js | 23 | `new URLSearchParams(location.search)` optionsFrom | mode, franchise_id, team_id, week, from, origin | IDENTITY | Low | franchise and team use ctx first. An empty week falls through to FranchiseContext. mode defaults to franchise. |
| js/shared/views/trainingReportView.js | 24 | catch fallback in optionsFrom | same as line 23 | IDENTITY | Low | Error fallback of line 23. |
| awards.html | 8 | `new URLSearchParams(location.search)` → set tab → replace to FCC | * (copies all) | NONE | n/a | Redirect stub that reads no keys. On desktop FCC merges the session back in, so the forwarded copy is harmless. |
| brackets-page.js | 69 | `.get('cc_profile')` inline in fetch URL | cc_profile | UI | n/a | Debug profiling flag |
| brackets.html | 8 | redirect stub, set tab | * (copies all) | NONE | n/a | Same as awards stub |
| common.js | 334 | `.get('cc_profile')` | cc_profile | UI | n/a | Debug profiling flag |
| court.html | 6859 | `.get('court_start')` | court_start | UI | n/a | One-shot entry intent that holds the overlay. Captured before bootGame strips it. |
| cut-players.js | 401 | `.get('cc_profile')` | cc_profile | UI | n/a | Debug profiling flag |
| cut-players.js | 403 | `.get('cc_profile')` | cc_profile | UI | n/a | Debug profiling flag |
| franchise-command-center.js | 54 | `.get('cc_profile')` (fccProfileSuffix) | cc_profile | UI | n/a | Debug profiling flag |
| franchise-command-center.js | 789 | `.get('team_id') \|\| teamId` | team_id | IDENTITY | Low | Dead branch: gobTables.js is loaded on FCC, so the GOBTables early-return always wins. If it ever ran, it would fall back to the viewed team as owner. |
| franchise-command-center.js | 790 | `new URLSearchParams()` + .set | — (outbound build) | NONE | n/a | Builds the team-roster-view href |
| franchise-command-center.js | 4014 | `.get('tab')` | tab | UI | n/a | Tab is written with history.replaceState (gobViews), so the URL stays accurate on desktop |
| game-plan.html | 7 | stub: get, delete, set, replace to FCC | * (copies all); embed, resume_from_timeout, mode, from | IDENTITY | Low | mode=tutorial and resume_from_timeout always travel explicitly on the inbound URL. FCC re-merges the session. |
| js/phaser/bootGame.js | 465 | `new URLSearchParams(location.search)`, forwarded + `.get('franchise_id')` | * (copies all); franchise_id | IDENTITY | Low | Raw read ignores the module's FranchiseContext franchiseId. If the URL lacks it, the exit goes to mode-select. |
| leaders.html | 8 | redirect stub, set tab | * (copies all) | NONE | n/a | Same as awards stub |
| news.html | 8 | redirect stub, set tab | * (copies all) | NONE | n/a | Same as awards stub |
| playbooks.html | 7 | stub: get, delete, set, replace to FCC | * (copies all); embed, mode | IDENTITY | Low | Tutorial links always carry ?mode=tutorial explicitly. FCC re-merges the session. |
| player-detail.html | 6 | stub: get, delete, set, replace to FCC | * (copies all); mode, recruit_id, player_id, id, origin, return_tab | IDENTITY | Low | The recruit bail keys are explicit on inbound links. FCC re-merges session identity. |
| practice-squad-bracket.html | 8 | redirect stub, set tab | * (copies all) | NONE | n/a | Same as awards stub |
| practice-squad-standings.html | 8 | redirect stub, set tab | * (copies all) | NONE | n/a | Same as awards stub |
| rankings.html | 8 | redirect stub, set tab | * (copies all) | NONE | n/a | Same as awards stub |
| recruiting-hub.js | 355 | `.get('hub')` | hub | UI | n/a | Sub-view. GOBShell writes it with replaceState. |
| recruiting-hub.js | 2195 | `new URLSearchParams()` + .set | — (outbound build) | NONE | n/a | Builds the player-view href from context ids |
| schedule.html | 8 | redirect stub, set tab | * (copies all) | NONE | n/a | Same as awards stub |
| set-lineup.js | 266 | `dest.searchParams.set('return_url', …)` | — (outbound build) | NONE | n/a | Sets return_url on the player-detail href |
| set-lineup.js | 268 | `location.search` embedded in return_url | * (copies all, into return_url) | UI | n/a | The return page re-merges the session, so dropped session-only keys are harmless |
| standings.html | 8 | redirect stub, set tab | * (copies all) | NONE | n/a | Same as awards stub |
| team-roster-view.html | 6 | stub: get, set, replace to FCC | * (copies all); mode, ps_team_id, roster_team_id, origin, return_tab | IDENTITY | Low | mode=practice_squad and ps_team_id are always explicit on inbound PS links |
| team-roster-view.js | 205 | `.get('cc_profile')` | cc_profile | UI | n/a | Debug profiling flag. Identity comes from emptyParams/context. |
| team-stats.html | 8 | redirect stub, set tab | * (copies all) | NONE | n/a | Same as awards stub |
| training-report.html | 7 | stub: get, delete, set, replace to FCC | * (copies all); embed | UI | n/a | Reads only embed |
| training-report.html | 135 | `.get('embed')` | embed | UI | n/a | Embed flag only |
| training-report.js | 62 | `new URLSearchParams()` empty fallback | — (empty fallback; real reads go through liveParams()) | NONE | n/a | Identity (mode, franchise_id, team_id, week) is read via FranchiseContext. The bag is only a catch fallback. |
| training.html | 7 | stub: get, delete, set, replace to FCC | * (copies all); embed, mode | IDENTITY | Low | Tutorial links always carry ?mode=tutorial explicitly. FCC re-merges the session. |
| training.js | 888 | `.get('tab')` | tab | UI | n/a | Tab is written via replaceState, so the URL is accurate |

## Franchise-identity reads needing desktop-lane follow-up
**High:**
1. **`js/shared/gobNav.js:625`, `stripParam()`:** passes the whole URL query to `FranchiseContext.commitParams`.
   - On desktop that **replaces the entire session state** with the URL's keys, so session-only identity (`team_id`, `tournament_id`, game keys) is wiped and only `runtime` survives.
   - The URL is never stripped either, so `?action=` survives a reload.
   - Callers: `recruiting-hub.js` 1451, 1467, 2579, 2639. *(Verified in code.)*
2. **`js/shared/gobAdvance.js:158`, `queryId()`:** `franchise_id` / `team_id` / `user_team_id` come from the URL only, with no FranchiseContext fallback. `load()` (from gobShell on every shell page) gives up if the URL has no `franchise_id`. The same reads happen at 674 / 687 / 709 / 717. *(Verified in code.)*
3. **`js/shared/officeHome.js:173`, `teamHref()`:** with no `team_id` / `user_team_id` in the URL, it sets `team_id` to the **viewed** team. FCC URLs built by gobNav carry only `franchise_id`, so on desktop the drill-in can make the target session treat the viewed team as the user's team. *(Verified in code.)*
4. **`js/shared/gobNav.js:796`, `guardClosedFranchiseGame()`:** `game_id` and `franchise_id` come from the URL only. On desktop `game_id` can be session-only, so the closed-game guard silently never fires. *(Verified in code.)*

**Low (URL-only identity where absent keys are omitted and the target page's session merge fills them; the URL can still be stale after a desktop `commitParams`):**
- `gobNav.js` 165, 499
- `gobShell.js` 254, 265, 938, 957
- `officeHome.js` 143, 159, 436, 854/857/858/861, 1086
- `gobViews.js` 16-19: the URL wins over FranchiseContext
- `gobTables.js` 269
- `trainingReportView.js` 23-24: `mode` comes from the URL only, and the URL `week` beats the context
- `authGuard.js` 20/117: cosmetic
- `bootGame.js` 465: ignores the module's `franchiseId`; one-line fix
- `franchise-command-center.js` 789: dead branch
- The `mode=tutorial` / `recruit` / `practice_squad` bail checks in the `game-plan` / `playbooks` / `training` / `player-detail` / `team-roster-view` `.html` stubs

**Worth checking (not a Gate B identity read):** `views/leagueScheduleView.js:57` writes the *browse* `week` into the URL. On desktop `absorbLocation` copies it into the session's `week`, and `week` is one of the keys `inboundNamesNewMatchup` compares, so browsing the schedule could clear `game_id` and the other gameplay keys on the next load.

## Re-baseline
- `check_migration_gates.py --write-allowlist` was run on an unmodified FrontEnd checkout. This is an owner-approved re-baseline, noted in the commit message.
- **Allowlist diff:** 49 new FrontEnd entries, plus `franchise-command-center.js` raised from 1 to 4. No other entry changed.
- **Final output:** `Migration gates passed.` / `Gate A: 0 imports in 0 files` / `Gate B: 144 lines in 50 files`.

## CLAUDE.md
Added a "CI migration gates" section (before "Don't commit"): no new `from BackEnd.db import` (use `get_store()`); no new URL-state reads for franchise identity outside `franchiseContext.js` (read `window.FranchiseContext`); never `--write-allowlist` over a new violation without Jamie's approval.

## Tests
| Run | Result |
|---|---|
| `test_browse_rev.py`, `test_schedule_week.py`, `test_home_base_data.py` (default mongomock) | 70 passed |
| Same 3 files with `GOB_PERSISTENCE=sqlite` | 69 passed, 1 failed: `test_writer_bumps_browse_etag[recruiting-watchlist]`. It fails **identically without this change** (checked by stash), so it's pre-existing in SQLite mode |
| Full suite (default config, once) | **4108 passed, 20 skipped, 109 xfailed, 1 xpassed, 0 failed, 0 errors**. The XPASS is the same pre-existing `test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference`; no new failures vs known_failures |

## Unsure / notes
- **Who classified:** three read-only agents did the classification (one per file group). I spot-checked all four High rows in code.
- **Borderline class:** `mode` is treated as IDENTITY where it is FranchiseContext state (`tutorial` / `franchise`). In `gobViews.js:376` it is the page kind parsed from a clicked href, so I classed that as UI.
- **Leftover noise:** the `.html` redirect stubs (awards, brackets, leaders, and so on) copy the query to FCC and read nothing. They are Gate B noise that could be removed rather than allowlisted.
