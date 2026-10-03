# Training bar gap — 2026-10-03

Branch `polish/training-bar-gap`, new worktree `~/gob-training-bar-gap`, from `origin/develop` `60c77d1a0`. Develop did not move during the task (checked before pytest and again after the Playwright run), so there was nothing to merge.

## Status

| Page | Flush bar? | What was done |
|---|---|---|
| Training (weekly), in season and training camp | **Yes**: the buttons touched the top strip's bottom edge (0px) | **Fixed**: the bar sits `--space-10` (10px) below the strip |
| Training Report | No: its pinned header already leaves 10px, on the solid page fill | Nothing changed; pinned by a test |
| Custom Playbook | No: no bar against the strip; the page card starts 12px below it | Nothing changed; pinned by a test |

## One thing the brief assumed that is not so

- The brief says the gap must hold "while the bar is pinned during scroll". On develop the Training bar is **not pinned**: it scrolls away with the page. Only the Training Report's header pins.
- I asked. Jamie's answer: **gap only, the bar still scrolls away.** So no pinning was added and Training scrolls exactly as before.
- Because the bar is not pinned, there is no gap for content to show through on Training. On the Training Report, where the header is pinned, the test checks the gap is filled by the header's own opaque background.

## What changed

- `FrontEnd/static/training.css`: the focus-host rule `html.gob-focus #training-view .training-header` gets `padding-top: var(--space-10)` (was 0). One rule serves in season and camp. It is the same token and the same space the Training Report's header uses.
- The in-app Prep › Training tab is untouched (that rule is focus-only; the tab hides this header).
- `_documentation_master/11_Design_Systems/UX_System.md`: one sentence recording the space on both focus hosts.
- `tests/e2e/training-bar-gap.spec.js` (new).
- No server, sim, finalize, cpu_week_pool or sim_rng change. `franchise-command-center.css` not touched (1779 lines).

## Shots (`reports/training-bar-gap/`, each at 1280 and 1920, before and after)

| What | At rest | Scrolled |
|---|---|---|
| Training, in season | `*-training-season-rest` | `*-training-season-scrolled` (bar has left with the page, as before) |
| Training, training camp | `*-training-camp-rest` | `*-training-camp-scrolled` |
| Training Report | `*-report-rest` | `*-report-scrolled` (header pinned, gap kept) |
| Custom Playbook | `*-custom-playbook-rest` | `*-custom-playbook-scrolled` |

The Report and Custom Playbook before/after pairs are the same picture: nothing changed there.

## Tests

| Test (each at 1280 and 1920) | Checks |
|---|---|
| Training, in season / training camp | `--space-10` is 10px; every control in the bar (Back, Tutorial, Points/Focus, Auto-Train, Submit) clears the strip by at least that, the tallest by exactly that; the buttons stay on one line; the bar is still unpinned and scrolls away |
| Training Report | Title and button clear the strip by the token at rest and scrolled, at the same position; the header is pinned at the strip's edge; the gap is covered by the header itself with an opaque background |
| Custom Playbook | The first thing under the strip clears it by at least the token; no pinned bar |

- Fail-on-old-code (`training.css` reverted): the **4 Training tests fail** (gap 0, expected at least 10). The 4 Report and Custom Playbook tests pass on old code by design: they record that those pages were already right.
- Neighbouring specs (v3-training, prep-modules-training, polish-training-playbooks, player-training-followup, training-advance-focus, polish-prep-plan, first-paint, training-report-top) with the new spec: 165 passed.

## Gates (final tree = this branch on `origin/develop` `60c77d1a0`)

| Gate | Result |
|---|---|
| `git fetch` + merge `origin/develop` | Already up to date (`60c77d1a0`) |
| `pytest --ignore=tests/e2e -q` | **4524 passed, 14 skipped, 108 xfailed, 2 xpassed**. No `FAILED` / `ERROR`. |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** |
| `scripts/ci/check_migration_gates.py` | **passed** (Gate A 0; Gate B 133 lines in 43 files) |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | **1285 passed, 56 skipped, 1 failed** (6.7 min). The failure is `standalone-roster.spec.js:11` (the roster redirect race seen on the last branch too; not a training file). Re-run alone `--repeat-each=5`: **5 passed**. |

- The 2 XPASS are the two already on the known-failures list; the list was not edited.
- The migration gates still print the note that `newsView.js` fell 3 → 2 on develop (`--write-allowlist` not run).

## Unsure / for Jamie

1. The gap is 10px to match the Training Report. If you want more air, `--space-12` or `--space-16` is a one-token change.
2. `standalone-roster.spec.js:11` has now failed once in two consecutive full runs and passed every time alone. It may deserve its own flake fix.
