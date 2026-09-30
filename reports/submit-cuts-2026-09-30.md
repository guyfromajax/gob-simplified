# Submit practice-squad assignment — 2026-09-30

Branch `fix/submit-cuts` from `origin/develop`. Week-1 `/cut-players.html` (no `mode=cut`) is practice-squad assignment after camp. Jamie's live hit: press Submit, hear a click, nothing happens. No server/payload change. `mode=cut` is sunset and not deleted.

## Repro (web + desktop, week 1 after camp)

| Selected vs `cutCount` | `#submit-btn` disabled | Computed look | Status / reason | Click fires | `#cut-modal-backdrop.is-visible` | `elementFromPoint` at centre | POST | `exitFlow` |
|---|---|---|---|---|---|---|---|---|
| Fewer (0 of 3) | yes | `cursor: not-allowed`, opacity &lt; 1, `--text-38` | Status visible; reason **Assign 3 more to the practice squad** next to the button | force-click only; hook + handler no-op | no | n/a | none | n/a |
| Exact (3 of 3) | no | live green **Assign Practice Squad** | Status visible; reason hidden | yes (`SFX_COMMIT` via `data-sfx`) | yes, `position:fixed`, parent `BODY` | hit is inside the overlay | `POST /franchise/cut-players` `{franchise_id, player_ids}` = the three selected ids | FCC `/franchise-command-center.html` |
| More (4 of 3) | yes | same dead look | reason **Remove 1** | force-click silent | no | n/a | none | n/a |

## Root cause(s)

**(b) Confirm modal under focus chrome — this is the live "sound, nothing happens" when the count is right.**

`gobShell.adoptMain` (`FrontEnd/static/js/shared/gobShell.js:1153`) moved every body child except scripts/footer into `#gob-main`. `#cut-modal-backdrop.gob-modal-overlay` went with them. `.gob .main>*` (`gob-components.css:71`) then won on specificity and set `position: relative; z-index: var(--z-raised)`. `resource-pages.css:371` `position: fixed; z-index: 200` lost. The dialog became an in-flow box under the table / sticky header. `submitCuts` (`cut-players.js:284`) had already played `confirm-2-lowervol.wav` and called `showModal`. Jamie heard the click and saw no dialog.

**(a) Disabled Submit did not look dead, and the click path played a sound anyway.**

`updateStatus` (`cut-players.js:157`) already set `disabled` + `.is-dead` when `selectedIds.size !== cutCount`. The handler still called `playSound('confirm-2-lowervol.wav')` before `submitCuts` (`cut-players.js:480`). A real disabled click does not fire, but `installSfxHooks` (`uiSfx.js:287`) played `data-sfx` on any matching click and did not skip `disabled` / `.is-dead`. After the token/shell pass the green `#submit-btn` still read as live (`cursor: default` in `resource-pages.css:275`). Wrong-count clicks that did reach JS returned silently in `submitCuts` (`cut-players.js:286`).

**(c) `exitFlow` after a successful POST was not a no-op.** `cut-players.js:325` already called `GOBNav.exitFlow(buildFccUrl())`. Once the confirm path is visible and the POST returns, landing is the FCC. Ruled out as a separate bug.

## Fixes

- `uiSfx.js` `onSfxClick`: skip `disabled`, `aria-disabled="true"`, `.is-disabled`, `.is-dead` (every `data-sfx` control, not just this page).
- Week-1 button label **Assign Practice Squad**; `data-sfx="SFX_COMMIT"` only (no second `playSfx` in the handler). Handler returns if the button is dead.
- Reason next to the button: "Assign N more to the practice squad" / "Remove N". Disabled look: `not-allowed` + `--text-38`.
- `adoptMain` leaves `.gob-modal-overlay` on `document.body`. `showModal` hoists `#cut-modal-backdrop` to `body` if it is not already there.
- `html.gob.gob-shell .main .gob-modal-overlay` keeps `position: fixed` and `z-index: var(--z-modal)` so a trapped overlay still paints above the focus top bar.
- POST body unchanged: `{ franchise_id, player_ids }`.

## Other affected pages

**Disabled `data-sfx` (hook now silent):**

- Training `#submit-btn` (`training.html` / `training-shell.js`, `SFX_COMMIT`, starts disabled).
- Shell `#play-now` (`gobShell.js` / FCC, `SFX_ADVANCE`, created `disabled`).
- Any future `data-sfx` + `disabled` / `.is-dead` / `aria-disabled`.

**Legacy `.gob-modal-overlay` that `adoptMain` used to swallow on focus pages:**

- `cut-players.html` `#cut-modal-backdrop` (this bug).
- `training.html` `#auto-train-modal` (same trap if opened on the weekly focus host).

**Already body-appended (were fine):** `gobLeaveConfirm.js`, `usernameModal.js`, `tutorialLineupModals.js`, `gobTutorialNav.js`, FCC/Advance new-season and required-cuts overlays.

## `mode=cut` dead-code note

Week-35 cuts. **No live FE or BE link** opens `/cut-players.html?mode=cut`. Grep hits: `cut-players.js` `isCutMode` only; docs in `Practice_Squad_System.md`. Advance and `buildAssignPracticeSquadUrl` omit `mode`. `POST /franchise/cut-players-final` remains. **Do not delete on this branch** — list for the dead-code sweep: `isCutMode` branch, `submitFinalCuts`, `cut-players-final`, week-35 copy.

## Screenshots (`reports/submit-cuts/`)

| File | What |
|---|---|
| `wrong-count-1280.png` | 0 selected, dead **Assign Practice Squad**, reason Assign 3 more |
| `exact-count-1280.png` | 3 selected, live button |
| `confirm-modal-1280.png` | Confirm Practice Squad on top of focus chrome |
| `landing-1280.png` | FCC after POST, Play Next Game |

## Files

- `FrontEnd/static/js/shared/uiSfx.js`
- `FrontEnd/static/js/shared/gobShell.js`
- `FrontEnd/static/css/gob-shell.css`
- `FrontEnd/static/css/gob-tokens.css` (`--z-modal`)
- `FrontEnd/static/cut-players.html` / `.js` / `.css`
- `FrontEnd/static/resource-pages.css` (disabled cursor)
- `_documentation_master/11_Design_Systems/UX_System.md`
- `tests/e2e/submit-cuts.spec.js`

## Gates

- `../gob-simplified/.venv/bin/python -m pytest --ignore=tests/e2e -q`: **4232 passed**, 14 skipped, 109 xfailed, **1 xpassed**, **0 failed** (246.06s). The xpass is pre-existing.
- Playwright (`env -u CI PORT=8261 BASE_URL=http://localhost:8261`, workers=1, once): **774 passed**, 6 skipped, **0 failed** (12.7m).
- `scripts/check_ui_tokens.py --strict --no-write`: **exit 0**. New colour-law 0 / 0 / 0. Legacy 204 green / 582 orange / 0 reward-gold (786).
- `scripts/ci/check_migration_gates.py`: **passed**. Gate A: 0 imports in 0 files. Gate B: 136 lines in 44 files. Notes: `training.html` / `training-report.html` now clean (0, was 1). Did **not** `--write-allowlist`.
