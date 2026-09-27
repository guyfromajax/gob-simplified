# Layout rules — browse templates

Density sets, shell grid, rail and top bar are unchanged from the Round 2 `layout.md` (`.gob-1280` default; `.gob-1920` at ≥1680×1000; ≈×1.18 on `--fs-*`, `--dsp-*`, `--dsz-*`). Content area = viewport − `--rail-w` − 2×`--page-pad` − 10px scrollbar:

| | 1280×720 | 1920×1080 |
|---|---|---|
| Content width | **1170px** | **1654px** |
| Viewport below top bar | 664px | 1016px |
| Sticky page head `.pg-head` | 118px (`--dsz-118`) | 139px |
| Detail bar `.dt-bar` | 60px (`--dsz-60`) | 71px |
| Table header row / group row | 34 / 22px | 40 / 26px |
| Table row | 40px (`--dsz-40`) | 47px |

Max content width stays 1664px centred on viewports wider than 1920 (apply the Round 2 `.office` cap to `.main > *`).

## Scroll and sticky rules (all templates)
1. **One vertical scroll: `.main.scroll`.** Nothing else scrolls vertically. No `max-height` + `overflow:auto` anywhere.
2. **T1/T2:** `.pg-head` (title + sub-tabs + tools) is `position:sticky; top:0; z --z-sticky-head`. Table `th` is sticky at `top: var(--dsz-118)` (`--th-top` on `.tbl`). The second header row of a grouped table sticks at `calc(var(--th-top) + var(--dsz-22))`. `rowspan="2"` header cells stick with the first row.
3. **Multiple tables on one page** (Standings groups) each stick their own header while they're in view; the next table's header pushes in naturally. The first header cell carries the group name (`th.gname`), so the stuck header always says which group you're reading.
4. **Page tools live in the sub-tab row** (`.pg-tools`, `margin-left:auto`) so scope/search stay reachable while scrolling without adding sticky height. At 1280 the tools slot has ≈430–520px beside five or six tabs; if a page needs more controls than fit, move secondary ones into the table card header — never add a second sticky row.
5. **Wide tables** (`.xs`): only when the natural table width exceeds the content width at the current density. The card is `overflow-x:auto` (horizontal only); **its header does not stick** (sticky can't escape an overflow container) — instead the column-header row repeats every 16 rows (`tr.rep`). The first column pins with `position:sticky; left:0`. Horizontal position is shown by edge fades (`.can-l` / `.can-r`), the `.xs-map` thumb and ◂ ▸ state. The same page at a density where the table fits renders as a normal `.tcard` with a sticky grouped header (see `t1-team-stats-1920`).
6. **T3:** `.dt-bar` is sticky at `top:0` (`--z-sticky-head`). Hero and cards scroll under it. Tables inside detail cards are `.tbl.flat` (static header) — they are short and live inside a card.
7. Scope / sub-tab change: content crossfades (`--dur-hover`), page scroll resets to top. Sort change: no scroll change. Back from a detail page restores the list's scroll position, sort and scope.

## T1 · Table page
```
.pg-head  [h1 section · crumb · (pg-meta)]  [subtabs ……… pg-tools: seg · seg/search]
content   .tstack (1280) | .tgrid2 (1920, groups side by side)   → .tcard > table.tbl
          or .xs (wide)   or .ldr-grid (Leaders)
```
- **Standings:** one `.tcard` per conference, **your conference first**, then the rest in order. 1280: stacked. 1920: `.tgrid2` 2 columns (gap `--col-gap`), fixed column plan (`.tbl.fx` + `<colgroup>`), 8px cell padding so the region's four conferences (32 rows) are visible at once. Columns: # · Team (absorbs) · W · L · PF · PA · DIFF (bar + signed numeral) · STRK · NEXT.
  - Column plan (px, 1280 / 1920): # 34/36 · W 56/46 · L 48/42 · PF 72/62 · PA 72/62 · DIFF 118/118 · STRK 64/52 · NEXT 220/196 · Team = remainder.
  - Fit at 1280: Region scope = 4 × (34 + 8×40) = 4 × 354 + gaps → scrolls (page scroll only). Conference scope (8 rows) fits above the fold.
- **Rankings:** single `.tcard`; `seg` Top 25 · All 128; columns rank · team · W–L · last week · next. Same row rules.
- **Team Stats:** grouped header (Shooting · 3-Point · Free Throws · Rebounding · Other · Defense) with a `line-strong` rule at each group start. `.tbl.tight` (cell padding `--dsp-8`). Measured natural width 1,300px at 1280 (content 1,168) → `.xs` wide mode; fits the 1,654px content at 1920 → normal sticky header. Switch on measured overflow (`scrollWidth > clientWidth`), not on a breakpoint.
- **Leaders:** `.ldr-grid` 4 × 2 of `.ldb` cards (gap `--col-gap`); at 1280 all eight fit above the fold (bottom at ≈690 of 720). "Full list →" opens a T1 table for that category.
- **Schedule / Player Stats:** single `.tcard`; Schedule uses week `sep` rows for bye weeks / phase breaks; your games are always your team so no navy — highlight the **next** game row with `td.on` wash only.

## T2 · Attribute grid
```
.pg-head  [Team · crumb]  [subtabs ……… seg Varsity 12 | Practice Squad 3]
.tcard > table.tbl.grp.agrid
  row 1:  Player | RT (cur→pot) | Pos | Yr | Ht | Wt | OFFENSE | DEFENSE | SKILLS | GRIT | BODY | MIND | Dev focus
  row 2:                                              SC SH     ID OD     PS BH    RB ST  AG ND  IQ FT
```
- **Fits 12 attributes + bio at 1280 without horizontal scroll.** Measured at 1170px content: Player ≥190 (`.pcol` min) · RT 76 · Pos 43–50 · Yr 38–45 · Ht 55 · Wt 45 · 12 × 34–38 attribute cells (≈430 with group rules) · Dev focus absorbs the remainder (≈240). Natural minimum ≈1,000px → ≈170px headroom at 1280.
- The **last text column absorbs** extra width (Dev focus / Lean), so the identity, RT and attribute block stay tight and compare vertically; the attribute block never spreads apart as the window widens.
- Attribute cells: 34px (`--dsz-34`), digit box 30×26. Group start = 1px `--line-strong` left rule + 4px extra left padding. Groups 2/4/6 (DEFENSE, GRIT, MIND) get a `--white-2` band so pairs read as columns.
- **Lineup order** (default) shows `Starters` / `Bench` divider rows. **Any sort** removes the dividers and washes the sorted column (`td.on`, `--white-5` in the grid).
- 1920 adds a 30px avatar in the player cell; nothing else is added.
- **Recruit pool:** ★ (26) · Recruit (`.pcol`) · Reg · RT · Pos · Ht · Wt · 12 attributes · Lean (absorbs). Measured natural width ≈1,065 → fits 1170. Tools: `seg` All · Region · Watchlist + search.
- **Team Attributes:** `.mcards` 2 columns (Character · On the floor), each a list of `.mrow`. Fits 1280×720 with room to spare; more measures add rows, not columns.

## T3 · Detail page
```
.dt-bar   [← Roster]  Team / Roster / Marcus Ruiz ……………… ‹ 4 of 12 ›
.hero     [portrait | logo]  [eyebrow · name · bio · RT letters · actions]  |  [key numbers]
.dt-body  grid: minmax(0,1.3fr) minmax(0,1fr), gap --col-gap
          [Attributes card]               [dt-side: Development · Recent changes]
          [Stats card — span both columns]
```
- Hero height ≈176 at 1280 (portrait 118×142). Team hero swaps the portrait for a 96px logo; recruit hero uses `.hero.neutral` (no team wash — the recruit isn't yours yet).
- Player at 1920: attribute rows add a one-line description; hero adds a second stat row (MIN · BLK · FT · DEF); career table adds TO · PF. Same sections.
- Team page body: Roster card (`.tbl.flat`) | Schedule card (last 6 results + next 4 + "Full schedule →"). Games against your team get the navy row.
- Detail pages may exceed the fold at 1280 (they are browse pages, not live-gameplay screens); the hero + first row of cards are above the fold.

## What changes 1280 ↔ 1920
| Element | 1280 | 1920 |
|---|---|---|
| Standings, Region scope | 4 conference cards stacked | 2 × 2 grid, all 32 teams visible |
| Team Stats | `.xs` wide card: pinned team column, fades, jumps, repeat header | fits; normal card with sticky grouped header |
| Next-opponent cell | day | day (+ time where a single column allows) |
| Roster / pool player cell | jersey + name | jersey + 30px avatar + name |
| Header tooltip | full name on hover/focus | same |
| Player page | attribute name + abbr | + one-line description; extra hero stat row; career +TO/PF |
