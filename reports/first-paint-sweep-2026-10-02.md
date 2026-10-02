# First-paint sweep — 2026-10-02

Branch `polish/first-paint-sweep`, from `origin/develop` `a4285e7e8` (still the tip at gate time, so the merged tree is this branch as is).

Jamie's rule: no screen is ever shown in a broken, half-built state.

## Result

| | Count |
|---|---|
| Screens swept (46 gallery screens; 32/33 are the one page on its two profiles; plus the team and player drill-ins) | 47 |
| Passed, nothing to fix (3 of them stats-owned) | 15 |
| Passed; the shell top strip under the loader fixed ("NR" and logo alt text before data) | 17 |
| Already fixed, re-checked (Training Report, Recruiting × 3) | 4 |
| Failed and **fixed** (Scouting, weekly Training, Training playbook, Program select, Team Builder, Archetype leaderboard, Account) | 7 |
| Failed, **left** for the owner (stats): playbook report, cut players, box score opened without a game | 3 |
| Not swept | 1 (Focus Game Plan in a timeout: needs a live game) |
| Transitions swept | 5, all pass (one small fix: drill-in breadcrumb) |

## Method

- Every `fetch` / XHR API response held 1.5 s (`tests/e2e/helpers/firstPaint.js` `delayApi`). Static files are not held.
- Each screen is probed and shot at 0.5 s and 1.1 s (before any data), 2.3 s, the moment the loader lifts, 0.8 s later, and settled.
- A probe reads only text a person can see (on screen, not covered), flags `--` / `—` / `NR` / `0-0` / `undefined` / `null` / `NaN`, and compares heading positions between each phase and the settled page (moved more than 6px, or gone).
- **Offline**: desktop SQLite server, a real 128-team league, a fresh Lancaster franchise. **Online**: hosted profile, replaying the real responses the offline pass recorded. Account pages hit the hosted test server.
- "Before" and "after" are the same sweep on `a4285e7e8` and on this branch.
- Flags are not verdicts. On a settled page "0-0" and "—" are real week-1 values; a screen fails only on what it shows **before** its data.

## Screens

"Offline / Online" = what stood at first paint → how much text the settled page has, on this branch.

| # | Screen | Before data, it showed | Result | Offline (first → settled) | Online (first → settled) | Shots |
|---|---|---|---|---|---|---|
| 01 | Office | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 59 texts | loader → 59 texts | [before](first-paint-sweep/01-office-before.png) [after](first-paint-sweep/01-office-after.png) |
| 02 | Team › Roster | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 247 texts | loader → 247 texts | [after](first-paint-sweep/02-team-roster-after.png) |
| 03 | Team › Player Stats | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 289 texts | loader → 289 texts | [after](first-paint-sweep/03-team-player-stats-after.png) |
| 04 | Team › Team Attributes | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 45 texts | loader → 45 texts | [after](first-paint-sweep/04-team-attributes-after.png) |
| 05 | Team › Schedule | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 116 texts | loader → 116 texts | [after](first-paint-sweep/05-team-schedule-after.png) |
| 06 | Practice Squad | Page loader, then the finished view. Nothing half-built. | Pass (stats-owned, not edited) | loader → 9 texts | loader → 9 texts | [after](first-paint-sweep/06-practice-squad-after.png) |
| 07 | Prep › Player Training | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 82 texts | loader → 82 texts | [after](first-paint-sweep/07-prep-player-training-after.png) |
| 08 | Prep › Game Plan | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 71 texts | loader → 71 texts | [after](first-paint-sweep/08-prep-game-plan-after.png) |
| 09 | Prep › Playbooks | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 153 texts | loader → 153 texts | [after](first-paint-sweep/09-prep-playbooks-after.png) |
| 10 | Prep › Scouting | After the loader lifted: a bare line, "Loading scouting report…", in an empty panel. | **Fixed**: shared view skeleton | loader → 158 texts | loader → 158 texts | [before](first-paint-sweep/10-prep-scouting-before.png) [after](first-paint-sweep/10-prep-scouting-after.png) |
| 11 | League › Standings | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 242 texts | loader → 158 texts | [after](first-paint-sweep/11-league-standings-after.png) |
| 12 | League › Rankings | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 118 texts | loader → 118 texts | [after](first-paint-sweep/12-league-rankings-after.png) |
| 13 | League › Leaders | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 89 texts | loader → 89 texts | [after](first-paint-sweep/13-league-leaders-after.png) |
| 14 | League › Team Stats | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 497 texts | loader → 497 texts | [after](first-paint-sweep/14-league-team-stats-after.png) |
| 15 | League › Schedule | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 77 texts | loader → 77 texts | [after](first-paint-sweep/15-league-schedule-after.png) |
| 16 | League › Tournament | Page loader, then the finished view. Nothing half-built. | Pass (stats-owned, not edited) | loader → 15 texts | loader → 15 texts | [after](first-paint-sweep/16-league-tournament-after.png) |
| 17 | Recruiting › Pool | One skeleton, then the hub. | Pass (already fixed) | skeleton → 185 texts | skeleton → 185 texts | [after](first-paint-sweep/17-recruiting-pool-after.png) |
| 18 | Recruiting › Leans | One skeleton, then the hub. | Pass (already fixed) | skeleton → 85 texts | skeleton → 85 texts | [after](first-paint-sweep/18-recruiting-leans-after.png) |
| 19 | Recruiting › Visits | One skeleton, then the hub. | Pass (already fixed) | skeleton → 30 texts | skeleton → 30 texts | [after](first-paint-sweep/19-recruiting-visits-after.png) |
| 20 | News | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 11 texts | loader → 11 texts | [after](first-paint-sweep/20-news-after.png) |
| 21 | News › Awards | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 84 texts | loader → 84 texts | [after](first-paint-sweep/21-news-awards-after.png) |
| 22 | Settings panel | Opens over a settled Office; the panel is static. | Pass | 11 texts → 11 texts | 16 texts → 16 texts | [after](first-paint-sweep/22-settings-panel-after.png) |
| 23 | Weekly training (focus) | The whole form at once with the default 24-point budget (camp is 30), "NR" in the strip, and the Player Development grid and any saved draft landing later. | **Fixed**: held behind the page loader | loader → 98 texts | loader → 98 texts | [before](first-paint-sweep/23-weekly-training-before.png) [after](first-paint-sweep/23-weekly-training-after.png) |
| 24 | Training report (focus) | Designed skeleton, then the report. Strip showed "NR". | Pass (already fixed); strip fixed | skeleton → 3 texts | skeleton → 3 texts | [before](first-paint-sweep/24-training-report-before.png) [after](first-paint-sweep/24-training-report-after.png) |
| 25 | Set Lineup | Page loader, then the finished view. Nothing half-built. | Pass (stats-owned, not edited) | loader → 196 texts | loader → 196 texts | [after](first-paint-sweep/25-set-lineup-after.png) |
| 26 | Court pre-game | The pre-game card (two buttons). Same at first paint and settled. | Pass | 2 texts → 2 texts | 2 texts → 2 texts | [after](first-paint-sweep/26-court-pregame-after.png) |
| 27 | Focus Game Plan (timeout) | "Missing required game" error card: this URL needs a live game in a timeout, which the sweep cannot create. | Not swept (unreachable without a live game) | 5 texts → 5 texts | 5 texts → 5 texts | [after](first-paint-sweep/27-focus-game-plan-after.png) |
| 28 | Box score | Opened without a game id: bare "Quarter Scoring / Player Of The Game / Player Stats" heads, "NR" strip. With a real game id (transition t4) it is loader, then the finished page. | **Left** (stats, box-score.js). Real entry passes; strip fixed | 49 texts → 49 texts | 49 texts → 49 texts | [after](first-paint-sweep/28-box-score-after.png) |
| 29 | Cut players | "Assign Practice Squad" heading and table shell, then replaced by "No Cuts Required". | **Left** (stats, practice-squad roster screen) | 22 texts → 3 texts | 22 texts → 3 texts | [after](first-paint-sweep/29-cut-players-after.png) |
| 30 | Training playbook | Bare "Offense" / "Defense" titles over empty space, "—" in both docks, an orange Save & Continue with nothing to save, "NR" strip. A heading moved when the cards landed. | **Fixed**: held behind the page loader | loader → 105 texts | loader → 105 texts | [before](first-paint-sweep/30-training-playbooks-before.png) [after](first-paint-sweep/30-training-playbooks-after.png) |
| 31 | Playbook report | Bare "Playbook Settings / Offense / Motion" heads; when data lands two heads jump (Set Plays +148px, Zone +42px) and three appear. | **Left** (stats, playbook-report) | 14 texts → 34 texts | 14 texts → 34 texts | [after](first-paint-sweep/31-playbook-report-after.png) |
| 32 | Mode select | Page loader, then the finished view. Nothing half-built. | Pass | loader → 68 texts | loader → 51 texts | [after](first-paint-sweep/32-mode-select-after.png) |
| 34 | Trophy case | Loader, then the finished case ("—" and "0-0" are a new program's real values). | Pass | loader → 30 texts | loader → 31 texts | [after](first-paint-sweep/34-trophy-case-after.png) |
| 35 | Program select | Title, "0 of 128 match", empty filter selects, 16 empty conference heads, footer high on the page; footer jumped when the programs landed. | **Fixed**: held behind the page loader | loader → 166 texts | loader → 166 texts | [before](first-paint-sweep/35-program-select-before.png) [after](first-paint-sweep/35-program-select-after.png) |
| 36 | Team Builder (step 1) | A plain "Loading Team Builder…" line over a white footer bar; then (no program picked yet) the program-select page, with failure 35. | **Fixed**: held behind the page loader | n/a | loader → 172 texts | [before](first-paint-sweep/36-team-builder-before.png) [after](first-paint-sweep/36-team-builder-after.png) |
| 37 | Login | Static page: complete at first paint, no data wait. (Signed-in visitors are redirected.) | Pass | n/a | 8 texts → 51 texts | [after](first-paint-sweep/37-login-after.png) |
| 38 | Sign up | Static page: complete at first paint, no data wait. | Pass | n/a | 7 texts → 8 texts | [after](first-paint-sweep/38-signup-after.png) |
| 39 | Reset password | Static page: complete at first paint, no data wait. | Pass | n/a | 6 texts → 6 texts | [after](first-paint-sweep/39-reset-password-after.png) |
| 40 | Archetype leaderboard | Title, a plain "Loading…" line and the footer directly under it; footer jumped down when the boards landed. | **Fixed**: held behind the page loader | n/a | loader → 31 texts | [before](first-paint-sweep/40-archetype-leaderboard-before.png) [after](first-paint-sweep/40-archetype-leaderboard-after.png) |
| 41 | Coaching archetypes | Static page: complete at first paint, no data wait. | Pass | n/a | 17 texts → 17 texts | [after](first-paint-sweep/41-coaching-archetypes-after.png) |
| 42 | Account | Placeholder name "Coach", Geek Points "0", empty Titles and Archetypes cards. | **Fixed**: held behind the page loader | n/a | loader → 21 texts | [before](first-paint-sweep/42-account-before.png) [after](first-paint-sweep/42-account-after.png) |
| 43 | Tutorial hub | Static page: complete at first paint, no data wait. | Pass | 23 texts → 23 texts | 23 texts → 23 texts | [after](first-paint-sweep/43-tutorial-hub-after.png) |
| 44 | Tutorial lesson (recruiting) | Static page: complete at first paint, no data wait. | Pass | 26 texts → 26 texts | 26 texts → 26 texts | [after](first-paint-sweep/44-tutorial-recruiting-after.png) |
| 45 | Persona intro | Static page: complete at first paint, no data wait. | Pass | 5 texts → 5 texts | 5 texts → 5 texts | [after](first-paint-sweep/45-persona-intro-after.png) |
| 46 | FAQs | Static page: complete at first paint, no data wait. | Pass | 11 texts → 11 texts | 11 texts → 11 texts | [after](first-paint-sweep/46-faqs-after.png) |
| 47 | Team page (drill-in) | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 160 texts | loader → 160 texts | [after](first-paint-sweep/47-team-page-after.png) |
| 48 | Player page (drill-in) | Page loader, then the finished view. Nothing half-built. Top strip showed "NR" and the logo's alt text under the loader. | Pass; strip fixed | loader → 74 texts | loader → 74 texts | [after](first-paint-sweep/48-player-page-after.png) |

## Transitions

Offline server, real league, API held 1.5 s, swept from the click that starts each one.

| Transition | It showed | Result | Phases (first / mid / loader lifts / settled) | Shots |
|---|---|---|---|---|
| Open a team page (from Standings) | Bar + shared view skeleton, then the page. Breadcrumb ended in a dangling "/" until the name loaded. | Pass; **breadcrumb fixed** | skeleton / 156 texts / n/a / 156 texts | [before](first-paint-sweep/t1-open-team-page-before.png) [after](first-paint-sweep/t1-open-team-page-after.png) |
| Open a player page (from Roster) | Bar + shared view skeleton, then the page. Same dangling "/". | Pass; **breadcrumb fixed** | skeleton / 75 texts / n/a / 75 texts | [before](first-paint-sweep/t2-open-player-page-before.png) [after](first-paint-sweep/t2-open-player-page-after.png) |
| After training (Submit Training → Training Report) | Newswire loader while training runs, then the Training Report skeleton, then the report. | Pass | loader / loader / skeleton / 58 texts | [after](first-paint-sweep/t3-after-training-after.png) [loader](first-paint-sweep/t3-after-training-loader.png) |
| After a game (box score of the game just played) | Box score of a real simmed game: loader, then the finished page. | Pass (stats-owned, not edited) | loader / loader / 66 texts / 66 texts | [after](first-paint-sweep/t4-after-a-game-after.png) [loader](first-paint-sweep/t4-after-a-game-loader.png) |
| After advancing (the Office in the new week) | The Office in the new week: loader, then the finished Office. | Pass | loader / loader / 70 texts / 126 texts | [after](first-paint-sweep/t5-after-advancing-after.png) [loader](first-paint-sweep/t5-after-advancing-loader.png) |

- After training: Auto-Train and Submit through the UI; the real training and CPU training ran behind the loader.
- After a game: the game was simmed through the API (the court is not a loading step), then the sweep opened the box score with the real game id.
- After advancing: the week was completed through the API (phase B is what the end-of-game "Go To Locker Room" runs behind its loader), then the sweep opened the Office in week 2. The score on the "Since last week" card counts up from 0: that is the Office's designed reveal (`officeHome.js` `countUp`), not a placeholder.

## What was fixed, and how

One shared pattern for a whole page that waits on data, the way the Training Report holds: an inline script at the top of `<body>` sets `is-loading` on `<html>` and shows the page loader; a CSS rule hides the page body while `is-loading` is set; the page script lifts both in a `finally` once it has drawn. No new skeleton styles.

| Screen | Fix | Files |
|---|---|---|
| Shell top strip (all in-app screens) | Rank stat hidden until the season data is in ("NR" is a real answer, not a placeholder). A logo with no `src` is `visibility:hidden`, so its alt text never shows. | `js/shared/gobShell.js`, `css/gob-shell.css` |
| Prep › Scouting | The shared view skeleton (`GOBTables.paintSkeleton`) in the status slot, not a line of text. | `js/shared/views/scoutingView.js` |
| Weekly training | Held behind the loader until the week's budget, saved draft and Player Development grid are in. The 24-point default is never shown. | `training.html`, `training.js` (`liftWeeklyLoading`), `training.css` |
| Training playbook | Held behind the loader until the cards are drawn. A failed load still lifts it. | `training-playbooks.html/.js/.css` |
| Program select | Held behind the loader until the programs are drawn; footer held with it. | `franchise-select-team.html/.js/.css` |
| Team Builder | Boot line and footer held behind the loader until step 1 is drawn. A boot that throws still lifts it. With no program picked it hands over to Program select with the loader still up. | `team-builder.html/.js/.css` |
| Archetype leaderboard, Account | Held behind the loader until the data is drawn; footer held with it. The "Loading…" line is gone. | `coaching-archetypes-leaderboard.html`, `account.html`, `css/community.css` |
| Team / player drill-in | The breadcrumb no longer ends in a dangling "/" while the name loads. | `js/shared/views/detailBar.js` |

## Left for the owner (stats agent), not edited

| Screen | What it shows before data |
|---|---|
| 31 Playbook report | Bare "Playbook Settings / Offense / Motion" heads. When data lands "Set Plays" drops 148px and "Zone" 42px, and "Fast Breaks", "HC Traps" and "Offense Playcall Center" appear. |
| 29 Cut players | "Assign Practice Squad" heading and table shell, then replaced by "No Cuts Required" (week 1, nothing to cut). |
| 28 Box score, opened without a game id | Bare "Quarter Scoring / Player Of The Game / Player Stats" heads. With a real game id it passes (transition t4): loader, then the finished page. |
| 06 Practice squad, 16 Tournament, 25 Set Lineup | Pass. |

## Design decisions for Jamie (not guessed)

| # | Question | Where it stands |
|---|---|---|
| 1 | ~~Should the page loader be solid?~~ **Ruled: yes.** | Done, see "Update" at the end. The loader is the page fill (`--bg`) at full opacity on every page. Shot: `first-paint-sweep/loader-solid-office-after-1280.png`. |
| 2 | ~~Training selector outline: A or B?~~ **Ruled: option B.** | Done: `--train-box-outline` is `var(--white-45)`. |
| 3 | **Login, when already signed in**: the form paints, then the page redirects to Home Base. Hiding the form until the auth check would delay it for every signed-out visitor. | Not changed. Only reachable by opening `/login.html` by hand while signed in. |
| 4 | **Weekly training now waits behind the loader** instead of showing a usable form at once with a budget that could be wrong. | Done as the rule says. Say if you would rather see the form with only the budget held back. |

## The four follow-up items (each its own commit)

| Commit | Item | Notes |
|---|---|---|
| `6e5e94ae8` | Playbooks tab row hidden under the Shot Distribution strip | Root cause: the strip was sticky at a legacy 22px offset with a transparent fill, so on scroll it rode over the page head and the tab row slid under it (34px overlap at 1280, 13px at 1920+). The strip now pins under the page head on the solid page fill and the tab row pins with it. Test at 1280 and 1920, at rest and scrolled. Shots: `reports/playbooks-followups/tabs-strip-after-*.png`. |
| `7539d604d` | Locked vs unlocked slider rows | Open padlock dim; closed padlock white on a neutral plate, `aria-pressed`, row class `is-locked`; locked track muted with no handle, percentage one step dimmer. Unlocked sliders gained a handle so "no handle" reads as locked. Fast Breaks and Press/Traps have no lock (they normalise). Shots: `reports/playbooks-followups/locks-after-*.png`. |
| `c6e1c2a8c` | Culture Builder icon is a heart | Same line weight, size and purple mark. The other three icons are byte-identical (pinned by a test). The icon appears only on the weekly Training page: not on the Training Report header or the coach archetype badge. Shot: `reports/training-followups/culture-builder-heart-after-1280.png`. |
| `c5bb28b74` | Training point selectors | Below. |

### Training point selectors

| Requirement | Built |
|---|---|
| 1. Empty boxes | 1px outline, no fill. Filled boxes solid white. |
| 2. Zero dot | Gone. A small × clear control shows only while the row has points; it ghosts in on row hover or keyboard focus. Keyboard clear: Home, Delete, Backspace or 0 on the focused row. |
| 3. Hover preview | Hovering box N lightly fills 1..N; filled boxes past N dim (what the click would give back). The row gets a faint highlight. |
| 4. Size | 22 × 28px hit area per box (was 18 × 10). |
| 5. Distance | Each column capped at 390px. Label-to-boxes gap is at most about 200px at 1280, 1920 and 2200 (tested). |
| 6. Number | Dim "0" at rest, full white with points. |
| 7. Out of points | Boxes the budget cannot reach dim further and take no click. |
| 8. Keyboard | Left / right change the value; 2px white focus ring round the boxes. |

- **Outline strength is one token**: `--train-box-outline` in `FrontEnd/static/css/gob-tokens.css`. Jamie chose option B: it is now `var(--white-45)` (option A was `var(--white-25)`).
- Shots in `reports/training-followups/`: `selectors-option-a-untouched-1280/1920.png`, `selectors-option-a-assigned-1280/1920.png`, the same four for `option-b`, and `selectors-option-a-vs-b-1280/1920.png` (A above B on one sheet). Also `selectors-hover-preview-1280.png`, `selectors-out-of-points-1280.png`, `selectors-keyboard-focus-1280.png`.
- Points are stored and submitted exactly as before: the clipped range input is still the model.

## Files touched (sweep commit)

- Fixes: `FrontEnd/static/js/shared/gobShell.js`, `css/gob-shell.css`, `js/shared/views/scoutingView.js`, `js/shared/views/detailBar.js`, `training.html`, `training.js`, `training.css`, `training-playbooks.html/.js/.css`, `franchise-select-team.html/.js/.css`, `team-builder.html/.js/.css`, `account.html`, `coaching-archetypes-leaderboard.html`, `css/community.css`.
- Gates: `tests/e2e/first-paint.spec.js` (9 tests), one test added to `tests/e2e/prep-scouting.spec.js`.
- Sweep tool (runs only with `FP_SWEEP` set): `tests/e2e/first-paint-sweep.spec.js`, `desktop-first-paint-sweep.spec.js`, `desktop-first-paint-transitions.spec.js`, `helpers/firstPaint.js`, `helpers/firstPaintScreens.js`.
- Docs: `_documentation_master/11_Design_Systems/UX_System.md` (first-paint rule, the held pages, the selector).
- Not touched: `franchise-command-center.css` (1779 lines, unchanged), any sim / finalize / cpu_week_pool / sim_rng code, any stats-owned file.

## Tests

- New tests fail on the old code: reverted the fixes and re-ran. 7 of the 8 first-paint tests and all 9 selector tests fail on `a4285e7e8`. The eighth ("a failed load still lifts the loader") passes on the old code by construction: it guards the new hold.
- Gates on the final tree: see the end of this report.

## Unsure / worth knowing

- **`/api/simulate-quarter` with `full_sim: true, advance_method: "sim_rest_of_game"` simmed one quarter** in the transitions run (final 15-13, Q2 to Q4 all 0). The box score therefore was not a final game, so its "Go To Locker Room" exit could not be driven and the advance was done through the API. Not investigated: sim code is out of scope here.
- The server logged `[ATL] record after phase-B flush failed` during phase B on the offline profile. Not caused by this branch; noted only.
- A milestone pop-up (coach archetype) opens over the Office once it has settled, on first visit. It is a designed moment. It hid the settled page in one after-pass, so that pass was rerun on a clean database.
- Settled-state things seen, outside this sweep's rule: the Office's Recruiting card is an empty box in weeks 1 and 2; hosted Mode select's "Around GOB" is six dashed placeholder boxes under a stub token (already in the gallery notes).
- Untracked `reports/` folders from other tasks and the regenerated PNGs of other reports were left alone and not staged.

## Gates (final tree, `a4285e7e8` + this branch)

| Gate | Result |
|---|---|
| `git fetch origin` + merge `origin/develop` | Already up to date: develop is still `a4285e7e8`, the base of this branch. |
| `pytest --ignore=tests/e2e -q` | **4367 passed, 14 skipped, 108 xfailed, 2 xpassed** (exit 0). No `FAILED` / `ERROR`. |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** |
| `scripts/ci/check_migration_gates.py` | **passed** (Gate A 0 imports; Gate B 134 lines in 43 files, unchanged) |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | **978 passed, 19 skipped, 0 failed** (5.1 min). Nothing to re-run. |
| `franchise-command-center.css` | 1779 lines, not touched. |

- The 2 XPASS are on the known-failures list and are not from this branch (it changes no Python): `tests/test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference` and `tests/test_settings_application_to_gameplay.py::TestSettingsApplicationToGameplay::test_settings_loaded_and_applied_to_gameplay`. The list was not edited.
- **One red outside the gates, not from this branch**: the offline-profile config (`playwright.desktop.config.js`, not part of the default suite) has `desktop-gallery-fixes.spec.js` "#10/#6 empty state: awards" failing. It expects an empty-state card on Awards in week 1; since the All-American merge (`431511e1f`) Awards shows the projected teams in week 1, so there is no empty card. The test is stale. Left alone here (out of scope); the other 15 offline specs pass.

## Update: merge with develop and Jamie's two rulings

| Commit | What |
|---|---|
| `f5f4cf9b4` | Merged `origin/develop` `71048e175` (chrome-followups + tables-followups). One conflict, `tests/e2e/polish-training-playbooks.spec.js`: kept this branch's selector tests and develop's async `teamMarks()`. `gobShell.js` and `gob-shell.css` merged cleanly; both sides work together: develop's season label and "Signing Day" / "Offseason" wording under the week, and this branch's rank hidden until data and no logo alt text. |
| `5cd5ed03b` | Selector outline is option B (`--white-45`). Tests expect the shipped strength and still prove it is one token. Shots retaken (`selectors-option-*`, the A-vs-B sheet now marks B as shipped). Styleguide and UX_System note the choice. |
| `02550d9fa` | The shared page loader is solid: `var(--bg)` at full opacity instead of 92% black. Changed in `js/shared/pageLoadOverlay.js` (base, pulse and the reset after the newswire) and in the static markup of the six pages that carry the loader: FCC, court, box score, set lineup, mode select, trophy case. |

Solid loader, checks:

- **Nothing relied on seeing through it.** Every caller uses it as a gate that hides the page: page loads, the court's entry / resume / matchups gates, the pulse variant (paints its own banner and stat feed) and the training newswire (paints its own sheet). The loader image is a transparent GIF, so it sits cleanly on the page fill.
- Looked at under the loader with the API held: Office, Standings, weekly Training, court pre-game. Nothing shows through on any of them. Shots: `first-paint-sweep/loader-solid-office-after-1280.png`, `-standings-`, `-training-`, `-court-pregame-`.
- Tests (`tests/e2e/first-paint.spec.js`, "the page loader is opaque"): on those four pages the loader's computed background is `rgb(11, 13, 20)` with no alpha and it is the top element across the viewport; and a static check that neither the shared script nor any page's markup carries a see-through loader.
- `box-score.html` and `set-lineup.html` each had one attribute changed (the loader's inline style). Their `.js` files, which were the ones in flight, were not touched.

Gates on the final tree (`71048e175` merged in):

| Gate | Result |
|---|---|
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** |
| `scripts/ci/check_migration_gates.py` | **passed** (Gate A 0; Gate B 134 lines in 43 files) |
| Named specs: first-paint, polish-training-playbooks, polish-chrome-followups, polish-chrome-audio, shell-1, prep-scouting | **122 passed, 12 skipped, 0 failed** |
| Full Playwright, once, under the lock | **1020 passed, 21 skipped, 2 failed** (4.7 min) |
| The 2 failures, re-run alone with `--repeat-each=5` | **25 passed, 0 failed** (both specs, every test, five times) |
| `franchise-command-center.css` | 1779 lines, not touched |

The two failures in the full run:

- `shared-chrome-tokens.spec.js` "Home Base alpha banner, page-load overlay and error screens": a real, expected failure. The test pinned the loader's background at `[0, 0, 0, 0.92]`, the value Jamie just overruled. Updated to the solid page fill `[11, 13, 20]`. Passes 5 of 5.
- `submit-cuts.spec.js` "wrong count is disabled, looks dead, no sound": a flake, not from this branch. A force-click on the disabled Submit logged one `SFX_SELECT` once in the full run; alone it passes 5 of 5. That screen (practice-squad cuts) was not edited here.

pytest was not re-run: this update changes no Python (the earlier run on this branch was 4367 passed, 14 skipped, 108 xfailed, 2 xpassed).

