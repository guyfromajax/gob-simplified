# Play-flow pages on gob tokens + TeamPicker cleanup: 2026-10-01

Batch 3 of `reports/ux-remaining-map-2026-10-01.md`. Branch `ux/play-flow-tokens` from `origin/develop` (`4ed72345c`), in `~/gob-audit`; upstream unset. `git fetch origin && git merge origin/develop` right before push: already up to date (develop did not move), so `NEW_DESIGN_CSS` is unchanged apart from this branch's three additions.

## Scope

| Page | Sheet | Before (colour literals / law hits) | After |
|---|---|---|---|
| `training-playbooks.html` (Training → custom playbook) | `training-playbooks.css` | 53 / 10 | tokens, 0 law hits |
| `playbook-report.html` (Playbook Settings) | `playbook-report.css` | 40 / 12 | tokens, 0 law hits |
| `player-detail.html?recruit_id=…` (recruit detail) | `player-detail.css` + `player-detail.js` | 55 / 3 (+ JS 12 / 4) | tokens, 0 law hits |

All three sheets are in `NEW_DESIGN_CSS` (strict).

**Skipped as instructed:**
- `play-details.html` (the in-app inspector decision is pending).
- The Expected Shot Distribution pills: `getPswColor` in `common.js:1225` and its copy in `playbooks.js:315`, the `set-lineup.js:602` fallback, and the `.psw-*` rules in `resource-pages.css`. None of the three pages renders them.

**Visual only:**
- **HTML:** `class="gob"` and the `gob-tokens.css` link replacing `resource-pages.css`.
- **JS:** `player-detail.js` has only the position-pill colour constants changed; no fetch, id or logic. No other page script changed.

## Peeled off `resource-pages.css`

None of the three pages loads `resource-pages.css` any more. A grep of each page's HTML and JS against the sheet's selectors showed they use only:
- the brand shell: `.resource-page-container`, `.fcc-brand-page-shell` and its `::before`/`::after`, `> *`;
- the shell `h1` rules;
- `.brand-back-link` (playbook-report only).

The sheet sets no global element rules.

Those rules are copied to the top of each page sheet with the **same selectors** (so specificity and order resolve exactly as before), on tokens. Geometry is pinned: the spec measured shell x, width, padding, corner radius and `h1` size/margin on develop (`tests/e2e/fixtures/play-flow-before-metrics.json`), and the AFTER run must equal it at 1280 and 1920 (it does). The shell is not the formula `min(1400px, 100vw − 24px)` in practice (1244px at 1280), because the gob shell wraps these pages, so the guard uses the measured numbers.

## Colour law applied

| Element | Before | After |
|---|---|---|
| Save & Continue (`.tp-btn-primary`), "Playbooks Saved" toast accent | orange | orange, annotated `saved` (both save) |
| Selected play card + check (`.tp-card.is-selected`) | orange | **navy** (selection, as Team Builder / program select) |
| PCC chip (`.tp-chip-pcc`), dock share bar | orange | neutral |
| "At least 1 required" (`.tp-warn`) | orange | `--red` (invalid, as Team Builder) |
| Edit Playbooks (`.report-btn-primary`) | orange gradient | neutral white plate (navigation) |
| Report section rules / subheads | orange | neutral |
| `.report-row.is-highlight` | orange | neutral. **Dead:** `playbook-report.js` never sets it |
| Recruit overall grade, primary position value, section-header rule | orange | `--text-100` / neutral rule |
| Position pills (PG/SG/SF/PF/C) | per-position blue/purple/green/red/gold | neutral (information codes, as Team Builder's position chips) |
| Recruit page glow, panel surfaces | navy glow, navy-tinted panels | neutral lift, `--surface-1/2` |
| CMD bars (`.tp-cmd-fill`: yellow < 50, green 50–79, blue 80+) | literals | `--tier-yellow` / `--tier-green` / `--blue`, **hues unchanged** |
| Attribute and position-rating bars (recruit) | shared RT ramp | unchanged |

**Open question this relies on:** the CMD ramp's blue on a non-RT value is the same question as `getPswColor` (blue is RT only). I left the hues and flagged it; it moves with that ruling. `#747474` (portrait placeholder) has no token and stays.

## TeamPicker cleanup (done)

Grep run before deleting:

```
$ grep -rn "team-picker\.css\|team-picker\"" FrontEnd BackEnd desktop tests scripts
(no output)
$ grep -rn "TeamPicker\.mount" FrontEnd --include=*.js --include=*.html | grep -v vendor
FrontEnd/static/js/shared/teamPicker.js:249:    if (!rootEl) throw new Error('TeamPicker.mount requires a root element');
$ for each export: grep -rln "TeamPicker\.<name>" FrontEnd/static tests desktop (excluding teamPicker.js)
mount                      (none)
fetchTeams                 team-builder.js franchise-select-team.js tests/e2e/program-select-tokens.spec.js
teamObjectId               (none)
formatConferenceLabel      team-builder.js js/team-builder/review.js
formatConferenceMeta       (none)
regionFromConference       team-builder.js franchise-select-team.js js/team-builder/establish.js js/team-builder/review.js
geographyForConference     franchise-select-team.js
formatGeographyList        franchise-select-team.js
distinctGeographies        franchise-select-team.js
conferencesForGeography    (none in FrontEnd; scripts/tb_phase2_team_select.mjs uses it)
assignRankBands            franchise-select-team.js
bandSizeHistogram          (none in FrontEnd; scripts/tb_phase2_team_select.mjs uses it)
```

- **Deleted:** `FrontEnd/static/css/team-picker.css` (438 lines).
- **Removed from `js/shared/teamPicker.js`:** `mount` (552 lines) and the helpers referenced only inside it: `escapeHtml`, `formatInt`, `assetPath`, `playClick`, `compareTeams`, `HEIGHT_BAND_LABELS`, `CLASS_BAND_LABELS`.
- **Export:** the `mount` export is gone. 816 → 212 lines.
- **Kept:** every data helper and export, including the ones only `scripts/tb_phase2_team_select.mjs` uses, plus `teamSortId` / `numericField` / `normalize*`, which `assignRankBands` and the geography helpers use. The header comment is updated.
- **Checks:**
  - `node --check` passes.
  - A Node sandbox load exercised `regionFromConference`, `formatConferenceLabel`, `distinctGeographies`, `conferencesForGeography`, `assignRankBands` and `bandSizeHistogram`.
  - The specs for every page that loads `teamPicker.js` pass: `desktop-play-flow`, `program-select-tokens`, `shared-chrome-tokens`, `team-builder-tokens`, and `play-flow-tokens` itself: 13 passed.

## Shots

`reports/play-flow-tokens/{before,after}-<surface>-{1280,1920}.png`, via `page.screenshot` at scroll 0. BEFORE was captured on develop CSS before any edit (`PLAY_FLOW_BEFORE=1`). Surfaces: `training-playbooks`, `training-playbooks-selected` (a selected card plus the red "At least 1 required"), `playbook-report`, `recruit-detail`. Data: `/api/playbooks` from `tests/e2e/fixtures/prep-plan.json`, a stubbed recruit, and stubbed `/franchise/play-next-game` (playbook-report POSTs it on load).

## Tests

- `tests/e2e/play-flow-tokens.spec.js`: shots + guards:
  - pinned shell geometry and title type vs develop;
  - `html.gob`; no `resource-pages.css`; neutral shell surface;
  - selected card navy and not orange; check, PCC and dock fill not orange;
  - Save orange; warning red;
  - Edit Playbooks, report rules/subheads and back link neither orange nor green;
  - recruit grade, primary value and header not orange; position pills untinted.
- **Fails on old code:** ran the guards (soft) with develop's 3 css + 3 html + `player-detail.js` served via `page.route` from a scratchpad config. They fail on all three pages:
  - `selected card navy …rgba(247,148,32,0.35)`, `check`, `PCC chip`, `dock fill`;
  - `report edit linear-gradient(…247,148,32…)`, `report h2`, `report h3`;
  - `recruit overall`, `recruit primary`, `recruit header`;
  - all five `position pill neutral` (e.g. `rgb(192,57,43)`);
  - `* no longer loads resource-pages.css`.

  Save orange and warning red pass on both (both legal).

## Gates

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` | **4298 passed**, 14 skipped, 108 xfailed, 2 xpassed, **0 failed** (239.39s). Same two XPASS as before. |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 (no pipe) |
| `scripts/ci/check_migration_gates.py` | passed. Gate A 0/0, Gate B 134 lines in 43 files. No `--write-allowlist`. |
| Playwright full `tests/e2e --workers=1` under `/tmp/gob-full-playwright.lock` (PORT=8244), code commit `748058883` | **822 passed, 7 skipped, 0 failed** (13.8m). No failures, so no reruns. Skips: 5 existing `test.skip`s plus 2 "handoff frames" tests that skip without `FRAMES_BASE`. |
| Merge `origin/develop` before push | already up to date |

## Files

`FrontEnd/static/training-playbooks.{css,html}`, `playbook-report.{css,html}`, `player-detail.{css,html,js}`, `js/shared/teamPicker.js`, `css/team-picker.css` (deleted), `scripts/check_ui_tokens.py` (`NEW_DESIGN_CSS` + docstring), `_documentation_master/11_Design_Systems/UX_System.md` ("Play-flow pages" section; team-picker note updated), `tests/e2e/play-flow-tokens.spec.js`, `tests/e2e/fixtures/play-flow-before-metrics.json`, this report + shots.
