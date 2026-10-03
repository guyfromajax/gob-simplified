# Component specs — browse templates

Conventions as Round 2 `components.md`: sizes at 1280; `--fs-*` / `--dsp-*` / `--dsz-*` scale ≈×1.18 at 1920; `--space-*`, radii and lines are fixed. `t100/t87/t60/t38` = `--text-*`; `w-N` = `--white-N`; `mix(X,N%)` = `color-mix(in srgb,var(--X) N%,transparent)`. Focus is always `:focus-visible` 2px `--white` outline. No spinners. Round 2 components (shell, card, chip, meter, `.lnk`, `.nm`, `.logo`, `.av`, `.portrait`, `.btn-ghost`, `.mv-p`) are reused unchanged.

---

## 1. Page tools `.pg-tools` (in `.subtabs`)
- Flex, `margin-left:auto`, gap 10, vertically centred in the 40px tab row. Holds 1–2 `.seg` and/or one `.search`.
- **`.pg-meta`** (title row, right): Inter 500 fs-12 t60 — freshness/context ("Updated after Week 21 · change vs last week").

### Segmented `.seg` (`role="radiogroup"`, buttons `role="radio"`)
- Track: padding 3, gap 2, radius 9, w-4, `inset 0 0 0 1px line`.
- Button: height `--dsz-28`, padding 0×12, radius 7, Inter 600 fs-12, t60, nowrap. Optional count `em`: Inter 500 fs-11 t38.
- Hover: t87 on w-4. **Selected `.on`:** w-11, t100, `inset 0 1px 0 w-9`; count → t60. Neutral — never navy/orange.
- Keys: ←/→ move selection; change applies instantly (crossfade `--dur-hover`), resets page scroll.
- Uses: scope (Conference · Region · National; Conference · National), Top 25 · All 128, Per game · Totals, Varsity · Practice Squad, All · Region · Watchlist.

### Search `.search`
- Height `--dsz-28`+6, width `--dsz-118`+72 (190 / 211), padding 0×8×0×10, radius 9, w-4, `inset line`. Icon 15px t38; input Inter 500 fs-12 t87, placeholder t38; `kbd` "/" hint: Inter 700 fs-10 t38, `inset line-strong`, radius 4.
- Hover w-6. Focus (`:focus-within`): w-6 + `inset 0 0 0 1px w-35`.
- Behaviour: filters rows as you type (no submit); "/" focuses it; Esc clears. Empty result → `.empty` in the table body ("No team matches “Whit”").

## 2. Table card `.tcard` + data table `.tbl`
- `.tcard`: 1px `--line`, radius 12, w-2. Never `overflow:hidden` (would break sticky).
- `.tbl`: `border-collapse:separate`, `--th-top: var(--dsz-118)`, fs-13.
- **Header `th`:** sticky at `--th-top`, `--z-sticky`; height `--dsz-34`; padding 0×`--dsp-10`; Inter 700 fs-10 UPPERCASE tracking-8 t60; background `linear-gradient(--surface-th-top, --surface-th-bottom)`; bottom 1px `line-strong`. Outer top corners radius 11.
- **Cells `td`:** height `--dsz-40`, padding 0×`--dsp-10`, bottom 1px `--line`, t87, nowrap.
- **Alignment:** numbers **right** (default) with tabular figures (inherited from `.gob`); text `.l`; short codes/badges `.c`. Header aligns with its column.
- **Rhythm:** divider on every row + zebra (even rows w-1p2). Hover row w-5.
- **Emphasis by luminance only:** `.b` t100 600 (the sort/primary value), default t87, `.dim` t60 (supporting numbers: PF/PA, HT/WT, attempts), `.qt` t38.
- **Rank `.rk`:** 1% width, fs-12 700 t38.
- **Group start `.gs`:** 1px `line-strong` left border (header and body).

### Sortable header `th.s`
| State | Treatment |
|---|---|
| Default | t60, pointer |
| Hover | t87 (`--dur-hover`) |
| Sorted `.on` | t100 + caret ▾ (desc) / ▴ (`.asc`) and `inset 0 -2px 0 w-70`. Caret sits before numeric labels, after `.l`/`.c` labels, and before the label when a `.cap` is present |
| Sorted column cells `td.on` | `background-image` w-3 (w-5 in `.agrid`) — layers over zebra/navy |
| Focus | 2px white outline, −2px |
- First click on a numeric column sorts **descending**; text columns ascending. Second click toggles. Sort persists per page for the session. The indicator is **neutral** (was orange in the earlier tile handoff — see decisions).
- `aria-sort` on the sorted `th`.

### Grouped header `.tbl.grp`
- Row 1 `tr.g`: height `--dsz-22`, Inter 700 fs-10 tracking-10 t38, centred, `--surface-th-top`, bottom 1px `--line`; one `th colspan` per group with `.gs`. Columns without a group use `rowspan="2"` (full header surface, t60).
- Row 2 sticks at `calc(--th-top + --dsz-22)`.
- Header caption `.cap` (under a label, e.g. RT "cur → pot"): 9px Inter 600 tracking-6 t38, block.

### Group name cell `th.gname`
- First header cell spanning rank + team: Bebas 700 fs-16 tracking-8 t87, padding-left `--dsp-14`; optional `em` tag (Inter 700 fs-10 tracking-8 t60, "Yours").

### Row kinds
- **Your team / your player `tr.me`:** td fill mix(navy,35%) (`!important` over zebra/hover), `inset 0 ±1px 0 mix(navy-hi,35%)` top and bottom; bottom divider transparent. One navy row per team; on player tables, every row of your team.
- **Divider `tr.sep`:** height `--dsz-28`, padding-top 6, left `--dsp-14`, Inter 700 fs-10 UPPERCASE tracking-10 t38, transparent. Only in the table's natural order (Starters/Bench, bye weeks); removed while sorted.
- **Repeat header `tr.rep`** (wide tables only): `th` cells in `tbody`, height `--dsz-30`, top 1px `line-strong`. Every 16 rows.

### Variants
- `.tbl.fx` — `table-layout:fixed` + `<colgroup>` plan; cells ellipsize. Use when several tables must align (Standings groups) or share a narrow card.
- `.tbl.tight` — cell padding `--dsp-8` (wide stat grids).
- `.tbl.flat` — static header, height `--dsz-30`, transparent header bg with `--line` rule; rows `--dsz-34`. For short tables inside detail cards. `tr.cur` = current season (t100 600); `tr.tot` = career total (top `line-strong`, t60 600).

### Cell atoms
- **Team `.tm`:** flex gap 8 · logo 20 (24 at 1920) · national rank `em` (Inter 600 fs-11 t60, `#6`; omitted when unranked) · `.nm` (ellipsis) · optional conference `em.tsc` t38. In wide grids the rank `.tsr` sits inside the pinned cell (width `--dsz-18`, 700 fs-12 t38).
- **Diverging bar `.dv` + `.dvn`** (DIFF): track `--dsz-40`×`--dsz-6`, radius 2, w-4; centre tick 1px w-25 (±3px); fill from centre, width `--v`×50%: positive w-55 to the right, negative (`.neg`) w-25 to the left. `--v` = |value| / scope max. Numeral `.dvn` min-width 4.2ch right-aligned, signed (+126 / −48 with a real minus); negative t60. No hue.
- **Streak `.stk`:** Inter 600 — W t87, L (`.l`) t60. Plain text, no chip (see decisions).
- **Next `.nxc`:** "vs"/"at" Bebas 400 fs-13 tracking-10 t60 (width `--dsz-18`) · logo 18 · optional rank `em` · `.nm` 500 t87 (ellipsis) · day `em` fs-11 t38.

## 3. Wide table card `.xs`
Only when the table's measured natural width exceeds the content width.
- **Card:** as `.tcard`; sets `--pin-bg: color-mix(white 2%, --bg-page-solid)` and receives `--pin-w`.
- **Header `.xs-h`:** height `--dsz-44`, padding 0×`--dsp-10`×0×`--dsp-14`, bottom 1px `line-strong`, gap 12.
  - Title `.xs-t` Bebas 700 fs-16 tracking-8 t87 + `.meta` (scope · count · per game · sort).
  - **Group jumps `.xs-jump`** (right): buttons height `--dsz-24`, padding 0×8, radius 6, Inter 600 fs-11 t60; hover w-6 t87; `.on` (group at the left edge of the viewport) w-9 t100. Click scrolls that group to just right of the pinned column (smooth).
  - **Position map `.xs-map`:** 64×4, radius 2, w-7; thumb w-45, width = visible ÷ total, left = scroll fraction (transition `--dur-hover`).
  - **Paging `.xs-nav`:** two 28×28 buttons, radius 7, `inset line-strong`, chevron 14 t87; hover w-7; disabled at the ends (t38, `inset line`). Pages by 80% of the visible width (smooth).
- **Body `.xs-body`:** `overflow-x:auto; overflow-y:hidden`, bottom radius 11, thin scrollbar (8px, thumb `line-strong`), `overscroll-behavior-x:contain`. Table `width:max-content; min-width:100%`. **Header cells static** (no sticky).
- **Pinned column `.pin`:** `position:sticky; left:0; z --z-raised`, opaque `--pin-bg` (even rows 3.2% white, hover 7%, `.me` navy 35% over `--bg-page-solid`). When scrolled (`.can-l`): `8px 0 12px -8px black-50` edge shadow.
- **Edge fades `.xs-fade.l/.r`:** 56px, `--z-sticky`, gradient transparent → `--pin-bg`; left fade starts at `--pin-w`. Opacity 0 → 1 (`--dur-hover`) via `.can-l` / `.can-r`.
- Input: trackpad / shift+wheel scroll; ←/→ on a focused cell scrolls one column. The page's vertical wheel is never captured.
- Behaviour reference: `templates.js`.

## 4. Empty and loading
- **Empty `.empty`** inside `td.empty-td colspan=all` (header stays): centred column, gap 8, padding `--dsp-24`×`--dsp-20`. Title Bebas 700 fs-20 tracking-4 t87; body fs-12 t60, max 440px; optional `.lnk`. Copy says why it's empty and when it fills ("Standings fill in after Week 1…").
- **Skeleton `.sk`:** inline-block, height 10 (`.lg` 18, custom sizes inline), radius 4 (`.o` round), w-6. Pulse `skPulse` opacity 1 → .45 → 1, `--dur-skeleton` 1.4s ease-in-out infinite; none under reduced motion. Skeletons use **the final shapes**: real header, real row height, bars at typical content widths, logo/avatar squares, digit boxes 26×22. Row count = expected rows (capped at what fits). No shimmer sweep, no spinner.

## 5. Leaders board `.ldr-grid` / `.ldb`
- Grid 4 columns, gap `--col-gap`. Card = Round 2 `.card` with gap 8.
- Header: category name (card h3) + meta ("PTS · per game").
- **Leader block `.ldb-top`** (link): grid `auto 1fr auto`, gap `--dsp-10`, padding `--dsp-8`×`--dsp-10`, radius 10, w-3, `inset line`. Avatar 36 · name `.nm` fs-14 + "Team · POS · YR" fs-11 t60 (ellipsis) · value Bebas 700 fs-32 t100 + unit Inter 700 fs-10 t60.
- **Rows `.ldb-r`** (links) 2–5: grid `--dsz-18 1fr auto`, height `--dsz-28`, padding 0×`--dsp-8`, top 1px line. Rank fs-11 700 t38 · name 500 t87 + team code fs-10 700 t38 · value Bebas 700 fs-18 t87.
- Your player: `.me` on block or row (navy 35% + navy-hi 35% ring, radius 6/10).
- Footer `.card-f` "Full list →".

## 6. Attribute grid `.tbl.grp.agrid`
- **Group row:** OFFENSE · DEFENSE · SKILLS · GRIT · BODY · MIND (`th.ag colspan=2 .gs`). Presentation-only pairing — do not reorder the production `ATTR_KEYS`.
- **Abbreviation header `th.aa.s`:** width `--dsz-34`, padding 0×2, Inter 700 fs-11 tracking-4, centred; sortable (desc first). `title` + `aria-label` = full name.
- **Header tooltip `.tip`** (hover after 300ms, or focus): absolute under the header (+6), 228 wide, padding 10×12, radius 10, `--surface-popover`, `--shadow-popover`, arrow 10px at top centre, `--z-popover`. Content: full name Bebas 700 fs-18 t100 + abbr Inter 700 fs-11 t60 · one-line description fs-12 t87 · "Click to sort · high → low" fs-11 t60. Fades in `--dur-hover`; hides on leave/Esc. It never blocks the sort click.
- **Attribute cell `td.a`:** width `--dsz-34`, padding 0×2, centred. Group start `.gs` adds 4px left padding. Alternate groups `.gb` (2/4/6): `background-image` w-2. Sorted column `.on`: w-5.
- **Digit `.ad`:** 30×26 (`--dsz-30`×`--dsz-26`), radius 5, Bebas 700 fs-20, padding-top 1.
  | Tier | Glyph | Background |
  |---|---|---|
  | 0–4 | `--red` | none |
  | 5–6 | `--yellow` | w-3 |
  | 7–8 | `--green` | w-6 |
  | 9+ | `--blue` | w-10 + `inset 0 0 0 1px w-12` |
  Two-digit values (10+) fit the same box. The fill is neutral luminance (magnitude), the hue is on the glyph (tier) — one channel each.
- **Player cell `.pc`** (in `td.pcol`, min-width `--dsz-118`+72): jersey `.jn` Bebas 700 fs-18 t38 right-aligned in `--dsz-22` · (1920: avatar 30) · `.nm` fs-13 (ellipsis).
- **RT lockup `.rtl`:** current Bebas 700 fs-20 tracking-2 · arrow fs-11 t38 · potential `.pot` Bebas 700 fs-15. Each letter coloured by its own bucket. Header "RT" + `.cap` "cur → pot".
- **Position chip `.pos`:** min-width `--dsz-30`, height `--dsz-20`, radius 5, Inter 700 fs-10 tracking-6 t87, w-6, `inset line-strong`. Neutral.
- **Dev focus `.dev`:** fs-12 t87; `.none` "Not set" t38.
- **Order:** Player · RT · Pos · Yr · Ht · Wt · 12 attributes · Dev focus. Last column absorbs width.

## 7. Recruit pool extras
- **Watch star `.wst`** (button, `aria-pressed`): 26×26, radius 7, star 16 stroke t38. Hover t87 on w-6. On: `--orange` stroke + fill (a save). Toggle is instant and optimistic; failure reverts with no spinner.
- **Lean `.lean`:** standing `b` (Inter 600 fs-12 t87, min `--dsz-30`: "1st"/"2nd"/"3rd"; `.out` t38 500 "Not in top 3" / "No leans yet") · ladder `.lean-l` of up to 3 logos 18 in lean order, gap 3; your school `.you` = `0 0 0 1.5px --bg, 0 0 0 3px --navy-hi` ring. Stand-in for the production lean ladder — reuse `RecruitingSpine.Lean.ladderHtml()` if it renders the same information.
- **Status tag `.tg`:** height `--dsz-20`, padding 1×7×0, radius 4, Bebas 700 fs-12 tracking-10 t87, `inset line-strong`. Neutral ("Invited", "Visit · Wk 5", "Committed").

## 8. Team measures `.mcards` / `.mrow`
- `.mcards`: 2 columns, gap `--col-gap`. Each card = one family (Character · On the floor).
- `.mrow` (link to the measure's detail/explainer): grid `1fr --dsz-64 (--dsz-118+30) --dsz-44`, gap `--dsp-16`, padding `--dsp-12`×2, top 1px line (not after the card header).
  - Name Inter 600 fs-14 t87 (hover t100) + description fs-11 t60.
  - Value Bebas 700 fs-28 t100, right-aligned, scale `/25` at .6em t38.
  - Meter: Round 2 `.meter` (neutral w-62 on w-7) = value / scale.
  - Delta: Round 2 `.chip` up / down / flat (`—`), right-aligned. Only movers are coloured.

## 9. Detail page (T3)
### Bar `.dt-bar`
- Sticky top 0, `--z-sticky-head`, height `--dsz-60`, padding-top 6, gap 14; background `linear-gradient(--bg-page-solid 85%, --bg-page)`.
- **Up one level `.up`:** height 32, padding 1×12×0×8, radius 8, `inset line-strong`; back arrow 16 + parent name in Bebas 700 fs-16 tracking-4 t87. Hover w-7 t100. Focus outline 2px offset 2. Returns to the parent list with its scroll, sort and scope restored. Esc / browser back do the same.
- **Crumb `.dt-crumb`:** fs-12 t60, separators "/" t38, current `b` 600 t87. Ancestors are links.
- **Pager `.pager`:** right; two 28×28 buttons (radius 7, `inset line-strong`, chevron 14) around "4 of 12" (Inter 600 fs-12 t60). Walks the parent list in its current sort. `[` / `]` keys.

### Hero `.hero`
- Grid `auto 1fr auto`, gap `--dsp-20`, padding `--dsp-16`×`--dsp-20`×`--dsp-16`×`--dsp-16`, radius 14, `--shadow-card`. `--tc` = team colour.
- Team wash (player, team): `linear-gradient(112deg, mix(tc,42%) 0%, mix(tc,14%) 42%, transparent 72%)` over `linear-gradient(w-4p5, w-2)`; border mix(tc,45%); 3px top bar `linear-gradient(90deg, tc, transparent 80%)`. Same vocabulary as the Office result card.
- **`.neutral`** (recruit): Round 2 card fill, `--line` border, no bar.
- **Media:** player `.portrait` `--dsz-118` × 1.2 (118×142 / 139×167), `object-position 50% 22%`. Team `.hero-lg` `--dsz-118` square holding a 96px logo (113 at 1920).
- **Identity `.hero-id`** (gap `--dsp-8`): eyebrow `.hero-k` (logo 18 + team/role, Inter 600 fs-11 UPPERCASE tracking-8 t60) · name `.hero-n` Bebas 700 fs-48 lh .9 t100 (jersey `.jn` t38 before it) · bio `.hero-bio` fs-13 t87 with `.pos` chip, "·" t38 · RT `.hero-rt`: current Bebas 700 fs-40, arrow fs-14 t38, potential fs-28, caption Inter 700 fs-10 UPPERCASE t60 · optional `.hero-act` (buttons, gap 10).
- **Key numbers `.hero-stats`:** left rule 1px w-10, padding-left `--dsp-20`; eyebrow (season · GP · per game) then `.hs-row` (gap `--dsp-24`): value Bebas 700 fs-40 lh .85 t100 (unit .55em t60) + label Inter 700 fs-10 UPPERCASE t60. `.hs-row.sm` second row at fs-22 (1920 only).

### Body `.dt-body`
- Grid `minmax(0,1.3fr) minmax(0,1fr)`, gap `--col-gap`, margin-top `--col-gap`; `.span` = full width; `.dt-side` stacks cards (gap `--col-gap`). Sections are Round 2 `.card`s with `card-h`; no tabs, no internal scroll.
- **Attribute panel `.apan`:** 3 columns (gap `--dsp-12`×`--dsp-20`) of 6 groups `.apg`. Group label `h4` Inter 700 fs-10 UPPERCASE tracking-10 t38, bottom 1px `line-strong`. Row `.apr`: grid `1fr auto`, min-height `--dsz-40`, bottom 1px line; full name Inter 600 fs-13 t87 + abbr (700 fs-10 t38); 1920 adds the description (fs-11 t60); digit `.ad` right. Rows carry the description as `title` at 1280.
- **Development `.dev-f`:** padding `--dsp-10`×`--dsp-12`, radius 10, w-3, `inset line`; eyebrow "Focus" · focus name Bebas 700 fs-24 t100 · "Trains ST · …" fs-11 t60. Header link to Team › Development (where it's changed).
- **Recent changes:** Round 2 `.mv-p` rows — attribute name t87 + week fs-12 t60 · from → to digits (`.tdig`, each its own tier) · delta `.chip`.
- **Stats:** `.seg` Per game · Totals + "Game log →" in the card header; `.tbl.flat` career table (current season `.cur`, career `.tot`).
- **Schedule list `.sch` / `.sch-r`** (team page): grid `--dsz-40 1fr auto`, height `--dsz-34`, padding 0×`--dsp-8`, top 1px line. Week fs-11 700 t38 · `.nxc` opponent · result `.sch-res` (W/L letter Bebas 700 fs-15 in `--dsz-18` + score, 600 t87; loss `.l` t60) or upcoming `.sch-up` fs-12 t60. Game vs your team `.me` (navy). Hover w-4. Sub-heads "Results · 18–3" / "Upcoming" (`.sub-h`).

## 10. Buttons
- **Orange action `.btn-o`** — saves and non-advancing actions (Offer promise, Invite, Save focus): height `--dsz-34`, min-width 118, padding 1×16×0, radius 10, `--orange` fill, `--badge-ink` text, Bebas 700 fs-16 `--tracking-btn-sm`, 1px w-28 border, `inset 0 1px 0 w-35`. Hover brightness 1.06 + −1px; pressed +1px scale .985 brightness .94 (`--dur-press`); disabled = Advance disabled vocabulary (w-6, t38, w-12 border, not-allowed). Saving state: label → "SAVING…", no spinner. At most one orange action per section.
- **`.btn-ghost.sm`** — navigation / secondary (Scout them): Round 2 ghost at height `--dsz-34`, fs-16, nowrap.

---

## Motion
- Hover/colour transitions `--dur-hover` (120ms). Button press `--dur-press`.
- Scope/sort/sub-tab change: content crossfade `--dur-hover`, no vertical shift. Sorting re-orders rows instantly (no row animation — tables of 32–128 rows).
- Wide table: fades and map thumb transition `--dur-hover`; paging and jumps use smooth scrolling.
- Tooltip: 300ms hover delay, fade `--dur-hover`; immediate on keyboard focus.
- Skeleton pulse `--dur-skeleton` (1.4s). Content replaces skeletons without animation.
- Detail open/back: page swap, no slide. Back restores the list scroll position exactly.
- Reduced motion: all transitions/animations off (Round 2 global rule); smooth scroll → instant.
