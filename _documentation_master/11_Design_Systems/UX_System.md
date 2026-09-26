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

`gobShell.js` mounts the shell. The Office and every browse page in the table below get the full shell. Flow pages get focus mode. The live court never mounts it.

Grid: `.app` is `grid-template-rows: var(--top-h) minmax(0, 1fr)` and `grid-template-columns: var(--rail-w) minmax(0, 1fr)`. `.top` spans both columns. `.rail` is column 1. `.main` is column 2 and the only scroller (`overflow-y: auto`). `html` and `body` do not scroll.

Top bar, left to right: team logo (existing `#team-logo`, height `calc(var(--top-h) * 0.72)`, width auto, no crop) whose alt, `title`, and link `aria-label` are the team name. The name is not painted as visible text. The control opens Team › Roster. Then a divider, Record, National Rank, Week. Record text comes from `#fcc-record-label` (standings W-L for the user's team). National Rank comes from `#fcc-rank-label` / `data.rank`, shown as `#N` or `NR`, with the label "National Rank". Week comes from `data.week`. There is no Team RT. There is no alpha badge, product logo, or social link. The build label stays in Settings.

Right side, browse pages: the ghost Edit Recruit Invites button (`#fcc-edit-recruiting`, same show/hide as today) then Advance (`#play-now` with class `advance`). Advance is `gobAdvance.js`. The Office passes its existing helpers into it. Labels, `dataset.mode`, routes, and gating are the same as the Office. A blocking task replaces the label; it does not disable the button or add a hint. Loading text is `STARTING…`. A second click while that class `is-loading` is set is ignored. Focus mode has no Advance. The page keeps its own green button.

On a browse page that does not already paint `#fcc-record-label`, Record comes from `team_record.wins` and `team_record.losses` on the command-center payload. National Rank still comes from `data.rank`. Week still comes from `data.week`. The Office keeps painting Record from the standings label.

Tier weeks: when `GOBTierEmblem.tierForWeek(data.week)` returns a tier and `TIER_TOKENS` has `metal` and `metalHi`, `.top` gets `is-tier` and those two custom properties. The existing `#fcc-header-emblem` is the emblem. If the tier is not available, the bar stays plain.

Rail order: Office, Team, Prep, League, Recruiting, News, then the utility group: Tutorials (`/tutorial.html`), Feedback, Settings, a quieter divider, Exit Franchise. Exit calls the existing `#exit-franchise` handler (same sound, same `/mode-select.html` destination). Feedback is the existing `#feedback-btn` modal and is omitted when `window.GOB_BUILD_PROFILE === 'desktop'`. Settings calls `GOBSettings.toggle()`.

`.gob-1280`: the grid column stays `--rail-w`. Labels are hidden. `title` tooltips remain. Hover or keyboard focus (`:focus-visible`) waits 400ms, then the overlay face widens from `--rail-w` to 200px in one `--dur-rail` (180ms) `--ease-out` transition. Labels fade in on that same timing. They do not change the face width. Collapse is one motion as well: 120ms after the pointer leaves (or focus clears), the face narrows with `--dur-rail`. The overlay must not change `.main`'s rectangle. `prefers-reduced-motion` makes the change instant. `.gob-1920`: the rail is `--rail-w` with labels visible.

Recruiting carries the existing `.inbox-badge` when `recruitingIsPrompted` is true. That is a presence dot, not a count. Do not pulse it unless a field already says the recruiting task gates Advance. Turning Advance into the recruiting task is the gating; it is not a pulse signal.

Sub-tabs sit in `.pg-head` (sticky title plus `.subtabs`). Office and Recruiting have no sub-tab row. Recruiting is a rail item that leaves the page: it calls the existing `openRecruitingSurface` (`GOBNav.go` to the recruiting URL the app already builds). On the Office, link sub-tabs call `GOBNav.go` with the href the page already built. On a standalone browse page, every sub-tab uses `GOBNav.replace`: an Office tab goes to `franchise-command-center.html?tab=<id>`, and a link sub-tab goes to that standalone page. Rail section clicks on a standalone page `GOBNav.go` to that section's first Office tab (or to recruiting). There is no Players | Team toggle.

Focus mode (`html.gob-focus`): the top bar only — logo, Record, National Rank, Week, and the Settings gear at the right (`#gob-focus-settings`). No rail. No Advance. The settings host anchors at `left: 0` and `top: var(--top-h)`. The page's own primary action and its exit or back control stay, including `exitFlow` back to the locker room.

Player and team pages highlight the section in `return_tab` or `return_url`. If those are absent, the user's own team is Team and a different `team_id` from `user_team_id` is League. No sub-tab is active. A back control that goes up a level (player to team, bracket to standings) stays. A back control that only returned to the locker room is hidden, because the rail replaces it.

Box score is browse when `return_url` is set, and focus when `from` is `lineup` or `game-plan` or neither param is set (the end-of-game open). Recruiting is focus for `action=run`, for weeks 20–26 before this week's invite board is submitted, and for week 35 before orders are submitted. Other hub views are browse.

On a full shell page, the settings host is positioned at `left: var(--rail-w)` and `top: var(--top-h)` so the scrim covers `.main` only. The top bar and the rail stay usable. Focus mode anchors that host at `left: 0`. Pages that still use the auth bar keep the host anchored under `#auth-bar`.

Scroll rule: only `.main` scrolls, on the Office, on browse pages, and in focus mode. Nested vertical scroll areas are removed (`overflow: visible`, no max-height). A table that is wider than `.main` at 1280 may scroll horizontally. `tests/e2e/helpers/oneVerticalScroll.js` (`assertOneVerticalScroll`) fails when any other element has `overflow-y` `auto` or `scroll` and `scrollHeight > clientHeight + 1`. Dialogs and the settings host are not page scrollers. A horizontal scroller whose extra height is only the scrollbar (24px or less, and wider than its box) is reported, not failed. Sticky `thead th` sits under `.pg-head` (`top: var(--dsz-118)`); in focus mode and inside a horizontal table wrap, `top` is 0.

Rail and sub-tab clicks play `click-tiny.wav` through `playSfx`. Advance does not switch to that sound.

## 6. Navigation and history

`gobNav.js` (`window.GOBNav`).

- `go(url)` leaves the page. From the franchise command center it records the flow start (unless the destination is a peek), stamps the next index for the following load, and assigns.
- `pushSection(url)` is the same-page section push. It saves `.main` scroll, increments `gobIdx` on the new history entry immediately, and does not write the pending-index key (the document is not reloading).
- `replace(url)` keeps the current index and replaces the page. In-page sub-tabs on the Office do not call it. They use `history.replaceState` through `CommandCenterTabs.show(tab, 'replace')` so the franchise page stays one entry. Sub-tabs on a standalone browse page do call `GOBNav.replace`, including the return to an Office tab.
- Rail section clicks call `CommandCenterTabs.show(tab, 'push')`, except Recruiting, which leaves the page with `GOBNav.go`. Sub-tabs call `show(tab, 'replace')`.
- Browser Back and Forward restore the section, the sub-tab, and the scroll position from `popstate` (`showTabFromUrl` plus `GOBNav.restoreScroll`). Scroll is stored per URL on `.main` when `html.gob-shell` is present, otherwise on the active tab panel.
- In-app flows (Play Game, Run Training, and the other Advance routes) still return to the locker-room entry via `exitFlow`. That collapse is separate from the section stack.
- `exitFlow` jumps back to the locker-room index that launched the flow. In-app Back uses `history.back()` only when the previous entry is that parent.

Old `?tab=` values still open the matching section and sub-tab. `schedule-tab` is Team › Schedule. `fcc-team-stats-summary-tab` is League › Team Stats. `recruits-tab` opens Office (`home-tab`). Each tab's `onTabShow` lazy-load still runs.

The shared tab module also serves any other command center that calls `initCommandCenterTabs`. Button clicks there stay on `replace`. Do not make those clicks push.

## 7. Section map

| Rail | Sub-tab | Opens |
|---|---|---|
| Office | (none) | `home-tab` |
| Team | Roster | `roster-tab` |
| Team | Player Stats | `player-stats-tab` |
| Team | Team Attributes | `team-stats-tab` (Team Measures) |
| Team | Schedule | `schedule-tab` (the user team's schedule) |
| Prep | Training | `training-tab` |
| Prep | Game Plan | `game-plan-tab` |
| Prep | Playbooks | `playbooks-tab` |
| Prep | Scouting Report | `coaches-tab` |
| League | Standings | `standings-tab` |
| League | Schedule | existing `#schedule-full-link` (`schedule.html` with `franchise_id`, `team_id`, `return_url`) |
| League | Rankings | existing rankings href (`/rankings.html` plus the resource query) |
| League | Leaders | `awards-tab` |
| League | Team Stats | `fcc-team-stats-summary-tab` |
| League | Practice Squad | existing `#fcc-ps-season-link` (`practice-squad-standings.html`, `franchise_id` and `team_id`) |
| League | Tournament | existing `brackets.html` href, or the same resource query already on the rankings link. Before the first week `GOBTierEmblem.tierForWeek` returns a tier, the control is disabled: same shape, `--text-38`, `not-allowed`, not focusable, title `Opens Week N`. |
| Recruiting | (none) | `recruiting.html` via `openRecruitingSurface` / `GOBNav.go` (`franchise_id`, `team_id`, `from=fcc`, `return_url`). An old `?tab=recruits-tab` deep link opens `home-tab`. |
| News | News | `press-tab` |
| News | Awards | `awards.html` with the resource query already on the rankings link. There is no dedicated awards anchor on the page |

History is not a section.

A fresh Recruiting Hub arrival (not a back/forward restore of filters the user already changed) opens "Leans to me" when `viewCounts().leans` is greater than 0. Otherwise it opens region = `team_region` (the existing "your region" value) and view = all. Filter changes after that stick for the rest of the visit, including a back/forward restore.

To add a section: add one rail item, one entry in the shell section list, and the `?tab=` ids that belong to it. Default the rail click to the first in-page sub-tab and push. To add a sub-tab: add it under that section. In-page sub-tabs replace. Links use an href the page already builds and `GOBNav.go`. Then update this table.

## 8. Checklist for a new page or brief

A page or brief is done only when this file is updated if the shell, the section map, history, settings, audio routing, or density rules changed.

1. Renderer only. No new API. No new field. Missing field: omit the element and name it in the task report.
2. One Advance. Blocking work changes its label. No spinner. No second green button.
3. Tokens from `gob-tokens.css` only. `.gob` plus `bindGobDensity`. Self-hosted fonts.
4. Two levels of navigation. Rail pushes. Sub-tabs replace. Flows still `exitFlow` back to the locker room.
5. Only `.main` scrolls. Run `assertOneVerticalScroll` on a new franchise page at 1280 and 1920.
6. Live gameplay does not mount the shell. Flow pages use focus mode. Browse pages use the full shell.
7. Sounds go through `playSfx` or the court bus. Advance keeps its confirm sound.
8. Settings opens from the rail gear on a full shell page, from the top-bar gear in focus mode, and from the auth-bar gear everywhere else.
9. Attribute digits and RT letters are unchanged.
10. This document matches what shipped.

## 9. Browse and focus pages

| Page | Mode | Section | Sub-tab |
|---|---|---|---|
| franchise-command-center.html | browse | per tab | per tab |
| recruiting.html | browse, or focus while that week's invites, Signing Day orders, or `action=run` are the task | Recruiting | none |
| rankings.html | browse | League | Rankings |
| schedule.html | browse | League | Schedule |
| practice-squad-standings.html | browse | League | Practice Squad |
| practice-squad-bracket.html | browse | League | Practice Squad |
| brackets.html | browse | League | Tournament |
| awards.html | browse | News | Awards |
| news.html | browse | News | News |
| leaders.html | browse | League | none |
| standings.html | browse | League | Standings |
| team-stats.html | browse | League | Team Stats |
| stats.html | browse | League | none |
| player-detail.html | browse | return context; else Team or League | none |
| team-roster-view.html | browse | return context; else Team or League | none |
| box-score.html | browse when `return_url` is set; otherwise focus | League when browse | none |
| set-lineup.html, training.html, training-report.html, training-squad-report.html, training-playbooks.html, cut-players.html, game-plan.html, playbooks.html, playbook-report.html | focus | — | — |

The top bar and Advance read `/franchise/command-center/data`. `gobAdvance.js` reuses a response the page already requested. Otherwise it fetches that URL once.

## 10. Office data

`GET /franchise/command-center/data` includes `office_digest`. The Office renders that block. It does not recompute ranks, streaks, to-dos, or attitude. The request does not send `profile=1` unless the page URL has `cc_profile=1`.

`office_digest` fields:

| Field | Source |
|---|---|
| `state` | `regular`, `first_week` (week ≤ 1), `tournament` (EOS active, weeks 27–34), `signing_day` (week 35), `win`, `loss` |
| `what_moved.national_rank` | `{now, prev, delta}`. Delta is previous minus current (positive means the team climbed). `prev` comes from the week-advance snapshot. |
| `what_moved.conference_standing` | Same shape. Place is wins, then national rank. |
| `what_moved.record` | `{wins, losses}` from standings already on the response. |
| `what_moved.streak` | `W4` or `L1`, from results. Null when the user has no decided game. |
| `what_moved.attribute_changes` | `{player_id, name, attribute, from, to}`. `from` and `to` are the first-digit display scale (`value // 10`). Keyed by player id. Legacy name-keyed direction maps are omitted. |
| `team_snapshot.state` | `set_after_camp` until a snapshot exists for a week before the current week. Otherwise `ready`. |
| `team_snapshot.chemistry` | `{value, max: 25}` from stored team chemistry. |
| `team_snapshot.attitude` | Counts in the EM buckets 0–19, 20–39, 40–59, 60–79, 80+. |
| `team_snapshot.moved_most` | Up to two `{measure, value, delta}` rows. Delta is this week's stored measure minus the previous snapshot. Empty until a prior snapshot exists. |
| `result` | Last completed user game, or null. Scores, site (`home` / `away`), `neutral` (always null; no stored neutral site), opponent rank, round name for weeks 27–34, POTG on a win or the user's highest-PTS player on a loss, box-score path and params. `headline` only when a `season_news` story stores this game's id. |
| `next_game` | Opponent, rank, record, conference, site, week, top scorer, top rebounder. `date`, `neutral`, `projected_starting_five`, `seeds`, `stakes`, and `team_rt` are null. |
| `todos` | `{id, label_key, required, done, gates_advance, is_advance_action, route}` from the same flags as `gobAdvance.js`. A blocking task is the Advance action. |
| `recruiting_wire` | Status line, events (`recruit`, `position`, `stars` and `filmed_grade` always null, `event_type`, `event_text` from the stored lean-event sentence, `list_position`, `direction`), `pending_count`, `urgent`, `unseen_count`. |
| `signing_day` | Week 35 only. Points remaining out of 50, playing-time promises, open roster spots, up to three targets. Otherwise null. |
| `season_preview` | `first_week` only. Preseason rank is the current national rank. Conference projection, team RT, returning starters, and top returner are null. Newcomers only when `pending_walk_on_welcome` is stored. Opener is `next_game`. |

The week-advance snapshot is the only new stored field: `franchises.office_week_snapshots.{season}.{completed_week}` with `national_rank_before`, `conference_position_before`, `team_measures`, and `team_measures_before` when a prior week exists. It is written in the same franchise `$set` as the week persist, before national rank is updated, and skipped when that week is already stored or rank/prestige for that week was already applied.
