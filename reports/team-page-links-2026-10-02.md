# Team page links, All-Americans, Recruiting Report, News back, Standings NEXT — 2026-10-02

Branch `polish/team-page-links`, from `origin/develop` 0fe743624 (contains the `polish/tables-followups` merge). Merged `origin/develop` twice, both without conflicts: 71048e175 (merge commit 18eeb7903) and, after develop moved during the first full Playwright run, 6d569a465 (merge commit d8eb14e18). Final tree: d8eb14e18. The gates below are on that tree.

**Status: ready for review.** Seven items, each in its own commit. Nothing skipped. Eight questions at the end. The final Playwright run has two intermittent failures that also fail on plain develop (Tests).

| # | Item | Commit | Status |
|---|---|---|---|
| 1 | Another team's page: completed results open the box score | 4c79f78c8 | Done |
| 2 | Every other plain-text final score: listed, linked where it fits | 4c79f78c8 | Done; one left for you (Upset Report) |
| 3 | All-American formula hidden from the player | a052e6e8c | Done |
| 4 | Recruiting Report: heading removed, teams as sub-headings | 8cf1ee616 | Done |
| 5 | Recruiting Report: layout, team rows, movement, caption, headings | bd6d37fe4 | Done |
| 6 | "← News" lands on the wrong tab; stale navigation parameters | 1875359b9, 3651d1fe8 | Done: cause found, fixed |
| 7 | Standings NEXT: opponent only | 1edcb897d | Done |

## 1. Team page results

On another team's page, each completed result in Schedule › Results is a link to that game's box score. Unplayed games are untouched, and a result whose game is not stored stays plain text.

| | |
|---|---|
| How it is built | The same as the Team › Schedule fix: `data-return`, so the box score opens as a read, the closed-game guard is skipped, and Back returns to that team page. |
| Server | No change. The team page payload already carried `game_id`; the page was not using it. |
| Look | Unchanged at rest: same colour (a loss keeps its quieter grey), no underline, same position to the pixel (tested against the plain version). Hover adds the faint highlight the Team › Schedule result has. |
| Real data | On the real offline save, on Little York's page: the week-3 result (the user's own finished game, the case the guard bounced) and the week-2 result (two CPU teams) both open the box score, desktop and web. Back returns to Little York's page. |

## 2. Other places a final score is plain text

| Surface | What it shows | Result |
|---|---|---|
| League › Rankings, Last Week | "W @ Little York, 63-58" | **Linked.** The result opens the box score; Back returns to Rankings. |
| Office weekly card, headline | A headline that links to the box score | **Fixed.** It lacked the read marker, so it bounced to the Office. Missed in the last fix. |
| News › Upset Report story | "Redwood High upset Pacific All-Stars by a score of 71-66." | **Not linked.** Question 1. |
| Office weekly card scoreboard; League › Schedule cards | The two scores | Unchanged: each already has a working "Box score" link beside it. |
| Player page | No game log (season and career lines, recent training changes) | Nothing to link. |
| Standings | No Last Week column | Nothing to link. |
| Team › Schedule, Tournament bracket, Practice Squads, News game results | Already links | Unchanged. |
| Mode Select highlight cards; milestone and championship modals | Scores | Not touched (off limits). |

- **Rankings:** the rankings payload has no game ids. Rather than add a read to the Office's main request, Rankings reads last week's schedule once the table is up (one cached request) and turns the results into links. Nothing moves when they arrive (tested).
- **Office headline:** the real save's result has no headline, so the test adds one to the recorded payload.

## 3. All-American formula hidden

| Awards page | Before | After |
|---|---|---|
| Under the heading | "After week 12 · Ratings 26% · Stats 70% · Team rank 4% · Updates every week" | "After week 12" |
| Week 26 on | label, weights, "Not final…" | "End of regular season · Not final: tournament play can still change these" |
| Final | "Final. Named after the National Tournament." | "Final" |
| Columns | Pos, Player, Yr, Team, RT, stats, Bonus, Score | Pos, Player, Yr, Team, RT, stats |
| Footnote | "…Score is 0–100 within the position, plus postseason bonus points." | "Stats are per game, regular season." |

Order within each team is still PG, SG, SF, PF, C.

| Server | |
|---|---|
| `GET /franchise/awards` | Status, label, week and the three teams. Each pick is cut to player, team, year, position, rating, games and stat line. No weights, component scores, composite score, rank, bonus, or how the final was built. |
| Stored data | Unchanged, so the engine, `trophy_log.py` and `career_data.py` work as before. |
| Command center | It never carried the projection: `awards_ready` (true / false) only. A test pins that. |
| Real check | The real offline engine's response, for a projection and a final: none of the formula keys. |

**Stories.** The five (weeks 1, 7, 13, 19, 26) are names only, and a test now enforces no percentages, weights, scores or bonus. One sentence stated the basis: the preseason story said the teams were "picked on ratings". It now reads "named before a game has been played" (question 2). The week-26 line about tournament play is unchanged. There is no news story for the final teams; the final is on the Awards page only.

## 4 and 5. Recruiting Report story

| Your point | What shipped |
|---|---|
| "Recruiting Leans Announced" heading | Gone. The two sub-headings stay. |
| Teams and recruits run together | Each team is a sub-heading (logo mark and name, linking to the team page) over its recruits, one per line: name, then RT in the canonical ramp. Stored as structured content (a team block with a list of recruits). |
| "Week N" under the headline | Gone on the Recruiting Report. Other story types keep it (question 7). |
| Use the width | From 1600px National and Region sit side by side and the story takes the page width. Below that they stack as before. The lean sections follow beneath. Checked at 1280, 1599, 1600, 1920, 2048 and 2560: no sideways scroll, no wrapped team name. |
| Team rows | Mark and name in the standard team style, linking to the team page. Your team is the navy "yours" row. |
| Your team outside the top 25 | Its row sits at the foot of the national table with its real rank (on the real save: 80th, in `after-recruiting-report-rankings-*.png`). |
| "Conference A2" | The conference is named as the rest of the app names it. |
| Score caption | "Score adds up the ratings of the recruits leaning toward a team: a first choice counts in full, a second choice half, a third a quarter." Taken from the scorer. Not hidden (question 6). |
| Headings | The app's two heading styles: sections (National Recruit Rankings, Region A, Top Rated…, Conference A2…) at the column-heading level, teams at the smaller card-title level. No bold body text. |
| Rank movement | "▲3" / "▼2" beside the rank, nothing when unchanged, "NEW" when the team was not in last week's table. Neutral both ways, the Office's rank-movement colours. National moves against last week's national table, region against region. Stored with the story. |

**Who appears is unchanged.** A test checks the team blocks name exactly the same teams and recruits, in the same order, as the old lines.

**Recruit names are plain text.** No news story links a recruit today. The block stores the recruit id, so a link can be added later.

**Old stories** (stored before this branch):

| They get | They do not get |
|---|---|
| The side-by-side layout, team links, the "yours" row, the heading styles, no "Week N" line, no outer heading | Team blocks (their lean lines stay plain, as before), movement marks, the caption, the foot row, the "A2" conference name |

Those five are stored with the story, so only new weeks have them. Old lean lines are not upgraded on read: they hold only the RT letter, and colouring from a letter would mean re-mapping the RT ramp in the page, which the frontend rules forbid (question 4).

**"Updated Recruiting Leans Announced".** That separate story is no longer written (leans were merged into the report earlier). Stored ones render as before. Left alone.

**Real data.** Five more weeks played on the real offline save with the new code. The week-9 story is the test fixture and the shots: it has teams that rose, fell, held and are new, and Lancaster at the foot.

## 6. "← News" and stale navigation parameters

**Cause, two parts.**

1. **"← News" was the browser's Back.** It stepped back one history entry, so it landed wherever the reader had been before the story: a team page, the Office, anything.
2. **Tab changes kept every URL parameter.** A tab or section change rebuilt the URL from the current one and only replaced `tab`. So `story`, `view_team_id`, `return_tab` and `origin` from an earlier drill-in rode along forever. That is how the Standings URL still carried `story=w4-recruiting-report`.

**About "opened from the Office".** The Office has no link to a story today. The `return_tab=home-tab&origin=office&view_team_id=…` on the story's URL were leftovers from a team opened from the Office earlier. I reproduced that exact URL.

| Rule | Now |
|---|---|
| "← News" always goes to the feed | Yes. From the feed it steps back onto the feed's own entry, at the reader's scroll. Any other way in, the feed replaces the story, so the browser's Back still returns to where the reader came from. |
| The rail's News always opens the feed | Yes, with a story open and from Awards. It was a no-op inside the section. |
| Browser Back returns to where the reader came from | Yes (Office if they came from the Office). |
| Stale parameters must not hijack either control | A tab or section change drops the drill parameters from the next URL (and from the desktop session store). The entry being left keeps its own, so Back still returns to it. A drill-in keeps the parameters it was opened with. |

**Tests** (`news-back.spec.js`, 8): one per way in (the feed, the Office with the leftovers, a link inside another story, a direct URL), the rail, and parameter clearing on web and on the desktop profile. Six fail on the old code; the two that pass on both check behaviour that was already right.

## 7. Standings NEXT

| | |
|---|---|
| Week label | Gone. |
| Cell | The opponent's mark. Its name sits beside it when the conference card is 760px or wider: yes at 1920 two-up, mark only at 1280 two-up. |
| Tooltip and label | The full name, in every case. |
| Link | To the opponent's page. There was no link before; it is new. |
| No next game | A quiet dash. |
| Sort | NEXT now sorts by opponent name (it sorted by the week, which was the same on every row). |
| Elsewhere | Rankings' Next reads "at Iowa Academy": no week label, no streak beside it. The Office conference card has no next cell. Neither changed. |

## Questions for Jamie

1. **Upset Report links.** Each upset line could carry a "Box Score" link. It needs the story writer to store the game with each line, and that writer runs in week completion. Your Recruiting Report items changed a writer in the same place, so say the word.
2. **Preseason All-American sentence.** Stories already stored keep "picked on ratings". Scrub those on read?
3. **Awards status.** "Updates every week" and "Named after the National Tournament" are gone, per your list. Want either back?
4. **Old Recruiting Report stories.** Their lean lines stay plain. I can upgrade them on read with the team as a sub-heading and the RT letter uncoloured.
5. **Deploy order.** If the server deploys before the frontend, a story written in that gap shows blank lines where the team blocks are until the frontend follows. Deploy together.
6. **Score caption.** It explains the scoring plainly, because lean order and recruit ratings are already on screen in Recruiting. If you want it hidden, the line becomes "Class strength so far".
7. **"Week N" line.** The Upset Report ("Week 3 Upset Report") repeats its week the same way. Remove it there too?
8. **Rail, found on the way.** On a team or player page the rail's Office does nothing (the page counts as the Office section). Not touched; say if you want it to go to the Office.

## Things to know

| Topic | Note |
|---|---|
| Navigation change | Item 6 changes how every tab and section change builds its URL. The navigation, shell, sub-tab and drill-in specs pass. |
| Two flaky tests on develop | The final Playwright run has two intermittent failures that are on develop itself (Tests, below). Their owners should know. |
| Story headings | The heading styles apply to every story type (the All-American stories' "First Team" headings too), not only the Recruiting Report. |
| Week completion | Items 4 and 5 edit the news builders that week completion calls, as directed: text and story content only. No sim, finalize logic, `cpu_week_pool` or `sim_rng` change. |
| Foot row rank | Its place among every team with points. With no points, the durable recruiting rank (the one the Roster shows). The story's table and the durable rank break ties separately; that is not new. |
| Migration gate | Passes. It notes one fewer URL read in `newsView.js`; the allow-list was not tightened (that needs your approval). My first rail fix added a URL read and failed the gate; it now reads the page instead (3651d1fe8). |
| Auth / ownership | Not touched. |
| Awards final shot | The spec's fixture. The save's own final was computed by older code and has the old stored shape. |
| Scratch season | The private offline engine on port 8791 with its scratch save. Stopped. Nothing touched staging or production. |
| Not edited | `court.html`, the top strip, Training and Training Report files. |

## Files

| Item | Files |
|---|---|
| 1, 2 | `views/teamView.js`, `views/rankingsView.js`, `officeHome.js`, `gob-tables.css` |
| 3 | `BackEnd/utils/all_american.py`, `views/awardsView.js`, `gob-views.css` |
| 4, 5 | `BackEnd/api/franchise_routes.py` (news builders), `BackEnd/utils/recruiting_report_news.py`, `newsStory.js`, `views/newsView.js`, `gob-views.css` |
| 6 | `commandCenterTabs.js`, `gobShell.js`, `gobViews.js`, `gobTables.js`, `views/newsView.js` |
| 7 | `gobTables.js`, `views/standingsView.js`, `gob-tables.css` |
| Docs | `UX_System.md`, `End_Of_Season_System.md`, `News_System.md` |
| New tests | `team-page-links.spec.js`, `recruiting-report-story.spec.js`, `news-back.spec.js`, `standings-next.spec.js`; fixtures `team-page-real-results.json`, `recruiting-report-real-stories.json` (recorded from the real offline season) |
| Updated tests | `all-american-awards.spec.js`, `t1-tables.spec.js`, `test_all_american.py`, `test_franchise_news.py`, `test_recruiting_report_news.py` |

## Tests

New tests fail on the old code (product files stashed, then restored), item by item:

| Item | On old code |
|---|---|
| 1, 2 | 5 of 6 in `team-page-links.spec.js` |
| 3 | 11 in `test_all_american.py`; the Awards spec |
| 4, 5 | 15 in the two news pytest files; 5 of 8 in `recruiting-report-story.spec.js` |
| 6 | 6 of 8 in `news-back.spec.js` |

Gates on the final merged tree (d8eb14e18 = branch + `origin/develop` 6d569a465):

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | 4411 passed, 14 skipped, 108 xfailed, 2 xpassed. No FAILED / ERROR. |
| `tests/test_all_american.py` alone | 59 passed |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 |
| `scripts/ci/check_migration_gates.py` | exit 0 (Gate A 0 imports; Gate B 133 lines in 43 files, one fewer than before) |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | 1105 tests: 1080 passed, 23 skipped, **2 failed** (19.6 min). Both are intermittent and fail the same way on plain develop: not from this branch. |

The two failures, each re-run alone with `--repeat-each=5`, on this branch and on develop's own code (develop's `FrontEnd/` and `BackEnd/` checked out over the tree, then restored):

| Test | This branch | Plain develop 6d569a465 | Whose |
|---|---|---|---|
| `first-paint.spec.js:111` "the page loader is opaque › court pre-game" | 3 of 5 fail | 3 of 5 fail | Arrived with `polish/first-paint-sweep`. A court screen: not edited here. |
| `office-frontend.spec.js:581` "six states fit at 1280 and 1920" ("signing_day column 2 clipped" by 3–4px) | 3 of 5 fail; 4 of 10 on a second pass | 1 of 5 fail; 6 of 10 on a second pass | Arrived with `polish/chrome-followups-2` (Office standings shows all 8 teams). Same message both ways. |

Neither failed on this branch before develop moved: the full run on the previous merged tree (3651d1fe8 = branch + develop 71048e175) was 1038 tests, 1017 passed, 21 skipped, 0 failed. I left both for their owners.

The two XPASS are the same two as before, outside this branch's area (`test_leaders_view_scope_filters_to_user_conference`, `test_settings_loaded_and_applied_to_gameplay`). The known-failures list is untouched.

## Shots

`reports/team-page-links/`, at 1280 and 1920 (the rankings also at 2000).

| Item | Files |
|---|---|
| 1 | `after-team-page-results`, `after-box-score-from-team-page` |
| 2 | `after-rankings-last-week` |
| 3 | `after-awards-projection-real` (real response), `after-awards-projection` (fixture, shows your own row), `after-awards-final` (fixture) |
| 4 | `after-recruiting-report` (real story, team blocks), `after-recruiting-report-old-shape` (real story from before) |
| 5 | `after-recruiting-report-rankings` at 1280, 1920 and 2000 (real week-9 story) |
| 7 | `after-standings-next` |

## Left behind

- `tests/e2e/zz-tl-debug.spec.js`: my scratch spec, untracked and uncommitted (it skips itself). Deleting files is blocked for me here.
