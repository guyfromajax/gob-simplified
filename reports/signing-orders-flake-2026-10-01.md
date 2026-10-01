# signing-orders-panel.spec.js:251 load flake — fix — 2026-10-01

Branch `fix/signing-orders-flake` off `origin/develop`. Test-only. No sim / finalize /
cpu_week_pool / sim_rng / animation-timing changes. The five equivalence specs stay 55/55.

## Symptom
`tests/e2e/signing-orders-panel.spec.js:251` (`deliverable signing frame`) failed once in a
full-suite run (court-3) and passed 5/5 isolated — a load flake.

## Root cause
The test serves the design deliverable
`_documentation_master/projects/Recruiting Hub Deliverables/Recruiting Hub Signing Board.html`
from a throwaway local server and screenshots it. That HTML pulls its runtime from **live
internet**:
- `https://unpkg.com/react@18.3.1/umd/react.development.js`
- `https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js`
- `https://unpkg.com/@babel/standalone@7.29.0/babel.min.js`  (~2.8 MB)
- `https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter…`

The React/Babel tags are **classic, render-blocking `<script src>`** (no async/defer), so the
original `page.goto(url)` (default `waitUntil:'load'`) blocked until those live fetches
finished. Under full-suite machine + network contention that fetch stalls, and the wait is
bounded only by the **180 s test timeout** (`test.describe.configure({ timeout: 180000 })`,
since no `navigationTimeout` is set). When the stall exceeds the budget the test times out.
None of these deps are in `node_modules`, so they can't be routed to a local copy directly.

There is a **second** blocking point behind the first: even once `goto` is switched off
`'load'`, a request that is *still pending* when the `fullPage` screenshot runs hangs the
screenshot too (Playwright waits on in-flight work). So fixing `goto` alone is not enough —
any single live request that outlives the test kills it.

## Reproduction (under load)
Env-gated harness in the test (inert by default): `SIGN_E2E_CDN_DELAY_MS=<ms>` stalls the
external fetch to simulate a contended CDN.

| Run | goto | `SIGN_E2E_CDN_DELAY_MS` | Result |
|---|---|---|---|
| **Before** (original code) | `'load'` | 190000 | **FAIL** — `page.goto: Test timeout of 180000ms exceeded … waiting until "load"` |
| `'commit'` only (insufficient) | `'commit'` | 10000 | pass 17.7 s (render lands at 10.9 s) |
| `'commit'` only (insufficient) | `'commit'` | 190000 | **FAIL** — 180 s timeout; page rendered, but the still-pending request hangs the screenshot |
| **After** (bounded route) | `'commit'` | 190000 | **PASS 21.3 s** |

The middle rows show why `commit` alone is not the fix: the stalled request has to be removed,
not just un-waited-on.

## Fix (test-only)
In the `deliverable signing frame` test, **bound every external request**:
`page.route(/unpkg\.com|fonts\.(googleapis|gstatic)\.com/, …)` races `route.fetch()` against a
15 s budget. If the CDN answers in time → `route.fulfill({ response })` (faithful render); if
not → `route.abort()`. An aborted request is no longer pending, so **nothing live can stall
`goto` or the screenshot**. Added latency is at most one budget window, never the 180 s test
timeout. `goto` is also switched to `waitUntil:'commit'` and a best-effort, soft-caught wait
for the React render (`#root > *`, 20 s) + `networkidle` (5 s) is added before the shot.

The deliverable HTML is **unchanged** (it's a design artifact that intentionally uses the CDN).
When the CDN is reachable the frame still renders fully (verified below); when it stalls the
test still passes with a degraded frame — acceptable, as this test has **no assertions** and
exists only to emit a report screenshot.

## Evidence
- **Before/after under 190 s stall:** FAIL (180 s goto timeout) → **PASS 21.3 s**.
- **Normal (no stall):** PASS 7.9 s; `reports/signing-orders-panel/frame-signing.png` renders
  the full Signing Board faithfully — Bebas Neue heading, Inter body, orange accents,
  green/yellow sign-odds bars, roster + orders rail (1280×1165, 5 225 distinct colours, not
  blank → React loaded through refetch+fulfill with SRI intact).
- **`--repeat-each=10` (normal): 10/10 passed** (14.5 s).
- **`--repeat-each=5` (under 190 s stall): 5/5 passed** (23.1 s) — deterministic under the exact
  failure condition.
- **Full spec (all 4 tests): 4/4 passed** (7.7 s) — the other three tests are untouched.

## Files touched
- `tests/e2e/signing-orders-panel.spec.js` — `deliverable signing frame` test only (+20/−1).

## Gates (`.venv/bin/python`)
- **pytest** `--ignore=tests/e2e -q`: **4298 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (235 s). Identical to develop — the change is a JS-only e2e test, so no Python is touched. The 2 XPASS are pre-existing/known.
- **`check_ui_tokens.py --strict --no-write`**: **exit 0** (no CSS/HTML changed).
- **`check_migration_gates.py`**: **passed** (Gate A 0/0; Gate B 134/43).
- **Full Playwright** (workers=1, port 8000, under `/tmp/gob-full-playwright.lock`, on the
  branch after merging `origin/develop`): **831 passed, 7 skipped, 0 failed** (14.5 m). `:251`
  ran green at [664/838]. The equivalence specs are included in that pass (55/55). Lock
  acquired/released cleanly. (The `[WebServer]` ERROR log lines in the run — invalid-ObjectId
  fixtures, `/api/init-game` negative tests, and the pre-existing `game_id_utils` global-RNG
  leak — are deliberate test fixtures / a known pre-existing issue, not test failures.)

## Unsure / notes
- The 15 s CDN budget is a judgement call — generous for a healthy CDN, far under the 180 s
  test budget. It can be lowered if we want the frame to fail faster to fallback under slow
  networks.
- Same class of live-CDN dependency exists in the other deliverable-frame screenshot tests, if
  any; only `:251` was in scope here.

STATUS: READY FOR REVIEW. Root-caused the live-CDN load flake, reproduced it under a stalled
CDN (180 s goto timeout), fixed it test-only by bounding every external request (serve-or-abort
within 15 s) + `goto('commit')` + soft render wait. 10/10 `--repeat-each` clean, 5/5 under the
stall, normal render faithful. All gates green: pytest 4298 passed / 0 failed, ui-tokens exit 0,
migration passed, full Playwright 831 passed / 0 failed. Committed `ae86fa6f3`, merged
`origin/develop`, pushed `fix/signing-orders-flake`.
