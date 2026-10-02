# Training follow-ups (2026-10-02)

Branch `polish/training-followups`, cut from `origin/develop` at `6ef3d58df` (Merge polish/training-playbooks). Worktree `~/gob-followups`.

## What changed

| # | Item | Change | File |
|---|---|---|---|
| 1 | Training Report, non-camp weeks: exactly 0 is a dash | `describeTrainingChange()` returns the dash for `n === 0` before the camp / in-season split. No threshold moved. | `FrontEnd/static/training-report.js` |
| 2 | Press/Traps tab title | "HC Traps" → "Half-Court Traps" (static page and shell template) | `FrontEnd/static/playbooks.html`, `FrontEnd/static/playbooks.js` |

"Custom Playbook": untouched. No CSS change needed (the dash reuses `.change-zero`, `--text-38`).

## Item 1 by view (in season, change exactly 0)

| View | Before | After |
|---|---|---|
| Player Report, Training Changes | ▲ (neutral, boxed) | – (grey, no box) |
| Playbook Summary | ▲ | – |
| Player Report, Attributes (+/-) | no mark | no mark (unchanged; already skipped 0) |
| Team Report | "No change" | "No change" (unchanged; same text as camp) |

Unchanged: −0.5 ≤ n < 0 and 0 < n < 1 still read one up; every other band as before.

## Tests

`tests/e2e/polish-training-playbooks.spec.js`:

| Test | Assertion added / changed |
|---|---|
| R2 in-season | the 0 row is `–` in `--text-38` (was ▲ neutral); −0.3 still ▲; Team Report "Shooting" (0) has no arrow |
| R2 camp | dash now asserted with its colour too |
| R3 Attributes | 0 cell: no `is-delta`, no tooltip |
| R4 Playbook Summary | every Defense row (no change) is `–` in `--text-38`; Offense still has ▲ |
| P2 tabs | section title is "Half-Court Traps" |

Fail-on-old check (source reverted, tests kept): R2 in-season, R4 and P2 fail; restored, all pass.

## Results

| Check | Result |
|---|---|
| Playwright: polish-training-playbooks, training-report-no-recruiting, prep-modules-report, prep-modules-playbooks, prep-modules-training, player-training-followup, training-advance-focus | 72 passed, 11 skipped (before-shot blocks), 0 failed |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 |
| `scripts/ci/check_migration_gates.py` | exit 0 (Gate A 0, Gate B 134 lines / 43 files) |
| Full pytest (default config) | `4313 passed, 14 skipped, 108 xfailed, 2 xpassed, 4206 warnings in 231.38s (0:03:51)`; no FAILED / ERROR |

No full Playwright run (per brief). Specs ran on `PORT=8137` so they could not collide with another agent's `:8000`.

## Shots (1280)

- `reports/training-followups/after-training-report-zero-dash-1280.png`: Player Report, Training Changes, week 12; the 0 row is a dash.
- `reports/training-followups/after-half-court-traps-1280.png`: Playbooks, Press/Traps tab.

## Unsure / for Jamie

| Item | Detail |
|---|---|
| Styleguide is now stale | `Styleguide.md` "Training movement marks" still says "In season there is no dash: 0 and dips to −0.5 read as one up". Not edited: outside the brief's file list. Suggested line: "Exactly 0 is a dash in every week. In season, dips to −0.5 (other than 0) read as one up (holding)." |
| Team Report at 0 | Shows "No change", camp and in season alike, never an arrow. Left as is ("same as camp weeks"). Say if it should be a literal dash. |
| "HC Traps" elsewhere | Still "HC Traps" in `playbook-report.html`, `court.html`, `box-score.js`, `set-lineup.js`: not in the brief. |
| Rows with no entry | Players with no change entry already showed a dash; unchanged. |
| Report + shots committed | Follows `acac0f243`; CLAUDE.md says reports stay untracked. |
| Worktree left dirty | Running the specs regenerated ~54 tracked PNGs under other `reports/*` folders and an untracked `reports/prep-modules-playbooks/`. None staged or committed. `git restore reports/` in `~/gob-followups` clears the tracked ones. |
| 2 XPASS in pytest | One each in `tests/test_resource_page_scoping.py` and `tests/test_settings_application_to_gameplay.py`. This branch touches no Python, so they are not from this change; `known_failures.py` not edited. |
| Server log noise | `init_game` logs `InvalidDocument: key was None` during the Set Lineup test (L1); test passes; untouched code. |
