# Schedule views — 2026-09-27

## Inventory (schedule.html before this change)

`FrontEnd/static/schedule.html` was the national schedule. Title "National Schedule". It loaded `GET /franchise/command-center/data` and `GET /franchise/schedule/national` and painted every week at once.

Views and filters:

- No week picker. Weeks 1–26, then 27–34, each a card.
- No team filter and no conference filter control. Games were sorted in the page: the user's conference, then the sister conference (`even ? n-1 : n+1`), then conference number, then away name, home name.
- "See all games" hid rows after the first 8 (16 on tournament weeks).

Each row:

- Optional `tournament_context`.
- Away team link, conference short label, score if the game was complete, the word "at", home team link, conference, score. The winner was wrapped in `.schedule-team-winner`.
- Box score when `game_id` was set and the game was complete: `/box-score.html?game_id&mode=franchise&franchise_id&team_id`.
- Team links went to `team-roster-view.html` with `return_tab=schedule-tab` and `origin=team` (that page already redirects into the team drill-in).

Tournament weeks 27–34, with these titles: Conference Tourney - R1, R2, Championships; Region Tourney - R1, Championships; National Tourney - R1, R2; National Championship. An empty tournament week said "No tournament matchups available yet." An empty regular week said "No games scheduled."

Not on this page: play or sim buttons, scouting links, a practice-squad link, a conference filter.

The Team › Schedule panel (`#schedule-tab`, not a link tab) was a separate surface. It showed the user's weeks 1–26 as `Wk N` plus `vs`/`@` and the opponent, or "Open", with the score when the game was complete. After week 26 it appended three text rows: Conference Tournaments, Region Tournaments, National Tournament. From week 27 the same tab swapped to the tournament bracket. Footers linked to `schedule.html` ("View Full National Schedule" and, during the tournament, "View Season Schedule").

Pages that linked to `schedule.html`:

- `franchise-command-center.js`: `#schedule-full-link`, `#tournament-schedule-link`, `#resources-schedule`.
- `brackets-page.js`: `#brackets-footer-schedule`.
- The shell League › Schedule tab (`link: schedule` → `schedule.html`). Team › Schedule was already an in-page tab (`schedule-tab`), not a link.

## Mapping

| What the old page did | Where it lives now |
|---|---|
| National weeks 1–26 | League › Schedule, one week at a time. The stepper is `‹ Week N ›`. |
| Tournament weeks 27–34 and their titles | Same stepper. Empty weeks are disabled. The round title sits above the table. Per-game `tournament_context` stays under the score. |
| "See all games" | The whole week is in the table. |
| Conference sort, no conference filter | The week route sorts the same way. There is no conference segment, because the old page had no filter control. |
| Box score link | Same target, on played games that have a `game_id`. |
| Team name → team page | Pushes `team-view`. League uses `origin=league` and `return_tab=league-schedule-view`. |
| User's season, site, opponent, score, Open | Team › Schedule, weeks 1–26. |
| Three tournament labels after week 26 | Trailing rows on that table. |
| Week ≥ 27 bracket inside the team tab | League › Tournament (`brackets.html`) is still the bracket. The team tab stays the season table. |
| Play, sim, scouting, practice squad | Not on either schedule surface before. They stay on their own tabs. |

The next-game row is a neutral tint (`color-mix` of `--text-100` at 8%). The Office marks the next game as a card, not a navy row. Navy (`tr.me`, `#1c2a52`) stays the user's game on the league week, which is how the Office marks the user's team.

## Data

`GET /franchise/schedule/national` on the offline Lancaster save: 464–981 ms, 26 weeks, 1,664 games. That is over 150 ms, so League › Schedule uses `GET /franchise/schedule/week` (`@browse_cached`). The season bundle stays in the process. A later week is a slice.

Week endpoint, same save (Lancaster, current week 3):

| Call | Time |
|---|---|
| Cold, week 3 (builds the bundle) | 397 ms, and 644 ms on a second process |
| Week 4, 1, 2, and 3 again | 1.5–4.7 ms |

Warm week changes are under 150 ms. The first open pays for ranks, the franchise document, and a prefix read of game ids. Week 3 of that save has 64 games, 63 complete, 63 with a box score. The user's week-1 result does not match a game document filed under week 1 (that document's week field is 2), so that one row has no box score. The same key is what the old national route used.

`GET /franchise/team-detail` additions, only:

- `opponent_wins` and `opponent_losses` on `next_game`, `results`, and `upcoming`, from standings already computed for the team.
- `game_id` on a result when a game document matches that week and matchup.

The team view does not derive the winner. It colors the server's `W` or `L` with `--delta-up` or `--delta-down`, on the letter only.

## Tests

- `tests/test_schedule_week.py` and `tests/test_t3_detail.py`: 5 passed on mongomock, 5 passed on sqlite.
- `tests/e2e/schedule-views.spec.js`: 6 passed (both tabs, week stepper, opponent push and Back, redirect with `week`, no `.main` overflow at 1280 and 1920, skeleton and error/Retry).
- `subtabs`, `t1-tables`, `t3-detail`, `shell-1b`, `navigation-history`: 30 passed, 1 skipped.

Screenshots in `reports/schedule-views/`: the offline Lancaster save (week 3, results on the league table, Next on the team table) and the fixture week 8, at 1280×720 and 1920×1080. The pointer was parked in `.main`.
