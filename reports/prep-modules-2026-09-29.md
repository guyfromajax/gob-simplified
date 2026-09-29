# Chapter 8 — Prep modules: plan + Training Report

Convert the four Prep embed-bridge views into real modules. This PR: the plan for all four, and the Training Report conversion. Game Plan, Playbooks, and Player Training follow as their own PRs.

Branch: `app/prep-modules-report` from `origin/develop`.

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

### Game Plan — later PR

| | |
|---|---|
| Files | `game-plan.html` (369), `game-plan.js` (1399), `game-plan.css` (917), `gamePlanView.js` (70) |
| Globals | `initGamePlan`, `#toast`, `gameStore`, `StateTelemetry`, `ErrorHandler`, `PointerValidation`, `GOBLeaveConfirm`, `GOBToast`, timeout/`resume_from_timeout` |
| Bridge | embed `.resource-page-container`, `#validation-modal`, **`#toast`**, then a stack of `loadScript` + `loadIsolated('/game-plan.js')` + `initGamePlan()` |
| Standalone that must keep working | `game-plan.html` with `resume_from_timeout=true` or `mode=tutorial` (no redirect; focus, no rail) |
| Tests | game-plan / timeout / leave-confirm specs, polish-prep |
| Risk | **High.** In-game timeout + tutorial stay on the standalone file. `#toast` already clashes. Leave-check. |

**Order reason:** after the Report, do Game Plan next — it already has `initGamePlan()`, but the standalone focus paths are the ones that can break a live game.

### Playbooks — later PR

| | |
|---|---|
| Files | `playbooks.html` (207), `playbooks.js` (1758), `playbooks.css` (2073), `playbooksView.js` (70) |
| Globals | `initPlaybooks`, `#toast`, `gameStore`, leave-confirm, playbook tiles |
| Bridge | same stack as Game Plan; embed `.resource-page-container` + `#toast` |
| Standalone | `playbooks.html` `mode=tutorial` or `embed=1` |
| Tests | playbooks save/leave, navigation-fixes custom playbooks |
| Risk | **Medium–high.** Tutorial + save + leave-check; `#toast` clash. |

**Order reason:** third. Same shape as Game Plan (`initPlaybooks` already exists) but no timeout-in-game path, so it is safer after Game Plan’s standalone pattern is proven.

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

STATUS: COMPLETE

