# Jamie rulings batch 2: 2026-10-01

Jamie approved every recommendation in `reports/jamie-decisions-2-2026-10-01.md`.

- **Branch:** `ux/jamie-rulings-batch-2`, from `origin/develop` `486705fe5`, in `~/gob-audit`; upstream unset.
- **Merge:** develop `cbf135d0e` (token hygiene) was merged before the full run, with two conflicts resolved (below).
- **Scope:** visual only. No logic, data, API, auth or id change. `cut-players.js` changes only CSS classes: the accent modifier, and an `is-neutral` class on Stay.

**Net rule (written in Styleguide and UX_System): orange = "there are unsaved changes" and nothing else.**

## What changed, per ruling

| # | Ruling | Change | Before → after (computed) |
|---|---|---|---|
| 1 | ▲ green on data chips, ▼ neutral | `--delta-down` → `--text-87` (`gob-tokens.css`). `.chip.down` (`gob-components.css`), `.attr-chip.down` / `.attr-chip-val.down` (`box-score.css`), `.gob-chg .is-down i` (`gob-tables.css`) neutral. The recruiting-wire ▼ (`.wr.dn .wr-tag`) rule deleted, so it falls back to the neutral base. `.chip.up` annotated `positive-data`. Dead `.attr-chip .arr` rules deleted (`office-home.css`; no emitter). | Office ▼ chip `rgb(255,109,109)` → neutral; wire ▼ red → neutral; box-score ▼ value red → neutral; ▲ stays `rgb(52,236,39)` |
| 2 | W/L in tables | `.gob-wl` (`gob-tables.css`): WIN `--white-90` plate with `--bg` ink, LOSS `--white-40` outline. Rankings "Last Week" and Team › Schedule share the class. Dead `.wl.win` / `.wl.loss` deleted (`gob-components.css`). | WIN green text → white plate; LOSS red text → outline |
| 3a | Rail count badge | `--badge` → `--white-90`; `--badge-ink` unchanged (dark). The urgent pulse uses `--badge`, so it is white too. | `rgb(247,148,32)` → white plate |
| 3b | `.td-gate`, `.is-on` | `.td-gate` and `.todo.gated` (`gob-components.css`), `.hub-anchor--orders.is-on` (`recruiting-signing.css`), `.fg-pick.is-on` (`gob-advanced.css`) neutral. Off the checker's orange allow-list. | tag orange → `--text-87` and `--white-40` ring; orders tab and advanced pick orange tint → white tint |
| 3c | Office blocking step | `.wk-step.gated` uses a `--white-62` 1.5px outline and a `--white-6` fill. | orange ring → white-62 ring |
| 3d | Attitude bars | `em_20_39` becomes `color-mix(--red 55%, --white-18)`, giving red / muted red / neutral / green-mix / green. | `rgb(247,148,32)` → muted red |
| 3e | Modal accent default | `.gob-modal-accent` default in `resource-pages.css` → `rgba(255,255,255,.14)`. The `auth-bar.css` mirror already was. | Trim Your Roster accent orange → neutral |
| 3f | Tutorial alert | No change (already neutral); now guarded. | neutral → neutral |
| 3g | "Stay" | `cut-players.js` passes `neutral: true`, which adds `.is-neutral`. `cut-players.css` adds `body.cut-players-page .gob-modal-btn-primary.is-neutral` (white plate). | `rgb(247,148,32)` → white plate |
| 4 | No team wash | Every `.office-res` rule deleted (`gob-components.css` ×10, `office-home.css` ×1). No code creates `.office-res`; the weekly card `.wkc` was already neutral. | no stylesheet rule mentions `.office-res` |
| 5 | Red only for irreversible deletes | **Kept red:** Home Base delete program, i.e. the `.pop-i.danger` menu item and the `.btn-del` red-outline confirm (`home-base.css`). **Now neutral:** every Assign Practice Squad accent (leave, confirm, load error; the initial `is-red` in `cut-players.html` and the fallback in `cut-players.js`), and the recruiting dock's remove-invite × (`.islot-remove`, `recruiting-dock.css`; reversible). | cut-players accents `rgb(255,109,109)` → neutral; × red → neutral; delete program unchanged |

**Destructive actions I found:**
- Home Base delete program is the only irreversible delete with a red style.
- Discard in the shared leave-confirm (`GOBLeaveConfirm`) was already neutral.
- The franchise-select "Discard" draft button is a neutral ghost.
- The skeleton / play-builder dev tools use the browser `confirm()`, with no styling.
- Not actions, left as they are: `.brow.dropped` (a recruit-status row tint), `.cut-player-badge.is-ptp` (a playing-time-promise status badge), `.rm-tile--cut` (an advanced-tutorial diagram), and the red error text in the Sammy / username modals.

**"Assign Practice Squad" Confirm stays orange.** It is the commit. The guard checks it stays orange.

## Checker: the orange allow-list

`scripts/check_ui_tokens.py`:
- `SAVE_RE` is now `save | saved | committed | is-saved | is-committed`. Removed: `gob-btn--action`, `toggle-btn`, `gated`, `td-gate`, `is-on`.
- The `.att-col` / `.att-bar` orange mid-stop allowance is removed. Green on those ramps is still allowed.
- Docstring and report text updated.
- `.gob-btn--action:hover` gets the same `/* colour-law: committed */` annotation as its base rule. It is the Assign Practice Squad save, and it was the only other hit the tightening raised.

**What's left.** By selector name, one rule: `.gob-save` (`gob-tables.css`, Player › focus save). By annotation (`committed` / `saved`), all in new-design files:

| Kind | Selectors |
|---|---|
| Real saves / commits | Save Game Plan and its warning save, Save Playbooks (and the `.btn-o` shell variants), `.idock-save`, `.bbtn-save`, `#sign-rail .rail-submit`, `.promise-cell.set .promise-toggle`, `.prow.funded`, `.sb-commit` (Establish program), `.tp-btn-primary` (Save & Continue), `.custom-focus-assign-btn`, `.gob-btn--action` (Assign Practice Squad) |
| **Not obviously "unsaved changes"** (Styleguide Open question 2) | toasts `.hub-toast`, `.toast` (training-playbooks); the choice toggle `.tsr-toggle .toggle-btn.active`; recruiting marks `.pool tbody tr.rec.on-board`, `.pool-rankbadge`, `.citem`, `.hub-anchor--orders .ic` (the orange dot on My Orders, visible in `after-sheet-guards`), `.prow.flash`, `.ssum-lr`, `.ssum-nm b`; `.gob-btn--action` used as a CONTINUE (username modal, Game Plan tutorial CTA) |

These were not in the brief, so they are listed, not changed.

## Docs

- **Styleguide:**
  - Orange row says "there are unsaved changes" and nothing else, and its banned list names the badge, gated tags, `.is-on`, ramps, accents and Stay.
  - Red row allows only data ramps and the irreversible Home Base delete.
  - Team colour row adds the result card.
  - Neutral-by-rule adds ▼, the badge, blocking to-dos, modal accents and Stay.
  - Data scales cover deltas and attitude; Modals, Chips and W/L plates are updated; Never-do has new orange and red lines.
  - New section "Settled 2026-10-01 (batch 2)".
  - Open questions 1–5 are closed. The stale "Save-at-rest is pending audit" phrase went with old #3.
- **UX_System:** colour-law summary updated, plus a new "Settled rulings, batch 2" table (built in / guard). §12 Blocking row neutral; Cut Players line (Stay, accents); shared-chrome modal-accent row; ruling #7's badge note; the Set Lineup line no longer cites the old token comment.
- **`gob-tokens.css`:** the `--orange` comment now says "unsaved changes only: save / commit".
- **Merge with develop `cbf135d0e` (token hygiene):**
  - `gob-tokens.css`: kept develop's new `--you*` aliases and my `--orange` comment.
  - Styleguide: kept develop's Navy and Blue rows with my Orange row, and develop's "Closed mechanically" table before my batch-2 table.
  - Open questions are now two: develop's "one blue or two" and my annotated-orange audit (above).

## Tests

- **New `tests/e2e/jamie-rulings-batch-2.spec.js`** (hosted config, route stubs): 8 tests of computed-style guards, one per surface. Each writes a 1280 shot at scroll 0. The last test loads the sheets into a harness page for rules with no cheap live page: box-score chips, Player › changes, the My Orders tab, the remove-invite ×, and the default accent.
- **Fails on old code:** a scratchpad copy serves the base commit's 13 changed files via `page.route` (soft asserts).
  - 6 tests failed, with every changed guard red. Examples: `Stay is a white plate: rgb(247, 148, 32)`, `badge white plate: rgb(247, 148, 32)`, `no orange attitude stop: … "em_20_39":"rgb(247, 148, 32)"`, `dead .office-res styling is deleted`.
  - 2 passed as they should: the tutorial alert was already neutral, and Home Base delete keeps its red.
  - On the branch: 8 passed, before and after the develop merge.
- **New `test_orange_allow_list_is_save_commit_only`** (`tests/test_check_ui_tokens.py`): fails against the old checker (scratch copy: `blocked == set()`), passes now. `test_allow_list_selectors_and_comments` no longer uses gated / `.att-bar` orange / `gob-btn--action` as allowed examples.
- **Overlapping specs**: office-frontend, office-weekly-card, fcc-peel-2, fcc-recruiting-layout, recruiting-button-state, schedule-views, signing-day-hub, team-schedule-columns, submit-cuts, boxscore-practice-squad-tokens, home-base-online, tutorials-fte-tokens and jamie-rulings-batch.
  - First run: 129 passed, 2 failed, both in `office-frontend.spec.js`: "attribute chips group, order, and cap" (1920 row count 3 vs 5) and "six states fit" (`2.0000152 <= 2`).
  - With `--repeat-each=5`, those two failed in parallel and passed **10/10 with `--workers=1`**.
  - **The same tests fail the same way on the base commit** (a scratch worktree at `486705fe5`: count 3, `2.0000305`). They are pre-existing, load-sensitive flakes: the 1920 count is read with a non-waiting `count()` while the fit logic trims rows. They are not caused by this change.

## Gates

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` (merged tree) | **4313 passed**, 14 skipped, 108 xfailed, 2 xpassed (the same two as before), **0 failed** (220s) |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 (no pipe), before and after the merge; new-surface colour-law hits 0 |
| `scripts/ci/check_migration_gates.py` | passed. Gate A 0/0, Gate B 134 lines in 43 files |
| Full Playwright under the lock (17:01:01–17:06:12, merged tree) | default **843 passed, 1 failed, 7 skipped** (3.9m); desktop config **17 passed** |
| The 1 failure, alone with `--repeat-each=5` | `player-stats.spec.js:166` "player cell matches the roster row": **5/5 failed** (row 46px vs roster 44px). **Not this branch:** it fails 3/3 on develop `cbf135d0e` itself and passes 3/3 on my pre-merge base `486705fe5`, so the token-hygiene merge introduced it. That merge touched `gob-buttons.css`, `gob-tokens.css`, `rt-buckets.css`, `rtBucket.js`, `recruiting-spine.css` and two Phaser utils; the RT files are the likely cause (unverified). Not fixed here (out of scope). |

## Shots

`reports/jamie-rulings-batch-2/{before,after}-<name>-1280.png`, scroll 0, 1280×720:

| Shot | Rulings |
|---|---|
| `office` | #1 (Moved most ▼, wire ▼), #3a, #3b tag, #3c, #3d, #4 |
| `rankings` | #2 |
| `modal-accent` | #3e (Trim Your Roster) |
| `stay` | #3g, #5 (leave accent) |
| `cut-confirm` | #5 (confirm accent; Confirm stays orange) |
| `delete-program` | #5 (kept red) |
| `tutorial-alert` | #3f (unchanged) |
| `advanced-pick` | #3b `.fg-pick.is-on` |
| `sheet-guards` | #1 box-score / Player chips, #3b orders tab, #5 remove ×, #3e default accent |

## Unsure / for Jamie

- The annotated orange list above (Styleguide Open question 2).
- `--delta-down` is now neutral at the token level, so any future use of it is neutral too. ▲ green comes only from `--delta-up`.
- The `.is-red` modal accent in `resource-pages.css` now has no users; I kept it as the opt-in for a future irreversible-delete modal.
- **Develop regression to fix separately:** `player-stats.spec.js` "player cell matches the roster row" is red on develop since token hygiene (see Gates).
- A scratch git worktree at `486705fe5` (detached), used for the base-commit flake check, is still registered at the session scratchpad path (`…/scratchpad/jrb2/basewt`). Removing it was denied; `git worktree remove --force <path>` clears it.
