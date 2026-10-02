# UX System

Version 1. How to build franchise screens. The look lives in [Styleguide.md](Styleguide.md). Every color, size, and duration lives in `FrontEnd/static/css/gob-tokens.css` under `.gob`. Name the token. Do not copy the value into a page, a component, or this document.

## 1. Principles

- The frontend is a pure renderer. UESS (`_documentation_master/05_UESS_System/UESS_System.md`) owns game logic. A screen formats fields the page already loaded. It does not invent a missing field, derive one, or move a rule to the client.
- One green Advance per screen. It is the only control that uses the advance color. A blocking task becomes the Advance button (same id, same `updatePlayButton` state machine, same labels and routes). There is no disabled-with-lock state and no hint link. Recruiting chrome follows the same law: green is only Advance and positive data (board gains); orange is only saves (Submit Invites, Submit Orders); navy is only "yours" (your lean, your region, your signing). Phase labels, week tiles, invite counts, and filter chips stay neutral.
- No spinners. A click that leaves the page switches Advance to the loading look immediately (`is-loading`, label `STARTING…`) and ignores repeat clicks.
- Blue belongs to RT. Do not use the rating blue for chrome, links, or navigation.
- Reward gold (`--reward-gold`) is only for milestone and season-peak reward tiers, exceptional stat gains and senior-tribute title marks. It is never for buttons, Advance (green), "yours" (navy), choice controls, everyday / weekly chrome, or Home Base chrome. It is the one reward token: tints are `color-mix()` at the point of use, so there are no gold tint or shadow tokens.
- Live gameplay has no shell. The court never mounts `.app`, `.top`, or `.rail`.
- Navigation is two levels: a rail section, then a sub-tab. Do not add a third level.
- Attribute digits stay on the first-digit scale (`attributeDisplay.js`). Player RT stays a letter grade (`rtBucket.js`).

## Colour law

The canonical law is [Styleguide.md#colour-law](Styleguide.md#colour-law); read it before touching colour.
In short: green is the one Advance plus positive data; orange is "there are unsaved changes" and nothing else (a save or commit); navy is "yours" and what you picked; blue is RT A / 9+ / elite only; `--reward-gold` is the six reward surfaces only. Choice controls, status codes, W/L plates (tables too), ▼ deltas, the rail count badge, blocking tags, modal accents and "Stay" stay neutral; ▲ is green only on data chips; red marks only an irreversible delete; team colour never washes a card. Two data palettes sit outside that line, each with its own rule in the Styleguide's Data scales: the coaching style marks and the Training Report movement marks. That line is a reminder, not the law: if it and the Styleguide differ, the Styleguide wins.
`scripts/check_ui_tokens.py --strict` enforces it on new-design files (§8). Annotate a legal exception with `/* colour-law: positive-data | committed | saved | reward */`.

### Settled rulings (2026-10-01)

Jamie's rulings (`reports/jamie-decisions-2026-10-01.md`) and the same day's gallery fixes. **The rule for each is in the Styleguide** ([Settled 2026-10-01](Styleguide.md#settled-2026-10-01) links every one to its section). This table is only where each was built and what guards it.

| # | Ruling | Built in | Guard |
|---|---|---|---|
| 1 | Navy for what you picked | Set Lineup on-court / selected rows (`set-lineup.css`). Plays in your Playcall Center, their slot number and the call-sheet rows (`#playbooks-view .play.on`, `.slot`, `.csr` in `playbooks.css`). Your lean-ladder slot (`.lb-slot.is-you`, `.is-you-list`, `.recruit-stand-*` in `recruiting-lean-ladder.css`; `--you-edge` in `recruiting-spine.css`). Your leaderboard row (`.alb-row.is-current`). Your team in a bracket (`.fcc-tb-*--user` in the frozen FCC sheet and `css/gob-views.css`; the big-news modal passes `userConnectorNavy`). | `jamie-rulings-batch.spec.js` |
| 2 | Shot-share ramp kept | `getPswColor()` in `common.js`, the `.psw-*` pills, `css/playbook-cmd.css`. Kept as they are. Not a migration target. | none |
| 3 | Court game-state colours kept as data | "Live-game screen chrome" below. | the five equivalence specs |
| 4 | Court side panels on blue-black surfaces | `court.html`, "Live-game screen chrome" below. | `court-panel-tokens.spec.js` |
| 5 | Court stat toggles neutral | `court.html` `.toggle-btn.active`, `.team-toggle-btn.active`. | `court-panel-tokens.spec.js` |
| 6 | Senior-tribute title marks gold | `.st-titles s`, `.st-cti s` in `css/senior-tribute.css`, annotated `reward`. | `jamie-rulings-batch.spec.js` |
| 7 | Recruiting presence dot neutral | `.inbox-badge` in `franchise-command-center.css`. Under the shell the dot only sits on the hidden legacy tab button, so nothing shows on the rail today. The rail count badge (`.office-rail-count`, `--badge`) is a different element: neutral since batch 2 (below). | `jamie-rulings-batch.spec.js`, `fcc-recruiting-layout.spec.js` |
| 8 | Big-news modal button neutral | `.bn-cta` in `css/big-news-modals.css`. The emblem, eyebrow and title glow keep the gold. | `jamie-rulings-batch.spec.js` |
| 9 | Submit Training green | `/training.html`. Its sound stays `SFX_COMMIT` (§3): the colour ruling did not change the sound. | none |
| 10 | Twin pages deleted | `homepage-v3.html` and `play-builder.html` (V1) are gone. `/play-builder.html` → `/play-builder-v2.html` and `/homepage-v3(.html)` → `/` in `netlify.toml` and `FrontEnd/static/_redirects`; the V1 path also in `BackEnd/api/play_routes.py` and in the local static middleware's `retired_pages` (`BackEnd/api/api.py`), because that middleware answers a missing `.html` before any router runs. | `tests/test_play_builder_redirect.py`, `jamie-rulings-batch.spec.js` |
| 11 | Desktop app icon | `desktop/build/icon.icns`, `icon.ico`, `icon.png` from `icon-source-1024.png`. `desktop/pack.js` picks them up when they exist. | `tests/test_desktop_shell_local.py` |
| — | Franchise Set Lineup starts empty | "Set Lineup" below. | none |
| — | One empty-state card | "Empty states" below. | `desktop-gallery-fixes.spec.js` |
| — | Save buttons neutral until something has changed (orange = there is something to save) | "Rulings recorded 2026-10-01 (gallery follow-up)" below. | `desktop-logo-save-state.spec.js`, `prep-modules-*.spec.js` |
| — | Team art `logo_square` → `logo_primary` → letter tile | "Rulings recorded 2026-10-01 (gallery follow-up)" below. | `desktop-logo-save-state.spec.js`, `tests/test_team_logo_manifest.py` |

### Settled rulings, batch 2 (2026-10-01)

Jamie approved every recommendation in `reports/jamie-decisions-2-2026-10-01.md`. **Net rule: orange = "there are unsaved changes" and nothing else.** The rules are in the Styleguide ([Settled 2026-10-01 (batch 2)](Styleguide.md#settled-2026-10-01-batch-2)); this is where each was built. Guard for all rows: `jamie-rulings-batch-2.spec.js` (computed styles), plus `tests/test_check_ui_tokens.py` for the checker.

| # | Ruling | Built in |
|---|---|---|
| 1 | ▲ green on data chips, ▼ neutral | `--delta-down` is `--text-87` (`gob-tokens.css`). `.chip.down` (`gob-components.css`), `.attr-chip.down` / `.attr-chip-val.down` (`box-score.css`), `.gob-chg .is-down i` (`gob-tables.css`) neutral; the recruiting-wire ▼ tag (`.wr.dn .wr-tag`) falls back to the neutral base. Dead `.attr-chip .arr` rules deleted (`office-home.css`). |
| 2 | W/L plates in tables | `.gob-wl` (`gob-tables.css`): WIN white plate (`--white-90` / `--bg`), LOSS `--white-40` outline. Rankings "Last Week" and Team › Schedule. Dead `.wl.win` / `.wl.loss` deleted (`gob-components.css`). |
| 3a | Rail count badge neutral | `--badge` is `--white-90` (`gob-tokens.css`); `--badge-ink` unchanged (dark). |
| 3b | `.td-gate` tag, `.is-on` neutral | `.td-gate` and `.todo.gated` (`gob-components.css`); `.hub-anchor--orders.is-on` (`recruiting-signing.css`); `.fg-pick.is-on` (`gob-advanced.css`). |
| 3c | Office blocking step | `.wk-step.gated`: `--white-62` outline, `--white-6` fill (`office-home.css`). |
| 3d | Attitude: no orange stop | `em_20_39` is `color-mix(--red 55%, --white-18)` (`office-home.css`). |
| 3e | Modal accent neutral by default | `.gob-modal-accent` default `rgba(255,255,255,.14)` in `resource-pages.css` (the `auth-bar.css` `:where()` mirror already was). `is-green` / `is-red` still opt in. |
| 3f | Tutorial alert neutral | Unchanged (`gob-tutorial.css`); now guarded. |
| 3g | "Stay" neutral primary | `cut-players.js` passes `neutral: true` → `.gob-modal-btn-primary.is-neutral` (`cut-players.css`, white plate). |
| 4 | No team-colour wash | Every `.office-res` rule deleted (`gob-components.css`, `office-home.css`); no code created it. The weekly card `.wkc` was already neutral. |
| 5 | Red only for irreversible deletes | **Kept red:** Home Base delete program (`.pop-i.danger` menu item, `.btn-del` red-outline confirm, `home-base.css`). **Now neutral:** every Assign Practice Squad modal accent (leave, confirm, load error; the initial and fallback accent in `cut-players.html` / `cut-players.js`) and the recruiting dock's remove-invite × (`.islot-remove`, `recruiting-dock.css`). No other destructive action has a red style (skeleton editors use the browser `confirm()`). |
| — | Checker | `SAVE_RE` in `scripts/check_ui_tokens.py` is save / commit only (`save`, `saved`, `committed`, `is-saved`, `is-committed`); `.gated`, `.td-gate`, `.is-on`, `toggle-btn`, `gob-btn--action` and the `.att-col` / `.att-bar` orange stop are off. Anything else orange needs `/* colour-law: committed */` or `saved`. |

### Settled rulings, orange stragglers (2026-10-01)

Jamie's ruling on the batch-2 annotated-orange list; rules in the Styleguide ([Settled 2026-10-01 (orange stragglers)](Styleguide.md#settled-2026-10-01-orange-stragglers)). Guard: `orange-stragglers.spec.js`.

| Was orange | Now | Built in |
|---|---|---|
| Recruiting hub toast | neutral | `.hub-toast` edge `--line-strong`, `.ti` `--white-6` / `--white-28` / `--text-87` (`recruiting-dock.css`) |
| Training playbook toast | neutral | `--toast-accent: var(--line-strong)` (`training-playbooks.css`) |
| Training Report stat toggle | neutral | `.tsr-toggle .toggle-btn.active` white 12% fill, white ink (`training-squad-report.html`) |
| Invite-board rank badge, on-board pool row | navy | `.pool-rankbadge` `--you` fill, `--text-100` ink; `.pool tbody tr.rec.on-board td` navy 14% (hover 20%) (`recruiting-dock.css`) |
| Committed recruit in the Orders rail | navy | `.citem` navy 14% fill, `--you-line` border, hover 20% (`recruiting-signing.css`) |
| My Orders mark | navy ink | `.hub-anchor--orders .ic` `--you-ink`, the hub's "yours" text colour (plain `--navy` is not legible on the dark rail) (`recruiting-signing.css`) |
| Username CONTINUE, Game Plan tutorial PLAY NOW | neutral plate | `gob-btn gob-btn--neutral` (`usernameModal.js`, `game-plan.js`) |
| Signing flash and summary | **kept orange** | `.prow.flash`, `.ssum-nm b` (`committed`), `.ssum-lr` (`saved`) unchanged |

### Live-game overlays (court.html DOM)

The live-game DOM overlays built with `createElement` in `js/phaser/utils/` are on the design system. (This covers the `js/phaser/utils/` overlays; the `court.html` inline **chrome** has its own section below, and the Phaser **canvas** HUD / announcements remain game presentation, out of scope.)

- `court.html` links `gob-tokens.css` (after `app-fonts`), and each overlay's root carries `.gob`, so `var(--token)` resolves. The `<link>` is the only allowed `court.html` change; it adds only `.gob`-scoped custom props, so the court paints identically.
- Colour, type, radii use gob tokens. The **one forward action** per overlay is green (`--green`/`--bg`): the EOG locker-room button, "Submit Defense Matchups", PGPC "Go To Locker Room", pregame "Submit & Tip Off". A button that only **navigates** (foul-out "Sub Players" → set-lineup) is neutral, not green.
- Neutralised law hits: W/L outcome badges → white fill / outline (never win-green/loss-red); orange accents/hovers/"don't-show" checkboxes → neutral (orange is saves only); the PGPC "simming" pulse bar → neutral (passive loader). "Don't show again" checkboxes are neutral because the pref persists only on submit — pending, not committed.
- Kept as data: team-colour name bars / badges / favor arrows (identification), the RT ramp (`matchupsUiShared.js` fallbacks), and the broadcast's 5-colour data palette.
- **Sim-safety:** visual-only; the five equivalence specs (`game-winner`, `sim-broadcast-fit`, `court-layout`, `game-start-sequence`, `sim-team-callouts` = 55) must stay byte-identical before/after.
- These are **legacy JS**, not on the `check_ui_tokens` new-design surface (do not add them to it — it would newly gate legacy files).
- **Game-state colours** in these overlays (the Sim broadcast's spotlight / "POSS" / "SPOT" orange, "FOUL TROUBLE" gold, the Sound switch's on green) are data and are not recoloured (ruling #3). The rule and the full list are in "Live-game screen chrome" below.

### Live-game screen chrome (court.html)

`court.html`'s own inline chrome (top scoreboard bar, pre-game start prompt, game-controls) is on gob tokens + the colour law. It is **legacy** (not on the `check_ui_tokens` new-design surface), so no top nav renders while a game is live.

- `court.html` `<body>` carries `class="gob"`, so gob-tokens.css custom properties resolve for the whole court DOM. gob-tokens.css is custom-properties-only (no element rules), so the court paints identically except where chrome now references tokens.
- **Pre-game start prompt** (`.pre-game-*`): "Play Quarter" / "Resume Game" (`.play-button`) is the **green Advance** (it starts the game); "Sim Full Game" is a neutral secondary; the top accent is neutral (was orange).
- **Scoreboard top bar** (`#scoreboard`): `--black` bar, `--text-*` neutrals. Kept as team-identity (annotated `/* colour-law: team-identity */`): the score underlines, the away→home divider gradient endpoints, and the logo-container framing tint. The strategy-gauge marker (`--mk-color`, neutral `#8A94A6` fallback) is read-only data.
- **Game controls** (pause / skip / game-speed, in base + `.pcc-*` cockpit + `#game-controls-strip` layers): choice controls → **neutral** (muted white tokens), differentiated by label, not hue. Were purple / orange / blue (off-law).
- **Part 2 (safe pass):** decorative off-law colours neutralised — the sim-quarter popup divider + scrollbar (`#ff6200` → neutral `#6b7280`, a legacy **light** popup so no gob dark tokens) and the player/play tooltip borders (`#ff6200` → `--white-28`); value-identical neutrals tokenised (`#main-container` `#000` → `--black`, side-panel `.momentum-bar-wrap` divider → `--white-6`, box-score `h3` + `.momentum-bar-value` `#fff` → `--text-100`).
- Verified by `tests/e2e/court-chrome-tokens.spec.js` + `court-chrome-2-tokens.spec.js` + `court-panel-tokens.spec.js` (computed-style guards) + the same five equivalence specs (55).
- **Side panels — gob navy surfaces (Jamie ruling #4, settled 2026-10-01):** the player-stats and team-stats panels moved off opaque legacy greys (`#1a1a1a` / `#222` / `#333` / `#444` / `#555` / `#151515`) to gob **navy surfaces + translucent whites** — `--surface-2` (panel), `--surface-1` (nested team-box + table heads), `--line` / `--line-strong` borders, `--text-60/87/100` text — matching the rest of the app. The team-colour **edge borders** (`.player-stats-panel.away/.home`) and the subtle side tints stay as team identity (annotated `/* colour-law: team-identity */`).
- **Side-panel stat toggles — neutral selected (Jamie ruling #5, settled 2026-10-01):** the selected `.toggle-btn.active` / `.team-toggle-btn.active` is **neutral** (`--white-20` fill, `--text-100`, `--white-28` border), not the panel's team colour. Choice controls are neutral.
- **Court live game-state colours — KEEP as data (Jamie ruling #3, settled 2026-10-01):** this is the documented **game-state** category. The Playcall Center cockpit state colours (armed offense/defense, the "COLOR-CODED ACTIVE BUTTON STATES" block, strategy dials), the playcall **reveal HUD**, the **lower-third** / **secondary-announcement** ribbons, the **active-player HUD** (gold has-ball/defender, `#4caf50` "AUDIBLE!"), the **momentum bars** (red/green/yellow/white direction), and the scoreboard **quarter + shot-clock** gold and **timeout pips** orange are **game-state data representation** — like the Sim-broadcast palette and the RT ramp, they are exempt from the everyday colour law and are **not recoloured**. New game-state colour here is annotated `/* colour-law: game-state */`.
- **Still open:** on-canvas Phaser text (fonts/colours in the Phaser scene JS) — equivalence-locked (`sim-broadcast-fit`, `sim-team-callouts`) and ramp-governed; its own pass.

## 2. Tokens and density

Root element: `html.gob` plus one density class.

`gobDensity.js` `bindGobDensity(root)` requires `.gob` already. It adds `.gob-1920` when the viewport matches `(min-width: 1680px) and (min-height: 1000px)`, otherwise `.gob-1280`.

`.gob` fills the viewport (`100vw` / `100vh`). Token names to use for the shell: `--top-h`, `--rail-w`, `--page-pad`, `--bg-chrome`, `--bg-page`, `--line`, `--line-strong`, `--green`, `--text-100`, `--text-60`, `--text-38`, `--white-6`, `--white-10`, `--white-28`, `--font-display`, `--font-body`, `--dur-hover`, `--ease-out`. Density overrides for `--top-h` and `--rail-w` live on `.gob.gob-1280` and `.gob.gob-1920`.

Consume a token with `var(--token-name)` inside a `.gob` subtree. Do not redeclare the value.

Rules for values that scripts or shared sheets also need (token hygiene, 2026-10-01):

- **A sheet that can be injected into a page without `.gob`** (`css/gob-buttons.css`, `css/rt-buckets.css`) writes `var(--token, same-value)`. The fallback must equal the token; `tests/test_token_mirrors.py` checks it.
- **A script that needs a concrete colour** (canvas, colour maths) keeps the literal next to the token name (`rtBucket.js` `color` / `token`, `POSITION_COLORS` in `matchupsUiShared.js`). The same test keeps the literal equal to the token. For a DOM style, write `var(--token, same-value)` instead (`simGamePresentation.js` `POSC`).
- **`--fs-*`, `--dsp-*` and `--dsz-*` scale with density.** Do not swap a fixed pixel size for one of them on a component that must not grow at 1920.
- The "yours" aliases `--you`, `--you-soft`, `--you-line`, `--you-ink` and the position colours `--pos-*` are tokens. Do not redeclare them in a page sheet.

Fonts are self-hosted. Display face: `/css/fonts.css` (Bebas Neue Pro). Body face: `/fonts/app-fonts.css` (Inter). Do not add a Google Fonts link.

Shell rules that must not restyle existing franchise cards live in `FrontEnd/static/css/gob-shell.css`, scoped under `html.gob-shell`. `gob-components.css` is scoped under `.gob`. If a component class (`.logo`, `.nm`, `.lnk`, `.card`) would change existing franchise markup, tighten the shell selector. Do not edit the old content CSS to accommodate the shell.

### Player headshots are square

A player headshot is a square with a small corner. Never a circle. A circle crops the head to its inscribed disc and throws away the shoulders, which is what made headshots read as too small. This holds everywhere a player's face appears — Roster, Leaders, Player Stats, Player detail, Scouting, Training Report, Recruiting — whether the element carries a photo, a monogram or a placeholder.

The corner scales with the box so every headshot reads the same weight: `--radius-6` on the 28–46px table and list badges (`.gob .av`, `.pool .pc-av`, `.pdg-av`, `.wr-hs`), `--radius-10` on the large portrait (`.gob .portrait`, `.pd-portrait-wrap`). A radius past a quarter of the side is closer to a circle than to a square, so treat that as the ceiling.

Team logos and team initials badges are not headshots. They keep `--radius-logo`. The on-court HUD and the sim's headshot marker are game presentation, not this rule.

## 3. Audio

`uiSfx.js` is the one audio bus. It has two scopes and one stored record (`gob_audio_v1`, `AUDIO_STORAGE_KEY`; the same record works online and in the offline desktop build). The scope is the page.

| Scope | Where | Controlled only from | Shape |
|---|---|---|---|
| `game` | `court.html`: everything on the court screen, a played game and Sim Game alike | The court. The command-center sound control (mute all, music level, SFX level) and the Sound switch in Sim Game, which is the same mute. | `master` / `music` / `sfx`, each a level 0-100 and a mute. Gain is master × channel, 0 when either is muted. |
| `app` | Every other page | Settings: two on/off switches, **Music** and **Sound**. | `app.music`, `app.sound`. No levels, no sliders. |

- Callers ask for a channel (`music`, `sfx`, `ambience`) through `outputVolume` / `channelGain(getAudioState(), ch)` and the bus answers for the scope the page is in. Off the court `music` and `ambience` are the Music switch and `sfx` is the Sound switch.
- **Music** is all non-gameplay music: the franchise track (`musicController.js`), the timeout loop on Set Lineup / Game Plan, the Home Base track, and the lobby track on team select and the persona intro. **Sound** is every non-gameplay sound: UI clicks, Advance, commits and stings.
- The two scopes never touch each other. Settings does not change the court; the court does not change Settings. A record written before the switches existed keeps what the player had silenced.
- There is no other audio control anywhere in the app. Do not add one to a page (the Account page's ambience switch was removed, 2026-10-02).
- Sim Game always plays its highlights (the callout cadence is never suspended). The switch in its footer is Sound, not Highlights.
- Settings uses `getAppAudio()` / `setAppAudio('music' | 'sound', on)`. Sim Game uses `isGameAudioMuted()` / `setGameAudioMuted()`. The court control keeps `setChannelMuted` / `setChannelLevel`, which write the game scope on the court and do nothing to levels elsewhere.

`playSfx(name, baseVolume)` plays one named sound on the `sfx` channel. `baseVolume` defaults to `0.7`. It still accepts a raw filename so existing callers keep working. Named catalog: `SFX_SELECT` (`click-tiny.wav`), `SFX_ADVANCE` (`confirm-1-lowervol.wav`), `SFX_COMMIT` (`click-beep.wav`), `STING_WIN` (`sting-win.wav`), `STING_MILESTONE` (`sting-milestone.wav`), `STING_SEASON_PEAK` (`sting-season-peak.wav`). Short UI sounds may overlap. A new sting stops the previous sting. A missing file fails silently (one `console.debug` per name) and must not throw or block a modal or navigation.

One delegated click listener per document (`installSfxHooks(document)`) plays `data-sfx="<name>"` on buttons, links, and `[role="tab"]`. Unknown names are ignored. The hook skips a disabled control (`disabled`, `aria-disabled="true"`, `.is-disabled`, `.is-dead`) so a dead button never plays a sound. The top-bar Advance (`#play-now`) uses `data-sfx="SFX_ADVANCE"` and must not also call `playSfx` from its click handler.

One sound per action. A control that has a `data-sfx` hook must not also call `playSfx` in its own handler, and vice versa — pick one path (proved in tests with the `window.__gobSfxCalls` spy). `SFX_ADVANCE` is reserved for `#play-now`; a page's own primary action (Submit Training, a tutorial PLAY NOW) uses `SFX_COMMIT`, not Advance. Everything goes through `playSfx` + the settings channels — a caller that constructs `new Audio()` itself bypasses the mute/level settings and is a bug to fix, not a pattern to copy.

Losses are silent, and so is a title the user's team did not win. `STING_WIN` plays only on a win's first showing (the office weekly card, at the score cue); a loss and a milestone elimination make no sound. A gold milestone or season-peak open plays its server-named sting (`playSfx(item.sting)`); a new sting stops the previous one. Stings follow the audio settings even under `prefers-reduced-motion`, and closing a modal early does not cancel or replay the sting. The client never picks a moment's sound — the server names it.

Routed: `playSfx` callers, `data-sfx`, the season-peak and milestone stings, `musicController.js`, the lobby tracks, `gameSfx.js`, and the court's quarter-end airhorn, whistle and timeout sounds (they scale by `outputVolume(base, 'sfx')` when they play). A sound that sets its own `Audio().volume` without asking the bus is a bug: it ignores both the Settings switches and the court control. Do not add a second store.

## 4. Settings panel

Module: `FrontEnd/static/js/shared/gobSettings.js`.

API on `window.GOBSettings`: `open()`, `close()`, `toggle()`, `isOpen()`.

Sections, top to bottom: Audio (two switches, Music and Sound, applied immediately; a line says game sound is set on the court), Stats (only fields `/api/auth/me` already returns; hidden until those fields exist: Career record, Titles, National Titles), Account. Stat tiles size to their content (`.cs-grid` is a wrapping flex row, each `.cs` at least as wide as its text), so a long record widens its tile instead of spilling out of it. The footer shows `window.GOB_BUILD_LABEL` when that string is set, and Online / Offline.

Online: Account shows username, email, a link to account details, and log out. Offline (`window.GOB_BUILD_PROFILE === 'desktop'`): Account is the offline note, the stats are not fetched, and the connection label is Offline.

The gear that opened the panel gets `.open` and `aria-expanded="true"` while it is open. Close with Escape, the scrim, the close control, or the gear again.

## 5. Shell

`gobShell.js` mounts the shell. The Office and every browse page in the table below get the full shell. Flow pages get focus mode. The live court never mounts it.

Grid: `.app` is `grid-template-rows: var(--top-h) minmax(0, 1fr)` and `grid-template-columns: var(--rail-w) minmax(0, 1fr)`. `.top` spans both columns. `.rail` is column 1. `.main` is column 2 and the only scroller (`overflow-y: auto`). `html` and `body` do not scroll.

Top bar, left to right: team logo (existing `#team-logo`, height `var(--top-h)`, width auto, `object-fit: contain`, no crop) with `--dsp-12` of horizontal padding on each side before the divider. Its alt, `title`, and link `aria-label` are the team name. The name is not painted as visible text. The control opens Team › Roster. Then a divider, Record, National Rank, Week. Record text comes from `#fcc-record-label` (standings W-L for the user's team). National Rank comes from `#fcc-rank-label` / `data.rank`, shown as `#N` or `NR`, with the label "National Rank". Week comes from `data.week`. There is no Team RT. There is no alpha badge, product logo, or social link. The build label stays in Settings.

Right side, browse pages: the ghost Edit Recruit Invites button (`#fcc-edit-recruiting`, same show/hide as today) then Advance (`#play-now` with class `advance`). Advance is `gobAdvance.js`. The Office passes its existing helpers into it. Labels, `dataset.mode`, routes, and gating are the same as the Office. A blocking task replaces the label; it does not disable the button or add a hint. Loading text is `STARTING…`. A second click while that class `is-loading` is set is ignored. On a training week, Advance (`dataset.mode=training`, "Run Training" / "Run Training Camp") goes to `/training.html` in focus — the same step pattern as Play Next Game → Set Lineup. After week 26 (`training_disabled_for_postseason` or week ≥ 27) Advance is the tournament game and does not open the training page. Focus mode has no Advance. The page keeps its own green button (`#submit-btn` "Submit Training" on the training focus page; `#play-now` "Play Game" on Set Lineup).

On a browse page that does not already paint `#fcc-record-label`, Record comes from `team_record.wins` and `team_record.losses` on the command-center payload. National Rank still comes from `data.rank`. Week still comes from `data.week`. The Office keeps painting Record from the standings label.

Tier weeks (27-34): when `GOBTierEmblem.tierForWeek(data.week)` returns a tier and `TIER_TOKENS` has `metal` and `metalHi`, `.top` gets `is-tier` and those two custom properties. **A tournament week shows no week number.** The week stat (`#gob-week-stat.ts-tier`) becomes the round descriptor, in the place the week sits: the tier emblem (`#fcc-header-emblem`, the emblem alone), then `#gob-week-value` reading `<Tier> Tournament` over `#gob-week-phase` reading the round. The round comes from `GOBAdvance.eosRoundForWeek(week)`, so it uses the same words as the Advance button (First Round, Semifinals, Championship). After the tournament the week is named, not numbered: week 35 reads `Signing Day` and week 36 reads `Offseason` (no emblem, no round line). Only weeks 1-26 read `Week N`. Nothing sits between the stats and the action button.

The season sits under the week, in the strip's value-over-label pattern (like `11-3 / RECORD`), on every page with the top bar:

| Weeks | `#gob-week-value` | `#gob-week-phase` |
|---|---|---|
| 1-26 | `Week 2` | `SEASON 3` |
| 27-34 | `Conference Tournament` | `FIRST ROUND · SEASON 3` |
| 35, 36 | `Signing Day`, `Offseason` | `SEASON 3` |

- The season is the payload's `current_season` (`syncTop(data)`); with no payload it is read from the Office's `#fcc-season-label`. Unknown season: the line is hidden, never guessed.
- The label never sets the stat's width (`.ts-txt span { width: 0; min-width: 100% }`): the value does, and a longer label runs on into the empty strip. It cannot widen `.top-stats` or move the action button. If the tier module is not loaded yet the bar paints `Week N` and repaints when it arrives.

Rail order: Office, Team, Prep, League, Recruiting, News, then the utility group: Tutorials (`/tutorial.html`), Feedback, Settings, a quieter divider, Exit Franchise. Exit calls the existing `#exit-franchise` handler (same sound, same `/mode-select.html` destination). Feedback is the existing `#feedback-btn` modal and is omitted when `window.GOB_BUILD_PROFILE === 'desktop'`. On a browse page the rail Feedback appears once the auth bar has added `#feedback-btn`, which can be after the shell mounts. Settings calls `GOBSettings.toggle()`.

`.gob-1280`: the grid column stays `--rail-w`. Labels are hidden. `title` tooltips remain. Hover or keyboard focus (`:focus-visible`) waits 400ms, then the overlay face widens from `--rail-w` to 200px in one `--dur-rail` (180ms) `--ease-out` transition. Labels fade in on that same timing. They do not change the face width. Collapse is one motion as well: 120ms after the pointer leaves (or focus clears), the face narrows with `--dur-rail`. The overlay must not change `.main`'s rectangle. `prefers-reduced-motion` makes the change instant. `.gob-1920`: the rail is `--rail-w` with labels visible.

Recruiting carries the existing `.inbox-badge` when `recruitingIsPrompted` is true. That is a presence dot, not a count, and it is neutral (ruling #7). Do not pulse it unless a field already says the recruiting task gates Advance. Turning Advance into the recruiting task is the gating; it is not a pulse signal.

Sub-tabs sit in `.pg-head` (sticky title plus `.subtabs`). Office has no sub-tab row. Recruiting is a rail item that leaves the page: it calls the existing `openRecruitingSurface` (`GOBNav.go` to the recruiting URL the app already builds). On that page the row is Pool, Leans, and Visits. On the Office, link sub-tabs call `GOBNav.go` with the href the page already built. On a standalone browse page, a link sub-tab uses `GOBNav.replace`: an Office tab goes to `franchise-command-center.html?tab=<id>`, and a link sub-tab goes to that standalone page. Recruiting's own Pool, Leans, and Visits stay on `recruiting.html` and do not use `GOBNav.replace`. Rail section clicks on a standalone page `GOBNav.go` to that section's first Office tab (or to recruiting). There is no Players | Team toggle.

Focus mode (`html.gob-focus`): the top bar only — logo, Record, National Rank, Week, and the Settings gear at the right (`#gob-focus-settings`). No rail. No Advance. The settings host anchors at `left: 0` and `top: var(--top-h)`. The page's own primary action and its exit or back control stay, including `exitFlow` back to the locker room.

Player and team pages highlight the section in `return_tab` or `return_url`. If those are absent, the user's own team is Team and a different `team_id` from `user_team_id` is League. No sub-tab is active. A back control that goes up a level (player to team, bracket to standings) stays. A back control that only returned to the locker room is hidden, because the rail replaces it.

Box score is browse when `return_url` is set, and focus when `from` is `lineup` or `game-plan` or neither param is set (the end-of-game open). **Every link that opens a box score to read it carries `return_url`**: Team › Schedule results, League › Schedule "Box score", a bracket score, the Office weekly card's "Box score", a News game result, Practice Squads (`data-return` on the anchor, or built into the href). That is what tells the page it is a read: `box-score.js` runs the closed-game guard (`GOBNav.guardClosedFranchiseGame`) only when there is no `return_url`, because the guard sends a final game that is the franchise's last game back to the Office once the week has moved on, which is exactly last week's result. A link without `return_url` to last week's game lands on the Office. Back on a browse box score returns to the tab named in `return_url` (the Office when it names none). Recruiting is focus for `action=run`, for weeks 20–26 before this week's invite board is submitted, and for week 35 before orders are submitted. Other hub views are browse.

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
- In-app flows (Play Game, Run Training → `/training.html` focus, and the other Advance routes) still return to the locker-room entry via `exitFlow`. That collapse is separate from the section stack.
- `exitFlow` jumps back to the locker-room index that launched the flow. In-app Back uses `history.back()` only when the previous entry is that parent.
- `warnOnLeave(hasEdits, { view, confirm })` registers an unsaved-edit check. `hasEdits` compares the current values with the last saved ones, so moving a control and moving it back is not an edit. A plain boolean "touched" flag is not enough. `CommandCenterTabs.show` asks `confirmLeave(proceed, view)` before it leaves `view`; with real edits the owner's `confirm` opens the in-app `GOBLeaveConfirm` and `proceed` runs after Discard or a landed Save. Its layout is its own (`.gob-leave-confirm .lc-*` in `gob-components.css`): the save across the top (the only orange), then Discard Changes and Keep Editing side by side as two equal neutral buttons; Keep Editing has focus, and Escape or the backdrop is Keep Editing. The root keeps `gob-modal-overlay` so the focus shell leaves it as a viewport layer. `go`, `replace`, `back`, and same-origin link clicks ask every check the same way. The browser's own `beforeunload` prompt fires only for a reload or a window close with real edits. The weekly training focus page (`/training.html`) registers a confirm: the allocation draft still persists, but leaving with a dirty form opens `GOBLeaveConfirm` (Keep Draft / Discard / Keep Editing). Prep › Player Training has no leave confirm — per-player settings save on change. A Back or Forward `popstate` is not guarded.

Old `?tab=` values still open the matching section and sub-tab. `schedule-tab` opens Team › Schedule (`team-schedule-view`). `fcc-team-stats-summary-tab` is League › Team Stats. `recruits-tab` opens Office (`home-tab`). Each tab's `onTabShow` lazy-load still runs.

The shared tab module also serves any other command center that calls `initCommandCenterTabs`. Button clicks there stay on `replace`. Do not make those clicks push.

## 7. Section map

| Rail | Sub-tab | Opens |
|---|---|---|
| Office | (none) | `home-tab` |
| Team | Roster | `roster-view` (in-page module view; `team-roster-view.html` redirects here and keeps `franchise_id`, `team_id`, `roster_team_id`, and return params). `?tab=roster-tab` opens this view. |
| Team | Player Stats | `player-stats-view` (in-page module view). `?tab=player-stats-tab` opens this view. |
| Team | Team Attributes | `team-attributes-view` (in-page module view; `team-traits.html` redirects here and keeps `franchise_id`, `team_id`, and `week`). `?tab=team-stats-tab` opens this view. |
| Team | Schedule | `team-schedule-view` (in-page module view). `?tab=schedule-tab` opens this view. Four week columns (1–7, 8–14, 15–21, 22–26), with the three tournament labels under 22–26 and the user's EOS games listed under each label when present. Two columns below 1100px. The bracket stays on League › Tournament. |
| Prep | Player Training | `training-view` (real module: `training.js` `init(root, { sections: 'player-dev' })`). Per-player development settings only — each player's position and development focus (the Player Development grid and its editors). No allocation sliders, Coaching Focus, or Submit. One neutral line: "Weekly training is set when you advance." The underline tab replaces. `?tab=training-tab` opens this view. Weekly training is not this tab: Advance ("Run Training" / "Run Training Camp") opens `/training.html` in focus (`init(root, { sections: 'weekly' })`, the same module). That page holds Player Drills / Scheme Installs / Full Team Sessions, points + requirements, Auto-Train, Training Plays, Coaching Focus, Player Development (the same editors as this tab, as cards under Coaching Focus) and Submit Training. Submit lands on `/training-report.html` in focus (same chrome as Set Lineup / weekly training), then Office. After week 26 Advance is the tournament game and skips `/training.html`. Tutorial (`training.html?mode=tutorial`) stays on the file in focus and shows the weekly sections. The Training Report is not an FCC tab: `/training-report.html` hosts `training-report.js` `init(root)` in focus. Old `?tab=training-report-view` and the redirect stub remap to that page. The FCC summary panel stays in the page and is no longer opened by the shell. |
| Prep | Game Plan | `game-plan-view` (real module: `game-plan.js` `init(root)`; `game-plan.html` redirects here). `?tab=game-plan-tab` opens this view. `game-plan.html` with `resume_from_timeout=true` or `mode=tutorial` does not redirect and stays focus, with no rail and no underline row. |
| Prep | Playbooks | `playbooks-view` (real module: `playbooks.js` `init(root)`; `playbooks.html` redirects here). `?tab=playbooks-tab` opens this view. `playbooks.html` with `mode=tutorial` does not redirect and stays on the file (browse chrome). |
| Prep | Scouting Report | `scouting-view` (in-page module view). The underline tab replaces. |
| League | Standings | `standings-view` (in-page module view; `standings.html` redirects here and keeps `franchise_id`, `team_id`, and return params). `?tab=standings-tab` remaps here (`canonicalTab`); the old panel is gone. |
| League | Rankings | `rankings-view` (in-page module view; `rankings.html` redirects here and keeps `franchise_id`, `team_id`, and return params) |
| League | Leaders | `leaders-view` (in-page module view; `leaders.html` redirects here). `?tab=awards-tab` still opens the old panel. |
| League | Team Stats | `team-stats-view` (in-page module view; `team-stats.html` and `stats.html` redirect here and keep `franchise_id`, `team_id`, and `week`). `?tab=fcc-team-stats-summary-tab` still opens the old panel. |
| League | Schedule | `league-schedule-view` (in-page module view; `schedule.html` redirects here and keeps `franchise_id`, `team_id`, `week`, and return params). |
| League | Tournament | `tournament-view` (in-page module view). `brackets.html` redirects here. Before week 27 the control is disabled: same shape, `--text-38`, `not-allowed`, not focusable, title `Opens Week N`. |
| Recruiting | Pool, Leans, Visits | `recruiting.html?hub=pool\|leans\|visits` via `openRecruitingSurface` / `GOBNav.go` from the rail (`franchise_id`, `team_id`, `from=fcc`, `return_url`). The sub-tab replaces `hub` on that same document. The name search sits in `.pg-tools` as `.gob-search` ("Search name…", `/` to focus). Weeks 20–26 hide Pool, Leans, and Visits: the invite stack (calendar, board, then the pool) is the page, with a neutral "Recruit pool below" callout that scrolls to `#hub-pool`. Weeks 1–19 and 27–34 keep the three tabs. Weeks 35 and 36 hide the row; the sign board or the results list is the page. Week 36 results: "Your class" first, then every conference as one full-width card in the server's order (yours, its sister, then 1–16), its eight teams in two rows of four, highest class score first (the signed recruits' RT summed, the number the Signing Day boards finish on); a team that signed nobody still has its place. Focus mode hides the head, including the row. An old `?tab=recruits-tab` deep link opens `home-tab`. |
| League | Practice Squads | `practice-squad-view` (in-page module view). The regional practice-squad league: every region's squads. `practice-squad-standings.html` and `practice-squad-bracket.html` redirect here. The user's own practice squad is the Varsity / Practice Squad segment on Team › Roster. |
| News | News | `news-view` (in-page module view; `news.html` redirects here and keeps `franchise_id`, `team_id`, `story`, and return params). `?tab=press-tab` opens this view. |
| News | Awards | `awards-view` (in-page module view; `awards.html` redirects here and keeps `franchise_id`, `team_id`, and return params) |

History is not a section.

The page h1 is the only title. There is no second "Recruiting Hub" heading and no outer card around the hub. The phase strip is the first content, 8px under the row hairline. Pool, Leans, and Visits do not show a Recruit Pool jump. Signing Day keeps the Recruit Pool / My Orders switch, because My Orders replaces the pool.

The Pool / Leans / Visits row, the search and the top-bar identity are not painted until the hub has its data (`RecruitingHub.ready()`), because the week decides whether there is a row at all. Until then the page is the title and a still skeleton (`.hub-skel` in `recruiting-spine.css`); the row then arrives in the same paint as the hub.

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

**UI tokens (required):** colour-law `--strict` on new-design files (see the Colour law section for the full clauses). Legacy pages are reported and do not fail the gate. New-design surface is: shell HTML (`gob-shell` / `gob-focus`, or a page in `gobShell.js` PAGES), `css/gob-*.css` except `css/gob-advanced.css` (advanced-topic teaching diagrams), the tutorial / FTE CSS (see Tutorials and FTE), the Chapter 7 chrome (`css/office-home.css`, `home-base.css`, `milestone-modal.css`, `season-peak.css`, `trophy-case.css`), the recruiting-hub CSS (`recruiting-spine.css`, `recruiting-dock.css`, `recruiting-signing.css`, `recruiting-results-hub.css`), `js/shared/gob*.js`, and `js/shared/views/**`. `css/gob-tokens.css` is the token source and is not scanned; everything else is legacy. Annotate a legal exception with `/* colour-law: positive-data | committed | saved | reward */`.

`--strict --no-write` (summary only, no `reports/ui-token-audit-*.md`) is a **CI gate** — a sibling job to the migration gates in `.github/workflows/test.yml`. Run it before merge:

```
.venv/bin/python scripts/check_ui_tokens.py --strict --no-write
```

## 9. Browse and focus pages

| Page | Mode | Section | Sub-tab |
|---|---|---|---|
| franchise-command-center.html | browse | per tab | per tab |
| recruiting.html | browse, or focus while that week's invites, Signing Day orders, or `action=run` are the task | Recruiting | Pool, Leans, or Visits (`hub`). The row is hidden on Signing Day and Results, and while focus hides the head. |
| rankings.html | redirect to `franchise-command-center.html?tab=rankings-view` | League | Rankings |
| schedule.html | redirect to `franchise-command-center.html?tab=league-schedule-view` | League | Schedule |
| practice-squad-standings.html | browse | League | Practice Squads (`practice-squad-view`; the file redirects) |
| practice-squad-bracket.html | browse | League | Practice Squads (`practice-squad-view`; the file redirects) |
| brackets.html | browse | League | Tournament (`tournament-view`; the file redirects) |
| awards.html | redirect to `franchise-command-center.html?tab=awards-view` | News | Awards |
| news.html | redirect to `franchise-command-center.html?tab=news-view` (`story` is kept) | News | News |
| leaders.html | browse | League | Leaders (`leaders-view`; the file redirects) |
| standings.html | browse | League | Standings (`standings-view`; the file redirects) |
| team-stats.html | redirect to `franchise-command-center.html?tab=team-stats-view` | League | Team Stats |
| stats.html | redirect to `franchise-command-center.html?tab=team-stats-view` | League | Team Stats |
| team-traits.html | redirect to `franchise-command-center.html?tab=team-attributes-view` | Team | Team Attributes |
| game-plans.html | redirect to `tutorial-game-plans.html` | — | — |
| scouting.html | redirect to `tutorial-scouting.html` | — | — |
| player-attributes.html | redirect to `tutorial-player-attributes.html` | — | — |
| team-attributes.html | redirect to `tutorial-team-attributes.html` | — | — |
| index.html | redirect to `homepage.html` | — | — |
| player-detail.html | redirect to `?tab=player-view` unless `recruit_id` or `mode=recruit` | return context | none |
| team-roster-view.html | redirect to `roster-view`, or `team-view` when `roster_team_id` is set | Team or League | Roster or the team drill-in |
| box-score.html | browse when `return_url` is set; otherwise focus | League when browse | none |
| training.html | focus | — | — |
| training-report.html | focus | — | — |
| game-plan.html | browse, or focus when `resume_from_timeout=true` or `mode=tutorial` | Prep | Game Plan (`game-plan-view`; the file redirects except in focus; same `init(root)` as the in-app module) |
| playbooks.html | browse | Prep | Playbooks (`playbooks-view`; the file redirects except `mode=tutorial`; same `init(root)` as the in-app module) |
| set-lineup.html, training.html, training-report.html, training-squad-report.html, training-playbooks.html, cut-players.html, playbook-report.html | focus | — | — |

A `.gob-modal-overlay` on a focus page stays a viewport layer (`position: fixed`, `--z-modal`) above the focus top bar. `adoptMain` does not move overlays into `#gob-main` — `.gob .main>*` would otherwise drop them to `position: relative` and they would render under the chrome. Week-1 `/cut-players.html` is practice-squad assignment (`#cut-players-view`, tokens + `cut-players.css`): the primary button is "Assign Practice Squad" as `.gob-btn--action` (committed orange — it saves assignment and returns to the FCC hub; it is not the single green Advance). It is disabled until the selected count equals `cut_count`; a disabled control uses the dead treatment (`--text-38`, `not-allowed`) and shows the reason next to it ("Assign N more to the practice squad" / "Remove N"). Week-35 `mode=cut` / **Submit Cuts** was removed from the frontend (2026-09).

`/box-score.html` uses `html.gob`, `#box-score-view`, and tokenized `box-score.css`: browse when `return_url` is set, focus post-game otherwise. Tables use `.rtab` / gob-table styling; player-name column sticks on horizontal scroll. User W/L is a white outline plate (`#user-game-wl-plate`), never win-green / loss-red. Scouting EV lines and non-data cells stay neutral; green is reserved for positive attribute-change data (`.attr-chip.up`). POTG headshots use the large portrait corner (`--radius-10` at 72px).

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
| `team_snapshot.moved_most` | Up to two `{measure, value, delta}` rows. Delta is this week's stored measure minus the previous snapshot. Empty until a prior snapshot exists. The server ranks over all stored measures, so a `momentum_score` row can appear here; the Office drops it in `officeHome.js` before the top-two render, so Momentum is never shown (matching Team Attributes and the Training Report Team Report). |
| `result` | Last completed user game, or null. Scores, site (`home` / `away`), `neutral` (always null; no stored neutral site), opponent rank, round name for weeks 27–34, POTG on a win or the user's highest-PTS player on a loss, box-score path and params. `headline` only when a `season_news` story stores this game's id. `result_key` is the game id: a stable id per result so the weekly entrance plays once. "Seen" is the client's own local state; the server stores none. |
| `next_game` | Opponent, rank, record, conference, site, week, top scorer, top rebounder. `conference_position` and `conference_size` are the opponent's 1-based place in its own conference and the number of teams there, using the Standings order. Both are null when the opponent cannot be placed. `date`, `neutral`, `projected_starting_five`, `seeds`, `stakes`, and `team_rt` are null. |
| `conference_standings` | The user's conference in Standings order. `conference` is the conference number, `region` is the stored region or the letter derived from that number (1–2 = A … 15–16 = H), and `rows` are `{team_id, team_name, wins, losses, differential, position, is_user}`. Ties follow `standings_display_sort_key` (wins, then point differential) and match `GET /franchise/standings` for the same results. Null when the user has no conference. |
| `todos` | `{id, label_key, required, done, gates_advance, is_advance_action, route}` from the same flags as `gobAdvance.js`. A blocking task is the Advance action. |
| `recruiting_wire` | Status line, events (`recruit`, `position`, `stars` and `filmed_grade` always null, `event_type`, `event_text` from the stored lean-event sentence, `event_detail`, `list_position`, `direction`), `pending_count`, `urgent`, `unseen_count`. |
| `signing_day` | Week 35 only. Points remaining out of 50, playing-time promises, open roster spots, up to three targets. Otherwise null. |
| `signed_class` | Week 36 only (running Signing Day moves the franchise from 35 to 36), once the hub reveal has played (`week_35_reveal_seen_season`). `{recruits: [...]}` from `class_signed`: every non-walk-on who signed with the user's team; an empty list when none did. Otherwise null. |
| `season_preview` | `first_week` only. Preseason rank is the current national rank. Conference projection, team RT, returning starters, and top returner are null. Newcomers only when `pending_walk_on_welcome` is stored. Opener is `next_game`. |
| `weekly_card_items` | WEEKLY-tier moments from the server moment queue, in order. Every item includes an `href` (the archetype row's is omitted on desktop, where the coaching-archetypes page is not served). The Office paints them with the existing card helper as links. They are not pop-ups. |
| `also` | The highest-priority weekly item as `{kind, title, line, href}`, or null. The weekly card's one folded-moment row. `weekly_card_items` stays the full list. |

`GET /franchise/command-center/data` also returns `moments`, `moments_for_this_visit`, and `weekly_card_items`. The browser does not rank, cap, or pick which moment opens, and it does not decide a moment's style or sound. MILESTONE-tier items play through one `.mm` template (`js/shared/milestoneModal.js`): gold items rise and play the server `sting`; elimination is quiet (fade only, no gold, no sound). `×` / Esc leaves the rest of the visit list for the next open. Seen PATCHes and championship-moment consume fire when the overlay mounts (shown), not when Continue is clicked, so Box score / rail / reload / tab close cannot re-show the same item. Unshown items stay eligible. `BackEnd/utils/moment_queue.py` builds the list from existing eligibility flags; `BackEnd/utils/season_moments.py` derives the three newer payloads at route level from the brackets, the season snapshot reader and the week-35 signings.

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

Cap: a season peak shows alone. When one is eligible the visit is the season-peak items only, and a championship plus its review are the one pair that shows together — exactly `[championship, season_review]`, as "1 of 2 / 2 of 2". Otherwise `moments_for_this_visit` is the first pop-up-tier item, plus a second only when the first is `duration=short` and the second is MILESTONE or SEASON PEAK. Remaining pop-up-tier items stay in `moments` (still eligible next visit; seen keys and championship consume are marked when the overlay mounts, not on Continue). WEEKLY items go to `weekly_card_items` and never take a pop-up slot.

A `championship` row is gold with `STING_SEASON_PEAK` only when at least one of its moments has `user_is_winner`. Another team's title is an announcement, not the coach's reward: the row is `style: quiet` with no sting, and the takeover (`.pk.is-quiet`) drops the confetti and the "Added to your Trophy Case" line. The same rule holds on the court's live-game overlay.

The command-center payload has no `franchise_id`, and the page's own `franchiseId` is script-scoped, not a window property. `momentQueue.js` reads the id from `window.FranchiseContext` for every consume and seen write. Without it those writes were skipped and each moment replayed on every Office visit. A test mock of this payload must not add a `franchise_id` key.

`recruiting_results_modal` is not queued as itself: the live Signing Day beat stays the week-35 hub reveal, and the Office's one-time summary is `signed_class`, which reuses that modal's `recruiting_results_modal_seen_season` stamp. Elimination and the review add the only new stored fields, `elimination_seen_season` and `season_review_seen_season`, written by `PATCH /franchise/elimination-seen` and `PATCH /franchise/season-review-seen` in the same season-stamped style as the existing modal flags.

The first-archetype reveal is marked seen in two places, one per build. Online the flag is on the account: `PATCH /api/auth/archetype-reveal-seen`. The offline build cannot reach `/api/auth` (always remote; loopback does not serve it), so there the client sends `PATCH /franchise/archetype-reveal-seen` with the `franchise_id`. That writes `archetype_reveal_seen` on the save's `local_coach` doc (the doc `_coach_archetype_signals` reads) and bumps the franchise's `browse_rev`, so the next command-center read is not a 304 of the body that still had the moment. The route refuses a principal that is not the local owner. `archetype_evolution_pending` (the "Coaching archetype" weekly-card row) has the same pair: the account's `PATCH /api/auth/archetype-evolution-seen`, and offline `PATCH /franchise/archetype-evolution-seen`, which removes the key from `local_coach` (removed, not set to `""`: a projected SQLite read of an empty-string field raises) and bumps `browse_rev`. A weekly row never pops, so nothing in the queue marks it: offline, `momentQueue.js` sends the write when the Office is the panel on screen for the authoritative read, so the row shows for one Office visit. Online nothing sends the account write today, so the row stays until the next evolution replaces it.

Cut-players (blocking) and tutorial return alerts stay outside the queue. The cut-players modal ("Trim Your Roster to Size") has one action, so it is a full-width ghost (`gob-modal-btn-dismiss`), not green: the green on that screen is the top-bar Advance. Tutorial alerts settle first. The queue plays next. The cut modal waits for both.

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
- Every request the store sends is `cache: 'no-store'`. The store is the cache; the browser's HTTP cache must not sit under it. Leaving a flow is a history traversal (`exitFlow` → `history.go`), and on that kind of load the browser answers a plain GET from its HTTP cache without revalidating. The week-completion writes have just cleared the store's ETag, so the Office read after a game came back as the pre-game body and never reached the server (the "refresh to see the new week" bug, 2026-10-02). Do not remove the mode, and do not read a browse GET with a bare `fetch` from a page that has no store. Request routing in Playwright turns the HTTP cache off, so only a real server can reproduce this (`polish-flow-bugs.spec.js` A1 runs one).
- The body is also written to `sessionStorage` under `gob-store:<franchise_id>`, inside try/catch. Bodies larger than about 1.5 MB are kept in memory only. If `sessionStorage` throws, the request still completes.

The ETag is `franchise:season:week:browse_rev:BUILD:signature`. The store remembers the newest season, week, revision, and build it has seen for that franchise. A greater season, a greater week in that season, a greater revision in that week, or a different `BUILD` drops every cached body for that franchise. A newer revision means any cached route may be stale, because every franchise write bumps the revision.

`GOBStore.mutate(url, options)` is the write wrapper. `window.fetch` sends POST, PUT, PATCH, and DELETE on `/franchise/`, `/api/gameplan`, and `/api/playbooks` through it. After a successful response it clears that franchise's memory and `sessionStorage`. The next GET is a full read and picks up the new revision. A flow page that navigates away after a write does not have to do anything else.

Cached routes are the browse GETs: command-center, standings, schedule (including national), leaders, team-stats, team-player-stats, player-stats, team-data, news, recruiting-data, recruiting-results, practice-squad, tournament brackets, awards, scouting-report, roster, player, player-detail, team-detail, recruit, teams, game plan, and playbooks.

**The list is also what attaches the session.** A route on `BROWSE_PREFIXES` gets the `Authorization` header and the ETag; a route that is not is a plain uncached request (it now carries the header too). A new `@browse_cached` route must be added to `BROWSE_PREFIXES` in the same change. League › Tournament shipped without its entry: the tab sent no session, the hosted server answered 401, and the tab showed "Tournament could not be opened." in every tournament week. Stubbed specs and the offline engine do not check the header, so neither caught it: a view's spec must refuse a request with no `Authorization` header (`tables-followups.spec.js` does), and the route's own test must run the real auth dependency (`test_tournament_browse.py`).

Never cached: `GET /api/game/{id}`, `POST /api/simulate-quarter`, `/api/auth`, and any URL with `profile=1`. `profile=1` is only added when the page URL has `cc_profile=1`.

`ResourceCache` (the old season+week `sessionStorage` copy) always misses. Do not add a second cache in a page.

A new browse view calls `GOBStore.get` or plain `fetch` (the store wraps `fetch` for the routes above). A new franchise write uses `fetch` or `GOBStore.mutate` so the franchise cache is cleared. Do not read `sessionStorage` for a browse body yourself.

The Office does not call `GET /franchise/state`. Season counting stats for the user's roster are `players[].stats.season` on `GET /roster/{teamId}` in franchise mode, copied on read from `franchise_players_data.season`.

## 12. Office

The home tab of `franchise-command-center.html` is the Office (`.office` inside `.main`). It has no page title and no sub-tab row. `js/shared/officeHome.js` paints it from `office_digest` only. Grouping and sorting attribute changes for display is allowed. A null field is omitted. The page does not substitute another payload, and it does not write "N/A". WEEKLY moments from `office_digest.weekly_card_items` use the existing card chrome in the This Week column. Pop-ups come from `moments_for_this_visit` through `js/shared/momentQueue.js`. MILESTONE-tier kinds open the shared `.mm` template (`js/shared/milestoneModal.js`). Championship stays on `ChampionshipMoments`. `season_review` waits for the season-peak template. WEEKLY kinds stay on the weekly card. The 300-retry Big News wait loop is not part of the Office flow.

The Office fills `.main` edge to edge inside the standard page padding (`--page-pad`). There is no 1664px cap. At a viewport of 2400px or wider the Office caps at 2200px and stays centred. The collapsed rail still overlays the page on hover. The Office does not reserve space for that overlay.

While the digest is absent the page shows a skeleton strip and three skeleton cards. There is no spinner.

A week strip sits under the top of `.main`, above the columns. It is one row, about 56px tall at the 1280 density and 64px at 1920. It does not repeat the week number. The top bar already shows it. Each `todos[]` entry is one step, in order, joined left to right. Labels use the same copy as before. An `is_advance_action` step that is not done copies the top-bar Advance label and does not add an ADVANCE tag. The only Advance button on the page is the green top-bar control. A gating step that is not the Advance action has a strong neutral outline and no tag (the BLOCKS ADVANCE tag was removed, 2026-10-02). Every step uses the same padding. The status circle sits at least `--dsp-8` in from the left edge of the pill at both densities. Steps size to their labels. If the row is wider than the page, the gap between steps comes down before the labels do. Labels are not truncated. The strip does not scroll and does not wrap to a second row.

| Step | Rule |
|---|---|
| Done | Check mark, opacity 38%, still clickable. Opens `route`. |
| Next | The first not-done required step. Neutral bright outline (`--text-100`). Green stays on the top-bar Advance only. If this step is `is_advance_action`, its label copies the top bar and the click runs the same action. |
| Blocking | `gates_advance` on a step that is not `is_advance_action` draws a neutral strong outline (`--white-62`). No tag. Never orange (batch 2). |
| Upcoming | The remaining steps. |

| State | Column 1 · Since last week | Column 2 · This Week | Column 3 · Recruiting |
|---|---|---|---|
| `win`, `loss`, `regular`, `tournament` | Result · What moved | Next game · Team snapshot · Conference standings | Recruiting wire. The column heading is the link to the recruiting hub. No events: "No recruiting movement this week". |
| `first_week` | Season preview | Next game · Team snapshot · Conference standings | One-line wire. The digest status when it is set, otherwise the empty-state line. The column heading is the hub link. |
| `signing_day` | Result · What moved | Team snapshot · Conference standings (`next_game` is null) | Signing Day card. The wire is hidden. The column heading still links to the hub. |
| any, with `signed_class` set (week 36) | as that state | as that state | Signing class card (`.office-class`): one row per signed recruit, name, position, home region, RT now → ceiling. It replaces the wire. |

The three columns are equal width. The column gap is `--dsp-12` (12px at the 1280 density, 14px at 1920) between the heading and the first card and between stacked cards, so Result and What moved, Next game and Team snapshot and Conference standings, and the recruiting column all share one rhythm. The wire card is as tall as its rows. "Recruiting →" opens the recruiting hub. Result team names wrap, and at the 1280 density the score is smaller so a long name is not cut off.

| Component | Digest fields |
|---|---|
| Week strip | `todos[]` `label_key`, `done`, `required`, `gates_advance`, `is_advance_action`, `route`. No week label and no ADVANCE tag. |
| Result | `result` scores, names, `opponent_rank`, `site`, `round_name`, `user_won`, `headline`, `leader`, `leader_role`, `box_score`. The user name is prefixed with `#` plus `what_moved.national_rank.now` when that rank is set. No team monograms. |
| What moved | `what_moved.national_rank`, `conference_standing`, `record`, `streak`, `attribute_changes` |
| Recruiting wire | Deduped `recruiting_wire.events`. One row per `recruit_id`, or per name when the id is missing, keeping the latest event. Every row is two lines with the same padding: the name in semibold and the position dimmed on the first line, `event_detail` on the second (or `event_text` when `event_detail` is null). There is no list-position column. A direction arrow stays on the right when `direction` is up or down. At most 8 rows at the 1280 density and 12 at 1920, and only whole rows that sit above the fold. The column heading opens the hub. Rail badge uses `pending_count` and `urgent`. |
| Next game | `next_game` opponent, `rank` as `21. Name` in upright Bebas, `record`, `Conference` plus the short label and `(place of size)` from `conference_position` and `conference_size`. The place is omitted when either is null. No week callout and no monogram. |
| Team snapshot | `team_snapshot.chemistry` (red 0–8, yellow 9–16, green 17–25), five equal attitude columns, `moved_most`, `state` |
| Conference standings | `conference_standings.rows` under Team snapshot. Header is `Conference` plus the short label plus `standings` (`Conference A2 standings`), with "Full standings" always in the card header, to League › Standings. **Every team of the user's conference is shown, in the server's standings order (ties included): never sliced to a window, never tightened to fit.** Each row is the place (`--text-38` tabular), the team's mark as the league tables draw it (`GOBTables.markHtml`) and name (`--fs-13` semibold), and W-L in the display face at `--fs-22`, at the same row padding as a players-to-watch row, at every density. The W-L header sits in the same column as the numbers, right-aligned. The user row uses the navy selected-row treatment. The card does not read the density class, so it cannot be caught by a late `.gob-1280` / `.gob-1920`. On a window too short for the middle column the Office is taller than the fold and `.main` scrolls (the Office chain is `flex-shrink: 0`): at 1280×720 by about 200px on a game week, at 1920×1080 by about 75px. |
| Signing Day | `signing_day.points_remaining`, `points_total`, `promises_made`, `open_roster_spots`, `targets` |
| Signing class | `signed_class.recruits[]`: `name`, `position`, `home_region`, `rt_now`, `rt_potential`. The header counts them (`4 signed`). An empty list reads "No recruits signed with your program." The ceiling is shown only when it differs from the grade now. |
| Season preview | `season_preview` fields that are non-null. The opener is the next-game card. |

Attribute changes are one row per `player_id`. The player name stays on the left and links to the player page. Chips are right-justified: the rightmost chip meets the card's right content edge, and the others sit to its left with a consistent gap. If they do not fit on one line they wrap, still right-aligned, under the name. A chip shows the attribute abbreviation in Bebas at `--fs-22` and `--text-100` (larger than the player name, the largest text in the chip), the new first-digit value in the tier colour from `attributeDisplay.js`, and a green ▲ or red ▼. Chips are not truncated. The previous value is not shown. The chip `title` is the full name from `ATTRIBUTE_NAMES` (`BH` → "Ball Handling"). Players sort by total absolute movement, then name. Inside a row, increases come before decreases. At 1280 the card shows up to 5 players. At 1920 it shows up to 8. When the list is longer, "All changes →" opens `/training-report.html` in focus for `result.week` (or `next_game.week` when there is no result). Rank, conference, and record tiles omit the delta chip when the delta is 0 or null.

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

The Office stays a panel already in the page. Roster, Player Stats, Team Attributes, Team Schedule, Standings, Rankings, Leaders, Team Stats, League Schedule, News, Awards, Game Plan (`game-plan-view`), Playbooks (`playbooks-view`), and Player Training (`training-view`) are module views. The Training Report is not an FCC tab. `/training-report.html` hosts `training-report.js` `init(root)` in focus (no rail, no Prep sub-tabs) — the same module, no `embed=1` fetch, no DOMParser, no IIFE. Submit Training, Office "All changes →", News drill-ins, and old `?tab=training-report-view` all land there. Exit is "Continue to Office" after submit, or "Back to Locker Room" from Office/News (Back returns to wherever the player came from). Game Plan mounts `game-plan.js` `init(root)` into `#game-plan-view` the same way — no `game-plan.html?embed=1` fetch, no DOMParser, no IIFE. `game-plan.html` still redirects here except `resume_from_timeout=true` and `mode=tutorial`, which stay on the standalone file in focus (no rail). Playbooks mounts `playbooks.js` `init(root)` into `#playbooks-view` the same way — no `playbooks.html?embed=1` fetch, no DOMParser, no IIFE. `playbooks.html` still redirects here except `mode=tutorial`, which stays on the standalone file (browse chrome). Player Training mounts `training.js` `init(root, { sections: 'player-dev' })` into `#training-view` the same way — no `training.html?embed=1` fetch, no DOMParser, no IIFE. That tab is player-development settings only. Weekly allocation lives on `/training.html` in focus (`init(root, { sections: 'weekly' })`, including `mode=tutorial`). A module view is the same kind of panel, loaded the first time it opens and left mounted so the next open is instant. The old Roster and Team Measures panels remain in the page. `?tab=roster-tab` and `?tab=team-stats-tab` open the new views. An old Standings, Leaders, or Team Stats `?tab=` still opens the old panel. Team › Schedule reads `GET /franchise/team-detail`. League › Schedule reads `GET /franchise/schedule/week` (`@browse_cached`, one week). The whole-season national route stays for other callers. The next-game row on the team schedule is a neutral tint with a 2px neutral marker on its week cell. Navy (`.gob-game.me`) is only the user's game on the league week, the same mark the Office uses for the user's team. The league week is four equal columns of compact game cards (two below 1100px). A card is the away line, the home line, and a quiet footer. Each line is the logo, the rank only when it is 1–25, the team name (ellipsis, never wraps), and the score. The winner's line is full white and the loser's is `--text-60`. The footer is the tournament context, or Final or Scheduled, and a quiet Box score link on played games. An unplayed regular-season game has no footer (no "Scheduled"). Region Tourney R1 (week 30): `GET /franchise/schedule/week` also returns `byes` (`{team, region, is_user, tournament_context}`, region order) and a `region` on each game; a bye is a card in the same style, the team over "Bye", and the week reads region by region, A to H (the server decides who has a bye: in a region `final`, in no `round1`). The week stepper, the round title, and the empty lines are unchanged. The team schedule is four equal mini-tables of weeks, so the whole regular season fits 1280×720. Each row is Week, Site (vs/at), then logo and "#rank Opponent" with the record on a quieter second line, then the result. The result ("W 75-65") is itself the box-score link; future games leave it empty and show no time.

League › Standings always shows the whole league: eight regions stacked, each with its two sister conferences side by side, the user's region first and the user's conference on the left. Width is read from the cards, not the window: a card under 640px drops DIFF and its pill, and a region row under 1060px stacks its two cards (DIFF then has room again). It has no Conference / Region / National segment; the only tool is the search. Standings, Rankings, Team Stats and Player Stats space their columns by stat family (Styleguide, Tables). League › Rankings is one T1 card, "National Rankings", in the Standings treatment: `#`, Team (logo and name), W, L, PF, PA, Last Week (the W/L mark in the `.gob-wl` data colours, then the stored line), Next. The user's row is navy (`tr.me`). Top 25 / All 128 is a neutral segment in the page-head tools (`gob-view-rankings-show-all`). The payload has no previous rank, so there is no movement column. League › Leaders keeps the Conference / National segment. The full list sits under a `.gob-dt-bar` with "← Leaders", which returns to the boards. Each board shows the top 10 on National and the top 5 on Conference; the board request's `limit` matches. League › Team Stats is one compact T1 table that fits `.main` at 1280 and 1920. It has exactly one header row, which pins under the page head on scroll; there is no group band and no repeated header row. The group names are the header `title`, and the shaded groups keep their shade. A Conference / National segment (`gob-view-team-stats-scope`, default National) sits before the search. Conference requests `GET /franchise/team-stats?scope=conference`, which the server filters to the user's conference.

News reads `GET /franchise/news` (`@browse_cached`). `news` is `season_news` as stored and `dispatches` are your-team rows from `latest_training` and `season_inbox`. Newest first, one section per week under a "Week N" heading. The top story is full width; the rest of each week sits in a 2-column grid at 1280 and a 3-column grid at 1920, left to right then down, equal card height in a row. The card does not repeat the week. The whole headline is the link. There is no separate View or Box Score control. A `game_result` headline ends with ` (Box Score)` and opens the box score. Other stories open the article in this panel; other dispatches open `target`. `yours` is the navy left edge. `news.html?story=` redirects here with the story param. The Office card still uses `news_headlines` (five, upset reports excluded).

Awards reads `GET /franchise/awards` (`@browse_cached`), which always answers 200 with `status`: `projected` (weeks 1-34), `final` (week 35 on) or `unavailable`. Projected shows the heading "Projected All-Americans" and one line under it: the label ("Preseason", "After week 12", "End of regular season"), the weight mix, and "Updates every week" (from week 26: "Not final: tournament play can still change these"). Final shows "All-Americans". Each team (1st, 2nd, 3rd) is one row per position, in PG, SG, SF, PF, C order. Columns follow the data: Pos, Player, Yr, Team, RT (the canonical ramp, rating at the listed position), the per-game stat line (omitted in the preseason, when nobody has one), Bonus (final only) and Score. Position and score are neutral; nothing on the page is green, orange or gold. `unavailable` and a 400 from an older server both show "Awards are not available yet." The user's team row is `tr.me`. There is no season list and no portrait. Scoring rules: `End_Of_Season_System.md`, "All-American Logic".

### Add a module view

1. Move the page's read onto a browse GET `GOBStore` already caches. No new endpoint.
2. Add `js/shared/views/<name>View.js` that exports `mount(container, ctx)` and `unmount()`. `ctx` has `franchiseId`, `teamId`, `store` (`GOBStore`), and `nav` (`GOBNav`). `mount` returns `{ unmount, revalidate }`.
3. Register it in `js/shared/gobViews.js`: `id`, `section`, `subtab`, `title`, and `module` (a function that returns `import(...)`).
4. Add an empty `<div id="<view-id>" class="tab-content">` on `franchise-command-center.html`, and map the id in the shell section list so the sub-tab calls `CommandCenterTabs.show(id, 'replace')`.
5. Leave the old HTML file as a redirect to `franchise-command-center.html?tab=<view-id>` that copies `franchise_id`, `team_id`, and any return params.
6. Update the section map in this file.
7. Cover it with tests: no document navigation, first-open skeleton, failed module, history, and a week-advance refresh.

### Save feedback

A save inside the command center confirms with `GOBToast.show(text)` (`js/shared/gobToast.js`, `css/gob-toast.css`): one short line such as "Playbooks saved", neutral chrome (`--surface-popover`, `--shadow-popover`, `--text-87`; no orange, no green, no icon), `role="status"` with `aria-live="polite"`. It is fixed over the centre of `.main`, `--dsp-24` above the bottom, so it never shifts layout. It fades after `GOBToast.SHOW_MS` (1500ms); a second call restarts the timer. The class is `.gob-save-toast`, because the tutorials' `.gob-toast` is unscoped. A hosted save stays on the view. A failed save uses the same toast with a short retry line. Standalone pages that still load `game-plan.html` or `playbooks.html` directly keep their own `#toast` and navigation. Playbooks choice chrome (Offense/Defense tabs, weight sliders, the open-row highlight) stays neutral; only the enabled Save button uses `--orange`. A play in your Playcall Center (`.play.on`), its slot number and the call-sheet rows (`.csr`) are navy with a `--navy-hi` edge: you picked them (ruling #1). Game Plan choice chrome (strategy sliders, shot-diet tip, selected knob) stays neutral; only Save Game Plan uses `--orange`. Scouting choice chrome (Attributes / Stats) stays neutral; attribute tiles keep the shared RT ramp (blue for A / 9+ / elite).

Unsaved-edit leave: see §6 (`warnOnLeave`, `GOBLeaveConfirm`). Game Plan and Playbooks register a confirm for their view. Training saves each edit as its session draft and restores it on the next open.

### Loading

The first open paints a neutral skeleton in the shape of the view. No spinner. Data comes from `GOBStore.get`. The module stays in the panel after the user leaves. Opening it again shows that panel immediately and calls `GOBStore.revalidate`. The view re-renders only when the body changed. A 304 keeps the table on screen.

An unknown module, or an import that fails, paints a quiet error card with Retry in that panel. The rest of the app stays up. Retry loads the module again. A `?tab=` that is neither a panel nor a registered view still falls back to the section default, as today's tabs do.

### Failure states

The same design-system error card (`.gob-view-error` / `.gob-view-retry`, `css/gob-views.css`) is the one way a franchise surface reports "couldn't load". Never leave a silent dead page or a dead button with no explanation.

- **Season load (FCC).** When `fetchCommandCenterData()` exhausts its retry loop on a transient failure — a network error / offline / a down desktop engine (status 0), a 5xx, or a 429 that never cleared — the Office main area (`#office-root`) shows the card: headline **"Couldn't load your season"**, one cause line when known (**"Connection lost." / "Server error." / "The server is busy."**), and a **neutral** Retry button (`SFX_SELECT`, not Advance). Retry re-runs the full load with the same retry policy, shows a busy button meanwhile (no double-submit), and on success renders the Office and re-enables Advance. A 404 (deleted franchise) keeps its own full-screen notice; a 401/403 still redirects via AccessDenied. Both build profiles behave the same (the desktop engine-crash screen is separate).
- **Advance during a failed load.** Advance stays disabled, *looks* disabled, plays no sound (a disabled button dispatches no click, so its `data-sfx` hook can't fire), and its `aria-label`/`title` say why: **"Season didn't load: retry above"**. Never a silent dead button.
- **Training Report (`/training-report.html`).** A failed report read shows the inline card (`.report-load-status`, "The training report did not load.") in place of the skeleton. Never a browser `alert`. A fetch cancelled because the player left the page (`beforeunload` / `pagehide`, or an `AbortError`) is not a failure and shows nothing. A failed refresh keeps the report that is already on screen.

Opening a player from Roster writes `gob-view-roster-order` in `sessionStorage`: a JSON array of the player ids in the order on screen at that click. The Leaders full list (and each Leaders board card) writes `gob-view-leaders-order`, the same shape. Player Stats writes `gob-view-player-stats-order`, the same shape, and the detail URL carries `pager=player-stats` with `origin=team` and `return_tab=player-stats-view`. Standings writes `gob-view-standings-order` as `{ ids, label }`, the visible team ids in that conference card and the card label (for example `A2`). The detail URL carries `pager=roster`, `pager=leaders`, `pager=player-stats`, or `pager=standings`. No `pager` param means no pager, even if a key is sitting in the session. Paging replaces the history entry and stops at the ends. The Roster Varsity / Practice Squad segment is `gob-view-roster-scope` (`varsity` or `practice`).

The team page stacks Roster above Schedule. Roster is the full Roster grid (twelve attributes in pairs; Dev focus only on the user's own team) with an Attributes / Stats segment (`gob-view-team-roster-mode`); Stats is the Player Stats grid for that team from `GET /franchise/player-stats`. Both sort from their headers. Schedule is Results and Upcoming side by side, two columns each.

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

There are eleven rows in family order. Character: Chemistry, Fight, Discipline. On the floor: Offense (`offensive_efficiency`), Defense (`defensive_efficiency`), P/T Offense (`pt_opp_modifier`), P/T Defense (`pt_efficiency`), Fast Break (`fb_efficiency`), Fast Break Defense (`fb_opp_modifier`), Shooting (`shot_threshold`), Rebounding (`rebound_modifier`). Momentum (`momentum_score`) is deliberately not one of them: the API `measures[]` list omits it (`_MEASURE_FAMILIES` in `BackEnd/utils/office_digest.py`; `test_team_attribute_measures.py`), and it swings game to game rather than accumulating, so a league place and a week-on-week arrow would read as noise. It stays in the stored weekly snapshot only. A missing stored value is still a row, with `value` null.

`pt_efficiency` is your own press and trap execution, so it reads as P/T Defense. `pt_opp_modifier` is working through the opponent's press, so it reads as P/T Offense. The radar's axis labels use the same words.

| Field | Meaning |
|---|---|
| `family`, `family_label` | `character` / Character, or `floor` / On the floor. |
| `key`, `label` | The eleven measures and the labels above. |
| `value` | The stored number for this week. Null when the team has no stored value. The zero-fill on `team_attributes` does not apply here. The page shows it for Chemistry as `19/25`, and as a signed number on the eight measures that carry `signed_scale`. |
| `scale_max` | 25 for Chemistry. Null for the others. |
| `signed_scale` | 20 on the eight trained and compounding measures that `Team_Attribute_System.md` documents at −20…+20: Fight, Discipline, Offense, Defense, P/T Offense, P/T Defense, Fast Break, Fast Break Defense. Null on the other three. Only a row with `signed_scale` may be drawn as a ± pill, because only those have a meaningful zero. Chemistry (7…25), Shooting (~85…95) and Rebounding (~0.5) stay on the league percentile bar. |
| `meter_pct` | Chemistry only: `value / 25 × 100`, clamped 0–100. Null when Chemistry has no value, and null on the other ten. The bar does not read this. |
| `delta` | Change in the stored value since the user team's snapshot. Null when there is no prior value. The page does not show this chip. |
| `description` | Null until a sentence is stored. |
| `direction` | `higher_better` for all ten others. `lower_better` for Shooting only: a make is `shot_score >= shot_threshold`. |
| `rank` | 1 is the best end of `direction`. Ties share a place and the next place skips (`1, 2, 2, 4`). Null when `value` is null. |
| `rank_of` | How many teams in the franchise have a stored value. A missing value is not counted. |
| `percentile` | 0–100. 100 is the best end, including a tie for best. 0 is the worst end, including a tie for worst. The bar fills to this. `100 × (teams strictly worse) / (teams strictly better + teams strictly worse)`. One team, or a measure where every stored value is equal, is 100. |
| `rank_delta` | How many places the user's team climbed since the latest earlier `office_week_snapshots` `team_measures`. Positive means it moved up. The snapshot is the user team only, so every other team is null. Chemistry is not in that snapshot, so Chemistry is null. Still on the payload; **Team Attributes does not draw it** (the ▲N / ▼N marks were removed 2026-10-02). |
| `tied` | True when this rank is shared. The place then reads `T-34th of 128`. |

The place reads `(34th of 128)`, beside the name. A null rank reads an em dash and the bar is empty. The bar fill is the neutral DIFF white, not navy.

The view is the radar over a grid of four columns by three rows. The radar is `franchise-command-center.js::buildTeamMeasuresRadarMarkup` at its ±20 scale — call it, never write a second one. The grid reads down each column: Shooting, Rebounding, Chemistry; Offense, Defense, Discipline; Fast Break, Fast Break Defense, Fight; P/T Offense, P/T Defense. Each cell is the name with its place beside it ("Offense (1st of 128)"), then the gauge and the value. There is no rank-movement mark. Prep › Scouting Report closes with "Spider Chart Comparison": the same radar twice, the user's team on the left and the opponent on the right.

The ± pill is the shared `.gob .dv` atom in `gob-components.css`, the same one Prep › Scouting uses: zero in the centre, filling right for positive and left for negative, with `--v` as the magnitude 0–1 and `.neg` flipping the fill.

## 16. Cross-cutting rules

Durable rules that span sections, current on `develop`.

### One measure vocabulary; no Momentum in team-measure surfaces

The franchise team-measure surfaces show the same eleven measures and the same labels: Team Attributes (`team-attributes-view`), the Training Report Team Report (`training-report.js`), and the Office "Moved most" card. Momentum (`momentum_score`) is not one of them — the API `measures[]` list omits it, the Training Report dropped it from `attrOrder`, and the Office filters it out of `moved_most`. `momentum_score` is still stored, still on the weekly snapshot, and still a live in-game player/box-score metric; it is only kept off these three team-measure displays. `pt_efficiency` reads as P/T Defense and `pt_opp_modifier` as P/T Offense everywhere, including the radar axes.

### One name per title

A title has one name everywhere it is a label: **Regular Season Conference Champions** (`conf_rs`, `trophy_spotlight`), **Conference Tournament Champions** (`conf_t`, `conference_championship`), **Region Champions**, **National Champions**. That covers the title overlays, the Trophy Case medallions, the season-review medallions, the Home Base shelf and the server's season finish line (`career_data._TITLE_FINISH_LABELS`). **Finish labels are capitalised everywhere**: the four titles and the round finishes (`career_data._FINISH_LABELS`: "Region Semifinal", "Missed the Bracket"), so the Trophy Case Finish column, its shelf, the Home Base shelf and Top Seasons read in one case. Top Seasons gives the finish twice the room of the program name (`home-base.css` `.tsn`), so the longest label is not cut off at 1280; a long program name is what gives way. The old "Conference Champions" could not say which conference title it meant, and "Conference Regular-Season #1" is retired. The season review names the region ("Region B Champions") and no longer swaps a conference title's label for "Conference X Champions".

### CH is hidden

CH is a hidden attribute. **It is never displayed and never sent to the client.** The engine, training and the database keep using it unchanged.

| Layer | Rule | Where |
|---|---|---|
| Display | No CH column, chip, label, tooltip or copy on any screen. Attribute lists are the twelve visible attributes (six pairs). | Practice Squad report draws the pair attributes only (`training-squad-report.js` `orderKeys`); the Office drops a CH row (`officeHome.js` `groupAttributes`); no `CH` entry in `attributeTooltips.js`. |
| Payloads | `CH`, `anchor_CH` and `development.ch_seed` are stripped from every response on the franchise and press-conference routers and from `/player/{id}`. Rows that name it (`{"attribute": "CH"}`) and attribute-key lists drop it too. The strip works on a copy; engine objects are never touched. | `BackEnd/utils/hidden_attrs.py`: `HiddenAttrsJSONResponse` is the router's default response class, so a new franchise route is covered without anyone remembering. |
| Copy | Generated text names and counts visible attributes only (Practice Squad All-Stars news). | `franchise_routes._build_ps_all_stars_story`; `NEWS_ATTRIBUTE_FULL_NAMES` has no CH. |
| Guards | `tests/test_hidden_attrs.py` (the strip, every franchise route's response class, a real franchise's payloads, DB still has it); `tests/e2e/hidden-attr-ch.spec.js` (main screens fed payloads that still carry CH). | |

Routes that still carry CH, pinned in `tests/test_hidden_attrs.py` (a decision for Jamie, not an oversight):

| Routes | Why |
|---|---|
| The court's own: `/roster/{team}`, `/api/init-game`, `/api/simulate-turn`, `/api/simulate-quarter`, `/api/call-timeout`, `/api/autoset-lineup`, `/api/game/{id}` and its `resume-state` / `lineup-for-matchups` | The Phaser client reads the receiver's CH to pick the pass-receive sound (`gameSfx.js` `playHcoReceiveSfx`: IQ + CH), and autoset posts roster attributes back. Nothing on the court displays it. |
| `/franchise/team-builder/*` | Team Builder round-trips whole player rows (walk-ons, the slot roster) through the client and saves what comes back; stripping would lose CH on Apply. Nothing in Team Builder displays it. |

### Team names are shown as stored

The display string is `teams.name` as stored. The stored key shows unchanged when no team document exists. Nothing is title-cased, hyphen-stripped, or exception-listed (e.g. `IDA`, `Bentley-Truman`, `Seattle AAA` render as stored). Do not reintroduce a `TEAM_NAMES` map or a `titleCaseName` helper. `common.js` `formatTeamName` returns the name unchanged (`String(name)`), and its callers (`set-lineup.js`, `playbook-report.js`, `pgpcSammyReminderModal.js`, FCC) display it as-is. `titleCaseTeamName` still exists but is only a lookup key for coach-asset abbreviations (`getTeamCoachAssetPath`), never a display string.

### Client API helpers: logout and rate-limited week routes

- **Logout** goes through `API_CONFIG.logout()` (`js/config/api-config.js`). It reads the auth header first, POSTs `/api/auth/logout` with the bearer token and `keepalive: true` (so the server revokes the session), then clears `auth_token` / `auth_user`, and never throws. The three callers (`mode-select.js`, `gobSettings.js`, `authBarInit.js`) call it and keep their own redirect. Desktop/offline: `/api/auth` is always-remote, so with no server the fetch rejects and the local clear still runs — no crash. Do not send a bare `POST /api/auth/logout`.
- **Rate-limited week routes** go through `API_CONFIG.fetchWithRateLimitRetry`. On a 429 it reads `Retry-After` (seconds; default 6), waits, and re-sends the same request up to 5 times, then returns the last 429 to the caller's existing `if (!res.ok)` path. A retried 429 surfaces no error UI; a busy/disabled Advance button just stays put during the wait. The four call sites are `complete-week/phase-a`, `complete-week/phase-b`, `complete-week/start-cpu-sims`, and `finish-season`. Desktop loopback is exempt from the limiter (`user_rate_limit` early-returns on `is_loopback()`), so a single desktop player cannot hit it.

### Scouting reads the opponent from FCC data

Prep › Scouting resolves the upcoming opponent from the already-loaded FCC payload (`commandCenterTopDataCache.next_game_summary`, else `office_digest.next_game`; via `GOBFccPrep.peekUpcomingOpponent`, cached per `franchiseId:week`). It must **never** call `POST /franchise/play-next-game` as a lookup: that route is not side-effect free — in EOS weeks 27–34 it runs `_maybe_reconcile_region_for_eos`, which can write `franchise_doc["region_tournaments"]`. The backend handler is intentionally unchanged; the fix is to not call it for reads.

### Prep views are in-app modules; the embed bridge is retired

Training, Game Plan, Playbooks, and Scouting are in-app module views: each is an ES module with `init(root, options)` / `teardown` / `revalidate` / `shellHtml()`, mounted by `gobViews.js`, with no `DOMContentLoaded` auto-start. There is no `?embed=1` fetch, no `DOMParser`, and no IIFE. `prepEmbed.js` is deleted; its shared helpers (`ensureCss`, `loadScript`, `ensureFranchiseMode`) live in `js/shared/views/viewLoader.js`, and `ensureFranchiseMode` reads `FranchiseContext` only (no `URLSearchParams` fallback). Training uses one implementation: `sections: 'player-dev'` in Prep, `sections: 'weekly'` on `/training.html` (focus, including tutorial). The Training Report uses the same `training-report.js` module on `/training-report.html` in focus (including tutorial-adjacent and Office/News entry). Both standalone hosts mount the module on `#training-view` / `#training-report-view` so the tokenised in-app CSS applies (no `body.training-page` / `body.training-report-page` gradient cards or red/green pill bars). Weekly rows show only the point selector (five boxes; the range input stays the model, clipped; see "Training, point selector"). The standalone report shows an `h1` "Training Report" above the week meta line, with Continue to Office / Back to Locker Room aligned to that title. `game-plan.html` and `playbooks.html` still redirect except `mode=tutorial` (and `game-plan.html` `resume_from_timeout=true`, which stays focus).

### Surfaces outside `FrontEnd/static`

The Electron shell and the ops pages are on the design system. `desktop/splash.html` and `desktop/error.html` cannot load `FrontEnd/static` (they paint before the local engine is up), so they copy the needed tokens inline (`--bg` `#0b0d14`, `--text-*`, `--navy-hi`, `--surface-2`, type roles) and load local copies of Bebas Neue Pro Bold, Barlow latin (`gf-03.woff2`), and the homepage lockup of the GOB wordmark from `desktop/assets/`. Splash: wordmark + "Starting the local engine…" + a navy-hi pulse (no orange, no reward gold). Crash: "The game engine stopped", the existing message, no new actions. Window `backgroundColor` is `--bg`. Native dialogs stay `dialog.showErrorBox` with title "Geeked-Out Basketball". The app menu is minimal (macOS app-name About/Hide/Quit, Edit copy/paste, View Reload / Toggle Full Screen; DevTools only when unpackaged). Pack keeps `productName` "Geeked-Out Basketball" and passes `--icon=build/icon` only when `desktop/build/icon.icns` (mac) / `icon.ico` (win) exists; otherwise the default Electron icon and a one-line warning. No ≥512px square brand source exists yet, so Jamie still supplies those icon files.

`404.html` and `maintenance.html` use gob tokens, app fonts, and the wordmark. 404 copy is "This page doesn't exist" with Home Base (`/mode-select.html`) when `auth_token` is set, otherwise Homepage. Netlify serves `FrontEnd/static/404.html` automatically (publish root). FastAPI serves that same file at status 404 for HTML requests; `/api/…` 404s stay JSON. The Netlify maintenance wildcard stays commented. Live-game Phaser/court overlays are still off-system (DON'T restyle without a sim-safe pass).

### franchise-command-center.css freeze — live

`FrontEnd/static/franchise-command-center.css` is frozen. No new rules. Put new styles in the view's own CSS. `scripts/check_ui_tokens.py --strict --no-write` fails if the file grows past `FCC_CSS_MAX_LINES` / `FCC_CSS_MAX_RULES` (live ceilings: 1779 lines, 230 style rules). Ceilings may shrink; they must not grow.

Peel 2 (2026-10-01), what the sheet and its neighbours now assume:

- **A rule is dead only when grep proves it.** Either a class / id in the selector has no mention in any html or js under `FrontEnd/static`, or the selector hangs off an id nothing creates. A rule that only fails to match at runtime stays.
- **Old tab panels still in the markup keep their rules:** `#home-tab`, `#fcc-team-stats-summary-tab`, `#awards-tab` (old `?tab=` links still reach them). `#standings-tab` was removed on 2026-10-01; its `.fcc-standings-*` rules are now unused and can go in the next peel.
- **`.inbox-badge` is neutral** (`--text-100`; ruling #7). The recruiting link focus ring and the "New" lean badge are neutral.
- **"This Franchise No Longer Exists"** (`#fcc-franchise-gone`) is on tokens with a neutral plate button. Leaving a dead franchise is not Advance.
- **Attribute tiles (`css/attr-tiles.css`):** the tier ramp is the only colour. Sort arrows and focus rings are neutral. Values stay literal because `team-roster-view.html` loads the sheet without tokens.
- **Senior tribute title marks are reward gold** (ruling #6). Green stays on `.st-advance` only.
- **"Yours" is navy from the tokens** (ruling #1): the bracket's `.fcc-tb-*--user` rows and the lean ladder's `.is-you` / `.you1` / `.list`. `#franchise-container .hero-btn` is the Advance fallback before the shell moves `#play-now`, and is the only law hit left in the sheet.

### Lessons

- **Never reuse a shell class name in page markup.** Once a page is `html.gob-shell`, shell rules for `.rail`, `.top`, `.main`, `.card`, `.nm`, `.lnk`, etc. apply to any element that borrows the name (e.g. a Your-Orders aside on `class="rail"` got hidden by `.gob-shell.gob-focus .rail { display:none }`). Give page components their own class (`.srail`, not `.rail`).
- **Guards assert computed styles, not class names.** Colour/law and before/after guards read the computed `backgroundColor` / `borderColor` / `borderRadius` off the element, so a rename or a token swap can't fake a pass.
- **Capture BEFORE screenshots from develop or a served frame.** Take the before shot from the develop build (behind the feature's `*_BEFORE=1` flag or the old embed bridge restored just for the shot) or from the handoff frame served so its CSS loads — never from the half-migrated working tree. Restore any regenerated tracked `reports/*` images with `git checkout -- reports/` before committing.
- **A page that uses `var(--token)` must carry `.gob` and load `css/gob-tokens.css`.** The tokens are scoped to `.gob`, so a standalone page (`set-lineup.html`) needs `<html class="gob">` + the `gob-tokens.css` link (as `training.html` does). `.gob` alone only defines the custom properties — it does not restyle the page (the shell layout lives in `gob-shell.css`, which a focus page does not load).
- **Injected chrome uses `.gob-scope`, not `.gob`.** Chrome that is appended to pages which may not be `.gob` (page-load overlay, error screen, the account toast, the Home Base body) carries `.gob-scope`: the same custom properties and nothing else. `.gob` on such an element would also match the component rules in `gob-components.css` (`position: relative; overflow: hidden; background`). The host page still has to load `gob-tokens.css`. `.gob-scope` has no density classes.

### Set Lineup

`set-lineup.html` is a `.gob` focus page that opens from Advance (Play Game) and hands off to `court.html`. It loads `gob-tokens.css` but not the shell, so it keeps its own layout. Colour law on it:

- **Play Game (`#play-now`, `.lineup-btn-advance`) is the one Advance — green.** Nothing else on the page is green except positive-data ramps.
- **Choice controls are neutral.** The Game / Attributes / Stats view toggle, Autoset Lineup (a non-advancing action, *not* a save; orange is unsaved changes only, and the token comment no longer lists non-advancing actions), position slots, and the FT-shooter lock badge carry no green or orange.
- **Selection is navy** (ruling #1, settled). On-court rows carry a `--navy` tint and a `--navy-hi` left edge; a selected row has the same edge. Never orange. The active drop target (`.slot.drag-over`, `tr.drag-over`) is a navy tint.
- **Energy / next-game readiness is a data ramp.** High is positive data (`--green`, annotated), then yellow, then an amber `color-mix`, then `--red` — the ramp never uses raw orange.
- **RT stays blue** via `rt-buckets.css` (`.rt-*`), the sanctioned A-grade / 9+ / elite colour.
- There is **no save state** on this page (the lineup persists through the flow, confirmed by a neutral toast), so orange has no home here.
- **A franchise lineup starts empty, by design** (settled 2026-10-01). The page opens with five empty slots and every player on the bench; the coach fills them or presses Autoset Lineup. Only `mode=tutorial` autosets on load (`set-lineup.js`). Do not add a franchise preset.
- `set-lineup.css` is on the design system (`NEW_DESIGN_CSS` in `check_ui_tokens.py`); `set-lineup.html` is already new-design via `gobShell.js` PAGES.

### Team Builder

`team-builder.html` is a pre-franchise flow (Identity → Gate → Roster → Review → Establish). It carries `<html class="gob">` and loads `gob-tokens.css`, but not the shell and not `gobDensity.js`, so it keeps its own layout and the 1280 token sizes at every width. `team-builder.css` is in `NEW_DESIGN_CSS`. Colour law on it:

| Element | Colour | Why |
|---|---|---|
| Continue, Continue to Review, Enter Franchise (`.btn.tb-advance`) | green, shell Advance paint | The one Advance per chapter. Disabled is the dead neutral. |
| Establish <program> (`.btn.sb-commit`) | orange, annotated `committed` | It writes the program into the league and cannot be undone. The only orange. |
| Attribute fills, signature bars, grid cells (`scaleColor`) | `--tier-red` / `-yellow` / `-green` / `-blue` | The rating ramp on the raw scale: ≤40, ≤60, ≤80, 81+. Blue appears nowhere else. |
| Selected roster row (`.bd-row.sel`, `.gr tr.sel`) | navy | Selection, as on Set Lineup. |
| Your seat in the Establish table (`.sw-t tr.slot.now`) | navy | "Yours". |
| Valid / legal / eligible / exact (`.ok`, `.d-ok`, `.verdict.ok`, `.meter.exact`, `.tally.ok`, `.pool.ok`, `.elig`, `.m-elig.ok`) | `--text-100`, neutral border | Status labels carry no green. Invalid stays `--red`. |
| Changed from inherited (`.cls.chg`, `.bd-ht.chg`, `.mk.edit`, `.dlt`) | `--text-100` | A diff marker, not a save. |
| Chapter cell, style buttons, palette ring, chips, year and view toggles, tone filters, input focus | neutral | Choice controls. |
| Position chips (`.pos`, `.gp`, `.pos-b`), attribute category headings and legend codes | neutral | Information codes. No per-position or per-category colour. |
| Wait pulse, pending sweep, picker accent, links | neutral | Not Advance, not a save. |

- Headshots are square: `--radius-6` on the 26px board badge and the 38px Review badge, `--radius-10` on the 104px inspector portrait and the picker tile.
- Team colours stay data: palette and swatch fills, court and banner art, skin-tone filter chips, and the Review "your program" row tint (`--me`, the program's primary).
- Raw attribute values run 5–99 here and nowhere else (`ATTR_MIN` / `ATTR_MAX` in `js/team-builder/constants.js`). The ramp thresholds are on that raw scale.
- Team names render as stored (Replacing cell, conference tables).

### Tutorials and FTE

Tutorial pages (`tutorial*.html`) are `html.gob` and load `gob-tokens.css`; no shell, own layout. The colour law applies to tutorial chrome; it has no tutorial accent colour.

- **Neutral primary is `.gob-btn--neutral`** (`gob-buttons.css`): a white plate with `--bg` ink, for a main CTA that neither saves nor advances (Start lesson, Continue, LET'S GO, pick-opponent CONTINUE, Got It). The tutorial alert / tip primaries (`.gob-talert-btn-primary`, `.gob-tip-overlay .btn-primary`) use the same plate.
- **Green** is only the FTE Advance: tip-off SIM GAME (`gob-btn--gate`) and the lineup-feedback CONTINUE.
- **Orange:** none. The username CONTINUE is the neutral plate (`.gob-btn--neutral`; Jamie, 2026-10-01: orange only for unsaved changes).
- **Sammy modals** (`sammy-modal.css`): the primary is the neutral plate by default; `primaryClass: 'is-orange'` is a no-op kept for old callers. A CTA that advances game state passes `primaryClass: 'is-advance'` for green (the region-bye "Sim Region First Round", which runs `#play-now`).
- **Neutral chrome:** Sammy portrait rings, eyebrows and ticks, the active tutorial-nav icon, depth badges, toast and callout bars, tutorial-alert rail, mark, progress and dots, the hub progress bar, order circles and seen check, the attribute-tour band, cue and explored state, and the pick-opponent selected card (the team-colour rail stays).
- **Hosts without `html.gob`.** `gob-tutorial.css` (injected on every auth-bar page), `sammy-modal.css`, `username-modal.css`, `fte.css` and `.gob-btn--neutral` write tokens as `var(--token, <gob value>)`.
- **`css/fte.css`** styles only the pre-press-conference reminder (`pgpcSammyReminderModal.js`) as dark Sammy chrome. It also overrides that module's light-shell label colour and orange checkbox accent.
- **Out of scope:** the lesson pages' inline teaching diagrams (they keep the `--orange`, `--orange-soft`, `--green` and `--lblue` aliases) and `gob-advanced.css` diagram colours stay legacy. Only that sheet's chrome is neutral.
- On the design system: `gob-tutorial.css`, plus the Sammy, username, walk-on, attribute-tour, lineup-modal, persona, pick-opponent, tip-off and `fte.css` sheets (`NEW_DESIGN_CSS`).

### Auth pages

`login.html`, `signup.html` (alpha access code + account step + Request Access modal) and `reset-password.html` are `html.gob` with `gob-tokens.css`; one sheet, `auth.css` (`NEW_DESIGN_CSS`). Visual only: ids, names, endpoints and scripts are unchanged.

- **Green** is only the submit that enters the game: LOG IN and SIGN UP (`.auth-button.auth-button--advance`).
- **Every other button is the neutral white plate** (`.auth-button`, same as `.gob-btn--neutral`): code Continue, Request Access, Got it, Send Reset Link, Update Password.
- **Errors are `--red`** (`.error-message`: text `--red`, 10% fill, 45% border).
- **Neutral:** success / confirmation (`.success-message`), "Code accepted", links (underlined `--text-100` / `--text-87`), input focus (`--white-45` border, `--white-12` ring), the Request Access modal top rule.
- **No navy/blue atmosphere** (navy is "yours", blue is RT): a neutral `--white-4` lift and the faint diagonal banding.
- Headings and buttons `--font-display` (Bebas Neue Pro); body `--font-body` (Inter).
- Logout lands on `/mode-select.html`, not an auth page.

### Community pages

`coaching-archetypes-leaderboard.html`, `coaching-archetypes.html` and `account.html` (geek points, titles, archetype board) are `html.gob` with `gob-tokens.css`; one sheet, `css/community.css` (`NEW_DESIGN_CSS`). The old inline `<style>` blocks are gone. The Home Base leaderboard is `home-base.css` (already new-design).

- **Navy is "yours" only:** your leaderboard row (`.alb-row.is-current`, the `.ldb-r.me` recipe) and your lead archetype card (`.ca-card.is-lead`, the `.agc.is-me` ring).
- **Data is neutral:** archetype share % (`.alb-pct`, `.arch-pct`), the geek points total, title counts. Points are a count, not a reward surface (no `--reward-gold`).
- **Neutral:** the plan/status pill (`.acct-status`), the In-Game Display segment on-state (a choice control), the tooltip focus ring, the avatar (surface tokens, no navy gradient).
- **No page wash:** a neutral `--white-4` top lift on `--bg-chrome` (was a navy radial).
- `body.has-auth-bar` (auth-bar.css) owns `padding-top`; `css/community.css` sets only sides and bottom.
- **Team Colors Mode** (the old Styleguide community-row fade) is not live in code; it stays retired.

### Shared chrome (auth bar, overlay, error screens, FAQ / legal)

Tokens reach this chrome three ways: `css/auth-bar.css` imports `gob-tokens.css`, and that file scopes the tokens to `.auth-bar` and `.site-footer` as well as `.gob` (both sit in static markup on pages that are not `.gob`: homepage, community); roots built by script carry `.gob-scope`; `faqs.html` is `html.gob`; `privacy.html`, `terms.html` and `mode-select.html` carry `.gob-scope` on `<body>` (the legal pages stay off `html.gob` because a tutorials spec uses `/privacy.html` as its non-gob host). `css/auth-bar.css`, `css/legal.css` and `mode-select.css` are in `NEW_DESIGN_CSS`.

| Surface | Rule |
|---|---|
| Auth bar (`.auth-bar`) | `--bg-chrome`, neutral text and controls. Nothing green or orange. Hidden under the franchise shell. |
| Tutorials alert (`.is-alert-glow`, `.nav-tutorials-callout`) | Neutral: white glow, white pill with `--bg` ink. An unread tutorial is not a save. |
| Switch (`.account-switch`) | On-state is a brighter neutral (white 18% / 28%) plus the knob position. A switch is a choice control. Literal values, because `account.html` reuses it and that page is not guaranteed to carry tokens. |
| Account toast (`.account-toast`) | Neutral rail and icon, like `GOBToast`. |
| Modal accent (`.gob-modal-accent` mirror in `auth-bar.css`) | Neutral at zero specificity (`:where()`). `resource-pages.css` is neutral by default too (batch 2); `is-green` / `is-red` / `is-neutral` modifiers still win. |
| Site footer (`.site-footer`) | White strip on `--white`; link is `--bg` ink, not orange. |
| Page-load overlay (`pageLoadOverlay.js`) | Solid `--bg` (the page fill at full opacity, Jamie 2026-10-02; never a see-through tint), in the script and in the static markup of the six pages that carry it; the pulse bar is a neutral gradient. A wait indicator is not Advance and not positive data. |
| Error screens (`errorHandler.js`) | `--bg` page, `--surface-2` card, neutral heading. Primary action is the neutral plate (like Retry), secondary is a ghost. No orange. |
| FAQ, Privacy, Terms | Dark `--bg` page; links are neutral and underlined. |
| Home Base alpha banner (`.alpha-disclaimer`) | Neutral rail and title; only the alert label is `--red`. Hidden while trailer mode is on. |

`account.html` is not part of this: the community pass owns it (see Community pages).

Not on tokens, on purpose: the Feedback button, its pulse and the Feedback modal in `auth-bar.css`, and the local modal system and Leaders By Team modal in `mode-select.css` (alpha-feedback and community surfaces, owned by the community pass); the literal `.gob-modal-*` mirror block in `auth-bar.css` (it must render on pages with no tokens).

### Program select

`franchise-select-team.html` (Find Your Program, the first step of a new franchise and Team Builder step 1 with `?builder=1`) is `html.gob` with `gob-tokens.css`; one sheet, `franchise-select-team.css` (`NEW_DESIGN_CSS`). Same rulings as Team Builder:

| Element | Colour | Why |
|---|---|---|
| Enter Franchise, Take This Slot (`#ab-primary`, `.btn.advance`) | green | The one Advance. Take This Slot is Team Builder step 1's Continue. |
| Selected program card (`.pg.sel`, `.pg-check`) | navy | Selection, as Team Builder and Set Lineup. |
| Open Team Builder, draft Continue (`.btn`) | neutral white plate | Navigation, not a save or an Advance. |
| Scout, Clear, Discard, Cancel (`.btn.ghost`, `.mb-x`) | ghost | Secondary. |
| Filters (search focus, active `.fsel.on`), Clear link, card hover | neutral | Choice controls. |
| Top Talent / Prestige tier (`.top1`, `.top1t`) | `--text-100`, bold | Information codes; weight, not colour. |
| Team Builder mode banner (`.mbar`), entry card (`.tbe`), unfinished draft card (`.draft-card`), loading dots | neutral | No orange wash, no blue (RT only). |
| Error (`.team-select-error`) | `--red` | |

- Team colour appears only in each program's own banner art.
- `css/team-picker.css` and `TeamPicker.mount` (the old picker UI) were removed; `js/shared/teamPicker.js` keeps only the league data helpers.

- **Career strip (online, left column, `.hb-career`).** The four numerals (Career record with the win % beside it, Titles, Seasons, Geek Points) take the whole column: each cell is as wide as its own content and the slack is shared between them (`justify-content: space-between`), with no dividers. The Trophy Case link is navigation and sits in the utility row with Tutorials, Settings and FAQs. The offline "Your Career" zone keeps its grid.

### Play-flow pages (training playbook, playbook report, recruit detail)

`training-playbooks.html`, `playbook-report.html` and `player-detail.html` (recruit detail) are `html.gob` with `gob-tokens.css` and no longer load `resource-pages.css`: each sheet (`training-playbooks.css`, `playbook-report.css`, `player-detail.css`, all `NEW_DESIGN_CSS`) carries the brand shell rules it used, same selectors, on tokens.

| Element | Colour | Why |
|---|---|---|
| Save & Continue (`.tp-btn-primary`) | orange, annotated `saved` | Saves. |
| "Playbooks Saved" toast (`.toast`) | neutral (`--line-strong` edge) | Reports a save; it is not the save (orange stragglers). |
| Selected play card + check (`.tp-card.is-selected`) | navy | Selection. |
| PCC chip, dock share bar, overall grade, primary position value, section rules and subheads, position pills (`.pd-pos-pill`) | neutral | Information codes / data. No per-position colour. |
| "At least 1 required" (`.tp-warn`) | `--red` | Invalid. |
| Edit Playbooks (`.report-btn-primary`) | neutral white plate | Navigation. |
| CMD bars (`.tp-cmd-fill`) | `--tier-yellow` / `--tier-green` / `--blue` | Unchanged hues. A data ramp, kept (ruling #2). |

- Not migrated: `play-details.html` (pending the inspector decision). The Shot Distribution pills (`getPswColor`, `.psw-*` in `resource-pages.css`) are not a migration target: the shot-share ramp is kept as a data ramp (ruling #2; [Styleguide, Data scales](Styleguide.md#data-scales)).

### Empty states

One shared pattern: `.gob-empty` (`css/gob-tables.css`). Its look is in the [Styleguide, Empty states](Styleguide.md#empty-states). Use it wherever a view or board has nothing to show, with one short sentence:

- League › Practice Squads before it opens, News › Awards with nothing to show, League › Standings with no rows.
- League › Leaders: a board with no qualified leader shows `No leaders yet.` and drops its "Full list →" (the rate floors in §13 leave FG% / DEF% empty at zero team games; per-game boards are empty before the first game).
- Page-specific empty classes (`.gob-ps-empty`, `.gob-news-empty`) may stay alongside it for spacing; the card look comes from `.gob-empty`.

Related small rules (gallery fixes, 2026-10-01):

- Box Score "Back to Locker Room" is the standard ghost `.brand-back-link`, inside the page shell above the first card.
- Cut Players: the page title is `--font-display`. "Assign Practice Squad" is the page's save (orange when enabled, dead when disabled). The "No Cuts Required" and load-error modals are not errors and not saves: neutral accent, neutral secondary "Back To Locker Room". Every other modal on the page (leave, confirm) has a neutral accent too, and the leave-confirm "Stay" is a neutral primary (batch 2).
- Set Lineup banner strip: `object-fit: contain` on `--surface-2` (the full lockup, never a crop).
- Segmented toggles with a count (`.stats-toggle button em`, e.g. "Varsity 15"): `--space-6` before the count.

### Rulings recorded 2026-10-01 (gallery follow-up)

- **Set Lineup, franchise mode: the five are not preset.** Slots stay empty until the user picks or presses Autoset. Intended (Jamie); only the tutorial (`mode=tutorial`) presets.
- **Team logos:** `getTeamAssetPath(name, 'logo_square')` (`common.js`) serves `<slug>_logo_square.png` when the team has one, else `<slug>_logo_primary.png`, else the generic square. It reads the known-asset lists `TEAM_LOGO_SQUARE_SLUGS` / `TEAM_LOGO_PRIMARY_SLUGS`, built once; `tests/test_team_logo_manifest.py` keeps them in sync with `images/teams/`. No per-image 404 probing. `teamLogoArtKind(name)` returns `none` for a core program with neither file; League tables (`gobTables`) then show the generated letter tile directly. The letter tile is the last resort.
- **Save buttons: orange = there is something to save.** Save Game Plan (`gamePlanHasEdits`) and Save Playbooks (`hasEdits`, the same check the leave prompt uses) toggle `.is-dirty`; the button is neutral (`--white-6`, `--text-60`, `--line-strong` ring) without it. A disabled Save keeps its dead style. Moving a Game Plan slider away and back is not an edit; a Playbooks weight step rebalances siblings, so stepping back stays an edit until saved or reverted.
- **Weekly Submit Training stays the green Advance** (Jamie).

### Rulings recorded 2026-10-02 (training, report, game plan, playbooks, set lineup)

Jamie's walk-through. Colour rules are in the [Styleguide, Settled 2026-10-02](Styleguide.md#settled-2026-10-02).

| Surface | Rule | Built as |
|---|---|---|
| Weekly training, Auto-Train | Plays the Autoset Lineup cue (`chaotic-choice.wav`), one sound for the action. | `training.js` `autoAssignTraining()`; `Sound_Design_System.md` already lists it. |
| Weekly training, Player Development | Editable on the weekly page again, under Coaching Focus: position and focus per player, saving on change. Cards in four columns, RT order reading down each column (twelve players = four columns of three; a longer camp roster adds a row). Prep › Player Training keeps the table. | `playerDevelopmentGrid.js` `layout: 'cards'` / `'table'`; `--pdg-rows`. |
| Weekly training, Coaching Focus | Four neutral cards, each with a coaching style mark. Options are neutral choice chips, two to a row. | `training.css` `.archetype-block`, `.arch-mark`. |
| Weekly training, Player Maximizer | Four options: Top 3 Attributes, Attributes 4–6, Positional Focus, Custom. Each is its own radio and opens the attribute modal titled with its own name. Assign keeps it; Cancel, Escape or the backdrop return to the focus that was in force. The checked radio's value is the leaf the server reads. | `training.js` `PM_LEAVES`; the modal is a `.gob-modal-overlay`. |
| Any page modal under the focus shell | Must be a `.gob-modal-overlay`. The shell adopts every other body child into `.main`, where `.gob .main > *` makes it `position: relative`: a fixed modal becomes an in-flow block and opens below the fold. | `gobShell.js` `adoptMain`; `gob-shell.css`. |
| Weekly training, labels | "Press/Traps" (not "P/T"); "Training Plays" (not "Playbook Training"). | `training.html` + `training-shell.js` (kept identical). |
| Weekly training, Custom Playbook | Leaving for the Training Playbook page is part of the training flow: the draft is saved and the unsaved-allocation confirm does not fire. | `training.js` `allowNextLeave()` before `GOBNav.go`. |
| Training Report, loading | Nothing half-built. Until the data is in, the sections and the "--" placeholders are hidden and a skeleton stands in (`.is-loading` on `#training-report-view`, set in the static page so it holds from first paint). A failed load shows one neutral line. | `training-report.js` `setReportLoading()`; `.report-skeleton`. |
| First paint, every screen | No screen is shown half-built. Before its data is in, a screen shows nothing or a shared loading pattern: never bare titles, placeholder dashes, "NR" / "0-0" / "undefined", a layout that jumps, or an old panel that is then replaced. Three shared patterns, no new ones: (1) the page loader (`PageLoadOverlay`) for a whole page; (2) the view skeleton (`GOBTables.paintSkeleton`, `.gob-view-skel`) for a view inside the shell; (3) the Training Report's own `.is-loading` skeleton. A standalone page that waits on data sets `is-loading` on `<html>` in an inline script at the top of `<body>`, shows the page loader, hides its body with an `html.is-loading …{visibility:hidden}` rule (so nothing half-built shows in the frame the loader lifts), and lifts both in a `finally` once it has drawn. | Sweep tool: `tests/e2e/first-paint-sweep.spec.js`, `desktop-first-paint-sweep.spec.js`, `desktop-first-paint-transitions.spec.js` (`FP_SWEEP`). Gates: `tests/e2e/first-paint.spec.js`. |
| First paint, held pages | Program select (`#claim-root`, footer), Training playbook (`.tp-shell`), weekly Training (`#training-view`, `.pg-head`; lifted by `liftWeeklyLoading()` so the 24-point default is never shown), Account (`.acct`) and Archetype leaderboard (`.alb`), each with its footer. | `franchise-select-team.*`, `training-playbooks.*`, `training.html` / `training.js` / `training.css`, `account.html`, `coaching-archetypes-leaderboard.html`, `css/community.css`. |
| First paint, shell top strip | Before the season data is in, the rank stat is hidden ("NR" is a real answer, never a placeholder) and a logo with no `src` is `visibility:hidden` (no alt text standing in). | `gobShell.js` `paintRank()`; `gob-shell.css` `.top .top-id img:not([src])`. |
| First paint, Scouting and drill-ins | Prep › Scouting stands the view skeleton in its status slot (`.scouting-status.is-loading`) instead of a line of loading text. A team or player page shows its bar and the view skeleton; the breadcrumb has no trailing separator until the name is known. | `scoutingView.js` `setLoading()`; `detailBar.js` `barHtml()`. |
| Training Report, page head | Sticky, on the solid page fill (`--bg-page-solid`), so sections scroll under it. | `training-report.css` `.report-header`. |
| Training Report, Playbook Summary | Two panels side by side, Offense and Defense. Sub-sections are compact columns: Motion, Inside / Attack / Outside Set Plays; Man, Zone. No Section column. | `createPlaybookSummaryPanel()`; `.pbs-*`. |
| Game Plan | Four section heads with one spacing: Shot Diet and Execution (offense), Disruption and Transition (defense). Disruption holds Aggression, Half-Court Trap, Full-Court Press. Each column is one lead slider, a section of three and a section of two, so the heads line up across the gutter. | `game-plan.html` + the shell string in `game-plan.js`; `.grp-h`, `.grp-hd`. |
| Playbooks, tabs | Offense, Defense, Fast Breaks, Press/Traps, in that order, each its own pane. | `PLAYBOOK_TABS`; `data-pane`. |
| Playbooks, Set Plays | Three sub-sections, Inside, Attack, Outside, each with its play count and its share of the section's 100%. A row names only the target shooter. | `buildSetPlayGroupHead()`; `.pb-sub`. |
| Playbooks, strip and tab row | The Shot Distribution strip is sticky (the live read-out while weights move). In the shell it pins directly under the page head on `--bg-page-solid`, and the tab row pins with it, `--dsp-16` below, at every width and scroll position. A sticky strip must never be transparent or pinned at an offset above the page head. | `playbooks.css` `.playbooks-shot-weights-strip`, `.playbooks-side-row`; `--pb-strip-h` from `syncStickyOffsets()`. |
| Playbooks, lock | Neutral only. Unlocked: open padlock, dim (`--text-38`), no plate; the slider carries a handle. Locked: closed padlock in `--text-100` on a filled plate (`--white-18`), `aria-pressed="true"`, row class `.is-locked`; the track is muted with no handle and is not focusable, the percentage drops to `--text-60` and is read-only, the play name stays full strength. Motion, Set Plays, Man and Zone lock; Fast Breaks and Press/Traps normalise instead and have no lock. | `playbooks.js` `buildEnforcedTile()`; `playbooks.css` `.wl`, `.play.is-locked`. |
| Training, point selector | Neutral only. Each drill row is five boxes, a clear control and the number; the clipped range input stays the model. Empty box: 1px outline, no fill; the outline strength is ONE token, `--train-box-outline`, set to `--white-45` (option B, Jamie's choice 2026-10-02; option A was `--white-25`). Filled box: solid `--white`. Hovering box N previews 1..N (`--white-25`), and filled boxes past N dim (`--white-45`); the row gets a `--white-3` highlight. A box past the remaining budget is disabled, `opacity:.35`, no pointer events. Clear (a small ×) shows only while the row has points, and ghosts in on row hover or keyboard focus; there is no permanent zero mark. The number is `--text-38` at 0 and `--text-100` with points. Keys on the focused row: left/right change the value; Home, Delete, Backspace or 0 clear; the focus ring is a 2px `--text-100` outline round the boxes. Hit area 22 by 28px per box. Each column is capped at 390px so the boxes sit within about 200px of their label at any width. | `training.js` `ensureTrainingSliderVisual()`, `updateTrainingSliderVisual()`; `training.css` `#training-view .ps`; `gob-tokens.css` `--train-box-outline`. |
| Playbooks, sliders | Left arrow decreases, right arrow increases (Shift: by 5). A drag ends in a re-render, so focus is put back on the slider that replaced the one dragged. | `refocusSlider()`. |
| Set Lineup, right panel | Autoset Lineup / Game Plan / Playbooks sit directly under the Shot Weight charts, not pinned to the bottom of the panel. | `set-lineup.css` `.lineup-rail-actions`. |
