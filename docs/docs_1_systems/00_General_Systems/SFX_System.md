# SFX System

Sound effects used across the app. Assets live under `FrontEnd/static/sounds/`. Playback uses root-relative `/sounds/` with `encodeURIComponent(filename)` for names with spaces/parentheses. Volume is typically 0.7; playback is wrapped in try/catch and `play().catch(() => {})` to avoid autoplay errors.

---

## Timeout popup

| Trigger | Sound | Asset | Volume | Location |
|--------|--------|-------|--------|----------|
| Timeout popup appears (user-called timeout) | Airhorn | `sounds/Timeout - Airhorn.mp3` | 70% | `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js` |
| Computer timeout (navigate to lineup) | Airhorn | `sounds/Timeout - Airhorn.mp3` | 70% | `timeoutButtonManager.js` → `showTimeoutPopup(computerTimeout: true)` |

The airhorn plays when the user calls a timeout and the “**[Team] Called Timeout**” popup (with “Go To Timeout” button) is shown. For **user** timeouts, playback is immediately before the popup; for **computer** timeouts, at the start of `showTimeoutPopup(computerTimeout: true)` with an 800 ms delay before navigation so it's audible. Sounds are loaded on demand via `ensureTimeoutSounds()` so the airhorn works for computer timeouts even if the timeout button was never initialized.

---

## Lineup

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Player dropped into a lineup slot | Click | `Click (1).mp3` | `FrontEnd/static/set-lineup.js` — `playSound('Click (1).mp3')` in both drop handlers (slotsContainer `drop` and slot `drop` in `setupSlotDragAndDrop`) |
| Click row (no drag) to add player to next slot | Click | `Click (1).mp3` | `FrontEnd/static/set-lineup.js` — roster row click before `fillNextSlot()` |
| Red X — remove player from slot | Collapse/expand | `Collapse & Expand.mp3` | `FrontEnd/static/set-lineup.js` — slot `.remove` button click before `clearSlot()` |
| Game Plan button | Button click | `buttonClickSound.wav` | `FrontEnd/static/set-lineup.js` — `#gameplan-optional` click |
| Playbooks button | Button click | `buttonClickSound.wav` | `FrontEnd/static/set-lineup.js` — `#playbooks-button` click |
| Box Score button | Button click | `buttonClickSound.wav` | `FrontEnd/static/set-lineup.js` — `#box-score-button` click |
| Autoset Lineup button | Confirm | `Confirm - Option 1 (3).mp3` | `FrontEnd/static/set-lineup.js` — at start of `autosetLineup()` |

---

## Save actions

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Save Game Plan (main button or modal "Save Game Plan") | Confirm | `Confirm - Option 1 (3).mp3` | `FrontEnd/static/game-plan.js` — before `saveGamePlan()` |
| Save Playbooks (submit or modal "Save Playbooks") | Confirm | `Confirm - Option 1 (3).mp3` | `FrontEnd/static/playbooks.js` — at start of `handleSubmit()` |

---

## Playbooks screen

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| 1–6 slot buttons (assign play to Playcall Center slot) | Pace | `Pace buttons.wav` | `FrontEnd/static/playbooks.js` — at start of `handleSlotClick()` |
| Even Distribution (per section) or Even Distribution - All | Handgun | `handgun.mp3` | `FrontEnd/static/playbooks.js` — at start of `handleEvenDistribution()` and `handleEvenDistributionAll()` |

---

## FCC / TCC — nav buttons

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Game Plan button (FCC) | Button click | `buttonClickSound.wav` | `FrontEnd/static/franchise-command-center.js` — `#set-gameplan-franchise` click |
| Playbooks button (FCC) | Button click | `buttonClickSound.wav` | `FrontEnd/static/franchise-command-center.js` — `#playbooks-franchise` click |
| Scouting Report button (FCC) | Button click | `buttonClickSound.wav` | `FrontEnd/static/franchise-command-center.js` — at start of `loadScoutingReport()` |
| Game Plan button (TCC) | Button click | `buttonClickSound.wav` | `FrontEnd/static/tournament.js` — `#set-gameplan-tournament` click |
| Playbooks button (TCC) | Button click | `buttonClickSound.wav` | `FrontEnd/static/tournament.js` — `#playbooks-tournament` click |
| Scouting Report button (TCC) | Button click | `buttonClickSound.wav` | `FrontEnd/static/tournament.js` — at start of `loadScoutingReport()` |

---

## Playcall Center (court)

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Offense play selected (user clicks a play in the offense scroller) | Confirm | `Confirm - Option 2 (1).mp3` | `FrontEnd/static/court.html` — offense `#offense-play-scroller` click handler |
| Defense play selected (Man/Zone) or aggression selected (Passive/Normal/Aggressive) | Confirm | `Confirm - Option 2 (1).mp3` | `FrontEnd/static/court.html` — defense override button click handler |
| Offense play up/down toggle arrows (▲ ▼) | Defense | `Defense buttons.wav` | `FrontEnd/static/court.html` — `#play-nav-up` and `#play-nav-down` click handlers |
| Red X — clear offense override | Collapse/expand | `Collapse & Expand.mp3` | `FrontEnd/static/court.html` — `#clear-offense-override-x` click |
| Red X — clear defense override | Collapse/expand | `Collapse & Expand.mp3` | `FrontEnd/static/court.html` — `#clear-defense-override-x` click |
| Red X — clear aggression override | Collapse/expand | `Collapse & Expand.mp3` | `FrontEnd/static/court.html` — `#clear-aggression-override-x` click |

---

## Play Game

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Play Game button (Lineup screen, `#play-now`) | Offense | `Offense buttons.wav` | `FrontEnd/static/set-lineup.js` — before navigating to court; navigation delayed 200 ms so sound can start |
| Play Game button (Game Plan screen) | Offense | `Offense buttons.wav` | `FrontEnd/static/game-plan.js` — `btnNavPrimary` click when label is "Play Game"; `navigateToCourt()` delayed 200 ms so sound can start |

---

## Foul / turnover announcements

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Shooting foul, offensive foul, defensive non-shooting foul, dead ball turnover — when the on-screen announcement appears | Match wise | `matchWisel.mp3` | `FrontEnd/static/js/phaser/utils/announcements.js` — in `showAnnouncement()` when text is foul- or dead-ball-turnover-related; in `showAndOneAnnouncement()` for AND-1 (shooting foul). **Not** played for STEAL! (live-ball turnover). |

Playback is synced to the moment the announcement is shown (same frame as adding to DOM / adding `active` class).

---

## FCC / TCC / Tutorials — tab click

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| New tab selected in Franchise Command Center | Back | `X (Back) (3).mp3` | `FrontEnd/static/js/shared/commandCenterTabs.js` — tab button click |
| New tab selected in Tournament Command Center | Back | `X (Back) (3).mp3` | Same shared module |
| New tab selected in Tutorials (Player Attributes, Team Attributes, Game Plans, Playbooks, Training) | Back | `X (Back) (3).mp3` | `FrontEnd/static/tutorial.html` — `.tutorial-tab` click |

---

## Tutorials — accordion expand

| Trigger | Sound | Asset | Location |
|--------|--------|-------|----------|
| Any accordion header expanded (e.g. Scoring (SC), Fight, Discipline) in any Tutorial tab | Cycle | `Team Cycle (1).mp3` | `FrontEnd/static/tutorial.html` — `.tutorial-attr-toggle` click, when toggling to open (`isOpen === true`) |
