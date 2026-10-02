# feature/office-week-1 — 2026-10-02

Branch `feature/office-week-1` from `origin/develop` @ `6d569a465` (the `polish/chrome-followups-2` merge). `origin/develop` had not moved at gate time, so the final tree is the code head `8240088e3`. Ready for review.

## What is on the branch

| Commit | What |
|---|---|
| `c7f8c1eed`, `f4b355111` | **Office week 1**: the season preview, and Top Recruits all season |
| `bcea82b6c` | Extra 1: stored news stories are scrubbed of "Clutch" as they are served |
| `2fd524345` | Extra 2: online, the "Coaching archetype evolved" row is marked seen once the Office has shown it |
| `d6742b4a4` | **Progress strip**: a read-only stepper, not a row of buttons |
| `8240088e3` | The flaky Office fit test: made deterministic, asserts the layout under the scroll rule |

## Office week 1

Week 1 of every season, before the first game. From week 2 the Office is as it was, plus Top Recruits. Nothing stored changes for a mid-season franchise; a franchise sitting in week 1 gets the new Office on its next load.

| Column | Section | Status | Notes |
|---|---|---|---|
| 01 | Title "Season Preview" | done | week 1 only |
| | Outlook line | done | "Picked 5th of 8 in Conference A1." From season 2: "Last season: 18-8, lost in the Region semifinal." |
| | Rankings (was "Season preview") | done | Conference "5 of 8", Region "11 of 16", National "100 of 128", all from the preseason national rank |
| | Key Players | done | top 5 by RT; Player, RT, Pos, Yr, Ht, Wt; names open the player page |
| | Newcomers | done, see data notes | last season's class now on the roster + "Returning 9 · Lost 3 seniors · 4 newcomers"; left out in season 1 |
| | Preseason All-Americans | done | first team: position, player, team, RT. No score, weights or percentages. Your players are the navy row |
| 02 | Title "Opening Week" | done | week 1 only |
| | Season Opener | done, see data notes | labelled; "Preseason #21 · Conference A2 · Last season: W 71-64" |
| | Circle these | done | the three toughest by opponent national rank, in week order, with week and home/away |
| | Team snapshot | unchanged | not in the brief; left where it was |
| | Preseason National Rankings | done | the conference's 8 teams by national rank, best first, each with its rank; user row navy |
| 03 | "No preseason leans" | done | week 1 only |
| | Walk-ons | done | week 1 only; "No walk-ons" when there are none |
| | Top Recruits | done | all season; steps aside from Signing Day |

### What defines a walk-on

A franchise player whose `meta.archetype` is the **"Walk On"** sentinel (`walk_on_portraits.is_walk_on_fpd`). The data can identify them, so I did not stop on this item.

The section lists **this season's** walk-ons, which is how "if there are none" can be true (a full signing class leaves no room for any):

| Season | How this season's are known |
|---|---|
| 1 | every walk-on was created with the franchise (three per team), so all of them |
| 2 on | the archetype cannot tell new arrivals from walk-ons who stayed; the rollover's `pending_walk_on_welcome` list names this season's |

Say if "the team's walk-ons" should mean everyone on the roster who ever walked on.

### Data notes: one change outside the Office code

The season rollover wipes three things the preview needs: the user's results (for "met last season"), the seniors who leave (for "Lost 3 seniors"), and the week-35 signing results (for the class's player ids). None of it existed anywhere after the reset.

- `finish_season` now stores one small `last_season` snapshot on the franchise, built by `season_preview.last_season_snapshot`. It is one guarded block and one key in the reset's `$set`; a failure is logged and the rollover carries on. Not sim, finalize, `cpu_week_pool` or `sim_rng`. **Say if you would rather this lived somewhere else.**
- **A save that rolled over before this ships** has no snapshot. For its current season:
  - last season's record and finish still show (they come from the coach's season-record trophy);
  - Newcomers still shows (the class is matched by name from the season review);
  - "Lost N seniors" and the opener's "Last season: W 71-64" are left out, not guessed.
- From its next rollover every save has all of it.

### Server

| File | What |
|---|---|
| `BackEnd/utils/season_preview.py` (new) | pure builders for every section, Top Recruits, and the rollover snapshot. No database access, no attributes read |
| `BackEnd/api/franchise_routes.py` | `_office_preview_blocks`: the reads (one projected roster read and, from season 2, the coach's trophies, in week 1 only; one projected recruit read in weeks 1-34). The rollover snapshot. A failed read leaves that block out and the Office still loads |
| `BackEnd/utils/office_digest.py` | carries `season_preview` (week 1) and `top_recruits`; "No preseason leans" |

Online and offline both: the reads go through the collections the routes file already uses, and a test runs them on mongomock and SQLite.

### Client

- `officeHome.js`, `office-home.css`. No new card style: the lists share the signing-class card's rules (two-line rows, grade on the right) under `.office-list`, and Key Players and the rankings table use the standings row.
- Navy for "yours"; RT as a letter in the canonical ramp (`rtBucket.js`); no decorative green, orange or gold.
- One payload paints the whole Office, so no section is half-built. Until it arrives the Office shows its skeleton. A preview whose reads failed (`ready: false`) paints none of its sections.
- `franchise-command-center.css` unchanged at 1779 lines.
- **CH**: the preview reads no attributes and the All-American rows carry no score. A spec checks no "CH", "Clutch" or percentage is drawn.

### Past the fold (px each column runs past the window)

| View | 1280×720: col 01 / 02 / 03 | 1920×1080: col 01 / 02 / 03 |
|---|---|---|
| Season 1, week 1 | 185 / 219 / 0 | 124 / 146 / 0 |
| Later season, week 1 (adds Newcomers) | 428 / 219 / 0 | 470 / 146 / 0 |
| Week 2 | 0 / 196 / 0 | 0 / 74 / 0 |

Week 2's column 02 is the standings card from the last branch, unchanged. Shots below show both the window and the whole Office.

### Rows per section

Five or fewer everywhere, except Preseason National Rankings, which is the conference's eight teams as specified.

## The progress strip is read-only

| # | Item | Status |
|---|---|---|
| 1 | No click, hover or keyboard behaviour; not focusable, not links; default cursor | **done** |
| 2 | A quiet stepper: state mark + plain text, joined by a thin line; no pill outline or fill; neutral only | **done** |
| 3 | A list, the current step `aria-current="step"` | **done** |
| 4 | Every state checked | **done**: regular week, invite week, week 1 camp, tournament, Signing Day, offseason |
| 5 | Tests; the old outlined-step tests updated | **done** |

**What the steps used to do, now removed.** They were `<button>`s with a click handler:

| Step | Used to | Now |
|---|---|---|
| The Advance step (the one that mirrors the top bar: "Play Next Game", "Run Training Camp", …) | press the top-bar action button, so it advanced the week | nothing; it still shows the top bar's label |
| Every other step ("Run training", "Review recruit invites", "Resume training", …), done or not | open the step's page (`todo.route`: Training, Recruiting, …) | nothing |

So "Review recruit invites" in the strip no longer opens Recruiting. The top bar's own "Edit Recruit Invites" button and the Recruiting rail item still do.

- Markup: `<ol class="week-track">` of `<li class="wk-step">`; no handler, no `tabindex`, no role. A done step carries a hidden "(done)" for a screen reader.
- Look: done = a check, dimmed; current = the mark filled, the label bold white; upcoming = dim. A step that blocks the advance is the current step and reads the same (it had a strong outline before). The steps sit further apart, joined by a hairline.
- Tests (`office-strip-readonly.spec.js`, 9): in each of the six states the track is an `ol` of `li` with no button, link, input, `tabindex`, role or `href` inside; Chrome reports **no event listeners** on the strip or any step; no outline, fill or border; default cursor; painted colours neutral; at most one `aria-current`; click, double click, Enter and Space on every step cause no navigation and no press of the action button; 40 Tabs never land in the strip. One more: the mirrored step does nothing and the top-bar button does. 7 of 9 fail on the old strip (the two shot tests pass).
- Updated: `office-frontend.spec.js` ("advance mirror" and "week strip states" no longer expect a step to navigate or to be a pill) and `jamie-rulings-batch-2.spec.js` (the blocking step has no outline).

## The flaky fit test (`office-frontend.spec.js`, "six states fit")

- **Not a layout fault.** On Signing Day at 1280 the middle column is exactly as tall as its content (619 / 619px) once the page is at rest. The 3-4px "clip" appeared only while the arrival animation was running: it moves the cards with a transform, and a column's `scrollHeight` counts that. The test's settle check watched rounded card edges, which look still a few frames before the animation ends, so the result depended on timing.
- **Deterministic now.** The settle wait also waits for the Office's finite animations to finish (capped at 4s).
- **What it asserts under the scroll rule**, at 1280, 1440 and 1920, in all six states: no sideways scroll (page and main); every column as tall as what it holds; no card ending below its column; no card cutting its own content off; one vertical scroll at 1280; and the standings card showing all eight rows. "Fits the fold" is gone from it. Renamed "six states lay out cleanly at 1280, 1440 and 1920".
- Run alone: `--repeat-each=10` with 1 worker, **10 of 10 passed**; again with 5 workers, **10 of 10 passed**.

## Extra 1: stored news says "Clutch"

- Scrubbed as a story is served, by the response class every franchise route already renders through, so any route that returns a stored story is covered. The stored story is not rewritten (a test reads it back unchanged).
- "Shooting and Clutch" → "Shooting"; "Scoring, Clutch, and Passing" → "Scoring and Passing"; "His strongest gains were in Clutch." → the sentence is dropped, the ones around it stay.
- Only attribute lists are touched (the "strongest gains were in" clause, or two or more attribute names in a row). "Clutch free throws sealed it", "in clutch time" and the sim callouts are left alone; tested.

## Extra 2: the archetype row online

- Same rule as offline: on the authoritative read, with the Office on screen, the client sends `PATCH /api/auth/archetype-evolution-seen`. A visit that lands on another tab leaves the row for the next Office visit.
- **One thing I had to add.** The account route does not move the franchise's `browse_rev`, so the next Office read would have been a 304 of the cached body that still had the row. The client now drops its cached Office body when it sends the write. The test serves real ETags and 304s; without the drop the row comes back.

## Tests

| Area | Covered by | On old code |
|---|---|---|
| Week-1 server | `tests/test_season_preview.py` (24): every builder; the digest in week 1, season 1, week 2, weeks 34-36; a stale snapshot ignored; the reads on mongomock and SQLite, local and online coach; a real new franchise through the real route (week 1, then week 2); no hidden key, score or weight in any block | fail (no module) |
| Week-1 client | `tests/e2e/office-week-1.spec.js` (10): season 1 week 1 (every section, order, content, links, navy rows, RT ramp classes, columns aligned, ≤5 rows); a later season (last season line, Newcomers and its summary, last meeting, a loss, a title); week 2 (normal Office + Top Recruits, no week-1 section); Signing Day and after; empty states; preview not ready; skeleton while loading; no CH; shots and fold at 1280 and 1920 with no overlap and no sideways scroll | 7 of 10 fail; the two shot tests and "steps aside" pass |
| Extra 1 | `tests/test_hidden_attrs.py` (+4): the four old-shape lines; the ordinary word untouched; the name list matches the copy's; a stored old story served through `/franchise/news` and unchanged in the save | fail |
| Extra 2 | `polish-chrome-followups-2.spec.js` G1: online, one account write, row gone on later visits, the next read is not a revalidation; a non-Office visit sends nothing; offline unchanged | online tests fail |

Existing tests updated: `tests/test_office_digest.py` (it asserted the old week-1 placeholder fields), `office-frontend.spec.js` (its week-1 fixture is now the real payload shape; the wire line), `helpers/officeFixtures.js` (week-1 preview and Top Recruits blocks), `polish-chrome-followups-2.spec.js` (the standings test no longer includes week 1, which shows the rankings table instead).

## Shots (`reports/office-week-1/`, 1280 and 1920)

| View | The window | The whole Office |
|---|---|---|
| Season 1, week 1 | `season-1-week-1-after-…` | `season-1-week-1-full-after-…` |
| A later season, week 1 | `later-season-week-1-after-…` | `later-season-week-1-full-after-…` |
| Week 2 | `week-2-after-…` | `week-2-full-after-…` |
| The strip, a regular week | `strip-regular-week-after-…` | close-up: `strip-regular-week-close-after-…` |
| The strip, an invite week | `strip-invite-week-after-…` | close-up: `strip-invite-week-close-after-…` |

`…-before-…` are the same views on develop's Office files; the strip's before shots are on the commit before it. `fold-after-1280.json` / `-1920.json` hold the fold numbers above.

## Questions

1. **Walk-ons**: this season's arrivals (as built), or everyone on the roster who walked on?
2. **"4 newcomers"** counts the signing class on the roster. Walk-ons are not counted there and not in "Returning" either (they have their own section). Count them as newcomers instead?
3. **The rollover snapshot** (`last_season` on the franchise): fine where it is?
4. **Team snapshot in week 1**: kept between Circle these and the rankings table, since the brief did not mention it. Before camp it says "Set after camp". Keep, move or drop?
5. **Last season's finish wording**: "lost in the Region semifinal", "missed the bracket", "won the National championship". A region or conference champion who lost later reads by where they lost. Right?
6. **Scores**: "18-8" and "W 71-64" use a hyphen, as in your brief; the next-game card's record elsewhere uses an en dash ("11–8"). One or the other?
7. **Later seasons at 1280×720**: column 01 runs 428px past the fold with all five sections. Fine, or should a section give way?

## Not acted on

**1.** A pasted note arrived mid-task describing a change to the Team snapshot's "Moved most" list (rank only the eight signed-scale measures; exclude chemistry, Shooting and Rebounding). It reads as another agent's notes rather than a brief: it has no request, and the "two cases" it refers to were not included. Nothing was done for it. Send the brief if it is meant for this branch.

**2.** A brief about the Training Report top (a five-step readiness meter, "Lagging" in camp and "Falling" in season, keep the "Notes" heading, then run the Training Report specs). That work is on `origin/polish/training-report-top`, another agent's branch; none of it (the meter, `training-report-top.spec.js`) exists in this worktree or on this branch. Nothing was done for it. It looks meant for the agent on that branch.

## Gates (final tree `8240088e3`; `origin/develop` @ `6d569a465` is its base, nothing to merge)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | 4413 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed. Both XPASS are pre-existing; `known_failures.py` not edited. |
| `check_ui_tokens.py --strict --no-write` | exit 0 |
| `check_migration_gates.py` | passed (Gate A 0, Gate B 134 lines / 43 files) |
| `franchise-command-center.css` | 1779 lines, unchanged |
| Full Playwright (lock held 16:38-16:58, 1 worker) | 1076 passed, 21 skipped, **1 failed**: `first-paint.spec.js:111` "the page loader is opaque › court pre-game". Re-run alone `--repeat-each=5`: **fails 5 of 5** (the other three pages in that block pass). |

**That failure is not from this branch.** With this branch's three client files put back to develop's (`officeHome.js`, `office-home.css`, `momentQueue.js`) and a server still running develop's code, it fails the same way. This branch does not touch `court.html`, the Phaser client or `first-paint.spec.js`. The test (added on develop at 14:45 today with the opaque page loader) waits 500ms after the court's loader appears and expects it still up; on the court pre-game page it is already gone. For whoever owns the first-paint sweep.

**A lock incident, mine.** When the strip brief arrived I cancelled a queued full run by killing its `sleep` child first. That made its wait loop run `mkdir` once more; the lock happened to be free, so the script took it and was killed before it could set its release trap. The lock sat orphaned from 16:00:13 to 16:38:06 and would have blocked any other agent's full run in that window. I released it once I had worked out it was mine (its creation time matched my kill to the second, and no full suite was running anywhere). My runner now sets its release trap before it waits.

**Full suite: pytest 4413 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed · Playwright 1076 passed, 21 skipped, 1 failed (`first-paint.spec.js:111` court pre-game; fails on develop's code too, 5 of 5 alone).**
