# Tutorials / FTE on gob tokens: 2026-10-01

Branch `ux/tutorials-fte-tokens` from `origin/develop` (`9c45db7c2`), in `~/gob-audit`. The tutorial, FTE and Sammy surfaces are now on `gob-tokens.css` and the colour law. Upstream was unset after `checkout -b` (it tracked `origin/develop`). Push is explicit to `origin ux/tutorials-fte-tokens`.

## Decisions (asked, answered)

| Question | Answer |
|---|---|
| Tutorial orange accent | **Neutral per law.** `gob-tutorial.css` is now strict new-design, no longer exempt. |
| Sammy modal CTAs | **Neutral by default; green only by opt-in.** `is-orange` is a no-op. `is-advance` is green, used only by the region-bye "Sim Region First Round" (it runs `#play-now`). |
| Scope | **Chrome only.** Lesson pages' inline teaching diagrams stay legacy (follow-up). |
| `box-score.css:494` red on develop | **Moved the existing annotation** inside the rule. The checker looks back 2 lines; the comment sat 3 above. No colour change. |

## `/css/fte.css`: restored on tokens

- **Reference:** `js/phaser/utils/pgpcSammyReminderModal.js` (`ensureFteStylesheet` loads `/css/fte.css`) is the only one. No other code reference; it appears only in a doc comment in the same file.
- **Cause:** `fa621a753` deleted `fte.css` with the old welcome modals. The pre-press-conference reminder (`gameCompletionPopup.js` → `showPgpcSammyReminderModal`) still uses the `fte-*` classes. Live, it rendered unstyled at the end of `<body>`, invisible at scroll 0 (`before-pgpc-legacy-host-*.png`).
- **Why restore, not remove:** removing the dead reference means editing `pgpcSammyReminderModal.js`, which the brief puts off-limits. A restored sheet fixes it with no JS change.
- **What it is:** a new `css/fte.css` that styles only the classes the reminder uses, as dark Sammy chrome with `var(--token, gob value)` fallbacks, because `court.html` is not `html.gob`. It outranks the module's own light-shell `<style>` (dark label → `--text-60`, orange checkbox `accent-color` → white).
- **Left as is (off-limits file):** the reminder's inline portrait ring is the team primary colour, or `#F79420` with no team colour, set by `style=""` in the JS.

## What changed

- **Pages:** all 15 `tutorial*.html` are `html.gob` and load `css/gob-tokens.css`. Navigation CTAs moved from `gob-btn--action` (orange) to the new `gob-btn--neutral`.
- **`.gob-btn--neutral`** (`gob-buttons.css`): white plate, `--bg` ink, two-class selector so it beats `body.gob-tut a { color: inherit }`.
- **`gob-tutorial.css`** (injected on every auth-bar page, so tokens carry fallbacks):
  - alias layer re-pointed onto tokens;
  - navy-wash page gradient replaced by flat `--bg` (navy is "yours" only);
  - neutral: tick, active nav icon, depth badges (filled vs outline), toast bar/icon, `::selection`, tip kicker/primary, alert rail/mark/portrait ring/num/dots/primary;
  - unused `--blue-*` aliases dropped. `--orange-soft` moved to the two lesson pages whose diagrams use it.
- **`tutorial.html` hub inline chrome:** continue link, progress bar, order circles, seen check, pulse are now neutral.
- **`gob-advanced.css`:** chrome only (list bullets, callout bar/icon/eyebrow, handoff label, focus ring). Diagram colours untouched; sheet stays exempt.
- **Modals and screens, each sheet tokenised:**
  - Sammy modal: primary neutral, input focus neutral.
  - Username: ring and focus neutral; CONTINUE stays orange because it saves.
  - Lineup modal: ring neutral; GOT IT neutral.
  - Attribute tour: band, cue, hover, explored, count, ring, eyebrow, GOT IT neutral.
  - Persona: tokens only.
  - Pick opponent: selected card, rank and check neutral; team rail kept; CONTINUE neutral.
  - Tip-off: ring and eyebrow neutral; SIM GAME stays green (FTE Advance).
  - Walk-on: tokens only.
- **JS (class swaps only):**
  - `attributeTour.js`: GOT IT → `gob-btn--neutral`.
  - `tutorialLineupModals.js`: `action` → `gob-btn--neutral`.
  - `gobTutorialAlertResume.js`: ready state → `gob-btn--neutral`.
  - `regionByeModal.js`: `primaryClass: 'is-advance'` ×2.
- **Checker:** `NEW_DESIGN_CSS` adds sammy-modal, username-modal, walk-on-welcome, attribute-tour, tutorial-lineup-modal, tutorial-persona-intro, tutorial-pick-opponent, tutorial-tipoff and fte. `NEW_SURFACE_EXCLUDE` keeps only `gob-advanced.css`. Docstring and report text updated.
- **Era:** `training.html` and `training-report.html` removed from `scripts/ci/migration_gates_allowlist.json` by hand (not `--write-allowlist`).
- **UX_System:** §8 surface list; new "Tutorials and FTE" section (neutral primary, Sammy CTA rule, fallbacks, `fte.css`, scope).

Not touched: `js/phaser/utils/*`, `pgpcSammyReminderModal.js`, sim/finalize/cpu_week_pool/sim_rng, `franchise-command-center.css`, lesson-page inline diagrams, `coach-mark.css` (`coachMark.js` has no importers).

## Shots

`reports/tutorials-fte-tokens/{before,after}-<surface>-{1280,1920}.png`, via `page.screenshot` after `scrollTo(0,0)`. BEFORE was captured on develop CSS (`TUTORIALS_FTE_BEFORE=1`) before any edit.

Surfaces: `hub`, `advanced`, `alert`, `tip`, `persona`, `opponent-sammy`, `opponent-selected`, `tipoff`, `username`, `lineup-intro`, `attribute-tour`, `pgpc-legacy-host`, `sammy-legacy-host`. The last two are on `/privacy.html`, which is not `.gob`, to prove the fallbacks.

## Tests

- `tests/e2e/tutorials-fte-tokens.spec.js`: shots at 1280 and 1920, plus computed-style guards:
  - pages are `html.gob` with `--text-100` resolving;
  - no orange/green on the chrome above;
  - neutral plates keep dark ink;
  - SIM GAME green; username save orange; `is-advance` green;
  - `fte.css` served, reminder fixed and dark, label readable;
  - team rail kept.
- **Fails on old code:** ran the guards (soft) in a detached `origin/develop` worktree. They fail on every surface (e.g. `tick rgb(247,148,32)`, `sammy GOT IT rgb(52,236,39)`, `/css/fte.css is served`, `fte modal is the dark surface rgba(0,0,0,0)`). Two checks did not fire there (username input focus, opponent card border-top); other guards cover those surfaces.
- `tests/test_check_ui_tokens.py`: exemption test moved to `gob-advanced.css`. New `test_tutorial_chrome_is_new_design` fails on the develop checker and passes on this one.
- **Caught while shooting:** the alert "Start lesson" was white on the new plate (`body.gob-tut a { color: inherit }` won; it was white-on-orange before). Fixed by specificity, with ink guards added.

## Gates

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` | **4298 passed**, 14 skipped, 108 xfailed, 2 xpassed, **0 failed** (248.67s). XPASS: `test_resource_page_scoping::test_leaders_view_scope_filters_to_user_conference` and `test_settings_application_to_gameplay::…::test_settings_loaded_and_applied_to_gameplay` (both also XPASS on the Game Plan branch run; `known_failures.py` not edited). |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0. New-design law hits **0** (was 1 on develop: `box-score.css:494`). |
| `scripts/ci/check_migration_gates.py` | passed. Gate A 0/0. Gate B 134 lines in 43 files, no "now clean" notes. No `--write-allowlist`. |
| Playwright full `tests/e2e --workers=1` under `/tmp/gob-full-playwright.lock` (PORT=8244) | **796 passed, 7 skipped, 0 failed** (12.5m). No failures, so no `--repeat-each=5` reruns. All 3 `tutorials-fte-tokens` tests passed. Skips: 5 existing `test.skip`s plus 2 "handoff frames" tests (Game Plan/Scouting, Playbooks) that skip without `FRAMES_BASE`, which this run did not set. |
| Targeted `tutorials-fte-tokens.spec.js` | 3 passed |

## Unsure / follow-ups

- **Lesson-page inline styles** (`tutorial-recruiting`, `-scouting`, `-playbooks`, `-game-plans`, `-training`, `-team-attributes`, `-player-attributes`): `.crumb .here`, `.handoff .h-l .lbl` and the diagram colours are still orange/green inline (legacy surface, reported, not gated).
- **`pgpcSammyReminderModal.js`:** inline orange ring fallback and the light-shell `<style>` stay. A later pass on that file could drop both, and `fte.css`'s overrides with them.
- **`walk-on-welcome.css` comment** still says "`.is-orange` modifiers": the callers still pass it; it is a no-op now.
- **Generic selectors:** `gob-tutorial.css` is injected app-wide with generic selectors (`.panel`, `.eyebrow`, `.gob-shell`) that can match non-tutorial pages. This was already true before; selectors left unchanged.
- **Temp worktree:** a detached `origin/develop` worktree used for the fails-on-old check is still at `<scratchpad>/old`; `git worktree remove --force` was denied.
