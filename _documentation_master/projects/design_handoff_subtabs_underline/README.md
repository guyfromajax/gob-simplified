# Handoff: GOB — Section sub-tab row · Direction A "Underline"

## Overview
Replaces the section sub-tab row in the franchise app shell (every section page: Team, Prep, League, Recruiting, News). Today's row is slanted, filled parallelogram tabs (`.stab`) with a thin top-border active state. It sits on a large rounded outer card that contains a second bordered card. The new row is plain display-face text tabs with a 2px sliding underline on one full-width hairline, and **no card around the head**. Right-aligned page tools (`.seg`, `.search`) keep sharing the row.

Goal: quiet, premium navigation that lets the content lead. **Only the tab row and its page head change.** The tables, tools, top bar and rail stay as they are.

## About the design files
`reference/Subtab Underline.html` is a **design reference built in HTML**, not production code. It shows the intended look and behaviour. Recreate it in the existing codebase using its current structure, patterns and files. `reference/subtabs.css` and `subtabs.js` contain all three explored directions. **Only the shared `.sx` rules and the `.dA` rules apply.** Ignore `.dB`, `.dC` and the `.sheet` spec-sheet styles.

Open `reference/Subtab Underline.html` in a browser to see:
- two live 1280×720 frames (Team › Roster, League › Standings);
- a spec sheet with every state, all five sections, the overflow ladder and the keyboard map.

## Fidelity
High fidelity. Colours, type, spacing, states and motion are final and use existing tokens from `tokens.css` (Round 2 / browse templates). **No new design tokens.** One new local custom property (`--pg-head-h`, below) is derived from existing tokens.

## Rules for the implementing agent (read first)
1. **Before writing any code, report back:**
   - which files own the section page head, the sub-tab row (`.pg-head`, `.subtabs`, `.stab` or their production equivalents) and the rounded outer card / inner bordered card that currently wrap it;
   - which files own the page tools (`.seg`, `.search`) and the sticky table header offset (`--th-top` / `--dsz-118`);
   - the **production sub-tab list for every section** and how a locked tab (Tournament) is determined today;
   - which data fields exist for everything in **Data needed** below.
2. **Never invent, derive or approximate a missing field.** If something has no backing field, stop and ask. This includes the Tournament unlock week: do not hardcode "27".
3. **Don't micromanage what already works.** Keep existing `.seg` / `.search` components, their copy and counts, existing colour scalings (RT ramp, energy ramp, shot weight), the top bar, the rail and the tables.
4. **All sample values in the reference are illustrative:** names, crumbs ("Week 22 · next game Saturday"), counts, tooltip copy, tab lists, placeholder text, initials and letter logos. Only structure, tokens and behaviour are specified.
5. **Colour:** the row is entirely neutral white. No green (reserved for the top-bar Advance), no navy (reserved for the user's own team/player selection), no blue (reserved for RT A / attribute 9+), no orange.

## What changes
- **Remove** the parallelogram `.stab` styling (clip-path, `--white-6` fill, top-border `::before`).
- **Remove** the large rounded outer card and the inner bordered card around the page head. The head sits directly on `.main`'s page background. The table keeps its **single** `.tcard` (1px `--line`, radius 12); there is no second wrapper.
- **Add** the underline tab row, overflow ("More") menu, collapsible search and keyboard model described below.
- **Update** the sticky page head height, and the table header offset (`--th-top`) to match.

## Layout — page head `.pg-head` (T1/T2 section pages)
```
.pg-head  sticky · top 0 · z --z-sticky-head · background as today (bg-page-solid → bg-page gradient)
├─ .pg-title       unchanged: h1 Bebas 700 fs-32 t100 · crumb Inter fs-12 t60, baseline-aligned, gap 14
│   (gap: --space-12)
└─ .nav-row        flex · align-items:center · gap --space-24 · height --dsz-44 (44 / 52)
   │               box-shadow: inset 0 -1px 0 var(--line-strong)   ← full-width hairline, runs under the tools too
   ├─ .tabs        role=tablist · flex · gap 26px · height 100% · position:relative
   │   ├─ .tb × n  role=tab
   │   ├─ .more-w  (hidden unless overflowing) → button.tb.more + .mmenu
   │   └─ .ink     the 2px selection underline (absolute, bottom 0)
   └─ .pg-tools    margin-left:auto · flex:none · gap --space-10 · existing .seg / .search, vertically centred
```
**Head height:**
```css
--pg-head-h: calc(var(--page-pad) + var(--fs-32) + var(--space-12) + var(--dsz-44) + var(--dsp-8));
/* 1280 → 18+32+12+44+8 = 114px    1920 → 28+38+12+52+9.5 ≈ 139.5px */
.pg-head{height:var(--pg-head-h)}
.tbl{--th-top:var(--pg-head-h)}
```
There is 8px (`--dsp-8`) of air between the hairline and the table card. At 1280 the head shrinks from 118px to 114px. At 1920 it stays ≈139px.

Detail pages (T3, `.dt-bar`) have no sub-tabs and are **not affected**.

## Components
### Tab `.tb` (an `<a>` or `<button>`, `role="tab"`)
| Property | Value |
|---|---|
| Font | `--font-display` (Bebas Neue Pro) 700 · `--fs-17` (17 / 20) · line-height 1 · letter-spacing `--tracking-5` (.05em) |
| Box | height 100% of row · padding 0 × `--space-2` · no min-width · no fill · no radius · `white-space:nowrap` |
| Rest | `--text-60` |
| Hover | `--text-87` + 1px `--white-30` underline preview at the row's bottom edge (`::after`, full label width). Not on the selected or locked tab. |
| Selected | `--text-100` · `aria-selected="true"` · the `.ink` sits under it |
| Press | no extra state (pages switch instantly) |
| Keyboard focus (`:focus-visible` only) | 2px `--white` ring (`box-shadow:0 0 0 2px`), radius `--radius-6`, inset from the label box: left/right −6px, top/bottom `--space-8`. No outline on mouse click. |
| Locked | `--text-38` · `cursor:not-allowed` · 12×12 lock icon after the label (gap `--space-6`, stroke 2) · `aria-disabled="true"` (**not** `disabled`: it stays focusable) · tooltip on hover and on focus |
| Transition | `color --dur-hover` (120ms) |

### Selection ink `.ink`
- Absolute, `bottom:0`, height 2px, radius 1px, background `--text-100` (white). It sits on top of the hairline.
- Width = the selected tab's width. Position = `translateX(tab.offsetLeft)`.
- **Slides** between tabs: `transform` + `width`, `--dur-tab` (160ms), `--ease-out`. No transition on first placement, so it doesn't animate in on page load. Under `prefers-reduced-motion`, no transition (the existing global rule covers this).
- Recompute on tab change, row resize and font load.

### Locked tooltip `.ltip` (`role="tooltip"`, referenced via `aria-describedby`)
- Below the tab (top: 100% + `--space-6`), centred. Padding `--space-10` × `--space-12` · radius `--radius-10` · `--surface-popover` · `--shadow-popover` · nowrap · z `--z-popover`.
- Title: Bebas 700 `--fs-16` tracking-4 t100, e.g. "Locked until Week 27". Body: Inter 400 `--fs-12` t87, e.g. "Tournament opens when the regular season ends." **Copy is illustrative, and the week comes from data.**

### Overflow menu — button `.tb.more` + `.mmenu`
- Button: same styling as `.tb`, label "More" + 14px chevron-down (rotates 180° when open, `--dur-toggle`). `aria-haspopup="menu"`, `aria-expanded`. When open: t100.
- Menu: absolute, top 100% + `--space-6`, anchored to the More button's right edge (flip left if it would leave the content area). Min-width 212 · padding `--space-6` · gap `--space-2` · radius `--radius-10` · `--surface-popover` · `--shadow-popover` · z `--z-popover`.
- Item `.mi` (`role="menuitem"`): height 34 · padding 0 × `--space-10` · radius `--radius-7` · Bebas 700 `--fs-16` tracking-4 t87. Hover or focus: `--white-6` background + t100. Keyboard focus: 2px inset `--white` ring. Locked item: t38 + lock icon + right-aligned meta, Inter 500 `--fs-11` t38 ("Unlocks Week 27").

### Collapsed search `.sbtn`
- Replaces `.search` when space runs out. Square button: `calc(--dsz-28 + 6px)` (34 / 39.5) · radius `--radius-9` · `--white-4` · inset 1px `--line` · 15px search icon t60. Hover: `--white-6` background + t87. Focus: 2px `--white` outline, offset 1px.
- `aria-label` = the field's placeholder (e.g. "Find a team").

### Page tools
Unchanged `.seg` and `.search` from `templates.css`. Selection in `.seg` stays neutral white (browse-templates decision 5).

## Interactions & behaviour
### Switching
Click (or keyboard, below) selects the tab and switches the page instantly, as today. The ink slides. The URL/route updates as today. A locked tab does nothing on click or Enter; only its tooltip shows.

### Keyboard (WAI-ARIA tabs pattern, automatic activation)
| Key | Behaviour |
|---|---|
| Tab | Lands on the **selected** tab (roving tabindex: selected tab `tabindex=0`, others `-1`), then moves on to the tools |
| → / ← | Move focus to the next / previous visible tab (wraps) **and select it**. Pages switch instantly, so selection follows focus. A locked tab receives focus (its tooltip shows) but is not selected. |
| Home / End | First / last visible tab (including More) |
| Enter / Space / ↓ on More | Open the menu, focus the first item |
| ↑ / ↓ in menu | Move between items · Enter/Space selects (not on a locked item) · Esc closes and returns focus to More · click outside closes |
| / | Focus search. If it is collapsed, expand it first (see overflow step 3). Esc clears (existing behaviour). |

### Overflow: measured, never by breakpoint
Run on mount, after fonts load, and on every row resize (ResizeObserver on `.nav-row`). The row overflows when `scrollWidth > clientWidth`.
1. Reset: all tabs visible, More hidden, search expanded.
2. If the row overflows, **collapse search** to `.sbtn`.
3. If it still overflows, show **More** and fold tabs into it **from the end**, skipping the selected tab. **The selected tab never folds.** Folded tabs keep their order in the menu.
4. **Search opened by the user** (click `.sbtn` or press "/"): the field expands in place and takes priority. Re-run the fit without step 2, so more tabs fold. When the field blurs while empty, collapse it again and re-fit.

Measured at 1280 (content width 1170):
- Team, Prep, Recruiting and News fit with room to spare.
- League › Standings (7 tabs + scope segment + search) **fits as-is**.
- League › Team Stats (7 tabs + 2 segments + search) collapses search to the icon and then fits.
- Tabs fold into More only when the user shrinks the window below 1280.

### Motion
Ink slide: `--dur-tab`, `--ease-out`. Colour: `--dur-hover`. Chevron: `--dur-toggle`. Nothing animates under reduced motion.

## State
- `selectedTab` per section: already exists in routing. Don't duplicate it.
- `overflowedTabs[]` and `searchCollapsed`: derived from measurement, never stored.
- `searchOpen`: UI-only; true while the user has expanded a collapsed search.
- `menuOpen`: UI-only.

## Data needed (confirm each exists — do not invent)
- **Tab list per section**, in production order. The reference uses: Team (Roster · Player Stats · Team Attributes · Schedule), Prep (Training · Game Plan · Playbooks · Scouting Report), League (Standings · Rankings · Leaders · Team Stats · Schedule · Practice Squad · Tournament), Recruiting (Pool · Leans · Visits), News (News · Awards). This supersedes the placeholder lists in the browse-templates handoff (decisions 15/16), but **the production list wins** if it differs. Report any mismatch.
- **Locked state + unlock condition** for Tournament: the current week and the week it unlocks (the reference shows Week 27). If there is no field, stop and ask.
- **Crumb text** per section: keep whatever production shows today. The reference crumbs are illustrative.
- Segment counts (e.g. Varsity 12 / Practice Squad 3): existing fields, unchanged.

## Accessibility
- `role="tablist"` + `aria-label="<Section> sections"`; `role="tab"` + `aria-selected`; the tab panel has `role="tabpanel"` + `aria-labelledby` (use existing page structure where possible).
- Locked: `aria-disabled="true"` + `aria-describedby` → tooltip.
- Contrast on `--bg-page-solid`: rest t60 ≈ 7:1 ✓, locked t38 is a disabled state (exempt, and the lock icon and tooltip carry the meaning).

## Design tokens used (all existing)
`--text-100/87/60/38` · `--white-30` (hover preview) · `--white-4/6` · `--white` (focus) · `--line` · `--line-strong` (hairline) · `--surface-popover` · `--shadow-popover` · `--font-display` · `--fs-11/12/16/17/32` · `--tracking-4/5` · `--space-2/6/8/10/12/24` · `--dsp-8` · `--dsz-28/44` · `--page-pad` · `--radius-6/7/9/10` · `--dur-hover/tab/toggle` · `--ease-out` · `--z-sticky-head/popover`.

## Assets
Icons: inline 24×24 stroke SVGs, `currentColor`, round caps/joins. Lock (stroke 2): `<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/>`. Chevron-down (stroke 1.8): `M6.5 9.5L12 15l5.5-5.5`. Search: the existing browse-templates icon. Use the codebase's icon set if it has equivalents at the same size and weight.

## Decisions to confirm
1. Removing the outer rounded card and the inner bordered card around the head, keeping one `.tcard` around the table.
2. Head 118 → 114px at 1280 (≈ unchanged at 1920) via `--pg-head-h`.
3. Automatic activation on arrow keys (selection follows focus), since pages switch instantly.
4. Locked tabs stay focusable (`aria-disabled`) so the unlock reason can be reached by keyboard.
5. Collapse order: search first, then trailing tabs. The selected tab is never folded.

## Files
```
README.md                         this spec
PROMPT.md                         paste-in brief for Claude Code
reference/Subtab Underline.html   live reference: 2 frames at 1280×720 + states / sections / overflow / keyboard sheet
reference/subtabs.css             row CSS — use shared .sx rules + .dA only
reference/subtabs.js              reference behaviour: fit/overflow, ink, keyboard, More menu, search collapse
reference/tokens.css · components.css · templates.css · fonts/   browse-templates files, unchanged (for the reference to render)
reference/shell-chrome.js · roster-table.js · standings-table.js   sample markup for the reference only
```
