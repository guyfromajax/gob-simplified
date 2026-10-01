# Team Builder onto the design tokens + colour law (2026-10-01)

**Status: ready for review.** Branch `ux/team-builder-tokens`, pushed. Not merged.

## Branch

| Commit | What |
|---|---|
| `aab140a1c` | Team Builder on tokens + colour law (the work) |
| `a0332d276` | Merge `origin/develop` (Game Plan + Scouting tokens). One conflict, `scripts/check_ui_tokens.py`: kept every `NEW_DESIGN_CSS` entry from both sides. |
| `e16a1d981` | One-line annotation in `box-score.css` so the strict token gate passes (see "Found") |
| `51dff5615` | Merge `origin/develop` (`b5af426ae`, game overlays tokens). No conflicts. |
| this commit | Report + screenshots |

History of the detour: the first `git checkout -b … origin/develop` was denied by the permission classifier, so the work was done uncommitted on the old branch (whose tree was identical to develop `47480f350` at the time). After Jamie's instruction the branch was created with the work carried over, committed, and develop merged twice. Every gate below was re-run on `51dff5615`.

Branch delta vs `origin/develop`: 11 files (the table below, plus `box-score.css`), plus this report and its screenshots.

## Scope

Team Builder is not tiny and was not tokenised: one page (`team-builder.html`), one sheet (2,141 lines), six JS modules.

| File | Change |
|---|---|
| `FrontEnd/static/team-builder.html` | `<html class="gob">` + `css/gob-tokens.css` link |
| `FrontEnd/static/team-builder.css` | page-local `:root` palette removed; every colour, radius, weight and font family on tokens; colour-law edits |
| `FrontEnd/static/team-builder.js` | Continue buttons get `tb-advance`; 4 inline `#fff` → `--text-100`; comment |
| `FrontEnd/static/js/team-builder/roster.js` | `scaleColor` → `--tier-*`; inline status / changed / meter colours → tokens; position and category inline colours removed |
| `FrontEnd/static/js/team-builder/review.js` | position chip inline colour removed; portrait well → `--white-12` |
| `FrontEnd/static/js/team-builder/establish.js` | Enter Franchise gets `tb-advance`; comment |
| `FrontEnd/static/js/team-builder/constants.js` | `ATTR_CATS` colours and `POS_COLOR` removed (no other caller) |
| `scripts/check_ui_tokens.py` | `team-builder.css` added to `NEW_DESIGN_CSS`; docstring |
| `_documentation_master/11_Design_Systems/UX_System.md` | new "Team Builder" section (the rulings below) |
| `tests/e2e/team-builder-tokens.spec.js` | new, 3 tests |
| `FrontEnd/static/box-score.css` | comment only (separate commit) |

Not touched: sim, finalize, `cpu_week_pool`, `sim_rng`, any backend file. `ATTR_MIN` / `ATTR_MAX` (5 / 99), `setAttr`, `cappedAttrMax` and the budget logic are unchanged; the spec asserts the slider `max` is `99` and a 99 renders as `99`.

## `team-builder.css` before → after (checker, file scanned as new-design)

| | Before (develop) | After |
|---|---|---|
| Colour-law hits (green / orange) | 15 / 16 | **0 / 0** |
| Raw colour literals | 290 | **0** |
| `font-weight` literals | 83 | 0 |
| `font-family` literals | 9 | 1 (the `@import`) |
| `font-size` literals | 151 | 74 |
| `letter-spacing` literals | 107 | 24 |
| `var(--…)` uses | 296 | 900 |

The 74 sizes and 24 trackings left are values with no token (9px, 10.5px, 12.5px, 19px, 62px; .09em, .13em, .2em…). I did not round them: that would move layout. Four radii stay literal for the same reason (`1px`, `999px`).

Nearest-step mappings, each a small visible shift: text `.88/.56/.36` → `--text-87/-60/-38`; panels → `--bg-chrome`, `--surface-1`, `--surface-2`, `--surface-popover`; 16px card radius → `--radius-card` (14px); monospace captions → `--font-body` (the system has no mono face); ramp blue `#4A90D9` → `--tier-blue` (`#6BA4E0`).

## Colour-law rulings (each is a choice: please confirm or reverse)

Applied "colour law wins, use neutral, list each conflict" (your Set Lineup decision). The page's old rule was "green = valid, orange = primary button", which the law does not allow.

| Element | Was | Now | Why |
|---|---|---|---|
| Continue / Continue to Review | orange | **green** (`.btn.tb-advance`, shell Advance paint) | The chapter's one forward action; it already plays the Advance sound. The alternative is neutral. **Biggest call here.** |
| Establish <program> | orange | **orange**, annotated `committed` | Irreversible write. The only orange left. |
| Enter Franchise | green | green (`tb-advance`) | Advance. |
| Valid / legal / eligible / exact (dots, verdict, meters, tallies, pool, "CVT is free", eligibility card and headline) | green | `--text-100`, neutral borders | Status labels are neutral. Invalid stays red. |
| Selected roster row | RT blue wash + edge | **navy** | Set Lineup precedent. |
| Your seat after the swap (Establish) | green wash | **navy** | "Yours". |
| Changed-from-inherited (class chip, height, dot, deltas, legend) | orange | `--text-100` | A diff marker, not a save. |
| Chapter cell, selected style button, palette ring, input focus, slider focus, tile hover | orange | neutral | Choice controls. |
| Position chips (PG blue, SG purple, SF green, PF red, C gold) | per-position colour | **neutral chip** | Blue is RT only; the app has no position colours elsewhere. **Most visible change.** |
| Attribute category headings + legend codes (Offense orange, Defense blue, Endurance green…) | per-category colour | **neutral** | Information codes. |
| Wait pulse, pending sweep, picker accent, eyebrow, links | green / orange | neutral | Not Advance, not a save. |
| Attribute ramp (bars, signature, grid cells) | red / yellow / green / blue | same, via `--tier-*` | The sanctioned ramp. |

Kept as data, not changed: palette and swatch fills, court / banner / jersey art, skin-tone filter chips, and the Review "your program" row tint (the program's own primary colour). The law says "your row" is navy; I left that one because it is the team colour, not chrome. Say if you want it navy.

Dead rules (no JS emits the class) were neutralised, not deleted: `.footbar`, `.stub`, `.toast`, `.alert`, `.uncapped`, `.commit`, `.local`, `.mdl-t/-s/-a`, `.d-warn`, `.warn`.

## Headshots

| Element | Size | Was | Now |
|---|---|---|---|
| Board badge `.pt` | 26px | 5px | `--radius-6` |
| Review badge `.fifteen .pt` | 38px | 7px | `--radius-6` |
| Inspector portrait `.pt-lg` | 104px | 10px | `--radius-10` |
| Picker tile `.pk-i` | ~82px | 7px | `--radius-10` |

## e2e spec

`tests/e2e/team-builder-tokens.spec.js`: 3 tests, both viewports, APIs stubbed, **computed styles only**.

- Continue / Continue to Review / Enter Franchise background is exactly `--green`; on Identity it is the only green button; disabled it is neutral.
- Establish background is exactly `--orange`.
- 30-odd elements (status, choice controls, chips, markers, pulse, accents) have no green, orange or RT blue in colour, background, border, gradient or shadow.
- Selected row shadow is navy and its background is not RT blue.
- Headshot radii are 6 / 10 px and under a quarter of the side.
- Ramp: 99 → `--tier-blue`, 72 → `--green`, 22 → neither; slider `max` is 99.
- Team names as stored: `Bentley-Truman`, `IDA`, `Seattle AAA`.

**Fails on the old code (verified):** with develop's Team Builder files restored, all 3 tests fail (Continue is orange not green; eligibility card border is green; a status element is not neutral). Files restored afterwards; the spec then passed 15/15 at `--repeat-each=5`.

## Screenshots (`reports/team-builder-tokens/`, `page.screenshot` at scroll 0)

`before-*` from develop's Team Builder (`47480f350`; no later develop commit touches these files), `after-*` from this branch. Each at 1280 and 1920 (36 files).

| State | File stem |
|---|---|
| Identity | `identity` |
| Gate, nothing chosen | `gate-unchosen` |
| Gate, capped chosen | `gate-capped` |
| Roster, legal | `roster-legal` |
| Roster, not legal | `roster-not-legal` |
| Roster, full grid | `roster-grid` |
| Portrait picker | `roster-portrait-picker` |
| Review | `review` |
| Establish, complete | `establish` |

Portraits are a flat test tile (the spec stubs the image CDN).

## Gates (all on `51dff5615`)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | exit 0. **4297 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (240s) |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** (read directly, no pipe). New-surface hits 0 / 0 / 0. |
| `scripts/ci/check_migration_gates.py` | **exit 0**. Gate A 0 / 0; Gate B 134 lines / 43 files (unchanged) |
| Full Playwright, one run under `/tmp/gob-full-playwright.lock`, `--workers=1`, `CI` unset, port 8017 | exit 0. **796 passed, 7 skipped, 0 failed** of 803 (12.4m). Lock taken 08:49:56, released 09:02:23. |
| Failure re-runs at `--repeat-each=5` | none needed (0 failures) |

Two earlier full runs were stopped part-way on purpose, each because the tree was about to change under them (branch fix, then the second develop merge). Neither had a failure when stopped (712/796 and about half-way). Only the run above counts.

XPASS (report only, list not edited), both unrelated to this change:
- `tests/test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference`
- `tests/test_settings_application_to_gameplay.py::…::test_settings_loaded_and_applied_to_gameplay`

## Found

1. **Fixed (own commit `e16a1d981`): the strict token gate was red on develop.** `box-score.css:491` had `/* colour-law: positive-data */`, but the `background` on line 494 is 3 lines below it and the checker's annotation window is 2, so `--strict` exited 1. The 2026-09-30 report said exit 0; `… | tail` returns `tail`'s exit code, which is the likely misread. Fix is the same annotation on line 494: comment only.
2. **Not fixed: resuming a Team Builder draft crashes boot.** `team-builder.js` boot → `mergeIdentity` → `TeamBuilderIdentity.clampName`, which reads `C.PROGRAM_NAME_MAX_LEN`; `C` is only set when an `IdentityChapter` is constructed, which happens later. Result: `TypeError`, page stays on "Loading Team Builder…". Reproduced in Playwright with a stubbed draft that has `identity`. `GET /franchise/team-builder/drafts` returns the whole stored doc and boot always stores `identity`, so a second visit should hit it. Not reproduced against a real backend. The spec types the identity in to avoid it.
3. Not fixed: `cut-players.css` uses `var(--white-8)`, which `gob-tokens.css` does not define (the pulse track renders transparent).
4. Not fixed: "Establish Cascade Valley" is clipped on the right in the Review band at both widths, before and after.

## Leftovers in the working tree (not committed)

- `tests/e2e/zz-tb-debug.spec.js`: my scratch file. `rm` was denied, so I emptied it (comments only, no tests). Untracked; delete it.
- ~240 tracked `reports/**` images of other tasks show as modified (regenerated by Playwright runs; dirty before I started). `git checkout -- reports/` restores them.
