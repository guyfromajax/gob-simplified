# Box score + practice squad design-system migration (2026-09-30)

Branch: `ux/boxscore-practice-squad-tokens` from `origin/develop` (includes `fix/submit-cuts`, merged **`origin/develop`** again 2026-10-01: `fix/fcc-load-retry`, `fix/roster-name-lookup-mongomock`, shell 404/maintenance, `fcc-load-retry.spec.js`, etc.).

## Summary

Migrated `/box-score.html` and week-1 `/cut-players.html` onto `html.gob` + token CSS (browse/focus shell patterns). Removed the sunset week-35 `mode=cut` frontend (`isCutMode`, `submitFinalCuts`, **Submit Cuts**). Kept `POST /franchise/cut-players-final` on the backend (still used by `tests/test_browse_rev.py`; no FE caller).

Practice-squad **Assign Practice Squad** uses `.gob-btn--action` (committed orange): it POSTs assignment and `exitFlow`s to the FCC hub — a save/commit, not the single green Advance (`gob-btn--gate`).

## Merge fix pass (2026-09-30 PM)

1. **POTG portrait** — `var(--radius-10)` at 72px (UX_System §2 large portrait corner). E2E guard: radius in px, `> 0`, `≤ 10`, not `%`.
2. **Assigning modal** — accent `neutral` (`.gob-modal-accent.is-neutral` → `var(--line)`); not red/green. **Confirm Practice Squad** stays **`is-red`** (unchanged from pre-token branch: destructive/warning confirm before an irreversible roster move; colour law allows red for danger, not for progress).
3. **Playwright** — see gates below.

## `submit-cuts.spec.js:212` repeat stress (Jamie's live bug)

**Verdict: test / environment isolation — not a product race.** No change to `cut-players.js` modal hoist, `exitFlow`, or submit re-enable for this flake.

**What we saw under `--repeat-each=5` (before hardening):** intermittent failures on the web assignment test — typically `page.waitForSelector('#cut-players-table .cut-player-checkbox')` timeout, `expect.poll(() => state.posts.length)` / FCC pathname wait timeout, or **`net::ERR_CONNECTION_REFUSED`** when another agent held `:8000` or killed `seed_and_serve` mid-suite. Not a stuck confirm modal or overlay-under-chrome regression.

**Why not product:** the same flow passes **10/10** on `submit-cuts.spec.js:212` with `--repeat-each=10` after test-only hardening; full suite **787 passed / 0 failed** with no FE change in this pass.

**Hardening (test-only):**

- Unique mock franchise per worker + repeat: `f-e2e-submit-cuts-w{workerIndex}-r{repeatEachIndex}` so mocked `state.assigned` / CC payload cannot collide across `--repeat-each` iterations.
- PNG captures only when `testInfo.repeatEachIndex === 0` (avoids parallel screenshot churn in `boxscore-practice-squad-tokens.spec.js`).

## Colour-law choices

| Area | Before (conflict) | After |
|------|-------------------|--------|
| Box score scouting EV rows | Green/red `.ev-positive` / `.ev-negative` | Neutral `--text-87` / `--text-60` |
| Box score section chrome | Orange `#F79420` borders/titles | `--line` / `--text-60` |
| Box score attribute chips (up) | Green borders/values | Kept green with `/* colour-law: positive-data */` |
| Box score user W/L | (none) | White outline plate `#user-game-wl-plate` — never win-green / loss-red |
| Box score POTG portrait | 8px radius / `0` | `--radius-10` (72px large portrait) |
| Cut page submit | `.gob-action-btn.is-green` | `.gob-btn--action` (orange commit) |
| Cut checkbox / GR badge / pulse | Green accent / green pulse | Neutral `--text-60` / white-grey pulse |
| Cut modal “assigning” | was `is-green`, briefly `is-red` | **`neutral`** (`--line`) |
| Cut modal “confirm” | `is-red` | **`is-red`** (kept) |

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
| `pytest --ignore=tests/e2e -q` | **4260 passed**, 14 skipped, 109 xfailed, 1 xpassed (post-merge; unchanged from prior commit on this branch) |
| Playwright targeted `boxscore-practice-squad-tokens.spec.js` + `submit-cuts.spec.js`, `--workers=1`, `--repeat-each=5`, `CI` unset, `PLAYWRIGHT_BROWSERS_PATH` unset | **20 passed**, **0 failed** (2026-10-01) |
| Playwright `submit-cuts.spec.js:212` only, `--repeat-each=10` | **10 passed**, **0 failed** |
| Playwright full (`workers=1`, `CI` unset, port **8000**, `/tmp/gob-full-playwright.lock`, `PLAYWRIGHT_BROWSERS_PATH` unset) | **787 passed**, **6 skipped**, **0 failed** (2026-10-01, ~12.1m; `npx playwright test --list` → **793** tests in **92** files) |
| `check_ui_tokens.py --strict --no-write` | exit **0** |
| `check_migration_gates.py` | **passed** — Gate A: 0 / 0 files; Gate B: **134** lines / **43** files |

### Playwright count note

After merging develop, the listed total is **793** (was **787** pre-merge: e.g. `fcc-load-retry.spec.js`, `shell-404-maintenance.spec.js`). The clean locked full run executed **793** cases with **787 passed + 6 skipped + 0 failed**. Use one full run under the lock; unset `PLAYWRIGHT_BROWSERS_PATH` in sandboxed shells so Chromium resolves from the normal Playwright cache.

## Screenshots (`reports/boxscore-practice-squad-tokens/`)

| Page | Viewport | Before | After |
|------|----------|--------|-------|
| Box score POTG | 1280 browse | (in browse baseline) | **`after-box-score-potg-1280.png`** |
| Box score | 1280 browse | `before-box-score-browse-1280.png` | `after-box-score-browse-1280.png` |
| Box score | 1920 browse | `before-box-score-browse-1920.png` | `after-box-score-browse-1920.png` |
| Box score | 1280 focus | `before-box-score-focus-1280.png` | `after-box-score-focus-1280.png` |
| Box score | 1920 focus | `before-box-score-focus-1920.png` | `after-box-score-focus-1920.png` |
| Practice squad assigning | 1280 | — | **`after-cut-assigning-modal-1280.png`** |
| Practice squad | 1280 wrong count | `before-cut-wrong-count-1280.png` | `after-cut-wrong-count-1280.png` |
| Practice squad | 1280 exact count | `before-cut-exact-count-1280.png` | `after-cut-exact-count-1280.png` |
| Practice squad | 1280 confirm modal | `before-cut-confirm-modal-1280.png` | `after-cut-confirm-modal-1280.png` |
| Practice squad | 1920 confirm modal | — | `after-cut-confirm-modal-1920.png` |

## Files touched

- `FrontEnd/static/box-score.html`, `box-score.css`, `box-score.js`
- `FrontEnd/static/cut-players.html`, `cut-players.css`, `cut-players.js`
- `scripts/check_ui_tokens.py`, `scripts/ci/migration_gates_allowlist.json`
- `tests/e2e/boxscore-practice-squad-tokens.spec.js`, `tests/e2e/submit-cuts.spec.js`
- `_documentation_master/04_Franchise_Mode_Systems/Practice_Squad_System.md`
- `_documentation_master/11_Design_Systems/UX_System.md`
