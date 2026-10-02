# Player Development grid — one layout on both pages, in RT order (polish/player-dev-grid, 2026-10-02)

Branch `polish/player-dev-grid` off `origin/develop` `665fce713`. `origin/develop` moved to `b24564e67` (polish/news-followups) after the first gate run; merged as `083e326b1` with no conflict and none of this branch's files touched. The gates below are on `083e326b1` (the first run on `0af076e3b` had the same results: pytest 4441 passed, Playwright 1157 passed / 43 skipped). Worktree `~/gob-player-dev-grid`. Ready for review.

## What changed

| # | Item | Result |
|---|---|---|
| 1 | Prep › Player Training › Player Development was one long table | Draws the same four-across cards as the Training page, from the one component (`playerDevelopmentGrid.js`). Position and training selectors work in every cell and save on change. |
| 2 | Order on both pages | By current RT, highest first, reading left to right, then top to bottom. Ties keep the order the roster arrived in. |

### Root cause

`playerDevelopmentGrid.js` had two layouts behind a `layout` option: `'cards'` (Training page; four CSS columns, `column-count`, filled down each column from `--pdg-rows`) and `'table'` (Prep; `<table>` with portrait, jersey, current → potential RT, Pos column). Neither sorted; both drew the roster in server order (`/franchise/training-points` `custom_focus_roster` = the franchise's `players` order).

### What changed, where

| File | Change |
|---|---|
| `FrontEnd/static/js/shared/playerDevelopmentGrid.js` | `orderByRt(players)` (exported): sort by the RT the card shows, `-Infinity` for a missing rating, ties by arrival index. `render` always draws cards (`pdg-layout-cards`), no `layout` option. `portraitHtml`, `rtPairHtml`, `tableRowHtml` removed. Header comment states the order rule. |
| `FrontEnd/static/css/player-development-grid.css` | `.pdg-grid` is a CSS grid: `repeat(4, minmax(0, 1fr))`, `grid-auto-flow: row` (was `column-count: 4` with `--pdg-rows`). Two columns under 1100px. Table rules removed. |
| `FrontEnd/static/training.css` | Dead `.pdg-table` / `.pdg-layout-table` rules removed. |
| `FrontEnd/static/training.js` | No `layout` option passed. |
| `_documentation_master/11_Design_Systems/UX_System.md` | Prep › Player Training row; the Player Development grid row now states one component, one layout, both hosts, the order rule, and what a longer roster does; `.pdg-av` dropped from the headshot-radius list. |

Server untouched: the roster order on the wire is unchanged; the client sorts.

### Decisions (stated, not guessed)

- **Which RT.** "Current RT" = the RT each card already shows: the rating at the player's **training** position (`rtAtTrainingPosition`, i.e. `GOBDevelopmentFocus.positionOf`). That is the number the coach reads on the card, so the order matches what is visible.
- **When.** The order is set when the grid renders. Changing a position repaints that card's RT but does **not** move the card (re-sorting would pull a card out from under the cursor right after it was used). The next render (reload, tab change, week advance) re-orders. Pinned by `tests/e2e/player-dev-grid.spec.js` "a change does not move the card".
- **More than 12 players.** Same as the Training page already did: the grid adds a row. Fifteen in camp = four rows, the last of three cards (shots `*-camp-*`). Nothing is hidden or paged; everyone can be set.
- **Ties.** Stable: `Array.prototype.sort` with the arrival index as the tiebreak, so equal RTs keep the server order.

### Question for Jamie

The Prep table variant showed two things the cards do not: the **potential RT** (`current → potential`) and a jersey number. The brief says reuse the Training page component and do not build a second version, so those are gone from Prep. If the potential RT should stay visible on Prep (it is still in the payload), say where, and it goes on the card for both hosts.

## Tests

| Test | What it pins |
|---|---|
| `tests/test_player_development_grid.py` | One layout for both hosts (no `pdg-table`, `tableRowHtml`, `layout` option); `orderByRt` exported and used once in `render`; node harness: cards ordered by shown RT, ties keep order, a missing RT goes last. |
| `tests/test_training_page_phase5.py` | Grid is four across, filled row by row (`grid-template-columns: repeat(4…)`, `grid-auto-flow: row`), no `column-count` / `--pdg-rows`. |
| `tests/e2e/player-dev-grid.spec.js` (new, 9) | Both hosts × camp (15) / in season (12) with a shuffled payload: 4 per row, RT descending reading left→right then down; ties keep arrival order; Prep selectors in every cell save (`PATCH` seen) and the card stays put; both pages draw the same card markup; shots. |
| `tests/e2e/polish-training-playbooks.spec.js` | T2/T3 row-major positions (`xs[i % 4]`, `ys[Math.floor(i / 4)]`), 15-player row; T10 expects `.pdg-card` ×12 and no `.pdg-table`. |
| `tests/e2e/fcc-peel-2.spec.js` | Prep ready selector `#training-view .pdg-card` (was `.pdg-row` / `table`). |

Fail-on-old-code: `player-dev-grid.spec.js` run against `665fce713`'s four product files — **9 failed** (Prep drew a table, Training cards ran down columns). Restored, 9 passed.

## Shots (`reports/player-dev-grid/`, 1280×720 and 1920×1080)

| Page | State | Full page | Grid close-up |
|---|---|---|---|
| Prep › Player Training › Player Development | in season (12) | `player-development-in-season-after-<w>.png` | `player-development-in-season-grid-after-<w>.png` |
| same | camp (15) | `player-development-camp-after-<w>.png` | `player-development-camp-grid-after-<w>.png` |
| Training page | in season (12) | `training-page-in-season-after-<w>.png` | `training-page-in-season-grid-after-<w>.png` |
| same | camp (15) | `training-page-camp-after-<w>.png` | `training-page-camp-grid-after-<w>.png` |

## Gates (merged tree `083e326b1` = this branch + `origin/develop` @ `b24564e67`)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | 4450 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed (the two XPASS are pre-existing; `known_failures.py` not edited) |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 |
| `scripts/ci/check_migration_gates.py` | passed (Gate A 0; Gate B 133 lines / 43 files; pre-existing note that `newsView.js` fell 3 → 2, allow-list not touched) |
| `franchise-command-center.css` | 1779 lines, not touched |
| Related specs (21 files touching the grid or its pages) | 222 passed, 15 skipped, 1 failed → the `fcc-peel-2` ready selector, fixed; 4 passed alone |
| Full Playwright (one run on the merged tree, under the lock, 1 worker) | 1177 passed, 43 skipped, 1 failed → `news-back.spec.js:138` ("← News" returns to the feed), a News spec this branch does not touch, from the develop merge; alone with `--repeat-each=5`: 5 passed. Flake, not a regression. Lock held 18:58–19:20. |

Limits kept: no sim / finalize / cpu_week_pool / sim_rng changes; tokens only; explicit paths; the `.venv` / `node_modules` symlinks another agent left in this worktree are untracked and not staged.

**Full suite: pytest 4450 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed · Playwright 1177 passed, 43 skipped, 1 failed (news-back.spec.js:138, 5/5 passed alone).**
