# Roster & Recruiting Attribute Tiles — As Built

Record of what shipped vs. [IMPLEMENTATION_PROMPT.md](IMPLEMENTATION_PROMPT.md). Where the two
disagree, this file is authoritative.

Shipped: `28353b607` → `2ae875633` (develop, 2026-08-16/17).

## Surfaces

| Surface | File | Column order |
|---|---|---|
| FCC Roster tab | `franchise-command-center.html/.js` | Player · RT · POS · YR · HT · WT · Attributes |
| FCC Recruiting tab | `franchise-command-center.html` + `recruiting-common.js` | Recruit · RT · POS · YR · HT · WT · Attributes · Current Lean |
| Standalone roster | `team-roster-view.html/.js` | Player · RT · POS · YR · HT · WT · Attributes *(or grouped season stats)* |

All three share one column order by design — the tabs are read against each other.

**Out of scope, deliberately unchanged:** `set-lineup.js` and `player-detail.js` (no `GOB_AttrTiles`
at all); `recruiting-hub.js` still renders the flat 12-tile strip via `tilesHtml`.

## Shared module

`FrontEnd/static/js/shared/attrTiles.js` (`window.GOB_AttrTiles`) + `css/attr-tiles.css`.
Classic script, no bundler. Both must be loaded by any page using tiles.

| Export | Use |
|---|---|
| `groupedTilesHtml(attrs)` | 6-pair tile block (row body) |
| `groupedTilesCellHtml(attrs)` | same, wrapped in `<td class="attr-tiles-cell">` |
| `groupedHeaderHtml({key, dir})` | 2-row header: pair labels + per-attribute sort controls |
| `compareByAttr(key, dir)` | sort comparator |
| `tileValue` / `tierClass` / `tooltipFor` | single-tile primitives |
| `tilesHtml` / `tilesCellHtml` / `tilesHeaderHtml` | legacy flat strip (Hub pool only) |

**`ATTR_KEYS` is byte-identical to its pre-redesign order and must stay that way** — it is the
canonical attribute order, not a display concern. `ATTR_PAIRS` is presentation-only; reorder freely.

Header markup constraint: the pair label nests **inside** `.attr-pair`. As a direct child of
`.attr-grid` it inherits `grid-column: 1/-1` and the header stacks vertically instead of laying
out six across. Covered by a geometry assertion, not an element count.

## Deviations from the prompt

| Prompt | Shipped | Why |
|---|---|---|
| Sticky two-row header on all three surfaces | Yes, but the header is one `<th>` holding a CSS grid | Two real `<tr>`s can't stick as a unit alongside a rowspan identity column |
| Region / Archetype as sortable folded columns | Folded into the identity sub-line; **sorting removed** | Requested 2026-08-17; header read as clutter. No other column lost its sort |
| — | `/team-roster/{team}` route + 16 templates deleted | Zero inbound links, wrong collection, unauthenticated. Confirmed dead before removal |
| — | Standalone roster: 4 stacked tables → 1 surface, 2 switches | Scope × View replaces Varsity/PS/stats/PS-stats duplication |
| — | `team_record` added to `/roster/{team}` | New identity lockup needs record + conference place |

## Tunable Constants

| Constant | Where | Value | Effect |
|---|---|---|---|
| `--tile-w` / `--tile-h` | `attr-tiles.css` | `26px` / `27px` | Tile footprint; drives total attribute-block width |
| `--attr-group-gap` | `attr-tiles.css` | `clamp(7px, 1vw, 15px)` | Gap between the 6 pairs. Raising it can overflow the Recruiting tab and push Current Lean off-screen |
| `tierClass` thresholds | `attrTiles.js` | `>=10` elite, `>=7` hi, `<=3` lo | Tile colour tiers. Elite is brand RT blue |
| `ATTR_PAIRS` | `attrTiles.js` | OFFENSE/DEFENSE/SKILLS/GRIT/BODY/MIND | Pair grouping + labels. Presentation only |
| `.ident-sub` colour | `attr-tiles.css` | `rgba(255,255,255,.62)` | AA floor at 11px on a banded row — do not lighten |
| `TR_STAT_GROUPS` | `team-roster-view.js` | 9 groups | Season-stat grouping. Columns are ordered for contiguity; `pct: true` exempts a column from the Per game divisor |

## Backend

`/roster/{team}` returns `team_record` (franchise mode only): `wins`, `losses`, `conference`,
`conference_place`, `conference_size`, `natl_rank`, `recruiting_rank`, `recruiting_region_rank`.
Conference place from `calculate_franchise_standings` (same helper as the Standings tab — wins,
then point differential); `natl_rank` / recruiting ranks from FTD. Lockup labels: Record,
Conference Rank (`N of M`), National Rank, Recruiting Rank. `null` outside a franchise.

⚠️ The block is wrapped in `except Exception` so a lookup failure degrades to no record rather than
a 500. That also **hides typos**: it first shipped calling `db.franchises` / `db.teams`, names that
do not exist in `api.py`, so every response silently carried `team_record: None`.
`tests/test_roster_team_record.py` now pins the collection handles against `BackEnd.db`.

## Tests

| File | Covers |
|---|---|
| `tests/e2e/attr-tiles.spec.js` | Builder, hover copy, tiers, cross-surface wiring |
| `tests/e2e/fcc-roster-tab.spec.js` | Both FCC tabs: order, sticky, scope toggle, width, lean ladder |
| `tests/e2e/standalone-roster.spec.js` | Surface 3: one table, both switches, per-game, lockup, sticky |
| `tests/test_roster_team_record.py` | `team_record` collection handles + standings contract |

Two assertions exist because counting was not enough:

- **Header count == body cell count**, per surface. A header-collapse regex once missed
  `data-sort="SC"`, leaving 12 `<td>`s under a 7-column header.
- **Each body cell sits under its own header label** (RT holds the lockup, POS the chip, …).
  Count-only and header-only tests both pass when the *body* is reordered.

Harness notes: specs drive the **real** renderers, never a hand-built copy of their markup — a
stand-in cannot catch order drift. `team-roster-view.js` keeps its data in top-level `let`
bindings, so it must be injected via `addScriptTag`; `eval()` inside `page.evaluate` scopes them
away and every row renders empty.

## Known gaps

- `recruiting-common.js` still carries the generic `[data-sub-sort]` binder and
  `applySubSortIndicators`. No markup uses them; they no-op. Safe to delete.
- 12 `court-layout` e2e tests fail without a live backend game (pre-existing, unrelated).
