# Orange stragglers: 2026-10-01

Jamie's ruling on the "not obviously unsaved changes" orange list from `reports/jamie-rulings-batch-2-2026-10-01.md` (its Styleguide Open question 2).

- **Branch:** `ux/orange-stragglers`, from `origin/develop` `3dd0b0968`, in `~/gob-audit`; upstream unset.
- **Scope:** visual only. No logic, data, API or id change. JS edits are class names only (`gob-btn--action` → `gob-btn--neutral` on two CTAs).
- **Housekeeping:** the scratch worktree left by batch 2 (`…/scratchpad/jrb2/basewt`) was removed with `git worktree remove --force` (rc 0; `git worktree list` no longer shows it).

## What changed

| Was orange | Now | Where | Before → after (computed) |
|---|---|---|---|
| Recruiting hub toast `.hub-toast` (edge + ✓ icon) | **neutral**, like the shared save toast | `recruiting-dock.css`: edge `--line-strong`; `.ti` `--white-6` fill, `--white-28` ring, `--text-87` ink | edge `rgb(247,148,32)` → neutral; icon orange → neutral |
| Training playbook "Playbooks Saved" `.toast` | **neutral** | `training-playbooks.css`: `--toast-accent: var(--line-strong)` | edge `rgb(247,148,32)` → neutral |
| Training Report stat toggle `.tsr-toggle .toggle-btn.active` | **neutral** (choice control) | `training-squad-report.html`: white 12% fill, white ink | `rgb(247,148,32)` fill → white 12% |
| Invite-board rank badge `.pool-rankbadge` | **navy** | `recruiting-dock.css`: `--you` fill, `--text-100` ink | orange → navy `#27408E` |
| On-board pool row `.pool tbody tr.rec.on-board td` | **navy** | `recruiting-dock.css`: navy 14% (hover 20%) | orange 5% → navy 14% |
| Committed recruit in the Orders rail `.citem` | **navy** | `recruiting-signing.css`: navy 14% fill, `--you-line` border (hover 20%) | orange tint → navy tint |
| My Orders mark `.hub-anchor--orders .ic` | **navy ink** (`--you-ink`) | `recruiting-signing.css` | `rgb(247,148,32)` → navy-tinted white |
| Username modal CONTINUE | **neutral plate** | `usernameModal.js`: `gob-btn gob-btn--neutral` | orange → white plate |
| Game Plan tutorial PLAY NOW | **neutral plate** | `game-plan.js`: `gob-btn gob-btn--neutral gob-btn--lg` | orange → white plate |
| Signing flash `.prow.flash`, summary `.ssum-nm b`, `.ssum-lr` | **kept orange** | unchanged; annotations kept (`committed`, and `saved` on `.ssum-lr`, which the checker treats the same) | orange → orange (guarded) |
| Assign Practice Squad `.gob-btn--action` | **kept orange** (a real save) | unchanged | orange (guarded) |

- **Annotations:** every now-wrong `/* colour-law: committed */` or `saved` annotation on these rules is removed; a short comment says why each is neutral or navy.
- **Comments:** stale comments fixed in `game-plan.html` and `usernameModal.js` (its header said "orange CTA" and "orange accent bar").
- **My Orders mark uses `--you-ink`, not plain `--navy`.** It is a text glyph (◧) on the dark rail, where `#27408E` is barely visible. `--you-ink` is the hub's existing "yours" text colour (`.rsigned-team.mine`, `.sd-tm.is-user .nm`). If you want literal `--navy`, it is a one-token change.

## Every remaining orange in new-design files

From the checker's own scan (`audit_tree`), every declaration that carries orange on a new-design surface and passes the law:

| Selector | File | Kind |
|---|---|---|
| `.gob-btn--action` (+ `:hover`) | `css/gob-buttons.css` | save: Assign Practice Squad |
| `.gob-save` | `css/gob-tables.css` | save: Player › focus save (the only one allowed by selector name) |
| `.btn-save-game-plan`, `.btn-o` (pg-tools / button-container) | `game-plan.css` | save: Save Game Plan (orange only while dirty) |
| `.gameplan-warning-save` | `game-plan.css` | save: the Game Plan warning modal's Save |
| `.playbooks-save-btn`, `.btn-o` / `#save-btn` (pg-tools) | `playbooks.css` | save: Save Playbooks (orange only while dirty) |
| `.idock-save` | `recruiting-dock.css` | save-styled, but **no emitter found** (dead CSS; nothing renders it) |
| `.bbtn-save` | `recruiting-spine.css` | save: Submit Invites (`#dock-save`) |
| `#sign-rail .rail-submit` | `recruiting-signing.css` | commit: Submit Orders |
| `.promise-cell.set .promise-toggle` (+ `.box`) | `recruiting-signing.css` | commit: a set playing-time promise |
| `.prow.funded` (+ `:hover`) | `recruiting-signing.css` | commit: the funded row |
| `.prow.flash` | `recruiting-signing.css` | **just-committed flash** |
| `.ssum-lr` (+ `:hover`), `.ssum-nm b` | `recruiting-signing.css` | **just-committed**: signing summary |
| `.sb-cell.act .btn.sb-commit` | `team-builder.css` | commit: Establish program |
| `.tp-btn-primary` | `training-playbooks.css` | save: Save & Continue |
| `body.training-page .custom-focus-assign-btn` | `training.css` | commit: Assign Focus Attributes |

Nothing else orange is left on the new-design surface. `check_ui_tokens.py --strict` reports 0 new-surface colour-law hits.

## Docs

- **Styleguide:**
  - Navy row gains "on your board / your orders" (rank badge, on-board rows, committed recruits in the Orders rail, the My Orders mark).
  - Orange row adds the Signing Day just-committed moment (`.prow.flash`, `.ssum-nm b`, `.ssum-lr`); its banned list adds "yours" marks and a CONTINUE that only continues.
  - Toasts covers the page-local toasts.
  - New section "Settled 2026-10-01 (orange stragglers)".
  - **Open question 2 closed.** One remains: "one blue or two" from token hygiene.
- **UX_System:** new "Settled rulings, orange stragglers" table (built in / guard). The Tutorials "Orange" line says none; the play-flow table splits Save & Continue (orange) from the toast (neutral).

## Tests

- **New `tests/e2e/orange-stragglers.spec.js`** (hosted config, route stubs): 7 tests of computed-style guards, plus a 1280 shot at scroll 0 for each surface. `OS_PREFIX=before` skips the guards (that is how the before shots were taken, on the untouched tree).
  1. Pool board: badge and on-board row navy.
  2. Signing: `.citem` navy, My Orders mark not orange and navy-tinted, hub toast and icon neutral, and the flash / summary still orange.
  3. Training playbook toast neutral.
  4. Training Report toggle neutral.
  5. Username CONTINUE white plate.
  6. Game Plan tutorial PLAY NOW white plate.
  7. Assign Practice Squad still orange.
- **Fails on old code:** a scratchpad copy serves develop's 7 changed files via `page.route` with soft asserts.
  - **6 failed** with every changed guard red. Examples: `rank badge navy: rgb(247, 148, 32)`, `My Orders dot not orange: rgb(247, 148, 32)`, `CONTINUE white plate: rgb(247, 148, 32)`, `selected toggle neutral: {"backgroundColor":"rgb(247, 148, 32)"…}`.
  - **1 passed**, as it should: Assign Practice Squad stays orange. The kept-orange flash and summary checks also held.
  - On the branch: 7 passed.
- **Changed expectation:** `tutorials-fte-tokens.spec.js` asserted "username save stays orange"; it now asserts CONTINUE is not orange. This was the only failure across the overlapping specs (recruiting-hub-tokens, token-hygiene, play-flow-tokens, shell-2, invite-board, recruits-pool, signing-orders-panel, signing-day-hub, signing-day, prep-modules-gameplan, jamie-rulings-batch-2: 139/140 before the fix; tutorials-fte-tokens 3/3 after).

## Gates (final tree `dcd716a95`; develop `3dd0b0968` merged, already up to date)

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` | **4313 passed**, 14 skipped, 108 xfailed, 2 xpassed (the same two as before), **0 failed** (227s) |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 (no pipe); new-surface colour-law hits 0 |
| `scripts/ci/check_migration_gates.py` | passed. Gate A 0/0, Gate B 134 lines in 43 files |
| Full Playwright under the lock, on `dcd716a95` (17:31:11–17:36:34) | default **850 passed, 1 failed, 7 skipped** (4.1m); desktop config **17 passed** |
| The 1 failure | `player-stats.spec.js:166` "player cell matches the roster row": the **known develop failure** (red on develop since the token-hygiene merge, until stats' fix lands; see `reports/jamie-rulings-batch-2-2026-10-01.md`). Not from this branch, not touched here. No other failure. |

## Shots

`reports/orange-stragglers/{before,after}-<name>-1280.png`, scroll 0, 1280×720:

| Shot | What it shows |
|---|---|
| `pool-board` | Invite Board week 21; the pool is below the fold |
| `pool-board-rows-scrolled` | Labelled extra: scrolled to the on-board pool row, rank badge "1" (orange → navy) |
| `signing` | Week 35: Orders rail `.citem`, My Orders mark |
| `hub-toast` | The hub toast over the signing page (injected with the hub's own markup) |
| `tp-toast` | Training playbook "Playbooks Saved" toast |
| `tsr-toggle` | Training Report Changes / Absolute toggle |
| `username` | Username modal CONTINUE |
| `gameplan-tutorial` | Game Plan tutorial PLAY NOW |
| `cut-submit` | Assign Practice Squad (unchanged, orange) |

## Found, not changed (for Jamie)

- **`.citem-x:hover` turns red** (`recruiting-signing.css`): it removes a recruit from your orders, which is reversible. Batch-2 ruling #5 says red is for irreversible deletes only. My batch-2 report said no other destructive red was left; that missed this one.
- **`.tsr-down` is red** (`#ff6d6d`, `training-squad-report.html`): a ▼ delta on the Training Report. Batch-2 ruling #1 says ▼ is neutral everywhere; my batch-2 grep only covered CSS files and missed this inline style.
- **Toast position (already like this before the change):** the training playbook toast renders at the top-left, partly under the top bar (`tp-toast` shots, before and after alike). Its CSS asks for bottom-right, so something on the page overrides the position. The colour guard is unaffected.
