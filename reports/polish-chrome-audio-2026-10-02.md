# polish/chrome-audio — 2026-10-02

Branch `polish/chrome-audio` from `polish/flow-bugs` (`cc9a91aba`). Gates ran on the merged tree `56a9f970b` (`origin/develop` @ `4046ff480` merged in). Ready for review.

## Items

| # | Item | Status | What changed |
|---|---|---|---|
| B1 | Remove "Blocks Advance" from the week strip | **done** | The tag is gone. The blocking step keeps its strong neutral outline. |
| B2 | Top strip in tournament weeks (Jamie's revised brief) | **done**, one question | Weeks 27-34 show **no week number**. In its place: the tier emblem, `<Tier> Tournament`, and the round under it (`First Round` / `Semifinals` / `Championship`, the Advance button's own words). Weeks 1-26 unchanged. Nothing sits beside the action button. |
| B3 | Champs overlay copy | **done**, one question | "Regular Season Conference Champions" and "Conference Tournament Champions". The eyebrow is "Season N" only. |
| B4 | Office "03 Recruiting": list the signed class | **done**, see note | After Signing Day has run the column is a "Signing class" card: one row per signed recruit (name, position, home region, RT now → ceiling), with a count. |
| B5 | Mode Select career strip | **done** | The four numerals take the whole left column, spaced by their own content, no dividers. Trophy Case moved to the utility row. Last Played untouched. |
| B6 | Unsaved-changes modal | **done** | Save across the top (the only orange); Discard Changes and Keep Editing side by side beneath it, equal, neutral. 460px. Same three actions and behaviour. |
| B7 | Settings stats | **done** | Tiles size to their content (271–168 and 1271–1168 fit). "National Titles" after "Titles". Heading is "Stats". |
| B8 | Audio controls | **done**, one question | Settings has two switches, Music and Sound, and no sliders. They control all non-gameplay audio and nothing else does. Gameplay audio is the court's. The Account page's ambience switch is removed. |
| B9 | Sim Game: Sound switch | **done** | The Highlights toggle is a Sound switch. Highlights are always on. The setting is stored and the next game starts as the player left it. |

Nothing skipped.

## Questions for Jamie

| # | Question | What I did |
|---|---|---|
| 1 | **B2, weeks 35 and 36.** "From week 27 onward no week number" — 35 (Signing Day) and 36 are not tournament rounds, so there is no round to show. | They still read "Week 35" / "Week 36". Say what they should read ("Signing Day"? "Offseason"?) and it is one line. |
| 2 | **B2, round words.** The top strip uses the Advance button's words ("Region Tournament / First Round"). `tierEmblem.js` also has an unused, different vocabulary (QUARTERFINAL / SEMIFINAL / CHAMPIONSHIP, "per PM decision"), where week 30 is a SEMIFINAL. | Used the button's words so the strip and the button beside it agree. If the normalised words are the ones you want, the button labels should change with it. |
| 3 | **B3, region and national.** You named the two conference overlays. | Region and National also lose the "Region Tournament" / "National Tournament" eyebrow line, so all four read "Season N". Headlines "Region Champions" / "National Champions" unchanged. The medallion label under the headline now uses the same new wording. Trophy Case and the season review keep their old medallion labels ("Conference Champions", "Conference Regular-Season #1"): not asked, say if they should follow. |
| 4 | **B8, the court popover.** "No volume sliders" is written under the Settings sentence. | Settings has no sliders. The court's command-center control still has its Mute all switch and Music / SFX sliders, now for gameplay audio only. Say if those should become on/off switches too. |
| 5 | **B4, which week.** Running Signing Day moves the franchise from week 35 to week 36, so "after recruiting has run in week 35" is the week-36 Office. | The list shows at week 36, and only once the hub's reveal has played (same gate as the signed-class moment, so the Office never shows the class before the live beat). |

## B8 / B9: how the audio is built

One bus (`uiSfx.js`), two scopes, one stored record (`gob_audio_v1`). The scope is the page.

| Scope | Where | Controlled only from |
|---|---|---|
| `game` | `court.html` (played game and Sim Game) | The command-center sound control; the Sim Game Sound switch (the same mute) |
| `app` | every other page | Settings: Music, Sound |

- **Music** = franchise track, timeout loop (Set Lineup / Game Plan), Home Base track, lobby track on team select and the persona intro.
- **Sound** = clicks, Advance, commit, stings.
- The scopes never touch each other (tested both ways).
- Turning Music off pauses the franchise track; turning it on starts it again on the page you are on (tested with a recording `Audio`).
- An existing player's record migrates: anything they had silenced in the old panel stays off.

Audio that bypassed the bus, now on it:

| Sound | Was |
|---|---|
| Lobby music on team select and the persona intro | fixed volume 0.4, ignored every setting |
| Quarter-end airhorn, whistle, timeout click and airhorn | fixed volume, ignored the court's Mute all |

Other controls removed: Settings Master and Ambience rows, the four sliders, the four mute buttons (a muted one was red, which the colour law bans), and the Account page "Scouting Ambience" switch. I found no other audio control in the app.

Two copies of the bus can be alive on the court (localhost serves the Phaser tree from `/static` and the shell from `/js`). They now re-read the stored record when the other announces a change, so a control writes once.

## Files

| Area | Files |
|---|---|
| B1, B4 | `js/shared/officeHome.js`, `css/office-home.css`, `BackEnd/utils/office_digest.py` (`signed_class_digest`) |
| B2 | `js/shared/gobShell.js`, `js/shared/gobAdvance.js` (`eosRoundForWeek`), `franchise-command-center.js` (emblem only), `css/gob-shell.css` |
| B3 | `js/shared/seasonPeak.js` |
| B5 | `js/shared/homeBase.js`, `css/home-base.css` |
| B6 | `js/shared/gobLeaveConfirm.js`, `css/gob-components.css` |
| B7, B8 | `js/shared/gobSettings.js`, `js/shared/uiSfx.js`, `css/gob-components.css`, `account.html`, `js/musicController.js` (comment), `franchise-select-team.js`, `tutorial-persona-intro.js`, `js/phaser/utils/quarterEndAirhorn.js`, `announcements.js`, `timeoutButtonManager.js` |
| B9 | `js/phaser/utils/simGamePresentation.js` |
| Docs | `UX_System.md` (§3 Audio rewritten, §4, §5, §6, §10, §12, Program select), `Styleguide.md` |
| Tests | new `tests/e2e/polish-chrome-audio.spec.js`, `helpers/officeFixtures.js`, `helpers/homeBaseFixtures.js`; `tests/test_office_digest.py`, `tests/test_ui_sfx.mjs` |

Not touched: Training, Training Report, Playbooks, Game Plan, Set Lineup, League, Team, Team Pages, Scouting Report, News, Schedule, Recruiting Results, `gob-tables.css`, sim / finalize / `cpu_week_pool` / `sim_rng`. `franchise-command-center.css` is still 1779 lines. B6 changes only the shared modal; Game Plan, Playbooks and Training call it unchanged (their labels, e.g. Training's "Keep Draft", still arrive through `saveLabel`).

## Tests

`tests/e2e/polish-chrome-audio.spec.js`: 26 tests. Against the branch-1 product files **23 of the first 25 fail**; the two that pass are the regular-season week (unchanged by design) and a four-digit-record check that I then tightened. All pass on the branch.

| Item | Covered by |
|---|---|
| B1 | no `.td-gate`, blocking step still outlined |
| B2 | week 22 reads "Week 22", no emblem; weeks 27-34 each: no week number in the strip, `<Tier> Tournament` + round, emblem beside (not over) the words, all inside the bar, space beside Advance empty; a browse page (recruiting) paints the same |
| B3 | four overlays: headline and "Season 3" eyebrow |
| B4 | rows, count, grade now → ceiling, long name not clipped, empty class, no payload keeps the wire; `test_office_digest.py`: three server tests |
| B5 | cells at least 24px apart, none clipped, no dividers, strip spans the column, Trophy Case in the utility row, Last Played still there, nothing below the fold |
| B6 | three actions, one line each, Save full width and the only orange, the other two equal, Keep Editing focused |
| B7 | labels and order, 271–168 and 1271–1168 inside the tile |
| B8 | two switches only; Sound off silences `playSfx`; Music off silences music and pauses the franchise track; game channels untouched; persists; Account has no switch |
| B9 | Sound switch, no Highlights toggle, mutes gameplay audio on every bus copy, stored, restored next game, highlights not suspended, separate from Settings |

`tests/test_ui_sfx.mjs` (run with `node --test`): scopes, separation, migration.

Existing tests changed because they asserted the behaviour these items replace:

| Spec | Was asserting |
|---|---|
| `office-frontend`, `jamie-rulings-batch-2` | the BLOCKS ADVANCE tag |
| `shell-1` | week 28 shows no phase label |
| `champ-moment-repeat` | the old overlay headlines |
| `foundation-settings` | sliders and mute buttons in Settings |
| `reward-gold-sfx` | a master level outside the court |
| `names-recruit-colour`, `shared-chrome-tokens` | the Account ambience switch |
| `sim-broadcast-fit` | the Highlights toggle |

## Shots (`reports/polish-chrome-audio/`, 1280)

| Item | Before | After |
|---|---|---|
| B1 | `b1-week-strip-before` | `b1-week-strip-after` |
| B2 | `b2-top-strip-week-{22,27,31,34}-before` (week 27 clipped by the emblem) | `b2-top-strip-week-{22,27,31,34}-after` |
| B3 | `b3-overlay-{regular-season,conference-tournament}-before` | `…-after` |
| B4 | `b4-signed-class-before` | `b4-signed-class-after` |
| B5 | `b5-mode-select-before` | `b5-mode-select-after` |
| B6 | `b6-unsaved-modal-before` | `b6-unsaved-modal-after` |
| B7, B8 | `b7-b8-settings-before`, `b8-account-before` | `b7-b8-settings-after`, `b8-account-after` |
| B9 | `b9-sim-game-before`, `b9-sim-toggle-before` | `b9-sim-game-after`, `b9-sim-toggle-after` |

## Unsure

- B8 changes what an existing player hears only if they had muted something in the old panel (it stays muted). Levels set in the old Settings sliders are not carried into the app scope, because it has no levels.
- B7: with three tiles the Stats row is one line; a very long record wraps the tiles rather than shrinking them.
- The quarter-end airhorn has a Jest file (`js/phaser/utils/tests/quarterEndAirhorn.test.js`) that is not part of any gate I ran. The module now imports the bus; I did not run Jest.

## Gates (merged tree `56a9f970b` = branch + `origin/develop` @ `4046ff480`)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | 4320 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed. Both XPASS are pre-existing; `known_failures.py` not edited. |
| `check_ui_tokens.py --strict --no-write` | exit 0 |
| `check_migration_gates.py` | passed (Gate A 0, Gate B 134 lines / 43 files) |
| Full Playwright, once, lock held 11:36-11:53 | **952 passed, 16 skipped, 0 failed** (968 tests, 16.6 min, 1 worker). Nothing to re-run. |
