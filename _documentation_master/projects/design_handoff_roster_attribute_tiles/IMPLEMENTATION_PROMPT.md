# Implementation prompt — Roster & Recruiting attribute-tile redesign

Paste this into Claude Code with the repo open. The HTML files referenced are design references in
`design_handoff_roster_attribute_tiles/` — read them for exact visual values, do not port them.

---

## Context

Repo: `guyfromajax/gob-simplified`, branch `develop`, frontend under `FrontEnd/static/`. Plain
classic scripts, per-page CSS, `window.GOB_*` shared modules, no bundler.

The 12 player attributes recently moved from plain numbers to colored tiles (`css/attr-tiles.css` +
`js/shared/attrTiles.js`). The tiles are keepers. The problem is that the tables hosting them were
laid out for numbers, so each row now reads as three unrelated zones: sparse text columns, a dense
undifferentiated 12-tile block, then a lone unlabeled `RT` at the far right edge.

Fix the hosting layouts on the three surfaces that show tiles in a table:

1. `team-roster-view.html` — standalone team roster page
2. `franchise-command-center.html` → `#roster-tab`
3. `franchise-command-center.html` → `#recruits-tab`

`recruiting.html` (Recruiting Hub pool) is **out of scope** this pass.

## Ground rules

- **Verify before you build.** This prompt was written from a partial read of the frontend. Where it
  describes an outcome, implement it however the codebase is actually structured. Where it names a
  specific file, function, or selector, confirm it before relying on it, and follow the real code if
  they disagree.
- **Reuse, don't fork.** Every visual primitive below already exists in the repo. Extend the shared
  modules; do not create parallel implementations.
- **Design references are references.** `design_handoff_roster_attribute_tiles/*.html` uses fixture
  data and a React tweaks panel for review only. Take visual values from them; take nothing else.
- **Don't build a settings UI.** The mocks expose the design alternatives as toggles so they could be
  compared. Exactly one configuration was approved (below). Ship that; drop the rest.
- Ask before changing anything you find that this prompt didn't anticipate, rather than guessing at
  intent.

## Approved configuration

| Decision | Approved |
| --- | --- |
| Tile grouping | Grouped into 6 labeled pairs |
| Tile labels | In the header only, never inside the tile |
| Header behavior | Sticky on all three surfaces |
| Density | Compact |
| RT placement | Immediately beside the player name |
| Position colors | **Off** — neutral chip |
| Row banding | Standalone roster: zebra. FCC tabs: keep existing banding. |
| Region + Archetype (Recruiting tab) | Folded into the identity cell |
| Practice squad | Scope toggle, not a second stacked table |
| Projected starting five (standalone) | Kept, **with headshots** |
| Season stats default (standalone) | Per game |

---

## Task 1 — Group the 12 tiles into 6 labeled pairs

Twelve identical tiles in a row read as a barcode. Grouped in pairs with a label over each pair, the
same data becomes six scannable chunks. This is the change that does most of the work.

Pairs, left to right:

| Label | Attributes |
| --- | --- |
| OFFENSE | SC, SH |
| DEFENSE | ID, OD |
| SKILLS | PS, BH |
| GRIT | RB, ST |
| BODY | AG, ND |
| MIND | IQ, FT |

**Critical constraint.** `js/shared/attrTiles.js` defines
`ATTR_KEYS = ['SC','SH','ID','OD','PS','BH','RB','AG','ST','ND','IQ','FT']` and exports it on
`window.GOB_AttrTiles`. Note `AG` precedes `ST` there, while the display pairing above needs
`RB, ST` then `AG, ND`. **Do not reorder `ATTR_KEYS` to achieve the pairing.** Its order is mirrored
by `SCOUTING_PROJECTED_ATTR_COLS` in `js/shared/scoutingReport.js`, whose comment states it matches
the backend `roster_builder` ATTR_KEYS order for ST/AG. Reordering the shared array would silently
shift the scouting modal and the projected-five table.

Add the pairing as a **presentation-only** structure alongside `ATTR_KEYS`, plus a grouped renderer
and a grouped header builder. Name them per the module's existing conventions. Search for every
consumer of `ATTR_KEYS`, `tilesHtml`, `tilesCellHtml`, and `tilesHeaderHtml` before you change
anything, and leave the ungrouped functions working for any surface outside this scope.

**Verify afterward:** `GOB_AttrTiles.ATTR_KEYS` is byte-identical to `develop`, and the scouting
modal's projected-five table renders unchanged.

## Task 2 — Move tile labels into the header

`tileHtml` currently emits `<u>KEY</u>` inside each tile, so every abbreviation repeats on every row
— twelve redundant labels per player. It already accepts a `showLabel` option.

Render the tiles label-less on these three surfaces, and print each abbreviation **once** in the
header above its column. Hover identification is unaffected: the tiles carry `data-tooltip` and the
surfaces call the shared tooltip initializer.

Everything else about the tile stays exactly as `css/attr-tiles.css` defines it — dimensions, radius,
tier colors, the `cursor: help`. Only the inner label goes away.

## Task 3 — Restore per-attribute sorting

Collapsing 12 columns into one cell removed 12 sort controls. Give them back: **the header
abbreviations are the sort controls.**

- Click sorts by that attribute, descending first; clicking again toggles ascending.
- The active control shows a caret (`▾` / `▴`) in `#F79420` and goes to full white.
- Sort on the 0–10 display value the tiles show — `attrTiles.js` has an anchor-aware helper that
  floors the stored value; use it so ties behave the way the user sees them, not the way they're
  stored.
- Whatever sorting mechanism each surface already uses (the FCC tabs and the standalone page may
  differ), extend it rather than adding a second one.

## Task 4 — Sticky headers on all three surfaces

`#roster-tab` already achieves this in `franchise-command-center.css` — the tab panel owns the
scroll, `thead th` is sticky with an opaque background so rows can't bleed through. Extend the same
approach to the Recruiting tab and the standalone roster table.

The grouped header is now two lines tall (pair label row + abbreviation row), so both rows must stick
together and both need opaque backing. Scroll a full table and confirm nothing shows through.

## Task 5 — RT becomes a labeled current → potential lockup

Today RT prints as a bare `B+/A` pair with a `data-tooltip="current/potential"`, positioned at the
far right of the row where it's disconnected from the player it describes. Nobody can decode it.

Change to an explicit two-part lockup, positioned immediately right of the player name and before
POS/YR/HT/WT:

- Current grade: Bebas 22px, colored by the existing RT bucket helper.
- Potential grade: Inter 600 11px at 62% opacity, prefixed with a dimmed `→`, also bucket-colored.
- Header caption under "RT": `cur → pot` — Inter 600 9px, `letter-spacing .08em`, uppercase,
  `rgba(255,255,255,.26)`.

"Potential" is the canonical product term — do not introduce "ceiling" anywhere. Colors come from
`css/rt-buckets.css` via the existing bucket-class helper; never hardcode thresholds.

## Task 6 — Neutral position chips

Colored position chips were built and **rejected**. Render POS as a neutral chip:

```
min-width 34px; height 21px; border-radius 5px;
font: 700 10.5px/1 'Inter'; letter-spacing .06em;
color rgba(255,255,255,.86);
background rgba(255,255,255,.07);
border 1px solid rgba(255,255,255,.1);
```

No position color tokens. If you add any while working, remove them before you're done.

## Task 7 — Compact density

Tiles at 26×27px, `2.5px` between the two tiles of a pair, and `clamp(7px, 1vw, 15px)` between pair
groups — the pair gap is what makes the grouping legible, so keep it responsive rather than fixed.

Let row height fall out of the existing cell padding rules; don't set explicit row heights.

---

## Surface 1 — FCC Roster tab

**Column order:** `Player · RT · POS · YR · HT · WT · Attributes`

**Sticky identity column.** Make the Player column sticky to the left edge so scanning the tiles
never loses track of whose row it is. It needs its own opaque background per row state, because the
FCC row banding sits on the `<tr>` and a transparent sticky cell will show rows sliding under it.
Match the banding: base, banded, and hover all need a solid equivalent.

**Player cell contents:** jersey number (Bebas 19px, `rgba(255,255,255,.26)`, right-aligned in a
fixed ~26px box so numbers align), then the player name as a link (Inter 700 13.5px, white), then any
status flags the row already carries.

**Replace the stacked practice squad.** Remove the separate practice-squad section below the main
table and replace it with a two-button scope toggle in the header row that swaps the body of the one
table:

```
[ Varsity  12 ]  [ Practice Squad  3 ]
```

Use the FCC control vocabulary already in `franchise-command-center.css`: `min-height 34px`,
`padding 0 14px`, `border-radius 8px`, `1px solid rgba(255,255,255,.1)` border,
`rgba(255,255,255,.06)` fill, `inset 0 1px 0 rgba(255,255,255,.06)`, `rgba(255,255,255,.62)` text.
Hover: fill `.11`, text `.9`. Selected: fill `.09`, border `.18`, text white. Counts render inside the
button in Inter 11px tabular-nums at `rgba(255,255,255,.26)`, brightening to `.55` when selected.

Set `aria-pressed` on the buttons; the selected state must be conveyed by more than color.

The tab's `<h3>` stays outside the data card as it is today. Put the scope toggle beside it and a
right-aligned row count (Inter 700 12px, `letter-spacing .06em`, uppercase, `rgba(255,255,255,.5)`).

**Note for later, don't build now:** the Player Stats tab has the same stacked practice-squad
pattern. Leave it alone this pass, but flag it so the two tabs don't drift.

## Surface 2 — FCC Recruiting tab

**Column order:** `Recruit · RT · POS · HT · WT · Attributes · Current Lean`

**Fold Home Region and Archetype into the identity cell** as a sub-line beneath the recruit's name:

```
Isaiah Frame
Region A · Slasher
```

- Sub-line: Inter 500 11px at `rgba(255,255,255,.62)`. This value is a floor, not a preference —
  lighter than this fails AA contrast at this size against the banded row. Archetype within it: 700 at
  `rgba(255,255,255,.78)`.
- Regions are single letters product-wide, so they display as "Region A" … "Region H". Confirm how the
  region value arrives and format accordingly.

**Why fold:** it's a width decision. With Region and Archetype as their own columns, the table's
natural width exceeds the panel's available content width at the production container cap and forces
horizontal scroll, which pushes Current Lean — the column a coach actually scans this table for —
off-screen. Folding frees roughly 200px. Measure this yourself in a real browser at the production
container width before and after; don't take the numbers on faith.

**Preserve both sort keys.** The table currently declares sortable Home Region and Archetype columns.
Folding must not silently delete those affordances — render the sub-line's two words as sort controls
in the header beneath "Recruit". Both sort ascending first, since they're alphabetical. Style them
like the attribute sort controls.

**Current Lean stays exactly as it is.** Keep the existing shared lean-ladder component and
`recruiting-lean-ladder.css` untouched, in the right-most position.

## Surface 3 — Standalone Team Roster (`team-roster-view.html`)

This page had the worst version of the problem: four stacked tables — attributes, season stats,
practice-squad attributes, practice-squad stats — each with its own heading, repeating the same
player names four times down the page.

**Collapse to one data surface with two switches:**

- **Scope:** Varsity / Practice Squad
- **View:** Attributes / Season Stats

Same control vocabulary as the FCC scope toggle. This removes all four headings and three of the four
tables. Sticky player column here too.

**Identity lockup at the top.** Team banner card image (224×79, radius 10, `1px solid
rgba(255,255,255,.16)` border) at left; eyebrow "TEAM ROSTER" above the team name in Bebas 34px
beside it; record and conference standing right-aligned in Bebas 24px over `letter-spacing .13em`
uppercase micro-labels. **No scholarship count** — scholarships are sunset.

**Page shell** matches the FCC container treatment: radius 24, `rgba(14,16,24,.96)` fill with the
160° highlight gradient, the 132° pinstripe overlay, `0 20px 48px rgba(0,0,0,.45)` and
`inset 0 1px 0 rgba(255,255,255,.07)`. The back-to-locker-room control is a ghost text link with a
`←` prefix, outside the shell.

**Zebra banding on this surface only:** even rows `rgba(255,255,255,.022)`, hover
`rgba(255,255,255,.05)`. The FCC tabs keep their existing banding — don't unify them.

**Season Stats view.** Keep the existing stat column set unchanged, but group the columns under a
header tier so it reads like a box score: SCORING · FIELD GOALS · 3-POINT · FREE THROWS ·
REBOUNDING · PLAYMAKING · DEFENSE · SCREENS · MISTAKES. Group labels Inter 700 9px,
`letter-spacing .13em`, `rgba(255,255,255,.26)`, with a hairline left border
(`rgba(255,255,255,.055)`) opening each group. The column row sticks beneath the group row.

Add a **Per game / Totals** segmented toggle, visible only on this view, **defaulting to Per game**.
Percentage columns are unaffected by it. Track: 3px padding, radius 9, `rgba(255,255,255,.04)`;
selected segment `rgba(255,255,255,.11)` with `inset 0 1px 0 rgba(255,255,255,.08)` and white text.

**Projected starting five — keep it, and keep the headshots.**

This strip is an existing shared component that renders image cards, already used by both this page
and the FCC Scouting Report. Reuse it as-is. Specifically preserve:

- the headshot image, including its existing fetch/retry/generic-fallback chain
- the position chip and the RT badge (current grade only — the current→potential pair belongs to the
  table, not the card)
- the name, the `YR · HT · WT` bio line, and the jersey number
- the four boxed per-game stats: PPG / RPG / APG / DEF

**The strip is always per game**, regardless of the table's Per game / Totals toggle. It already
formats per-game values — simply don't wire the toggle to it.

If the design reference's five-card strip appears to show initials instead of photos, that is a
fixture artifact of the mock, not a design proposal. Headshots stay.

Only the surrounding chrome changes: a `PROJECTED STARTING FIVE` eyebrow (Bebas 17px,
`letter-spacing .09em`, `rgba(255,255,255,.62)`) with a hairline rule, placed inside the new shell
above the toolbar.

---

## Shared design tokens

All of these already exist in the repo; listed so you can match rather than invent.

```
Surfaces
  container fill     rgba(14,16,24,.96) + linear-gradient(160deg, rgba(255,255,255,.028), rgba(255,255,255,.014) 18%, transparent 40%)
  container radius   24px    border 1px solid rgba(255,255,255,.09)
  container shadow   0 20px 48px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.07)
  hairline           rgba(255,255,255,.09)     soft hairline rgba(255,255,255,.055)

Type
  display/numerals   'Bebas Neue Pro', 'Bebas Neue'
  UI/data            'Inter'
  ink                #f7f9ff
  ink-2              rgba(255,255,255,.62)
  ink-3              rgba(255,255,255,.40)
  ink-4              rgba(255,255,255,.26)

Accent
  orange #F79420   green #34EC27   blue #4A90D9   yellow #FFD700   amber #f2c14e
  tile tiers and RT bucket colors come from css/attr-tiles.css and css/rt-buckets.css — never hardcode
```

## Acceptance checks

1. `GOB_AttrTiles.ATTR_KEYS` is unchanged from `develop`; the scouting modal's projected-five table
   and the stats view render exactly as before.
2. All 12 attributes sort, ascending and descending, on all three surfaces.
3. Home Region and Archetype still sort on the Recruiting tab after folding.
4. Both header rows stay stuck and fully opaque through a full-table scroll, on all three surfaces.
5. The Recruiting tab shows no horizontal scrollbar at the production container width.
6. Practice-squad players are reachable via the scope toggle; no second stacked table remains on the
   Roster tab.
7. The standalone roster opens on Per game; switching the table to Totals leaves the projected-five
   strip per game.
8. Projected-five headshots load, and the generic-headshot fallback still works when one is missing.
9. No position color tokens remain; POS chips are neutral.
10. RT reads as current → potential with the `CUR → POT` caption, bucket-colored, beside the name.
11. The word "ceiling" appears nowhere in the UI.
12. No user-facing toggles exist for grouping, density, tile labels, banding, RT placement, or the
    recruit identity fold.
