# Training Report tables and play score arrows — 2026-10-02

Branch `polish/training-report-tables`, from `origin/develop` `ff7f60885` (contains the `polish/training-report-top` merge; still the tip at gate time, so there was nothing to merge).

Two items, each its own commit. Item 2 is **measured and proposed, not switched on**: it needs Jamie's approval, so it comes first.

---

## Item 2. Play score arrows: measurements and proposal (FOR JAMIE TO APPROVE)

### The finding in four lines

- Today the Playbook Summary marks a play's CMD movement on the player-attribute scale (three arrows from +3). Measured on the real engine, **97% of trained offense plays and 100% of trained defenses show three arrows.**
- **CMD never falls in a training session.** In 4,608 play-rows across 144 sessions, and 7 real weeks, a trained play gained and an untrained play stayed at 0. CMD only falls at end of game.
- A trained play's gain depends on what it is: set plays 2-7, motions 13-35, zones 13-66, Man 41-178 (middle of the range). Camp and in-season sessions are the same size.
- A percentage-of-score rule does not fit: gains are fixed points, many plays train from a score of 0, and the percentage runs from 12% to 800%.

### Proposal

| | One arrow | Two arrows | Three arrows | Share of real results (1 / 2 / 3) |
|---|---|---|---|---|
| **Offense plays, up** | under 5 | 5 to 19 | 20 or more | 30% / 38% / 32% |
| **Defenses, up** | under 30 | 30 to 49 | 50 or more | 39% / 27% / 34% |
| Offense plays, down | under 5 | 5 to 9 | 10 or more | 29% / 37% / 34% (end-of-game drops) |
| Defenses, down | under 10 | 10 to 19 | 20 or more | 39% / 36% / 25% (end-of-game drops) |

- Two scales, because a defense gains several times what a play does (nine defenses share the points, against twenty-three plays).
- Down cut-offs are proposed for completeness. The Training Report never carries a drop today (drops happen after the game, not in training), so they would only show if the report is ever given the week's net change.
- Tones are unchanged: the existing training movement marks (faint one-arrow, green two, blue three; red down).
- **The alternative**, one scale for everything (two from 10, three from 30), is simpler to say but splits badly: offense 58% / 22% / 20%, defense 0% / 39% / 61%.

**To switch it on once approved:** one line in `FrontEnd/static/training-report.js`: `const PLAY_CMD_SCALE = 'attribute';` becomes `'play'`. The cut-offs are `PLAY_CMD_CUTOFFS` beside it. Nothing changes until then (a test pins today's behaviour, and another flips the constant and checks the proposed marks).

### How it was measured

Real training on the offline engine (the loopback server on SQLite, the real 128-team league). No engine code was changed. Tool: `scripts/measure_play_cmd_training.py`; raw rows in `reports/training-report-tables/play-cmd-data/`.

| Pass | What ran | Rows |
|---|---|---|
| Matrix, camp | 72 training sessions at week 1 on 72 different programs: 8 coaching focuses, 12 offense / defense install spreads (0 to 5 points each), the rest of the 30 points spread at random; 1 in 5 with a Custom Playbook (2, 4 or 8 plays) | 2,304 |
| Matrix, in season | The same 72 at week 10 (24 points) | 2,304 |
| Real weeks | One franchise (Lancaster) played for 7 weeks: training, the user's game simmed in full, the week completed. CMD read before training, after training and after the game | 448 |

### A. One training session (matrix: 72 camp sessions, 72 in-season sessions)

| Week | Group | Trained (gained) | Not trained (0) | Dropped | n | min | Q1 | median | Q3 | max |
|---|---|---|---|---|---|---|---|---|---|---|
| Camp (week 1) | Offense, all plays | 431 | 1225 | 0 | 431 | 2 | 4 | 6 | 27 | 157 |
| Camp (week 1) | · motion | 140 | 148 | 0 | 140 | 13 | 21 | 29 | 35 | 93 |
| Camp (week 1) | · set plays | 291 | 1077 | 0 | 291 | 2 | 4 | 5 | 6.5 | 157 |
| Camp (week 1) | Defense, all | 183 | 465 | 0 | 183 | 14 | 25 | 36 | 63 | 271 |
| Camp (week 1) | · Man (man, tight, loose) | 51 | 165 | 0 | 51 | 47 | 74.5 | 92 | 118.5 | 271 |
| Camp (week 1) | · zones | 132 | 84 | 0 | 132 | 14 | 20 | 30 | 40 | 66 |
| In season (week 10) | Offense, all plays | 449 | 1207 | 0 | 449 | 2 | 4 | 6 | 27 | 194 |
| In season (week 10) | · motion | 138 | 150 | 0 | 138 | 13 | 23 | 29 | 33 | 194 |
| In season (week 10) | · set plays | 311 | 1057 | 0 | 311 | 2 | 4 | 5 | 6.5 | 107 |
| In season (week 10) | Defense, all | 187 | 461 | 0 | 187 | 13 | 22.5 | 32 | 59.5 | 387 |
| In season (week 10) | · Man (man, tight, loose) | 55 | 161 | 0 | 55 | 41 | 73.5 | 87 | 111.5 | 387 |
| In season (week 10) | · zones | 132 | 84 | 0 | 132 | 13 | 20 | 26.5 | 39.25 | 58 |

By playbook mode (offense, both weeks pooled):

| Mode | n | min | Q1 | median | Q3 | max |
|---|---|---|---|---|---|---|
| current-playbooks | 774 | 2 | 4 | 5 | 21.75 | 62 |
| custom | 106 | 12 | 15 | 30 | 54 | 194 |

### B. Real weeks, one franchise played through (weeks 1, 2, 3, 4, 5, 6, 7)

| Week | Step | Group | Moved | Did not move | n | min | Q1 | median | Q3 | max |
|---|---|---|---|---|---|---|---|---|---|---|
| Camp (week 1) | Training (gain) | offense | 9 | 14 | 9 | 7 | 7 | 7 | 46 | 48 |
| Camp (week 1) | Training (gain) | defense | 4 | 5 | 4 | 39 | 39 | 40 | 60.75 | 120 |
| Camp (week 1) | End of game (drop) | offense | 6 | 17 | 6 | 4 | 6 | 6.5 | 7.75 | 10 |
| Camp (week 1) | End of game (drop) | defense | 4 | 5 | 4 | 7 | 10.75 | 14.5 | 21.5 | 35 |
| In season (weeks 2+) | Training (gain) | offense | 45 | 93 | 45 | 2 | 4 | 8 | 12 | 24 |
| In season (weeks 2+) | Training (gain) | defense | 20 | 34 | 20 | 18 | 20.75 | 39 | 56 | 202 |
| In season (weeks 2+) | End of game (drop) | offense | 35 | 103 | 35 | 2 | 4 | 7 | 10 | 17 |
| In season (weeks 2+) | End of game (drop) | defense | 24 | 30 | 24 | 5 | 8 | 11.5 | 22.25 | 47 |

Rows that moved the other way (a drop in training, a gain at end of game): **0**.

### C. Cut-offs against the measured gains (one / two / three arrows)

| Rule | Offense plays (n=880) | Defenses (n=370) |
|---|---|---|
| Today: player-attribute scale (two from 1, three from 3) | 0% / 3% / 97% | 0% / 0% / 100% |
| **Proposed**: offense two from 5, three from 20; defense two from 30, three from 50 | **30% / 38% / 32%** | **39% / 27% / 34%** |
| Alternative: one scale for both, two from 10, three from 30 | 58% / 22% / 20% | 0% / 39% / 61% |
| Near misses: offense 6 / 20, defense 25 / 50 | 45% / 23% / 32% | 25% / 41% / 34% |

- Proposed, camp only: offense 31% / 38% / 31%, defense 36% / 28% / 36%.
- Proposed, in season only: offense 29% / 38% / 33%, defense 41% / 26% / 33%.

### D. Would a percentage-of-score rule fit better?

Gain as a share of the score before training, real weeks, plays that already had a score (n=51):

| Group | n | min % | Q1 % | median % | Q3 % | max % |
|---|---|---|---|---|---|---|
| Offense | 31 | 12 | 28 | 42 | 72 | 800 |
| · motion | 15 | 12 | 18 | 27 | 40 | 71 |
| · set plays | 16 | 29 | 41 | 65 | 179 | 800 |
| Defense | 20 | 17 | 19 | 23 | 112 | 532 |

Trained from a score of 0 (no percentage exists): 27 of 78 gains in the real weeks; every gain in camp.

### E. Drops (end of game), against the same cut-offs

| Rule | Offense drops (n=41) | Defense drops (n=28) |
|---|---|---|
| Proposed up cut-offs reused for down (5 / 20, 30 / 50) | 29% / 71% / 0% | 75% / 25% / 0% |
| **Proposed for drops**: offense two from 5, three from 10; defense two from 10, three from 20 | **29% / 37% / 34%** | **39% / 36% / 25%** |

### What I am unsure of

- The matrix franchises are fresh, so every play starts the session at CMD 0 (in season too: the week-10 franchises are started at week 10, not played to it). Gains are added points, so the gain sizes are right; only the percentage question needs evolved scores, and that comes from the 7 real weeks.
- Drops are from one franchise's 7 games (41 offense, 28 defense). Enough to see the shape, thin for cut-offs. They matter only if a report ever shows drops.
- Fast Breaks, Half-Court Traps and the press are not in the Playbook Summary, and install points for them do not move play CMD: not measured.
- The coaching focus changes the size (Systems Coach multiplies the points by 1.5 to 1.8; Authoritarian Execution / Teamwork do the same for set plays / motions): all are in the matrix, pooled.

---

## Item 1. Player Report and Projected Starting 5 tables (shipped)

| Was | Is |
|---|---|
| A boxed grid: twelve evenly spaced attribute columns, a white box round every moved cell | The roster's table: `.gob-roster.gob-pairs`, `.gob-tbl`. No table style of its own. |
| No grouping | Six pairs in the roster's order, SC SH · ID OD · PS BH · RB ST · AG ND · IQ FT: tight inside a pair, a gutter between pairs, the roster's shade on every other pair |
| Cell borders | Row zebra, no borders. A moved cell is marked by its arrows alone |
| Projected Starting 5 listed RB AG ST ND | Same six pairs, the roster's order. Stats view unchanged |
| Values spread across the page | Values sit right beside the names; rows and zebra still span the page |

- **Training Changes** still shows only what was trained, laid out by the same pairs: a pair present in full stays together; an attribute whose partner was not trained stands alone with a gutter both sides.
- **Attributes** keeps NG and EM (they were there before): they stand alone after the six pairs, then RT.
- **Name, position chip and RT stay.**
- **Row height: 44px**, the roster's row (it was about 37px in Training Changes and 51px in Attributes). It did not break the page.
- **Above the fold:** the Player Report still starts at y = 530 at 1280×720 and y = 598 at 1920×1080 (the top of the page is untouched).
- **CH** is never a column in any of the three tables, whatever the data carries.
- The three cards, the Team Report grid and the Player Energy row are untouched.

### Choices I made

| Choice | Why | Alternative |
|---|---|---|
| Values beside the names: the name column is as wide as its longest name, an empty last cell takes the spare width | The Styleguide lets the name column take the slack; on Training Changes with five columns that put the marks about 750px from the names at 1280 and further at 1920, the very thing Jamie flagged on the top of this page | Follow the roster literally (name column takes the slack). One CSS rule to change |
| Group shade alternates in the order shown | On Training Changes a missing pair would otherwise put two shaded (or two unshaded) groups side by side. On Attributes it is exactly the roster's shade | Shade by pair identity |
| The page links `gob-views.css` and `gob-tables.css` | That is where the shared pair and table classes live; the report page did not load them | — |
| The changed-cell box is gone by not adding `is-delta` to player cells | The class carried the box | — |

### Shots

`reports/training-report-tables/`, each section shot whole.

| | Before | After |
|---|---|---|
| In season, Attributes | `before-season-attributes-1280/1920/2000.png` | `after-season-attributes-…` |
| In season, Training Changes (SC SH · PS · AG ND trained) | `before-season-changes-…` | `after-season-changes-…` |
| In season, Projected Starting 5 | `before-season-projected-…` | `after-season-projected-…` |
| Camp, Attributes | `before-camp-attributes-…` | `after-camp-attributes-…` |
| Camp, Training Changes (all twelve) | `before-camp-changes-…` | `after-camp-changes-…` |
| Camp, Projected Starting 5 | `before-camp-projected-…` | `after-camp-projected-…` |
| Whole page at 1280×720 | `before-season-page-1280.png`, `before-camp-page-1280.png` | `after-…-page-1280.png` |

## Files touched

- Item 1: `FrontEnd/static/training-report.js` (`ATTRIBUTE_PAIRS`, `layoutAttributeColumns()`, `renderPlayersTable()`, `renderProjectedStartingFiveAttributes()`), `training-report.css` (`.tr-ptable`), `training-report.html` (two stylesheet links, table classes); `Styleguide.md`, `UX_System.md`; `tests/e2e/training-report-tables.spec.js` (new), `helpers/trainingReportFixture.js`, one assertion in `polish-training-playbooks.spec.js`.
- Item 2: `training-report.js` (`PLAY_CMD_SCALE`, `PLAY_CMD_CUTOFFS`, `describePlayCmdChange()`, `describeTrainingMark()` factored out, no behaviour change); two tests; `scripts/measure_play_cmd_training.py` (new); `UX_System.md`; the raw data.
- Not touched: any sim / finalize / cpu_week_pool / sim_rng code; Office, News, playbook report, cut players, box score; `franchise-command-center.css` (1779 lines).

## Tests

`tests/e2e/training-report-tables.spec.js`: 13 tests plus the shot tests.

| Brief asked for | Test |
|---|---|
| Pair order and gutters | Attributes at 1280, 1920 and 2000: the six pairs in order on `gstart` / `gend`, shade on ID OD, RB ST, IQ FT; gap inside a pair ≤ 6px and identical; gutter ≥ 16px, identical, and more than three times the inside gap; label centred over its value |
| No boxed cells | Every cell: no borders, no box-shadow, no outline; moved and unmoved cells identical but for the arrows; no `is-delta`; zebra present |
| Pairs stay together on Training Changes | SC SH PS AG ND → pair, solo, pair; camp → six pairs; SH ID ST → three solos |
| Player Report above the fold | Heading, column heads and first row, both weeks, 1280×720 and 1920×1080 |
| No CH column | CH in attributes, changes and the projected rows: no CH header and no "CH" text in either section |
| Also | Rows 44px; name, chip, RT present; Projected Starting 5 pairs match the Player Report's rhythm; its Stats view unchanged; the play-scale switch (today's marks pinned; the constant flipped gives the proposed marks) |

Fail-on-old-code (item 1): with the tables reverted, 6 fail and 5 pass. The 5 are the four above-the-fold checks and the CH check, which the old tables already met; they are guards.

## Gates (final tree: `ff7f60885` + this branch)

| Gate | Result |
|---|---|
| `git fetch` + merge `origin/develop` | Already up to date: develop is `ff7f60885`, the base of this branch. |
| `pytest --ignore=tests/e2e -q` | **4411 passed, 14 skipped, 108 xfailed, 2 xpassed** (exit 0). No `FAILED` / `ERROR`. |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** |
| `scripts/ci/check_migration_gates.py` | **passed** (Gate A 0; Gate B 133 lines in 43 files) |
| Training Report specs (tables, top, polish-training-playbooks, prep-modules-report, training-advance-focus, no-recruiting, first-paint) | **117 passed, 30 skipped, 0 failed** |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | **1123 passed, 39 skipped, 1 failed** (5.1 min) |
| The 1 failure re-run alone, `--repeat-each=5` | **5 passed, 0 failed** |

- The failure: `office-frontend.spec.js` "six states fit at 1280 and 1920" ("signing_day column 2 clipped": 3px against a 1px allowance). It is an Office test; this branch touches no Office file, and it passes 5 of 5 alone. A flake under full-suite load, not from this branch. The Office is the audit agent's just now.
- The 2 XPASS are the two already on the known-failures list (`test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference`, `test_settings_application_to_gameplay.py::…::test_settings_loaded_and_applied_to_gameplay`); the list was not edited. pytest ran before the play-scale down cut-offs were set in the JS; nothing Python changed after it.
- Migration gates print a NOTE that is not from this branch: Gate B's count for `js/shared/views/newsView.js` fell from 3 to 2 on develop, and the allow-list can be tightened. I did not run `--write-allowlist`.
