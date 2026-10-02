# News follow-ups and first-paint fixes — 2026-10-02

Branch `polish/news-followups`, from `origin/develop` 6d569a465.

**The base did not contain the `polish/team-page-links` merge when I started.** I did items 6–9 first, then asked; on your answer I merged `origin/polish/team-page-links` (a394f056c) into this branch (1abc51d92) and did items 1–5 on top. Develop has since taken that merge itself (d6f8418b5). I merged `origin/develop` twice more as it moved, both without conflicts: ff7f60885 (e7196507c) and 1d8be6c67 (19b857bae). Final tree: 19b857bae. Develop moved a third time while the last suite ran (665fce713, `polish/play-cmd-scale`); it merges cleanly and touches no file this branch touches, and I stopped chasing there.

**Status: ready for review.** All nine items done. One item was not what the brief described (5): details below. Three questions at the end.

| # | Item | Status |
|---|---|---|
| 1 | Score caption hides the formula | Done |
| 2 | Upset Report: "Box Score" link per line | Done |
| 3 | No "Week N" line under a headline that names the week | Done; types listed below |
| 4 | Stored "picked on ratings" scrubbed on read | Done |
| 5 | Rail items from drill-ins | Done; the dead clicks were elsewhere than reported |
| 6 | Playbook report first paint | Done |
| 7 | Cut players first paint | Done |
| 8 | Box score with no game | Done |
| 9 | Stale offline Awards test | Done |

## 1. Score caption

| Story | Before | Now |
|---|---|---|
| Weekly Recruiting Report | "Score adds up the ratings of the recruits leaning toward a team: a first choice counts in full, a second choice half, a third a quarter." | "Class strength so far" |
| Season Recruiting Results | "Score adds up the ratings of the recruits a team signed." | "Class strength" (question 1) |

No other news copy explains how a score is built: I read every story builder (upset, practice-squad all-stars and results, recruiting movement, walk-ons, All-Americans). The Score column itself stays.

## 2. Upset Report links

- Each upset line now stores its game when the story is written, and the page draws "Box Score" after it. The link opens the game as a read: the closed-game guard is skipped and Back returns to the story.
- A story stored before this has no stored games and shows no link.
- **How the game is found.** Result rows carry no game id, so the writer looks up the week's stored games once, and only in a week that has an upset. It is a read. If it fails, the story is written without links. No sim, finalize logic, `cpu_week_pool` or `sim_rng` change.
- **Real data.** One more week played on the real offline save: the week-9 Upset Report has four lines, all four with their game. On desktop and web the first link opened that game (Amarillo Tech 61 @ Bayou District 65, two CPU teams) and Back returned to the story.

## 3. "Week N" line

The rule is now by reason, not by type: no "Week N" line under a headline that already names the story's week.

| Story type | Headline | "Week N" line |
|---|---|---|
| Recruiting Report | "Week 9 Recruiting Report" | Gone (already) |
| **Upset Report** | "Week 9 Upset Report" | **Gone** |
| **Practice Squad Game Results** | "Week 4 Practice Squad Game Results" | **Gone** |
| **Projected All-Americans, weeks 7 / 13 / 19** | "Projected All-Americans: week 7" | **Gone** |
| Preseason All-Americans | "Preseason All-Americans announced" | Kept |
| Projected All-Americans, week 26 | "…: end of the regular season" | Kept |
| Practice Squad All-Stars, Your Recruiting Board Moved, Walk Ons, Recruiting Results, Updated Recruiting Leans | no week in the headline | Kept |

The three in bold are the types this branch changed.

## 4. "Picked on ratings"

`GET /franchise/news` replaces the old sentence with "named before a game has been played" on the way out. The stored story is not rewritten (a test reads the store after the request and finds the old sentence still there). The news feed is the only place a story body reaches the client; the Office gets headlines only.

## 5. The rail from drill-ins

**What I found is not what I told you last time.** From a team or player page inside the app, every rail item already worked, the Office included. My note ("the rail's Office does nothing") was wrong: I misread the code and had not clicked it. Sorry for the false lead.

I then clicked every rail item from every kind of drill-in. The dead clicks were these:

| Drill-in | Dead item (before) | Now |
|---|---|---|
| A team page (from the Office, from Standings) | None | All five work |
| A player page (from the roster, from the Office) | None | All five work |
| A news story | News (fixed on the last branch) | All five work |
| **A box score opened to read** | **League** (the lit item) | All five work |
| **A practice-squad roster page** | **Team** (the lit item) | All five work |

Rule now: every rail item leaves a drill-in, the lit one too, and lands on the section itself with nothing carried along. On a section's own page the lit item still does nothing. Recruiting from a drill-in opens the recruiting page.

## 6, 7, 8. First paint

| Screen | Before | Now |
|---|---|---|
| Playbook report | Bare "Playbook Settings / Offense / Motion" heads, then "Set Plays" jumped 148px, "Zone" 42px, and three heads appeared | Held behind the shared loader until the playbook is drawn. A test records every frame the page is on show: it always has its rows, and every head is already where it ends up. |
| Cut players, nothing to cut | "Assign Practice Squad" heading and table shell, then replaced by "No Cuts Required" | Held behind the shared loader until the roster and the cut count are in. No frame shows the page without the modal over it. |
| Box score with no game | Bare "Quarter Scoring / Player Of The Game / Player Stats" heads and "Away Team 0 @ Home Team 0" | One card: "This box score could not be opened. The game was not found." The back button stays and works. |

- All three use the shared page-loader hold (`html.is-loading`), as the Training Report and Training Playbook do. No new skeleton styles. The box score's card is one small tokenised rule set in `box-score.css`.
- A failed load still lifts the loader on both held pages (tested).
- **Box score, one more case.** A game id whose data cannot be loaded showed the same bare page; it now shows the same card. A game that loads and then hits an error part-way through drawing keeps what it drew, as before (an existing spec depends on that).

Seven gates added to `tests/e2e/first-paint.spec.js`.

## 9. Offline Awards test

`desktop-gallery-fixes.spec.js` "#10/#6 empty state: awards" is now "#10/#6 awards: the week-1 preseason projection, not an empty card": heading "Projected All-Americans", status "Preseason", three teams of five in PG–C order, columns Pos / Player / Yr / Team / RT, no empty card. Run with `playwright.desktop.config.js` against a fresh throwaway save: 10 of 10 pass.

The shared offline test save (`/tmp/gob-desktop-e2e.sqlite`) already held two franchises from other sessions, so the spec could not create its own there ("You already have 2 active franchises"). I pointed it at a fresh file with `GOB_DESKTOP_E2E_SQLITE`. Someone should clear the shared one.

## Questions for Jamie

1. **Results caption.** You gave "Class strength so far" for the weekly report. The end-of-season Recruiting Results story had its own explaining line; I made it "Class strength". Say if you want different words.
2. **Week 26 All-Americans.** "Projected All-Americans: end of the regular season" keeps "Week 26" under it, because the headline does not say the week number. Drop it there too?
3. **Box score card copy.** "This box score could not be opened. The game was not found." Change the words if you like.

## Things to know

| Topic | Note |
|---|---|
| Branch base | Explained at the top. The branch now sits on develop ff7f60885, which has the team-page-links merge. |
| Week completion | Item 2 adds one read (the week's stored games) to the news builder, only in weeks with an upset. Story text and content only. |
| Old stories | Upset Reports stored before this: no links. Recruiting Reports stored with the explaining caption: none exist outside my test save (that code never reached staging before this branch). |
| Desktop, pre-existing | After Back from a box score on the desktop build, the page URL keeps a few absorbed parameters (`game_id`, `mode`, `return_url`). They are dropped on the next tab change since the last branch. |
| CH | Not displayed or sent by anything here. |
| Not edited | `court.html`, the top strip, `officeHome.js`, `office-home.css`, Training and Training Report files. |
| Scratch season | The private offline engine on port 8791 with its scratch save. Stopped. Nothing touched staging or production. |

## Files

| Item | Files |
|---|---|
| 1 | `BackEnd/utils/recruiting_report_news.py` |
| 2 | `BackEnd/api/franchise_routes.py` (upset builder, `_week_game_ids`), `js/shared/newsStory.js` |
| 3 | `js/shared/views/newsView.js` |
| 4 | `BackEnd/utils/all_american.py`, `BackEnd/api/franchise_routes.py` (news route) |
| 5 | `js/shared/gobShell.js` |
| 6 | `playbook-report.html`, `playbook-report.js`, `playbook-report.css` |
| 7 | `cut-players.html`, `cut-players.js`, `cut-players.css` |
| 8 | `box-score.js`, `box-score.css` |
| Docs | `News_System.md`, `UX_System.md`, `End_Of_Season_System.md` |
| New tests | `tests/e2e/news-followups.spec.js`, fixture `upset-report-real-stories.json` (recorded from the real offline season) |
| Updated tests | `first-paint.spec.js` (7 added), `desktop-gallery-fixes.spec.js`, `recruiting-report-story.spec.js`, `test_franchise_news.py`, `test_all_american.py`, `test_recruiting_report_news.py` |

## Tests

New tests against the code before each change (product files stashed, then restored):

| Items | On old code |
|---|---|
| 1–5 | 10 pytest tests fail. In `news-followups.spec.js`: the Upset link test, the "Week N" test, and the rail tests for the box score and the practice-squad roster fail. The rail tests for team and player pages pass on old code: that behaviour already worked. |
| 6–8 | 5 of the 7 new first-paint gates fail; the two "a failed load still lifts the loader" tests pass on both, by design. |

Gates on the final merged tree (19b857bae = branch + `origin/develop` 1d8be6c67):

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | 4448 passed, 14 skipped, 108 xfailed, 2 xpassed. No FAILED / ERROR. |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 |
| `scripts/ci/check_migration_gates.py` | exit 0 (Gate A 0 imports; Gate B 133 lines in 43 files). It notes one fewer URL read in `newsView.js`; the allow-list was not tightened (that needs your approval). |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | 1206 tests: 1165 passed, 41 skipped, **0 failed** (21.5 min). Nothing to re-run. |
| `playwright.desktop.config.js`, `desktop-gallery-fixes.spec.js` | 10 passed, against a fresh throwaway save |

The previous merged tree (e7196507c, develop ff7f60885) also ran the full suite clean: 1167 tests, 1132 passed, 35 skipped, 0 failed.

The two XPASS are the same two as on the earlier branches, outside this branch's area (`test_leaders_view_scope_filters_to_user_conference`, `test_settings_loaded_and_applied_to_gameplay`). The known-failures list is untouched. Of the 41 skips, 2 are my scratch spec and 29 belong to the training-report and training-playbooks specs (their own gating).

## Shots

`reports/news-followups/`, each at 1280 and 1920.

| Item | Files |
|---|---|
| 1 | `after-recruiting-report-caption` |
| 2 | `after-upset-report` (real week-9 story), `after-upset-report-stored-without-games` (real week-8 story) |
| 6 | `after-playbook-report` |
| 7 | `after-cut-players-no-cuts` |
| 8 | `after-box-score-no-game` |

## Left behind

- `tests/e2e/zz-tl-debug.spec.js`: my scratch spec, untracked and uncommitted (it skips itself). Deleting files is blocked for me here.
