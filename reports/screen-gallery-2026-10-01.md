# Screen gallery: 2026-10-01

Eye-test gallery after today's token work. No product changes. Branch `docs/screen-gallery` from `origin/develop` (`315c93f9b`). Shots in `reports/screen-gallery/` (`<screen>-1280.png`, plus `-1920.png` for the six highest-traffic screens: Office, Roster, Recruiting Pool, Set Lineup, Court pre-game, Mode select online). All are `page.screenshot` at scroll 0.

## How it was shot

- **Franchise screens: desktop SQLite e2e server** (`seed_and_serve_desktop.py`, `base_league.sqlite`, real 128-team league), desktop profile, Playwright `playwright.desktop.config.js`. One franchise was created through `POST /franchise/select-team` (Lancaster, Week 1, preseason #43), as `desktop-play-flow` does. The hosted e2e seed has 6 teams, and franchise creation needs 128 (`ValueError: Franchise schedule expects exactly 128 teams, got 6`), so a hosted seeded franchise is not possible today.
- **Hosted e2e server** (`seed_and_serve.py`, mongomock) for online-only and account-free pages: mode select online, auth, community, tutorials, FAQs. `/api/auth/me` is stubbed; the stub token is rejected by real endpoints, so online mode select shows no programs and a few 401s.
- **Spec:** a throwaway gallery spec + config in the session scratchpad (not committed). Both passes ran inside **one lock session** (`/tmp/gob-full-playwright.lock`, 13:24:38–13:28:25, released). An earlier attempt held the lock for 3 s and failed fast on the token, then released it.
- **What the seed state means:** Week 1, preseason, no games played. So **no real box score, training report or in-game court**; those shots are empty states (noted). Team Builder without params redirects to program select step 1 (`?builder=1`), so Team Builder steps 2–5 are not in the gallery.

## Gallery

| # | Screen | Path | Shot | Visual issues (blunt) |
|---|---|---|---|---|
| 1 | Office | `/franchise-command-center.html?tab=home-tab` | `office-1280.png`, `office-1920.png` | "Moved most" shows two identical placeholder rows ("Set after camp —"). "Since last week" column is one small card with a big empty area under it. Attitude bars use red/orange/grey/green/bright-green (documented attitude ramp; fine by UX_System). |
| 2 | Team › Roster | `?tab=roster-view` | `team-roster-1280.png`, `-1920.png` | Segment labels jam the count into the word: "Varsity15", "Practice Squad0" (italic number, no space). Attribute digits on the RT ramp, blue = elite (legal). |
| 3 | Team › Player Stats | `?tab=player-stats-view` | `team-player-stats-1280.png` | **Clipped at 1280:** the last column ("F") is cut at the right edge with no visible scroll affordance. Preseason: every cell "—" (expected). |
| 4 | Team › Team Attributes | `?tab=team-attributes-view` | `team-attributes-1280.png` | Fine. Radar tiny in a large card. Ranks "1st of 128" on zero values read oddly in preseason. |
| 5 | Team › Schedule | `?tab=team-schedule-view` | `team-schedule-1280.png` | Fine. Some teams show letter tiles (W, N, M) instead of logos. |
| 6 | Team › Practice Squad | `?tab=practice-squad-view` | `team-practice-squad-1280.png` | Empty state is one line of plain text under the tabs: no card, no styling. |
| 7 | Prep › Player Training | `?tab=training-view` | `prep-player-training-1280.png` | Table is ~600px wide in a 1200px column: the right half is dead space. "Training by Position ↗" floats far right. |
| 8 | Prep › Game Plan | `?tab=game-plan-view` | `prep-game-plan-1280.png` | "Save Game Plan" is **orange at rest** (nothing changed). The law says orange = the enabled save; check that it is not shown as enabled before an edit. Slider end labels wrap ("100% Half-Court / Sets", "100% Get Back on / D"). |
| 9 | Prep › Playbooks | `?tab=playbooks-view` | `prep-playbooks-1280.png` | Expected Shot Distribution numbers in red/yellow/blue/green (`getPswColor`, **blue on a non-RT value**: pending ruling). "Save Playbooks" orange at rest. |
| 10 | Prep › Scouting | `?tab=scouting-view` | `prep-scouting-1280.png` | Fine. Attribute tiles on the RT ramp. |
| 11 | League › Standings | `?tab=standings-view` | `league-standings-1280.png` | **77 × 404** in the console (team art). Columns unevenly spaced: wide empty gap between PA and DIFF. STRK empty preseason. |
| 12 | League › Rankings | `?tab=rankings-view` | `league-rankings-1280.png` | Many teams show letter tiles (L, H, P, E, S, M, K) instead of logos (17 × 404). "Last Week" column empty. |
| 13 | League › Leaders | `?tab=leaders-view` | `league-leaders-1280.png` | **Inconsistent empty states:** Points, Assists, FG%, Rebounds and DEF% are empty cards with a floating "Full list →", while 3-Pointers, Blocks and Steals list five players at 0. Bottom row clipped at 720. |
| 14 | League › Team Stats | `?tab=team-stats-view` | `league-team-stats-1280.png` | Dense but fits. Letter-tile logos (77 × 404). |
| 15 | League › Schedule | `?tab=league-schedule-view` | `league-schedule-1280.png` | Fine. Your game navy (legal). |
| 16 | League › Tournament | `?tab=tournament-view` | `league-tournament-1280.png` | Locked state is bare text rows ("Conference … Weeks 27–29"): no card, reads unfinished. |
| 17 | Recruiting › Pool | `/recruiting.html?hub=pool` | `recruiting-pool-1280.png`, `-1920.png` | **At 1920 the table stops at ~1440px**, leaving a ~450px empty band on the right inside the card. Lean column cells are tall dashed "1 open" boxes that dominate the row. |
| 18 | Recruiting › Leans | `?hub=leans` | `recruiting-leans-1280.png` | Fine. LAN pill navy (yours). |
| 19 | Recruiting › Visits | `?hub=visits` | `recruiting-visits-1280.png` | Fine (pre-window state). |
| 20 | News | `?tab=news-view` | `news-1280.png` | Fine. Second story card is half width beside nothing. |
| 21 | News › Awards | `?tab=awards-view` | `news-awards-1280.png` | Plain-text empty state ("Awards are not available yet."). 1 × 400 in the console. |
| 22 | Settings panel | FCC + `GOBSettings.open()` | `settings-panel-1280.png` | "Coach stats" heading with nothing under it (empty section). Otherwise clean. |
| 23 | Weekly training (focus) | `/training.html` | `focus-training-1280.png` | **"Submit Training" is green** (and looks dimmed/disabled). UX_System calls it the page's own primary, not the Advance (SFX_COMMIT); check against the law (a commit = orange). Large empty band between the sections and Coaching Focus. |
| 24 | Training report (focus) | `/training-report.html` | `focus-training-report-1280.png` | Gallery URL lacked `week`, so it is an empty state; but the empty state is raw: "Week: -- · Upcoming Opponent: --", empty sections with underline rules. Not a product bug as reached here. |
| 25 | Set Lineup | `/set-lineup.html` | `set-lineup-1280.png`, `-1920.png` | **All five starter slots "Empty" on arrival** (no autoset at Week 1). Team banner lettering clipped by the card top ("LANCASTER" cut) at both sizes. Shot-weight bars red/yellow/blue/green (`getPswColor`, pending). At 1920 the right column has a large empty gap above Autoset. |
| 26 | Court pre-game | `/court.html` | `court-pregame-1280.png`, `-1920.png` | **Two buttons on a blank page:** no court, no scoreboard, no team context behind the Play Quarter / Sim Full Game card (in this e2e state). |
| 27 | Focus Game Plan (timeout) | `/game-plan.html?resume_from_timeout=true` | `focus-game-plan-1280.png` | Gallery URL lacked `game_id`, so it shows the error card ("Missing Required GAME ID", ⚠️ emoji title). The card is styled; the emoji is the only colour. |
| 28 | Box score | `/box-score.html` | `box-score-1280.png` | No game played (empty state "Away Team 0 @ Home Team 0"). **"Back to Locker Room" renders as an unstyled browser-default grey button** at the top left, overlapping the card edge. |
| 29 | Cut players | `/cut-players.html` | `cut-players-1280.png` | At Week 1 it opens straight into a "No Cuts Required" modal over the table. **Orange on navigation:** "Back To Locker Room" (modal) and "Assign Practice Squad" (with 0 to assign). Page title is Inter, not Bebas (inconsistent). Red top rule on the modal. |
| 30 | Training playbook | `/training-playbooks.html` | `training-playbooks-1280.png` | **Top bar has no team logo** (blank left, starts at "0-0"); every other focus page shows it. Save & Continue disabled (legal). |
| 31 | Playbook report | `/playbook-report.html` | `playbook-report-1280.png` | Fine. |
| 32 | Mode select (offline) | `/mode-select.html` (desktop) | `mode-select-offline-1280.png` | Fine. Trophy-case medallions are empty dashed circles. |
| 33 | Mode select (online) | `/mode-select.html` (hosted) | `mode-select-online-1280.png`, `-1920.png` | Stub token, so no programs (expected). "Around GOB" is six large dashed "WAITING FOR NEXT RESULT" boxes: half the screen is placeholder. 4 × 401 in the console. |
| 34 | Trophy case | `/trophy-case.html` | `trophy-case-1280.png` | Fine. Empty titles are three dashed circles with no labels. |
| 35 | Program select | `/franchise-select-team.html` | `program-select-1280.png` | Fine. |
| 36 | Team Builder (step 1) | `/team-builder.html` → `franchise-select-team.html?builder=1` | `team-builder-1280.png` | Fine. Steps 2–5 not captured (need a slot pick). |
| 37 | Login | `/login.html` | `auth-login-1280.png` | Fine. |
| 38 | Sign up | `/signup.html` | `auth-signup-1280.png` | Fine (non-alpha form on this server). |
| 39 | Reset password | `/reset-password.html` | `auth-reset-1280.png` | Fine. |
| 40 | Archetype leaderboard | `/coaching-archetypes-leaderboard.html` | `community-leaderboard-1280.png` | Fine (empty boards). 1 × 401. |
| 41 | Coaching archetypes | `/coaching-archetypes.html` | `community-archetypes-1280.png` | Minor: the "Cerebral Offense" title sits higher than its neighbours (shorter badge art shifts the row). |
| 42 | Account | `/account.html` | `community-account-1280.png` | Fine. |
| 43 | Tutorial hub | `/tutorial.html` | `tutorial-hub-1280.png` | Fine. |
| 44 | Tutorial lesson (recruiting) | `/tutorial-recruiting.html` | `tutorial-lesson-recruiting-1280.png` | Breadcrumb "Recruiting" is orange (lesson-page inline chrome, the known follow-up). Diagram bars gold/orange (content, out of scope). |
| 45 | Persona intro | `/tutorial-persona-intro.html` | `tutorial-persona-1280.png` | Fine. |
| 46 | FAQs | `/faqs.html` | `faqs-1280.png` | Fine. |

Console signals the gallery recorded on every screen: no horizontal page overflow, no serif fallback text. One screen (box score) has a browser-default button.

## Top 10 issues (most visible first)

1. **Court pre-game is two buttons on a blank page** (`court-pregame-*`): no court, scoreboard or team context. The first thing a coach sees at tip-off.
2. **Set Lineup opens with all five starters "Empty"** (`set-lineup-*`) at Week 1, and the team banner lettering is clipped at the top. High-traffic, every game.
3. **Missing team art across League**: 77 × 404 on Standings / Team Stats / Schedule, and letter tiles instead of logos for many programs in Rankings and Team Stats.
4. **Box score "Back to Locker Room" is an unstyled browser button** overlapping the card edge (`box-score-1280`).
5. **Orange on navigation in Cut Players**: "Back To Locker Room" and "Assign Practice Squad" are orange, the page opens in a modal at Week 1, and its title is Inter, not Bebas.
6. **Leaders boards disagree with each other**: five boards empty with a floating "Full list →", three list players at 0.
7. **Weekly training "Submit Training" is green and looks disabled**: a commit painted as Advance (check against the colour law). Same family: Save Game Plan / Save Playbooks are orange at rest, before any change.
8. **Player Stats clips its last column at 1280** with no visible horizontal-scroll cue.
9. **Dead space**: the Player Training table uses half its column; the Recruiting Pool table stops ~450px short at 1920; the Set Lineup right rail has a large gap at 1920; the Office "Since last week" column is mostly empty.
10. **Raw empty states**: Practice Squad, Tournament (locked), Awards and the Training Report placeholders ("Week: --") are plain text with no card. Plus small ones: no team logo on the Training Playbook top bar, "Varsity15" / "Practice Squad0" labels, the duplicated "Set after camp" rows on the Office, and the empty "Coach stats" section in Settings.

Pending rulings, not ranked as bugs: the Expected Shot Distribution and shot-weight colours (`getPswColor`: blue on a non-RT value) on Playbooks and Set Lineup; the orange breadcrumb on tutorial lesson pages (known follow-up).

## Correction to an earlier report

`reports/play-flow-tokens-2026-10-01.md` says `desktop-play-flow` passed in the targeted run. It did not run: `playwright.config.js` has `testIgnore: 'desktop-*.spec.js'`, so that spec only runs under `playwright.desktop.config.js`. The 13 passes were the other four specs. Desktop pages that load `teamPicker.js` (program select) were exercised by `program-select-tokens` and by this gallery's desktop pass (program select and Team Builder step 1 render).
