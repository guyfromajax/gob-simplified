# recruiting-tabs flake: `:415` week-21 focus flow, `:479` browse-hub Leans sync (2026-10-01)

**Status: ready for review.** Branch `fix/recruiting-tabs-flake`, pushed. Test-only. No product file changed.

## Read this first

- I found and fixed **one real race, in the test, shared by exactly these two tests**.
- I did **not** reproduce the symptom as reported ("page shows only ← Back to Locker Room"). The unmodified spec passed 160/160 for me under load. So "10/10 after the fix" does not by itself prove the reported flake is gone. The evidence that discriminates is the injected-delay experiment below.
- No product race found.

## Root cause (test)

Both tests check back/forward restore with:

```
await page.goto('/login.html');
await page.goBack();
await page.waitForSelector('#hub-pool .pool-view');
```

`/login.html` is not a neutral page. With a token it calls `/api/auth/me` and then sets `location.href = '/mode-select.html'`.

| When the redirect lands | History | `goBack()` goes to | Result |
|---|---|---|---|
| Before login's `load` event (the usual case) | redirect **replaces** the login entry | recruiting | pass |
| After `load`, and Back is issued first | login is unloaded before it redirects | recruiting | pass |
| After `load`, and the redirect commits before Back | redirect **adds** an entry | login, which redirects to Home Base again | hub never returns; `waitForSelector` runs to the test timeout |

No other test in the file leaves via login, and no other test in the file was reported flaky. The same pattern is in `tests/e2e/shell-1b.spec.js:449`; I left it (not in the brief).

## Evidence

Temporary probe in the old spec (removed before commit): delay the stubbed `/api/auth/me` by D ms, pause P ms on login before Back, log the URL before and after Back.

| D (auth delay) | P (pause) | URL before Back | URL after Back | Result |
|---|---|---|---|---|
| 0 | 0, 300, 1500 | mode-select | recruiting | pass ×3 |
| 400 | 0, 200 | login | recruiting | pass ×2 |
| **400** | **1000** | **mode-select** | **login**, then mode-select | **fail**: `waitForSelector('#hub-pool .pool-view')` hit the test timeout; page snapshot is Home Base |
| 1200, 2500 | 0, 200, 1000 | login | recruiting | pass ×6 |

With D = 120 ms and CPU load, 6 of 40 runs resolved `goto` on `login.html` (redirect after `load`); all 40 still passed because Back went out first. So the failing window is real but narrow on this machine.

What does not match the report: my reproduced failure ends on **Home Base**, not on a recruiting page with only the back link. I could not produce that page state by any means:

| Attempt on the unmodified spec | Result |
|---|---|
| Both tests ×10, 8 workers | 20/20 |
| Both tests ×40, 24 workers | 80/80 |
| Both tests ×10, 7 workers, 28 busy loops | 20/20 |
| Both tests ×20, 7 workers, 42 busy loops, auth delay 120 ms | 40/40 |
| Both tests ×10, 10 workers, 112 busy loops (slowest test 47s of a 120s budget) | 20/20 |
| 3s and 7s delay on `gobShell.js`; 3s on `gobStore.js`, `gobAdvance.js`, `command-center/data` | all pass |

The 7s shell delay passing shows `goto` / `goBack` already wait for the shell scripts (`load` waits for them), so the existing `#hub-phase .pstrip` + not-`gob-pending` wait was sound for fresh loads. The hub itself paints synchronously in one `renderShell()` call after `recruiting-data` resolves: strip, pool toolbar and rows appear together. There is no state where the strip exists and the pool rows do not.

## Change (`tests/e2e/recruiting-tabs.spec.js` only)

| Change | Why |
|---|---|
| `leaveAndComeBack(page)`: `goto('about:blank')` → `goBack()` → `toHaveURL(hubUrl)` → `hubReady` → first pool row | `about:blank` has no script and no server, so it cannot navigate on its own. The URL assertion fails fast and names the page if Back ever lands elsewhere. |
| `hubReady(page)`: phase strip present, `html.gob-shell` present, `gob-pending` gone | One readiness definition for fresh loads and Back. Adds "shell mounted" so "not pending" cannot pass before the shell exists. Not shown to be needed today (see the 7s result); it costs nothing. |
| Both tests call `leaveAndComeBack` instead of login + Back + `.pool-view` | The fix. |

No fixed waits were in the spec before and none were added.

## Proof

On the final tree (`22e628193`, develop `cbb3ebdac` merged in):

| Run | Result |
|---|---|
| week-21 focus flow, `--repeat-each=10 --workers=1` | **10/10**, exit 0 (25.5s) |
| browse-hub Leans sync, `--repeat-each=10 --workers=1` | **10/10**, exit 0 (13.5s) |

Before the laptop crash, on `a969aefdb` + the same change: 10/10 and 10/10 at one worker, and 20/20 at 7 workers, all three with 112–140 busy loops running.

## Gates (all on `22e628193`)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | exit 0. **4298 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (238s) |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** (no pipe). New-surface hits 0 / 0 / 0. |
| `scripts/ci/check_migration_gates.py` | **exit 0**. Gate A 0 / 0; Gate B 134 lines / 43 files. |
| Full Playwright, one run under `/tmp/gob-full-playwright.lock`, `--workers=1`, `CI` unset, port 8017 | exit 0. **803 passed, 7 skipped, 0 failed** of 810 (12.6m). Lock taken 10:52:44, released 11:05:22. |
| Failure re-runs at `--repeat-each=5` | none needed |

Not strictly foreground: the foreground limit is 10 minutes and the suite takes about 12.6, so it ran as one tracked job that took and released the lock itself while I blocked on it.

XPASS (unchanged, not from this work): `test_leaders_view_scope_filters_to_user_conference`, `test_settings_loaded_and_applied_to_gameplay`.

## Things that went wrong on my side

- **I left about 140 CPU busy loops running for roughly 25 minutes.** My load-test commands started them and tried to kill them with `kill $pids`; zsh does not word-split, so nothing was killed. Load average reached 155 while you were using the machine. I found and killed them before the first full Playwright run. The crash came later, during that run; I cannot say whether the earlier load contributed. The post-crash runs used no load helpers.
- The pre-crash full Playwright run was lost with the reboot (output and lock both in `/tmp`). The run above replaces it.
- Develop moved twice during the task (`dd931bab4`, `cbb3ebdac`). I committed the fix and merged develop before the final gates, so the numbers are for the tree that would merge. No conflicts.

## Open

- **If `:415` still flakes after this merges, the cause is something I did not find.** The next step is to keep the failing run's `test-results/…/error-context.md` and the error line; the gob-ux artifacts from the original sighting were already gone.
- `tests/e2e/shell-1b.spec.js:449` has the same login-then-Back step.
- `tests/e2e/zz-tb-debug.spec.js` is still in the worktree (my earlier scratch file, comments only, untracked; `rm` is denied to me).
- About 255 tracked `reports/**` images show as modified from Playwright runs. Not committed; `git checkout -- reports/` restores them.

## Files

- `tests/e2e/recruiting-tabs.spec.js`
- `reports/recruiting-tabs-flake-2026-10-01.md`
