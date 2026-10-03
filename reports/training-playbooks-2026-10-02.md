# Training / Report / Game Plan / Playbooks / Set Lineup polish — 2026-10-02

Branch `polish/training-playbooks`, from `origin/develop` `b3eb1fb25`. Ready for review; not merged.

## Flags first

| # | Flag |
|---|---|
| 1 | **R2: there are two scales, as you expected.** Thresholds below. I changed no threshold, only the colours. |
| 2 | **R2 colours overrule two lines of the colour law** (▼ never red; blue is RT only). I recorded your colours in the Styleguide as a new data scale, "Training movement marks", and as "Settled 2026-10-02". Confirm, or say which way it should go. |
| 3 | **Worktree.** Work is in `~/gob-training-playbooks`, not `~/gob-ux`. Switching branches in `gob-ux` was blocked: it holds 320 uncommitted files on `docs/qa-playthrough`. Nothing in `gob-ux` was touched. |
| 4 | **T6 not reproduced.** At 1280×720 on seeded data the header never covered a row, on the old tree or the new. Cause and fix are below; if you still see it, tell me the window size. |
| 5 | **One extra fix, not on your list.** The Training Report head is sticky but had a transparent fill, so every section scrolled through the title and the button. It now has the page's solid fill. Say so if you want it reverted. |
| 6 | **26 scratch PNGs left in `reports/training-playbooks/`** (`wip-*`, `explore-1`, four stale `before-*`). Deleting them was not permitted in this session. They are untracked and not committed; safe to delete. |

### R2 thresholds (found in `training-report.js` `describeTrainingChange()`)

`n` is the raw change. Camp is report week 1.

| Week | One | Two | Three |
|---|---|---|---|
| Training Camp | 0 < \|n\| < 2 | 2 ≤ \|n\| ≤ 5 | \|n\| > 5 |
| Non-camp, up | −0.5 ≤ n < 1 | 1 ≤ n < 3 | n ≥ 3 |
| Non-camp, down | −1.5 < n < −0.5 | −2.5 < n ≤ −1.5 | n ≤ −2.5 |

- Camp is symmetric, and exactly 0 is a dash.
- Non-camp has no dash: 0 and dips to −0.5 show one up. So in a normal week every unchanged attribute shows one neutral ▲.

## Items

| Item | Status | What changed / root cause |
|---|---|---|
| T1 | Done | Auto-Train plays `chaotic-choice.wav`, the Autoset Lineup cue. Commit `422e151a6` had swapped it for the select click. No sound file added or staged. |
| T2 | Done | Player Development is cards: 4 columns of 3, RT order down each column. A 15-player camp roster keeps 4 columns and adds a row. |
| T3 | Done | **Missing, not broken.** Commit `69573d8f6` hid the section on the weekly page on purpose. Restored under Coaching Focus; position and focus save on change. Prep › Player Training is unchanged. |
| T4 | Done | Four neutral cards. Mark = icon + 2px left edge. Tokens `--coach-authoritarian` / `-systems` / `-maximizer` / `-culture`; `--purple` is new. Styleguide: "Coaching style marks". |
| T5 | Done | Four options: Top 3 Attributes, Attributes 4–6, Positional Focus, Custom. Modal title is the option chosen. Cause of "below the fold": the focus shell adopts body children into `.main` and makes them `position: relative`, so the fixed modal became an in-flow block at the page foot. It is now a `.gob-modal-overlay`, which the shell leaves alone. |
| T6 | Done (see flag 4) | The modal sat inside the scrolling page, where the shell's sticky-header rule applied to its table. The rebuilt modal has its own header in its own scroll box. |
| T7 | Done | "Press/Traps" in the drill title, both install rows and the Systems Coach option. Training page only. |
| T8 | Done | Cause: once any point was spent, the click opened the "Unsaved Training" leave confirm instead of the page. The trip is part of the same flow (draft saved, restored on return), so it no longer asks. Test added; the old test never spent a point. |
| T9 | Done | "Training Plays", with space above the toggle. |
| T10 | Done | More space between the Training by Position button and the tallies. Change is in `training.css`. `franchise-command-center.css` untouched: 1779 lines / 230 rules. |
| R1 | Done | Sections and the "--" placeholders stay hidden until the data is in; a skeleton stands in. The static page carries the hidden state, so it holds from first paint. |
| R2 | Done | Colours as specified, both scales. Applied wherever the marks appear, including Playbook Summary (same function). |
| R3 | Done | Attributes view shows `+` / `−` beside the value, same tones. Tooltip matches. |
| R4 | Done | Offense and Defense panels side by side; sub-sections as columns; no Section column. |
| G1 | Done | Shot Diet and Disruption are section heads like Execution and Transition. The four heads line up across the gutter. Shot Diet lost its inset line. |
| P1 | Done | Set Plays has Inside / Attack / Outside sub-sections, each with its play count and share. |
| P2 | Done | Tabs: Offense, Defense, Fast Breaks, Press/Traps. |
| P3 | Done | Cause: ending a drag re-rendered the tiles and destroyed the focused slider, so the arrow keys had nothing to act on. Focus now returns to the same slider. |
| P4 | Done | "Shot Distribution". |
| L1 | Done | Buttons sit directly under the charts. Cause: `margin-top: auto` pinned them to the panel foot. |

Nothing skipped.

## Calls I made — say if any is wrong

| Where | Call |
|---|---|
| T5 | Cancel, Escape or the backdrop return to the focus that was in force before the modal. Assign keeps the option. |
| T5 | "Assign Focus Attributes" is a neutral plate, not orange: it saves nothing; Submit Training is the save. |
| T5 | "Attributes 4–6" keeps the en dash already used in the app. |
| T4 | The four icons (whistle, play diagram, rising bars, group) are my drawings. Swap freely. |
| T4 | `--purple` is `#A876E6`, the purple already in the coaching archetype badge set. |
| T7 | The Training Report and Team Attributes still say "P/T Defense" / "P/T Offense": the Styleguide fixes that vocabulary. Rename there too? |
| T8 | The button still reads "Custom Playbook" (singular). You wrote "Custom Playbooks" twice. Rename? |
| P1 | Rows now read "Target shooter SF", not "Inside · Target shooter SF": the sub-section head says it. This changed one assertion in `polish-prep-plan.spec.js`. One-line revert. |
| P2 | The Press/Traps tab's section is still titled "HC Traps". |
| R4 | A set play with no focus would appear in an "Other Set Plays" column instead of being dropped. None exist in the fixture. |

## Existing tests changed

| Spec | Change | Why |
|---|---|---|
| `training-advance-focus.spec.js` | `#player-dev-section` expected visible, with one card per player | T3 |
| `prep-modules-training.spec.js` | Opens the modal with the Top 3 option | T5 removed "Choose Attributes" |
| `polish-prep-plan.spec.js` | Set-play row line starts "Target shooter"; heads are Inside / Attack / Outside | P1 |

## Files touched

- `FrontEnd/static/`: `training.html`, `training-shell.js`, `training.js`, `training.css`, `training-report.html`, `training-report.js`, `training-report.css`, `game-plan.html`, `game-plan.js`, `game-plan.css`, `playbooks.html`, `playbooks.js`, `playbooks.css`, `set-lineup.css`
- `FrontEnd/static/css/`: `gob-tokens.css`, `player-development-grid.css`
- `FrontEnd/static/js/shared/playerDevelopmentGrid.js`
- `_documentation_master/11_Design_Systems/`: `Styleguide.md`, `UX_System.md`
- `tests/e2e/`: `polish-training-playbooks.spec.js` (new, 22 tests), and the three above

Not touched: sim / finalize / cpu_week_pool / sim_rng, the unsaved-changes modal, Settings, Mode Select, top strip, audio controls, court screens, any stats-owned file, `gob-tables.css`, `FrontEnd/static/sounds/`. No auth or ownership code.

## Tests

- New spec: 22 tests, all pass on this tree. **All 22 fail on the old tree** (run against an export of `b3eb1fb25`).
- Before / after shots at 1280: `reports/training-playbooks/before-*.png` and `after-*.png`. Before shots were taken on the old tree.

## Gates (final tree = `origin/develop` `b3eb1fb25` + this branch; merge was a no-op)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | exit 0: **4313 passed, 14 skipped, 108 xfailed, 2 xpassed** (241s) |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 |
| `scripts/ci/check_migration_gates.py` | exit 0 (Gate A 0 imports; Gate B 134 lines in 43 files) |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | **877 passed, 16 skipped, 2 failed** (5.8 min) |

The 2 XPASS are not from this branch; both xpass the same way on `b3eb1fb25`:

- `tests/test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference`
- `tests/test_settings_application_to_gameplay.py::TestSettingsApplicationToGameplay::test_settings_loaded_and_applied_to_gameplay`

The 2 Playwright failures, re-run alone with `--repeat-each=5`:

| Spec | Alone ×5 | Verdict |
|---|---|---|
| `tournament-view.spec.js:259` brackets.html redirects into the view | 5 / 5 pass | Load flake (`waitForURL` timeout in the full run). |
| `office-frontend.spec.js:932` attribute chips group, order, and cap | 1 / 5 pass | **Already red on develop.** Same test on an export of `b3eb1fb25`, alone ×5: 0 / 5 pass, same error (expects 5 `.gn` rows at 1920, gets 3). Office is not touched by this branch. Not fixed here. |

## Unsure about

- Flags 2 and 4, and every row of "Calls I made".
- The Playwright before shots show each old screen under the same file name as its after shot. The T6 pair shows the old in-flow modal, not an overlap (flag 4).
- `tests/conftest.py` overrides auth for every test. Nothing here touches auth or ownership.

