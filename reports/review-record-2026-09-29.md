# Live review record + milestone-modal nits — 2026-09-29

Branch `fix/review-record-and-mm-nits` off `origin/develop` (season peak already merged). Two follow-ups: the live season review now carries the same W–L / conference place as the stored Trophy Case review, and three milestone-modal nits from PR 4.

## 1. Live review record

`season_review_payload` now calls `season_record_detail` — the same helper `record_season_record_trophy` stores on the `season_record` trophy — instead of `season_review_snapshot` alone. One code path: wins, losses, `conf_finish`, `furthest_round`, then the snapshot fields.

Titles on the live review come from the season's title trophies (`title_trophies_for_season`: coach trophy log, this franchise + current season, `TITLE_TROPHY_KINDS`). `momentQueue` passes `titleTrophies: data.titles` and no longer feeds same-visit championship moments into the review. Team colour can still come from those moments.

The live `.rv` already rendered record and conference place when the payload had them. With the fields on the live payload it now headlines **31–5**, **#1 National**, **1st Conference**, matching the stored review. Region seed stays omitted (absent on region brackets; `finishBits` never prints it).

`test_live_review_matches_stored_season_record` (mongomock + SQLite, local + online coach) asserts live payload and stored `season_record.detail` have equal `wins` / `losses` / `conf_finish` for the same franchise and season, and that the live `titles` list is the season's title trophies.

## 2. Milestone-modal nits

- **Queue chrome:** `.mq` (dots and “N of M”) is omitted when the visit has only one moment, same as the frame and the season-peak takeover.
- **Focus ring:** `.mm-f .btn-ghost:focus` clears the browser default; `:focus-visible` uses the design-system ring (`outline: 2px solid var(--white); outline-offset: 2px` — the same token as `.gob button:focus-visible`).
- **Full bracket:** `.mm-f a.lnk` is `text-decoration: none`. The arrow is still `.lnk::after`.

## 3. Frame compare

Previous `compare-*.png` frame halves rendered without CSS because `season-peak.html` links `../../design_handoff_browse_templates/*.css`. This PR served frames from a static server rooted at `_documentation_master/projects` (port 8777) so those relative URLs resolve. `compare-review-1280.png` is live review (right) next to the styled frame (left). Confirmed loaded sheets: `tokens.css`, `components.css`, `templates.css`, `ch7.css`. Frame invents region seed and a five-recruit class; product omits the seed and shows the two signed recruits on the fixture.

## Screenshots

`reports/review-record/`

- `peak-review-1280.png` — live review: 31–5, #1 National, 1st Conference, three title medals, no region seed
- `compare-review-1280.png` — frame (CSS loaded) | live
- `bracket-reveal-single.png` — one-moment visit: no dots / “N of M”; Full bracket not underlined
- `milestone-focus.png` — Next/Done `:focus-visible` ring (2px `var(--white)`, offset 2px), clipped around the button so the ring is visible
- `frame-review-1280.png` — the styled frame half used in the compare (CSS loaded from the projects-root server)

## Tests + gate

- `tests/test_trophy_log.py::test_live_review_matches_stored_season_record`
- `tests/e2e/season-peak-trophy-case.spec.js` — live `.rv-rec` / conference place / titles from trophies not visit championships
- `tests/e2e/milestone-modal.spec.js` — single-moment `.mq` hidden; `.lnk` not underlined; 2px focus-visible ring

**§8 (this run):**

- pytest `--ignore=tests/e2e -q`: **4116 passed**, 16 skipped, 109 xfailed, 1 xpassed, **0 failed**.
- Playwright: full `tests/e2e`, workers=1, `CI` unset, `PORT=8171`, `BASE_URL=http://localhost:8171`: **702 passed**, 3 skipped, **0 failed**.

Did not touch Office weekly (`officeHome.js`, `office-home.css`) or Game Plan (`game-plan.*`, `gamePlanView.js`).

STATUS: COMPLETE
