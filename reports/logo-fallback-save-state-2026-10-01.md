# Logo fallback + save state: 2026-10-01

Jamie's rulings from the gallery-fixes report. Branch `ux/logo-fallback-save-state` from `origin/develop` (`79e4a6e17`), in `~/gob-audit`; upstream unset. Merged develop twice: `76039eaf5` (court part 3) before the full run (clean), and `fe28bb4d0` (Jamie rulings batch) right before push (doc conflict resolved below; gates and overlapping specs re-run).

## (a) Set Lineup franchise mode: no preset (recorded, no code change)

UX_System "Rulings recorded 2026-10-01 (gallery follow-up)": the five stay empty until the user picks or presses Autoset; only `mode=tutorial` presets.

## (b) Team logos: no team-art 404s

- **Known-asset lists, built once** (no per-image probing): `TEAM_LOGO_SQUARE_SLUGS` (50) and `TEAM_LOGO_PRIMARY_SLUGS` (73) in `common.js`, generated from `images/teams/` on 2026-10-01. Four core programs have neither file: `cupertino`, `decatur_dei`, `empire_city`, `ha_rushmore`. **`tests/test_team_logo_manifest.py`** fails if the lists drift from the files.
- **`filesystemTeamAssetPath(name, 'logo_square')`** (what `getTeamAssetPath` uses for core teams) returns:
  1. `<slug>_logo_square.png` when the team has one;
  2. else `<slug>_logo_primary.png`;
  3. else the generic `general_logo_square.png`.

  Every caller gets a file that exists. Custom / Team Builder programs are unchanged (generated art comes first).
- **`teamLogoArtKind(name)`** returns `square | primary | none` (or `''` for a non-core name). League tables (`gobTables.markHtml`) show the generated letter tile **directly** for `none`, in the team colour and with no request. The letter tile is the last resort.
- **Proof** (desktop server, real Week-1 league):
  - Standings, Team Stats and Rankings log **0** responses ≥ 400 under `/images/teams/`, and each shows `_logo_primary.png` images where squares are missing.
  - On develop (served via `page.route`) the same check fails with the old 404s, e.g. `404 /static/images/teams/lawrence/lawrence_logo_square.png`, `…/houston_jesuit/…`, `…/independence/…`.
  - Shots: `reports/logo-fallback-save-state/{before,after}-{standings,team-stats,rankings}-1280.png`. Rankings now shows the Lawrence / Houston Jesuit / Pacific All-Stars marks instead of letter tiles; Empire City keeps a tile (no art).
- Why a path-level fallback: the 77 404s were `logo_square` requests for teams that only ship `logo_primary` (73) or nothing (4). Primary logos are wider than square (e.g. 750×547); League table marks are small and contained, and they read correctly in the shots.

## (c) Save buttons: orange = there is something to save

**Rule:** a save button is neutral at rest and after a successful save, and orange only while the page's own dirty tracking reports a real unsaved edit. Visual/state only; no save logic, endpoint or data change.

- **Save Game Plan** (`game-plan.js`): `syncSaveDirtyState()` toggles `.is-dirty` from `gamePlanHasEdits()`, the existing real-edit check (moving a slider away and back is not an edit). It is called from `markUnsavedChanges()` and after each of the four places that clear `hasUnsavedChanges` (load, revert, successful save, leave-without-saving).
- **Save Playbooks** (`playbooks.js`): `syncSaveDirtyState()` toggles `.is-dirty` from `hasEdits()`, the same check the leave prompt uses. It is called from `updateTotals()` (every edit path) and `markSaved()` (load and successful save). A Playbooks weight step rebalances the sibling plays, so one step back is still an edit until saved or reverted, exactly as the leave prompt sees it.
- **CSS** (`game-plan.css`, `playbooks.css`): without `.is-dirty` the button is neutral (`--white-6`, `--text-60`, `--line-strong` ring). The existing orange rules apply only with `.is-dirty`. A disabled Save (Playbooks, unbalanced sections) keeps its dead style.
- **Other Prep saves:** none. Player Training and Scouting have no save button. Weekly **Submit Training stays the green Advance** (Jamie).
- **Proof** (desktop server):

  | Button | Rest | Dirty | Edit reverted | After save |
  |---|---|---|---|---|
  | Save Game Plan | neutral | **orange** | neutral | neutral |
  | Save Playbooks | neutral | **orange** | n/a (see above) | neutral |

  On develop: `rest rgb(247,148,32)`, `after save rgb(247,148,32)`, `moved back = no edit rgb(247,148,32)`.
  Shots: `{before,after}-game-plan-{rest,dirty,saved}-1280.png`, `{before,after}-playbooks-{rest,dirty,saved}-1280.png`.

## Docs

- **UX_System:** the Colour law summary adds "orange = there is something to save"; new "Rulings recorded 2026-10-01 (gallery follow-up)" covers (a), (b), (c) and Submit Training.
- **Styleguide** colour-law table: the orange row adds "Save Game Plan / Playbooks (only while there is an unsaved edit: neutral at rest and after a save)".
- **Conflict with develop, flagged:** develop's new "Settled rulings" note (from `reports/jamie-decisions-2026-10-01.md`) says "#9 Submit Training green / Save orange" were *kept as they are*. This brief's ruling (c) changes the Save half. The merge keeps develop's table and amends that sentence: Submit Training green (kept); Save buttons were ruled the same day (later): orange only while there is an unsaved edit. **Please confirm this later ruling supersedes #9's Save part.**

## Tests

- **New `tests/e2e/desktop-logo-save-state.spec.js`** (desktop config, real franchise, deletes its franchise after): 5 tests, (b) ×3 and (c) ×2. All fail on develop's six changed files served via `page.route` (scratchpad copy) and pass on the branch.
- **New `tests/test_team_logo_manifest.py`** (2 tests): lists ↔ disk. On develop the lists do not exist, so it fails.
- **Changed expectations** (they encoded orange-at-rest):
  - `prep-modules-gameplan.spec.js` and `prep-modules-playbooks.spec.js` geometry tests compared Save's rest colour to an orange baseline; they now assert Save is **not** orange at rest.
  - `prep-modules-playbooks.spec.js` "unsaved Save button" read the colour immediately after the edit and caught the 0.18s background transition mid-way (`rgba(248,164,65,0.298)`; 500ms later `is-dirty` and `rgb(247,148,32)`). It now polls until orange.

  These three were the only failures in the first full run (deterministic: 15/15 with `--repeat-each=5`). After the change: 80/80 with `--repeat-each=5`.

## Gates

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` (final merged tree) | **4304 passed**, 14 skipped, 108 xfailed, 2 xpassed, **0 failed** (233.47s) |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 (no pipe), before and after both merges |
| `scripts/ci/check_migration_gates.py` | passed. Gate A 0/0, Gate B 134 lines in 43 files |
| Full Playwright, first lock session (15:30:26–15:45:51) | default **824 passed, 3 failed**, 7 skipped (the three spec expectations above); desktop **17 passed** |
| Full Playwright, second lock session (15:48:31–16:02:29), after the spec updates | default **827 passed, 7 skipped, 0 failed** (14.0m) |
| After merging develop `fe28bb4d0` (Jamie rulings batch; touched `playbooks.css` and `prep-modules-playbooks.spec.js`) | `prep-modules-playbooks`, `prep-modules-gameplan`, `jamie-rulings-batch`, `fcc-peel-2`: **27 passed**; desktop config: **17 passed**. Full suite not re-run a third time. |

## Files

- **Code:** `FrontEnd/static/common.js`, `js/shared/gobTables.js`, `game-plan.{js,css}`, `playbooks.{js,css}`.
- **Docs:** `_documentation_master/11_Design_Systems/UX_System.md`, `Styleguide.md`.
- **Tests:** `tests/test_team_logo_manifest.py`, `tests/e2e/desktop-logo-save-state.spec.js`, `tests/e2e/prep-modules-gameplan.spec.js`, `tests/e2e/prep-modules-playbooks.spec.js`.
- This report + shots.
