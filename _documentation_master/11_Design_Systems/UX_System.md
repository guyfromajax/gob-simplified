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

Top bar, left to right: team logo (existing `#team-logo`, height `var(--top-h)`, width auto, `object-fit: contain`, no crop) with `--dsp-12` of horizontal padding on each side before the divider. Its alt, `title`, and link `aria-label` are the team name. The name is not painted as visible text. The control opens Team › Roster. Then a divider, Record, National Rank, Week. Record text comes from `#fcc-record-label` (standings W-L for the user's team). National Rank comes from `#fcc-rank-label` / `data.rank`, shown as `#N` or `NR`, with the label "National Rank". Week comes from `data.week`. There is no Team RT. There is no alpha badge, product logo, or social link. The build label stays in Settings.

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

Scroll rule: only `.main` scrolls, on the Office, on browse pages, and in focus mode. Nested vertical scroll areas are removed (`overflow: visible`, no max-height). `tests/e2e/helpers/oneVerticalScroll.js` (`assertOneVerticalScroll`) fails when any other element has `overflow-y` `auto` or `scroll` and `scrollHeight > clientHeight + 1`. Dialogs and the settings host are not page scrollers. A horizontal scroller whose extra height is only the scrollbar (24px or less, and wider than its box) is reported, not failed.

Sticky versus wide tables: after each render and on resize, each table's content width is compared with `.main`'s content box. A table that fits gets a page-level sticky `thead` (`top: var(--gob-stick-top)`, the measured `.pg-head` height; `0` in focus). Ancestors between the header and `.main` stay `overflow: visible`, so the header pins on `.pg-head`'s bottom and scrolls away with its own table. A table wider than `.main` gets `.gob-wide-wrap`: `overflow-x: auto`, `overflow-y: clip`, the table stays inside its card, a right-edge fade shows while columns are hidden (and a left fade once scrolled), and that header is not sticky.

Page transitions: browse shell pages and the Office use `@view-transition { navigation: auto; }`. `.top` and `nav.rail` have stable `view-transition-name`s so they stay put. The rest of the page crossfades in 150ms with `--ease-out`. Focus pages set `navigation: none` so a flow step is a normal load. `prefers-reduced-motion: reduce` also sets `navigation: none`. Browsers without the API navigate normally.

The top bar Record reads `#fcc-record-label` on the Office, then `team_record.wins` / `team_record.losses` when that object is on the command-center payload, then the user's row in `rankings` (`W` and `L` for `user_team_object_id` / `user_team_id` / `team_id`). Those standings are already on `/franchise/command-center/data`.

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
| `what_moved.attribute_changes` | `{player_id, name, attribute, from, to}`. `from` and `to` are the first-digit display scale (`value // 10`). Keyed by player id. Legacy name-keyed direction maps are omitted. |
| `team_snapshot.state` | `set_after_camp` until a snapshot exists for a week before the current week. Otherwise `ready`. |
| `team_snapshot.chemistry` | `{value, max: 25}` from stored team chemistry. |
| `team_snapshot.attitude` | Counts in the EM buckets 0–19, 20–39, 40–59, 60–79, 80+. |
| `team_snapshot.moved_most` | Up to two `{measure, value, delta}` rows. Delta is this week's stored measure minus the previous snapshot. Empty until a prior snapshot exists. |
| `result` | Last completed user game, or null. Scores, site (`home` / `away`), `neutral` (always null; no stored neutral site), opponent rank, round name for weeks 27–34, POTG on a win or the user's highest-PTS player on a loss, box-score path and params. `headline` only when a `season_news` story stores this game's id. |
| `next_game` | Opponent, rank, record, conference, site, week, top scorer, top rebounder. `conference_position` and `conference_size` are the opponent's 1-based place in its own conference and the number of teams there, using the Standings order. Both are null when the opponent cannot be placed. `date`, `neutral`, `projected_starting_five`, `seeds`, `stakes`, and `team_rt` are null. |
| `conference_standings` | The user's conference in Standings order. `conference` is the conference number, `region` is the stored region or the letter derived from that number (1–2 = A … 15–16 = H), and `rows` are `{team_id, team_name, wins, losses, differential, position, is_user}`. Ties follow `standings_display_sort_key` (wins, then point differential) and match `GET /franchise/standings` for the same results. Null when the user has no conference. |
| `todos` | `{id, label_key, required, done, gates_advance, is_advance_action, route}` from the same flags as `gobAdvance.js`. A blocking task is the Advance action. |
| `recruiting_wire` | Status line, events (`recruit`, `position`, `stars` and `filmed_grade` always null, `event_type`, `event_text` from the stored lean-event sentence, `list_position`, `direction`), `pending_count`, `urgent`, `unseen_count`. |
| `signing_day` | Week 35 only. Points remaining out of 50, playing-time promises, open roster spots, up to three targets. Otherwise null. |
| `season_preview` | `first_week` only. Preseason rank is the current national rank. Conference projection, team RT, returning starters, and top returner are null. Newcomers only when `pending_walk_on_welcome` is stored. Opener is `next_game`. |

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

Cached routes are the browse GETs: command-center, standings, schedule (including national), leaders, team-stats, team-player-stats, team-data, news, recruiting-data, recruiting-results, practice-squad, awards, scouting-report, roster, player, recruit, teams, game plan, and playbooks.

Never cached: `GET /api/game/{id}`, `POST /api/simulate-quarter`, `/api/auth`, and any URL with `profile=1`. `profile=1` is only added when the page URL has `cc_profile=1`.

`ResourceCache` (the old season+week `sessionStorage` copy) always misses. Do not add a second cache in a page.

A new browse view calls `GOBStore.get` or plain `fetch` (the store wraps `fetch` for the routes above). A new franchise write uses `fetch` or `GOBStore.mutate` so the franchise cache is cleared. Do not read `sessionStorage` for a browse body yourself.

The Office does not call `GET /franchise/state`. Season counting stats for the user's roster are `players[].stats.season` on `GET /roster/{teamId}` in franchise mode, copied on read from `franchise_players_data.season`.

## 12. Office

The home tab of `franchise-command-center.html` is the Office (`.office` inside `.main`). It has no page title and no sub-tab row. `js/shared/officeHome.js` paints it from `office_digest` only. Grouping and sorting attribute changes for display is allowed. A null field is omitted. The page does not substitute another payload, and it does not write "N/A".

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
| `win`, `loss`, `regular`, `tournament` | Result · What moved | Next game · Team snapshot | Recruiting wire, then the full conference standings. The column heading is the link to the recruiting hub. No events: "No recruiting movement this week". |
| `first_week` | Season preview | Next game · Team snapshot | One-line wire, then the full conference standings. The digest status when it is set, otherwise the empty-state line. The column heading is the hub link. |
| `signing_day` | Result · What moved | Team snapshot (`next_game` is null) | Signing Day card, then the full conference standings. The wire is hidden. The column heading still links to the hub. |

The three columns are equal width. The wire card is as tall as its rows. "Recruiting →" opens the recruiting hub. Result team names wrap, and at the 1280 density the score is smaller so a long name is not cut off.

| Component | Digest fields |
|---|---|
| Week strip | `todos[]` `label_key`, `done`, `required`, `gates_advance`, `is_advance_action`, `route`. No week label and no ADVANCE tag. |
| Result | `result` scores, names, `opponent_rank`, `site`, `round_name`, `user_won`, `headline`, `leader`, `leader_role`, `box_score`. The user name is prefixed with `#` plus `what_moved.national_rank.now` when that rank is set. No team monograms. |
| What moved | `what_moved.national_rank`, `conference_standing`, `record`, `streak`, `attribute_changes` |
| Recruiting wire | Deduped `recruiting_wire.events` (`event_text`, `position`, `list_position`, `direction`). One row per `recruit_id`, or per name when the id is missing, keeping the latest event. At most 8 rows at the 1280 density and 12 at 1920. The list shrinks, oldest first, so the standings card below it stays on the page. It never drops below 3 events when any exist, and it never shows a half-cut row. The column heading opens the hub. Rail badge uses `pending_count` and `urgent`. |
| Next game | `next_game` opponent, `rank` as `21. Name` in upright Bebas, `record`, `Conference` plus the short label and `(place of size)` from `conference_position` and `conference_size`. The place is omitted when either is null. No week callout and no monogram. |
| Team snapshot | `team_snapshot.chemistry` (red 0–8, yellow 9–16, green 17–25), five equal attitude columns, `moved_most`, `state` |
| Conference standings | `conference_standings.rows` under the recruiting list in column 3. Every row, at every size. Header is `Conference` plus the short label plus `standings` (`Conference A2 standings`). The user row uses the navy selected-row treatment. |
| Signing Day | `signing_day.points_remaining`, `points_total`, `promises_made`, `open_roster_spots`, `targets` |
| Season preview | `season_preview` fields that are non-null. The opener is the next-game card. |

Attribute changes are one row per `player_id`. The player name stays on the left and links to the player page. Chips are right-justified: the rightmost chip meets the card's right content edge, and the others sit to its left with a consistent gap. If they do not fit on one line they wrap, still right-aligned, under the name. A chip shows the attribute abbreviation in Bebas at `--fs-22` and `--text-100` (larger than the player name, the largest text in the chip), the new first-digit value in the tier colour from `attributeDisplay.js`, and a green ▲ or red ▼. Chips are not truncated. The previous value is not shown. The chip `title` is the full name from `ATTRIBUTE_NAMES` (`BH` → "Ball Handling"). Players sort by total absolute movement, then name. Inside a row, increases come before decreases. At 1280 the card shows up to 5 players. At 1920 it shows up to 8. When the list is longer, "All changes →" opens the training report for `result.week` (or `next_game.week` when there is no result). Rank, conference, and record tiles omit the delta chip when the delta is 0 or null.

Card titles (What moved, Team snapshot, Signing Day, Conference standings) are one type step smaller than the shared card title, `--fs-15`, and stay larger than the body copy under them.

Chemistry fill uses the red, yellow, and green tokens for 0–8, 9–16, and 17–25. The track stays neutral. The bar and the chemistry value keep the shared meter and snapshot sizes at both densities. Attitude is five equal columns, 😡 😕 😐 😊 😎, each with the count and a short bar for that bucket's share of the roster. The bar colours run red, orange, neutral, green, bright green. The emoji, count, and bar are centred in the column, at the same sizes at both densities.

Attribute `from` / `to` are already the first-digit scale. Player RT on a signing target is the letter already on the digest. Attitude counts use the EM emoji buckets. A loss result uses the calm card (no wash, no count-up). A win counts the scores up once, on the first open after that result. `prefers-reduced-motion` shows the final state immediately.

Tournament weeks keep the top-bar tier from `tierEmblem.js`. The next-game card takes the same metal tokens. `projected_starting_five`, `team_rt`, `seeds`, `stakes`, `date`, `neutral`, `stars`, and `filmed_grade` stay off the page because they are null. There is no Team RT row and no coach-stat block.
