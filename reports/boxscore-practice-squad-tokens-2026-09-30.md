# Box score + practice squad design-system migration (2026-09-30)

Branch: `ux/boxscore-practice-squad-tokens` from `origin/develop` (includes `fix/submit-cuts`).

## Summary

Migrated `/box-score.html` and week-1 `/cut-players.html` onto `html.gob` + token CSS (browse/focus shell patterns). Removed the sunset week-35 `mode=cut` frontend (`isCutMode`, `submitFinalCuts`, **Submit Cuts**). Kept `POST /franchise/cut-players-final` on the backend (still used by `tests/test_browse_rev.py`; no FE caller).

Practice-squad **Assign Practice Squad** uses `.gob-btn--action` (committed orange): it POSTs assignment and `exitFlow`s to the FCC hub — a save/commit, not the single green Advance (`gob-btn--gate`).

## Colour-law choices

| Area | Before (conflict) | After |
|------|-------------------|--------|
| Box score scouting EV rows | Green/red `.ev-positive` / `.ev-negative` | Neutral `--text-87` / `--text-60` |
| Box score section chrome | Orange `#F79420` borders/titles | `--line` / `--text-60` |
| Box score attribute chips (up) | Green borders/values | Kept green with `/* colour-law: positive-data */` |
| Box score user W/L | (none) | White outline plate `#user-game-wl-plate` — never win-green / loss-red |
| Box score POTG portrait | 8px radius | Square (`border-radius: 0`) |
| Cut page submit | `.gob-action-btn.is-green` | `.gob-btn--action` (orange commit) |
| Cut checkbox / GR badge / pulse | Green accent / green pulse | Neutral `--text-60` / white-grey pulse |
| Cut modal “assigning” accent | `is-green` | `is-red` (non-reward chrome) |

## Week-35 cut removal

Removed from `cut-players.js` / HTML: `isCutMode`, `nextUrl`, `goNext`, `submitFinalCuts`, `mode=cut` DOM relabel, training-squad pool merge, week-35 recruiting redirect.

**Caller check for `POST /franchise/cut-players-final`:**

| Layer | Caller |
|-------|--------|
| FE | None (removed) |
| BE | Route remains in `franchise_routes.py` |
| Tests | `tests/test_browse_rev.py` (rev/concurrency writer) |
| Desktop/scripts | None found |

## Token / allow-list

- Added `box-score.css` and `cut-players.css` to `NEW_DESIGN_CSS` in `scripts/check_ui_tokens.py`.
- Literal brand hex in those files (develop → now): box-score `#34EC27`/`#F79420`/`#0b0d14` hits 8 → 0; cut-players green literals 3 → 0.
- `check_ui_tokens.py --strict --no-write`: exit 0 (new-surface colour-law: 1 green allowlisted positive-data on box-score attr chips).
- Shrunk Gate B allowlist: removed `FrontEnd/static/cut-players.js` (0 URLSearchParams reads after cleanup).

## Gates

| Gate | Result |
|------|--------|
| `pytest --ignore=tests/e2e -q` | **4260 passed**, 14 skipped, 109 xfailed, 1 xpassed |
| Playwright `--workers=1` (CI unset) | **755 passed**, 6 skipped |
| `check_ui_tokens.py --strict --no-write` | exit **0** |
| `check_migration_gates.py` | **passed** — Gate A: 0 / 0 files; Gate B: **134** lines / **43** files |

## Screenshots (`reports/boxscore-practice-squad-tokens/`)

| Page | Viewport | Before | After |
|------|----------|--------|-------|
| Box score | 1280 browse | `before-box-score-browse-1280.png` (shell-2 baseline on develop) | `after-box-score-browse-1280.png` |
| Box score | 1920 browse | `before-box-score-browse-1920.png` | `after-box-score-browse-1920.png` |
| Box score | 1280 focus | `before-box-score-focus-1280.png` | `after-box-score-focus-1280.png` |
| Box score | 1920 focus | `before-box-score-focus-1920.png` | `after-box-score-focus-1920.png` |
| Practice squad | 1280 wrong count | `before-cut-wrong-count-1280.png` (submit-cuts baseline) | `after-cut-wrong-count-1280.png` |
| Practice squad | 1280 exact count | `before-cut-exact-count-1280.png` | `after-cut-exact-count-1280.png` |
| Practice squad | 1280 confirm modal | `before-cut-confirm-modal-1280.png` | `after-cut-confirm-modal-1280.png` |
| Practice squad | 1920 confirm modal | — | `after-cut-confirm-modal-1920.png` |

E2E: `tests/e2e/boxscore-practice-squad-tokens.spec.js` (W/L plate, no illegal green on plate/name cell, square POTG, orange enabled submit). `submit-cuts.spec.js` unchanged green.

## Files touched

- `FrontEnd/static/box-score.html`, `box-score.css`, `box-score.js`
- `FrontEnd/static/cut-players.html`, `cut-players.css`, `cut-players.js`
- `scripts/check_ui_tokens.py`, `scripts/ci/migration_gates_allowlist.json`
- `tests/e2e/boxscore-practice-squad-tokens.spec.js`
- `_documentation_master/04_Franchise_Mode_Systems/Practice_Squad_System.md`
- `_documentation_master/11_Design_Systems/UX_System.md`
