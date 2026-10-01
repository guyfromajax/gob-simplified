# Game Plan + Scouting tokens — 2026-09-30

Visual-only migration of Prep › Game Plan and Prep › Scouting onto the design system. Branch `ux/gameplan-scouting-tokens` from `origin/develop`. Colour law wins over frames; conflicts listed below. Work only in `~/gob-audit`.

## Per-file hits (before → after)

Develop baseline from `audit_tree` on this branch before the CSS pass. After is this branch with the three CSS files in `NEW_DESIGN_CSS`.

| File | Colours | Type | Colour-law |
|---|---:|---:|---:|
| `game-plan.css` | 50 → **0** | 38 → **14** | 6 → **0** |
| `scouting-report.css` | 60 → **0** | 37 → **0** | 2 → **0** |
| `css/prep-v2-scouting.css` | 0 → **0** | 1 → **0** | 0 → **0** |
| `game-plan.js` | 8 → **0** (legacy; not reclassified) | 4 → **0** | 1 → **0** |
| `js/shared/scoutingReport.js` | 1 → **0** | 0 → 0 | 0 → 0 |

`game-plan.css` leftover type is leftover standalone chrome (`px` on the old basketball-node slider fallback). Live in-app sliders are `.gt`. `--strict` only fails colour-law on new-design; all three CSS files are **0 law**.

## Frame vs colour-law

Frames served from `_documentation_master/projects` (`python3 -m http.server` on that tree so relative CSS loads): `design_handoff_prep` + `design_handoff_prep_v2` `prep-game-plan-1280.html` and `prep-scouting-1280/1920.html`. Jamie: colour law wins; use neutral; list each conflict.

| Frame paint | Law | Choice |
|---|---|---|
| Enabled **Save Game Plan** orange (v1 `.save`, v2 `.btn-o`) | Orange = committed / saved | **Keep** `var(--orange)` + `/* colour-law: committed */` |
| Top-bar **PLAY NEXT GAME** green | Advance | **Keep** (shell Advance; not this batch) |
| Strategy slider fill / selected stop (v1 `.stops button.on`) | Choice control | Frame v1 is already `--white-10`. **Neutral** in-app (white knob, no orange basketball) |
| Shot-diet tip hover orange (`#f79420`) | Choice control | **Neutral** (`--white-50` / `--text-100`) |
| Validation **OK** / `.btn-primary` green | Not Advance | **Neutral** (`--white-4` / `--text-87`) |
| Standalone toast green accent | Toast is neutral in UX_System | **Neutral** (`--text-60`) |
| Scouting Attributes/Stats selected | Choice control | Already `--white-11` in prep-v2. **Keep** |
| Scouting attribute digits / RT letter | Blue = RT A / 9+ / elite | **Keep** shared RT ramp (`.rtl b.rt-elite`) |
| Reward gold | None on these frames | — |

## Navy-hold list

Jamie has not ruled on navy for selected items. Did **not** add navy to selections.

| Surface | What was there | Kept |
|---|---|---|
| Game Plan selected knob (`.gt-k`) | `--white` | Yes |
| Game Plan selected end-label (`.gt-l.on`) | `--text-100` | Yes |
| Fallback basketball node (`.strategy-slider-node.is-selected`) | Orange SVG | Neutralized (black SVG + white ring). Not navy. |
| Scouting Attributes/Stats (`.seg button.on`) | `--white-11` | Yes |
| Frame v1 `.play.on` navy wash | In shared `prep.css` play-row (Playbooks, not Game Plan sliders) | Untouched — not this surface |

## Shared with court (listed, untouched)

`court.html` and Phaser do **not** load `game-plan.css`, `scouting-report.css`, or `prep-v2-scouting.css`. The timeout path is standalone `game-plan.html?resume_from_timeout=true` (focus shell via `authGuard` → `gobShell.mountFocus`). It does not share selectors with the sim. Left `court.html`, Phaser, and the sim alone.

`resource-pages.css` was not restyled. Game Plan overrides stay under `body.game-plan-page` / `#game-plan-view` / `html.gob-shell .gpc`. No rules added to `franchise-command-center.css`.

## Three Game Plan paths

All three open and paint:

1. In-app `#game-plan-view` (Prep tab)
2. `game-plan.html?mode=tutorial` (focus, read-only, PLAY NOW)
3. `game-plan.html?resume_from_timeout=true` (focus; seed/stub reaches it)

## Scouting speed fix

Unchanged. Opponent still comes from FCC data (`GOBFccPrep.peekUpcomingOpponent`). The e2e stub still 500s `POST /franchise/play-next-game` so a regression would fail. Visual only.

## Deletions (ch8 evidence bar)

Grep of `FrontEnd/static` `*.{js,html}`: no live markup for these classes (only JS looking for missing nodes, or pages that do not load this CSS).

Removed from `scouting-report.css`:

- Unscoped `button { font-family: Bebas }` (was global on every FCC page)
- Dead modal: `.scouting-modal*`, `.scouting-modal-header`, `.scouting-modal-close`, `.scouting-modal-body`, `.scouting-loading`
- Dead CTA: `.scouting-report-btn` (green law hits). FCC HTML has no `#scouting-report-btn`; leftover JS hides it if present
- Dead light-theme sections: `.projected-starting-five-section`, `.scouting-projected-header`, `.scouting-projected-toggle`, `.scouting-projected-table`, `.play-usage-section`, `.play-usage-table`

Kept: `.p5-*` cards (team-roster Starting 5 still calls `renderProjectedStartingFiveCards`), `.scouting-projected-empty`, `.scouting-projected-lineup-wrap`. Those are now tokens; headshot well is 1:1 with `--radius-10` (under a quarter of the side).

No Game Plan class deletions: old basketball-node CSS stays as a non-`.gt` fallback.

## Geometry fixture

`tests/e2e/fixtures/gameplan-before-metrics.json` stayed green (≤2px on every track). Execution / Transition colour still `--text-60` (`rgba(255,255,255,0.6)`). Not updated.

## Screenshots

Desktop pages and FCC views: Playwright `page.screenshot` after `scrollTo(0,0)` (and `#game-plan-view` / `#scouting-view` / `.main` scroll 0). Frames opened from `FRAMES_BASE` (http.server on `_documentation_master/projects`).

| State | Before | After | Frame (beside) |
|---|---|---|---|
| Game Plan in-app 1280 | `before-in-app-1280.png` | `after-in-app-1280.png` | `frame-game-plan-v2-1280.png` (also `frame-game-plan-v1-1280.png`) |
| Game Plan in-app 1920 | `before-in-app-1920.png` | `after-in-app-1920.png` | — |
| Unsaved + enabled Save 1280 | `before-unsaved-1280.png` | `after-unsaved-1280.png` | — |
| Unsaved 1920 | — | `after-unsaved-1920.png` | — |
| Saved toast 1280 | `before-saved-1280.png` | `after-saved-1280.png` | — |
| Saved 1920 | — | `after-saved-1920.png` | — |
| Timeout resume 1280 | `before-timeout-1280.png` | `after-timeout-1280.png` | — |
| Tutorial 1280 | `before-tutorial-1280.png` | `after-tutorial-1280.png` | — |
| Scouting in-app 1280 | `before-scouting-1280.png` | `after-scouting-1280.png` | `frame-scouting-v2-1280.png` |
| Scouting in-app 1920 | `before-scouting-1920.png` | `after-scouting-1920.png` | `frame-scouting-v2-1920.png` |

Timeout path is reachable from the stub (`resume_from_timeout=true`). Electron was not required.

## Tests

- `tests/e2e/gameplan-scouting-tokens.spec.js`: before/after shots, geometry fixture, computed-style guards (choice controls not green/orange, Save orange when dirty, scouting `.av` square), frames.
- Existing `prep-modules-gameplan.spec.js` / `prep-scouting.spec.js` left in place.

## Gates

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` (after `f65a541a9`) | **4297 passed**, 14 skipped, 108 xfailed, **2 xpassed**, 0 failed (246.77s). XPASS: `test_resource_page_scoping::test_leaders_view_scope_filters_to_user_conference` (pre-existing) and `test_settings_application_to_gameplay::...::test_settings_loaded_and_applied_to_gameplay` (XPASS not in the earlier 4264-pass run; this branch does not touch it; origin not investigated). `known_failures.py` not edited. |
| Playwright full `tests/e2e --workers=1` under `/tmp/gob-full-playwright.lock`, after merging `origin/develop` + `f65a541a9` (PORT=8244, FRAMES_BASE=8243) | **789 passed, 5 skipped, 0 failed** (11.9m). No flaky reruns needed. All 7 `gameplan-scouting-tokens.spec.js` tests passed, frames included; the 3 invite-board seed-notice tests are green. Skips are pre-existing `test.skip`s (office live digest, retire-prep in-app scouting before, t3 offline compact header, tournament offline week 27, training flow shots). |
| Targeted `gameplan-scouting-tokens.spec.js` | **7 passed** (PORT=8244, FRAMES_BASE=8243) |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 (re-run 2026-10-01). Colour-law new-design **0**. |
| `scripts/ci/check_migration_gates.py` | passed (re-run 2026-10-01). Gate A: 0/0. Gate B: 136 lines in 44 files. NOTES: training-report.html and training.html now clean (allow-list can shrink; not edited). Did not `--write-allowlist`. |

## Files touched

- `FrontEnd/static/game-plan.css`
- `FrontEnd/static/game-plan.html` (`class="gob"`, `gob-tokens.css`)
- `FrontEnd/static/game-plan.js` (toast accent neutralized; unsaved-warning paint moved to classes)
- `FrontEnd/static/scouting-report.css`
- `FrontEnd/static/css/prep-v2-scouting.css`
- `FrontEnd/static/js/shared/scoutingReport.js` (empty-cell class; no fetch/cache change)
- `scripts/check_ui_tokens.py` (`NEW_DESIGN_CSS` + docstring)
- `tests/e2e/gameplan-scouting-tokens.spec.js`
- `tests/e2e/fixtures/gameplan-before-metrics.json`
- `_documentation_master/11_Design_Systems/UX_System.md` (Game Plan / Scouting choice-chrome sentence)
- `reports/gameplan-scouting-tokens-2026-09-30.md` + `reports/gameplan-scouting-tokens/*.png`

Not touched: `franchise-command-center.css`, `resource-pages.css`, box-score, cut-players, set-lineup, training, playbooks, recruiting (except the seed-notice e2e below), `office-home.*`, `court.html`, Phaser, the sim, `uiSfx`.

## Suite health

`origin/develop` (roster-name-lookup merge) was merged into this branch at `5eec55162`. Full Playwright after that merge is the Gate line above.

### Invite-board seed-notice (the 3 reds from the roster full run)

Not full-run-only. Isolated `--repeat-each=5` on this tree (develop + batch-4; those specs unchanged by Game Plan CSS):

| | Result |
|---|---|
| Before fix | **4 failed / 11 passed** (15 runs, 3.3m). `dismissible` timed out twice; `disappears once the board is saved` and `saving is the only thing that posts the order` each failed at least once. |
| After fix | **15 passed** (17.0s) |

**Cause:** `maybeShowSeedModal` loads `sammyModal.js` from the e2e server and puts **Got It** over the board. Playwright `force: true` still clicks whatever is on top. Screenshot of the isolated fail shows the Sammy overlay; `#board-seed-dismiss` is in the a11y tree underneath. `9bdd19a73` already dismissed Got It before the reorder `×`; the other three tests did not. Not uiSfx disabled-skip, not submit-cuts `adoptMain`, not signing-orders-panel.

**Fix** (same branch, separate commit `f65a541a9`): `dismissSeedSammy()` before those three clicks.
