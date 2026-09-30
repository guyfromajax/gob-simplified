# End-of-Chapter-8 dead-code sweep — 2026-09-30

Branch `chore/ch8-dead-code-sweep` off `origin/develop` (`6587c3cba`). Worked only in `~/gob-audit`.

Evidence bar: static miss across `FrontEnd/static` html/js/css (incl. template strings), `BackEnd`, `desktop/`, `netlify.toml`, `_redirects`, `tests` — plus runtime for anything page-reachable. Removed only what's provably dead.

## Removed (grouped, with evidence)

### FrontEnd/ root leftovers (never served)

Netlify publishes `FrontEnd/static`. FastAPI mounts the same dir. These four HTML files and their companions sit **outside** `static/` and have **zero** refs in `FrontEnd/static`, `BackEnd`, `desktop/`, `netlify.toml`, `_redirects`, or `tests`. Coverage-gap-check already marked them DEAD.

| File | Lines | Evidence |
|---|---|---|
| `FrontEnd/games.html` | 21 | Only loads `app.js` + `style.css` (same folder). Never published. |
| `FrontEnd/app.js` | 160 | Only referenced by `games.html`. |
| `FrontEnd/style.css` | 26 | Only referenced by `games.html`. |
| `FrontEnd/index_legacy.html` | 163 | Internal link to `roster.html`. Never published. |
| `FrontEnd/player.html` | 87 | Never published. Not `static/player-detail.html`. |
| `FrontEnd/roster.html` | 56 | Loads `/static/roster.js` (file is actually `FrontEnd/roster.js`, also unpublished). |
| `FrontEnd/roster.js` | 303 | Only referenced by `FrontEnd/roster.html`. Not `js/team-builder/roster.js`. |

### Homepage extract leftovers

Live `homepage.html` and `homepage-v3.html` **inline** CSS and JS. `package.json` `"sync:homepage"` is only `cp homepage.html homepage-v3-source.html`. None of these four files are `<link>`ed or `<script>`ed from any HTML, `BackEnd`, `desktop`, Netlify, or tests.

| File | Lines | Evidence |
|---|---|---|
| `FrontEnd/static/homepage.js` | 10 | Mouse/keyboard focus helper. Not loaded. |
| `FrontEnd/static/homepage.css` | 216 | Old light homepage sheet. Not loaded. |
| `FrontEnd/static/homepage-v3.css` | 868 | Extract of inlined v3 CSS. Not loaded. |
| `FrontEnd/static/homepage-v3.js` | 200 | Sticky-nav / FAQ extract. Not loaded. Live pages keep the inline scripts. |

**Kept:** `homepage.html` (canonical `/`), `homepage-v3.html` (authGuard public + `tests/e2e/homepage-v3-auth.spec.js`), `homepage-v3-source.html` (`sync:homepage` write target).

### Redirect-stub companion

`index.html` is a `location.replace('/homepage.html')` stub. The leftover body was the old "Game Time!" team-picker (never painted; redirect runs in `<head>`). `team-select.js` was only loaded by that leftover body.

| File | What |
|---|---|
| `FrontEnd/static/index.html` | Slimmed 127 → 11 lines (same stub pattern as `stats.html`). |
| `FrontEnd/static/team-select.js` | 173 lines. Zero callers after the slim. |

`_redirects` already rewrites `/` → `/homepage.html 200!`. Slimming `/index.html` does not change that.

### One unused CSS alias

`recruiting-spine.css` `:root` had `--lblue:var(--blue);`. Defined once, never consumed in that sheet (or by hub/signing/dock/results CSS). Other `--lblue` uses live in tutorial/advanced sheets that define their own token. Removed the one alias line.

## Kept-and-why

| Candidate | Decision | Why |
|---|---|---|
| `recruiting-lean-ladder.css` | **KEEP** | Task said "unlinked" — that is false. `franchise-command-center.html:22` links it. `recruiting-common.js` + `RecruitingSpine.Lean.ladderHtml()` emit `.lean-b` / `.lb-slot` markup on FCC. |
| `css/team-picker.css` | **UNSURE — do not wire or delete** | Never `<link>`ed. `teamPicker.js` + franchise-select-team / team-builder emit `.team-picker-*` markup that this sheet styles. Missing link is a wiring gap. Don't guess. |
| `js/shared/coachMark.js` + `css/coach-mark.css` | **KEEP** | Zero live imports. `fte_system.md` documents it as an unused primitive kept for future tutorials. Listed, not deleted. |
| `homepage-v3-source.html` | **KEEP** | `sync:homepage` destination. |
| `homepage.html` / `homepage-v3.html` | **KEEP** | Live marketing pages. |
| `player-detail.js` / `.css` | **KEEP** | `player-detail.html` still serves recruit mode (`mode=recruit` / `recruit_id` skips the FCC redirect) and loads both files. `recruiting-common.js` builds recruit-mode links. |
| `team-roster-view.html` + `.js` | **KEEP** | Dual-mode: franchise URLs redirect to FCC; `mode=practice_squad` + `ps_team_id` still paints the page. |
| Playbook `.et` / `.chip-*` / `--cmd-*` | **SKIPPED** | Stats-agent files (`playbook-tiles.css`, `playbook-cmd.css`). Not touched. |
| set-lineup / training / playbooks / game-plan / scouting / court / Phaser / sim / sounds | **NOT TOUCHED** | Per brief. |

## Unused JS exports (static pass — listed, not deleted)

Scanner: `export function` in `FrontEnd/static/js` (not Phaser). Zero extra name hits after subtracting the defining file.

| Export | File | Why not deleted |
|---|---|---|
| `showCoachMark` | `js/shared/coachMark.js:81` | Documented unused primitive (see above). |
| `bindGobDensityAll` | `js/shared/gobDensity.js:23` | On `window.GOBDensity`. Public helper. |
| `resumeTimeoutLoop` | `js/musicController.js:442` | Called inside the same file. |
| `mountCourtAudio` / `mountCourtAudioWhenReady` | `js/shared/courtAudio.js` | Self-mount + `window.GOBCourtAudio`. Court — don't touch. |
| `renderRichLines` | `js/shared/newsStory.js:91` | Called by `renderStoryBody` in the same file. |
| `installSfxHooks` / `playCommit` | `js/shared/uiSfx.js` | Self-installed / re-exported. |
| `sectionLabel` / `pageLabel` | `js/shared/views/detailBar.js` | Same-module helpers. |
| `prefetchOpponentReport` | `js/shared/views/scoutingView.js:144` | Called from `mount` in the same file. Scouting — don't touch. |

No function-level deletes. The rest of the export surface has callers.

## Unused FastAPI routes (DO NOT DELETE — for Jamie)

Zero frontend / test / desktop / script callers. Handler file:line and last git touch. Sim / finalize / cpu_week_pool / sim_rng untouched.

| Route | Handler | Last git touch | Notes |
|---|---|---|---|
| `POST /franchise/save-result` | `BackEnd/api/franchise_routes.py:5797` | `a72f776e2` 2025-08-10 "feat: save franchise game results" (`@marks_last_played` added `bc554ace39` 2026-09-28) | No `FrontEnd` / `desktop` / `tests` / `scripts` caller. Live save path is elsewhere. |
| `POST /franchise/delete-current` | `BackEnd/api/franchise_routes.py:10116` | `f2462b8e7` 2026-02-02 "added delte franchise functionality" | Sibling `DELETE /franchise/current` (same commit, next line) **is** live (`mode-select.js` deletes `/franchise/{id}`). This POST alias has no caller. |
| `GET /franchise/team-traits` | `BackEnd/api/franchise_routes.py:12053` | `8887f4ffc` 2026-01-18 "Add Team Traits tab to Franchise Command Center" | `team-traits.html` is now a redirect stub. No JS fetches this API. Team Attributes view uses `/franchise/team-data`. |
| `GET /franchise/latest-training` | `BackEnd/api/franchise_routes.py:16324` | `e66fee7aa` 2025-10-09 "Add Training tab… with latest session results" | No frontend caller. Training report uses `/franchise/training-report` / `latest-training` is leftover. |
| `GET /startup-error` | `BackEnd/api/api.py:8731` | `c38c4da14` 2026-02-05 "used Sentry to fix the bug" | Only registered if app **startup throws**. Not a product route. |

**Not unused (listed so the scanner miss is explicit):** `POST /api/billing/webhook` (`billing_routes.py:41`, `7133031e6` 2026-09-06) has zero frontend callers because it is a Stripe inbound receiver. Keep.

## Lines removed per area

| Area | Files | Net lines |
|---|---|---|
| FrontEnd/ root leftovers | 7 deleted | −816 |
| Homepage extract leftovers | 4 deleted | −1,294 |
| Redirect-stub slim (`index.html` + `team-select.js`) | 1 slim + 1 deleted | −293 |
| Recruiting spine unused alias | 1 line | −1 |
| **Total** | | **2 insertions, 2,402 deletions** |

## Pixel-diff

42 pairs, 1280×720, web + desktop (`GOB_BUILD_PROFILE=desktop`). Chrome for Testing chromium-1200. `document.fonts.ready`. Mocked API. FCC 18 views + Recruiting + Home Base + Trophy Case.

| Pair | % | Note |
|---|---|---|
| 40 pairs | **0.000%** | Identical. |
| `web-prep-training` | **0.077%** | Same painted card; subpixel / webfont flicker on the training-submitted panel. Recaptured twice; stays ~0.08%. Under 0.5%. |
| `desktop-prep-training` | **0.004%** | Same class as web training. Under 0.5%. |

First `desktop-prep-game-plan` after-shot was 33.6% because the **before** frame caught the skeleton (empty bars) before the view painted. Recaptured both phases with a wait for game-plan content → **0.000%**. Not a restyle.

Recruiting 0.000% after dropping unused `--lblue` (nothing painted with it). Home Base and Trophy Case 0.000% web + desktop.

## Gates

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` | **4229 passed**, 16 skipped, 109 xfailed, **1 xpassed**, **0 failed** (242s) |
| Full Playwright `PORT=8187`, `CI` unset, workers=1 | **757 passed**, 5 skipped, **0 failed** (11.0m) |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0**. Colour-law new = 0, legacy = 786 (204 green / 582 orange / 0 reward-gold) |
| `scripts/ci/check_migration_gates.py` | **passed**. Gate A: 0 imports in 0 files. Gate B: **138 lines / 46 files** (unchanged). Did not run `--write-allowlist`. |

XPASS (not edited in `known_failures.py`): `tests/test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference` — same pre-existing xpass as redirects-fcc-leftovers.

## Self-check

- Worked only in `~/gob-audit`. Did not switch branches elsewhere.
- Did not touch set-lineup, training/playbooks/game-plan/scouting files, court.html, Phaser, sim, sounds.
- Did not delete unused FastAPI routes.
- Did not wire or delete `team-picker.css`.
- Did not invent a design call on the team-picker wiring gap.
- Module views still read identity from `window.FranchiseContext.get(key)`.
- Did not `git add .`. Sounds, `.DS_Store`, other agents' report trees are not in this commit.

STATUS: COMPLETE
