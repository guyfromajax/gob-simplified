# Training Report, top of the page — 2026-10-02

Branch `polish/training-report-top`, from `origin/develop` `6c6c841f9` (contains the `polish/first-paint-sweep` merge), with `origin/develop` `6d569a465` merged in before the final gates.

Jamie's verdict on the old top: the information runs together and is not elegant. This is a redesign of the **Notes** section and the **Team Report** only. What data is shown and how it is computed are unchanged.

## What it is now

| Block | Contents | Layout |
|---|---|---|
| **Standouts** (card) | Practice Player of the Week, Biggest Regression, Most Positive Locker Room Influence (camp: Training Camp MVP, Biggest Concern) | Headshot (40px, unchanged), then the label with the name, position and year directly under it. "No Significant Updates" keeps the quiet `NS` box and is now dimmed. |
| **Trends** (card) | Rising, Falling (today's Strong Cumulative Increase and Concerning Regression), then Strongest Defensive Set and Strongest Offensive Plays | Rising / Falling: label with its tags immediately beside it, each attribute behind a faint green ▲ or faint red ▼ (the one-arrow tones of the marks below). Scheme lines: label above value. |
| **Readiness** (card) | Fast Break, P/T Defense | Label above a five-step neutral meter (one step per level) with the word beside it. |
| **Player Energy** (row, only when there is something to report) | The week's energy notes. This row was labelled "Misc"; it has only ever shown these notes, so it is named for them. | Label above the text, under the cards. No row when there is nothing to report. |
| **Team Report** (card) | The eleven team attributes | Four columns, read down, in the order of Team › Team Attributes. A cell is the name and, right beside it, its mark. No movement is a quiet dash and a quieter name. |

- Cards are the shared `.card` (gob-components). No new card style, no new colours, tokens only.
- One layer of small grey caps (the labels). Values are white; empty values are `--text-38`.
- The page meta line and "Continue to Office" are untouched. Player Report, Projected Starting 5 and Playbook Summary are untouched.

## Height

| | Before | After | |
|---|---|---|---|
| Top section (Notes + Team Report) at 1280 | 583px | **372px** | 64% of before |
| Top section at 1920 / 2000 | 658px | **415px** | 63% |
| Player Report starts at, 1280×720 | y = 741 (below the fold) | **y = 530** | heading, column heads and first row all above the fold |
| Player Report starts at, 1920×1080 | y = 841 | **y = 598** | |
| Camp week with a Player Energy note | 583 / 658 | 417 / 468 | Player Report at 575 / 650 |

The target was "about half". It is just under two thirds, and the stated purpose (Player Report above the fold at both sizes) is met in all three weeks. The remaining height is the three headshots (kept at 40px on purpose). Jamie ruled that the "Notes" heading stays.

## Decisions (Jamie's rulings, 2026-10-02)

| # | Decision | Ruling | Shipped |
|---|---|---|---|
| 1 | **Readiness meter steps.** The server sends five words. | **Five steps, one per level**, with the word beside it. | Very Weak 1, Weak 2, Neutral 3, Strong 4, Very Strong 5. Shots: `option-readiness-5-step-1280.png` (shipped), `option-readiness-3-step-1280.png` (the first build, for the record). |
| 2 | **Camp: the second trend line.** Nothing falls in camp. | **"Lagging" in camp, "Falling" in season.** | As built. Shots: `option-camp-lagging-1280.png` (shipped), `option-camp-falling-1280.png`. |
| 3 | **The "Notes" heading.** | **Keep it.** | Kept. |
| 4 | **The row under the cards.** | **"Player Energy"**, not "Misc": it only ever shows the player energy notes. Label above the text; hidden when there is nothing to report. | Renamed. |
| 5 | The "Week N training brief · for coaching staff only" line. | Not ruled on. | Dropped: the week is in the page meta line, one row above. |
| 6 | Readiness label: brief says "Press/Traps Defense Readiness", Styleguide says the measure is "P/T Defense" everywhere. | Not ruled on. | "P/T Defense" (the card title supplies "Readiness"). One string in `NOTES_READINESS_ROWS`. |
| 7 | "Team Chemistry" → "Chemistry" in the Team Report grid. | Not ruled on. | "Chemistry", as the brief lists it and as Team › Team Attributes names it. Office still says "Team Chemistry". |
| 8 | Rising / Falling arrows in camp (camp's own one-up mark is neutral white). | Not ruled on. | Faint green ▲ / faint red ▼ in every week: they are tags, not magnitudes. |

## CH

- CH is never named. `noteAttributeLabels()` drops it from Rising / Falling whatever a stored report says (the server already excludes it from new notes, and develop `6d569a465` now keeps CH out of every payload).
- If CH was the only attribute on a line, the line reads "No Significant Updates".
- The Team Report's "Chemistry" is the team attribute, not CH, and stays (the brief lists it).

## Audit of recent work on these files

Built on what is on develop; nothing reverted.

| Recent change | Status |
|---|---|
| Plain Attributes values (Player Report) | Untouched: Player Report code not edited. |
| Faint single arrows (`describeTrainingChange`, `.tr-tone-*`) | Reused as is: Team Report marks and the Trends tags read the same classes. |
| Load-error card (`is-load-failed`) | Untouched and still covered by its test. |
| R1 skeleton (`is-loading`) | Kept. The skeleton is reshaped to the new top (three card blocks and a grid block), so nothing jumps when data lands. |

## Files touched

- `FrontEnd/static/training-report.js`: `buildStandoutsCard()`, `buildTrendsCard()`, `buildReadinessCard()`, `createReadinessMeter()`, `noteAttributeLabels()`, `TEAM_REPORT_GRID_ROWS`, `createTeamAttrItem()` (dash instead of "No change"), shell markup and skeleton.
- `FrontEnd/static/training-report.css`: `.tr-cards`, `.tr-card`, `.tr-pair`, `.tr-label`, `.tr-value`, `.tr-tags`, `.tr-meter`, `.tr-misc`, the Team Report grid; the page is one column now (Notes above Team Report, not beside it).
- `FrontEnd/static/training-report.html`: same markup as the module's shell.
- Docs: `UX_System.md` (two rows: Notes, Team Report), `Styleguide.md` (Trends tags and Readiness meters under Training movement marks).
- Tests: `tests/e2e/training-report-top.spec.js` (new), `tests/e2e/helpers/trainingReportFixture.js` (new).
- Three existing tests updated for the intended changes: `prep-modules-report` (looked for the text "P/T Defense Readiness"), `training-advance-focus` (Team Report row was a grid, is now a block in a grid), `training-report-no-recruiting` (looked for `#training-notes-brief`).

## Shots

`reports/training-report-top/`, full page.

| Week | Before | After |
|---|---|---|
| In season, plenty moved (`busy`, week 12) | `before-busy-1280.png`, `-1920`, `-2000` | `after-busy-1280.png`, `-1920`, `-2000` |
| In season, almost nothing moved (`quiet`, week 14) | `before-quiet-1280.png`, `-1920`, `-2000` | `after-quiet-1280.png`, `-1920`, `-2000` |
| Training camp (`camp`, week 1) | `before-camp-1280.png`, `-1920`, `-2000` | `after-camp-1280.png`, `-1920`, `-2000` |
| Options (the three cards, 1280) | | `option-readiness-3-step`, `option-readiness-5-step`, `option-camp-lagging`, `option-camp-falling` |

The weeks are fixtures in the server's own note vocabulary (`trainingReportFixture.js`), on the 12-man fixture roster. The camp Player Energy sentence is sample text. The after shots were retaken with the five-step meter and the "Player Energy" label.

## Tests

`tests/e2e/training-report-top.spec.js`: 29 tests, plus the shot tests.

| Brief asked for | Test |
|---|---|
| Each card's contents | Standouts (people, headshot, position · year; empty state), Trends (tags, arrows, the same colours as the marks below; empty; camp), Readiness (five steps, each level lights its own count, word beside, neutral colours) |
| Label-above-value layout | Every pair in every card and every Team Report cell, in all three weeks at 1280, 1920 and 2000: directly above (left edges equal, ≤ 8px under) or immediately beside (same line, a short step right), never more than half a card apart, never outside the card |
| Team Report grid order | The four columns read down, at all three widths; dash for no change; moved cells white and semibold, unmoved quiet |
| Empty Player Energy hidden | No row and no "Player Energy" text when the note is "No Significant Updates"; a row with label above text when there is something to report; the word "Misc" is nowhere on the page |
| Player Report above the fold | Heading, column heads and first row above the fold at 1280×720 and 1920×1080, all three weeks; top section ≤ 380px at 1280 (≤ 420 with a Player Energy row) |
| No CH anywhere | A stored note with CH in both lists: CH is dropped, and the top of the page has no "CH" |
| Nothing half-built | With the report held 1.5 s: no headings, no cards, a three-column skeleton with the grid block under it; then the cards |

Fail-on-old-code: with the redesign reverted, 25 of the original 28 fail. The 3 that pass are the 1920×1080 above-the-fold checks: the old layout already cleared the fold at that size (y = 841). The three tests changed for the rulings (the two Readiness tests and Player Energy) fail on the three-step / "Misc" build.

## Unsure / worth knowing

- **For the record (Jamie):** `training_camp_physique_notes` is always an empty list today; the code that generated those notes was removed. So there is nothing else to show in the row under the cards, and the server field was left alone.
- **Co-winners.** For "Practice Players Of The Week" the page shows one name (the first id match), as before. Not changed.
- Running `prep-modules-report.spec.js` rewrites PNGs in other reports' folders; those were not staged.

## Gates (final merged tree: `origin/develop` `6d569a465` merged in)

Develop moved while the first gate run was in progress (chrome-followups-2: CH hidden at the server). It merged cleanly (`f76d75f4a`) and every gate was run again on the merged tree. The numbers below are that second run.

| Gate | Result |
|---|---|
| `git fetch` + merge `origin/develop` | Merged `6d569a465`, no conflicts. |
| `pytest --ignore=tests/e2e -q` | **4385 passed, 14 skipped, 108 xfailed, 2 xpassed** (exit 0). No `FAILED` / `ERROR`. |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** |
| `scripts/ci/check_migration_gates.py` | **passed** (Gate A 0; Gate B 134 lines in 43 files, unchanged) |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | **1085 passed, 32 skipped, 0 failed** (5.5 min). Nothing to re-run. |
| `franchise-command-center.css` | 1779 lines, not touched. No sim / finalize / cpu_week_pool / sim_rng changes (this branch changes no Python). |

- The 2 XPASS are the two already on the known-failures list (`test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference`, `test_settings_application_to_gameplay.py::…::test_settings_loaded_and_applied_to_gameplay`); the list was not edited.
- First run, on `6c6c841f9` before develop moved: pytest 4372 passed / 2 xpassed, Playwright 1050 passed / 0 failed.

## Update: Jamie's rulings applied

- Five-step Readiness meter, "Player Energy" row, "Lagging" in camp and the "Notes" heading kept (decisions table above). Styleguide and UX_System updated; after shots and option shots retaken.
- `origin/develop` has not moved since the last full run (`6d569a465`), so the full Playwright suite was not re-run, as instructed.

| Gate | Result |
|---|---|
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** |
| `scripts/ci/check_migration_gates.py` | **passed** (Gate A 0; Gate B 134 lines in 43 files) |
| Specs: training-report-top, polish-training-playbooks, prep-modules-report, training-advance-focus, training-report-no-recruiting, first-paint | **104 passed, 24 skipped, 0 failed** |
| Last full runs (merged tree, before these rulings) | pytest 4385 passed / 2 xpassed; Playwright 1085 passed / 0 failed |

