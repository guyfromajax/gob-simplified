# Chapter 8 — Prep modules: plan + Training Report + Game Plan + Playbooks

Convert the four Prep embed-bridge views into real modules. Training Report shipped first, then Game Plan. This section adds Playbooks. Player Training follows as its own PR.

Branches: `app/prep-modules-report` (Report), `app/prep-modules-gameplan` (Game Plan), `app/prep-modules-playbooks` (Playbooks) from `origin/develop`.

---

## Step 0 — Plan (written before the conversion)

The bridge (`js/shared/views/prepEmbed.js`, 84 lines) does four things: `ensureCss` (global `<link>`), `embed(url, host, selectors)` (fetch HTML, `DOMParser`, `importNode` selected roots), `loadScript` (plain tags), `loadIsolated` (fetch JS, wrap in an IIFE so top-level `const`/`let` do not collide with the command center). That is why first open fetches the old page, why `#franchise-container .tab-content h3` leaked, and why scripts re-ran.

### Training Report — converted in this PR

| | |
|---|---|
| Files | `training-report.html` (134), `training-report.js` (was 2058, now ~2170 with `init`), `training-report.css` (1858), `trainingReportView.js` (was 34) |
| Globals the page script used | `FranchiseContext`, `API_CONFIG`, `GOBNav`, `formatNameWithJersey`, `renderProjectedStartingFive`, `buildFranchiseLockerRoomUrl` / `resolveFranchiseLockerRoomUrl`, `document` ids (`week-number`, `locker-room-btn`, `players-thead`, `attribute-tooltip`, …), `DOMContentLoaded` + immediate start (`__gobTrainingReportStarted`) |
| Bridge today | CSS ×4, `embed('/training-report.html?embed=1', ['.training-report-container'])`, `loadScript(playerYear)`, `loadIsolated('/training-report.js')`, `body.training-report-page` |
| Standalone | `/training-report.html` redirects to `?tab=training-report-view` unless `embed=1`. Keep the redirect. |
| Tests | `player-training-followup`, `training-report-no-recruiting`, `office-frontend` href, `news-awards` / `test_news_dispatches`, `navigation-fixes-3`, `test_measure_vocabulary`, `test_attribute_gain`, `test_player_development_grid` (from=inbox Back) |
| Risk | **Low–medium.** Read-only drill-in, no save, no Advance override. Large renderer; ids were document-global. |

### Game Plan — converted on `app/prep-modules-gameplan`

| | |
|---|---|
| Files | `game-plan.html`, `game-plan.js` (ES module `init`/`teardown`/`revalidate`/`shellHtml`), `game-plan.css`, `gamePlanView.js` |
| Globals | `initGamePlan` (compat), `gameStore`, `StateTelemetry`, `ErrorHandler`, `PointerValidation`, `GOBLeaveConfirm`, `GOBToast`, timeout/`resume_from_timeout` |
| Was | embed `.resource-page-container`, `#validation-modal`, **`#toast`**, then `loadScript` + `loadIsolated('/game-plan.js')` + `initGamePlan()` |
| Standalone that must keep working | `game-plan.html` with `resume_from_timeout=true` or `mode=tutorial` (no redirect; focus, no rail) |
| Tests | polish-prep-plan (layout, tooltip, shared toast, leave-confirm), `prep-modules-gameplan` (no embed, geometry, timeout save → court, tutorial PLAY NOW) |
| Risk | **High.** In-game timeout + tutorial stay on the standalone file. |

**Order reason:** after the Report — standalone focus paths can break a live game.

### Playbooks — converted on `app/prep-modules-playbooks`

| | |
|---|---|
| Files | `playbooks.html`, `playbooks.js` (ES module `init`/`teardown`/`revalidate`/`shellHtml`), `playbooks.css`, `playbooksView.js` |
| Globals | `initPlaybooks` (compat), `#toast` (standalone only), `gameStore`, leave-confirm, playbook tiles |
| Was | embed `.resource-page-container` + `#toast`, then `loadScript` + `loadIsolated('/playbooks.js')` |
| Standalone that must keep working | `playbooks.html?mode=tutorial` (no redirect; browse chrome). `embed=1` leftover only. |
| Tests | polish-prep-plan, navigation-fixes custom playbooks, `prep-modules-playbooks` (no embed, geometry, tutorial, save → toast → report) |
| Risk | **Medium–high.** Tutorial + save + leave-check; `#toast` clash. |

**Order reason:** third. Same shape as Game Plan (`initPlaybooks` already existed) but no timeout-in-game path.

### Player Training — later PR

| | |
|---|---|
| Files | `training.html` (479), `training.js` (2261), `training.css` (2601), plus development-focus / player-dev grid / newswire; `trainingView.js` (73) |
| Globals | `GOBTraining.syncAdvance`, sliders, `#requirements-bar` / `#auto-train-btn` moved into `.pg-tools`, `trainingAllocationClosed`, `warnOnLeave` draft, `pageshow` |
| Bridge | embed `.training-container`, `#custom-focus-modal`, `#auto-train-modal`; strip `#submit-btn`; `loadIsolated('/training.js')`; tools row |
| Standalone | `training.html` `mode=tutorial` or `embed=1`; tutorial pages |
| Tests | `player-training-followup`, training-page phase5, development-focus |
| Risk | **Highest.** Weekly submit, Advance override, tools parking, post-week-26 note, tutorial. |

**Order reason:** last. Most state, and the follow-up just settled the drill-in / toast / week-26 behaviour — convert once the other three modules show the `init(root)` pattern.

---

## Step 1 — Training Report conversion

- `training-report.js` is an ES module: `init(root, { franchiseId, teamId, week, from, origin })`, `revalidate`, `teardown`, `shellHtml()`. Queries are scoped to `root` (`byId` / `qsa`). Tooltip id is `training-report-attr-tooltip` (was `#attribute-tooltip`). `#locker-room-btn` still sets `data-exit-wired="1"` so existing leave-report tests wait for the same hook. No `DOMContentLoaded` auto-start.
- `trainingReportView.js` imports `init` and dependency scripts. No `embed()`, no `DOMParser`, no `loadIsolated`. First mount paints the shell into the host; `revalidate` re-reads the URL and refreshes in place if the payload changed (JSON signature).
- `/training-report.html` still redirects into `?tab=training-report-view`. `embed=1` (unused by the app) calls the same `init(document.body)`.
- Deleted for this view only: the fetch of `/training-report.html?embed=1`, the IIFE re-run, `body.training-report-page` chrome toggle. `prepEmbed.js` is unchanged for the other three.
- CSS: removed the leaking `:root` gold tokens, global `*` reset, and `body` background. App layout stays under `#training-report-view` with tokens. No gold.

Returns unchanged: ← Back (Office), **Back to Office** + `tut_alert=training_return` (post-submit), **← News** (News).

---

## First-open timing

`scripts/measure_nav_timing.js --only=training-report-view --pass=timing` (PORT 8173, 5 runs × desktop + online). The view was not in the previous measure map (it is a drill-in, not a Prep sub-tab), so there is no embed-era number for this exact click. Coverage-map siblings on the same script: Training embed 22/25 ms desktop cold, Game Plan embed 24/25. After:

| screen | profile | cold med/worst | warm med/worst | flags cold \| warm | timeouts |
|---|---|---|---|---|---|
| training-report-view | desktop | 16/18 | 3/4 | skeleton4 jump5 \| — | 0 |
| training-report-view | online | 15/19 | 2/3 | skeleton5 jump5 \| — | 0 |

Cold ~16 ms (shell then fill). Warm 2–4 ms (panel kept; signature skip). No blank/white. Cold `jump` is CLS from the shell filling notes + team columns in the same 16 ms — not a second document/IIFE paint. Raw: `reports/prep-modules-report/timings.json`.

---

## Screenshots (opened)

Same real fixture (week 12, Four Corners, Roger Henrich, P/T Defense Readiness). Develop befores were captured from `b9dd1df23` (embed + `body.training-report-page`) in a worktree.

| File | Check |
|---|---|
| `before-office-1280.png` / `1920.png` | Develop embed. Three Notes columns, square RH/NS/RH portraits, ghost ← Back, quiet Attributes / Training Changes segment at 1920. |
| `before-news-1280.png` / `1920.png` | Same report, News rail + ← News. |
| `training-report-office-1280.png` / `1920.png` | After. Same columns, portraits, ghost Back, Office rail, Play Next Game green. No gold. No Player Training underline. |
| `training-report-news-1280.png` / `1920.png` | After. Same report, News rail + ← News. |
| `training-report-after-1280.png` / `1920.png` | Same as Office after. |

### Before / after (same fixture)

1280 Office: `before-office-1280.png` · `training-report-after-1280.png`. Notes cards 225px (`before-metrics.json`). After matches, including ← Back: computed fill / border / text are the develop ghost (`rgba(255,255,255,0.06)` / `0.18` / `0.85`). Portraits are the same 40×40 square initials (this fixture’s `p-roger` has no painted master). No mid-word wrap. Toggle at 1920 is the same quiet segment, not orange and not the old light control.

---

## Tests

- `tests/e2e/prep-modules-report.spec.js`: no `training-report.html` fetch, no clash ids inside the view (`#toast` / leftover `#attribute-tooltip`), real data, Office / News / post-submit returns, revalidate keeps the shell, geometry guard vs `before-metrics.json`.
- `tests/test_prep_modules_report.py`: source scan — no embed/DOMParser/IIFE in the view; `init` export; HTML still redirects; `training-report-page` is on the view root, not `document.body`.
- Existing: player-training-followup, training-report-no-recruiting, `test_player_development_grid` (news or inbox Back), navigation-fixes-3 leave-report (`data-exit-wired`).

---

## Fix pass

The first conversion dropped `document.body.classList.add('training-report-page')` (correct — that leaked). The polished Notes grid, 40×40 square portraits, and in-app chrome still lived under `body.training-report-page …`, so the unscoped 3-column `.training-notes-container` crushed the hero cards, portraits had no size, and the Back/toggle fell back to leftover page styles.

What changed:

- `init` adds `training-report-page` on the **view root** (`#training-report-view`), never on `document.body`.
- 161 `body.training-report-page .…` descendant rules remapped to `.training-report-page .…`. The bare `body.training-report-page { }` page chrome stays for leftover `embed=1` only.
- `#training-report-view .training-notes-container` is a single column (no `word-wrap: break-word`). Hero portraits are 40×40, `border-radius: var(--radius-6)`.
- `#locker-room-btn` is an `<a role="button">` (not a native `<button>`). Chrome remaps a `<button>`’s used `background-color` / `border-color` to UA `buttonface` (the light-grey block) even when the class is `.gob-btn--ghost` and the specified fill is `rgba(255,255,255,0.06)`. The view rule restates that same ghost fill / `0.18` border / `0.85` text, with `transition: none` so `.gob-btn`’s 140ms background tween cannot sample as a mid-fade.
- Visual guard: Notes column widths vs `before-metrics.json` (±16px), no label/name wider than its card, 40×40 square portraits, Back is `gob-btn--ghost` at 138×42. Computed `background-color`, `border-color`, and `color` must match the before values (or be transparent). Toggle is not orange.

No gold tokens brought back. No global `:root` / `*` / `body` leaks.

---

## UX_System §8 merge gate

- pytest `--ignore=tests/e2e`: **4062 passed**, 16 skipped, 109 xfailed, 1 xpassed, **0 failed**.
- Full Playwright, workers=1, port 8157, CI unset: **676 passed**, 3 skipped, **0 failed** (clean full run).
- This-work Playwright (scoped, no full suite): **8 passed** — `prep-modules-report.spec.js` (6) plus navigation-fixes-3 report-exit (2: training submit → report → Back; custom playbooks → report → Back).

---

## Game Plan

Branch: `app/prep-modules-gameplan` from `origin/develop` (Training Report already merged).

### What changed

- One implementation: `game-plan.js` is an ES module with `init(root, options)`, `teardown`, `revalidate`, `shellHtml()`. Both the in-app view and standalone `game-plan.html` call the same `init`. `window.initGamePlan` remains as a compat wrapper.
- `gamePlanView.js` imports `init` and the same dependency scripts. No `embed('/game-plan.html?embed=1')`, no `DOMParser`, no `loadIsolated` IIFE. First mount paints the shell into `#game-plan-view` if needed; reopening calls `revalidate` and keeps the panel.
- `/game-plan.html` still redirects into `?tab=game-plan-view` for regular browse. `resume_from_timeout=true` and `mode=tutorial` stay on the standalone file (`html.gob-focus`, no rail). `embed=1` also stays and calls the same `init(document.body)`.
- In-app save uses the shared `GOBToast` and stays on the view. The embed's duplicate `#toast` is gone from `#game-plan-view`. Standalone keeps its own `#toast` for the timeout/tutorial chrome.
- Timeout save (`resume_from_timeout=true`) PUTs then `executeNavigateToCourt()` — back to the court, no rail. Tutorial keeps PLAY NOW → `tutorial-situation.html`.
- Polish kept: equal slider tracks, Execution / Transition headers, copy lines, shot-diet tooltip, `GOBNav.warnOnLeave` + in-app `GOBLeaveConfirm` on a real edit. Local `playSound` (same as Training Report) so the standalone module does not throw on Save.
- CSS: `*` / `body` reset is `body.game-plan-page` only (standalone chrome). In-app header hide is `#game-plan-view`. Slider / Save polish stays on tokens under `html.gob-shell`. The view never adds `body.game-plan-page`.

### Standalone paths verified

- `game-plan.html?resume_from_timeout=true` (from lineup, `game_id`, quarter 2): focus, no rail, Back To Lineup + Save Game Plan. Save PUTs `/api/gameplan` and leaves for `court.html` (or `set-lineup.html` if the helper routes there).
- `game-plan.html?mode=tutorial`: Sammy GOT IT → PLAY NOW → `tutorial-situation.html`. URL stays on `game-plan.html` until PLAY NOW. No Save button.

Existing polish-prep-plan specs (leave-confirm, layout/copy, shot-diet tooltip, shared toast) passed unchanged: **14 passed**.

### First-open timing

`scripts/measure_nav_timing.js --only=game-plan-view --pass=timing` (PORT 8174, 5 runs × desktop + online). Embed-era sibling on the same script (Training Report report): Game Plan embed **24/25** ms desktop cold. After:

| screen | profile | cold med/worst | warm med/worst | flags cold \| warm | timeouts |
|---|---|---|---|---|---|
| game-plan-view | desktop | 30/33 | 5/7 | skeleton5 \| — | 0 |
| game-plan-view | online | 29/30 | 6/7 | skeleton5 \| — | 0 |

Cold is the module import + first fill (one skeleton, then sliders). Warm 5–7 ms is the kept panel (`revalidate`, no rebuild). No blank/white. Raw: `reports/prep-modules-gameplan/timings.json`.

### Screenshots (opened)

Same fixture (`tests/e2e/fixtures/prep-plan.json`, franchise `6abbd5c3042952060db8726e`, Lancaster). Befores captured from develop embed-bridge with `GAMEPLAN_BEFORE=1` before any conversion.

| File | Check |
|---|---|
| `before-in-app-1280.png` / `1920.png` | Develop embed. Rail + Prep underline, Save in `.pg-tools`, equal tracks, Execution / Transition. |
| `after-in-app-1280.png` / `1920.png` | Same layout, tracks, headers, orange Save. No `#toast` inside `#game-plan-view`. |
| `before-timeout-1280.png` | Focus, no rail, Back To Lineup + Save Game Plan. |
| `after-timeout-1280.png` | Same focus chrome, same controls. Still `game-plan.html?resume_from_timeout=true`. |
| `before-tutorial-1280.png` | Focus, PLAY NOW, no Save. |
| `after-tutorial-1280.png` | Same. Still `game-plan.html?mode=tutorial`. |

### Before / after (same fixture)

Geometry guard vs `before-metrics.json`: slider tracks 1280 x=394/1000 w=260; 1920 x=596/1452 w=439. Execution / Transition `rgba(255,255,255,0.6)`. Save `rgb(247, 148, 32)` / `rgb(26, 18, 6)`. After matches (±2px). Visual pairs: no layout shift, no extra rail on timeout/tutorial, no missing PLAY NOW.

Differences: in-app after has no duplicate `#toast` in the view (`toastHost` false; develop embed was true). That is the intended clash removal. Nothing else listed.

### Tests

- `tests/e2e/prep-modules-gameplan.spec.js`: after shots + geometry, no `game-plan.html` fetch, no duplicate ids, reopen keeps `.gpc`, timeout save → court, tutorial PLAY NOW.
- `tests/test_prep_modules_gameplan.py`: no embed/DOMParser/IIFE; `init` export; HTML keeps focus + browse redirect; view never toggles `body.game-plan-page`; no global `*` / `body` reset.
- Existing: polish-prep-plan leave-confirm + game-plan layout/tooltip/toast (**14 passed**).

### UX_System §8 merge gate

- pytest `--ignore=tests/e2e`: **4117 passed**, 16 skipped, 109 xfailed, 1 xpassed, **0 failed**.
- Full Playwright, workers=1, port 8157, CI unset: **697 passed**, 3 skipped, **1 failed** — `invite-board.spec.js` “seed notice › disappears once the player reorders”. Isolated re-run on 8158 fails the same way: a Sammy “GOT IT” Invite Board modal sits over the board, so `#board-seed-notice` never clears. Not a Game Plan file; develop’s recruiting spec.
- This-work Playwright: **7 passed** (`prep-modules-gameplan.spec.js`) + polish-prep-plan **14 passed**.

---

## 0. Invite Board test (on clean develop)

The Game Plan full run failed `invite-board.spec.js` › "seed notice › disappears once the player reorders" — a Sammy "GOT IT" Invite Board modal sat over the board.

On clean `origin/develop` (`c87c838de`, after the Game Plan merge) that spec was run **3 times**. It **failed 3/3**. Isolated re-run of the same test failed the same way.

This is not a today's product merge. `maybeShowSeedModal()` in `recruiting-hub.js` dates to `cbe692841` (2026-08-20). The isolated harness now successfully imports `/js/shared/sammyModal.js` from the Playwright static server, so the modal paints. `force: true` on the first-row × still hits the overlay. Dismiss/save tests pass because their targets sit above it.

Fix (own commit `9bdd19a73` on this branch): after mount, click GOT IT (`getByRole('button', { name: /got it/i })`) then `#hub-board .brow[data-index="0"] .bx`. Isolated re-run after the dismiss: **1 passed** (2.7s). Product recruiting-hub JS was not changed.

---

## Playbooks

Branch: `app/prep-modules-playbooks` from `origin/develop` (Game Plan already merged).

### What changed

- One implementation: `playbooks.js` is an ES module with `init(root, options)`, `teardown`, `revalidate`, `shellHtml()`. Both the in-app view and standalone `playbooks.html` call the same `init`. `window.initPlaybooks` remains as a compat wrapper. No `DOMContentLoaded` auto-start.
- `playbooksView.js` imports `init` and the same dependency scripts. No `embed('/playbooks.html?embed=1')`, no `DOMParser`, no `loadIsolated` IIFE. First mount paints the shell into `#playbooks-view` if needed; reopening calls `revalidate` and keeps the panel. Tools park `#playbooks-tools-home` / `GOBTables.registerTools`.
- `/playbooks.html` still redirects into `?tab=playbooks-view` for regular browse. `mode=tutorial` stays on the standalone file (browse chrome, full rail — that is the §9 map, not Game Plan's focus). `embed=1` also stays and calls the same `init(document.body)`. Nothing in the app fetches `playbooks.html?embed=1` after this conversion; leftover skip + init only. Leave deletion to the cleanup batch.
- In-app save uses the shared `GOBToast` ("Playbooks saved" / "Playbooks not saved. Try again.") and stays on the view. The embed's duplicate `#toast` is gone from `#playbooks-view`. Standalone keeps its own `#toast` and `handleBack()` after `SAVE_NAV_DELAY_MS` (900) → locker room when `resolveFranchiseLockerRoomUrl` resolves, else `playbook-report.html`.
- Polish kept: Playbooks/Playcall divider, no LIVE pill, wide sliders with the value beside them and arrow-key nudging, Offense/Defense toggle next to the editor, set-play focus labels and Inside→Attack→Outside ordering by CMD, top-level locks, `GOBNav.warnOnLeave` + in-app `GOBLeaveConfirm` on a real edit.
- CSS: `*` / `body` / `:root` reset is `#playbooks-view, body.playbooks-page` tokens + `body.playbooks-page` chrome only. Toast rules are `body.playbooks-page .toast*`. In-app header hide and layout stay under `#playbooks-view`. The view never adds `body.playbooks-page`. Gold `--line` values kept on the scoped host so AFTER matches BEFORE.

### Standalone paths verified

- `playbooks.html?mode=tutorial`: stays on the file. Save is enabled after a real edit. After save, URL becomes `playbook-report.html` or `franchise-command-center.html` (locker-room resolve).
- Regular `/playbooks.html` still `location.replace`s into `?tab=playbooks-view`.
- `embed=1`: leftover skip-redirect + `init(document.body)` only. No in-app caller.

Existing polish-prep-plan specs passed unchanged: **14 passed**. navigation-fixes-3 custom playbooks → report: **1 passed**.

### First-open timing

`scripts/measure_nav_timing.js --only=playbooks-view --pass=timing` (PORT 8175, 5 runs × desktop + online). Playbooks was not a named embed-era sibling on the coverage map (Game Plan embed was 24/25 ms desktop cold). After:

| screen | profile | cold med/worst | warm med/worst | flags cold \| warm | timeouts |
|---|---|---|---|---|---|
| playbooks-view | desktop | 113/194 | 7/8 | skeleton5 jump5 \| — | 0 |
| playbooks-view | online | 114/117 | 8/8 | skeleton5 jump5 \| — | 0 |

Cold is the module import + first fill (tiles + shot-weights preview). Warm 7–8 ms is the kept panel (`revalidate`, no rebuild). `jump5` on cold is CLS from the shell filling `#pane-offense` / playcall lists — same class of first-fill flag as the Training Report. No timeouts. Raw: `reports/prep-modules-playbooks/timings.json`.

### Screenshots (opened)

Same fixture (`tests/e2e/fixtures/prep-plan.json`, franchise `6abbd5c3042952060db8726e`, Lancaster). Befores captured from develop embed-bridge with `PLAYBOOKS_BEFORE=1` before any conversion.

| File | Check |
|---|---|
| `before-in-app-1280.png` / `1920.png` | Develop embed. Rail + Prep underline, Save in `.pg-tools`, Playbooks/Playcall divider, Offense/Defense toggle by the editor, wide sliders + value + CMD, locks, no LIVE. |
| `after-in-app-1280.png` / `1920.png` | Same layout, tracks, divider, toggle, orange Save, locks. No `#toast` inside `#playbooks-view`. |
| `before-tutorial-1280.png` | Standalone browse chrome: Playbook Settings card, grey disabled Save, shot-distribution cards. Still `playbooks.html?mode=tutorial`. |
| `after-tutorial-1280.png` | Same. Still `playbooks.html?mode=tutorial`. |
| `playbooks-toast.png` | In-app GOBToast "Playbooks saved" over `.main`, panel still up. 3-2 Motion 34% → 35% from the arrow nudge. |

### Before / after (same fixture)

Geometry guard vs `before-metrics.json`: slider tracks 1280 x=499 w=168; 1920 x=804 w=202. Divider `rgba(255, 255, 255, 0.14) 1px 0px 0px 0px inset`. Toggle 1280 x=82 y=247 w=150. Save `rgb(247, 148, 32)` / `rgb(26, 18, 6)`. `lockVisible` true. After matches (±2px). Visual pairs: no layout shift, no extra rail on tutorial, no LIVE pill.

Differences: in-app after has no duplicate `#toast` in the view (`toastHost` false; develop embed was true). That is the intended clash removal. Nothing else listed.

### Tests

- `tests/e2e/prep-modules-playbooks.spec.js`: after shots + geometry, no `playbooks.html` fetch, no duplicate ids, reopen keeps `.pbc` / `.playbooks-layout`, in-app save → GOBToast and stay, tutorial stays on the file, standalone save → report or locker room.
- `tests/test_prep_modules_playbooks.py`: no embed/DOMParser/IIFE; `init` export; HTML keeps tutorial + browse redirect; view never toggles `body.playbooks-page`; no global `*` / `body` / `:root` reset.
- Existing: polish-prep-plan **14 passed**; navigation-fixes-3 custom playbooks **1 passed**.

### Cleanup (left for the audit batch)

- `playbooks.html?embed=1` skip + `init(document.body)` — unused by the app after this conversion. Do not delete the file (`mode=tutorial` still needs it).
- Dead `playbooks.html` links in `franchise-command-center.js` (if any remain) — not touched.

### UX_System §8 merge gate

- pytest `--ignore=tests/e2e`: **4126 passed**, 16 skipped, 109 xfailed, 1 xpassed, **0 failed**.
- Full Playwright, workers=1, port 8157, CI unset: **716 passed**, 3 skipped, **0 failed**.
- This-work Playwright: **7 passed** (`prep-modules-playbooks.spec.js`) + polish-prep-plan **14 passed** + navigation-fixes-3 custom playbooks **1 passed**.

---

STATUS: COMPLETE

