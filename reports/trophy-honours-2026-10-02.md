# Trophy Case honours, preseason week line, two checks — 2026-10-02

Branch `polish/trophy-honours`, from `origin/develop` de38092ae (contains the `feature/all-conference` merge). Develop had not moved when the gates started; it moved while the full suite ran (b0ed947d4, `polish/office-grid-followups`), which merges cleanly and touches no file this branch touches, so I did not re-run for it. Final tree: 72afd028e plus this report.

**Status: ready for review.** Items 1 and 2 built; items 3 and 4 checked and answered below (one fix came out of 3, none out of 4). One thing for you at the end.

| # | Item | Result |
|---|---|---|
| 1 | Trophy Case draws All-American and All-Conference entries | Done: an Honours shelf |
| 2 | No "Week 1" line under the preseason stories | Done |
| 3 | Week 13 vs "After week 9" in the real-save shot | The test, not the product. The projection cannot lag a real player. Shot re-taken from one save. |
| 4 | Can the week close at halftime for a real player? | Not through the app. Only through the harness, or a direct API call. Evidence below. |

## 1. Honours on the Trophy Case

- A new **Honours** shelf between Titles and Milestones, drawn only when the coach's trophy log holds All-American or All-Conference entries. With none, nothing extra: no head, no empty state.
- Each tile is the page's own small tile (the milestones' neutral medal, letter A for All-American, C for All-Conference): the team-level label ("1st Team All-American", "2nd Team All-Conference"), then player · position · program · Season N.
- Order: newest season first; within a season All-American before All-Conference, first team first. The count sits in the section head like the others.
- No new colours: the medal is the milestones' `--text-87`; gold stays on titles alone (tested).
- **Position:** trophy entries did not store it. New All-American and All-Conference entries now carry `position` in `detail`; entries written before this read without it (tested with one).

## 2. Preseason week line

"Preseason …" on a week-1 story now counts as naming its week, so "Preseason All-Americans announced" and "Preseason All-Conference A2 teams" carry no "Week 1" line. A later story that happens to say "preseason" keeps its line (tested).

## 3. "Week 13" over "After week 9"

**It was the test.** The All-Conference spec's `openAwards` stubs the command center with a fixed week-13 payload, and the "real projection" shot fed it the awards response recorded from the scratch save, which is at week 10. Two sources, two weeks.

**The projection cannot lag a real player.** Both projections are rebuilt on the first command-center or Awards read after a week advance, whenever the stored week differs from the completed week (`ensure_projection`, `ensure_conference_projection`). The read runs the handler because the advance bumps `browse_rev`, so the client's ETag no longer matches. Evidence from the real save, read together in one go:

| Read | Says |
|---|---|
| `GET /franchise/state` | week 10, season 1 |
| `GET /franchise/command-center/data` | week 10 |
| `GET /franchise/awards` | All-American "After week 9"; All-Conference "After week 9" |

Week 10 means nine weeks complete: "After week 9" is right. The only way the block could sit behind the week is if the projection code raised on every read (logged, never silent) — no such log line in the engine's output.

**Fix:** the real-projection shot now takes the command center from the same save (`ac-command-center.json`) and asserts the top strip's week and the block's "After week N" agree. `after-awards-all-conference-real-*.png` in this report's folder shows Week 10 over "After week 9".

## 4. Halftime close: real player or harness only?

**Harness only.** Three pieces of evidence, no sim code touched:

1. **The server simulates one quarter per call.** `POST /api/simulate-quarter` runs the quarter in `body.quarter`; `advance_method` ("sim_rest_of_game", "sim_full_game") is metadata for analytics and the bulk-sim flag (`_apply_bulk_sim_metadata`), not a loop. The harness's one call with `quarter: 1` therefore simulated one quarter; the stored game shows `quarter: 2`, clock 0:00 (the next quarter, unstarted), `is_final: false`. I called it "halftime" in the last report; it is the end of the first quarter.
2. **The app loops until the game is final.** `bootGame.js` ("Sim Full Game" / "Sim Rest of Game") posts one quarter at a time and breaks only on `lastSummary.is_final`, incrementing the quarter otherwise (bootGame.js, the `while (true)` loop around line 3110: `if (lastSummary.is_final) break; currentQ += 1;`). Play Quarter is the same, one quarter per click. The week-closing call (`/franchise/complete-week/phase-a`) comes from the end-of-game flow after that.
3. **The harness closes the week itself.** `ws2_loopback_season.py` posts the single quarter, reads the score off that response (`_score_from_sim`) and calls `finish_open_week`, which posts `complete-week` with the scores it chose.

So a player going through the app cannot reach `complete-week` with an unfinished game: nothing in the app posts it before `is_final`. What is true is that the **server does not check**: `CompleteWeekRequest` takes `result: {team1_score, team2_score}` from the caller and writes it, and `complete_week` only logs `is_final` from the game document (`[COMPLETE_WEEK] … is_final=…`), it does not refuse on it. The harness, or any direct API call, can close a week on any score. Whether to add a server-side guard is yours to call (below); it is not something a player can trigger from the UI.

## Questions for Jamie

1. **Server guard on `complete-week`?** It trusts the caller's scores and does not require the user's game to be final. The app never sends it early; the harness does. Say if you want the server to refuse a week close while the user's game is not final (that would also make the harness play games out, which would slow its seasons).

## Things to know

| Topic | Note |
|---|---|
| Trophy entries | `detail.position` is new on entries written from now on. Nothing is backfilled. |
| Spec shots | `all-conference.spec.js` now takes `AC_SHOTS_DIR`, so this report's real shot did not overwrite the earlier report's. Its `AC_AWARDS_DIR` run also expects `ac-command-center.json` beside the awards file when present. |
| One pytest fix | `test_all_conference_trophies_and_career_tags_sit_beside_all_american` was the "wobble" I could not name last time: its both-teams check used Birch, whose All-Conference second-team seat depends on the seeded coin (the franchise id is random in tests). It now uses Alder, first team either way. |
| Scratch season | The private offline engine on port 8791 with its scratch save, read only this time. Stopped. Nothing touched staging or production. |
| Not edited | Sim, `court.html`, the top strip, the Office, Training files. |

## Files

| Area | Files |
|---|---|
| 1 | `js/shared/trophyCase.js`, `css/trophy-case.css`, `BackEnd/utils/trophy_log.py` (`_player_detail`) |
| 2 | `js/shared/views/newsView.js` |
| 3 | `tests/e2e/all-conference.spec.js` (same-save command center, `AC_SHOTS_DIR`) |
| Docs | `End_Of_Season_System.md`, `News_System.md` |
| Tests | New `tests/e2e/trophy-honours.spec.js`; `tests/test_trophy_log.py` (position on new entries); `tests/e2e/news-followups.spec.js` (week-line rows); `tests/test_all_american.py` (the deterministic both-teams check) |

## Tests

New tests against the code before this branch (product files stashed, then restored): 4 trophy-log tests fail; the two Honours e2e tests and the "Week N" table fail. The "no honours" test passes on both, by design.

Gates on the final tree (72afd028e = branch on `origin/develop` de38092ae):

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | 4477 passed, 14 skipped, 108 xfailed, 2 xpassed. No FAILED / ERROR. (A first run had the one All-Conference test fail by the coin; fixed and re-run clean, see Things to know.) |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 |
| `scripts/ci/check_migration_gates.py` | exit 0 |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | 1237 tests: 1191 passed, 46 skipped, **0 failed** (24.4 min). Nothing to re-run. |

The two XPASS are the same two as before, outside this branch's area. The known-failures list is untouched.

## Shots

`reports/trophy-honours/`, at 1280 and 1920: `after-honours` (the shelf, four entries including one without a position), `after-awards-all-conference-real` (item 3: Week 10 over "After week 9").

## Left behind

- `reports/trophy-honours/after-awards-all-conference-projected-*.png` and `-final-*.png`: the All-Conference spec's fixture shots, regenerated here by the same run. Untracked and not committed (they are the earlier report's shots). Deleting files is blocked for me here.
- `tests/e2e/zz-tl-debug.spec.js`: my scratch spec, untracked and uncommitted.
