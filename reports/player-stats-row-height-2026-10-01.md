# Player Stats row height: 46px vs 44px (2026-10-01)

**Status: ready for review.** Branch `fix/player-stats-row-height`, pushed. Not merged. **Test-only change.**

## Finding: the token-hygiene merge did not add the 2px

The brief asked me to bisect my four token changes. I could not: none of them changes the row. The premise was wrong, so I stopped short of a product change and report it here.

| Fact | Evidence |
|---|---|
| The failing test passes here on all three commits | `player cell matches the roster row`, `--repeat-each=10`: 10/10 on `486705fe5`, 10/10 on `cbf135d0e`, 10/10 on develop `3dd0b0968` |
| The 46px is a row whose avatar holds a headshot `<img>`; 44px is a monogram row | Probe: with the headshot request held open the Player Stats row is 46px and its avatar is an `<img>`; when the request 404s the avatar becomes the monogram and the row is 44px |
| Same on the commit before my merge | Table 1 |
| The committed test fails on **all three commits** as soon as the headshot 404 arrives late | Table 2 |
| Old and new token files give identical row heights on every surface | Table 3 |

**Cause.** `a.gob-player` is an inline-flex box aligned to the text baseline. A monogram avatar has a text baseline inside it; an image-only avatar does not, so its baseline is its bottom edge and the line box grows by the font's descent: 2px. The cell is `28 + 16` with a monogram and `30 + 16` with an image.

**Why the test failed for you.** The fixture's headshots (`/static/images/players/ada.png`) 404 and fall back to the monogram. The test measured the roster row after that fallback (44px) and the Player Stats row straight after the view appeared. If the stats headshot was still in flight at that moment, it measured 46px. Here the 404 returns within one frame, so it passes; on a busier machine it does not. I cannot say why your runs split 3/3 by commit; a late 404 reproduces the exact failure on the pre-merge commit too.

### Table 1: one row, headshot state by commit

| Commit | Headshot | Roster row | Player Stats row at first paint | Player Stats row settled |
|---|---|---|---|---|
| `486705fe5` (before my merge) | request held open | 44 (monogram) | **46** | 46 (image) |
| | 404 after 400ms | 44 (monogram) | **46** | 44 (monogram) |
| | loads | 46 (image) | 46 | 46 (image) |
| `cbf135d0e` (my merge) | request held open | 44 | **46** | 46 |
| | 404 after 400ms | 44 | **46** | 44 |
| | loads | 46 | 46 | 46 |
| develop `3dd0b0968` | request held open | 44 | **46** | 46 |
| | 404 after 400ms | 44 | **46** | 44 |
| | loads | 46 | 46 | 46 |

### Table 2: the committed test, verbatim, with the headshot 404 answered late (3 runs each)

| Commit | 0ms | 50ms | 150ms | 400ms |
|---|---|---|---|---|
| `486705fe5` | 3 passed | 3 failed: expected ≤ 44, received 46 | 3 failed | 3 failed |
| `cbf135d0e` | 3 passed | 3 failed | 3 failed | 3 failed |
| develop `3dd0b0968` | 3 passed | 3 failed | 3 failed | 3 failed |

### Table 3: settled row heights, old token files vs new

"Old" = the seven front-end files at `486705fe5` (`gob-tokens.css`, `gob-buttons.css`, `rt-buckets.css`, `rtBucket.js`, `recruiting-spine.css`, `simGamePresentation.js`, `matchupsUiShared.js`) on today's develop. Measured with `getBoundingClientRect().height` on every row, 1280.

| Surface | Headshots | Old token files | New token files |
|---|---|---|---|
| Team › Roster (1-player fixture) | fail | 1 × 44 | 1 × 44 |
| | load | 1 × 46 | 1 × 46 |
| Team › Roster (15-player fixture, 12 have local headshots) | as on disk | 3 × 44 + 12 × 46 | 3 × 44 + 12 × 46 |
| | all load | 15 × 46 | 15 × 46 |
| Team › Player Stats | fail | 3 × 44 | 3 × 44 |
| | load | 3 × 46 | 3 × 46 |
| Recruiting › Pool | fail / load | 1 × 43 | 1 × 43 |
| League › Standings | fail / load | 128 × 36 | 128 × 36 |
| League › Rankings | fail / load | 25 × 36 | 25 × 36 |
| League › Leaders, list rows | fail / load | 32 × 28 | 32 × 28 |
| League › Leaders, top card | fail / load | 8 × 52.73 | 8 × 52.73 |
| League › Team Stats | fail / load | 5 × 30 + 123 × 32 | 5 × 30 + 123 × 32 |

No surface moved. The recruiting pool fixture has one row in the week it opens on.

## What I changed

`tests/e2e/player-stats.spec.js` only.

| Change | Why |
|---|---|
| `avatarsSettled(page, view)`: wait until every `.av img` in the view has loaded, or has been swapped for its monogram, before measuring | Compares like with like. No timing guess, no fixed sleep. |
| `player cell matches the roster row` uses it | The same assertion as before. |
| New: `…when headshots answer late` (404 after 400ms) | Makes the race deterministic. Asserts both rows are 44px. |
| New: `…when headshots load` (a real PNG) | Both rows carry an image and still match. |

Proof: 80/80 at `--repeat-each=10`. With the wait disabled, the late-headshot test fails (expected ≤ 44, received 46), which is the reported failure.

## Not changed: the product does have a 2px inconsistency (your call)

It is older than today and is not what broke the test, but it is real:

| Where | Today |
|---|---|
| A roster where some players have headshots and some do not | Rows of 46px and 44px in the same table (3 × 44 + 12 × 46 in the fixture) |
| A headshot that fails or arrives late | The row changes height by 2px after first paint |
| Production rosters, where headshots load | Roster and Player Stats rows are 46px, not the 44px the CSS intends (28px avatar + 16px padding) |

One line fixes it at the source: `a.gob-player { vertical-align: middle; }` in `css/gob-tables.css`. Measured as a mock (injected style, not committed):

| Surface | Headshots | Today | With the one-line fix |
|---|---|---|---|
| Team › Roster (15-player fixture) | as on disk | 3 × 44 + 12 × 46 | 15 × 44 |
| | all load | 15 × 46 | 15 × 44 |
| Team › Player Stats | load | 3 × 46 | 3 × 44 |
| Team › Roster / Player Stats | fail | 44 | 44 |
| Standings, Rankings, Leaders, Team Stats, Recruiting pool | any | unchanged | unchanged |

I did not apply it. It makes every real roster and Player Stats row 2px shorter in production (a 15-row roster gets 30px shorter). That is a visible change nobody asked for with the right facts in hand, so it is yours to rule. Say the word and it is one line plus a guard.

## Gates (final merged tree `f6e84918f`: this change + develop `297ab0efb`)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | exit 0. **4313 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (757s; the machine was busy) |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** (no pipe) |
| `scripts/ci/check_migration_gates.py` | **exit 0**. Gate A 0 / 0; Gate B 134 lines / 43 files. |
| Full Playwright under `/tmp/gob-full-playwright.lock`, `--workers=1`, `CI` unset, port 8017, **after** merging `origin/develop` | exit 0. **853 passed, 7 skipped, 0 failed** of 860 (14.9m). Lock taken 17:51:58, released 18:06:55. Run on `f6e84918f`. |
| Failure re-runs at `--repeat-each=5` | none needed |

The Playwright job fetched and merged `origin/develop` itself, after taking the lock and before starting the suite.

| Run | Tree | Result | Counts as final? |
|---|---|---|---|
| 1 | `d62ff86d1` (develop `3dd0b0968`) | 846 passed, 7 skipped, 0 failed (14.9m) | No. Develop moved during it (orange stragglers: product files). |
| 2 | `f6e84918f` (develop `297ab0efb`) | **853 passed, 7 skipped, 0 failed** (14.9m) | **Yes.** Develop had not moved when it finished or when I pushed. |

pytest, the token gate and the migration gates were also run on `f6e84918f`. The only commit after that is this report.

## On my last task

You are right that my token-hygiene Playwright run was on `74966b32b`, before I merged develop, and I said so in that report. This time the job fetched and merged develop after taking the lock and before starting the suite, so the run is on the merged tree.

## Leftovers

- `tests/e2e/zz-tb-debug.spec.js`: my scratch file, comment-only again, untracked. `rm` is denied to me.
