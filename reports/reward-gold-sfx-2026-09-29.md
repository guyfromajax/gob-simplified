# Reward gold + sound module (2026-09-29)

Chapter 7 groundwork. No screen redesign. Tokens are defined only. Two proofs: Advance `data-sfx`, championship season-peak sting.

Branch: `feat/reward-gold-sfx` from `origin/develop`.

## Tokens added

In `FrontEnd/static/css/gob-tokens.css`, next to `--green` / `--orange`, unused anywhere else:

| Token | Value | Role |
| --- | --- | --- |
| `--reward-gold` | `#E8B84A` | Placeholder until the Chapter 7 Claude Design handoff. ONLY milestone / season-peak rewards + exceptional stat gains. |
| `--reward-gold-12` | `color-mix(in srgb, var(--reward-gold) 12%, transparent)` | Tint, same mix pattern as the other alpha tints. |
| `--reward-gold-24` | `color-mix(in srgb, var(--reward-gold) 24%, transparent)` | Tint. |
| `--shadow-reward` | Same shape as `--shadow-advance`, gold instead of green | Elevation for those reward surfaces when they land. |

Never for buttons, Advance (green), "yours" (navy), choice controls, or everyday / weekly tiers. Documented in `UX_System.md` §1.

## Module API

`FrontEnd/static/js/shared/uiSfx.js` is still the only volume bus (`master × channel`, mute, `gob_audio_v1`). Same `/sounds/` base and storage key online and in the desktop build.

Named catalog (constants keep their filenames so existing `playSfx('click-tiny.wav')` callers still work):

| Name | File |
| --- | --- |
| `SFX_ADVANCE` | `confirm-1-lowervol.wav` |
| `SFX_SELECT` | `click-tiny.wav` |
| `SFX_COMMIT` | `click-beep.wav` |
| `STING_WIN` | `sting-win.mp3` (Jamie; missing today) |
| `STING_MILESTONE` | `sting-milestone.mp3` (Jamie; missing today) |
| `STING_SEASON_PEAK` | `sting-season-peak.mp3` (Jamie; missing today) |

- `playSfx(name, baseVolume = 0.7)` — name key, filename, or constant. Respects the sfx channel (muted or master 0 → no `Audio`, no play). Lazy preload of the three existing UI files on hook install; stings load on first play. Short UI sounds overlap. A new sting stops the previous sting. Missing file: one `console.debug` per name, `play()` rejection swallowed, never throws, never awaited by a modal or navigation.
- `installSfxHooks(document)` — one delegated click listener per document. Plays `data-sfx="<name>"` on `button`, `a`, and `[role="tab"]`. Unknown names ignored. Auto-installs when the module loads.
- `playAdvance` / `playSelect` / `playCommit` unchanged.
- `window.GOBUiSfx` exposes the same surface plus the six names and `installSfxHooks`.

## Two proofs

1. **Top-bar Advance.** `#play-now` has `data-sfx="SFX_ADVANCE"` (HTML, `gobShell` adopt/create, `GOBAdvance.bind`). `onAdvanceClick` no longer calls `playSound('confirm-1-lowervol.wav')`. One play per click. New-season modal proceed still uses the direct confirm (not the top-bar button).
2. **Championship moment.** `championshipMoments.js` `showMoment` calls `playSfx(STING_SEASON_PEAK)` after the variation is appended. Fire-and-forget. Silent until Jamie's file exists; does not block the overlay.

No other screens gained `data-sfx`.

## Sound inventory (report only — Chapter 8 sweep)

### Plays a UI sound today

| file::function | Sound | Trigger |
| --- | --- | --- |
| `gobAdvance.js::onAdvanceClick` | `SFX_ADVANCE` via `data-sfx` | `#play-now` click (this task) |
| `gobAdvance.js::new-season proceed` | `confirm-1-lowervol.wav` | `#fcc-new-season-proceed` |
| `championshipMoments.js::showMoment` | `STING_SEASON_PEAK` | overlay open (this task) |
| `championshipMoments.js::variation click` | `click-tiny.wav` via `window.playSound` | `[data-cm-action]` (silent if `playSound` unset) |
| `officeHome.js::clickTiny` / `go` | `SFX_SELECT` | office card / link navigation |
| `gobShell.js::playClick` | `click-tiny.wav` | rail section, sub-tab, tutorials, feedback, settings, exit |
| `gobShell.js` focus back | `x-back.mp3` | focus-mode back |
| `commandCenterTabs.js` tab click | `click-tiny.wav` | in-page tab / `data-route` |
| `franchise-command-center.js::navigateToGamePlan` | `click-tiny.wav` | Set Game Plan |
| `franchise-command-center.js::wireFccNavButtons` | `click-tiny.wav` | Playbooks legacy button |
| `franchise-command-center.js` exit | `x-back.mp3` | `#exit-franchise` |
| `franchise-command-center.js` cut-required close | `confirm-1-lowervol.wav` | practice-squad required modal |
| `game-plan.js` PLAY NOW | `SFX_ADVANCE` via `playAdvance` | funnel CTA |
| `game-plan.js` slider change | `click-tiny.wav` | strategy slider |
| `game-plan.js` save / warning confirm | `confirm-2-lowervol.wav` | Save Game Plan |
| `game-plan.js` page back | `x-back.mp3` | command-center back |
| `playbooks.js` many click handlers | `click-tiny.wav` | tabs, rows, editors |
| `playbooks.js` save | `confirm-2-lowervol.wav` | Save Playbooks |
| `training.js::navigateToTrainingTutorial` | `click-tiny.wav` | tutorial link |
| `training.js::wirePlayerDevelopmentTutorialButton` | `click-tiny.wav` | player-dev tutorial |
| `training.js::onCustomFocusCellClick` | `click-tiny.wav` | custom-focus cell |
| `training.js` slider change | `click-tiny.wav` | drill sliders |
| `training.js::autoAssignTraining` | `chaotic-choice.wav` | Auto-Train |
| `training.js` auto-train modal close | `click-tiny.wav` | close |
| `training.js` coaching-focus change | `whistle-3` / `positive-slide` / `positive-plop` / `positive-beep` | archetype radios |
| `training.js` pm-modal mode | `click-tiny.wav` | player-maximizer mode |
| `training.js` custom-focus assign | `confirm-1-lowervol.wav` | Assign |
| `training.js` custom-focus cancel | `click-tiny.wav` | Cancel |
| `training.js::submitTraining` | `confirm-2-lowervol.wav` | Submit |
| `training.js::wireCustomTrainingPlaybook` | `click-tiny.wav` | playbook mode toggle |
| `training.js` req-focus nudge | `click-tiny.wav` | requirements bar |
| `training-report.js` | `click-tiny.wav` / `click-strong.wav` | tabs / continue |
| `training-playbooks.js` | `click-tiny.wav` / `confirm-2-lowervol.wav` | select / save |
| `set-lineup.js` view tabs | `click-tiny.wav` | Game / Attr / Stats |
| `set-lineup.js` drop / fill | `click-soft.mp3` | assign |
| `set-lineup.js` row remove | `x-back.mp3` | clear slot |
| `set-lineup.js::autosetLineup` | `chaotic-choice.wav` | Auto-set |
| `set-lineup.js::wireLineupNavButtons` | `positive-beep` / `positive-slide` | game plan / playbooks / box score |
| `set-lineup.js` Play | `confirm-1-lowervol.wav` | Advance to court / game plan |
| `set-lineup.js` view-toggle | `click-tiny.wav` | court/player toggle |
| `cut-players.js` | `click-tiny` / `confirm-1` / `confirm-2` | row / confirm / submit |
| `box-score.js` | `click-tiny.wav` / `x-back.mp3` | tabs / back / locker room |
| `mode-select.js` | `click-beep.wav` / `click-strong.wav` | tiles / enter / delete |
| `teamPicker.js` | `click-beep.wav` | team pick |
| `team-builder.js` | `confirm-1-lowervol.wav` | commit |
| `franchise-select-team.js` | `click-beep` / `click-tiny` / `confirm-1` | list / row / enter |
| `homepage-v2.js` / `homepage-v3.js` | `click-strong` / `click-tiny` | CTA / secondary / feedback |
| `alpha-feedback.html` | `click-tiny.wav` | form controls |
| `authBarInit.js` | `click-tiny.wav` | feedback open |
| `gobTutorialNav.js` | `x-back.mp3` / `click-tiny.wav` | back / next |
| `gobTutorialHub.js` | `click-tiny.wav` | topic / reset |
| `gobTutorialAlertResume.js` | `click-tiny.wav` | resume |
| `gobPlayerAttributes.js` | `click-tiny.wav` | tile |
| `tutorial-situation.js` / `tutorial-pick-opponent.js` / `tutorial-persona-intro.js` | `playAdvance` / `playSelect` | continue / pick |
| tutorial HTML pages | `GOB.playSound` | in-page clicks |
| `court.html::playSound` | `confirm-2` / `x-back` / `click-tiny` | pause / timeout / box / leave |
| `gameScene.js` / `bootGame.js` | `click-tiny` / `positive-*` via `window.playSound` | HUD / EOG |
| `gameCompletionPopup.js` / `postGamePressConference.js` / `foulOutPopup.js` / `timeoutButtonManager.js` / `pgpcSammyReminderModal.js` | `click-tiny.wav` via `window.playSound` | modal actions |
| `matchupsUiShared.js::playMatchupsUiSfx` | caller filename via `window.playSound` | matchup UI |

`recruiting-common.js::playSound` and `gobTutorialAlerts.js::sfx` are defined and unused.

### Button / tab types with no sound (Chapter 8)

- Settings gear (rail, focus top-bar, auth-bar) and every control inside `gobSettings` (sliders, mute, logout, FAQs, close, scrim).
- News / Awards inner tabs, filters, and article rows.
- Player Stats sort headers and filters.
- Team Attributes tiles (non-tutorial).
- Team Schedule opponent / result / week controls.
- Scouting filters, usage unlocks, and player rows.
- Recruiting board, watchlist, invite, and visit controls (`recruiting-common` helper is dead).
- Practice-squad / cut list chrome that is not the confirm/submit path.
- Championship moment actions when `window.playSound` is missing (FCC often).
- Auth login / signup submit.
- Office week-strip / digest chips that are not `officeHome` `go` links.
- Choice controls that are not already wired in Training (most radios/checks elsewhere).
- Modal dismiss X / backdrop on most franchise dialogs.

## Tests

- `tests/test_ui_sfx.mjs` — existing volume/mute plus mute/master-0 skip and unknown-name ignore. **8 passed.**
- `tests/e2e/reward-gold-sfx.spec.js` — `data-sfx` once; sfx mute → no play; master 0 → no play; missing sting → no `pageerror`, modal still closes; Advance once per click; championship open requests `sting-season-peak.mp3`. **4 passed** (isolated run).

## Gate counts (UX_System §8)

- `.venv/bin/python -m pytest --ignore=tests/e2e -q` → **3918 passed, 16 skipped, 109 xfailed, 1 xpassed, 0 failed.**
- Full Playwright (`tests/e2e`, workers=1, `PORT=8088`, `CI` unset, no other Playwright run): **550 passed, 3 skipped, 1 failed** on first pass. The failure was `office-frontend.spec.js` “standings show every conference team…” at 1440×900 (`window` 5/8 instead of all 8). Unrelated to tokens/sfx (no standings CSS). Immediate retry of that test **passed**. Our new spec is in the 550.

Server on 8088 stopped. Regenerated `reports/*` screenshots restored with `git checkout -- reports/`. This file is new.

STATUS: COMPLETE
