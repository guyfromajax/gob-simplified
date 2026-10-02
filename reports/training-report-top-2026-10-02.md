# Training Report, top of the page — 2026-10-02

Branch `polish/training-report-top`, from `origin/develop` `6c6c841f9` (contains the `polish/first-paint-sweep` merge; still the tip at gate time, so there was nothing to merge).

Jamie's verdict on the old top: the information runs together and is not elegant. This is a redesign of the **Notes** section and the **Team Report** only. What data is shown and how it is computed are unchanged.

## What it is now

| Block | Contents | Layout |
|---|---|---|
| **Standouts** (card) | Practice Player of the Week, Biggest Regression, Most Positive Locker Room Influence (camp: Training Camp MVP, Biggest Concern) | Headshot (40px, unchanged), then the label with the name, position and year directly under it. "No Significant Updates" keeps the quiet `NS` box and is now dimmed. |
| **Trends** (card) | Rising, Falling (today's Strong Cumulative Increase and Concerning Regression), then Strongest Defensive Set and Strongest Offensive Plays | Rising / Falling: label with its tags immediately beside it, each attribute behind a faint green ▲ or faint red ▼ (the one-arrow tones of the marks below). Scheme lines: label above value. |
| **Readiness** (card) | Fast Break, P/T Defense | Label above a three-step neutral meter with the word beside it. |
| **Misc** (row, only when it speaks) | The week's energy notes (what "Misc" has always shown) | Label above the text, under the cards. No row when it has nothing to say. |
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
| Camp week with a Misc note | 583 / 658 | 417 / 468 | Player Report at 575 / 650 |

The target was "about half". It is just under two thirds, and the stated purpose (Player Report above the fold at both sizes) is met in all three weeks. The remaining height is the three headshots (kept at 40px on purpose). Dropping the "Notes" heading would take another 38px (to 57%); I kept it because the brief speaks of a section title. Say if you want it gone.

## Decisions, and the two I shot both ways

| # | Decision | Shipped | Alternative |
|---|---|---|---|
| 1 | **Readiness meter steps.** The server sends five words (Very Weak, Weak, Neutral, Strong, Very Strong); the brief asks for three steps. | Three steps: Weak 1, Neutral 2, Strong 3. "Very Strong" lights the same three and the word says "Very". Shot: `option-readiness-3-step-1280.png` | Five steps, one per word. Shot: `option-readiness-5-step-1280.png` |
| 2 | **Camp: the second trend line.** In camp nothing falls (no decay); that note is the attributes camp under-developed ("Concerning Progression"). | "Lagging" in camp, "Falling" in season. Shot: `option-camp-lagging-1280.png` | "Falling" in every week. Shot: `option-camp-falling-1280.png` |
| 3 | **The "Week N training brief · for coaching staff only" line.** | **Dropped.** The week is already in the page meta line, one row above. | — |
| 4 | **Readiness label.** The brief says "Press/Traps Defense Readiness"; the Styleguide says this measure is "P/T Defense" everywhere, and the Team Report cell under it says "P/T Defense". | "P/T Defense" (card title supplies "Readiness"). One string in `NOTES_READINESS_ROWS` to change. | "Press/Traps Defense" |
| 5 | **"Team Chemistry" → "Chemistry"** in the Team Report grid, as the brief lists it and as Team › Team Attributes names it. | "Chemistry" | Office still says "Team Chemistry" (not touched). |
| 6 | **Rising / Falling arrows in camp.** Camp's own one-up mark is neutral white. | Faint green ▲ / faint red ▼ in every week, as the brief says: they are tags, not magnitudes. | — |

## CH

- CH is never named. `noteAttributeLabels()` drops it from Rising / Falling whatever a stored report says (the server already excludes it from new ones).
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

The weeks are fixtures in the server's own note vocabulary (`trainingReportFixture.js`), on the 12-man fixture roster. The camp Misc sentence is sample text.

## Tests

`tests/e2e/training-report-top.spec.js`: 28 tests, plus the shot tests.

| Brief asked for | Test |
|---|---|
| Each card's contents | Standouts (people, headshot, position · year; empty state), Trends (tags, arrows, the same colours as the marks below; empty; camp), Readiness (steps lit, word beside, neutral colours) |
| Label-above-value layout | Every pair in every card and every Team Report cell, in all three weeks at 1280, 1920 and 2000: directly above (left edges equal, ≤ 8px under) or immediately beside (same line, a short step right), never more than half a card apart, never outside the card |
| Team Report grid order | The four columns read down, at all three widths; dash for no change; moved cells white and semibold, unmoved quiet |
| Empty Misc hidden | No row and no "Misc" text when the note is "No Significant Updates"; a row with label above text when it speaks |
| Player Report above the fold | Heading, column heads and first row above the fold at 1280×720 and 1920×1080, all three weeks; top section ≤ 380px at 1280 (≤ 420 with Misc) |
| No CH anywhere | A stored note with CH in both lists: CH is dropped, and the top of the page has no "CH" |
| Nothing half-built | With the report held 1.5 s: no headings, no cards, a three-column skeleton with the grid block under it; then the cards |

Fail-on-old-code: with the redesign reverted, 25 of the 28 fail. The 3 that pass are the 1920×1080 above-the-fold checks: the old layout already cleared the fold at that size (y = 841).

## Unsure / worth knowing

- **Camp physique notes are not shown, and were not before.** The server stores a camp section titled "Misc" (physique notes). The page's "Misc" row has always shown the "Player Energy Levels" note instead. I kept that as it is (no change to what is shown) but it looks like an old oversight.
- **Co-winners.** For "Practice Players Of The Week" the page shows one name (the first id match), as before. Not changed.
- Running `prep-modules-report.spec.js` rewrites PNGs in other reports' folders; those were not staged.

## Gates (final tree: `6c6c841f9` + this branch)

| Gate | Result |
|---|---|
| `git fetch` + merge `origin/develop` | Already up to date: develop is `6c6c841f9`, the base of this branch. |
| `pytest --ignore=tests/e2e -q` | **4372 passed, 14 skipped, 108 xfailed, 2 xpassed** (exit 0). No `FAILED` / `ERROR`. |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** |
| `scripts/ci/check_migration_gates.py` | **passed** (Gate A 0; Gate B 134 lines in 43 files, unchanged) |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | **1050 passed, 32 skipped, 0 failed** (4.7 min). Nothing to re-run. |
| `franchise-command-center.css` | 1779 lines, not touched. No sim / finalize / cpu_week_pool / sim_rng changes (no Python changed). |

The 2 XPASS are the two already on the known-failures list (`test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference`, `test_settings_application_to_gameplay.py::…::test_settings_loaded_and_applied_to_gameplay`); this branch changes no Python and the list was not edited.
