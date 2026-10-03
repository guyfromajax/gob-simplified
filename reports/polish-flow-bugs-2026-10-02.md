# polish/flow-bugs — 2026-10-02

Branch `polish/flow-bugs` from `origin/develop` @ `b3eb1fb25`. Gates ran on the merged tree `151db65a8` (`origin/develop` @ `3b53ad1ef` merged in). Ready for review.

## Items

| # | Item | Status | Root cause | Fix |
|---|---|---|---|---|
| A1 | FCC stale after a game | **done** | Chrome's HTTP cache answered the season read. Detail below. | `gobStore.js`: every store request is `cache: 'no-store'`. |
| A2 | Championship announcements repeat | **done** | The consume was never sent: the client had no franchise id. Detail below. | `momentQueue.js` reads the id from `FranchiseContext`. Non-winner titles are quiet (server + client). |
| A3 | Recruiting paints the old panel first | **done** | The shell painted the default Pool / Leans / Visits row and search before the hub knew its week. | Row, search and top-bar identity wait for `RecruitingHub.ready()`. First paint is the title and a still skeleton. |

## A1: root cause (proven on a real build, not a mock)

Reproduced on the offline build (SQLite, real engine, real Sim Game): after the game the FCC showed **Week 2 / Play Next Game**; a manual refresh showed **Week 3 / Run Training** and the result. Trace of the returning document:

```
court.html   POST /franchise/complete-week/phase-a -> 200
court.html   POST /franchise/complete-week/phase-b -> 200
franchise-…  DOC start navType=back_forward
franchise-…  GET /franchise/command-center/data  inm=(none)
franchise-…    -> 200 in 0 ms, etag …:1:2:33:…      <- week 2, the court's own read
```

The server log has no `command-center/data` request for that document. Three facts combine:

1. Every exit from a game (`exitFlow`) is `history.go()` back onto the Office entry. The Office is not bfcache-restored here, so it loads as a **back_forward** navigation.
2. On a back_forward load Chrome serves a plain `fetch()` GET from its HTTP cache **without revalidating**, `Cache-Control: no-cache` or not.
3. The phase-a / phase-b writes go through `GOBStore.mutate`, which clears the store's ETag. With no `If-None-Match` to send, the read is a plain GET, and (2) answers it with the body the court page fetched before the game.

Same path for a played game, Sim Game and the sim with highlights off (they all end in the same popup → `exitFlow`), online and offline (same store, same Chromium).

Why the 09-30 fix and its spec missed it: Playwright request routing switches the HTTP cache off, so a mocked spec cannot see this. `polish-flow-bugs.spec.js` A1 starts a real HTTP server for that reason.

After the fix, same walk: `GET … cache=no-store -> 200 in 159 ms, etag …:1:4:71:…`, FCC on **Week 4 / Run Training** with the result card, no refresh.

## A2: root cause

- `GET /franchise/command-center/data` has **no `franchise_id` key**. `momentQueue.js` used `topData.franchise_id || window.franchiseId`; the page's `franchiseId` is a script-scoped `let`, not a window property. Both were undefined, so `dismissOnServer` and every milestone seen-PATCH returned early and nothing was ever consumed. Every title replayed on each Office visit, and the national title rode into the next season.
- The 09-30 spec (`champ-moment-repeat`) mocks the payload **with** `franchise_id`, which hid it. The new spec uses the real shape.
- Not the winner: the queue row is now `style: quiet`, `sting: null` unless a moment has `user_is_winner`. The takeover drops confetti, the sting and the "Added to your Trophy Case" line (that line was false for another team's title). The court's live-game overlay follows the same rule.

## Files

| File | Change |
|---|---|
| `FrontEnd/static/js/shared/gobStore.js` | `cache: 'no-store'` on every store request |
| `FrontEnd/static/js/shared/momentQueue.js` | `franchiseIdOf()` (payload → `FranchiseContext`) |
| `FrontEnd/static/js/shared/seasonPeak.js` | quiet title (`.pk.is-quiet`): no confetti / sting / Trophy Case line; a row with `sting: null` stays silent |
| `FrontEnd/static/js/shared/championshipMoments.js` | court overlay: sting only when `user_is_winner` |
| `BackEnd/utils/moment_queue.py` | championship row quiet + no sting when no moment is the user's |
| `FrontEnd/static/js/shared/gobShell.js`, `recruiting-hub.js` | `RecruitingHub.ready()`; no row before it |
| `FrontEnd/static/recruiting.html`, `recruiting-spine.css` | `.hub-skel` first paint |
| `FrontEnd/static/css/gob-shell.css` | `gob-pending` also hides the top-bar identity |
| `tests/e2e/polish-flow-bugs.spec.js` (new), `tests/e2e/reward-gold-sfx.spec.js`, `tests/test_moment_queue.py` | tests |
| `UX_System.md`, `Styleguide.md` | store rule, quiet title, recruiting first paint |

No change to sim, finalize, `cpu_week_pool`, `sim_rng`, or the frozen FCC sheet.

## Tests

`tests/e2e/polish-flow-bugs.spec.js`, 10 tests. On the old product files: **9 fail, 1 passes** (the one that passes is "the coach's own title still celebrates", which is unchanged behaviour). On the fix: 10 pass.

| Test | Old code |
|---|---|
| A1 season read after a game reaches the server | fails: `Week 5`, expected `Week 6` |
| A2 conference / region / national announced once (reload, next visit, next season) | fail: 0 dismiss requests |
| A2 another team's title: no sting, confetti, Trophy Case | fails |
| A2 milestone marked seen with the context id | fails: 0 requests |
| A3 week 5 / 22 / 35: no row before the hub | fail |

Also: `tests/test_moment_queue.py` (quiet/silent row), `reward-gold-sfx.spec.js` (court overlay silent for a rival title).

## Shots (`reports/polish-flow-bugs/`, 1280)

| Item | Before | After |
|---|---|---|
| A1 | `a1-before-return-after-game-1280.png` (Week 2 after the week-2 game), `a1-before-after-manual-refresh-1280.png` | `a1-after-return-after-game-1280.png` |
| A2 | `a2-before-rival-title-1280.png` | `a2-after-rival-title-1280.png`, `a2-after-own-title-1280.png` |
| A3 | `a3-before-real-build-first-paint-1280.jpg`, `a3-before-loading-week22-1280.png` | `a3-after-real-build-first-paint-1280.jpg`, `a3-after-real-build-hub-1280.jpg`, `a3-after-loading-week{5,22,35}-1280.png` |

## Seen on the way, not fixed (outside the three items)

| Finding | Detail |
|---|---|
| "Coach archetype" pop-up repeats on every Office visit **offline** | Its seen write is `PATCH /api/auth/archetype-reveal-seen`, an always-remote route, while offline the flag is read from the local coach doc. Needs a local seen route; that is a storage decision, so not done here. |
| Sim Game Q4 crash (once in four games) | `AttributeError: 'NoneType' object has no attribute 'player_id'` in `TurnManager._ensure_lineup_fields` during a free throw: a lineup slot was `None`. Engine code, out of scope. The client shows "Simulation Error: Q4 simulation failed". |
| "Trim Your Roster" modal | Its green button sits on the same screen as the green Advance (two greens). |
| Training Report | Leaving before its fetch lands shows an `alert("Failed to load training report")` (the aborted fetch). Owned by ux. |
| Any other API GET on a back_forward load | The same HTTP-cache behaviour applies to GETs outside the store (`/franchise/list`, `/api/auth/me`, …). None of them drive the week, so untouched. A server `Cache-Control: no-store` on API JSON would close it for every caller. |

## Unsure

- A3 also blanks the top-bar record / rank / week until the season data lands on the recruiting page (it painted "NR" for a beat). Say if you would rather keep it.
- A2: I kept the gold rule and medallion on another team's title; only the confetti, sound and Trophy Case line go.

## Gates (merged tree `151db65a8` = branch + `origin/develop` @ `3b53ad1ef`)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | 4314 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed. Both XPASS are pre-existing; `known_failures.py` not edited. |
| `check_ui_tokens.py --strict --no-write` | exit 0 |
| `check_migration_gates.py` | passed (Gate A 0, Gate B 134 lines / 43 files) |
| Full Playwright, once, lock held 10:43-11:02 | **890 passed, 15 skipped, 1 failed** (906 tests, 19.1 min, 1 worker) |

The one failure is environmental, not this branch:

- `tests/e2e/t3-detail.spec.js:625` "compact header sits under the title on the offline save" timed out waiting for `#team-view .gob-roster.is-compact tbody td.rt`.
- The test does not use the suite's server. It opens `http://127.0.0.1:8766/...?franchise_id=6ab284847ab3853ae89a1184`: a fixed loopback port and a hard-coded franchise id. Another agent's desktop loopback is on 8766, and its database has no such franchise.
- Per Jamie it is not re-run. (My `--repeat-each=5` re-run was cut off when the session exited; it would have hit the same loopback.)

Run notes: the first attempt at the full run was lost when the session exited at about 09:34 (at test 82 of 875, no failures to that point). The result above is the second, complete run on the merged tree.
