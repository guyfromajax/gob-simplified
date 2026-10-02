# polish/office-followups — 2026-10-02

Branch `polish/office-followups` from `origin/develop` @ `6ddd8820f` (the `feature/office-week-1` merge). `origin/develop` moved to `1d8be6c67` (polish/training-report-tables) while I worked; merged as `fe7c1f360` with no conflict. The gates below are on that merged tree. Ready for review.

## Items

| # | Item | Status | What changed |
|---|---|---|---|
| 1 | "Moved most" ranks only the eight signed-scale attributes | **done**, one wording question | Server filter where the list is built, client guard, and a quiet empty line when none of the eight moved. |
| 2 | Week 1: no Team snapshot card in the middle column | **done** | Week 1's middle column is Season Opener, Circle these, Preseason National Rankings. From week 2 the card is back as before. |
| 3 | Week-1 records and scores use the en dash | **done** | "Last season: 18–8, …" and "Last season: W 71–64". |

## Item 1: detail

**The eight** (`office_digest.MOVED_MOST_KEYS`, derived from the team-measure table's signed-scale rows, so it cannot drift from Team Attributes):

| Key | Label |
|---|---|
| `offensive_efficiency` | Offense |
| `defensive_efficiency` | Defense |
| `discipline` | Discipline |
| `fb_efficiency` | Fast Break |
| `fb_opp_modifier` | Fast Break Defense |
| `fight` | Fight |
| `pt_opp_modifier` | P/T Offense |
| `pt_efficiency` | P/T Defense |

- **Excluded:** Team Chemistry, Shooting (`shot_threshold`), Rebounding (`rebound_modifier`). Momentum was already never shown; it is now dropped on the server too, not only in the client.
- **Checked against the stored measures:** the weekly snapshot stores eleven keys (`TEAM_MEASURE_KEYS`): the eight, plus Shooting, Rebounding and Momentum. Chemistry is not in the snapshot at all, so it could not appear before either; the filter and the client guard exclude it anyway.
- **Server** (`office_digest.moved_most`): only the eight are ranked, then the top two taken. Before, a week where Shooting moved most sent Shooting first.
- **Client** (`officeHome.js` `snapshotCard`): keeps only rows whose measure is one of the eight, whatever the payload carries.
- **Empty line.** When none of the eight moved, the card shows the "Moved most" heading over one quiet line: **"No movement this week —"**. It never falls back to an excluded measure. Before this, a ready snapshot with nothing to list showed no heading and no line. The line is dimmer than a real row and does not underline on hover.
- **Chemistry** keeps its own bar at the top of the card; untouched.

**Question:** the wording of that line. The card's only existing quiet line was "Set after camp" (before the first snapshot), which would be wrong after camp, so I wrote "No movement this week". Say if you want other words.

## Items 2 and 3: detail

- Week 1 (`officeHome.js` render): the Team snapshot card is no longer in the middle column. If the week-1 preview's own reads fail, the column is the opener and the standings card, still without the snapshot.
- Past the fold in week 1 now (px each column runs past the window):

| View | 1280×720: col 01 / 02 / 03 | 1920×1080: col 01 / 02 / 03 |
|---|---|---|
| Season 1, week 1 | 185 / 5 / 0 | 124 / 0 / 0 |
| Later season, week 1 | 428 / 5 / 0 | 470 / 0 / 0 |

  Column 02 was 219px (1280) and 146px (1920) past the fold with the snapshot card in it.
- En dash: the outlook's last-season record and the opener's last-season score. The standings card's W-L column and the Rankings card ("5 of 8") have no dash to change.

## Files

| File | Item |
|---|---|
| `BackEnd/utils/office_digest.py` | 1 |
| `FrontEnd/static/js/shared/officeHome.js` | 1, 2, 3 |
| `FrontEnd/static/css/office-home.css` | 1 (the quiet line) |
| `_documentation_master/11_Design_Systems/UX_System.md` | 1, 2, 3 |
| `tests/test_office_digest.py`, `tests/e2e/office-followups.spec.js` (new) | 1 |
| `tests/e2e/office-week-1.spec.js`, `tests/e2e/office-frontend.spec.js`, `tests/e2e/desktop-gallery-fixes.spec.js` | 2, 3 |
| `tests/e2e/office-weekly-sfx.spec.js`, `tests/e2e/jamie-rulings-batch-2.spec.js` | 1 (fixtures that listed an excluded measure) |

`franchise-command-center.css` unchanged at 1779 lines. No sim / finalize / `cpu_week_pool` / `sim_rng` change.

## Tests

| Item | Covered by | On old code |
|---|---|---|
| 1, server | `test_office_digest.py` (+3): the set is exactly the eight; a week where Shooting moved most (with Rebounding, Chemistry and Momentum also moving more) lists Discipline and Fight only; a week where only the excluded moved is empty; through the digest, the list is empty and the Chemistry bar is still there | the first two fail |
| 1, client | `office-followups.spec.js` (6), fed payloads that still carry the excluded measures: Shooting first → only Discipline and Fast Break Defense are drawn, no "Shooting", "Rebounding" or "Momentum", Chemistry bar 18/25; only the excluded three → "No movement this week —", quiet, no hover underline; nothing moved → the same line; each of the eight can be listed; before camp from week 2 the line still says "Set after camp" | 3 of 6 fail (the shot tests and "Set after camp" pass) |
| 2, 3 | `office-week-1.spec.js`: the middle column's cards in order; no `.office-snap` and no "Set after camp" in week 1; the card present in week 2; the en-dash strings | fail |

Existing tests updated because they encoded the old behaviour:

| Test | Was | Now |
|---|---|---|
| `office-weekly-sfx.spec.js` "Moved most never surfaces Momentum" | expected "Shooting" to be listed | expects it not to be |
| `jamie-rulings-batch-2.spec.js` fixture | listed Chemistry as the "up" row | lists Fight |
| `office-frontend.spec.js` week-1 state | one "Set after camp" line | none, and no snapshot card |
| `desktop-gallery-fixes.spec.js` #10 (desktop config, not in the full run) | one "Set after camp" line on a real week-1 Office | none. **Not run here:** the desktop harness's save already holds two franchises, so its set-up is refused ("You already have 2 active franchises"). |

## Shots (`reports/office-followups/`, 1280 and 1920)

| What | Files |
|---|---|
| Shooting moved most (payload still lists it) | `moved-most-shooting-first-after-…` (Office), `moved-most-shooting-first-card-after-…` (the card) |
| Only the excluded three moved | `moved-most-excluded-only-after-…`, `moved-most-excluded-only-card-after-…` |
| Week 1, season 1 | `season-1-week-1-after-…` (window), `season-1-week-1-full-after-…` (whole Office) |
| Week 1, a later season | `later-season-week-1-after-…`, `later-season-week-1-full-after-…` |

The week-1 spec also rewrites its own shots under `reports/office-week-1/`; those are not committed here.

## Gates (merged tree `fe7c1f360` = this branch + `origin/develop` @ `1d8be6c67`)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | 4442 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed. Both XPASS are pre-existing; `known_failures.py` not edited. |
| `check_ui_tokens.py --strict --no-write` | exit 0 |
| `check_migration_gates.py` | passed (Gate A 0, Gate B 133 lines / 43 files) |
| `franchise-command-center.css` | 1779 lines, unchanged |
| Office specs (every spec that loads the Office) | 260 passed, 2 skipped, 0 failed |
| Full Playwright (lock held 17:30-17:51, 1 worker) | 1150 passed, 39 skipped, 0 failed |

**Full suite: pytest 4442 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed · Playwright 1150 passed, 39 skipped, 0 failed.**
