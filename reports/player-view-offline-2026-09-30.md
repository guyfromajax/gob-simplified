# Player view offline — 2026-09-30

Branch `fix/player-view-offline` from `origin/develop`.

## What was broken

Coverage-map (2026-09-29) finding 1: desktop player drill-in showed **"This player could not be opened"** in 10/10 roster clicks. Online was fine. The named cause was desktop `FranchiseContext` (Session / localStorage) having no `player_id`, then `CommandCenterTabs.show` → `updateUrl` rebuilding the URL from that session.

`50f85867e` already added `SessionContextProvider.absorbLocation` and `GOBNav.absorbIntoContext`. On current develop, a roster/leaders click on real SQLite loopback often worked **if** absorb ran before `updateUrl`. The remaining hole: `playerView` still read `player_id` only from `location.search` (`detailBar.query()`), and `updateUrl` still rebuilt from session without absorbing first. Any missed absorb wiped `player_id` from the URL; `load()` then hit `!id` and showed the error card. No request was fired.

`GET /franchise/player-detail` on SQLite returned 200 with name, attributes, and stats when `player_id` was present. Not a Mongo-only query.

## Entry paths (desktop / loopback)

| Path | Before | After |
|---|---|---|
| Roster player row | Error card when session lacked `player_id` and `updateUrl` stripped it from the URL. No `/franchise/player-detail` request. | Name, attributes grid, stats table. `player_id` stays on the URL and in session. |
| Leaders player link | Same wipe. | Same as roster. Week-1 boards still have names; click opens that player. |
| Office POTG | No player link at week 1 (preseason: “Set after camp”). `officeHome.js` was not edited. | Unchanged. After a played game the existing `GOBViews.open` path now persists `player_id` like the other drills. |
| Box-score player name | `box-score.js` name cells are `<span class="player-name-link">` and open `showSpecialStatsPopup`. They do **not** navigate to player-view. | Unchanged. Not an entry path. |
| `player-detail.html?id=` | Redirect stub → FCC `?tab=player-view&player_id=`. Failed when session rebuild dropped `player_id`. | Redirect still used. Hard-nav with `player_id` in the query loads the player. |

## Root cause

1. `FrontEnd/static/js/shared/commandCenterTabs.js:111` (`updateUrl`) rebuilt `location.search` from `FranchiseContext.toSearchParams()` without absorbing the just-pushed drill URL. Desktop session had no `player_id` → URL lost it.
2. `FrontEnd/static/js/shared/views/playerView.js:128` (`playerId`, previously `query().get('player_id')` only) read the live query string. Empty id → `showError()` at line 145 (`This player could not be opened.`).
3. `FrontEnd/static/js/shared/gobViews.js:110` (`open`) updated history then called `CommandCenterTabs.show` without writing drill keys into session first.

`detailBar.query()` still reads `location.search` on purpose: `stampOrigin` (`a7fa890bf`) must see the **live** tab so a late player fetch cannot stamp another view’s history entry.

## Fix

- `gobViews.js` `persistIncoming` (desktop only): before history + `show`, `FranchiseContext.setMany` copies `tab` and every drill key from the destination href (`parseSearch`, no new Gate B reads). Web skips this — `setMany` on the URL provider would `replaceState` the current entry and break Back.
- `playerView.js` `playerId()`: `FranchiseContext.get('player_id')` first, then `query()`.
- `commandCenterTabs.js` `updateUrl`: `absorbLocation()` before `toSearchParams()`, so a same-document `player_id` cannot be dropped.

Backend unchanged. No sim / `cpu_week_pool` / `sim_rng` / finalize changes.

## Leftovers (do not delete on this branch)

| File | Why it stays |
|---|---|
| `FrontEnd/static/player-detail.html` | Redirect stub for old `/player-detail.html?id=` and recruit mode (`recruit_id`). Gate B: 1 line. |
| `FrontEnd/static/player-detail.js` | Still loaded by that HTML for recruit mode. In-app player-view does not use it. |
| `FrontEnd/static/player-detail.css` | Same. Cleanup batch (legacy-migration-plan batch 8). |

## Screenshots (1280)

| File | What |
|---|---|
| `reports/player-view-offline/offline-before-1280.png` | Desktop `?tab=player-view` with no `player_id`: error card + Retry. |
| `reports/player-view-offline/offline-after-1280.png` | Desktop roster → Player 3: hero, attributes, stats. |
| `reports/player-view-offline/online-after-1280.png` | Web profile, same roster drill. |

## Tests

- `tests/e2e/player-view-offline.spec.js`: web + desktop profiles. Roster and Leaders → player-view. Asserts name, `.gob-apan` / `.gob-apr`, Season/Career stats, no page/console errors.
- `tests/js/testFranchiseContext.mjs`: session absorb + `setMany` keep `player_id` across a rebuild.

## Gates

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | **4180 passed**, 14 skipped, 109 xfailed, **1 xpassed**, 0 failed (clean env, unsandboxed). XPASS is pre-existing (not this change). |
| Playwright `player-view-offline.spec.js` | 3 passed (web roster+leaders, desktop roster+leaders, desktop missing-id error). |
| Full Playwright | **751 passed**, 4 skipped, 0 failed (`workers=1`, `CI` unset, port 8014). |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 |
| `scripts/ci/check_migration_gates.py` | pass. Gate A: 0/0. Gate B: **136 lines in 44 files** (unchanged). |

## Files touched

- `FrontEnd/static/js/shared/gobViews.js`
- `FrontEnd/static/js/shared/views/playerView.js`
- `FrontEnd/static/js/shared/commandCenterTabs.js`
- `tests/js/testFranchiseContext.mjs`
- `tests/e2e/player-view-offline.spec.js`

Not touched: `office-home.*`, `officeHome.js`, `gob_nav` / alpha-badge, Prep views, training/game-plan/playbooks/scouting JS, `uiSfx`.
