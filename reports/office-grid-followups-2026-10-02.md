# polish/office-grid-followups — 2026-10-02

Branch `polish/office-grid-followups` off `origin/develop` @ `f5bc9b66f` (after `polish/office-followups` and `polish/player-dev-grid` merged). Worktree `~/gob-office-grid-followups`. `origin/develop` moved to `de38092ae` (feature/all-conference) as the first gate run finished; merged as `8da67c035` with no conflict and none of this branch's files touched. The gates below are on `8da67c035` (the first run on `ebfbe43d0` had pytest 4454 passed and Playwright 1188 passed / 43 skipped / 0 failed). Ready for review.

## Items

| # | Item | Status | What changed |
|---|---|---|---|
| 1 | Player Development cards show "current → potential" | **done** | Both pages, one component, one layout. The RT slot reads e.g. `B+ → A++`. Sort stays on the current. Jersey and portrait stay off. |
| 2 | "No movement this week" with no trailing dash | **done**, one question | The line stands alone. |
| 3 | Week 1 Rankings card: last season as a quiet line at the bottom | **done** | "Last season: 18–8, lost in the Region semifinal." Season 1 shows nothing. |

## Detail

**1. Cards** (`playerDevelopmentGrid.js` `rtPairHtml`, `player-development-grid.css`)
- `<span class="pdg-rt rtl"><b data-pdg-rt>current</b><i>→</i><b class="pot">potential</b></span>`: the current is the rating at the training position (as before); the potential is the payload's `potential_rt_ratcheted`, which both hosts already carried (`training.js` adapts `custom_focus_roster` for both). No second grade and no arrow when a player has none.
- Look: the same lockup the roster and scouting tables use (`.rtl`); arrow `--text-38` at `--fs-11`, potential at `--fs-13` under the current's `--fs-16`, each grade in its own tier colour. Nothing wraps or clips at 1280 or 1920.
- A position change repaints only the current grade; the potential and the card's place stay.
- Order: still the current RT, highest first, ties by arrival. A potential never moves a card (pinned: a player given potential 120 stays where his current puts him).

**2. Quiet line** (`officeHome.js` `snapshotCard`)
- "No movement this week" with nothing after it. The `.msr-empty` style is unchanged.
- **Question:** the other state of the same line, "Set after camp —" (week 2+ before the first snapshot), kept its dash: it had one before this work and the ruling names only "No movement this week". Say if it should lose it too.

**3. Last season** (`officeHome.js` `rankingsCard`, `office-home.css` `.rk-last`)
- One `<p class="rk-last">` after the three rows, `--text-60`, `--fs-13`, from `season_preview.outlook.last_season` (`wins`, `losses`, `finish`), which the server was already sending. En dash in the record; the finish clause only when there is one ("Last season: 12–14." without it). No `last_season` (season 1) → no line, and the card ends at its rows.
- Fold after this (px past the window): season 1 unchanged at 155 (1280) / 75 (1920); later season col 01 372 → 403 (1280), 394 → 435 (1920), the line's height. Columns 02 and 03 unchanged.

## Files

| File | Item |
|---|---|
| `FrontEnd/static/js/shared/playerDevelopmentGrid.js`, `FrontEnd/static/css/player-development-grid.css` | 1 |
| `FrontEnd/static/js/shared/officeHome.js` | 2, 3 |
| `FrontEnd/static/css/office-home.css` | 3 |
| `_documentation_master/11_Design_Systems/UX_System.md` | 1, 2, 3 (grid row, Team snapshot row, week-1 Rankings row) |
| `tests/test_player_development_grid.py`, `tests/e2e/player-dev-grid.spec.js` | 1 |
| `tests/e2e/office-followups.spec.js` | 2 |
| `tests/e2e/office-week-1.spec.js` | 3 |

No server change. `franchise-command-center.css` untouched at 1779 lines. No sim / finalize / `cpu_week_pool` / `sim_rng` change. Tokens only.

## Tests

| Item | Covered by | On old code |
|---|---|---|
| 1 | `test_player_development_grid.py`: node harness renders the lockup with a potential, without one, and with `""`; the card has no jersey / `<img>` / portrait; the order harness gives one player potential 120 and he stays put. `player-dev-grid.spec.js` (+3): on both hosts every card reads `current → potential` from the page's own `formatRtDisplay`, a player with no potential shows the current alone, a potential below the current still draws, the order is the current's; a position change moves only the current grade | harness and the two "every card" tests fail; the position-change test is a guard and passes on old code (no potential there to lose) |
| 2 | `office-followups.spec.js`: the line's value is `''`, no `—` in the card; "Set after camp —" asserted unchanged | 2 fail |
| 3 | `office-week-1.spec.js`: season 1 has no `.rk-last` and no "Last season: N"; later season has exactly one, with the text, last in the card, below the rows, smaller than a row's number, `--text-60`, fits; a title finish; a record without a finish; `last_season: null` | 3 fail |

Fail-on-old-code run: the three specs against `f5bc9b66f`'s four product files: 7 failed, 22 passed; restored, 29 passed.

## Shots (`reports/office-grid-followups/`, 1280×720 and 1920×1080)

| What | Files |
|---|---|
| Prep › Player Training › Player Development, in season (12) / camp (15) | `player-development-in-season-after-…`, `player-development-camp-after-…` (+ `-grid-` close-ups) |
| Training page, in season / camp | `training-page-in-season-after-…`, `training-page-camp-after-…` (+ `-grid-`) |
| Week 1 Office, season 1 (no last-season line) | `season-1-week-1-after-…` |
| Week 1 Office, a later season (the line under Rankings) | `later-season-week-1-after-…` |
| Empty "Moved most" | `moved-most-excluded-only-after-…` (Office), `moved-most-excluded-only-card-after-…` (the card) |

The specs also rewrite their own shots under `reports/player-dev-grid/`, `reports/office-week-1/` and `reports/office-followups/`; those are not committed here.

## Gates (merged tree `8da67c035` = this branch + `origin/develop` @ `de38092ae`)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | 4474 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed (both XPASS pre-existing; `known_failures.py` not edited) |
| `check_ui_tokens.py --strict --no-write` | exit 0 |
| `check_migration_gates.py` | passed (Gate A 0, Gate B 133 lines / 43 files) |
| `franchise-command-center.css` | 1779 lines, unchanged |
| Specs touching the grid or the Office (41 files) | 448 passed, 15 skipped, 0 failed |
| Full Playwright (one run on the merged tree under the lock, 1 worker) | 1192 passed, 44 skipped, 0 failed (lock held 20:05–20:36) |

**Full suite: pytest 4474 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed · Playwright 1192 passed, 44 skipped, 0 failed.**
