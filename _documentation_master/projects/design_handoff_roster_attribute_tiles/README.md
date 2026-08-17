# Handoff: Roster & Recruiting attribute-tile redesign

## Overview

The 12 player attributes recently changed from plain numbers to colored tiles (`attr-tiles.css` +
`js/shared/attrTiles.js`). The tiles are good, but the surfaces that host them were laid out for
numbers, so the rows now read as disjointed: sparse text columns, then a dense 12-tile block, then a
lone unlabeled `RT` far to the right.

This package redesigns the three surfaces that show the tiles in a table, so the tiles become the
row's visual spine instead of an intrusion:

1. **`team-roster-view.html`** — the standalone team roster page.
2. **FCC → Roster tab** (`franchise-command-center.html#roster-tab`).
3. **FCC → Recruiting tab** (`franchise-command-center.html#recruits-tab`).

Nothing else that displays attributes is in scope. The Recruiting Hub pool screen
(`recruiting.html`) is deliberately excluded from this pass.

## About the design files

The files in this bundle are **design references created in HTML** — prototypes showing the intended
look and behavior. They are **not production code to copy**. They use fixture data, vanilla DOM
rendering, and a React-based Tweaks panel that exists only for design review.

Your task is to **implement these designs inside the existing GOB frontend** — plain ES5-ish classic
scripts, per-page CSS files, `window.GOB_*` shared modules, no bundler — reusing the shared
components already in the repo (`GOB_AttrTiles`, `getRtBucketClass`, `RecruitingSpine.Lean`,
`renderProjectedStartingFiveCards`, `initAttributeTooltips`).

Repo: `guyfromajax/gob-simplified`, branch `develop`, all paths under `FrontEnd/static/`.

## Fidelity

**High-fidelity.** Colors, type, spacing, and interaction states are final. Every frame value in the
FCC mock was lifted from `franchise-command-center.css` verbatim — match the mock pixel-for-pixel,
and where the mock and the production stylesheet agree, the production stylesheet is the source of
truth (don't re-declare what already cascades).

## The configuration that was approved

Both surfaces ship with these settings. The mocks expose them as a Tweaks panel for review; **ship
only the approved column, and do not build a user-facing settings UI for them.**

| Setting | FCC Roster + Recruiting | Standalone Team Roster |
| --- | --- | --- |
| Attribute grouping | Grouped in 6 pairs | Grouped in 6 pairs |
| Tile labels | In the header, not in the tile | In the header, not in the tile |
| Sticky header | Yes, on every surface | Yes, on every surface |
| Density | Compact | Compact |
| Row banding | (inherits FCC odd-row banding) | Zebra |
| RT placement | Beside the name | Beside the name |
| Position colors | **Off** | **Off** |
| Region + Archetype (Recruiting only) | Folded into the identity cell | n/a |
| Practice squad | Scope toggle, not a stacked table | Scope toggle, not a stacked table |
| Projected starting five | n/a | Kept, with headshots |

---

## Shared work (do this first)

### 1. Group the 12 tiles into 6 labeled pairs

The single biggest fix. Twelve identical tiles in one row read as a barcode. Grouped in pairs with a
label above each pair, the same row becomes six scannable chunks.

The pairs, left to right:

| Group label | Attributes |
| --- | --- |
| OFFENSE | SC, SH |
| DEFENSE | ID, OD |
| SKILLS | PS, BH |
| GRIT | RB, ST |
| BODY | AG, ND |
| MIND | IQ, FT |

**Do not reorder `ATTR_KEYS` in `js/shared/attrTiles.js`.** That array is exported as
`GOB_AttrTiles.ATTR_KEYS` and its order (`… RB, AG, ST, ND …`) is mirrored by
`SCOUTING_PROJECTED_ATTR_COLS` in `js/shared/scoutingReport.js` and by the backend
`roster_builder` ATTR_KEYS. Reordering it would silently shift the scouting modal and the projected-
five table.

Instead add a **presentation-only** constant beside it and a grouped renderer:

```js
// js/shared/attrTiles.js — additions, no changes to ATTR_KEYS
var ATTR_PAIRS = [
  ['OFFENSE', ['SC', 'SH']],
  ['DEFENSE', ['ID', 'OD']],
  ['SKILLS',  ['PS', 'BH']],
  ['GRIT',    ['RB', 'ST']],
  ['BODY',    ['AG', 'ND']],
  ['MIND',    ['IQ', 'FT']],
];

/** Grouped tile row. Same tiles, wrapped in 6 pair groups. */
function tilesGroupedHtml(attrs, opts) { /* .attr-tiles > .attr-pair * 6 > .attr-tile * 2 */ }

/** Grouped header: pair label + the two abbreviations as sort buttons. */
function tilesGroupedHeaderHtml(sortKey, sortDir) { /* … */ }
```

Keep `tilesHtml` / `tilesHeaderHtml` intact for any surface not in this scope.

### 2. Move the labels from the tile into the header

Today `tileHtml` emits `<u>SC</u>` inside every tile — the abbreviation repeats on every row, twelve
times per player. Call the tiles with `showLabel: false` on these three surfaces and print each
abbreviation **once**, in the header, above its column.

Tile stays exactly as `attr-tiles.css` defines it (tiers, radius, `data-tooltip`) — only `<u>` is
dropped. Hover still identifies the attribute via `initAttributeTooltips`, so nothing is lost.

### 3. Restore per-attribute sort

Collapsing 12 columns into one `<td>` removed 12 sort controls. The header abbreviations **are** the
sort controls now:

```html
<button class="attr-sort" data-attr="RB">RB</button>
```

- Click sorts by that attribute, descending first; click again toggles ascending.
- Active control gets `.is-sorted` and a caret (`▾` / `▴`) in `--orange` `#F79420`.
- Sort on the 0–10 display value (`GOB_AttrTiles.tileValue`), so ties behave the way the user sees them.

### 4. Make the header sticky on all three surfaces

`#roster-tab` already does this (`overflow-x: auto` on the tab panel, `position: sticky; top: 0` on
`thead th`, opaque `#262b34` base so rows don't bleed through). Extend the same treatment to the
Recruiting tab and to the standalone roster table. The grouped header is two lines tall, so the
opaque base matters more than before — verify no row shows through while scrolling.

### 5. RT becomes a labeled `current → potential` lockup

Today RT prints `B+/A` with a `data-tooltip="current/potential"` and sits at the far right of the
row, disconnected from the player. Change to:

```html
<th>RT<span class="rt-cap">cur → pot</span></th>
…
<td><span class="rt-lockup"><b class="rt-high">B+</b><i class="rt-elite">→ A</i></span></td>
```

- Current: `Bebas Neue Pro` 22px. Potential: Inter 600 11px at 62% opacity, prefixed with a dim `→`.
- Colors from `getRtBucketClass()` / `css/rt-buckets.css` — **do not** hardcode thresholds.
- Header caption: Inter 600 9px, `letter-spacing .08em`, uppercase, `rgba(255,255,255,.26)`.
- Position: immediately right of the player name, before POS/YR/HT/WT.

### 6. Drop position colors

The mock supports colored position chips and they were **rejected**. Render POS as the neutral chip:
`min-width 34px; height 21px; border-radius 5px; font: 700 10.5px/1 Inter; letter-spacing .06em;
color rgba(255,255,255,.86); background rgba(255,255,255,.07); border 1px solid rgba(255,255,255,.1)`.

No `--pos-*` color tokens. Delete them rather than leaving them unused.

### 7. Compact density

```css
--tile-w: 26px;   /* matches attr-tiles.css .attr-tile width */
--tile-h: 27px;
--pair-gap: clamp(7px, 1vw, 15px);   /* between pair groups */
--tile-gap: 2.5px;                    /* within a pair — attr-tiles.css value */
```

Row height follows from the FCC `td { padding: 9px 10px; font-size: 13px }` rule; don't set an
explicit row height.

---

## Surface 1 — FCC Roster tab

### Layout

Column order, left to right:

`Player · RT · POS · YR · HT · WT · Attributes (6 pair groups)`

- **Player** is a sticky left column (`position: sticky; left: 0`). It must carry its own opaque
  background because the FCC odd-row banding is on `<tr>`: `#262b34` for even rows, `#2a2f39` for
  odd, `#2f353f` on hover.
- Cell contents: jersey (Bebas 19px, `rgba(255,255,255,.26)`, right-aligned in a 26px box), then the
  name as a link (Inter 700 13.5px `#fff`), then any status flags.
- Everything else keeps the existing FCC table rules — `min-width: 1180px`, `th` padding
  `12px 10px 10px`, `td` padding `9px 10px` at 13px, odd-row `rgba(255,255,255,.03)`, hover
  `rgba(255,255,255,.04)`.

### Practice squad → scope toggle

**Remove `#training-squad-section`** — the second full table stacked below the first. Replace with a
two-button scope toggle on the header row that swaps the body of the single table:

```html
<div class="fcc-scope">
  <button data-scope="varsity" aria-pressed="true">Varsity <em>12</em></button>
  <button data-scope="squad" aria-pressed="false">Practice Squad <em>3</em></button>
</div>
```

Button chrome is the FCC control vocabulary: `min-height 34px; padding 0 14px; border-radius 8px;
border 1px solid rgba(255,255,255,.1); background rgba(255,255,255,.06); inset 0 1px 0
rgba(255,255,255,.06); color rgba(255,255,255,.62); Inter 600 12.5px`. Hover `background
rgba(255,255,255,.11); color rgba(255,255,255,.9)`. Selected (`aria-pressed="true"`)
`background rgba(255,255,255,.09); border-color rgba(255,255,255,.18); color #fff`.

The count in `<em>` is Inter 11px tabular-nums at `rgba(255,255,255,.26)`, `.55` when selected.

The same treatment applies to `#ps-stats-section` on the Player Stats tab — out of scope for this
pass, but note it so the two tabs don't drift.

### Header row

`<h3>Roster</h3>` stays outside the card (existing `.tab-content h3`, 30px, `letter-spacing .03em`).
Put the scope toggle immediately right of it, and a right-aligned group holding the row count
(Inter 700 12px, `letter-spacing .06em`, uppercase, `rgba(255,255,255,.5)`).

---

## Surface 2 — FCC Recruiting tab

### Layout

`Recruit · RT · POS · HT · WT · Attributes · Current Lean`

**Home Region and Archetype fold into the identity cell** as a sub-line under the name:

```html
<td class="c-name">
  <div class="recruit-ident">
    <a class="nm" href="…">Isaiah Frame</a>
    <span class="id-sub">Region A · <b>Slasher</b></span>
  </div>
</td>
```

- `.id-sub`: Inter 500 11px, `rgba(255,255,255,.62)` (this exact value — `.40` failed AA contrast at
  this size against the banded row). Archetype in `<b>`: 700, `rgba(255,255,255,.78)`.
- Region names are single letters product-wide, so they render as "Region A" … "Region H".

**This is a space decision, and here are the numbers.** Available content width inside the FCC panel
is `container − 88px` (36 container padding + 8 tab-strip padding + 44 panel padding), so **1312px**
at the 1400px container cap. Measured natural table widths:

| Variant | Natural width | Fits 1312? |
| --- | --- | --- |
| Roster tab | 967px | Yes, comfortably |
| Recruiting, folded identity | 1117px | Yes, ~195px spare |
| Recruiting, Region + Archetype as columns | 1325px | **No** |
| Recruiting, columns at compact density | 1260px | Barely |

Folding is what buys the room for the grouped tiles and the lean ladder to coexist without
horizontal scroll.

**Keep both sort keys.** Production declares `data-sort-key="homeRegion"` and
`data-sort-key="archetype"`. Folding must not delete them — render the sub-line's two words as sort
buttons in the header, under "Recruit":

```html
<th class="c-name">
  <span class="lbl">Recruit</span>
  <span class="sub-sorts">
    <button class="subsort" data-subsort="homeRegion">Region</button>·<button class="subsort" data-subsort="archetype">Archetype</button>
  </span>
</th>
```

Both sort ascending first (they're alphabetical). Styling matches `.attr-sort`: Inter 700 9px,
uppercase, `letter-spacing .08em`, `rgba(255,255,255,.5)`, white when active with the orange caret.

### Current Lean

Unchanged. Keep `RecruitingSpine.Lean.ladderHtml()` and the `.lean-b` ranked ladder from
`recruiting-lean-ladder.css` exactly as they are — the mock reuses that CSS verbatim. It stays the
right-most column because it's the thing a coach scans this table for.

---

## Surface 3 — Standalone Team Roster (`team-roster-view.html`)

This page had the worst of the problem: four stacked tables (Attributes, Season Stats, Practice
Squad roster, Practice Squad stats), each with its own heading, repeating the same player names four
times.

### Structure

```
Back to Locker Room                        ← existing ghost text link
┌─ shell ──────────────────────────────────────────────────────┐
│  [banner card]  TEAM ROSTER / FOUR CORNERS      9-2 · 2nd    │  identity lockup
│  PROJECTED STARTING FIVE                                     │
│  [p5 card] [p5 card] [p5 card] [p5 card] [p5 card]           │  unchanged component
│  Varsity(12) | Practice Squad(3)   [Attributes | Season Stats]│  scope + view
│  ─────────── one data surface, sticky header ─────────────── │
└──────────────────────────────────────────────────────────────┘
```

- **One data surface, two switches.** Scope (Varsity / Practice Squad) and view (Attributes / Season
  Stats). This removes all four headings and three of the four tables.
- **Identity lockup**: the team banner card (`<slug>_banner_card.webp`, 224×79, radius 10, border
  `rgba(255,255,255,.16)`) left, eyebrow "TEAM ROSTER" + team name (Bebas 34px) beside it, record and
  conference standing right-aligned. Scholarship count removed (scholarships are sunset).
- **Shell chrome** matches the FCC container exactly: radius 24, `rgba(14,16,24,.96)` with the
  160° highlight gradient, the 132° pinstripe overlay, `0 20px 48px rgba(0,0,0,.45)` +
  `inset 0 1px 0 rgba(255,255,255,.07)`.
- **Zebra banding** on this surface: even rows `rgba(255,255,255,.022)`, hover `rgba(255,255,255,.05)`.
  (The FCC tabs keep their existing odd-row `.03` instead — don't unify them.)

### Season Stats view

Keep all 23 production columns, but group them under a header tier the way a box score reads:

`SCORING · FIELD GOALS · 3-POINT · FREE THROWS · REBOUNDING · PLAYMAKING · DEFENSE · SCREENS · MISTAKES`

Group row: Inter 700 9px, `letter-spacing .13em`, `rgba(255,255,255,.26)`, with a hairline left
border (`rgba(255,255,255,.055)`) starting each group. Column row sticks below it (`top: 31px`).

**Per game / Totals toggle**, visible only on this view, **defaulting to Per game**. Segmented
control: 3px padding, radius 9, `rgba(255,255,255,.04)` track; selected segment
`rgba(255,255,255,.11)` with `inset 0 1px 0 rgba(255,255,255,.08)` and white text. Percentage
columns are unaffected by the toggle.

### Projected starting five — keep the headshots

**To be explicit, because the mock could be misread: the headshots stay.** The mock renders initials
in the photo slot only because it can't reach the image service; that is a fixture artifact, not a
design proposal.

This strip is the existing shared component — `renderProjectedStartingFiveCards()` in
`js/shared/scoutingReport.js` with `.p5-*` styles from `scouting-report.css`. **Reuse it as-is**,
including:

- the headshot (`getPlayerImageUrl` → `ensurePlayerImage` retry → `getGenericHeadshotUrl` fallback),
- the white `.p5-pos` chip and the `.p5-rt-badge` (current rating only — the current→potential pair
  belongs to the table),
- `.p5-name`, `.p5-bio` (`YR · HT · WT lb`), `.p5-jersey`,
- the four boxed per-game stats: PPG / RPG / APG / DEF.

**The strip is always per game, regardless of the table's Per game / Totals toggle.** That's already
true in the shared renderer (`scoutingFormatOneDecimal(r.ppg)` etc.) — just don't wire the toggle to
it.

Only the surrounding chrome changes: the section gets a `PROJECTED STARTING FIVE` eyebrow (Bebas 17px,
`letter-spacing .09em`, `rgba(255,255,255,.62)`) with a hairline rule, sits inside the new shell, and
uses `gap: 14px` in a `repeat(5, minmax(0,1fr))` grid.

---

## Design tokens

Everything below already exists in the repo; listed for completeness.

**Surface / structure**
```
container fill      rgba(14,16,24,.96) + linear-gradient(160deg, rgba(255,255,255,.028), rgba(255,255,255,.014) 18%, transparent 40%)
container radius    24px
container border    1px solid rgba(255,255,255,.09)
container shadow    0 20px 48px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.07)
panel               rgba(14,16,26,.9) + linear-gradient(180deg, rgba(255,255,255,.05), transparent 16%)
panel radius        20px    panel border 1px solid rgba(255,255,255,.18)
data card           linear-gradient(180deg, rgba(42,48,58,.92), rgba(30,35,44,.95))
data card radius    14px    border 1px solid rgba(255,255,255,.12)
hairline            rgba(255,255,255,.09)   soft hairline rgba(255,255,255,.055)
```

**Table**
```
th                  padding 12px 10px 10px · Inter 700 12px · .06em · uppercase · rgba(255,255,255,.66)
th background       linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.015)), #262b34
td                  padding 9px 10px · 13px · rgba(255,255,255,.9)
odd row (FCC)       rgba(255,255,255,.03)      row hover rgba(255,255,255,.04)
zebra (standalone)  rgba(255,255,255,.022)     row hover rgba(255,255,255,.05)
sticky name column  #262b34 / #2a2f39 odd / #2f353f hover
min table width     1180px
```

**Text**
```
display / numerals  'Bebas Neue Pro', 'Bebas Neue'
UI / data           'Inter'
ink                 #f7f9ff
ink-2               rgba(255,255,255,.62)
ink-3               rgba(255,255,255,.40)
ink-4               rgba(255,255,255,.26)
```

**Accent**
```
orange  #F79420   green #34EC27   blue #4A90D9   yellow #FFD700   amber #f2c14e
tile elite  bg rgba(74,144,217,.18)  text #4A90D9
tile high   bg rgba(52,236,39,.15)   text #9cf294
tile low    bg rgba(255,109,109,.12) text #ffa8a8
RT buckets  css/rt-buckets.css via getRtBucketClass() — never hardcode
```

## Assets

No new assets. Existing ones used: team banner cards
(`images/teams/<slug>/<slug>_banner_card.webp`), player headshots via
`API_CONFIG.getPlayerImageUrl` / `getGenericHeadshotUrl`.

## Files in this bundle

| File | What it is |
| --- | --- |
| `Team Roster Redesign.html` | Standalone team roster page — the full redesign |
| `team-roster-redesign.css` | Its styles |
| `team-roster-redesign.js` | Its rendering + sorting |
| `FCC Roster + Recruiting Tabs.html` | FCC frame with the Roster and Recruiting tabs |
| `fcc-tabs.css` | FCC mock styles (frame values lifted from `franchise-command-center.css`) |
| `fcc-tabs.js` | FCC mock rendering + sorting |
| `roster-fixture.js` | Fixture roster; per-game inputs, derived season totals |
| `recruits-fixture.js` | Fixture recruit pool with lean standings |
| `tweaks-panel.jsx` | **Review tooling only — do not port** |

Open either HTML file and click **Display options** to compare the rejected alternatives (flat tiles,
labels in tile, regular density, region/archetype as columns, stacked practice squad). The approved
configuration is what loads by default.

## Repo files you'll touch

| Repo file | Change |
| --- | --- |
| `js/shared/attrTiles.js` | Add `ATTR_PAIRS`, `tilesGroupedHtml`, `tilesGroupedHeaderHtml`. **Do not reorder `ATTR_KEYS`.** |
| `css/attr-tiles.css` | Add `.attr-pair` / pair-group + grouped-header rules. Tiers unchanged. |
| `franchise-command-center.html` | Roster tab: scope toggle, remove `#training-squad-section`. Recruits tab: folded identity header with the two sub-sorts. |
| `franchise-command-center.css` | Sticky header on the recruits table; sticky name column; control styles. |
| `franchise-command-center.js` | Scope-toggle state, per-attribute + sub-sort handlers. |
| `js/shared/rosterLoader.js` / `rosterStatsRenderer.js` | Grouped tiles + RT lockup in the row builders. |
| `team-roster-view.html` / `.js` (+ its CSS) | Scope + view switches, one data surface, grouped stats header, per-game default, new shell. |
| `js/shared/scoutingReport.js` | **No changes.** Reuse `renderProjectedStartingFiveCards` as-is. |
| `recruiting-lean-ladder.css` | **No changes.** |
| `css/rt-buckets.css` | **No changes.** |

## Acceptance checks

1. `GOB_AttrTiles.ATTR_KEYS` order is byte-identical to `develop`; the scouting modal's projected-
   five table and `SCOUTING_PROJECTED_ATTR_COLS` render unchanged.
2. All 12 attributes are sortable on all three surfaces, ascending and descending.
3. Home Region and Archetype are still sortable on the Recruiting tab after folding.
4. Headers stay stuck and fully opaque while scrolling, on all three surfaces.
5. Recruiting tab shows no horizontal scrollbar at a 1400px container.
6. Practice squad players appear via the scope toggle; no second stacked table anywhere on the
   Roster tab.
7. Standalone roster defaults to **Per game**; the projected-five strip stays per game when the
   table is switched to Totals.
8. Projected-five headshots load, with the generic-headshot fallback intact.
9. No `--pos-*` color remains; POS chips are neutral.
10. RT reads `B+ → A` with the `cur → pot` caption, colored by `getRtBucketClass`.
