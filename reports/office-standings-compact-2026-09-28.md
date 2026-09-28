# Office conference standings: compact rows before windowing (2026-09-28)

Branch: `ux/office-standings-compact` (from origin/develop ee7eece4c). Commit: 249f81a37.

## Result

The standings card now tightens its rows in two steps before it falls back to windowing. The card's footprint, the column layout and every other Office card are unchanged.

- **1440×900 (gob-1280):** all 8 of 8 teams in every Office state, using compact rows. Before, it showed 7 of 8. This is the "two rows short" case in Jamie's screenshot, where he saw rows 3–8.
- **1920×1080 (gob-1920):** 8 of 8, unchanged (normal rows). The tournament state is still a window of 7 of 8, now with tight rows.
- **1280×720 (gob-1280):** windowing is still the last resort. The window grows from 2 to 4 teams in five of the six states. Signing day shows all 8 compact.
- **1066×640 and 1024×600 (gob-1280):** a window of 2. The page itself still scrolls 22–69px, because the Office layout overflows at these sizes before the standings card is involved.
- **10-team conference:** no real conference has more than 8 teams (the live database has 16 conferences of 8). With a synthetic 10-team conference, 1920×1080 shows all 10 compact, and 1280×720 shows a tight window of 4 of 10.

## Why 1280×720 still windows

The standings card sits under Next game and Team snapshot in the middle column. At 1280×720 that leaves the card about 106px. Eight compact rows plus the card heading need about 240px. Even the tight step (20px rows, no column header) needs about 200px. Fitting all 8 would mean slimming or moving another card, which was ruled out (option C).

## Change

`FrontEnd/static/js/shared/officeHome.js`

- `fitStandings` now tries the steps in this order: normal rows, compact rows, tight rows, then windowing (tight rows, shrinking the window around the user, as before).
- The card records `data-standings-mode`: `all`, `compact` or `window`. It records `data-standings-density`: `normal`, `compact` or `tight`. `data-standings-shown` and `data-standings-total` are unchanged.
- "Full standings →" is in the card head in compact and window modes. At normal density with every team shown, there is no link, as before.
- `standingsOverflow` also compares the column's scroll height when the card is compact, on both tiers. Without this, tight rows in the tournament state at 1920 pushed the card 8px past the bottom of its column.

`FrontEnd/static/css/office-home.css` (tokens only, scoped to `.office-st`)

- `.is-compact`: team name `--fs-13` → `--fs-12`; W-L `--fs-22` → `--fs-16`; row line-height `--lh-1`; at gob-1280, row padding `--dsp-6` → `--dsp-4` (the user row keeps `--dsp-8` side padding).
- `.is-tight` (added on top of compact): the column-header row is hidden; W-L `--fs-14`; at gob-1280, vertical row padding is `--space-2`.
- The user row keeps its navy background at every density.

## Measurements (8-team conference, `win` state, after)

| Viewport (innerWidth×innerHeight) | Tier | Mode / density | Shown | Row px | Card px (w×h) | Page scroll |
|---|---|---|---|---|---|---|
| 1280×720 | gob-1280 | window / tight | 4 of 8 | 20 | 383×106 | 0 |
| 1440×900 | gob-1280 | compact / compact | 8 of 8 | 25 | 436×236 | 0 |
| 1920×1080 | gob-1920 | all / normal | 8 of 8 | 27 | 539×290 | 0 |
| 1066×640 | gob-1280 | window / tight | 2 of 8 | 20 | 311×66 | 29 |
| 1024×600 | gob-1280 | window / tight | 2 of 8 | 20 | 297×66 | 69 |

Before, the same fixture showed 2, 7, 8, 2 and 2 of 8, with 35px rows at gob-1280. The six-state sweep is in `office-standings-compact/before-fit.json` and `after-fit.json`.

## Tests

`tests/e2e/office-frontend.spec.js`

- New test: "standings show every conference team by tightening rows before windowing". It logs `innerWidth`/`innerHeight` and the tier, and checks the five viewports above plus the 10-team conference.
  - At 1440×900 and 1920×1080 it asserts shown equals total, the last row is above the fold, and there is no page scroll or column clip.
  - At 1280×720 and smaller it asserts a tight window: at least 4 teams at 1280×720 (at least 2 below that) and no page scroll at 1280×720.
  - At every size it asserts the user row is navy and "Full standings" is in the head whenever the card isn't at normal density.
  - With `STANDINGS_SWEEP=1` it also records all six Office states.
- "Next game, standings, chemistry, and attitude":
  - The existing checks that standings rows match the watch row now apply at normal density only. At compact and tight density it checks the 12px name, the 16px or 14px W-L, and the hidden column header.
  - At 1440×900 it now expects all 8 teams.
- "Six states fit": compact mode counts as a full table, and the 1920 clip check covers it.

Runs (port 8157, workers=1, CI unset):

- `office-frontend.spec.js`: 10 passed, 1 skipped (environment-gated).
- Full suite (`tests/e2e`, run after checking that no other agent's Playwright was running): 514 passed, 2 skipped (environment-gated), 7.8 minutes. The server stopped afterwards; nothing is listening on 8157.
- Screenshots: `reports/office-standings-compact/before-*.png` and `after-*.png` at 1280×720 and 1920×1080.
- Regenerated `reports/office-tweaks-4` images were restored, and the untracked suite folders were removed.

STATUS: COMPLETE
