# Training Advance focus — 2026-09-30

Branch `app/training-advance-focus` from `origin/develop` (`f6a7cff7d`). Franchise UI only: weekly training is an Advance step; Prep › Player Training is player-development settings. No sim, training-engine, or backend payload change.

## Old vs new flow

**Today (develop):** On a training week, top-bar Advance (`dataset.mode=training`, "Run Training" / "Run Training Camp") went to FCC `?tab=training-view`. `GOBTraining.syncAdvance` overrode `#play-now` to "Submit Training". Weekly allocation, Coaching Focus, Auto-Train, Playbook Training, and the Player Development grid all lived on that Prep tab. `training.html` redirected here except `mode=tutorial`. Post-week-26 already set Advance to `play` / tournament. Camp week 1 used the same tab with `session_type=preseason`. Submit POSTed `/franchise/run-training/user` then `cpu-train`, then `rewriteReportRedirect` → FCC `tab=training-report-view`. Draft `gob_training_form_draft_*` cleared `trainingDirty` on save, so leave-confirm never fired.

**Now:** Advance on a training week goes to `/training.html` in **focus** (same chrome as Set Lineup: top bar, no rail, no Prep sub-tabs, no shell `#play-now`). That page owns weekly allocation, requirements, Auto-Train, Playbook Training, Coaching Focus, and green `#submit-btn` "Submit Training". Back is "Back to Locker Room". Submit → Training Report drill-in → Office, unchanged. Prep › Player Training mounts the same module with `sections: 'player-dev'`: Player Development grid only, plus one line "Weekly training is set when you advance." No sliders, Coaching Focus, or Submit. After week 26 Advance stays the tournament game and never opens `/training.html`. Camp week 1 still opens the focus page (`session_type=preseason`). Tutorial (`training.html?mode=tutorial`) stays on the file and now uses weekly focus chrome.

## Host choice

**`training.html` as a focus page** (`gobShell.js` PAGES `kind: 'focus'`), not a shell focus route.

Set Lineup is a standalone file + `html.gob-focus` (authGuard injects gob-tokens / gob-shell.css / gobShell.js; `mountFocus` → `buildTop(false)`). Weekly training is the same kind of Advance step. A shell-internal focus route would still sit inside FCC history and keep Prep chrome unless we special-cased it. Reusing `training.html` also matches the Office week-strip `route: '/training.html'` and `training-playbooks.js` return URL.

## What moved where

| Surface | Weekly allocation / Coaching Focus / Auto-Train / Submit | Player Development grid |
|---|---|---|
| Advance → `/training.html` (focus) | Yes (`init(root, { sections: 'weekly' })`) | Hidden |
| Prep › Player Training | Hidden | Yes (`init(root, { sections: 'player-dev' })`) |
| Tutorial `training.html?mode=tutorial` | Yes (weekly focus) | Hidden |

One implementation: `training.js` `init` / `teardown` / `revalidate` / `shellHtml` plus `applySections()`. `collectTrainingData` and the user/cpu POST path are untouched.

Kept: weekly draft persistence (`sessionStorage`); dirty stays true after draft save so `GOBLeaveConfirm` can fire on the focus page (Keep Draft / Discard / Keep Editing). Per-player Saved toast stays on the Prep tab. Auto-Train, custom-focus modal, requirements bar. SFX: Advance only via `#play-now`; `#submit-btn` is `SFX_COMMIT`. Gate B: module views read `window.FranchiseContext.get` / `toSearchParams` only. `training.html` no longer reads `URLSearchParams(location.search)` to redirect.

## Payload-identical proof

`collectTrainingData` and the `/franchise/run-training/user` body shape are unchanged. e2e `training-advance-focus.spec.js` (a) allocates the same 24-point pattern as today's in-app test (first slider 5, next four 4, sixth 3, Discipline) and asserts `JSON.parse(request.postData())` equals:

```
franchise_id: 6abbd5c3042952060db8726e
team_id: 69a6fcb68d2c56aa82e48a54   # FranchiseContext team id (same as today's liveParams)
training_data.player_drills.offense { inside: 5, outside: 4 }
training_data.player_drills.defense { inside: 4, outside: 4 }
training_data.player_drills.technical { passing: 4, ball_handling: 3, rebounding: 0 }
coaching_focus: authoritarian-discipline
playbook_training_mode: current-playbooks
training_playbook_focus: null
```

Passed in Playwright.

## Tutorial

`training.html` no longer redirects. `mode=tutorial` inits weekly focus on that file (focus chrome, `#submit-btn`, sliders). `GOBTutorialAlerts.interceptTraining` already stored `/training.html?…`; gobAdvance now navigates there, so the resume URL matches the docs. Desktop may still show the Player Attributes intercept first; "I'll do this later" continues to the focus page (`onLaterAdvance`).

## Screenshots (`reports/training-advance-focus/`)

| File | What |
|---|---|
| `before-flow-in-app-1280.png` | Develop: weekly allocation on Prep › Player Training; Advance overridden to Submit Training |
| `before-prep-player-training-1280.png` | Same develop Prep tab at 1280 |
| `before-prep-player-training-1920.png` | Develop Prep tab at 1920 |
| `after-focus-default-1280.png` | New weekly focus page, empty allocation |
| `after-focus-allocated-unsaved-1280.png` | 24/24 + Discipline, Submit enabled |
| `after-submit-report-1280.png` | Training Report drill-in after Submit |
| `after-prep-player-training-1280.png` | Prep tab: PDG + pointer only; Advance still "Run Training" |
| `after-focus-default-1920.png` | Focus page at 1920 |
| `after-set-lineup-chrome-1280.png` | Set Lineup focus chrome for comparison (no rail, no shell Advance) |
| `after-tutorial-1280.png` | Tutorial weekly focus |

## Files

- `FrontEnd/static/js/shared/gobAdvance.js` — `mode=training` → `/training.html`
- `FrontEnd/static/js/shared/gobShell.js` — `training.html` `kind: 'focus'`
- `FrontEnd/static/js/shared/views/trainingView.js` — `sections: 'player-dev'`; no Advance override
- `FrontEnd/static/training.js` — sections flag, applySections, leave-confirm, no `#play-now` override; submit → `/training-report.html`
- `FrontEnd/static/training.html` — drop FCC redirect; always weekly init + gobLeaveConfirm
- `FrontEnd/static/training-report.html` — focus host; drop FCC redirect
- `FrontEnd/static/training-report.js` — Continue to Office / Back to Locker Room
- `FrontEnd/static/js/shared/gobViews.js` — retire `training-report-view`; `/training-report.html` is a real page
- `FrontEnd/static/js/shared/commandCenterTabs.js` — remap old tab to standalone
- `FrontEnd/static/js/shared/officeHome.js` — All changes → `/training-report.html`
- `FrontEnd/static/franchise-command-center.html` — remove `#training-report-view`
- `FrontEnd/static/training-shell.js` — submit button + pointer (hidden in player-dev)
- `FrontEnd/static/training.css` — pointer + player-dev hide rules
- `_documentation_master/11_Design_Systems/UX_System.md` — Prep + Advance + coverage table
- `reports/coverage-map-2026-09-29.md` / `.csv` — training.html is focus, not a redirect stub
- Tests: `training-advance-focus.spec.js`, `prep-modules-training.spec.js`, `navigation-fixes-3.spec.js`, `player-training-followup.spec.js`, `polish-prep-plan.spec.js`, `prep-scouting.spec.js`, `shell-2.spec.js`, `test_prep_modules_training.py`

## Gates

- `../gob-simplified/.venv/bin/python -m pytest --ignore=tests/e2e -q`: **4203 passed**, 14 skipped, 109 xfailed, **1 xpassed**, **0 failed** (226.20s). The xpass is pre-existing (not this branch).
- Playwright (`env -u CI PORT=8260 BASE_URL=http://localhost:8260`, workers=1): **787 passed**, 6 skipped, **0 failed** (12.0m). Includes training-advance-focus a–j (report add-on).
- `scripts/check_ui_tokens.py --strict --no-write`: **exit 0**. New colour-law 0 / 0 / 0. Legacy 210 green / 610 orange / 0 reward-gold (820).
- `scripts/ci/check_migration_gates.py`: **passed**. Gate A: 0 imports in 0 files. Gate B: 134 lines in 42 files. Notes: `training.html` and `training-report.html` are now clean (0, was 1 each). Did **not** `--write-allowlist`.

## Add-on: Training Report is a standalone focus page

**Today (this branch, before the add-on):** Submit Training rewrote the server `/training-report.html` redirect to FCC `?tab=training-report-view`. Office "All changes →" used `viewHref` to the same tab. `training-report.html` itself redirected into FCC. The report sat in the Command Center with rail/origin chrome; Back was "Back to Office" / "← Back" / "← News".

**Now:** `/training-report.html` is `kind: 'focus'` (same chrome as weekly training and Set Lineup: top bar, no rail, no Prep sub-tabs, no shell `#play-now`). One implementation: `training-report.js` `init` / `teardown` / `revalidate` / `shellHtml` on that file. After Submit Training, land here with "Continue to Office" (`tut_alert=training_return` unchanged). Office "All changes →", News dispatches, and the old `/training-report.html` URL open the same page. Old `?tab=training-report-view` remaps (`gobShell` boot + `commandCenterTabs.leaveForStandaloneReport`) carrying `franchise_id` / `team_id` / `week`. From Office or News the exit is "Back to Locker Room" and `GOBNav.back` returns to wherever the player came from. The in-FCC `training-report-view` tab is unregistered and the empty panel is gone. Report body tokens are unchanged (`inAppShell()` treats `html.gob-focus` as the token path so hero accents stay CSS-only).

| File | What |
|---|---|
| `before-report-fcc-1280.png` | In-FCC report after Submit (this branch, before the add-on) |
| `after-submit-report-1280.png` | Submit → standalone focus report |
| `after-report-from-office-1280.png` | Office All changes → standalone |
| `after-report-standalone-1280.png` | Direct `/training-report.html` |
| `after-report-standalone-1920.png` | Same at 1920 |
| `after-set-lineup-chrome-1280.png` | Set Lineup focus chrome (unchanged compare) |

## Unsure

- Desktop tutorial intercept still fires on first Advance if `__gobAuthMeData` has no dismissals; the later-advance path is the same as today.
- `team_id` on the submit body is FranchiseContext's resolved id (ObjectId), not the display name in the FCC query. Same as today's `liveParams()`.
