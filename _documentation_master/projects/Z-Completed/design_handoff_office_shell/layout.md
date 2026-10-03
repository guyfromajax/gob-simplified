# Layout rules

## Density sets
There are two density sets, selected by a class on the root `.gob` element. Set the class from the viewport in JS:

```js
const lg = matchMedia('(min-width: 1680px) and (min-height: 1000px)');
const apply = () => root.classList.toggle('gob-1920', lg.matches) || root.classList.toggle('gob-1280', !lg.matches);
lg.addEventListener('change', apply); apply();
```
In production, give `.gob` `width:100vw;height:100vh`. The fixed `1280×720` / `1920×1080` sizes in `components.css` exist for the reference frames only.

| | 1280 set (`.gob-1280`, default) | 1920 set (`.gob-1920`) |
|---|---|---|
| Applies at | viewport < 1680 wide **or** < 1000 tall (design floor 1280×720) | ≥ 1680×1000 (designed at 1920×1080) |
| Top bar `--top-h` | 56px | 64px |
| Rail `--rail-w` | 64px, icons only, labels via `title` tooltip / hover-expand | 200px, icons + labels |
| Page padding `--page-pad` | 18px | 28px |
| Column gap `--col-gap` | 16px | 24px |
| Type `--fs-*`, density spacing `--dsp-*`, density sizes `--dsz-*` | base values | ≈ ×1.18 (rounded to 0.5px) |
| Fixed spacing `--space-*`, radii, lines | same | same |

## Shell grid
```
.app  grid-template-rows: var(--top-h) minmax(0,1fr)
      grid-template-columns: var(--rail-w) minmax(0,1fr)
.top  spans both columns
.rail column 1 / .main column 2 (padding var(--page-pad), overflow-y:auto)
```
- **Max content width:** `.office` caps at **1664px**, centred, so viewports wider than 1920 add margin rather than stretching the cards. The top bar and rail always span the full window.
- **Scrolling:** Office states are designed to fit 1280×720 with nothing below the fold. Design against the worst-case row count. `.main` is `overflow-y:auto` only so that a user who shrinks the window below 720 can still reach everything. No card ever scrolls internally. Long lists show their top items plus a "See all" link.
- **Section pages** (e.g. Team → Roster): `.main.scroll` removes the top padding. `.pg-head` (title + sub-tabs) is `position:sticky; top:0`, height `--dsz-118`. The table's `th` is sticky at `top: var(--dsz-118)`. Only the page scrolls; there are no nested scroll areas.
- **Overlays:** the Settings panel and scrim are absolutely positioned inside `.app`, starting at `left: var(--rail-w)` and `top: var(--top-h)`. The top bar and rail stay visible and usable.

## The Office grid
```
.office  display:grid; height:100%; gap: var(--col-gap)
  1280:  grid-template-columns: minmax(0,.9fr) minmax(0,1.36fr) minmax(0,1.04fr)
  1920:  grid-template-columns: minmax(0,.86fr) minmax(0,1.3fr) minmax(0,1.14fr)
.office-col  flex column, gap var(--dsp-12) (1280: 10px); children flex-shrink:0
```
Resulting column widths at the design sizes:
- **1280:** ≈ 313 / 473 / 362px.
- **1920:** ≈ 421 / 637 / 558px.

Columns always read left to right: **01 This week → 02 Since last week → 03 Next game**. In two states the zones change:

| State | Column 2 | Column 3 |
|---|---|---|
| Win / loss / tournament | Result card · What moved · Recruiting wire | Next game · Team snapshot |
| First week | Season preview · one-line Wire card | Next game (season opener) · Team snapshot |
| Signing Day | Result card (season final) · Final standings | **Signing Day card only** |

## What appears or disappears between sizes
| Element | 1280 | 1920 |
|---|---|---|
| Rail labels | hidden (tooltip) | shown |
| To-do list | first 4 items (tasks first, then notes) + "See all · N more" | all items |
| To-do second line (`td-m2`) | hidden | shown |
| Result portrait | 46px | 76px |
| POTG shooting line (FG / 3PT / MIN) | hidden | shown |
| Loss "Up next · Scout them" row | hidden (column 3 covers it) | shown |
| Avatars in What moved, Wire and Signing targets | hidden | 30–32px |
| Next game: players to watch | top scorer + top rebounder rows | replaced by **projected starting five** with leader tags |
| Tournament card RT | inline after each team's record | separate Team RT row |
| Tournament stakes copy | short ("Winner → Keystone Final") | full sentence |

The extra room at 1920 adds depth (more items, portraits). It never adds new sections.

## Worst-case fit (1280×720)
Measured gap from the bottom of each column to the fold, in the reference frames:
- **Win:** 205 / 12 / 44px.
- **Loss:** 224 / 12 / 44px.
- **First week:** 255 / 214 / 44px.
- **Tournament:** 235 / 12 / 15px.
- **Signing Day:** 280 / 67 / 182px.

At 1920×1080, win is 424 / 46 / 165px and tournament is 457 / 46 / 20px.

The middle column is the tight one at 1280, as is the tournament right column. If you add a row there, remove one.
