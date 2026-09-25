# UX System

Version 1. How to build franchise screens. The look lives in [Styleguide.md](Styleguide.md). Every color, size, and duration lives in `FrontEnd/static/css/gob-tokens.css` under `.gob`. Name the token. Do not copy the value into a page, a component, or this document.

## 1. Principles

- The frontend is a pure renderer. UESS (`_documentation_master/05_UESS_System/UESS_System.md`) owns game logic. A screen formats fields the page already loaded. It does not invent a missing field, derive one, or move a rule to the client.
- One green Advance per screen. It is the only control that uses the advance color. A blocking task becomes the Advance button (same id, same `updatePlayButton` state machine, same labels and routes). There is no disabled-with-lock state and no hint link.
- No spinners. A click that leaves the page switches Advance to the loading look immediately (`is-loading`, label `STARTING…`) and ignores repeat clicks.
- Blue belongs to RT. Do not use the rating blue for chrome, links, or navigation.
- Live gameplay has no shell. The court never mounts `.app`, `.top`, or `.rail`.
- Navigation is two levels: a rail section, then a sub-tab. Do not add a third level.
- Attribute digits stay on the first-digit scale (`attributeDisplay.js`). Player RT stays a letter grade (`rtBucket.js`).

## 2. Tokens and density

Root element: `html.gob` plus one density class.

`gobDensity.js` `bindGobDensity(root)` requires `.gob` already. It adds `.gob-1920` when the viewport matches `(min-width: 1680px) and (min-height: 1000px)`, otherwise `.gob-1280`.

`.gob` fills the viewport (`100vw` / `100vh`). Token names to use for the shell: `--top-h`, `--rail-w`, `--page-pad`, `--bg-chrome`, `--bg-page`, `--line`, `--line-strong`, `--green`, `--text-100`, `--text-60`, `--text-38`, `--white-6`, `--white-10`, `--white-28`, `--font-display`, `--font-body`, `--dur-hover`, `--ease-out`. Density overrides for `--top-h` and `--rail-w` live on `.gob.gob-1280` and `.gob.gob-1920`.

Consume a token with `var(--token-name)` inside a `.gob` subtree. Do not redeclare the value.

Fonts are self-hosted. Display face: `/css/fonts.css` (Bebas Neue Pro). Body face: `/fonts/app-fonts.css` (Inter). Do not add a Google Fonts link.

Shell rules that must not restyle existing franchise cards live in `FrontEnd/static/css/gob-shell.css`, scoped under `html.gob-shell`. `gob-components.css` is scoped under `.gob`. If a component class (`.logo`, `.nm`, `.lnk`, `.card`) would change existing franchise markup, tighten the shell selector. Do not edit the old content CSS to accommodate the shell.

## 3. Audio

`uiSfx.js` is the volume bus. Channels: `master`, `music`, `sfx`, `ambience`. Effective gain is master × channel, or 0 when either is muted. Levels are 0–100.

Persisted in `localStorage` under `gob_audio_v1` (`AUDIO_STORAGE_KEY`). The same record works online and in the offline desktop build.

`playSfx(filename, baseVolume)` plays one file on the `sfx` channel. `baseVolume` defaults to `0.7`. Named files: `SFX_SELECT` (`click-tiny.wav`), `SFX_ADVANCE` (`confirm-1-lowervol.wav`), `SFX_COMMIT` (`click-beep.wav`).

Routed today: `playSfx` callers (rail, sub-tabs, the shared tab strip) and the court sound control (`courtAudio.js`), which mirrors master / music / sfx into this bus. Advance on the franchise page keeps its existing confirm sound in the page click handler.

Not routed: any player that constructs `Audio()` itself and never calls `playSfx` or the court bus. Leave those until that caller is moved onto the bus. Do not add a second volume store.

## 4. Settings panel

Module: `FrontEnd/static/js/shared/gobSettings.js`.

API on `window.GOBSettings`: `open()`, `close()`, `toggle()`, `isOpen()`.

Sections, top to bottom: Audio (four channels, mute and level, applied immediately), Coach stats (only fields `/api/auth/me` already returns; hidden until those fields exist), Account. The footer shows `window.GOB_BUILD_LABEL` when that string is set, and Online / Offline.

Online: Account shows username, email, a link to account details, and log out. Offline (`window.GOB_BUILD_PROFILE === 'desktop'`): Account is the offline note, coach stats are not fetched, and the connection label is Offline.

The gear that opened the panel gets `.open` and `aria-expanded="true"` while it is open. Close with Escape, the scrim, the close control, or the gear again.

## 5. Shell

Mounted only by `gobShell.js` on `franchise-command-center.html`. Standalone pages keep their current header until Shell 2.

Grid: `.app` is `grid-template-rows: var(--top-h) minmax(0, 1fr)` and `grid-template-columns: var(--rail-w) minmax(0, 1fr)`. `.top` spans both columns. `.rail` is column 1. `.main` is column 2 and the only scroller (`overflow-y: auto`). `html` and `body` do not scroll.

Top bar, left to right: team logo and name (existing team field and `#team-logo`; the control opens Team › Roster), divider, Record, National rank, Week. Record text comes from `#fcc-record-label` (standings W-L for the user's team). National rank comes from `#fcc-rank-label` / `data.rank`, shown as `#N` or `NR`. Week comes from `data.week`. There is no Team RT. There is no alpha badge, product logo, or social link. The build label stays in Settings.

Right side: the ghost Edit Recruit Invites button (`#fcc-edit-recruiting`, same show/hide as today) then Advance (`#play-now` with class `advance`). Advance keeps `updatePlayButton`: same labels, `dataset.mode`, and routes. A blocking task replaces the label; it does not disable the button or add a hint.

Tier weeks: when `GOBTierEmblem.tierForWeek(data.week)` returns a tier and `TIER_TOKENS` has `metal` and `metalHi`, `.top` gets `is-tier` and those two custom properties. The existing `#fcc-header-emblem` is the emblem. If the tier is not available, the bar stays plain.

Rail order: Office, Team, Prep, League, Recruiting, News, then the utility group: Tutorials (`/tutorial.html`), Feedback, Settings, a quieter divider, Exit Franchise. Exit calls the existing `#exit-franchise` handler (same sound, same `/mode-select.html` destination). Feedback is the existing `#feedback-btn` modal and is omitted when `window.GOB_BUILD_PROFILE === 'desktop'`. Settings calls `GOBSettings.toggle()`.

`.gob-1280`: the grid column stays `--rail-w`. Labels are hidden. `title` tooltips remain. Hover or keyboard focus expands an overlay face to the labeled rail width after 400ms. The overlay must not change `.main`'s rectangle. `.gob-1920`: the rail is `--rail-w` with labels visible.

Recruiting carries the existing `.inbox-badge` when `recruitingIsPrompted` is true. That is a presence dot, not a count. Do not pulse it unless a field already says the recruiting task gates Advance. Turning Advance into the recruiting task is the gating; it is not a pulse signal.

Sub-tabs sit in `.pg-head` (sticky title plus `.subtabs`). Office and Recruiting have no sub-tab row. Link sub-tabs look the same as in-page sub-tabs and call `GOBNav.go` with the href the page already built. The Stats sub-tab has a Players | Team toggle (`player-stats-tab` and `fcc-team-stats-summary-tab`) that uses replace.

On a shell page, the settings host is positioned at `left: var(--rail-w)` and `top: var(--top-h)` so the scrim covers `.main` only. The top bar and the rail stay usable. Pages that still use the auth bar keep the host anchored under `#auth-bar`.

Scroll rule: only `.main` scrolls. Do not add a second page-level scroller. Leave scroll inside an existing table or card; list it, do not refactor it, when the task says so.

Rail and sub-tab clicks play `click-tiny.wav` through `playSfx`. Advance does not switch to that sound.

## 6. Navigation and history

`gobNav.js` (`window.GOBNav`).

- `go(url)` leaves the page. From the franchise command center it records the flow start (unless the destination is a peek), stamps the next index for the following load, and assigns.
- `pushSection(url)` is the same-page section push. It saves `.main` scroll, increments `gobIdx` on the new history entry immediately, and does not write the pending-index key (the document is not reloading).
- `replace(url)` keeps the current index and replaces the page. Sub-tabs do not call it. They use `history.replaceState` through `CommandCenterTabs.show(tab, 'replace')` so the franchise page stays one entry.
- Rail section clicks call `CommandCenterTabs.show(tab, 'push')`. Sub-tabs and the Stats toggle call `show(tab, 'replace')`.
- Browser Back and Forward restore the section, the sub-tab, and the scroll position from `popstate` (`showTabFromUrl` plus `GOBNav.restoreScroll`). Scroll is stored per URL on `.main` when `html.gob-shell` is present, otherwise on the active tab panel.
- In-app flows (Play Game, Run Training, and the other Advance routes) still return to the locker-room entry via `exitFlow`. That collapse is separate from the section stack.
- `exitFlow` jumps back to the locker-room index that launched the flow. In-app Back uses `history.back()` only when the previous entry is that parent.

Old `?tab=` values still open the matching section and sub-tab. Each tab's `onTabShow` lazy-load still runs.

The shared tab module also serves any other command center that calls `initCommandCenterTabs`. Button clicks there stay on `replace`. Do not make those clicks push.

## 7. Section map

| Rail | Sub-tab | Opens |
|---|---|---|
| Office | (none) | `home-tab` |
| Team | Roster | `roster-tab` |
| Team | Stats | `player-stats-tab`, with Players \| Team toggle to `fcc-team-stats-summary-tab` |
| Team | Development | `team-stats-tab` (Team Measures) |
| Team | Practice Squad | existing `#fcc-ps-season-link` (`practice-squad-standings.html`, `franchise_id` and `team_id`) |
| Prep | Training | `training-tab` |
| Prep | Game Plan | `game-plan-tab` |
| Prep | Playbooks | `playbooks-tab` |
| Prep | Scouting | `coaches-tab` |
| League | Standings | `standings-tab` |
| League | Schedule & Results | `schedule-tab` |
| League | Rankings | existing rankings href (`/rankings.html` plus the resource query) |
| League | Leaders | `awards-tab` |
| League | Brackets | existing `brackets.html` href, or the same resource query already on the rankings link |
| Recruiting | (none) | `recruits-tab` |
| News | News | `press-tab` |
| News | Awards | `awards.html` with the resource query already on the rankings link. There is no dedicated awards anchor on the page |

History is not a section.

To add a section: add one rail item, one entry in the shell section list, and the `?tab=` ids that belong to it. Default the rail click to the first in-page sub-tab and push. To add a sub-tab: add it under that section. In-page sub-tabs replace. Links use an href the page already builds and `GOBNav.go`. Then update this table.

## 8. Checklist for a new page or brief

A page or brief is done only when this file is updated if the shell, the section map, history, settings, audio routing, or density rules changed.

1. Renderer only. No new API. No new field. Missing field: omit the element and name it in the task report.
2. One Advance. Blocking work changes its label. No spinner. No second green button.
3. Tokens from `gob-tokens.css` only. `.gob` plus `bindGobDensity`. Self-hosted fonts.
4. Two levels of navigation. Rail pushes. Sub-tabs replace. Flows still `exitFlow` back to the locker room.
5. Only `.main` scrolls on a shell page.
6. Live gameplay does not mount the shell.
7. Sounds go through `playSfx` or the court bus. Advance keeps its confirm sound.
8. Settings opens from the shell gear on a shell page and from the auth-bar gear everywhere else.
9. Attribute digits and RT letters are unchanged.
10. This document matches what shipped.
