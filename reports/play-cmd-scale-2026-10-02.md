# Play CMD scale switched on — 2026-10-02

Branch `polish/play-cmd-scale`, from `origin/develop` `1d8be6c67` (contains the `polish/training-report-tables` merge; still the tip at gate time, so there was nothing to merge).

Jamie approved the cut-offs as proposed. The switch is on.

## What changed

| | Before | Now |
|---|---|---|
| `PLAY_CMD_SCALE` in `FrontEnd/static/training-report.js` | `'attribute'` | **`'play'`** |
| Playbook Summary marks for a play or a defense | Player-attribute scale: three arrows from +3 (97% of trained plays showed three) | The play scale below |
| Player Report and Team Report marks | Attribute scale | Unchanged |

| | One arrow | Two arrows | Three arrows |
|---|---|---|---|
| Offense play, up | under 5 | 5 to 19 | 20 or more |
| Defense, up | under 30 | 30 to 49 | 50 or more |
| Offense play, down | under 5 | 5 to 9 | 10 or more |
| Defense, down | under 10 | 10 to 19 | 20 or more |

- Tones are the existing training movement marks: one up faint green in season (neutral in camp), two up green, three up blue; down red.
- An untrained play is a dash.
- The down bands only show if a report ever carries a drop: CMD never falls in a training session.
- To go back: `PLAY_CMD_SCALE = 'attribute'`.

## Shots

"The Plays tab" is the Training Report's **Playbook Summary** section (the report has no tab of that name; this is where play marks are drawn). The section, shot whole, in `reports/play-cmd-scale/`:

| Week | Before | After |
|---|---|---|
| In season | `before-season-playbook-summary-1280.png`, `-1920.png` | `after-season-playbook-summary-1280.png`, `-1920.png` |
| Camp | `before-camp-playbook-summary-1280.png`, `-1920.png` | `after-camp-playbook-summary-1280.png`, `-1920.png` |

The weeks are fixtures with CMD gains the size the engine really gives (set plays a few points, motions a few dozen, zones 26 to 52, Man 85 to 120). In the in-season shot the eleven trained plays read 4 one-arrow, 4 two-arrow, 3 three-arrow; before, ten of the eleven were three arrows. The defense rows show a CMD of 0 because the fixture's defenses carry no score; the marks are what the shot is for.

## Files touched

- `FrontEnd/static/training-report.js`: the constant and its comment. No other code change.
- Tests: `tests/e2e/training-report-tables.spec.js` (the "today" and "one constant away" tests replaced by six tests of the shipped scale; a shots test), `tests/e2e/polish-training-playbooks.spec.js` (the R2 test's play changes moved from attribute-sized to CMD-sized numbers; its expectations are the same tones), `tests/e2e/helpers/trainingReportFixture.js` (real-sized CMD gains in the season and camp weeks).
- Docs: `Styleguide.md` (Training movement marks: the play bands), `UX_System.md` (Playbook Summary marks row).

## Tests

| Test | Checks |
|---|---|
| The play scale ships | The constant is `'play'`; the four cut-off pairs are the approved ones |
| Offense | +3 and +4 one arrow, +5 and +19 two, +20 three; 0 and untrained a dash; faint green / green / blue |
| Defense | +29 one, +30 and +49 two, +50 three; separate from the offense scale |
| Drops | Offense -4 / -5 / -9 / -10 and defense -9 / -10 / -19 / -20 land on one / two / two / three |
| A real-sized week | In season: offense 4 / 4 / 3, defense 1 / 1 / 2; camp: one up is neutral, +12 two arrows, +46 three |
| Player marks untouched | +2.5 on SC is still two arrows |

Fail-on-old-code: with the constant back at `'attribute'`, 6 of these 7 (with the R2 test) fail; the one that passes is the guard that player marks are untouched.

## Gates (final tree: `1d8be6c67` + this branch)

| Gate | Result |
|---|---|
| `git fetch` + merge `origin/develop` | Already up to date: develop is `1d8be6c67`, the base of this branch. |
| `pytest --ignore=tests/e2e -q` | **4439 passed, 14 skipped, 108 xfailed, 2 xpassed** (exit 0). No `FAILED` / `ERROR`. |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** |
| `scripts/ci/check_migration_gates.py` | **passed** (Gate A 0; Gate B 133 lines in 43 files) |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | **1148 passed, 43 skipped, 0 failed** (5.4 min). Nothing to re-run. |

- The 2 XPASS are the two already on the known-failures list (`test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference`, `test_settings_application_to_gameplay.py::…::test_settings_loaded_and_applied_to_gameplay`); this branch changes no Python and the list was not edited.
- No sim / finalize / cpu_week_pool / sim_rng changes; `franchise-command-center.css` not touched.
- The migration gates still print the note that `newsView.js` fell 3 → 2 on develop (not from this branch; `--write-allowlist` not run).
