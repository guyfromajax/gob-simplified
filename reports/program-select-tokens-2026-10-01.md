# Program select on gob tokens: 2026-10-01

Batch 4 of `reports/ux-remaining-map-2026-10-01.md`. Branch `ux/program-select-tokens` from `origin/develop` (`bfd66e649`), in `~/gob-audit`; upstream unset. Merged develop `5d22f4dac` (shared chrome) right before push: conflicts in `franchise-select-team.html` (both sides added the `gob-tokens.css` link; develop's "page itself is not migrated yet" comment dropped) and `UX_System.md` (both sections kept). `NEW_DESIGN_CSS` keeps every entry.

## Scope

`franchise-select-team.html` / `.css` / `.js`: Find Your Program (new franchise) and Team Builder step 1 (`?builder=1`). One sheet, 89 colour literals / 16 law hits before, 0 literals after; now in `NEW_DESIGN_CSS` (strict).

**Visual only.**
- **HTML:** `class="gob"` and a `gob-tokens.css` link.
- **JS:** one class string: the action-bar CTA was `'btn lg'` (builder) / `'btn lg grn'` and is now `'btn lg advance'`. No logic, endpoint or id changed.

## Rulings (matched to Team Builder)

| Element | Before | After |
|---|---|---|
| Enter Franchise (`#ab-primary`) | green `.grn` | green `.btn.advance` (on the checker's allow-list) |
| Take This Slot (builder `#ab-primary`) | **orange** | **green**: Team Builder step 1's Continue, which Team Builder paints as the Advance |
| Selected card (`.pg.sel`), check (`.pg-check`) | orange | **navy** (`--navy-hi`), as Team Builder's selected row |
| Open Team Builder, draft Continue (`.btn`) | orange | neutral white plate (navigation) |
| Scout / Clear / Discard / Cancel | ghost | ghost (tokenised) |
| Search focus, active filter (`.fsel.on`), Clear link, card hover | orange | neutral (choice controls) |
| Top Talent / Prestige tier text (`.top1` yellow, `.top1t` orange) | yellow / orange | `--text-100` bold (information codes) |
| Team Builder mode banner (`.mbar`), builder headline | orange wash, peach text | neutral surface, `--text-100` |
| Team Builder entry card (`.tbe`) | orange wash | neutral |
| Unfinished draft card (`.draft-card`) | blue wash | neutral (blue is RT only) |
| Loading dots, toast bar | orange | neutral |
| Error | pink literals | `--red` |
| Team colour | banner art only | unchanged: only each program's own banner art |

**Open Jamie decision this relies on:** the map lists "navy for selected items" as undecided across batches 2–4. Following the brief ("match Team Builder"), the selected program card is navy, like Team Builder's selected row. If the ruling goes neutral, change `.pg.sel` and `.pg-check` only.

## `css/team-picker.css`: dead, list for deletion (not deleted)

- No HTML, JS, CSS, Python or desktop file links or injects `team-picker.css` (grep across `FrontEnd/static`, `BackEnd`, `desktop`, `tests`).
- Its classes (`.team-picker*`, `.team-card*`) are rendered only by `TeamPicker.mount()` in `js/shared/teamPicker.js`. **Nothing calls `mount`** (the one hit is its own error string).
- `teamPicker.js` is still loaded by `franchise-select-team.html` and `team-builder.html`, but only for helpers: `fetchTeams`, `regionFromConference`, `geographyForConference`, `formatGeographyList`, `distinctGeographies`, `assignRankBands`, `formatConferenceLabel`.
- `franchise-select-team.js`'s header says it "replaces the old TeamPicker-mounted franchise entry".
- `mode-select.css`'s `.lbt-team-card` is a different class.

**Recommendation:** delete `css/team-picker.css`, plus `TeamPicker.mount` and its render helpers in `teamPicker.js` (keep the data helpers), in a cleanup pass. The program picker renders correctly without it (shots below).

## Shots

`reports/program-select-tokens/{before,after}-<surface>-{1280,1920}.png`, via `page.screenshot` at scroll 0. BEFORE was captured on develop CSS before any edit (`PROGRAM_SELECT_BEFORE=1`). The e2e seed has no teams, so the spec stubs `/teams` with 128 synthetic programs (16 conferences × 8) named after real art folders so the banner cards load. Drafts and `/app-config` are also stubbed.

Surfaces:
- `browse`;
- `selected`: card selected, action bar with Enter Franchise;
- `filtered`: active Talent filter, dimmed cards;
- `builder-selected`: `?builder=1` banner, Take This Slot;
- `draft`: unfinished-draft card.

## Tests

- `tests/e2e/program-select-tokens.spec.js`: shots + computed-style guards:
  - `html.gob` and tokens resolve; Bebas title;
  - no orange on the entry card, back link, search focus, active filter, Clear, card hover, builder banner and headline;
  - Open Team Builder, Scout and draft Continue neither orange nor green;
  - tier markers neither orange nor yellow;
  - selected card navy and not orange; check not orange;
  - Enter Franchise green with dark ink; Take This Slot green;
  - draft card not blue; error red; loading dot not orange.
- **Fails on old code:** ran the guards (soft) with develop's css/html/js served via `page.route` from a scratchpad config. They fail across the page:
  - `selected card navy rgb(247,148,32)`, `check …`;
  - `Take This Slot green rgb(247,148,32)`, `Open Team Builder neutral …`, `draft Continue neutral …`;
  - `active filter rgba(247,148,32,0.55)`, `search focus …`, `Clear …`;
  - `tier marker neutral rgb(255,215,0)` / `rgb(247,148,32)`;
  - `builder bg …`, `Team Builder entry not orange …`, `draft card not blue rgba(74,144,217,0.1)`, `loading dot …`, `html.gob`.

## Gates

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` | **4298 passed**, 14 skipped, 108 xfailed, 2 xpassed, **0 failed** (241.72s). Same two XPASS as before. |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 (no pipe), before and after the merge |
| `scripts/ci/check_migration_gates.py` | passed. Gate A 0/0, Gate B 134 lines in 43 files. No `--write-allowlist`. |
| Playwright full `tests/e2e --workers=1` under `/tmp/gob-full-playwright.lock` (PORT=8244), pre-merge tree `0c05d474a` | **815 passed, 7 skipped, 0 failed** (13.5m). No failures, so no reruns. Skips: 5 existing `test.skip`s plus 2 "handoff frames" tests that skip without `FRAMES_BASE`. |
| After merging develop `5d22f4dac` | strict exit 0; migration gates passed; `tests/test_check_ui_tokens.py` 10 passed; `program-select-tokens` + `shared-chrome-tokens` + `desktop-play-flow` (the specs that load this page) **7 passed**. The full suite was not re-run after the merge (one full run per the brief). |

## Files

`FrontEnd/static/franchise-select-team.css`, `franchise-select-team.html`, `franchise-select-team.js` (one class string), `scripts/check_ui_tokens.py` (`NEW_DESIGN_CSS` + docstring), `_documentation_master/11_Design_Systems/UX_System.md` ("Program select"), `tests/e2e/program-select-tokens.spec.js`, this report + shots.

## Unsure

- Navy selection: see the open decision above.
- "127 of 128 match" appears in the shots with the synthetic stub data on both develop and this branch (not investigated; no filter logic was touched).
