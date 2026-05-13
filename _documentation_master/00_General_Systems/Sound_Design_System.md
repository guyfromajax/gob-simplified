# Sound Design System

Sound effects used across the app. Assets live under `FrontEnd/static/sounds/`. The canonical spec is `FrontEnd/static/sounds/_SFX_notes.md`. Playback uses root-relative `/sounds/` with `encodeURIComponent(filename)` for names with spaces/parentheses. Volume is typically 0.7; playback is wrapped in try/catch and `play().catch(() => {})` to avoid autoplay errors.

---

## Sound name → file reference

| Short name       | Filename           |
|-----------------|--------------------|
| click-strong    | click-strong.wav   |
| click-tiny      | click-tiny.wav     |
| click-beep      | click-beep.wav     |
| click-handgun   | click-handgun.mp3  |
| click-soft      | click-soft.mp3     |
| x-back          | x-back.mp3         |
| positive-beep   | positive-beep.wav  |
| positive-slide  | positive-slide.wav |
| positive-plop   | positive-plop.wav  |
| confirm-1       | confirm-1-lowervol.wav      |
| confirm-2       | confirm-2-lowervol.wav      |
| movement-cycle  | movement-cycle.mp3 |
| chaotic-choice  | chaotic-choice.wav |
| whistle-3       | whistle-3.mp3      |

---

## Homepage

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Play Alpha button (carousel CTA) | click-strong | `click-strong.wav` | `FrontEnd/static/homepage-v2.js` — `.carousel-cta` click |

---

## Top Nav Bar

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Tutorials button | click-tiny | `click-tiny.wav` | `FrontEnd/static/js/shared/authBarInit.js` — `.tutorials-nav-btn` click |
| Feedback button | click-tiny | `click-tiny.wav` | `authBarInit.js` — `#feedback-btn` → `openModal()` |

---

## Tutorials

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Tab headers (Player Attributes, Team Attributes, etc.) | click-tiny | `click-tiny.wav` | `FrontEnd/static/tutorial.html` — `.tutorial-tab` click |
| Closing an accordion section | movement-cycle | `movement-cycle.mp3` | `tutorial.html` — `.tutorial-attr-toggle` click when toggling to closed (`!isOpen`) |

---

## Mode-Select

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Play Now (Scrimmage, Tournament, Franchise) | click-strong | `click-strong.wav` | `FrontEnd/static/mode-select.js` — scrimmage-btn, tournament-play-now-btn, franchise-play-now-btn |
| New Tournament / New Franchise | click-beep | `click-beep.wav` | `mode-select.js` — tournament-new-btn, franchise-new-btn |

---

## Team-Select

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Team buttons (Single Game / Scrimmage) | click-handgun | `click-handgun.mp3` | `FrontEnd/static/team-select.js` — logo button click and drop |
| Team buttons (Tournament / Franchise) | click-beep | `click-beep.wav` | `tournament-select.js`, `franchise-select-team.js` — team button click |
| Play Now (Single Game) | click-beep | `click-beep.wav` | `team-select.js` — `#play-btn` click |

---

## FCC / TCC

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Exit Tournament / Exit Franchise | x-back | `x-back.mp3` | `tournament.js` — `#exit-tournament`; `franchise-command-center.js` — `#exit-franchise` |
| Set Game Plan, Playbooks | positive-beep | `positive-beep.wav` | `franchise-command-center.js`, `tournament.js` — set-gameplan / playbooks button click |
| Scouting Report | positive-slide | `positive-slide.wav` | `franchise-command-center.js`, `tournament.js` — `loadScoutingReport()` start |
| Play Next Game / Run Training | confirm-1 | `confirm-1-lowervol.wav` | Same files — `#play-now` click |
| Tab headers | click-tiny | `click-tiny.wav` | `FrontEnd/static/js/shared/commandCenterTabs.js` — tab button click |

---

## Game Plan

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Save Game Plan (button or modal) | confirm-2 | `confirm-2-lowervol.wav` | `FrontEnd/static/game-plan.js` — btnSaveGamePlan click, modal Save click |
| Slider move & release | click-tiny | `click-tiny.wav` | `game-plan.js` — slider `change` in `setupSliders()` |
| Back To Locker Room | x-back | `x-back.mp3` | `game-plan.js` — btnNavPrimary (Back To Locker Room) click |
| Play Game | confirm-1 | `confirm-1-lowervol.wav` | `game-plan.js` — btnNavPrimary (Play Game) click; navigation delayed 200 ms |

---

## Playbooks

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Save Playbooks | confirm-2 | `confirm-2-lowervol.wav` | `FrontEnd/static/playbooks.js` — `handleSubmit()` start |
| Playcall Center slot buttons (1–6) | click-tiny | `click-tiny.wav` | `playbooks.js` — `handleSlotClick()` |
| Percentage spinner up/down | click-tiny | `click-tiny.wav` | `playbooks.js` — percentage input `input` when delta ±1 |
| Percentage manual entry (commit) | click-soft | `click-soft.mp3` | `playbooks.js` — percentage input `change` |
| Standard / PG / SG / SF / PF / C (position filter) | positive-plop | `positive-plop.wav` | `playbooks.js` — `.position-filter-btn` click |

---

## Scouting Report Pop-Up

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| X to close | x-back | `x-back.mp3` | `FrontEnd/static/js/shared/scoutingReport.js` — `.scouting-modal-close` click |

---

## Lineup Screen

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Add player (click row or drag & drop into slot) | click-soft | `click-soft.mp3` | `FrontEnd/static/set-lineup.js` — roster row click, slot `drop` |
| Remove player (Red X) | x-back | `x-back.mp3` | `set-lineup.js` — slot `.remove` click before `clearSlot()` |
| Drag & drop within lineup (reorder) | click-soft | `click-soft.mp3` | `set-lineup.js` — slot `drop` when swapping/reassigning |
| Game Plan, Playbooks buttons | positive-beep | `positive-beep.wav` | `set-lineup.js` — `#gameplan-optional`, `#playbooks-button` |
| Box Score button | positive-slide | `positive-slide.wav` | `set-lineup.js` — `#box-score-button` |
| Autoset Lineup | chaotic-choice | `chaotic-choice.wav` | `set-lineup.js` — `autosetLineup()` start |
| Grid View / Player View toggle | click-tiny | `click-tiny.wav` | `set-lineup.js` — `.view-toggle-btn` click |
| Play Game | confirm-1 | `confirm-1-lowervol.wav` | `set-lineup.js` — `#play-now` click; navigation delayed 200 ms |

---

## Gameplay Buttons Popup (court.html)

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Play Quarter | positive-slide | `positive-slide.wav` | `FrontEnd/static/js/phaser/bootGame.js` — `.play-button` click |
| Sim Full Game / Sim Rest of Game | positive-plop | `positive-plop.wav` | `bootGame.js` — `handleSimFullGame()` start |
| Sim Quarter | positive-beep | `positive-beep.wav` | `bootGame.js` — `handleSimQuarter()` start |

---

## Defense Matchups Popup (court.html)

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Drag & drop players | click-soft | `click-soft.mp3` | `FrontEnd/static/js/phaser/utils/defenseMatchupsPopup.js` — drop handler |
| Submit Defense Matchups | confirm-1 | `confirm-1-lowervol.wav` | `defenseMatchupsPopup.js` — `.submit-matchups-button` click |
| Don't show again this game checkbox | click-tiny | `click-tiny.wav` | `defenseMatchupsPopup.js` — `#dont-show-again-checkbox` change |

---

## Playcall Center (court.html)

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Offense play select | confirm-2 | `confirm-2-lowervol.wav` | `FrontEnd/static/court.html` — `#offense-play-scroller` click |
| Up/down toggle arrows (offense plays) | click-tiny | `click-tiny.wav` | `court.html` — `#play-nav-up`, `#play-nav-down` |
| Defense play or aggression select | confirm-2 | `confirm-2-lowervol.wav` | `court.html` — defense override button click |
| Red X (offense, defense, aggression) | x-back | `x-back.mp3` | `court.html` — clear-offense-override-x, clear-defense-override-x, clear-aggression-override-x |

---

## Court UI (in-game)

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Timeout (green UI button) | click-beep | `click-beep.wav` | `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js` — timeout button click |
| Pause / Resume | click-tiny | `click-tiny.wav` | `FrontEnd/static/js/phaser/gameScene.js` — `#pause-btn` click |
| Game Speed (button and options) | click-tiny | `click-tiny.wav` | `gameScene.js` — `#game-speed-btn`, `.speed-option` click |
| In-game popup buttons (Go To Timeout, quarter break, foul out, EOG) | click-tiny | `click-tiny.wav` | `timeoutButtonManager.js` (Go To Timeout); `gameScene.js` (quarter/OT popups); `foulOutPopup.js` (Sub Players); `gameCompletionPopup.js` (Box Score, Go To Locker Room) |

---

## Timeout popup (airhorn)

| Trigger | Sound | Asset | Volume | Location |
|--------|--------|-------|--------|----------|
| Timeout popup appears (user-called timeout) | Airhorn | `airhorn-lowervol.wav` | 70% | `timeoutButtonManager.js` |
| Computer timeout (navigate to lineup) | Airhorn | `airhorn-lowervol.wav` | 70% | `timeoutButtonManager.js` → `showTimeoutPopup(computerTimeout: true)` |

---

## Foul / turnover announcements

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Foul or dead-ball turnover announcement shown | whistle-1 | `whistle-1-lowervol.wav` | `FrontEnd/static/js/phaser/utils/announcements.js` — `showAnnouncement()`, `showAndOneAnnouncement()` when text is foul- or dead-ball-turnover-related. Not played for STEAL! (live-ball). |

---

## Box Score

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Team tabs (Home/Away) | click-tiny | `click-tiny.wav` | `FrontEnd/static/box-score.js` — `.tab-button` click in `setupTabs()` |
| Back | x-back | `x-back.mp3` | `box-score.js` — Back button click (when from lineup/game-plan) |

---

## Training

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Auto-Train | chaotic-choice | `chaotic-choice.wav` | `FrontEnd/static/training.js` — `autoAssignTraining()` start |
| Submit Training | confirm-2 | `confirm-2-lowervol.wav` | `training.js` — submit button click |
| Slider move & release | click-tiny | `click-tiny.wav` | `training.js` — slider `change` |
| Coaching style / focus: Authoritarian (any of four) | whistle-3 | `whistle-3.mp3` | `training.js` — coaching radio `change` when value starts with `authoritarian` |
| Coaching style / focus: Systems Coach (any of four) | positive-slide | `positive-slide.wav` | `training.js` — value starts with `systems-coach` |
| Coaching style / focus: Player Maximizer (any of four) | positive-plop | `positive-plop.wav` | `training.js` — value starts with `player-maximizer` |
| Coaching style / focus: Culture Builder (any of four) | positive-beep | `positive-beep.wav` | `training.js` — value starts with `culture-builder` |
| Close button (auto-training popup) | click-tiny | `click-tiny.wav` | `training.js` — `#auto-train-modal-close` click |

---

## Training Report

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Attributes / Training Changes toggle | click-tiny | `click-tiny.wav` | `FrontEnd/static/training-report.js` — `.toggle-btn` click |
| Go To Locker Room | click-strong | `click-strong.wav` | `training-report.js` — `#locker-room-btn` click |
