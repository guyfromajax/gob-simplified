# Suite green — 2026-09-27

Branch `test/suite-green` off `develop` (`b048cc926`). Workers=1, `CI` unset, `desktop-*.spec.js` ignored by `playwright.config.js`. Port 8010 for the develop baseline (8000 left free). No product changes. No sim, `cpu_week_pool`, `sim_rng`, or finalize edits.

`fcc-invite-step` and `fcc-recruiting-buttons` passed on this develop tip. They were already fixed by `ux/recruit-pool-grid`.

## Develop baseline

`474 passed`, `7 failed`, `1 skipped`, `3 did not run` (7.5m). The three that did not run are the rest of `depth-ordering.spec.js` (serial mode after the boot timeout): merged pairs, ball stays above every player, headshot mask.

The one skip is `tests/e2e/t3-detail.spec.js` “compact header sits under the title on the offline save”: `test.skip(!up, 'offline loopback is not running')`. `reports/office-frontend/live-digest.json` is present, so the office digest case ran.

## Classification

| Test | Class | Cause | Action | Commit |
|---|---|---|---|---|
| `depth-ordering.spec.js:61` GATE flag OFF | ENV | `boot()` opened `http://localhost:8000/depth-harness.html` while the suite was on 8010, so `__HARNESS_READY` never arrived | Open `/depth-harness.html` on `baseURL`. The other three cases in the file then run | `a719d98f6` |
| `fcc-roster-tab.spec.js:52` column order | STALE | `5a585b349` added DEV FOCUS after the attribute tiles (the evidence, then the coaching call). Spec still expected 7 headers | Expect 8 headers, last label DEV FOCUS, and keep the Player–WT prefix | `17013336e` |
| `fcc-roster-tab.spec.js:60` sort keys | STALE | Same column carries `data-sort-col="Focus"`. The grouped attribute cell still has no sort key | Expect the key list to end in Focus. Keep the 12 attribute controls | `17013336e` |
| `franchise-context-commit-params.spec.js:119` timeout path | STALE | `11b62d0cf` strips `quarter_break_from` on set-lineup load so Back cannot replay the break. `a6ad2d6d4` classifies the court return from `lineup_checkpoint` when that marker was dropped. Durable flags (`resume_from_timeout`, `resume_from_anchor`, `locked_exhausted_user_lineup`) were still present | Assert the marker is null on the lineup page and on the court return, and that the durable flags and `lineup_checkpoint` survive. `commitParams` still clears them without a document load | `5bac44cff` |
| `franchise-context-commit-params.spec.js:166` quarter-break path | STALE | Same strip. A live quarter return is `lineup_checkpoint`, not a `play_quarter` marker left on the lineup URL | Same contract: marker is null, checkpoint stays, `commitParams` still clears it in place | `5bac44cff` |
| `homepage-v3-auth.spec.js:30` redirect | STALE | `a0ea3d36d` kept `homepage-v3.html` as a marketing page. The sibling cases in this file already load it and pass | Assert the URL stays `homepage-v3.html`, it does not go to login, and the hero logo is visible | `e2c8db28e` |
| `season-advance.spec.js:113` modal before the request | STALE | The proceed handler moved to `gobAdvance.js` (`53ed664c3`). The spec still sliced `franchise-command-center.js` up to `/franchise/play-next-game`, so `closeModal()` was not in the window | Assert against `gobAdvance.js`: `closeModal()` precedes the finish-season helper; the no-seniors path raises the cover before `await startFinishSeason()`; the tribute path starts finish-season in the background and raises the cover only while that request is still pending; no `finally` removes the cover | `bc9977e50` |
| `t2-roster.spec.js:239` roster navigate (not in the develop seven; failed on a later full run) | FLAKY | Passed alone and on one full run, then failed. The team-section click leaves the pointer on the rail. At 1280 the face overlays `.main` (64 → 200). A sampled `page.mouse.click` sometimes hit the face, so Player Stats never activated. Switching to `locator.click()` then waited out the whole 180s test timeout, because the face kept intercepting the tab | Park the pointer off the rail and wait until the face width is back to the column width, then `locator.click()`. Re-ran the case 5× alone (pass) and once with the face held open at ≥190px (pass). No sleep, no retry | `aef98758b` |

## Real bugs

None. Nothing here touches gameplay, sim, results, stats, recruiting mechanics, or saves.

## desktop-*

`tests/e2e/desktop-play-flow.spec.js` (one case), run once on port 8014 against the suite’s mongomock server, with `testIgnore` cleared for that invocation only.

Failed: `POST /franchise/select-team` returned `{"detail":"Not authenticated"}`. The spec is the desktop SQLite profile (`GOB_BUILD_PROFILE=desktop`). The default harness is the web mongomock server, which is why `playwright.config.js` ignores `desktop-*.spec.js`. Not trivially stale. Left excluded. Not edited.

## After

Both runs are `workers=1`, `CI` unset, `desktop-*` ignored, on `aef98758b`.

| Run | Port | Result | Duration |
|---|---|---|---|
| 1 | 8030 | 484 passed, 0 failed, 1 skipped | 12.1m |
| 2 | 8032 | 484 passed, 0 failed, 1 skipped | 11.6m |

The skip is the same offline-loopback case, with the reason in the spec.

Running the suite is noted in `_documentation_master/11_Design_Systems/UX_System.md` §8 (`8d5115e14`).

STATUS: COMPLETE
