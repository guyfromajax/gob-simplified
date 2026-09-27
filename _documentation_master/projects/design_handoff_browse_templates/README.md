# Handoff: GOB — Browse page templates (T1 table · T2 attribute grid · T3 detail)

## Overview
Three page templates that every browse page in the franchise app is built from. Each sits inside the approved franchise shell (top bar + rail + sticky section title and parallelogram sub-tabs) from the Office/Shell handoff. Pages are views inside one app and switch instantly.

| Template | Used by | Frames |
|---|---|---|
| **T1 · Table page** | League › Standings · Rankings · Leaders · Team Stats · Schedule; Team › Player Stats · Schedule | `t1-standings-1280/1920`, `t1-team-stats-1280/1920`, `t1-leaders-1280` |
| **T2 · Attribute grid** | Team › Roster, Team › Team Attributes, Recruiting › Pool | `t2-roster-1280/1920`, `t2-recruit-pool-1280`, `t2-team-attributes-1280` |
| **T3 · Detail page** | Player, team, recruit (third level only) | `t3-player-1280/1920`, `t3-team-1280` |

Plus `frames/component-sheet.html` — the Round 2 sheet (unchanged, Part 1) followed by every new component and state (Part 2).

## About these files
Plain HTML/CSS/JS, same as the target codebase. `frames/*.html` are static, high-fidelity references whose markup and CSS are written to be copied — but they are **reference implementations, not drop-in files**: wire them to real data and routes, merge them into the existing page structure, and keep behaviour that already works.

`tokens.css` and `components.css` are the Round 2 files, carried over byte-for-byte except **one new token** in `tokens.css` (`--dur-skeleton`, see `decisions.md`). Everything new lives in `templates.css`. `templates.js` is reference behaviour for the wide-table card only.

## Fidelity
High fidelity. Colours, type, spacing, radii, states and motion are final and use tokens only. Literal px left in `templates.css` are component dimensions and are listed in `components.md`.

## Rules for the implementing agent (read first)
1. **Before writing any code, report back:**
   - which existing files own each affected page (Standings, Rankings, Leaders, Team Stats, Schedule, Player Stats, Roster, Team Attributes, recruit pool, player / team / recruit pages) and the shared table / attribute-tile code (`attrTiles.js`, `attr-tiles.css`, `rt-buckets.css`, the lean ladder);
   - which data fields actually exist for every value in **Data needed** below.
2. **Never invent, derive or approximate a missing field.** If a mock value has no backing field, stop and ask. This includes things that look derivable (PCT, games back, team attribute averages).
3. **Don't micromanage what already works.** Keep existing CTA copy, existing column sets where a page already has them, and existing colour scalings (shot weight keeps its own programmed scaling and thresholds — never substitute a ramp).
4. **All sample values are illustrative** — names, teams, records, stat values, measure values/scales, dev-focus labels, lean ladders, tag and CTA labels, initials standing in for headshots, the portrait image, letter monograms standing in for logos. Only structure, tokens and behaviour are specified.
5. **Canonical encodings, game-wide:**
   - **Attributes** display as one digit = `floor(raw/10)`, no cap: 0–4 `--red` · 5–6 `--yellow` · 7–8 `--green` · 9+ `--blue`.
   - **Player RT** (current → potential) is **always a letter grade** (A/B/C/D/F with +/−), never a digit: A blue · B green · C yellow · D/F red. Use `getRtBucketClass()` / `rt-buckets.css` — don't hardcode thresholds.
   - Channels: hue on a glyph = tier (attribute digit, RT letter); hue on a bar/fill = energy; luminance only = supporting numbers and magnitudes; direction/position = diverging values (DIFF). **Blue appears only as elite rating** (RT A / attribute 9+).
6. **Green `#34EC27` is only the top-bar Advance** as an action. **Orange** = saves / non-advancing actions (watch star, `.btn-o`). **Navy** = structure and selection: the user's own team/player row, switch-on. Sort, scope and tab selection are neutral white.
7. **Exactly one vertical scroll per page** (`.main`). No nested vertical scroll boxes. Table headers stick directly under the sticky page head. A table genuinely wider than the page scrolls horizontally inside its own card (`.xs`) with edge fades and **no sticky header**.
8. **No spinners anywhere.** Loading = neutral skeletons in the final shapes (`.sk`).
9. **Navigation cap:** section → sub-tab. A third level exists only for player / team / recruit detail pages, always with the "up one level" back (`.up`).
10. Everything works at 1280×720 (floor) and 1920×1080. Density comes from the root class (`.gob-1280` / `.gob-1920`, see `layout.md`).

## Files
```
tokens.css        Round 2 tokens + 1 new token (--dur-skeleton)
components.css    Round 2 components (unchanged)
templates.css     all new T1/T2/T3 components, tokens only
templates.js      reference behaviour: wide-table fades, map, paging, group jumps
components.md     every new component: dimensions, tokens, states, motion
layout.md         per-template anatomy, grids, breakpoints, sticky/scroll rules, measured fits
decisions.md      everything decided that wasn't in the brief — confirm before shipping
index.html        links to every frame
frames/
  t1-standings-1280.html     t1-standings-1920.html
  t1-team-stats-1280.html    t1-team-stats-1920.html
  t1-leaders-1280.html
  t2-roster-1280.html        t2-roster-1920.html
  t2-recruit-pool-1280.html  t2-team-attributes-1280.html
  t3-player-1280.html        t3-player-1920.html
  t3-team-1280.html
  component-sheet.html       Part 1 Office + Shell · Part 2 Browse templates
assets/portrait-placeholder.png   illustrative headshot (replace with real portraits)
fonts/BebasNeuePro-*.otf          display face (Inter loads from Google Fonts)
```
Open any frame directly in a browser. Frames load `../tokens.css`, `../components.css`, `../templates.css`, `../templates.js`.

## How the CSS is organised
- Root `.gob` + density class; shell `.app` › `.top` / `.rail` / `.main.scroll` exactly as Round 2.
- **T1/T2 pages:** `.pg-head` (Round 2) with optional `.pg-tools` at the right of `.subtabs` → content: `.tcard > table.tbl` (+ `.grp` two-row header, `.agrid` attribute grid, `.fx` fixed columns, `.tight` wide-grid padding), or `.xs` for the wide case, or `.ldr-grid` / `.mcards` board layouts.
- **T3 pages:** `.dt-bar` (sticky) → `.hero` → `.dt-body` of `.card` sections.
- Inline custom properties are **data**: `--tc` (team colour on `.logo` / `.hero`), `--v` (0–1 magnitude on `.dv`). `.xs` receives `--pin-w` from `templates.js`.
- `.is-hover`, `.is-press`, `.is-focus`, `.is-disabled` exist so frames and the sheet can show states statically; in product use `:hover`, `:active`, `:focus-visible`, `aria-disabled`.
- `.rtab` (Round 2 roster table) is superseded by `.tbl`; same header surface, row rhythm and sticky offset.

## Data needed (confirm each exists — do not invent)
- **Standings:** per team: conference, conference place, W, L, PF, PA, DIFF, streak, national rank (or unranked), next opponent + home/away + day/time. Region and national groupings (regions × conferences).
- **Rankings:** rank, team, W–L, last-week result, next opponent; Top 25 and all 128.
- **Leaders:** per category (PTS, REB, AST, STL, BLK, 3PM, FG%, DEF%) × scope (conference / national) × per-game / totals: top N players with team, position, year, value. **Qualification rule for % categories** — confirm.
- **Team Stats:** the ~23 team columns (FGM FGA FG% · 3PM 3PA 3P% · FTM FTA FT% · OREB DREB REB · AST STL BLK TO PF · OPP PPG, OPP FG%, OPP 3P%, DEF%), GP, PPG; per game and totals. Use the production column set if it differs.
- **Roster:** jersey, name, RT current + potential letters, POS, YR, HT, WT, 12 attributes (raw → digit), dev focus, starter flag / lineup order, varsity vs practice squad.
- **Recruit pool:** name, region, RT letters, POS, HT, WT, 12 attributes, watchlist flag, lean ladder (top schools in order, your position or not listed), scope counts.
- **Team Attributes:** each team measure's name, value, scale max, weekly delta, and a one-line description. **Scales for Fight / Discipline / Shooting / Rebounding / Defensive efficiency** — confirm (mock shows /100).
- **Player page:** portrait, jersey, name, team, role (starter/bench), POS, YR, HT, WT, RT letters, 12 attributes, dev focus (+ which attribute it trains), attribute change history (week, attribute, from, to), season line, career lines by season + career total.
- **Team page:** logo, name, conference, region, record, national rank, conference place, next game, roster (jersey, name, RT, POS, YR, HT, PTS, REB), results (week, opp, site, W/L, score) and upcoming (week, opp, site, day/time).
- **Recruit page:** headshot, name, class, region, POS, HT, WT, RT letters, attributes, lean ladder, visit/invite status, available actions.
- **Detail pager:** the ordered list the user came from (for "4 of 12" and prev/next).

## Assets
- Portrait: `assets/portrait-placeholder.png`, illustrative only. Initials in `.av` stand in for headshots in lists.
- Team logos: letter monograms drawn by `.logo` with `--tc`. Replace with real logos at the same sizes.
- Icons: inline 24×24 stroke SVGs, stroke-width 1.8, round caps/joins, `currentColor` (Round 2 set + search, chevrons, back arrow, star). If the codebase has an icon set, use it at the same size and weight.
