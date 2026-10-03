# FCC stale return after a game: 2026-09-30

Branch `fix/fcc-stale-return` (worktree `../gob-fccfix`), commit `23b6fc409`, pushed. Ready for review.

## Root cause

The bfcache and marker path in gobNav was not the problem. Every Locker Room exit I traced writes the exit marker and lands fresh. The stale FCC comes from the FCC's own warm-paint cache.

- **Stale cache survives the week advance.** `franchise-command-center.js` saves `topData` to sessionStorage under `fcc-shell:<fid>:<team>`. Only gobStore's franchise-write hook clears that key, and gobStore isn't loaded on court.html, where phase-a and phase-b run. The FCC also re-writes the key from late reads (roster, standings, team-data, schedule). If one of those lands after the play-next-game POST, the pre-game week survives the game.
- **The warm paint drives Advance.** On the next FCC load, the warm paint's `populateTop` set `window.__gobCommandCenterData` and the shell week, and called `updatePlayButton` with the cached data. `#play-now` was also enabled at DOMContentLoaded.
- **A missed first read leaves it live.** If the first read after the advance fails (busy server, or one of today's staging deploy cutovers), `init()` returns early and hides the overlay. The result is Week 25 with a live Play Next Game, which is the reported symptom. Back from Set Lineup then does a fresh load, which is why it looked correct.
- **Second bug found on the way.** `gobStore.js` runs twice on the FCC: authGuard injects it from `<head>` before the page's own `<script>` tag is parsed. The second copy's "native" fetch is the first copy's wrapper, so `GOBStore.revalidate` on the FCC answered from memory and never reached the server. That affects the in-app views (rankings, roster, standings and others) as well.

Not proven: the exact staging trigger. It is either the late write plus a failed first read, or a restore the markers missed. The mock harness can't reproduce staging timing, so test 3 seeds the late-written cache. None of today's merges changed the gobNav exit logic.

## What changed

| File | Change |
|---|---|
| `franchise-command-center.js` | Warm paint (`populateTop(…, {warm:true})`) no longer sets `__gobCommandCenterData`, the shell week, Advance or the edit ghost. `#play-now` stays disabled until authoritative data is applied. The first command-center read retries 1s/2s/4s (not on 401/403/404). A bfcache restore that gobNav didn't already reload revalidates and reloads when the Advance-relevant fields changed. |
| `js/shared/gobNav.js` | `isReloading()`: true once reloadIfStale or consumeExitLanding has scheduled the replacement. |
| `js/shared/gobStore.js` | A second evaluation is a no-op. |
| `tests/e2e/fcc-fresh-after-game.spec.js` | New, 4 tests. A sampler records every Advance the player could press (enabled and on top) during the return; only `Week 26 / Review Recruit Invites` is allowed. |
| `tests/test_gob_nav.js` | New `isReloading` case. |

Behavior notes for review:
- Every bfcache return to the FCC, including peeks, now sends one conditional GET for `command-center/data` (normally a 304).
- The in-app views' `revalidate` now reaches the server as designed, so expect extra 304s.

## Tests

- **New spec `fcc-fresh-after-game`:** 4/4 pass with the fix.
  - With the fix reverted, tests 3 and 4 fail; test 3 shows the staging symptom (stays on Week 25).
  - Tests 1 and 2 (game in week 25 → FCC; recruiting page → game → FCC) pass on old and new code. They cover the path the task named.
  - Test 4 uses a synthetic persisted `pageshow`, because the FCC isn't bfcache-eligible in this harness (Back loads it fresh).
- **Related e2e:** 179 passed, 2 skipped, 2 failed (fcc-*, nav*, office-*, shell-*, store-client, season-advance, t3-detail).
  - `navigation-fixes-3` "a replaced … returns to the lineup" fails on old code too.
  - `office-frontend` "attribute chips group order and cap" fails on old code too.
  - `office-frontend` "standings rows" failed once and passed on both reruns (flake).
- **Node:** `node tests/test_gob_nav.js`: 31 pass.
- **Gates:** `check_migration_gates.py` passed (Gate A 0, Gate B 136 lines / 44 files, unchanged).
- **Full suite:** default config, run once. XPASS: `test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference`, a backend harness test unrelated to this change; I didn't edit `known_failures.py`.

Migration gates: passed.
Full suite: 4225 passed, 20 skipped, 109 xfailed, 1 xpassed, 0 failed.
