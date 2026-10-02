# polish/chrome-followups-2 — 2026-10-02

Branch `polish/chrome-followups-2` from `origin/develop` @ `71048e175` (the `polish/chrome-followups` merge). `origin/develop` had not moved at gate time, so the final tree is the code head `0e697f474`. Ready for review.

## Items

| # | Item | Status | What changed |
|---|---|---|---|
| 1 | Offline: "Coaching archetype evolved" weekly row shows once | **done**, two things to know | New offline route clears the pending key on the save; the client sends it once the Office has shown the row. Online unchanged. Both stores tested. |
| 2 | Finish labels one case | **done**, one question | Titles and round finishes are capitalised on the server and the Home Base shelf. Top Seasons was cutting the longest label off at 1280 by under a pixel; fixed. |
| 3 | court.html "HC Traps" | **done** | Both rows read "Half-Court Traps". It fits on one line at every court width tested (1280, 1366, 1440, 1700, 1701, 1920). |
| 4 | CH is hidden (priority, own commit `c11e5489d`) | **done**, two route groups left for Jamie | Removed from the Practice Squad report, the Office card, the tooltip map and news copy. Stripped from every franchise payload. Guarded by a server test and a Playwright test. Court and Team Builder routes still carry it; see below. |

| 5 | Office "Conference standings" card showed 2 cramped rows (own commit `0e697f474`) | **done**, one thing to know | Cause found (a different bug from stats' race). The card now always shows all 8 teams at normal row spacing, with team marks; the user's row is navy; "Full standings" stays. The Office now scrolls on a short window. |

Account page rows and the senior tribute tallies: not touched, as asked.

## Item 1: detail

- **What my last report got wrong.** I said this row "has the same always-remote write" as the pop-up. The write exists (`PATCH /api/auth/archetype-evolution-seen`) but nothing reaches it: it sits in the evolution pop-up, and the row is WEEKLY tier, which never pops. So today the row is never cleared **in either build**.
- **Offline, now:** `PATCH /franchise/archetype-evolution-seen` (`franchise_routes.py`) removes `archetype_evolution_pending` from the save's `local_coach` doc and bumps `browse_rev`. `momentQueue.js` sends it when the build is desktop, the read is the authoritative one, the row is in `weekly_card_items` and the Office is the panel on screen. The row stays for that visit and is gone on the next. A visit that lands on another tab leaves it for the next Office visit.
- **Online, unchanged, as asked:** nothing sends the account write, so the row stays until the next evolution replaces it. Say if online should get the same "seen when shown" rule.
- **Found, not fixed (persistence adapter):** on SQLite a projected read of a field holding an empty string raises (`sqlite_collection._extracted_value`: `'' in "{["` is true, so it tries to parse `""` as JSON). The Office reads this field projected, so setting the key to `""` would have broken the offline Office. The route removes the key instead, and a test pins that. The adapter bug is still there for any other empty-string field.

## Item 2: detail

| Place | File | Now |
|---|---|---|
| Season finish line (Trophy Case Season Reviews, Home Base Top Seasons) | `BackEnd/utils/career_data.py` `_TITLE_FINISH_LABELS`, `_FINISH_LABELS` | "National Champions", "Region Champions", "Conference Tournament Champions", "Regular Season Conference Champions"; rounds: "National Final", "Region Semifinal", "Conference Quarterfinal", "Missed the Bracket", … |
| Home Base shelf | `mode-select.js` `HB_TITLE_MEDALLIONS` | the same four, capitalised |
| Trophy Case shelf and its Finish fallback | `trophyCase.js` `TITLE_KINDS` | already capitalised |

- **Round finishes too.** Your list named the four titles. The round finishes ("Region semifinal", "Missed the bracket") share the same Finish column, so leaving them would have kept the mix. They are capitalised as well. Computed on read: past seasons change too.
- **Truncation at 1280.** Top Seasons cut "Regular Season Conference Champio…" off by 0.7px. The finish column now gets twice the room of the program name (`home-base.css` `.tsn`, 1.75fr → 2fr): 10px spare at 1280. The earlier test missed it because `scrollWidth` is a whole number; both specs now compare the text's real width.
- Trophy Case Finish column and both shelves: nothing cut off at 1280 or 1920.

## Item 5: Office conference standings

**Why only two rows.** The card had its own fit loop (`officeHome.js` `fitStandings`). When column 02 ran past the fold it (1) switched the rows to a compact spacing, (2) then a tight one (2px padding, header hidden), and (3) then sliced a window around the user's row, shrinking it one row at a time down to a minimum of two. At week 6 the middle column is tall (This Week, Team snapshot with Moved most), so the loop ended at two tight rows: rows 3 and 4, cramped. Not the window-slicing arithmetic and not ties: the server order is already final, and the client kept it.

**Same bug as stats' race?** No. Stats fixed the weekly-card row caps reading `.gob-1280` / `.gob-1920` before the shell had set it. The standings loop did read that class too, but it was sliced on a correctly classed page (reproduced at 1280×720 with the class set: four tight rows; before shot). The card no longer reads the density class at all, and a test strips the class and redraws to prove it.

**Now**

| Rule | How |
|---|---|
| All 8 teams, standings order, no slicing | `paintStandingsRows` draws every row the server sends; `fitStandings`, `standingsWindow`, `standingsOverflow` are gone |
| Rank, team mark and name, record | the mark is the league tables' own (`GOBTables.markHtml`: logo, or the letter tile) |
| User's row navy | unchanged treatment (`.st-r.me`) |
| "Full standings →" stays | always in the card header now (it used to appear only when the card was squeezed) |
| Normal row height and padding | the compact / tight styles and the 1920 zero-padding rule are removed; a row has the same padding as a players-to-watch row at every density (35px rows at 1280, 41px at 1920) |

**The thing to know: the Office no longer always fits the fold.** Eight normal rows do not fit under This Week and Team snapshot on a short window, and the rule is that the card is never squeezed, so the Office is taller than the fold and `.main` scrolls. Measured (px the Office is taller than the window):

| State | 1280×720 | 1440×900 | 1920×1080 |
|---|---|---|---|
| win / loss / regular week | 196 | 16 | 74 |
| first week | 155 | 0 | 31 |
| tournament week | 191 | 11 | 176 |
| Signing Day | 31 | 0 | 0 |

To make that scroll clean, the Office container now grows with its tallest column (`office-home.css`, `flex-shrink: 0` on the Office chain); before, the card would have hung out of its column. Three existing tests in `office-frontend.spec.js` encoded the old rule (fit the fold, compact, window) and were rewritten to the new one; one float-rounding tolerance there went from 2 to 2.01.

## Item 4: CH is hidden

**The rule:** never displayed, never sent to the client. Engine, training and database unchanged (no sim / finalize / `cpu_week_pool` / `sim_rng` change).

### Every hit, and what I did

| Where | File:line | What it was | Action |
|---|---|---|---|
| Practice Squad report, 13th column | `training-squad-report.js:30`, `:49` | `ATTR_KEYS` ended in `'CH'`; `orderKeys` appended "anything else the server sends (CH)" | Removed. Only the twelve paired attributes are ever columns, whatever a payload carries. |
| Practice Squad report payload | `franchise_routes.py:16857` | `attr_keys` sent all 13 | Sends the visible 12. CH still develops on the practice squad (`:14129` unchanged). |
| Office "Since last week" chips | `office_digest.py:611`, `officeHome.js:433` | a row per moved attribute, CH included | Server skips CH rows; client drops one if it ever arrives. |
| Attribute tooltip map | `attributeTooltips.js` (was line 21) | `CH: 'Clutch'` | Removed. |
| News, Practice Squad All-Stars | `franchise_routes.py:14306`, `:14593-14604` | "His strongest gains were in … Clutch"; the points total included CH | Names and counts visible attributes only. Which players qualify is unchanged. |
| Growth profile | `player_development.py:299` | `development.ch_seed` (a frozen copy of CH) rides on player docs | Stripped from payloads with CH. Stored value unchanged. |
| Training Report: Team Report, Training Changes, Attributes, notes | `training-report.js` | never showed CH (fixed attribute list; notes exclude it) | No change. Payload now stripped. |
| Roster, Player page, Player Training, Training page, Set Lineup, recruit cards and detail, scouting, box score, sort menus, column pickers | — | never showed CH (fixed twelve-attribute lists) | No change. Guarded. |
| Tutorials, FAQs, Team Builder, court overlays, desktop/debug views | — | no CH, "Clutch" or other name for it in any client file | No change. ("clutch" in sim callouts and press-conference questions is late-game, not the attribute.) |

### Payloads

- `BackEnd/utils/hidden_attrs.py`: `HiddenAttrsJSONResponse` is the default response class of the franchise router and the press-conference router, and is set on `/player/{id}` and `/teams/{id}/players`. A new franchise route is covered without anyone remembering.
- It removes `CH`, `anchor_CH`, `ch_seed` as keys; rows that name it (`{"attribute": "CH"}`); and CH from attribute-key lists. It works on a copy of the response, so the documents the engine reads and saves are never touched.

### Still carrying CH: stopped for Jamie

| Routes | Why I stopped | Shown anywhere? |
|---|---|---|
| The court's own: `/roster/{team}`, `/api/init-game`, `/api/simulate-turn`, `/api/simulate-quarter`, `/api/call-timeout`, `/api/autoset-lineup`, `/api/game/{id}` (+ `resume-state`, `lineup-for-matchups`) | The Phaser client needs it: `gameSfx.js:562,580` picks the pass-receive sound from the receiver's IQ + CH. Autoset also posts roster attributes back. | No. The court spec checks every panel tab. |
| `/franchise/team-builder/*` (12 routes) | Team Builder round-trips whole player rows (walk-ons, slot roster) through the client and saves what comes back. Stripping would lose the generated CH on Apply. | No. |

`/roster/{team}` is the notable one: Set Lineup and other screens read it too, so CH still reaches the browser there. One way out, if you want it: have the server send the receive-sound tier with the turn, then strip the court routes as well.

### Things that reveal CH indirectly (not changed; your call)

| What | Where | Why it tells |
|---|---|---|
| Training note "Most Positive Locker Room Influence" | `training_notes.py:235-251` | Only players with CH above 59 are eligible, weighted above 79. Never names CH. |
| Pass-receive sound on the court | `gameSfx.js:580` | strong / medium / weak depends on IQ + CH. |
| News stories already stored in a save | `league_news` | A story written before this change can still say "Clutch". Not scrubbed (no database change). |

Nothing of stats' or ux's in-flight screens showed CH except `training-squad-report.js` (stats'), which the brief gave me.

## Files

| File | Item |
|---|---|
| `BackEnd/api/franchise_routes.py` | 1 (route), 4 (router default, Team Builder exemptions, practice-squad keys, news copy) |
| `FrontEnd/static/js/shared/momentQueue.js` | 1 |
| `BackEnd/utils/career_data.py`, `FrontEnd/static/mode-select.js`, `FrontEnd/static/css/home-base.css` | 2 |
| `FrontEnd/static/court.html` | 3 (two rows) |
| `FrontEnd/static/js/shared/officeHome.js`, `FrontEnd/static/css/office-home.css` | 5 (and 4: the Office chip guard) |
| `BackEnd/utils/hidden_attrs.py` (new), `BackEnd/api/api.py`, `BackEnd/api/press_conference_routes.py`, `BackEnd/utils/office_digest.py` | 4 |
| `FrontEnd/static/training-squad-report.js` (**stats' file**, as the brief allowed), `js/shared/officeHome.js`, `js/shared/attributeTooltips.js` | 4 |
| `_documentation_master/11_Design_Systems/UX_System.md`, `Styleguide.md` | 1, 2, 4 |
| `tests/e2e/polish-chrome-followups-2.spec.js` (new), `tests/e2e/hidden-attr-ch.spec.js` (new), `tests/test_hidden_attrs.py` (new), `tests/test_career_data.py`, `tests/e2e/polish-chrome-followups.spec.js`, `tests/e2e/home-base-offline.spec.js`, `tests/e2e/office-frontend.spec.js` (5), `tests/e2e/tables-followups.spec.js` (4: **stats' spec**, its practice-squad test asserted the CH column) | tests |

Not touched: Training page, Playbooks, training point selector (ux); News, Awards, team pages (stats). `franchise-command-center.css` unchanged at 1779 lines.

## Tests

| Item | Covered by | On old code |
|---|---|---|
| 1 | `test_career_data.py`, mongomock and SQLite: key removed (not blanked), row gone, `browse_rev` bumped, other coach fields untouched, a later evolution brings the row back; online coach and foreign franchise refused. e2e: offline at 1280 and 1920 one local PATCH, none to `/api/auth`, row gone on later visits; a non-Office visit sends nothing; online sends no local write. | route tests fail (no route); 3 of 4 e2e fail, "online" passes |
| 2 | `test_career_data.py` finish labels. e2e at 1280 and 1920: Trophy Case Finish column and shelf, Home Base shelf and Top Seasons: capitalised, one line, not cut off (sub-pixel exact), at least 4px spare. | Home Base tests fail; Trophy Case e2e passes (its strings come from the mocked server; the pytest covers the server) |
| 3 | e2e at six widths, both panels: "Half-Court Traps" on one line, same row height as "Fast Breaks", table not overflowing, no "HC Traps". | all six fail |
| 4 | `test_hidden_attrs.py` (9): the strip in every form and no mutation; every `/franchise` route renders through it bar the pinned Team Builder list; court routes pinned as the known exceptions; a real franchise's payloads (create, state, roster, recruits, recruiting-data, command-center, team-data, team-stats, training-points, training-squad-reports) carry no trace while the database still has CH; player page; Office rows; news copy. `hidden-attr-ch.spec.js` (11): Office card and Practice Squad report fed CH (1280, 1920); Roster, Player Training, Training page, Training Report (both tabs), Set Lineup fed payloads with CH put back; the court's panels on real rosters. | Office and Practice Squad e2e fail (4); the other 7 pass, as they should: those screens never showed it |

| 5 | e2e, 10 tests: all 8 rows in server order with rank, mark, name and record; user row navy and only it; same padding as the reference list row; one row height; no row or text overlapping the next; "Full standings" once; no horizontal scroll. Run in six Office states at 1280×720, 1440×900, 1920×1080, 2048×1152, 2560×1440, 1066×640, 1024×600. Ties (Jamie's case, and all eight tied with the user first, last and middle). Density class stripped and redrawn. | all 10 fail |

## Shots (`reports/chrome-followups-2/`, 1280 and 1920)

| Item | After | Before |
|---|---|---|
| 1 | `g1-evolution-row-first-visit-after-…`, `g1-evolution-row-next-visit-after-…` | — |
| 2 | `g2-trophy-case-season-reviews-after-…`, `g2-home-base-after-…` | — |
| 3 | `g3-court-play-stats-after-…`, `g3-court-play-stats-away-panel-after-…` | — |
| 4 | `ch-office-since-last-week-after-…`, `ch-practice-squad-report-changes-after-…`, `ch-practice-squad-report-absolute-after-…` | `ch-office-since-last-week-before-…`, `ch-practice-squad-report-changes-before-…` |

| 5 | `g5-office-standings-after-…` (page), `g5-office-standings-card-after-…` (the card) | `g5-office-standings-before-…`, `g5-office-standings-card-before-…` |

Untracked and not committed: `g1-…-before` and `g2-…-before` shots from my old-code runs (their mocked payloads already use the new strings, so they are not true befores). Safe to delete.

## Questions

1. **Court routes and CH** (item 4): leave as is, or move the receive-sound tier to the server so the court payloads can be stripped too?
2. **Team Builder routes and CH** (item 4): leave as is, or keep CH server-side through the draft (a bigger change to how drafts are saved)?
3. **"Most Positive Locker Room Influence"** note: keep, or pick it another way so it does not track CH?
4. **Stored news stories that say "Clutch"**: leave, or scrub on read?
5. **Archetype row online** (item 1): nothing clears it today. Same "seen when the Office shows it" rule as offline?
6. **Round finishes capitalised** (item 2): done with the titles. Right call? "In progress · Week N" in the same column was left as it is (a status, not a finish).
7. **SQLite empty-string projection bug** (item 1): fix in the adapter?
8. **The Office scrolls now** (item 5): by about 200px at 1280×720 and 75px at 1920×1080 on a game week. That is the cost of eight normal rows. If the Office should still fit the fold at 1920×1080, the room has to come from another card in column 02 (Team snapshot is the tallest), not from the standings rows.

## Gates (final tree `0e697f474`; `origin/develop` @ `71048e175` is its base, nothing to merge)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | 4385 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed. Both XPASS are pre-existing; `known_failures.py` not edited. |
| `check_ui_tokens.py --strict --no-write` | exit 0 |
| `check_migration_gates.py` | passed (Gate A 0, Gate B 134 lines / 43 files) |
| `franchise-command-center.css` | 1779 lines, unchanged |
| Full Playwright (lock held 14:50-15:09, 1 worker) | 1027 passed, 19 skipped, 0 failed |

An earlier full run on `c11e5489d` (before item 5): 1016 passed, 19 skipped, 1 failed. The failure was `tables-followups.spec.js:138`, stats' test asserting the thirteenth CH column; it now asserts twelve columns and no CH (`03c757300`).

**Full suite: pytest 4385 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed · Playwright 1027 passed, 19 skipped, 0 failed.**
