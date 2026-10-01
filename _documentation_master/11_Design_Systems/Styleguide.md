# Style Guide

The look of GOB and the canonical colour law. This document says what things look like and which colour may go where. [UX_System.md](UX_System.md) says how to build (shell, navigation, data, the page checklist). `FrontEnd/static/css/gob-tokens.css` holds every value, scoped under `.gob`. `scripts/check_ui_tokens.py --strict` enforces the colour law on new-design files. Name a token; never copy its value into a page, a component or this document. Where this document and the token file disagree, the token file wins and this document is the bug.

## Colour law

One colour, one meaning. Everything not listed is neutral: white text at `--text-100` / `--text-87` / `--text-60` / `--text-38`, white alpha fills (`--white-*`), lines (`--line`, `--line-strong`) and the blue-black surfaces (`--bg`, `--surface-*`).

| Colour | Token(s) | Allowed | Banned |
|---|---|---|---|
| Green | `--green` (ink on green: `--bg`) | The one Advance per screen (top-bar `#play-now` / `.advance`, `.gob-btn--gate`, the one forward action in a live-game overlay, Submit Training on the weekly training page). Positive data: delta-up, tier green, chemistry high, board-gain bars, the RT / attribute ramps. | Cards, WIN/LOSS plates, badges, scores, choice controls, a second button on the same screen, any button that only navigates or only saves. |
| Orange | `--orange` | **"There are unsaved changes" and nothing else**: the save or commit of something you changed. Submit Invites, Submit Orders, Save Game Plan / Playbooks (only while there is an unsaved edit: neutral at rest and after a save), Assign Practice Squad (`.gob-btn--action`), the promise toggle, the committed-order rail, the funded row. | Brand accent, "warning / low" data, navigation, choice controls and their selected state (`.is-on`), checkboxes, hovers, toasts, a loader, the rail count badge, gated / "Blocks Advance" tags and blocking-step outlines, data ramps (attitude), modal accents, a "Stay" / keep-editing button. |
| Navy | `--navy`, `--navy-hi` (edge / halo only) | "Yours": your row, your game, your lean, your region, your signing, your `#n`, on-your-list, your team in a bracket. What you picked for your team or plan: Set Lineup on-court and selected rows, plays in your Playcall Center, your leaderboard and lean-ladder slot. Structure: the active rail item, switch on. | Data fills, stat bars, page or shell backgrounds, a green or gold substitute. A generic "selected" state on a choice control: tabs, toggles, radios, sliders and filter chips stay neutral. |
| Blue | `--tier-blue` | RT only: an A grade, a 9+ attribute, elite. One exception: the top band of the shot-share ramp (see [Data scales](#data-scales)). | Chrome, links, navigation, "good / above average". |
| Reward gold | `--reward-gold` | Only: title medallions (`.med.gold`); season-peak glow, rule and confetti (`.pk`, `.cf`); milestone accents (`.mm.is-gold`, `.mm .med`); the exceptional-gain marker (`.xg`, `.xg-key`); the words "Trophy Case" (`.gold-t`); senior-tribute title marks (`.st-titles s`, `.st-cti s`). Tints are `color-mix()` at the point of use; there are no gold tint or shadow tokens. | Any button, including the button on a reward modal (the big-news CTA is a neutral plate). Advance, "yours", choice controls, everyday or weekly chrome, Home Base chrome. |
| Red / yellow | `--tier-red`, `--tier-yellow`; `--red` for the one destructive style | Data ramps (rating tiers, chemistry, energy, the attitude bars' low buckets). **Irreversible deletes only**: the red-outline confirm button and the red menu item for deleting a program on Home Base (`.btn-del`, `.pop-i.danger`). | ▼ deltas, LOSS plates or letters, buttons, chrome, warnings, modal accents, and destructive styling on anything reversible (removing a queued invite, assigning the practice squad, leaving with selections). |
| Team colour | `--team-primary` (set per team) | Identification: logos, name bars, favour arrows, team badges, the edge border and side tint that say which team a live-game side panel belongs to. | A wash or tint on a card, panel, tab, header or the weekly / result card, win or loss. The selected state of a choice control. |
| Tier metal | `--tier-metal`, `--tier-metal-hi` (set per tournament tier) | Tournament-tier top bar and the tier next-game card. | Anything outside tournament weeks. |

Neutral by rule (no green, orange, gold or navy):

- **Choice controls**: tabs, segments, filter chips, sliders, the watch star, checkboxes, view toggles, the live-game side-panel stat toggles, Autoset Lineup, a Retry button. Selected is a brighter neutral, never navy, team colour or orange.
- **Status and information codes**: phase labels, week tiles, invite counts, status labels, Player Development Grid "develops" / "adds" markers. Muted text, not colour.
- **W/L plates**: WIN is a white plate, LOSS is an outline, everywhere, tables included (Rankings "Last Week", Team › Schedule). The result carries the meaning, not a colour.
- **▼ deltas** everywhere: neutral (`--delta-down` is `--text-87`). Never red.
- **▲ deltas** on result and weekly surfaces: ▲ at `--text-100`, ▼ at `--text-60`. On data chips (Office "Moved most", box-score attribute chips, Player › attribute changes, the Office recruiting wire) ▲ is green as positive data (`--delta-up`).
- **The rail count badge**: a white plate (`--badge`) with dark ink (`--badge-ink`); the urgent pulse stays.
- **Blocking to-dos**: the Office blocking step and its "Blocks Advance" tag are a neutral strong outline (`--white-62`) and an outlined tag; the words carry the meaning.
- **Modal accents**: a functional modal's accent is neutral by default (`--white-14` hairline). A modal opts in to a colour with a modifier.
- **"Stay" / keep editing** in a leave-confirm: a neutral primary (white plate), never orange: it saves nothing.
- **Navigation-only buttons** (Sub Players, Back, Continue to Office, Full standings).
- **The recruiting presence dot** and the button on a reward modal.

**Data palettes outside the table.** These are data, so the table's "one colour, one meaning" does not recolour them. None of them is chrome, and none is a token:

- The rating ramps and the other ramps in [Data scales](#data-scales), including the shot-share ramp.
- **Live-court game-state colours**: Playcall Center state, the reveal HUD, the lower-third and secondary ribbons, the active-player HUD, momentum bars, the scoreboard quarter, shot clock and timeout pips, and the sim broadcast palette. They are game presentation and are not recoloured. The list and the build rules are in UX_System, "Live-game screen chrome".

**Annotation.** In a new-design file, a legal green, orange or gold that the checker's selector allow-list does not already cover needs `/* colour-law: positive-data */`, `/* colour-law: committed */`, `/* colour-law: saved */` or `/* colour-law: reward */` on the same line or one of the two lines above. `saved` and `committed` mean the same. The annotation records an exception the table already allows; it never licenses a banned use. Legacy files are reported, not failed; the new-design surface is listed in UX_System §8. The legacy court chrome also carries `/* colour-law: game-state */` and `/* colour-law: team-identity */`. Those two document an exemption for readers; the checker does not read them.

## Data scales

**Attributes** show the first digit: `floor(raw / 10)` via `js/utils/attributeDisplay.js`. Raw has a minimum of 1 and no upper cap in game (105 shows 10, 160 shows 16). Team Builder caps raw at 99. A missing value shows `--`, never 0.

| Display digit | Tier | Token |
|---|---|---|
| 0–4 | low | `--tier-red` |
| 5–6 | mid | `--tier-yellow` |
| 7–8 | high | `--tier-green` |
| 9+ | elite | `--tier-blue` |

Tiles (`js/shared/attrTiles.js` + `css/attr-tiles.css`), bars and chips all use this one scale. No surface builds its own tile or its own bands.

**RT** is a letter grade at the display boundary only (`formatRtDisplay()` in `js/shared/rtBucket.js`; backend prose `BackEnd/utils/rt_display.py`). Storage, sorting, filters and the sim stay numeric. Same scale for players and recruits of every year.

| RT | Grade | Tier | Class |
|---|---|---|---|
| 80+ | A, A+ (90+), A++ (100+) | `--tier-blue` | `.rt-elite` |
| 60–79 | B, B+ (70+) | `--tier-green` | `.rt-high` |
| 40–59 | C, C+ (50+) | `--tier-yellow` | `.rt-mid` |
| below 40 | D (30+), F | `--tier-red` | `.rt-low` |

Development deltas stay numeric (`+6 RT`). Minimum-RT controls show threshold and grade together (`75 (B+)`).

**Other ramps** (data, so tier colours are allowed):

- Chemistry: 0–8 `--tier-red`, 9–16 `--tier-yellow`, 17–25 `--tier-green`. Track stays neutral.
- Energy / readiness: high `--green` (annotated), then `--yellow`, then an amber `color-mix()`, then `--red`. Never raw `--orange`.
- Team measures (−20…+20): the diverging pill `.dv`, neutral white fills, zero in the centre. Place bars are neutral white, not navy.
- Shot share (Expected Shot Distribution, shot weights; `getPswColor()` in `common.js`): four bands by share of shots. Above 35% blue, 21–35% green, 11–20% gold, 10% and below red. A self-contained data ramp, and the one place blue is not RT. Its values live in the helper, not in tokens. The playbook CMD bands (`css/playbook-cmd.css`: blue, green, yellow) were kept by the same ruling.
- Deltas: `--delta-up` (green) marks ▲ on data chips; `--delta-down` is neutral (`--text-87`), so ▼ is never red; `--delta-flat` is `--text-60`.
- Attitude (Office Team snapshot, buckets 0–19 … 80+): red, muted red, neutral, green-mix, green. No orange stop.

**Display text.** Class year is always a two-letter uppercase abbreviation (`FR`, `SO`, `JR`, `SR`, `GR`, `JH`; unknown `--`) via `playerYear.js` / `BackEnd/utils/player_year.py`. Team names show exactly as stored in `teams.name`: no title-casing, no hyphen stripping, no exception map. Team measures use one vocabulary of eleven measures; Momentum is never shown on Team Attributes, the Training Report Team Report or Office "Moved most". `pt_efficiency` is P/T Defense and `pt_opp_modifier` is P/T Offense everywhere.

## Typography

Two self-hosted families. No Google Fonts link.

- `--font-display` (Bebas Neue Pro, weight `--fw-bold`): page titles, card and column headings, big numbers, scores, tabs, and every button.
- `--font-body` (Inter): body copy, data, table cells, labels, metadata.
- Numerals are tabular everywhere (set on `.gob`).

Roles (sizes are density tokens; they grow at `.gob-1920`):

| Role | Family | Size | Line / tracking | Use |
|---|---|---|---|---|
| score | display | `--fs-48` | `--lh-9`, `--tracking-1` | result card score |
| display-lg | display | `--fs-40` | `--lh-85`–`--lh-9` | tournament round, points remaining |
| display-md | display | `--fs-32` | `--lh-9` | page title, opponent name, stat-line numbers |
| display-sm | display | `--fs-28` | `--lh-9` | what-moved values, tier team names |
| heading-col | display | `--fs-20` | `--lh-1`, `--tracking-7` | column headers |
| heading-card | display | `--fs-16` | `--lh-1`, `--tracking-8`, `--text-60` | card titles |
| button | display | `--fs-18` | `--lh-1`, `--tracking-btn` | Advance and buttons (`--tracking-btn-sm` small) |
| tab | display | `--fs-16` | `--lh-1`, `--tracking-4` | sub-tabs |
| body-strong | body `--fw-semibold` | `--fs-14` | `--lh-body` | to-do labels, headlines |
| body | body `--fw-regular`–`--fw-medium` | `--fs-13` | `--lh-body` | default, names in lists |
| meta | body `--fw-medium` | `--fs-11` / `--fs-12` | `--text-60` | metadata, links |
| micro-label | body `--fw-bold`, uppercase | `--fs-10` | `--tracking-8` / `--tracking-10`, `--text-60` or `--text-38` | eyebrows, table headers |

Text colour is one of four opacities: `--text-100` display, `--text-87` primary, `--text-60` secondary, `--text-38` disabled / tertiary.

## Spacing, radius, elevation, motion

**Spacing.** `--space-*` (1–24) is fixed and never scales: chrome and controls. `--dsp-*` (4–24) scales with density: card padding, row and column gaps. `--dsz-*` are density-scaled component sizes (row heights, chip heights, avatars). Shell sizes: `--top-h`, `--rail-w`, `--page-pad`, `--col-gap`.

**Radius.** Chip / tag `--radius-4`–`--radius-6`; row, cell, button `--radius-10`; card `--radius-card`; shell `--radius-shell`; team logos `--radius-logo`; dots `--radius-round`. Player headshots are square: `--radius-6` on 28–46px table and list badges, `--radius-10` on large portraits. Never a circle; never more than a quarter of the side.

**Elevation.** Surfaces step up `--bg` → `--surface-1` → `--surface-2` → `--surface-3`, always blue-black, never grey. That includes the live-game side panels: `--surface-2` panel, `--surface-1` nested box and table head. Page area `--bg-page`, chrome `--bg-chrome`, sticky head `--bg-page-solid`. Shadows: `--shadow-card` (cards), `--shadow-popover` (toasts, popovers), `--shadow-panel` (settings panel), `--shadow-scoreboard`, `--shadow-logo`, `--shadow-advance` (Advance only), `--shadow-tier` (tier card only). Scrim `--scrim`. Layers: `--z-raised`, `--z-sticky`, `--z-sticky-head`, `--z-popover`, `--z-scrim`, `--z-panel`, `--z-modal`.

**Motion.** Press `--dur-press`, hover `--dur-hover`, toggle `--dur-toggle`, tab `--dur-tab`, rail `--dur-rail`, panel `--dur-panel`, arrivals `--dur-arrive-card` / `--dur-arrive-item` with `--stagger` / `--stagger-chip`, pop `--dur-pop` with `--ease-pop`, count-up `--dur-count`, exceptional-gain sweep `--dur-gain-sweep` (once), pulse `--dur-pulse`, skeleton `--dur-skeleton`. Default easing `--ease-out`. Motion never blocks pointer events. `prefers-reduced-motion` shows final states with no movement. No spinners.

## Components

Every reusable control defines default, hover, active (press), selected, disabled and, where it can be dead, dead. Focus is a 2px `--white` outline (`:focus-visible`).

### Buttons

All buttons: `--font-display` bold, `--tracking-btn`, `--radius-10`, height `--dsz-40`, `--space-20` side padding, minimum width 138px. Hover lifts 1px and brightens; press drops 1px and darkens slightly (`--dur-press`); disabled is `--white-6` fill, `--text-38` text, `not-allowed`, no lift, and shows its reason next to it or in its title. No lock icon, no hint link.

| Role | Class | Fill / ink | Rule |
|---|---|---|---|
| Gate (Advance) | `.advance`, `.gob-btn--gate` | `--green` / `--bg`, `--shadow-advance` | One per screen. A blocking task changes its label; it never disables it. Loading: `.is-loading`, label `STARTING…`, repeat clicks ignored. Submit Training is the training page's gate. |
| Action (save) | `.gob-btn--action` | `--orange` / dark ink | Only for a save or commit, and only while there is something to save (a page save is neutral at rest and after saving). |
| Neutral | `.gob-btn` | transparent fill, `--white-28` border, `--text-100` | Navigation, Retry, Autoset, every other button. |
| Ghost | `.gob-btn--ghost`, `.btn-ghost` | `--white-5` fill, `--white-18` border | Secondary, dismiss, acknowledgement. |

**Back / return** is a ghost text link, not a filled button: small left arrow plus label, left-aligned above the content, `--text-60` resting, `--text-100` on hover. A back that only returned to the locker room is hidden under the shell (the rail replaces it).

**Sticky action bar.** A page with a primary or save button keeps it on screen while the page scrolls (in the sticky page head or an action bar).

### Tabs

Sub-tabs (`.stab` in `.pg-head .subtabs`): parallelogram (`clip-path`), height 40px, tab type role. Default `--white-6` fill, `--white-55` text; hover `--white-11`, `--white-90`; selected `.on` `--white-9`, `--white` text and a 2px `--white-70` top edge; disabled `--text-38`, `not-allowed`, not focusable, title says when it opens. Never blue, navy or team colour. Two levels only (rail, then sub-tab). Segments (Top 25 / All, Conference / National) follow the same neutral states.

### Tables

`.rtab` / `gob-tables.css` inside a contained card (`--white-2`, `--radius-12`). Header: sticky where the table fits `.main`, `--surface-th-top` → `--surface-th-bottom`, micro-label type at `--text-60`, `--line-strong` under it. Rows: `--line` separators only (no boxed cells), even rows `--white-1p2`, hover `--white-5`, your row navy (`tr.me`). Grouped columns `--group-shade`. First (name) column left-aligned and heavier; numbers centred. Linked names are not underlined at rest. A table wider than `.main` scrolls inside its card with an edge fade and no sticky header. Never white zebra stripes, never spreadsheet gridlines.

### Modals

One modal at a time, toggled with `.is-visible`, above everything at `--z-modal`. Surface `--surface-popover` family, border `--white-12`, `--radius-card`, `--shadow-popover`, scrim `--scrim`. Title in the display face, copy in body `--text-60`.

| Type | Use | Rule |
|---|---|---|
| Functional | Confirmations, warnings, settings, leave-with-edits, destructive actions | Max 420px. Esc and backdrop dismiss. Two actions: primary `flex: 2`, secondary `flex: 1`. One action: full-width ghost. Action-only variant (no title, stacked equal buttons) must be answered; no backdrop dismiss. Accent neutral by default. A "Stay" primary is a neutral white plate. Red only on an irreversible delete (red-outline confirm; Cancel takes focus). |
| Moment | Milestones and season peaks (`.mm`, season-peak template), big news, results | Max 560px (720px only for tabular content). Requires a button, and the button is neutral (ghost or a neutral plate), never gold. Outcome is the hero. Gold only on reward tiers, as art: emblem, eyebrow, rule, title glow. Elimination is quiet (fade, no gold, no sound). The server names the style and sting. |
| Strategic | In-game decision points (defense matchups, timeouts, foul-outs) | Wide (up to 1160px). Requires an explicit submit. Data is the hero; muted title. Team colour only as identification on panel headers. The one forward action is green; skip is a low-weight checkbox or ghost link. |
| Tutorial | Coach Sammy lesson alerts (`gob-tutorial.css`) | Full-screen takeover card, neutral: white "Start lesson" primary, no orange. |

### Toasts

`GOBToast.show(text)` (`.gob-save-toast`, `css/gob-toast.css`): one short line, neutral chrome (`--surface-popover`, `--shadow-popover`, `--text-87`), no icon, no orange, no green. Fixed over the centre of `.main`, `--dsp-24` above the bottom, never shifts layout. Fades after 1.5s; a second call restarts the timer instead of stacking. A failed save uses the same toast with a short retry line. Toasts replace success modals whenever no decision follows.

### Headshots and logos

Player headshot: square with a small corner, photo, monogram or placeholder alike. `.av` and list badges `--radius-6` on `--surface-3`; `.portrait` `--radius-10`; image `object-fit: cover`. Team logos and initials badges are not headshots: `--radius-logo`, `--shadow-logo`.

### Chips, pills and badges

`.chip` (`--radius-6`, `--dsz-20` high, micro type). Data chips may carry a tier or delta token; choice and filter chips are neutral (default `--white-6`, selected `--white-9` with `--text-100`). The rail count badge is a neutral white plate (`--badge` / `--badge-ink`); the recruiting presence dot is a dot, not a count, does not pulse, and is neutral (`--text-100`, never orange or green). Meters (`.meter`) are neutral unless they show a data ramp.

### Empty states

`.gob-empty`: one neutral card. `--white-2` fill, 1px `--line` border, `--radius-10`, body text `--text-60` at `--fs-14`. No icon, no colour, one short sentence. It is the only empty-state look; where to use it is in UX_System, "Empty states".

### W/L plates

`.wl`: display face, `--radius-6`, `--dsz-22` high. WIN is a white plate; LOSS is an outline with no fill. Never green or red. Table letters (`.gob-wl.up` / `.dn`, Rankings and Team › Schedule) use the same plate and outline.

## Never do

- A hex, `rgb()` or `rgba()` value in a page, component or doc. Name the token.
- A second green control on a screen, or green on anything that is not Advance or positive data.
- Orange on anything that is not an unsaved change (a save or commit).
- Gold outside the six reward surfaces, or on any button.
- Blue on chrome, links or navigation; navy as a data colour or page background.
- A team-colour wash or tint on a card, panel, tab or header, or team colour as a control's selected state.
- Red on a ▼, a LOSS, a modal accent, or any button except the irreversible-delete confirm.
- A grey surface. Surfaces are the blue-black `--surface-*` steps, on the court too.
- A circular player headshot.
- A spinner, a disabled-with-lock Advance, or a hint link.
- A third navigation level.
- Page-local rating bands, a recomputed attribute or RT tier, or a renamed team.
- Momentum on a team-measure surface.

## Settled 2026-10-01

Jamie's rulings (`reports/jamie-decisions-2026-10-01.md`) and the same day's gallery fixes. The rule itself is in the section linked; how each was built is in UX_System, "Settled rulings".

| Ruling | Settled as | Lives in |
|---|---|---|
| Navy for selected items | Navy marks "yours" and what you picked for your team or plan, with a `--navy-hi` edge. It is not a generic selected colour. | [Colour law](#colour-law), Navy row |
| Shot-share ramp uses blue | Kept: a self-contained data ramp. | [Data scales](#data-scales), Other ramps |
| Live-court game-state colours | Kept: data, game presentation, not recoloured. | [Colour law](#colour-law), Data palettes outside the table |
| Court side panels | Blue-black surfaces, not grey. | [Spacing, radius, elevation, motion](#spacing-radius-elevation-motion), Elevation |
| Court stat toggles | Neutral selected state, not team colour. | [Colour law](#colour-law), Team colour row and Choice controls |
| Senior-tribute title marks | Reward gold: the sixth reward surface. | [Colour law](#colour-law), Reward gold row |
| Recruiting presence dot | Neutral. | [Chips, pills and badges](#chips-pills-and-badges) |
| Gold button on the big-news modal | No gold on any button; a neutral plate. | [Colour law](#colour-law), Reward gold row; [Modals](#modals) |
| Submit Training | Green: it is the training page's Advance. | [Colour law](#colour-law), Green row; [Buttons](#buttons) |
| Empty views and boards | One neutral card. | [Empty states](#empty-states) |
| Franchise Set Lineup opens with five empty slots | By design. Behaviour, not look. | UX_System, "Set Lineup" |
| Duplicate pages, desktop icon | Done; not a look rule. | UX_System, "Settled rulings" |

Done since (ux/logo-fallback-save-state):

- Save buttons stay neutral until something has changed; orange only when there is something to save. The Orange row and the Action button role now say so.
- Team art: a missing `logo_square` falls back to `logo_primary` before the generated letter tile (UX_System, "Rulings recorded 2026-10-01").

## Settled 2026-10-01 (batch 2)

Jamie approved every recommendation in `reports/jamie-decisions-2-2026-10-01.md`. Net rule: **orange = "there are unsaved changes" and nothing else.** Built on `ux/jamie-rulings-batch-2`; the checker's orange selector allow-list is now save / commit only.

| Ruling | Settled as | Lives in |
|---|---|---|
| Delta chips | ▲ green on data chips (positive data); ▼ neutral everywhere. No red. | [Colour law](#colour-law), Neutral by rule; [Data scales](#data-scales) |
| W/L in tables | White WIN plate, outlined LOSS, everywhere. | [W/L plates](#wl-plates) |
| Rail count badge | Neutral white plate. | [Chips, pills and badges](#chips-pills-and-badges) |
| `.td-gate` tag, `.is-on` selections | Neutral; off the checker's orange allow-list. | [Colour law](#colour-law), Orange row |
| Office blocking-step outline | Neutral strong outline. | [Colour law](#colour-law), Neutral by rule |
| Attitude bars | No orange stop: red, muted red, neutral, green. | [Data scales](#data-scales) |
| Functional-modal accent default | Neutral. | [Modals](#modals) |
| Tutorial alert | Neutral (confirmed). | [Modals](#modals) |
| Leave-confirm "Stay" | Neutral primary. | [Modals](#modals) |
| Weekly / result card wash | None; the dead `.office-res` styling is deleted. | [Colour law](#colour-law), Team colour row |
| Destructive actions | Red outline only for irreversible deletes (Home Base delete program); everything else neutral. | [Colour law](#colour-law), Red row; [Modals](#modals) |

## Open questions

1. **Navy aliases.** `--you`, `--you-soft`, `--you-line`, `--you-ink`, `--you-edge` are defined locally in `recruiting-spine.css`, not in `gob-tokens.css`, yet UX_System cites them. Promote to tokens?
2. **RT colours.** `rtBucket.js` and `css/rt-buckets.css` carry their own colour values, and RT elite uses the `--blue` value, not `--tier-blue` (which exists for contrast). Point RT at the tier tokens?
3. **Canonical button CSS.** `css/gob-buttons.css` still hard-codes the old values and labels orange as "advances UI". The shell buttons in `gob-components.css` are tokenised. Retokenise `gob-buttons.css` to match this guide?
4. **Position colours** (PG/SG/SF/PF/C) have no tokens. Tokenise, or keep as game presentation? (The broadcast palette and the other game-state colours are settled: kept as game presentation, in code.)
5. **Tier digit ceiling.** The token comment says the player digit runs 0–16; `attributeDisplay.js` says there is no upper cap. Which is right?
6. **Repo CLAUDE.md** still says the colour law lives in UX_System. Update it to point here?
7. **Annotated orange that may not be a save.** Since batch 2 the checker allows orange by selector only on save / commit names. These still pass through a `/* colour-law: committed */` annotation and may not mean "there are unsaved changes":
   - toasts (`.hub-toast` in `recruiting-dock.css`, `.toast` in `training-playbooks.css`), which the Orange row bans;
   - a choice control (`.tsr-toggle .toggle-btn.active`, `training-squad-report.html`);
   - recruiting board and signing marks (`.pool tbody tr.rec.on-board`, `.pool-rankbadge`, `.citem`, `.hub-anchor--orders .ic`, `.prow.flash`, `.ssum-lr`, `.ssum-nm b`);
   - `.gob-btn--action` used as a CONTINUE (the username modal, which saves the username, and the Game Plan tutorial CTA).

   Audit each, keep or neutralise?
