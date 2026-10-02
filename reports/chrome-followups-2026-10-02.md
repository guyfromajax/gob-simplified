# polish/chrome-followups — 2026-10-02

Branch `polish/chrome-followups` from `origin/develop` @ `a4285e7e8` (contains the `polish/chrome-audio` merge `30ecc7eca`). `origin/develop` had not moved at gate time (fetched, still `a4285e7e8`), so the merged tree is the code head `b8e69f007`. Ready for review.

The court sound control keeps its sliders: not touched.

## Items

| # | Item | Status | What changed |
|---|---|---|---|
| 1 | Top strip, weeks 35 and 36 | **done** | Week 35 reads "Signing Day", week 36 reads "Offseason", in the week's place. No week number, no emblem. B2 test extended to both. |
| 2 | Champion wording everywhere | **done**, one question | Trophy Case medallions, season-review medallions, the Home Base shelf and the season finish line now say "Regular Season Conference Champions" / "Conference Tournament Champions". Region and National unchanged. List below. |
| 3 | Offline "Coach archetype" pop-up repeats | **done** | The offline build saves the seen flag on this computer (`PATCH /franchise/archetype-reveal-seen` → the save's `local_coach` doc). Shows once. Online still writes the account route. Tested on both stores. |
| 4 | "Trim Your Roster" button | **done** | Neutral (a full-width ghost). One class changed; no CSS added. |
| 5 | Training Report load errors | **done** | Leaving before the fetch lands shows nothing. A real failure shows the inline card. No browser alert. |
| 6 | Top strip: the season, under the week | **done** | "Week 2" over "SEASON 3"; "Conference Tournament" over "FIRST ROUND · SEASON 3"; "Signing Day" / "Offseason" over "SEASON 3". Same label style as RECORD and NATIONAL RANK. Does not widen the strip or move the action button. Every page with the top strip. |
| 7 | Training Report › Player Report › Attributes tab | **done** | Current values only. The plus/minus marks, the red/green change tint and the marks' tooltip are removed. Training Changes unchanged by this item. |
| 8 | Training Report single arrows | **done**, one question | In season: one up is green at 45%, one down is red at 60% (see below); a single arrow follows the sign (0 < n < 1 up, −1.5 < n < 0 down). Two- and three-arrow thresholds not moved. Camp unchanged. Team Report, Training Changes, Playbook Summary. |

Nothing skipped.

## Item 2: where the old labels were

Old labels: "Conference Champions" and "Conference Regular-Season #1" (and their sentence-case forms).

**Changed**

| Place | File | Now |
|---|---|---|
| Trophy Case medallions; its Season Reviews "Finish" fallback | `js/shared/trophyCase.js` `TITLE_KINDS` | Conference Tournament Champions / Regular Season Conference Champions |
| Season review medallions | `js/shared/seasonPeak.js` `TROPHY_TITLE` | same |
| Home Base "Trophy Case" shelf (offline) | `mode-select.js` `HB_TITLE_MEDALLIONS` | Conference tournament champions / Regular season conference champions (this surface is sentence case) |
| Season finish line: Home Base Top Seasons, Trophy Case Season Reviews | `BackEnd/utils/career_data.py` `_TITLE_FINISH_LABELS` | same, sentence case. Computed on read, so past seasons change too; nothing stored carries the old words. |
| Title overlays | `js/shared/seasonPeak.js` `TITLE_TYPES` | already new (chrome-audio) |

**Left as they are** (not the old labels, but the same idea in other words; say if any should follow)

| Place | File | Reads |
|---|---|---|
| Account page, Titles card rows | `account.html:94` | "Conference Tournament", "Conference (Reg. Season)" (count rows, no "Champions") |
| Senior tribute title tallies | `js/shared/seniorTribute.js:18-19` | "Conf. Regular Season", "Conf. Tourney" |
| Bracket champion slot | `fcc-tournament-style-a.js:11` | "Conference Champion" (the bracket's winner, singular) |
| Region-bye and region-qualified copy | `js/shared/milestoneModal.js:13,32,299`, `regionByeModal.js:89,129`, `conferenceRsRegionModal.js:105,140` | sentences: "conference regular-season title", "regular-season conference title", "conference tournament title" |
| Office weekly-card line | `BackEnd/utils/moment_queue.py:268` | "Regular-season conference title still qualifies you for region." |
| The tournament's own name | `franchise-tournament-brackets-render.js`, `js/shared/bigNewsModals.js:380`, `BackEnd/api/franchise_routes.py:4131-4139` | "Conference Tournament" (a tournament, not a title) |

Two knock-on changes inside item 2:

- **The season review used to rename the conference medallion** to "Conference A2 Champions" (the conference's name in place of the title's). That cannot say which of the two conference titles it is, so both now keep the new wording. The region medallion still reads "Region B Champions", and the conference is still named in the review's finish line. One existing test asserted the old label and was updated.
- **Top Seasons truncated the longer finish line** ("Conference tournament cham…") at 1280. Its finish column is now the wider of the two flexible columns (`home-base.css`, one rule); a long team name is what gives way. Tested: both long finishes read in full.

## Item 3: detail

- Cause: the reveal's seen write is `PATCH /api/auth/archetype-reveal-seen`. The offline build treats `/api/auth` as always remote and loopback does not serve it, while the flag is read from the save's `local_coach` doc. Shown, never marked.
- Fix: `PATCH /franchise/archetype-reveal-seen` (`franchise_routes.py`). It checks franchise ownership, refuses a principal that is not the local owner (404), sets `archetype_reveal_seen` on `local_coach`, and bumps the franchise's `browse_rev` so the next Office read is not a 304 of the body that still had the moment.
- Client: `momentQueue.js` and `archetypeReveal.js` use the local route when `GOB_BUILD_PROFILE === 'desktop'`, the account route otherwise.
- Not done: `archetype_evolution_pending` (the "Coaching archetype evolved" weekly-card row, not a pop-up) has the same always-remote write. You asked for the pop-up; say if the row should get the same treatment.

## Item 6: detail

- The season goes in the week stat's existing label line (`#gob-week-phase`), so weeks 1-26 and 35-36 now have the same value-over-label shape as RECORD and NATIONAL RANK. No new element.
- Source: the Office payload's `current_season`, the one every page's top strip is already painted from. No payload: the Office's own "Season N / Week N" label. Neither: the line is hidden.
- "Must not widen the strip": the label is laid out at zero width under the value (`.ts-txt span { width: 0; min-width: 100% }`, `gob-shell.css`), so the value alone sets the stat's width. A label longer than its value ("SEASON 12" under "Week 2", or "CHAMPIONSHIP · SEASON 3") runs on into the empty strip to its right. The tests measure the strip with and without the label: same stats width, same button position.
- In tournament weeks the label keeps its tier metal colour (as the round did before); in weeks 1-26 and 35-36 it is the same quiet colour as RECORD.
- Tests that asserted the old label line were updated: B2 in `polish-chrome-audio.spec.js` (round only → round · season) and one line in `shell-1.spec.js` ("Semifinals").

## Item 7: detail

- `createAttributeCell` now takes the attribute and its value only. Removed with it, because nothing else used them: `markTrainingDelta`, the three tooltip functions and `TOOLTIP_ID`, `displayMovementsForPlayer` / `displayMovementValue`, the `signs` (plus/minus) form in `describeTrainingChange`, and the CSS for `.delta-mark`, `.attribute-tooltip*` and `td.attribute-display-increase` / `-decrease`.
- The white outline box on a moved value (`is-delta`) went with the mark, since it was drawn by the same call. The server still sends `player_attribute_display_movements`; the report no longer reads it (no backend change).
- R3 now sets two display movements in its fixture so the old tint would show, and asserts every SC cell is a bare number with the same colour and weight as an unmoved one, no child, no tooltip, no help cursor; then that Training Changes still shows its marks.

## Item 8: detail

| n (in season) | Before | Now |
|---|---|---|
| 0 < n < 1 | ▲ neutral | ▲ faint green |
| −0.5 ≤ n < 0 | ▲ neutral | ▼ faint red |
| −1.5 < n < −0.5 | ▼ neutral | ▼ faint red |
| 1 ≤ n < 3, n ≥ 3 | ▲▲ green, ▲▲▲ blue | same |
| −2.5 < n ≤ −1.5, n ≤ −2.5 | ▼▼ red, ▼▼▼ red | same |
| 0 | dash | same |

- **Camp is unchanged** and the function did not force a change: the tone is picked per week inside `describeTrainingChange` (camp: one up neutral, any down red). The R2 camp test is untouched and passes.
- **Faint = the same token let through to the row** (`color-mix(in srgb, var(--delta-up) 45%, transparent)`), not a new colour and not `opacity` (which would also fade a cell's outline). No new token.
- **Red is 60%, not 45%.** You gave 45% for green and "reduced opacity" for red. At 45% the red arrow is 2.3:1 on the page, below the 3:1 a graphic needs to read; 60% puts it level with the green. Measured on the Player Report table:

| Row | ▲ faint green | ▼ faint red | full green / red |
|---|---|---|---|
| zebra, dark row | 3.19 | 3.16 | 11.9 / 6.9 |
| zebra, light row | 3.17 | 3.09 | 11.2 / 6.5 |
| Practice Player of the Week row (lighter highlight) | 3.01 | 2.85 | 9.6 / 5.6 |

- Colour-blind: faint vs full is one arrow vs two or three; up vs down is the glyph. Unchanged.
- The "run together" part: single arrows are now tinted by direction, so a column of ▲ and ▼ no longer reads as one grey run. Spacing was not changed.

## Item 4 and 5: detail

- **4.** The modal is built in `franchise-command-center.js` (the FCC), not in the Assign Practice Squad screen's files, so nothing of stats' was touched. The button went from `gob-modal-btn-primary is-green` to `gob-modal-btn-dismiss`, the Styleguide's "one action: full-width ghost". The frozen FCC sheet already had the width rule for that class.
- **5.** Only `loadTrainingReport`'s error path and a small leave-watch above it changed in `training-report.js` (ux's file). The inline card (`.report-load-status`, "The training report did not load.") already existed; the `alert` is gone. A failed refresh keeps a report that is already on screen.

## Files

| File | Item |
|---|---|
| `FrontEnd/static/js/shared/gobShell.js` | 1, 6 |
| `FrontEnd/static/css/gob-shell.css` | 6 (one rule) |
| `FrontEnd/static/js/shared/trophyCase.js`, `seasonPeak.js`, `FrontEnd/static/mode-select.js`, `BackEnd/utils/career_data.py`, `FrontEnd/static/css/home-base.css` | 2 |
| `BackEnd/api/franchise_routes.py`, `FrontEnd/static/js/shared/momentQueue.js`, `archetypeReveal.js` | 3 |
| `FrontEnd/static/franchise-command-center.js` | 4 |
| `FrontEnd/static/training-report.js` | 5 (**ux's file**: fetch error handling only), 7, 8 |
| `FrontEnd/static/training-report.css` | 7 (dead rules removed), 8 (two tone rules) |
| `_documentation_master/11_Design_Systems/Styleguide.md` | 7, 8 (Training movement marks entry, rulings table) |
| `_documentation_master/11_Design_Systems/UX_System.md` | all |
| `tests/e2e/polish-chrome-followups.spec.js` (new), `polish-chrome-audio.spec.js` (B2 weeks 35-36, season line), `shell-1.spec.js` (one assertion), `season-peak-trophy-case.spec.js`, `home-base-offline.spec.js` (fixture wording), `polish-training-playbooks.spec.js` (R2, R3, shots), `tests/test_career_data.py` | tests |

Other agents' files touched: `training-report.js` (ux), as the briefs asked, and for items 7-8 its stylesheet `training-report.css` and the training spec `polish-training-playbooks.spec.js`. None of stats' files (practice-squad rosters, playbook report, box score, set lineup, Tournament tab). No sim / finalize / `cpu_week_pool` / `sim_rng` change. `franchise-command-center.css` unchanged at 1779 lines.

## Tests

`tests/e2e/polish-chrome-followups.spec.js`, 19 tests. Against `origin/develop`'s product files **17 fail**; the two that pass are "online, the seen flag still goes to the account route" (unchanged behaviour) and "a payload that names no season shows no season line" (nothing to show on old code either). With the new strip code but the old CSS, the 5 tests where the label is wider than its value fail on "does not widen the strip". All pass on the branch.

`tests/e2e/polish-training-playbooks.spec.js` (items 7-8): against the previous commit's `training-report.js` / `.css`, **3 fail** (R2 in-season marks, R2 single arrow follows the sign, R3 plain values). The contrast test and the camp test pass on both, as they should: camp did not change, and the old neutral arrows were not low-contrast.

| Item | Covered by |
|---|---|
| 1 | weeks 35 and 36: label, no "week" and no number in the strip, no emblem, no round, in the week's place (also added to the B2 block in `polish-chrome-audio.spec.js`) |
| 2 | Trophy Case medallion labels; season review medallions; Home Base shelf labels; no old wording on any of them; Top Seasons finishes not clipped. `test_career_data.py` finish label. |
| 3 | e2e offline: one PATCH to the local route with the franchise id, none to `/api/auth`, no pop-up on the next two visits. e2e online: the account route, not the local one. `test_career_data.py` on mongomock and SQLite: flag set on `local_coach`, the moment no longer eligible, `browse_rev` bumped, other coach fields untouched; an online coach and a foreign franchise are refused. |
| 4 | button not green (fill, ink, border), Advance still green, spans the modal, still goes to the assignment screen |
| 5 | a 500 shows the inline card and no dialog; leaving mid-load fires no dialog |
| 6 | regular week (2), tournament week (27) and week 35, each at 1280 and 1920: value and label text; label beneath the value, on the RECORD / NATIONAL RANK label line, same size, weight, case, tracking and (outside tournament weeks) colour; stats width and action-button position identical with and without the label; more than 100px of empty strip before the action button. Also: season 12 under "Week 2"; a browse page and a focus page (recruiting); no season in the payload. The B2 block asserts the same line for weeks 2, 27-34, 35, 36 and on a browse page. |
| 7 | R3: every SC cell on Attributes is a bare number, same colour and weight as an unmoved value, no mark, no outline, no tooltip attribute, no help cursor, nothing appears on hover; Training Changes still shows ▲▲▲ for the same player |
| 8 | R2 in season: Team Report, Training Changes and Playbook Summary marks and painted colours (faint green, faint red, green, blue, red, dash). R2 thresholds: 0.01, 0.99, 1, 2.99, 3, −0.01, −0.5, −1.49, −1.5, −2.49, −2.5, 0. R2 contrast: the painted faint colours are 3:1 or better on both zebra rows and clearly fainter than full strength. R2 camp: unchanged test. |

## Shots (`reports/chrome-followups/`, 1280; items 6-8 also at 1920)

| Item | After | Before |
|---|---|---|
| 1 | `f1-top-strip-week-35-after`, `f1-top-strip-week-36-after` | `…-before` |
| 2 | `f2-trophy-case-after`, `f2-season-review-after`, `f2-home-base-offline-after` | `f2-trophy-case-before`, `f2-home-base-offline-before` |
| 3 | `f3-archetype-first-visit-after`, `f3-archetype-next-visit-after` | `f3-archetype-first-visit-before` |
| 4 | `f4-trim-your-roster-after` | `f4-trim-your-roster-before` |
| 5 | `f5-report-load-failed-after` | `f5-report-load-failed-before` (the page under the old browser alert; a screenshot does not capture the alert itself) |
| 6 | `f1b-season-regular-after-1280` / `-1920`, `f1b-season-tournament-after-1280` / `-1920`, `f1b-season-signing-day-after-1280` / `-1920` (the top strip, 130px tall) | same names with `-before` |
| 7 | `f7-attributes-tab-after-1280` / `-1920` | `f7-attributes-tab-before-…` |
| 8, in season (week 12) | `f8-marks-in-season-team-report-after-…`, `f8-marks-in-season-training-changes-after-…`, `f8-marks-in-season-playbook-summary-after-…`, each at 1280 and 1920 | same names with `-before` |
| 8, camp (week 1) | `f8-marks-camp-team-report-after-…`, `f8-marks-camp-training-changes-after-…`, each at 1280 and 1920 | same names with `-before` (identical: camp did not change) |

The item 7-8 shots are taken by `polish-training-playbooks.spec.js` only when `FOLLOWUP_SHOT_TAG` is set, so a normal run does not rewrite them.

The item 1 after shots were retaken and now show the season line too. Fifteen stray `*-cssold-*` shots, `f3-archetype-next-visit-before-1280.png` and `f2-season-review-before-1280.png` from my old-code runs are in the folder (the last two are mislabelled: they show the fixed state), untracked and not committed (deleting them was not permitted in this session); safe to delete.

## Questions

1. **Season review, conference medallion.** It no longer reads "Conference A2 Champions"; it reads "Conference Tournament Champions" (see item 2). Right call?
2. **The "left as they are" list above.** Any of those to change (the Account rows and the senior tribute tallies are the closest to labels)?
3. **Case.** The Trophy Case page shows "National Champions" (its own label) beside "Conference tournament champions" (the server's finish line) in the same Finish column. That mix predates this branch. One case for both?
4. **Archetype evolution row offline** (see item 3): same local write wanted?
5. **Faint red at 60%** (item 8). 45% as for green fails 3:1 (2.3:1). Keep 60%, or do you want both at one number? Both at 45% makes the down arrow hard to see; both at 60% makes the up arrow stronger than you asked (about 4.8:1).
6. **Practice Player of the Week row** (item 8): its highlight is lighter than either zebra row, so a faint red arrow there is 2.85:1 (faint green 3.01). Only matters when that player has a one-arrow drop. Left as is; say if that row should get full-strength arrows or a stronger faint.
7. **The outline box on a moved value** (item 7): removed from the Attributes tab with the marks. It still frames moved cells on Training Changes.

## Gates (final tree `b8e69f007`; `origin/develop` @ `a4285e7e8` is its base, nothing to merge)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | 4371 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed. Both XPASS are pre-existing; `known_failures.py` not edited. |
| `check_ui_tokens.py --strict --no-write` | exit 0 |
| `check_migration_gates.py` | passed (Gate A 0, Gate B 134 lines / 43 files) |
| `franchise-command-center.css` | 1779 lines, unchanged |
| Full Playwright (lock held 13:15-13:33, 1 worker) | 975 passed, 19 skipped, **1 failed**: `shell-1b.spec.js:442` "recruiting hub lands on leans, otherwise the user region" (`page.goBack: net::ERR_ABORTED` after `goto('/login.html')`). Re-run alone with `--repeat-each=5`: **5 of 5 passed**. |

The one full-run failure is the known Back-from-`login.html` flake (`login.html` redirects itself, so Back can be aborted mid-navigation; the fix on `fix/recruiting-tabs-flake` is not merged and names this spec as having the same pattern). This branch does not touch that spec, `recruiting.js` or `login.html`.

Earlier full runs on this branch, before items 6-8 were added: 964 passed, 17 skipped, 0 failed (tree `436a11944`).

## After merging `origin/develop` @ `0fe743624` (polish/tables-followups), merge commit `15b2aceaa`

- One conflict: Styleguide "Training movement marks". Kept this branch's entry (single arrows follow the sign, faint green / faint red, Attributes tab plain values); stats' side was the old in-season rule.
- `UX_System.md` merged without conflict; the two sides edited different lines, both kept. No other file was changed on both sides.

| Check on the merged tree | Result |
|---|---|
| `check_ui_tokens.py --strict --no-write` | exit 0 |
| `check_migration_gates.py` | passed (Gate A 0, Gate B 134 lines / 43 files) |
| `pytest tests/test_career_data.py` | 70 passed |
| `polish-chrome-followups`, `polish-training-playbooks`, `polish-chrome-audio`, `tables-followups` specs | 86 passed, 11 skipped (the shot-only tests), 0 failed |
| `franchise-command-center.css` | 1779 lines |

No full Playwright re-run on the merged tree (not asked for). The full-suite line below is from the pre-merge tree `b8e69f007`.

**Full suite: pytest 4371 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed · Playwright 975 passed, 19 skipped, 1 failed (flake, 5/5 alone).**
