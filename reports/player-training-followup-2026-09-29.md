# Player Training follow-up — 2026-09-29

Jamie's batch C answers: the Training Report is a drill-in, per-player saves stay instant and toast, one measure vocabulary everywhere, and the dead post-week-26 FCC fallback is replaced by a real tournament state on Player Training.

Branch: `ux/player-training-followup` (from `origin/develop`, which already had batch C).

---

## 1. Training Report is a drill-in

Player Training (`training-view`) is always the editable settings. Arriving from the Office week-strip "Run training" todo still lands on those settings (`/training.html` → Prep › Player Training).

`training-report-view` is a GOBNav-push drill-in (`TAB_SECTION` `'detail'`). It is not a Prep sub-tab. `detailMark` returns `''` so nothing underlines Player Training while the report is open. `?origin=` still lights the rail you came from.

`gob-office` is the Office-*home* layout (week cards, no page head). Lighting the Office rail via `?origin=office` used to turn that layout on, which forced `#home-tab` visible and stacked the week cards on the report. `gob-office` now applies only when the tab is `home-tab`. The Office rail can still be on.

### Report entry points

| From | How it opens | Query | Back |
|---|---|---|---|
| Office digest "All changes" | `officeHome.js` `trainingReportHref` | `tab=training-report-view&from=office&origin=office` | ← Back → Office (GOBNav.back) |
| Office week strip "Run training" | `todo.route` `/training.html` | settings, not the report | — |
| Post-submit / Run Training | `training.js` `rewriteReportRedirect` (server still returns `/training-report.html?from=training`) | rewritten to `tab=training-report-view&from=training&origin=prep` | **Back to Office** + `tut_alert=training_return` |
| Submitted-week note on Player Training | `training.js` `trainingReportHref` | `from=training&origin=prep` | same as post-submit |
| News dispatch | `franchise_routes.py` news items `type=training_report` | `/training-report.html?from=news&origin=news` (GOBViews rewrite → FCC tab) | **← News** |
| Standalone `/training-report.html` | `gobViews.js` `drillUrl` + `training-report.html` bootstrap | infers `origin` from `from` (`news`/`inbox` → news, `office` → office, else prep) | as above |
| Week strip | does **not** open the report | opens Player Training settings | — |

Top-bar Advance on the report is the normal week Advance (Run Training / Play Next Game / …). Advance on Player Training is still Submit Training / Run Training Camp, except on a closed-allocation week (see §4).

---

## 2. Per-player save toast

`POST /franchise/player/development-focus` still fires on every `training_position` / `training_focus` change. Success: GOBToast **"Saved"**, debounced 400ms so a run of changes is one toast. Failure: **"Not saved. Try again."** and the select reverts to `data-devfocus-prev`. No orange Save, no leave-check.

---

## 3. One vocabulary

Display strings only. Data keys (`pt_efficiency`, `fb_efficiency`, `pt_opp_modifier`, …) unchanged. Playcall Center "Press/Trap" setter and gameplay event names left alone.

Renamed in the listed surfaces plus the leftover grep hits in those same files:

- P/T Offense
- P/T Defense
- Fast Break
- Fast Break Defense

Covered: `court.html`, `box-score.js` (including `fb_opp_modifier` / `pt_opp_modifier`), `training-report.js` (+ `NOTES_TACTICAL_DISPLAY_TITLES` maps stored `'Press/Trap Readiness'` → display `'P/T Defense Readiness'`), `training.html` install/coaching labels, `officeHome.js` measure chips, `tutorial-scouting.html`, `tutorial-team-attributes.html`, `tutorial-training.html`, `tutorial-advanced-press-trap.html` measure names, `training-report.css` comment, `teamAttributesView.js` comment.

Grep of `FrontEnd/static` `*.{js,html,css}` for `Press/Trap Efficiency`, `Press/Trap Defense`, `Press Break`, `Fast Break Offense` as display text: **no hits**. `tests/test_measure_vocabulary.py` pins that.

---

## 4. Post-week-26 (tournament) state

**What happened today.** `commandCenterTabs.canonicalTab` already mapped `training-tab` → `training-view` before `onTabShow`, so `renderFccTrainingTab` never ran. The "fallback" for `/franchise/training-points` 400 after week 26 was dead. Opening Player Training after week 26 hit the 400, skipped the roster, and could show 0/NaN on the points chip.

**What we did (small and clear).**

- `GET /franchise/training-points` returns **200** after week 26 with `training_unavailable: true`, `training_points: 0`, and the custom-focus roster so the grid still binds.
- Player Training stays on the settings page. Weekly sliders / coaching / Points / Auto-Train hide. Note: *"No team training during the tournament — player development focus still applies"*.
- Advance is the normal tournament Advance (not Submit Training). A `trainingAllocationClosed` flag stops `syncTrainingAdvance` from putting Submit Training back after `GOBTraining.syncAdvance()`.
- The dead `#training-tab` / `#fcc-training-dev` panel and `renderFccTrainingTab` / `wireFccTrainingTutorialButton` / `fccMaxPositionRating` are deleted. Nothing reached them.

Online vs desktop: same FCC shell and same endpoints. Desktop only changes auth/chrome, not this path.

---

## Tests

- `tests/e2e/player-training-followup.spec.js` — 7 passed (settings after submit; drill-in, no Player Training highlight, no `gob-office` stack, ← Back; `tut_alert=training_return`; Saved toast; fail + revert; week-26 note + hidden allocation + Advance not Submit Training).
- `tests/test_measure_vocabulary.py` — 2 passed.
- `tests/test_player_development_grid.py` — 24 passed (single editor).
- `tests/e2e/shell-1b.spec.js` / `office-frontend.spec.js` updated for `training-view` / `origin=office`.

---

## Screenshots (1280×720)

All four opened and checked:

| File | Self-check |
|---|---|
| `reports/player-training-followup/player-training-1280.png` | Settings (sliders + coaching). Empty state-note box gone. Player Training underlined. Advance = Submit Training (green). Fast Break / P/T install labels. No gold. |
| `reports/player-training-followup/training-report-drillin-1280.png` | Title Training Report. ← Back. Office rail on, no Prep sub-tab selected. No Office week cards. Advance = Run Training (normal). |
| `reports/player-training-followup/player-save-toast-1280.png` | Neutral "Saved" toast after a focus change. |
| `reports/player-training-followup/post-week-26-1280.png` | Tournament note, no empty link pill, no Points/Auto-Train. Advance = Play Conference Tourney Semifinals. Player Development grid still editable. |

1920 not needed — no layout breakpoint change.

---

## UX_System §8 merge gate

- pytest `--ignore=tests/e2e`: **4052 passed**, 16 skipped, 109 xfailed, 1 xpassed, **0 failed**.
- Full Playwright (`tests/e2e`, workers=1, port 8157, CI unset, after `ps` showed no other Playwright): **649 passed**, 3 skipped, **0 failed** (9.3m).
- Playwright follow-up spec (this work): **7 passed**.

---

STATUS: COMPLETE
