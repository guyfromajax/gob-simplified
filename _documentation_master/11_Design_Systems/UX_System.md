# UX System

Version 1. How to build franchise screens. The look lives in [Styleguide.md](Styleguide.md). Every color, size, and duration lives in `FrontEnd/static/css/gob-tokens.css` under `.gob`. Name the token. Do not copy the value into a page, a component, or this document.

## 1. Principles

- The frontend is a pure renderer. UESS (`_documentation_master/05_UESS_System/UESS_System.md`) owns game logic. A screen formats fields the page already loaded. It does not invent a missing field, derive one, or move a rule to the client.
- One green Advance per screen. It is the only control that uses the advance color. A blocking task becomes the Advance button (same id, same `updatePlayButton` state machine, same labels and routes). There is no disabled-with-lock state and no hint link. Recruiting chrome follows the same law: green is only Advance and positive data (board gains); orange is only saves (Submit Invites, Submit Orders); navy is only "yours" (your lean, your region, your signing). Phase labels, week tiles, invite counts, and filter chips stay neutral.
- No spinners. A click that leaves the page switches Advance to the loading look immediately (`is-loading`, label `STARTING…`) and ignores repeat clicks.
- Blue belongs to RT. Do not use the rating blue for chrome, links, or navigation.
- Reward gold (`--reward-gold`) is only for milestone and season-peak reward tiers and exceptional stat gains. It is never for buttons, Advance (green), "yours" (navy), choice controls, everyday / weekly chrome, or Home Base chrome. It is the one reward token: tints are `color-mix()` at the point of use, so there are no gold tint or shadow tokens.
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

### Player headshots are square

A player headshot is a square with a small corner. Never a circle. A circle crops the head to its inscribed disc and throws away the shoulders, which is what made headshots read as too small. This holds everywhere a player's face appears — Roster, Leaders, Player Stats, Player detail, Scouting, Training Report, Recruiting — whether the element carries a photo, a monogram or a placeholder.

The corner scales with the box so every headshot reads the same weight: `--radius-6` on the 28–46px table and list badges (`.gob .av`, `.pool .pc-av`, `.pdg-av`, `.wr-hs`), `--radius-10` on the large portrait (`.gob .portrait`, `.pd-portrait-wrap`). A radius past a quarter of the side is closer to a circle than to a square, so treat that as the ceiling.

Team logos and team initials badges are not headshots. They keep `--radius-logo`. The on-court HUD and the sim's headshot marker are game presentation, not this rule.

## 3. Audio

`uiSfx.js` is the volume bus. Channels: `master`, `music`, `sfx`, `ambience`. Effective gain is master × channel, or 0 when either is muted. Levels are 0–100.

Persisted in `localStorage` under `gob_audio_v1` (`AUDIO_STORAGE_KEY`). The same record works online and in the offline desktop build.

`playSfx(name, baseVolume)` plays one named sound on the `sfx` channel. `baseVolume` defaults to `0.7`. It still accepts a raw filename so existing callers keep working. Named catalog: `SFX_SELECT` (`click-tiny.wav`), `SFX_ADVANCE` (`confirm-1-lowervol.wav`), `SFX_COMMIT` (`click-beep.wav`), `STING_WIN` (`sting-win.wav`), `STING_MILESTONE` (`sting-milestone.wav`), `STING_SEASON_PEAK` (`sting-season-peak.wav`). Short UI sounds may overlap. A new sting stops the previous sting. A missing file fails silently (one `console.debug` per name) and must not throw or block a modal or navigation.

One delegated click listener per document plays `data-sfx="<name>"` on buttons, links, and `[role="tab"]`. Unknown names are ignored. The top-bar Advance (`#play-now`) uses `data-sfx="SFX_ADVANCE"` and must not also call `playSfx` from its click handler.

Routed today: `playSfx` callers (rail, sub-tabs, the shared tab strip), `data-sfx` on Advance, the championship-moment season-peak sting, and the court sound control (`courtAudio.js`), which mirrors master / music / sfx into this bus.

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

Top bar, left to right: team logo (existing `#team-logo`, height `var(--top-h)`, width auto, `object-fit: contain`, no crop) with `--dsp-12` of horizontal padding on each side before the divider. Its alt, `title`, and link `aria-label` are the team name. The name is not painted as visible text. The control opens Team › Roster. Then a divider, Record, National Rank, Week. Record text comes from `#fcc-record-label` (standings W-L for the user's team). National Rank comes from `#fcc-rank-label` / `data.rank`, shown as `#N` or `NR`, with the label "National Rank". Week comes from `data.week`. There is no Team RT. There is no alpha badge, product logo, or social link. The build label stays in Settings.

Right side, browse pages: the ghost Edit Recruit Invites button (`#fcc-edit-recruiting`, same show/hide as today) then Advance (`#play-now` with class `advance`). Advance is `gobAdvance.js`. The Office passes its existing helpers into it. Labels, `dataset.mode`, routes, and gating are the same as the Office. A blocking task replaces the label; it does not disable the button or add a hint. Loading text is `STARTING…`. A second click while that class `is-loading` is set is ignored. Focus mode has no Advance. The page keeps its own green button.

On a browse page that does not already paint `#fcc-record-label`, Record comes from `team_record.wins` and `team_record.losses` on the command-center payload. National Rank still comes from `data.rank`. Week still comes from `data.week`. The Office keeps painting Record from the standings label.

Tier weeks: when `GOBTierEmblem.tierForWeek(data.week)` returns a tier and `TIER_TOKENS` has `metal` and `metalHi`, `.top` gets `is-tier` and those two custom properties. The existing `#fcc-header-emblem` is the emblem. If the tier is not available, the bar stays plain.

Rail order: Office, Team, Prep, League, Recruiting, News, then the utility group: Tutorials (`/tutorial.html`), Feedback, Settings, a quieter divider, Exit Franchise. Exit calls the existing `#exit-franchise` handler (same sound, same `/mode-select.html` destination). Feedback is the existing `#feedback-btn` modal and is omitted when `window.GOB_BUILD_PROFILE === 'desktop'`. On a browse page the rail Feedback appears once the auth bar has added `#feedback-btn`, which can be after the shell mounts. Settings calls `GOBSettings.toggle()`.

`.gob-1280`: the grid column stays `--rail-w`. Labels are hidden. `title` tooltips remain. Hover or keyboard focus (`:focus-visible`) waits 400ms, then the overlay face widens from `--rail-w` to 200px in one `--dur-rail` (180ms) `--ease-out` transition. Labels fade in on that same timing. They do not change the face width. Collapse is one motion as well: 120ms after the pointer leaves (or focus clears), the face narrows with `--dur-rail`. The overlay must not change `.main`'s rectangle. `prefers-reduced-motion` makes the change instant. `.gob-1920`: the rail is `--rail-w` with labels visible.

Recruiting carries the existing `.inbox-badge` when `recruitingIsPrompted` is true. That is a presence dot, not a count. Do not pulse it unless a field already says the recruiting task gates Advance. Turning Advance into the recruiting task is the gating; it is not a pulse signal.

Sub-tabs sit in `.pg-head` (sticky title plus `.subtabs`). Office has no sub-tab row. Recruiting is a rail item that leaves the page: it calls the existing `openRecruitingSurface` (`GOBNav.go` to the recruiting URL the app already builds). On that page the row is Pool, Leans, and Visits. On the Office, link sub-tabs call `GOBNav.go` with the href the page already built. On a standalone browse page, a link sub-tab uses `GOBNav.replace`: an Office tab goes to `franchise-command-center.html?tab=<id>`, and a link sub-tab goes to that standalone page. Recruiting's own Pool, Leans, and Visits stay on `recruiting.html` and do not use `GOBNav.replace`. Rail section clicks on a standalone page `GOBNav.go` to that section's first Office tab (or to recruiting). There is no Players | Team toggle.

Focus mode (`html.gob-focus`): the top bar only — logo, Record, National Rank, Week, and the Settings gear at the right (`#gob-focus-settings`). No rail. No Advance. The settings host anchors at `left: 0` and `top: var(--top-h)`. The page's own primary action and its exit or back control stay, including `exitFlow` back to the locker room.

Player and team pages highlight the section in `return_tab` or `return_url`. If those are absent, the user's own team is Team and a different `team_id` from `user_team_id` is League. No sub-tab is active. A back control that goes up a level (player to team, bracket to standings) stays. A back control that only returned to the locker room is hidden, because the rail replaces it.

Box score is browse when `return_url` is set, and focus when `from` is `lineup` or `game-plan` or neither param is set (the end-of-game open). Recruiting is focus for `action=run`, for weeks 20–26 before this week's invite board is submitted, and for week 35 before orders are submitted. Other hub views are browse.

On a full shell page, the settings host is positioned at `left: var(--rail-w)` and `top: var(--top-h)` so the scrim covers `.main` only. The top bar and the rail stay usable. Focus mode anchors that host at `left: 0`. Pages that still use the auth bar keep the host anchored under `#auth-bar`.

Scroll rule: only `.main` scrolls, on the Office, on browse pages, and in focus mode. Nested vertical scroll areas are removed (`overflow: visible`, no max-height). `tests/e2e/helpers/oneVerticalScroll.js` (`assertOneVerticalScroll`) fails when any other element has `overflow-y` `auto` or `scroll` and `scrollHeight > clientHeight + 1`. Dialogs and the settings host are not page scrollers. A horizontal scroller whose extra height is only the scrollbar (24px or less, and wider than its box) is reported, not failed.

Sticky versus wide tables: after each render and on resize, each table's content width is compared with `.main`'s content box. A table that fits gets a page-level sticky `thead` (`top: var(--gob-stick-top)`, the measured `.pg-head` height; `0` in focus). Ancestors between the header and `.main` stay `overflow: visible`, so the header pins on `.pg-head`'s bottom and scrolls away with its own table. A table wider than `.main` gets `.gob-wide-wrap`: `overflow-x: auto`, `overflow-y: clip`, the table stays inside its card, a right-edge fade shows while columns are hidden (and a left fade once scrolled), and that header is not sticky.

Page transitions: browse shell pages and the Office use `@view-transition { navigation: auto; }`. `.top` and `nav.rail` have stable `view-transition-name`s so they stay put. The rest of the page crossfades in 150ms with `--ease-out`. Focus pages set `navigation: none` so a flow step is a normal load. `prefers-reduced-motion: reduce` also sets `navigation: none`. Browsers without the API navigate normally.

The top bar Record reads `#fcc-record-label` on the Office, then `team_record.wins` / `team_record.losses` when that object is on the command-center payload, then the user's row in `rankings` (`W` and `L` for `user_team_object_id` / `user_team_id` / `team_id`). Those standings are already on `/franchise/command-center/data`.

Rail and sub-tab clicks play `click-tiny.wav` through `playSfx`. Advance does not switch to that sound.

## 6. Navigation and history

`gobNav.js` (`window.GOBNav`).

- `go(url)` leaves the page. From the franchise command center it records the flow start (unless the destination is a peek), stamps the next index for the following load, and assigns.
- `pushSection(url)` is the same-page section push. It saves `.main` scroll, increments `gobIdx` on the new history entry immediately, and does not write the pending-index key (the document is not reloading).
- `replace(url)` keeps the current index and replaces the page. In-page sub-tabs on the Office do not call it. They use `history.replaceState` through `CommandCenterTabs.show(tab, 'replace')` so the franchise page stays one entry. Link sub-tabs on a standalone browse page do call `GOBNav.replace`, including the return to an Office tab. Recruiting's Pool, Leans, and Visits also stay on one entry: `activateSubtab` writes `hub=pool|leans|visits` with `history.replaceState` and calls `RecruitingHub.show`. It does not call `GOBNav.replace` and it does not call `fccHref`. A reload and a `popstate` read `hub` back into `pageMode.sub`.
- Rail section clicks call `CommandCenterTabs.show(tab, 'push')`, except Recruiting, which leaves the page with `GOBNav.go`. Sub-tabs call `show(tab, 'replace')`.
- Browser Back and Forward restore the section, the sub-tab, and the scroll position from `popstate` (`showTabFromUrl` plus `GOBNav.restoreScroll`). Scroll is stored per URL on `.main` when `html.gob-shell` is present, otherwise on the active tab panel.
- In-app flows (Play Game, Run Training, and the other Advance routes) still return to the locker-room entry via `exitFlow`. That collapse is separate from the section stack.
- `exitFlow` jumps back to the locker-room index that launched the flow. In-app Back uses `history.back()` only when the previous entry is that parent.
- `warnOnLeave(hasEdits, { view, confirm })` registers an unsaved-edit check. `hasEdits` compares the current values with the last saved ones, so moving a control and moving it back is not an edit. A plain boolean "touched" flag is not enough. `CommandCenterTabs.show` asks `confirmLeave(proceed, view)` before it leaves `view`; with real edits the owner's `confirm` opens the in-app `GOBLeaveConfirm` (Keep Editing, Discard, Save) and `proceed` runs after Discard or a landed Save. `go`, `replace`, `back`, and same-origin link clicks ask every check the same way. The browser's own `beforeunload` prompt fires only for a reload or a window close with real edits. A view whose edits persist as a session draft (Training) registers no confirm, because nothing is lost. A Back or Forward `popstate` is not guarded.

Old `?tab=` values still open the matching section and sub-tab. `schedule-tab` opens Team › Schedule (`team-schedule-view`). `fcc-team-stats-summary-tab` is League › Team Stats. `recruits-tab` opens Office (`home-tab`). Each tab's `onTabShow` lazy-load still runs.

The shared tab module also serves any other command center that calls `initCommandCenterTabs`. Button clicks there stay on `replace`. Do not make those clicks push.

## 7. Section map

| Rail | Sub-tab | Opens |
|---|---|---|
| Office | (none) | `home-tab` |
| Team | Roster | `roster-view` (in-page module view; `team-roster-view.html` redirects here and keeps `franchise_id`, `team_id`, `roster_team_id`, and return params). `?tab=roster-tab` opens this view. |
| Team | Player Stats | `player-stats-view` (in-page module view). `?tab=player-stats-tab` opens this view. |
| Team | Team Attributes | `team-attributes-view` (in-page module view). `?tab=team-stats-tab` opens this view. The old Team Measures panel stays in the page and is no longer opened by the shell. |
| Team | Schedule | `team-schedule-view` (in-page module view). `?tab=schedule-tab` opens this view. Four week columns (1–7, 8–14, 15–21, 22–26), with the three tournament labels under 22–26 and the user's EOS games listed under each label when present. Two columns below 1100px. The bracket stays on League › Tournament. |
| Team | Practice Squad | `practice-squad-view` (in-page module view). The regional practice-squad league. `practice-squad-standings.html` and `practice-squad-bracket.html` redirect here. |
| Prep | Training | `training-view` (real module: `training.js` `init(root)`; `training.html` redirects here). The underline tab replaces. `?tab=training-tab` opens this view. `training.html` with `mode=tutorial` does not redirect and stays on the file. The Training Report is `training-report-view`, a real module (`training-report.js` `init(root)`; `training-report.html` redirects). The FCC summary panel stays in the page and is no longer opened by the shell. |
| Prep | Game Plan | `game-plan-view` (real module: `game-plan.js` `init(root)`; `game-plan.html` redirects here). `?tab=game-plan-tab` opens this view. `game-plan.html` with `resume_from_timeout=true` or `mode=tutorial` does not redirect and stays focus, with no rail and no underline row. |
| Prep | Playbooks | `playbooks-view` (real module: `playbooks.js` `init(root)`; `playbooks.html` redirects here). `?tab=playbooks-tab` opens this view. `playbooks.html` with `mode=tutorial` does not redirect and stays on the file (browse chrome). |
| Prep | Scouting Report | `scouting-view` (in-page module view). The underline tab replaces. |
| League | Standings | `standings-view` (in-page module view; `standings.html` redirects here and keeps `franchise_id`, `team_id`, and return params). `?tab=standings-tab` still opens the old panel. |
| League | Rankings | `rankings-view` (in-page module view; `rankings.html` redirects here and keeps `franchise_id`, `team_id`, and return params) |
| League | Leaders | `leaders-view` (in-page module view; `leaders.html` redirects here). `?tab=awards-tab` still opens the old panel. |
| League | Team Stats | `team-stats-view` (in-page module view; `team-stats.html` redirects here). `?tab=fcc-team-stats-summary-tab` still opens the old panel. |
| League | Schedule | `league-schedule-view` (in-page module view; `schedule.html` redirects here and keeps `franchise_id`, `team_id`, `week`, and return params). |
| League | Tournament | `tournament-view` (in-page module view). `brackets.html` redirects here. Before week 27 the control is disabled: same shape, `--text-38`, `not-allowed`, not focusable, title `Opens Week N`. |
| Recruiting | Pool, Leans, Visits | `recruiting.html?hub=pool\|leans\|visits` via `openRecruitingSurface` / `GOBNav.go` from the rail (`franchise_id`, `team_id`, `from=fcc`, `return_url`). The sub-tab replaces `hub` on that same document. The name search sits in `.pg-tools` as `.gob-search` ("Search name…", `/` to focus). Weeks 20–26 hide Pool, Leans, and Visits: the invite stack (calendar, board, then the pool) is the page, with a neutral "Recruit pool below" callout that scrolls to `#hub-pool`. Weeks 1–19 and 27–34 keep the three tabs. Weeks 35 and 36 hide the row; the sign board or the results list is the page. Focus mode hides the head, including the row. An old `?tab=recruits-tab` deep link opens `home-tab`. |
| News | News | `news-view` (in-page module view; `news.html` redirects here and keeps `franchise_id`, `team_id`, `story`, and return params). `?tab=press-tab` opens this view. |
| News | Awards | `awards-view` (in-page module view; `awards.html` redirects here and keeps `franchise_id`, `team_id`, and return params) |

History is not a section.

The page h1 is the only title. There is no second "Recruiting Hub" heading and no outer card around the hub. The phase strip is the first content, 8px under the row hairline. Pool, Leans, and Visits do not show a Recruit Pool jump. Signing Day keeps the Recruit Pool / My Orders switch, because My Orders replaces the pool.

A fresh Recruiting Hub arrival with no `hub` query (not a back/forward restore of filters the user already changed) selects the Leans tab when `viewCounts().leans` is greater than 0 and the week is outside 20–26. Otherwise it selects Pool and sets region = `team_region` (the existing "your region" value). A reload or `popstate` with `hub` already set restores that tab when the tabs are showing. Region, position, year, Watchlist, Unranked by me, and the name search stick for the rest of the visit, including a back/forward restore. Weeks 20–26 always show the visit calendar and the invite board above the pool; the in-pool Leans / Watchlist / Unranked filters stay. There is no weekly results panel. Weeks 1–19 Visits shows the calendar as a preview ("Invite window opens Week 20") with the seven weeks upcoming. Weeks 27–34 Visits shows `visit_history` for weeks 20–26. Pool, Leans, Visits, and the board list recruits with a square headshot from `getRecruitImageUrl(image_id)`, falling back to the generic silhouette or initials.

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
11. The Playwright suite is green before merge. See "Running the suite" below.

### Running the suite

From the repo root, run both gates before merge. Leave `CI` unset so Playwright retries stay at 0. Pick a port that is not already listening (another worktree may be on 8000). `desktop-*.spec.js` is ignored by the default config; run that file on its own only when a change touches the desktop play flow.

**Python (required):** zero failures.

```
.venv/bin/python -m pytest --ignore=tests/e2e -q
```

**Playwright (required):** one worker on the chosen port.

```
env -u CI PORT=8010 BASE_URL=http://localhost:8010 PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright" PYTHON_PATH=".venv/bin/python" ./node_modules/.bin/playwright test tests/e2e --workers=1 --reporter=line
```

**UI tokens (required):** colour-law `--strict` on new-design files. Legacy pages are reported and do not fail the gate. Allowed: green on Advance and positive data (delta-up, tier-green, W badges, chemistry / board-gain bars, RT/attribute ramps); orange on committed/saved. Annotate an exception with `/* colour-law: positive-data */` or `/* colour-law: committed */`.

```
.venv/bin/python scripts/check_ui_tokens.py --strict
```

## 9. Browse and focus pages

| Page | Mode | Section | Sub-tab |
|---|---|---|---|
| franchise-command-center.html | browse | per tab | per tab |
| recruiting.html | browse, or focus while that week's invites, Signing Day orders, or `action=run` are the task | Recruiting | Pool, Leans, or Visits (`hub`). The row is hidden on Signing Day and Results, and while focus hides the head. |
| rankings.html | redirect to `franchise-command-center.html?tab=rankings-view` | League | Rankings |
| schedule.html | redirect to `franchise-command-center.html?tab=league-schedule-view` | League | Schedule |
| practice-squad-standings.html | browse | Team | Practice Squad (`practice-squad-view`; the file redirects) |
| practice-squad-bracket.html | browse | Team | Practice Squad (`practice-squad-view`; the file redirects) |
| brackets.html | browse | League | Tournament (`tournament-view`; the file redirects) |
| awards.html | redirect to `franchise-command-center.html?tab=awards-view` | News | Awards |
| news.html | redirect to `franchise-command-center.html?tab=news-view` (`story` is kept) | News | News |
| leaders.html | browse | League | Leaders (`leaders-view`; the file redirects) |
| standings.html | browse | League | Standings (`standings-view`; the file redirects) |
| team-stats.html | browse | League | Team Stats (`team-stats-view`; the file redirects) |
| stats.html | browse | League | none |
| player-detail.html | redirect to `?tab=player-view` unless `recruit_id` or `mode=recruit` | return context | none |
| team-roster-view.html | redirect to `roster-view`, or `team-view` when `roster_team_id` is set | Team or League | Roster or the team drill-in |
| box-score.html | browse when `return_url` is set; otherwise focus | League when browse | none |
| training.html | browse | Prep | Training (`training-view`; the file redirects except `mode=tutorial`; same `init(root)` as the in-app module) |
| training-report.html | browse | Prep | Training Report (`training-report-view`; the file redirects) |
| game-plan.html | browse, or focus when `resume_from_timeout=true` or `mode=tutorial` | Prep | Game Plan (`game-plan-view`; the file redirects except in focus; same `init(root)` as the in-app module) |
| playbooks.html | browse | Prep | Playbooks (`playbooks-view`; the file redirects except `mode=tutorial`; same `init(root)` as the in-app module) |
| set-lineup.html, training-squad-report.html, training-playbooks.html, cut-players.html, playbook-report.html | focus | — | — |

The top bar and Advance read `/franchise/command-center/data`. `gobAdvance.js` reuses a response the page already requested. Otherwise it fetches that URL once. Record on a browse page uses that same payload: `team_record` when present, otherwise the user team's `W`-`L` in `rankings`.

## 10. Office data

`GET /franchise/command-center/data` includes `office_digest`. The Office renders that block. It does not recompute ranks, streaks, to-dos, or attitude. The request does not send `profile=1` unless the page URL has `cc_profile=1`.

`office_digest` fields:

| Field | Source |
|---|---|
| `state` | `regular`, `first_week` (week ≤ 1), `tournament` (EOS active, weeks 27–34), `signing_day` (week 35), `win`, `loss` |
| `what_moved.national_rank` | `{now, prev, delta}`. Delta is previous minus current (positive means the team climbed). `prev` comes from the week-advance snapshot. |
| `what_moved.conference_standing` | Same shape. Place is the Standings order: wins, then point differential. |
| `what_moved.record` | `{wins, losses}` from standings already on the response. |
| `what_moved.streak` | `W4` or `L1`, from results. Null when the user has no decided game. |
| `what_moved.attribute_changes` | `{player_id, name, attribute, from, to}`. `from` and `to` are the first-digit display scale (`value // 10`). Keyed by player id. Legacy name-keyed direction maps are omitted. `exceptional: true` is added on a row whose **raw** gain clears the report week's threshold (10 at camp, 5 in season — `BackEnd/utils/attribute_gain.py`, ported from `training-report.js::getExceptionalGainThreshold`). The key is absent rather than false, and the client never recomputes it. The same pairs are on the training-report route as `exceptional_gains`. |
| `team_snapshot.state` | `set_after_camp` until a snapshot exists for a week before the current week. Otherwise `ready`. |
| `team_snapshot.chemistry` | `{value, max: 25}` from stored team chemistry. |
| `team_snapshot.attitude` | Counts in the EM buckets 0–19, 20–39, 40–59, 60–79, 80+. |
| `team_snapshot.moved_most` | Up to two `{measure, value, delta}` rows. Delta is this week's stored measure minus the previous snapshot. Empty until a prior snapshot exists. |
| `result` | Last completed user game, or null. Scores, site (`home` / `away`), `neutral` (always null; no stored neutral site), opponent rank, round name for weeks 27–34, POTG on a win or the user's highest-PTS player on a loss, box-score path and params. `headline` only when a `season_news` story stores this game's id. `result_key` is the game id: a stable id per result so the weekly entrance plays once. "Seen" is the client's own local state; the server stores none. |
| `next_game` | Opponent, rank, record, conference, site, week, top scorer, top rebounder. `conference_position` and `conference_size` are the opponent's 1-based place in its own conference and the number of teams there, using the Standings order. Both are null when the opponent cannot be placed. `date`, `neutral`, `projected_starting_five`, `seeds`, `stakes`, and `team_rt` are null. |
| `conference_standings` | The user's conference in Standings order. `conference` is the conference number, `region` is the stored region or the letter derived from that number (1–2 = A … 15–16 = H), and `rows` are `{team_id, team_name, wins, losses, differential, position, is_user}`. Ties follow `standings_display_sort_key` (wins, then point differential) and match `GET /franchise/standings` for the same results. Null when the user has no conference. |
| `todos` | `{id, label_key, required, done, gates_advance, is_advance_action, route}` from the same flags as `gobAdvance.js`. A blocking task is the Advance action. |
| `recruiting_wire` | Status line, events (`recruit`, `position`, `stars` and `filmed_grade` always null, `event_type`, `event_text` from the stored lean-event sentence, `event_detail`, `list_position`, `direction`), `pending_count`, `urgent`, `unseen_count`. |
| `signing_day` | Week 35 only. Points remaining out of 50, playing-time promises, open roster spots, up to three targets. Otherwise null. |
| `season_preview` | `first_week` only. Preseason rank is the current national rank. Conference projection, team RT, returning starters, and top returner are null. Newcomers only when `pending_walk_on_welcome` is stored. Opener is `next_game`. |
| `weekly_card_items` | WEEKLY-tier moments from the server moment queue, in order. Every item includes an `href` (the archetype row's is omitted on desktop, where the coaching-archetypes page is not served). The Office paints them with the existing card helper as links. They are not pop-ups. |
| `also` | The highest-priority weekly item as `{kind, title, line, href}`, or null. The weekly card's one folded-moment row. `weekly_card_items` stays the full list. |

`GET /franchise/command-center/data` also returns `moments`, `moments_for_this_visit`, and `weekly_card_items`. The browser does not rank, cap, or pick which moment opens, and it does not decide a moment's style or sound. MILESTONE-tier items play through one `.mm` template (`js/shared/milestoneModal.js`): gold items rise and play the server `sting`; elimination is quiet (fade only, no gold, no sound). `×` / Esc leaves the rest of the visit list for the next open. Seen PATCHes fire only for moments that were shown. `BackEnd/utils/moment_queue.py` builds the list from existing eligibility flags; `BackEnd/utils/season_moments.py` derives the three newer payloads at route level from the brackets, the season snapshot reader and the week-35 signings.

Each row carries `kind`, `tier`, `priority`, `payload_ref` (the response key holding the payload), `seen_key`, `title`, `line`, `style`, `sting`, and `duration` on pop-up tiers.

Priority (lower number first):

| Priority | Kind | Tier | Duration | Style | Sting | Payload source |
|---|---|---|---|---|---|---|
| 10 | championship | SEASON PEAK | long | gold | `STING_SEASON_PEAK` | `pending_championship_moments` |
| 15 | season_review | SEASON PEAK | long | gold | `STING_SEASON_PEAK` | `season_review` — `career_data.season_review_snapshot`, once the season's games are played |
| 20 | elimination | MILESTONE | short | quiet | — | `elimination` — the season-ending tournament loss, read off the brackets |
| 30 | bracket_reveal | MILESTONE | long | gold | `STING_MILESTONE` | `bracket_reveal_modal`, when the user's team is in the revealed bracket |
| 40 | signed_class | MILESTONE | long | gold | `STING_MILESTONE` | `signed_class` — eligible only after the week-35 hub reveal has been seen |
| 50 | walk_on_welcome | MILESTONE | long | gold | `STING_MILESTONE` | `walk_on_welcome_modal` |
| 60 | region_bye | MILESTONE | short | gold | `STING_MILESTONE` | `region_bye_modal_eligible` |
| 65 | conference_rs_region | MILESTONE | short | gold | `STING_MILESTONE` | `conference_rs_region_modal` |
| 70 | first_archetype | MILESTONE | short | gold | `STING_MILESTONE` | `first_archetype` — lead archetype set and its reveal not yet seen |
| 80 | bracket_update | WEEKLY | — | — | — | `bracket_update_modal` |
| 90 | recruit_visit | WEEKLY | — | — | — | `recruit_visit_modal` |
| 100 | archetype_evolution | WEEKLY | — | — | — | `archetype_evolution_pending` (an evolution, not a first establish) |
| 110 | bracket_reveal | WEEKLY | — | — | — | `bracket_reveal_modal`, when the user's team is **not** in it |

Cap: a season peak shows alone. When one is eligible the visit is the season-peak items only, and a championship plus its review are the one pair that shows together — exactly `[championship, season_review]`, as "1 of 2 / 2 of 2". Otherwise `moments_for_this_visit` is the first pop-up-tier item, plus a second only when the first is `duration=short` and the second is MILESTONE or SEASON PEAK. Remaining pop-up-tier items stay in `moments` (still eligible next visit; seen keys are not marked until shown). WEEKLY items go to `weekly_card_items` and never take a pop-up slot.

`recruiting_results_modal` is not queued as itself: the live Signing Day beat stays the week-35 hub reveal, and the Office's one-time summary is `signed_class`, which reuses that modal's `recruiting_results_modal_seen_season` stamp. Elimination and the review add the only new stored fields, `elimination_seen_season` and `season_review_seen_season`, written by `PATCH /franchise/elimination-seen` and `PATCH /franchise/season-review-seen` in the same season-stamped style as the existing modal flags.

Cut-players (blocking) and tutorial return alerts stay outside the queue. Tutorial alerts settle first. The queue plays next. The cut modal waits for both.

`recruit` is the recruit's display name. It comes from the lean-recruit set already loaded for the request. When the recruit is not in that set, the name on the event record is used (`recruit`, `recruit_name`, or `name`). Otherwise one projected read of `franchise_recruits_data` loads every missing `recruit_id` at once (`name`, `position`, `position_ratings`, `Lean`). The name is null only when none of those have it. The copy placeholder "A recruit" is not a name. `position` is the best `position_ratings` entry, or a stored position string, or the position on the event. It is null only when none of those exist.

`event_detail` is the update sentence without the recruit's name. It is built from the event `kind` and the structured fields (rank, rival, cause) when those fields are enough to finish the sentence, using the same wording as the stored line. When a team name that sentence needs is missing, it falls back to stripping the resolved display name from the start of the stored line, and only when that whole name matches. The first letter is capitalised. `event_text` stays the stored line for other consumers. `event_detail` is null when neither path can produce a sentence.

The week-advance snapshot is the only new stored field: `franchises.office_week_snapshots.{season}.{completed_week}` with `national_rank_before`, `conference_position_before`, `team_measures`, and `team_measures_before` when a prior week exists. It is written in the same franchise `$set` as the week persist, before national rank is updated, and skipped when that week is already stored or rank/prestige for that week was already applied.

## 11. Browse cache contract

`franchises.browse_rev` is an integer. A document without the field is revision 0. Every franchise-scoped write that can change a browse GET increments it once. `fold_browse_rev` adds that `$inc` to an update the route is already sending to the franchise document. `bump_browse_rev` is one extra update when the write does not touch the franchise document (game plan, playbooks, development focus, week-35 recruiting orders).

Browse GETs use one dependency, `@browse_cached`. Before the handler it reads `_id`, `current_season`, `week`, and `browse_rev` and builds:

`W/"<franchise_id>:<season>:<week>:<browse_rev>:<BUILD>:<route-signature>"`

`BUILD` is the deployed commit, so a deploy invalidates every tag. The route signature is the path plus the sorted query string. A matching `If-None-Match` returns 304 with an empty body and the handler does not run. Any other result runs the handler and sets `ETag` plus `Cache-Control: private, no-cache`. `profile=1` always runs the handler.

A GET that still writes (command-center region reconcile, playbooks first-open, practice-squad stat backfill) stamps the post-write tag on that response. The 304 path does not do a second read.

Not on this rev: `GET /api/game/{id}`, `POST /api/simulate-quarter`, press-conference sessions, and lineup or game-plan saves that target an in-progress game (`game_id`). The sim, `cpu_week_pool`, and end-of-game persistence do not increment it. Phase A does, because command-center returns `season_inbox` before phase B.

A new franchise write must fold or bump. A new browse GET must use the dependency.

## Client store

`js/shared/gobStore.js` is the only client cache for franchise browse reads. `authGuard.js` loads it on every page. The store caches server responses. It does not compute standings, ratings, season lines, or anything else the page renders.

`GOBStore.get(url, init)` fetches a browse GET:

- Two callers of the same URL in one document share one request.
- A resolved entry in that document is reused. A new document does not keep the JavaScript heap, so it sends `If-None-Match` with the stored ETag.
- `304` returns the stored body. `200` replaces the body and the ETag.
- The body is also written to `sessionStorage` under `gob-store:<franchise_id>`, inside try/catch. Bodies larger than about 1.5 MB are kept in memory only. If `sessionStorage` throws, the request still completes.

The ETag is `franchise:season:week:browse_rev:BUILD:signature`. The store remembers the newest season, week, revision, and build it has seen for that franchise. A greater season, a greater week in that season, a greater revision in that week, or a different `BUILD` drops every cached body for that franchise. A newer revision means any cached route may be stale, because every franchise write bumps the revision.

`GOBStore.mutate(url, options)` is the write wrapper. `window.fetch` sends POST, PUT, PATCH, and DELETE on `/franchise/`, `/api/gameplan`, and `/api/playbooks` through it. After a successful response it clears that franchise's memory and `sessionStorage`. The next GET is a full read and picks up the new revision. A flow page that navigates away after a write does not have to do anything else.

Cached routes are the browse GETs: command-center, standings, schedule (including national), leaders, team-stats, team-player-stats, player-stats, team-data, news, recruiting-data, recruiting-results, practice-squad, awards, scouting-report, roster, player, player-detail, team-detail, recruit, teams, game plan, and playbooks.

Never cached: `GET /api/game/{id}`, `POST /api/simulate-quarter`, `/api/auth`, and any URL with `profile=1`. `profile=1` is only added when the page URL has `cc_profile=1`.

`ResourceCache` (the old season+week `sessionStorage` copy) always misses. Do not add a second cache in a page.

A new browse view calls `GOBStore.get` or plain `fetch` (the store wraps `fetch` for the routes above). A new franchise write uses `fetch` or `GOBStore.mutate` so the franchise cache is cleared. Do not read `sessionStorage` for a browse body yourself.

The Office does not call `GET /franchise/state`. Season counting stats for the user's roster are `players[].stats.season` on `GET /roster/{teamId}` in franchise mode, copied on read from `franchise_players_data.season`.

## 12. Office

The home tab of `franchise-command-center.html` is the Office (`.office` inside `.main`). It has no page title and no sub-tab row. `js/shared/officeHome.js` paints it from `office_digest` only. Grouping and sorting attribute changes for display is allowed. A null field is omitted. The page does not substitute another payload, and it does not write "N/A". WEEKLY moments from `office_digest.weekly_card_items` use the existing card chrome in the This Week column. Pop-ups come from `moments_for_this_visit` through `js/shared/momentQueue.js`. MILESTONE-tier kinds open the shared `.mm` template (`js/shared/milestoneModal.js`). Championship stays on `ChampionshipMoments`. `season_review` waits for the season-peak template. WEEKLY kinds stay on the weekly card. The 300-retry Big News wait loop is not part of the Office flow.

The Office fills `.main` edge to edge inside the standard page padding (`--page-pad`). There is no 1664px cap. At a viewport of 2400px or wider the Office caps at 2200px and stays centred. The collapsed rail still overlays the page on hover. The Office does not reserve space for that overlay.

While the digest is absent the page shows a skeleton strip and three skeleton cards. There is no spinner.

A week strip sits under the top of `.main`, above the columns. It is one row, about 56px tall at the 1280 density and 64px at 1920. It does not repeat the week number. The top bar already shows it. Each `todos[]` entry is one step, in order, joined left to right. Labels use the same copy as before. An `is_advance_action` step that is not done copies the top-bar Advance label and does not add an ADVANCE tag. The only Advance button on the page is the green top-bar control. A gating step that is not the Advance action shows BLOCKS ADVANCE. Every step uses the same padding. The status circle sits at least `--dsp-8` in from the left edge of the pill at both densities. Steps size to their labels. If the row is wider than the page, the gap between steps comes down before the labels do. Labels are not truncated. The strip does not scroll and does not wrap to a second row.

| Step | Rule |
|---|---|
| Done | Check mark, opacity 38%, still clickable. Opens `route`. |
| Next | The first not-done required step. Neutral bright outline (`--text-100`). Green stays on the top-bar Advance only. If this step is `is_advance_action`, its label copies the top bar and the click runs the same action. |
| Blocking | `gates_advance` on a step that is not `is_advance_action` draws an orange outline and BLOCKS ADVANCE. |
| Upcoming | The remaining steps. |

| State | Column 1 · Since last week | Column 2 · This Week | Column 3 · Recruiting |
|---|---|---|---|
| `win`, `loss`, `regular`, `tournament` | Result · What moved | Next game · Team snapshot · Conference standings | Recruiting wire. The column heading is the link to the recruiting hub. No events: "No recruiting movement this week". |
| `first_week` | Season preview | Next game · Team snapshot · Conference standings | One-line wire. The digest status when it is set, otherwise the empty-state line. The column heading is the hub link. |
| `signing_day` | Result · What moved | Team snapshot · Conference standings (`next_game` is null) | Signing Day card. The wire is hidden. The column heading still links to the hub. |

The three columns are equal width. The column gap is `--dsp-12` (12px at the 1280 density, 14px at 1920) between the heading and the first card and between stacked cards, so Result and What moved, Next game and Team snapshot and Conference standings, and the recruiting column all share one rhythm. The wire card is as tall as its rows. "Recruiting →" opens the recruiting hub. Result team names wrap, and at the 1280 density the score is smaller so a long name is not cut off.

| Component | Digest fields |
|---|---|
| Week strip | `todos[]` `label_key`, `done`, `required`, `gates_advance`, `is_advance_action`, `route`. No week label and no ADVANCE tag. |
| Result | `result` scores, names, `opponent_rank`, `site`, `round_name`, `user_won`, `headline`, `leader`, `leader_role`, `box_score`. The user name is prefixed with `#` plus `what_moved.national_rank.now` when that rank is set. No team monograms. |
| What moved | `what_moved.national_rank`, `conference_standing`, `record`, `streak`, `attribute_changes` |
| Recruiting wire | Deduped `recruiting_wire.events`. One row per `recruit_id`, or per name when the id is missing, keeping the latest event. Every row is two lines with the same padding: the name in semibold and the position dimmed on the first line, `event_detail` on the second (or `event_text` when `event_detail` is null). There is no list-position column. A direction arrow stays on the right when `direction` is up or down. At most 8 rows at the 1280 density and 12 at 1920, and only whole rows that sit above the fold. The column heading opens the hub. Rail badge uses `pending_count` and `urgent`. |
| Next game | `next_game` opponent, `rank` as `21. Name` in upright Bebas, `record`, `Conference` plus the short label and `(place of size)` from `conference_position` and `conference_size`. The place is omitted when either is null. No week callout and no monogram. |
| Team snapshot | `team_snapshot.chemistry` (red 0–8, yellow 9–16, green 17–25), five equal attitude columns, `moved_most`, `state` |
| Conference standings | `conference_standings.rows` under Team snapshot. Header is `Conference` plus the short label plus `standings` (`Conference A2 standings`). Show every row when the card fits above the fold. When the full table would scroll `.main` or overflow its column, show as many rows as fit, centred on the user — at least five when five fit, otherwise the shorter window that keeps the page still — plus "Full standings" in the card header to League › Standings. A row matches a players-to-watch row: the team name is `--fs-13` semibold, W-L is the display face at `--fs-22`, and the place is `--text-38` tabular. At the 1920 density the standings rows drop their vertical padding so the type sizes stay. The W-L header sits in the same column as the numbers, right-aligned. The user row uses the navy selected-row treatment, with padding inside the highlight. The gap under the card title matches the other Office cards. |
| Signing Day | `signing_day.points_remaining`, `points_total`, `promises_made`, `open_roster_spots`, `targets` |
| Season preview | `season_preview` fields that are non-null. The opener is the next-game card. |

Attribute changes are one row per `player_id`. The player name stays on the left and links to the player page. Chips are right-justified: the rightmost chip meets the card's right content edge, and the others sit to its left with a consistent gap. If they do not fit on one line they wrap, still right-aligned, under the name. A chip shows the attribute abbreviation in Bebas at `--fs-22` and `--text-100` (larger than the player name, the largest text in the chip), the new first-digit value in the tier colour from `attributeDisplay.js`, and a green ▲ or red ▼. Chips are not truncated. The previous value is not shown. The chip `title` is the full name from `ATTRIBUTE_NAMES` (`BH` → "Ball Handling"). Players sort by total absolute movement, then name. Inside a row, increases come before decreases. At 1280 the card shows up to 5 players. At 1920 it shows up to 8. When the list is longer, "All changes →" opens the training report for `result.week` (or `next_game.week` when there is no result). Rank, conference, and record tiles omit the delta chip when the delta is 0 or null.

Card titles (What moved, Team snapshot, Signing Day, Conference standings) are one type step smaller than the shared card title, `--fs-15`, and stay larger than the body copy under them.

Chemistry fill uses the red, yellow, and green tokens for 0–8, 9–16, and 17–25. The track stays neutral. The bar and the chemistry value keep the shared meter and snapshot sizes at both densities. Attitude is five equal columns, 😡 😕 😐 😊 😎, each with the count and a short bar for that bucket's share of the roster. The bar colours run red, orange, neutral, green, bright green. The emoji, count, and bar are centred in the column, at the same sizes at both densities.

Attribute `from` / `to` are already the first-digit scale. Player RT on a signing target is the letter already on the digest. Attitude counts use the EM emoji buckets. A loss result uses the calm card (no wash, no count-up). A win counts the scores up once, on the first open after that result. `prefers-reduced-motion` shows the final state immediately.

Tournament weeks keep the top-bar tier from `tierEmblem.js`. The next-game card takes the same metal tokens. `projected_starting_five`, `team_rt`, `seeds`, `stakes`, `date`, `neutral`, `stars`, and `filmed_grade` stay off the page because they are null. There is no Team RT row and no coach-stat block.

## 13. Leader qualification

A rate leader qualifies when attempts are at least the floor times the games that player's team has completed in the scope being read (attempts per team game). Team games are wins plus losses from `franchise.results`. There is no separate games-played rule. The floors live in `LEADER_QUALIFICATION_FLOORS` (`BackEnd/constants/leader_qualification.py`). `qualifies(stat, attempts, team_games)` is the only check.

| Stat | Floor (attempts per team game) | Attempt field |
| --- | --- | --- |
| FG% | 5 | FGA |
| 3PT% | 2 | 3PTA |
| FT% | 2 | FTA |
| DEF% | 6 | DEF_A |
| SCR% | 5 | SCR_A |

Season Leaders (FG% and DEF%), the league-news FG% and DEF% boards, and the community-highlights top defender use this rule. SCR%, 3PT%, and FT% are defined for any later consumer. Leaders does not show those three today.

Career Leaders keep the older rule for FG% and DEF%: attempts at least 5 times that player's own games played. Zero team games never qualifies a season rate. Exactly the floor qualifies. One attempt below does not.

## 14. Views

A view is a section of the franchise app that lives at `franchise-command-center.html?tab=<view-id>`. That is the same URL rule as today's in-page tabs. Rail clicks still push. Sub-tabs still replace. Back restores the view and the scroll position `GOBNav` already stores. There is no second URL scheme.

The Office stays a panel already in the page. Roster, Player Stats, Team Attributes, Team Schedule, Standings, Rankings, Leaders, Team Stats, League Schedule, News, Awards, the Training Report (`training-report-view`), Game Plan (`game-plan-view`), Playbooks (`playbooks-view`), and Player Training (`training-view`) are module views. The Training Report mounts `training-report.js` `init(root)` into `#training-report-view` — no `training-report.html?embed=1` fetch, no DOMParser, no IIFE. `training-report.html` still redirects here. Game Plan mounts `game-plan.js` `init(root)` into `#game-plan-view` the same way — no `game-plan.html?embed=1` fetch, no DOMParser, no IIFE. `game-plan.html` still redirects here except `resume_from_timeout=true` and `mode=tutorial`, which stay on the standalone file in focus (no rail). Playbooks mounts `playbooks.js` `init(root)` into `#playbooks-view` the same way — no `playbooks.html?embed=1` fetch, no DOMParser, no IIFE. `playbooks.html` still redirects here except `mode=tutorial`, which stays on the standalone file (browse chrome). Player Training mounts `training.js` `init(root)` into `#training-view` the same way — no `training.html?embed=1` fetch, no DOMParser, no IIFE. `training.html` still redirects here except `mode=tutorial`, which stays on the standalone file. A module view is the same kind of panel, loaded the first time it opens and left mounted so the next open is instant. The old Roster and Team Measures panels remain in the page. `?tab=roster-tab` and `?tab=team-stats-tab` open the new views. An old Standings, Leaders, or Team Stats `?tab=` still opens the old panel. Team › Schedule reads `GET /franchise/team-detail`. League › Schedule reads `GET /franchise/schedule/week` (`@browse_cached`, one week). The whole-season national route stays for other callers. The next-game row on the team schedule is a neutral tint with a 2px neutral marker on its week cell. Navy (`.gob-game.me`) is only the user's game on the league week, the same mark the Office uses for the user's team. The league week is four equal columns of compact game cards (two below 1100px). A card is the away line, the home line, and a quiet footer. Each line is the logo, the rank only when it is 1–25, the team name (ellipsis, never wraps), and the score. The winner's line is full white and the loser's is `--text-60`. The footer is the tournament context, or Final or Scheduled, and a quiet Box score link on played games. The week stepper, the round title, and the empty lines are unchanged. The team schedule is four equal mini-tables of weeks, so the whole regular season fits 1280×720. Each row is Week, Site (vs/at), then logo and "#rank Opponent" with the record on a quieter second line, then the result. The result ("W 75-65") is itself the box-score link; future games leave it empty and show no time.

League › Standings always shows the whole league, one T1 card per conference with the user's conference first. It has no Conference / Region / National segment; the only tool is the search. League › Rankings is one T1 card, "National Rankings", in the Standings treatment: `#`, Team (logo and name), W, L, PF, PA, Last Week (the W/L mark in the `.gob-wl` data colours, then the stored line), Next. The user's row is navy (`tr.me`). Top 25 / All 128 is a neutral segment in the page-head tools (`gob-view-rankings-show-all`). The payload has no previous rank, so there is no movement column. League › Leaders keeps the Conference / National segment. Each board shows the top 10 on National and the top 5 on Conference; the board request's `limit` matches. League › Team Stats is one compact T1 table that fits `.main` at 1280 and 1920. It has exactly one header row, which pins under the page head on scroll; there is no group band and no repeated header row. The group names are the header `title`, and the shaded groups keep their shade. A Conference / National segment (`gob-view-team-stats-scope`, default National) sits before the search. Conference requests `GET /franchise/team-stats?scope=conference`, which the server filters to the user's conference.

News reads `GET /franchise/news` (`@browse_cached`). `news` is `season_news` as stored and `dispatches` are your-team rows from `latest_training` and `season_inbox`. Newest first. The top story is full width; the rest sit in a 2-column grid at 1280 and a 3-column grid at 1920, left to right then down, equal card height in a row. The whole headline is the link. There is no separate View or Box Score control. A `game_result` headline ends with ` (Box Score)` and opens the box score. Other stories open the article in this panel; other dispatches open `target`. `yours` is the navy left edge. `news.html?story=` redirects here with the story param. The Office card still uses `news_headlines` (five, upset reports excluded).

Awards reads `GET /franchise/awards` (`@browse_cached`). Before week 35 the route is 400 and the view says "Awards are not available yet." From week 35 the snapshot is `all_american_teams` (1st, 2nd, 3rd) with the stored stat line. The user's team row is `tr.me`. There is no season list and no portrait.

### Add a module view

1. Move the page's read onto a browse GET `GOBStore` already caches. No new endpoint.
2. Add `js/shared/views/<name>View.js` that exports `mount(container, ctx)` and `unmount()`. `ctx` has `franchiseId`, `teamId`, `store` (`GOBStore`), and `nav` (`GOBNav`). `mount` returns `{ unmount, revalidate }`.
3. Register it in `js/shared/gobViews.js`: `id`, `section`, `subtab`, `title`, and `module` (a function that returns `import(...)`).
4. Add an empty `<div id="<view-id>" class="tab-content">` on `franchise-command-center.html`, and map the id in the shell section list so the sub-tab calls `CommandCenterTabs.show(id, 'replace')`.
5. Leave the old HTML file as a redirect to `franchise-command-center.html?tab=<view-id>` that copies `franchise_id`, `team_id`, and any return params.
6. Update the section map in this file.
7. Cover it with tests: no document navigation, first-open skeleton, failed module, history, and a week-advance refresh.

### Save feedback

A save inside the command center confirms with `GOBToast.show(text)` (`js/shared/gobToast.js`, `css/gob-toast.css`): one short line such as "Playbooks saved", neutral chrome (`--surface-popover`, `--shadow-popover`, `--text-87`; no orange, no green, no icon), `role="status"` with `aria-live="polite"`. It is fixed over the centre of `.main`, `--dsp-24` above the bottom, so it never shifts layout. It fades after `GOBToast.SHOW_MS` (1500ms); a second call restarts the timer. The class is `.gob-save-toast`, because the tutorials' `.gob-toast` is unscoped. A hosted save stays on the view. A failed save uses the same toast with a short retry line. Standalone pages that still load `game-plan.html` or `playbooks.html` directly keep their own `#toast` and navigation.

Unsaved-edit leave: see §6 (`warnOnLeave`, `GOBLeaveConfirm`). Game Plan and Playbooks register a confirm for their view. Training saves each edit as its session draft and restores it on the next open.

### Loading

The first open paints a neutral skeleton in the shape of the view. No spinner. Data comes from `GOBStore.get`. The module stays in the panel after the user leaves. Opening it again shows that panel immediately and calls `GOBStore.revalidate`. The view re-renders only when the body changed. A 304 keeps the table on screen.

An unknown module, or an import that fails, paints a quiet error card with Retry in that panel. The rest of the app stays up. Retry loads the module again. A `?tab=` that is neither a panel nor a registered view still falls back to the section default, as today's tabs do.

Opening a player from Roster writes `gob-view-roster-order` in `sessionStorage`: a JSON array of the player ids in the order on screen at that click. The Leaders full list (and each Leaders board card) writes `gob-view-leaders-order`, the same shape. Player Stats writes `gob-view-player-stats-order`, the same shape, and the detail URL carries `pager=player-stats` with `origin=team` and `return_tab=player-stats-view`. Standings writes `gob-view-standings-order` as `{ ids, label }`, the visible team ids in that conference card and the card label (for example `A2`). The detail URL carries `pager=roster`, `pager=leaders`, `pager=player-stats`, or `pager=standings`. No `pager` param means no pager, even if a key is sitting in the session. Paging replaces the history entry and stops at the ends. The Roster Varsity / Practice Squad segment is `gob-view-roster-scope` (`varsity` or `practice`).

`player-view` and `team-view` are drill-ins, not sub-tabs. A list opens them in the command center with `GOBViews.open(url, 'push')`: no document load, and Back pops to the list. Team links are built by `GOBTables.rosterHref` as `?tab=team-view&view_team_id=…`. An old `team-roster-view.html?roster_team_id=…` or `player-detail.html?id=…` link clicked inside the command center opens the same drill-in in place; loaded directly, the file still redirects. A drill-in URL starts from the current query minus the last drill's keys (`player_id`, `view_team_id`, `pager`, `up`, `origin`, `return_tab`, `return_url`), so `return_url` never nests. The rail highlights `origin` (`team`, `league`, `office`, or `prep`); with no `origin`, no section is highlighted. Every rail button, Office included, works from a drill-in. The page's `team_id` stays the user's team. The team being read is `view_team_id`.

On desktop, same-document URL changes (push, replace, Back) are written into the session context as they happen, so the next tab switch keeps the drill-in's params.

A desktop resume (the command center opened without `?tab=`) onto a locked tab (Tournament before week 27) opens Office instead, with a replace. An explicit `?tab=tournament-view` link, or `brackets.html`, still shows the locked Tournament screen. Web has no resume, so the rule never fires there.

## 15. Detail data

`player-detail.html` still reads `GET /player/{id}`. The T3 player page reads `GET /franchise/player-detail`. The T3 team page reads `GET /franchise/team-detail`. Both are `@browse_cached`. The page formats the numbers. It does not derive a rate, a place, a streak, or an attribute bucket. The roster table on the team page is still `GET /roster/{team}`. There is no server pager. The client keeps the list order it already sorted.

### Player

`GET /franchise/player-detail?franchise_id&player_id`

| Field | Meaning |
|---|---|
| `player_id`, `name`, `team_id`, `team_name`, `team_primary_color` | Identity. Color is null when the team document is missing. |
| `position` | Same rule as the roster chip (`_roster_position`). |
| `year` | Class abbreviation from `format_player_year_abbrev` (`FR`, `SO`, `JR`, `SR`). Unknown is `--`. |
| `height_in`, `weight`, `jersey` | Stored meta. Height is inches. |
| `is_user_team` | This player's team is the franchise's user team. |
| `rt` | Highest numeric position rating. The same number the roster page passes to `rtBucket.js`. Null when there is no rating. |
| `potential` | `potential_rt_ratcheted`. Already ratcheted. Null when there is no projection, and the page shows the current rating alone. |
| `attributes` | Six groups, in order: Offense `SC` `SH`, Defense `ID` `OD`, Skills `PS` `BH`, Grit `RB` `ST`, Body `AG` `ND`, Mind `IQ` `FT`. Each attribute is `{attr, raw, display}`. `display` is `floor(raw / 10)`. Missing raw is null, and so is display. |
| `season`, `career` | `gp`, `min_per_game`, `pts_per_game`, `reb_per_game`, `ast_per_game`, `stl_per_game`, `blk_per_game`, `fg_pct`, `tp_pct`, `ft_pct`, `def_pct`, and `totals`. Per-game is null when GP is 0. A percentage is makes / attempts × 100, and null when attempts are 0. `totals` holds `GP`, `MIN`, `PTS`, `REB`, `AST`, `STL`, `BLK`, `FGM`, `FGA`, `3PTM`, `3PTA`, `FTM`, `FTA`, `DEF_S`, `DEF_A`. |
| `recent_changes` | This season's training reports for this player, newest week first. `{week, session_type, changes}`. A current-shape week stores display buckets: `{attr, from, to}`. An older week stores a name-keyed signed raw delta and cannot supply from/to: `{attr, delta}` only. Zero changes are omitted. A week with none is omitted. `session_type` is the stored value, or `preseason` for week ≤ 1 and `in-season` after that. |
| `development` | `{focus, focus_label, emphasises, editable}`. `emphasises` is the attributes whose weight in `TRAINING_FOCUS_PERCENTAGES[position][focus]` is above `standard`, highest first, at most three. Ties keep the group order above. `standard` emphasises nothing. `editable` is true only on the user's team. |

### Team

`GET /franchise/team-detail?franchise_id&team_id` for any team in the franchise.

| Field | Meaning |
|---|---|
| `team_id`, `name`, `primary_color` | Display name and color, including a Team Builder overlay on the replaced slot. |
| `conference` | Short label: region letter plus the conference's own number (`A1`, `A2`, `B3` … `H16`). |
| `region` | Stored region, or the letter derived from the conference number. |
| `record` | `{wins, losses}` from `calculate_franchise_standings`. |
| `natl_rank` | Current `franchise_team_data.natl_rank`. |
| `conference_place` | `1st of 8`. Place is `standings_display_sort_key` only (wins, then point differential). The size is the number of franchise teams in that conference. Null when the team has no conference. |
| `streak` | `W4` or `L1` from `current_streaks`. Null when the team has no decided game. A tie ends the streak. |
| `next_game` | The next schedule game that has no result. Null when none remain. `{week, site, opponent_id, opponent_name, opponent_primary_color, opponent_natl_rank, opponent_wins, opponent_losses}`. `site` is `home` or `away`. Opponent rank is that team's current national rank. Wins and losses come from `calculate_franchise_standings`. |
| `results` | Completed games, newest week first. The next-game fields plus `team_score`, `opp_score`, and `result` (`W` or `L`). A tie has `result` null. `game_id` is set when a played game document matches the matchup. |
| `upcoming` | Later unplayed schedule games, same shape as `next_game`, not including `next_game`. |

No stored tip time, neutral site, or hometown. Those stay off the page.

### Team attributes

`GET /franchise/team-data?franchise_id&team_id` stays `@browse_cached`. It still returns `team_attributes`, `plays_data`, and `scouting_data`. It returns one `measures` list and `updated_after_week`. The page does not sort the league or decide which end of a measure is good.

`updated_after_week` is the closed week of the latest earlier office snapshot, or null. The line "Updated after Week N" renders only when it is set.

There are always twelve rows — every stored team measure — in family order. Character: Chemistry, Fight, Discipline, Momentum (`momentum_score`). On the floor: Offense (`offensive_efficiency`), Defense (`defensive_efficiency`), P/T Offense (`pt_opp_modifier`), P/T Defense (`pt_efficiency`), Fast Break (`fb_efficiency`), Fast Break Defense (`fb_opp_modifier`), Shooting (`shot_threshold`), Rebounding (`rebound_modifier`). A missing stored value is still a row, with `value` null.

`pt_efficiency` is your own press and trap execution, so it reads as P/T Defense. `pt_opp_modifier` is working through the opponent's press, so it reads as P/T Offense. The radar's axis labels use the same words.

| Field | Meaning |
|---|---|
| `family`, `family_label` | `character` / Character, or `floor` / On the floor. |
| `key`, `label` | The twelve measures and the labels above. |
| `value` | The stored number for this week. Null when the team has no stored value. The zero-fill on `team_attributes` does not apply here. The page shows it for Chemistry as `19/25`, and as a signed number on the eight measures that carry `signed_scale`. |
| `scale_max` | 25 for Chemistry. Null for the others. |
| `signed_scale` | 20 on the eight trained and compounding measures that `Team_Attribute_System.md` documents at −20…+20: Fight, Discipline, Offense, Defense, P/T Offense, P/T Defense, Fast Break, Fast Break Defense. Null on the other four. Only a row with `signed_scale` may be drawn as a ± pill, because only those have a meaningful zero. Chemistry (7…25), Momentum (−10…+10), Shooting (~85…95) and Rebounding (~0.5) stay on the league percentile bar. |
| `meter_pct` | Chemistry only: `value / 25 × 100`, clamped 0–100. Null when Chemistry has no value, and null on the other eleven. The bar does not read this. |
| `delta` | Change in the stored value since the user team's snapshot. Null when there is no prior value. The page does not show this chip. |
| `description` | Null until a sentence is stored. |
| `direction` | `higher_better` for all eleven others. `lower_better` for Shooting only: a make is `shot_score >= shot_threshold`. |
| `rank` | 1 is the best end of `direction`. Ties share a place and the next place skips (`1, 2, 2, 4`). Null when `value` is null. |
| `rank_of` | How many teams in the franchise have a stored value. A missing value is not counted. |
| `percentile` | 0–100. 100 is the best end, including a tie for best. 0 is the worst end, including a tie for worst. The bar fills to this. `100 × (teams strictly worse) / (teams strictly better + teams strictly worse)`. One team, or a measure where every stored value is equal, is 100. |
| `rank_delta` | How many places the user's team climbed since the latest earlier `office_week_snapshots` `team_measures`. Positive means it moved up. The snapshot is the user team only, so every other team is null. Chemistry is not in that snapshot, so Chemistry is null. Movement is neutral, matching Prep v2: ▲ at `--text-100`, ▼ at `--text-60`. Null and 0 draw nothing. |
| `tied` | True when this rank is shared. The place then reads `T-34th of 128`. |

The place reads `34th of 128`. A null rank reads an em dash and the bar is empty. The bar fill is the neutral DIFF white, not navy.

The view is the radar over a grid of four columns by three rows. The radar is `franchise-command-center.js::buildTeamMeasuresRadarMarkup` at its ±20 scale — call it, never write a second one. The grid pairs a measure with its opposite down each column: Offense/Defense, P/T Offense/P/T Defense, Fast Break/Fast Break Defense, Shooting/Rebounding, with the four character measures on the bottom row. Each cell is the name, the place, the gauge, the value and the movement.

The ± pill is the shared `.gob .dv` atom in `gob-components.css`, the same one Prep › Scouting uses: zero in the centre, filling right for positive and left for negative, with `--v` as the magnitude 0–1 and `.neg` flipping the fill.
