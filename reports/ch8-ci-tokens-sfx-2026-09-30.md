# Chapter 8 — token check into CI + SFX sweep

Branch `chore/ch8-ci-tokens-sfx` in `~/gob-audit`, from `origin/develop`. Sounds follow UX_System §3 / `uiSfx.js`. No new or renamed files under `FrontEnd/static/sounds/`.

## 1. CI gate

Sibling job next to `migration-gates` in `.github/workflows/test.yml`:

```yaml
  ui-tokens:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - name: Check UI token colour law
        run: python scripts/check_ui_tokens.py --strict --no-write
```

`scripts/check_ui_tokens.py` gained `--no-write`: summary only, no `reports/ui-token-audit-*.md`. CLAUDE.md “CI migration gates” now names this command.

Local run of the exact CI command:

```
.venv/bin/python scripts/check_ui_tokens.py --strict --no-write
```

Exit 0. Colour-law new 0 / 0 / 0. Legacy 263 / 789 / 0 (1052). No `Full detail:` line (report not written).

`tests/test_check_ui_tokens.py::test_no_write_skips_report` covers the flag.

## 2. SFX catalog (from the doc)

| Name | File | Use |
|---|---|---|
| `SFX_SELECT` | `click-tiny.wav` | tabs, toggles, close, links, rail |
| `SFX_ADVANCE` | `confirm-1-lowervol.wav` | `#play-now` via `data-sfx` only |
| `SFX_COMMIT` | `click-beep.wav` | save / confirm |
| `STING_WIN` | `sting-win.wav` | moments |
| `STING_MILESTONE` | `sting-milestone.wav` | gold milestone open |
| `STING_SEASON_PEAK` | `sting-season-peak.wav` | season-peak / championship open |

Elimination / losses: silent. `playSfx` already multiplies master × sfx (0 when either is muted).

## 3. Full SFX table

| Screen | Control | Expected | Current | Status |
|---|---|---|---|---|
| Shell | Rail items | `SFX_SELECT` | `playSfx('click-tiny.wav')` | ok |
| Shell | Sub-tabs | `SFX_SELECT` | `playClick()` | ok |
| Shell | Settings gear | `SFX_SELECT` | `playClick()` | ok |
| Shell | Tutorials | `SFX_SELECT` | `playClick()` | ok |
| Shell | Feedback | `SFX_SELECT` once | rail `playClick` + `#feedback-btn` `playSound` | **fixed** (rail no longer plays; forwarded click keeps one) |
| Shell | Exit Franchise | same as `#exit-franchise` | `x-back.mp3` via `playSfx` | ok (legacy filename, not in named catalog; goes through the bus) |
| Shell | `#play-now` Advance | `SFX_ADVANCE` once | `data-sfx="SFX_ADVANCE"` | ok |
| Shell | New-season Proceed | `SFX_COMMIT` or keep confirm? | `playSound('confirm-1-lowervol.wav')` | flag: uses Advance’s file on a second control |
| Settings | Close × | `SFX_SELECT` | none → `data-sfx` | **fixed** |
| Settings | Mute toggles | `SFX_SELECT` | none → `data-sfx` | **fixed** |
| Settings | Log Out | `SFX_SELECT` | none → `data-sfx` | **fixed** |
| Settings | FAQs / Account details | `SFX_SELECT` | none → `data-sfx` | **fixed** |
| Home Base | Enter / Resume (green) | `SFX_ADVANCE` | `data-sfx` | ok |
| Home Base | Other primary / links / tabs | `SFX_SELECT` | `data-sfx` | ok |
| Home Base | Slot ··· menu | `SFX_SELECT` | none → `data-sfx` | **fixed** |
| Home Base | Delete program… | `SFX_SELECT` | none → `data-sfx` | **fixed** |
| Home Base | Confirm delete | `SFX_COMMIT` | none → `data-sfx` | **fixed** |
| Home Base | Settings | `SFX_SELECT` | `data-sfx` | ok |
| Trophy Case | Back / Log Out | `SFX_SELECT` | `data-sfx` | ok |
| Trophy Case | Review | `SFX_SELECT` | none → `data-sfx` | **fixed** |
| Season peak title | Open | `STING_SEASON_PEAK` | `playSfx` | ok |
| Season peak title | Continue | `SFX_SELECT` | none → `data-sfx` | **fixed** |
| Season peak title | Box score | `SFX_SELECT` | none → `data-sfx` | **fixed** |
| Season review | Continue | `SFX_SELECT` | none → `data-sfx` | **fixed** |
| Milestone (gold) | Open | server `sting` | `playSfx` if gold | ok |
| Milestone (elim) | Open | silent | no sting | ok |
| Milestone | × / Next / Done | `SFX_SELECT` | none → `data-sfx` | **fixed** |
| Milestone | Explore archetypes / Full bracket | `SFX_SELECT` | none → `data-sfx` | **fixed** |
| Championship moment | Open | `STING_SEASON_PEAK` | `playSfx` | ok |
| Championship moment | Back to Locker Room / Box Score | `SFX_SELECT` | none → `data-sfx` | **fixed** |
| Leave confirm | Keep / Discard | `SFX_SELECT` | `playSfx` + would double with hook | **fixed** (`data-sfx` only) |
| Leave confirm | Save | `SFX_COMMIT` | silent → `data-sfx` | **fixed** |
| Shared tabs | Tab buttons | `SFX_SELECT` | `playSfx('click-tiny.wav')` | ok |
| Office weekly card | Result / highlight links | `SFX_SELECT` | `playSelect()` via `go()` | deferred: office |
| Office weekly card | +N more toggle | `SFX_SELECT` | none | deferred: office |
| Office weekly card | Win sting | `STING_WIN` | `playSfx(STING_WIN)` on win only | deferred: office (loss stays silent) |
| Office | other weekly / digest clicks | `SFX_SELECT` | `clickTiny` | deferred: office |
| Prep Training | tabs / save / start | `SFX_SELECT` / `SFX_COMMIT` / `SFX_ADVANCE` | `playSound` in `training.js` (incl. non-catalog files) | deferred: stats |
| Prep Game Plan | sliders / save / PLAY NOW | `SFX_SELECT` / `SFX_COMMIT` / `SFX_ADVANCE` | `playSfx` / `playAdvance` in `game-plan.js` | deferred: stats |
| Prep Playbooks | toggles / Save | `SFX_SELECT` / `SFX_COMMIT` | `click-tiny` / `confirm-2-lowervol.wav` in `playbooks.js` | deferred: stats |
| Prep Scouting | close | `SFX_SELECT` | `new Audio('x-back.mp3')` bypasses settings | deferred: stats |
| Prep Training Report | tabs / actions | `SFX_SELECT` | `click-tiny` / `click-strong.wav` | deferred: stats |
| Prep views (`*View.js` / `prepEmbed.js`) | — | — | no `playSfx` | deferred: stats |

## 4. Flags

**Double for one action**

- Rail Feedback used to play `SFX_SELECT` in `gobShell` and again from `#feedback-btn`. Rail no longer plays; one call remains.
- Advance `#play-now` is `data-sfx` only (no handler `playSfx`). Existing e2e still asserts one `SFX_ADVANCE`.
- Leave confirm Keep/Discard dropped the extra `playSfx` when `data-sfx` was added.

**Loss path**

- Milestone elimination: no sting (already). Close still uses `SFX_SELECT` (a click, not a loss sting).
- Office weekly card plays `STING_WIN` only when `user_won === true`. Loss card is silent. Deferred: office.

**Reserved sound on the wrong control**

- New-season Proceed plays `confirm-1-lowervol.wav` (`SFX_ADVANCE`). The doc reserves that for `#play-now`. Left as-is (second step of the Advance flow). Not changed.

**Settings bypass**

| Caller | Path | Settings? |
|---|---|---|
| All `playSfx` / `data-sfx` / `playSelect` / `playAdvance` / `playCommit` | `uiSfx.js` `outputVolume` | yes |
| `scoutingReport.js` close | `new Audio('/sounds/x-back.mp3')` | **no** — deferred: stats |
| Court `gameSfx.js` / announcements / airhorn / timeout | own `Audio()` | court bus (`courtAudio.js`); leave until moved |
| `mode-select.js` / team-select lobby music | own `Audio()` | music, not UI sfx; leave |

**Missing / extra files (none added)**

Named catalog files already exist. Extra files already used through `playSfx` (do not add): `x-back.mp3`. Deferred Prep files not in the catalog: `confirm-2-lowervol.wav`, `click-strong.wav`, `chaotic-choice.wav`, `whistle-3.mp3`, `positive-slide.wav`, `positive-plop.wav`, `positive-beep.wav`. Did not add or rename any sound file.

## 5. Fixes made

- `data-sfx` on Home Base menu / delete / confirm-delete; Trophy Case Review; Season Peak Continue + box score; Season review Continue; Milestone × / Next / links; Settings close / mute / logout / FAQs / account; Championship moment buttons; Leave confirm buttons.
- Leave confirm: remove handler `playSfx` so the hook is the only play.
- Rail Feedback: one sound.
- `playSfx` records `window.__gobSfxCalls` after the volume check (e2e spy).

## 6. Deferred per agent

**Office:** `office-home.*`, `officeHome.js`, weekly-card `+N more` (no sound), weekly-card link `playSelect`, `STING_WIN` on win. `gob_nav` / alpha-badge untouched.

**Stats:** `prepEmbed.js`, `trainingView` / `trainingReportView` / `gamePlanView` / `playbooksView` / `scoutingView`, training / game-plan / playbooks / training-report HTML + their standalone JS (`training.js` extra files, `game-plan.js` PLAY NOW `playAdvance`, `playbooks.js` `confirm-2-lowervol.wav`, `training-report.js` `click-strong.wav`, `scoutingReport.js` raw `Audio()`).

## 7. Tests

`tests/e2e/ch8-ci-tokens-sfx.spec.js` clicks Settings close, Season Peak Continue, Milestone Next, Leave-confirm Keep Editing. Each expects exactly `['SFX_SELECT']`. Sfx muted: `[]`.

Proved against old code: removing `data-sfx` from `.pk-go` made Continue return `[]`.

## 8. Files

- `.github/workflows/test.yml`
- `CLAUDE.md`
- `scripts/check_ui_tokens.py`
- `tests/test_check_ui_tokens.py`
- `tests/e2e/ch8-ci-tokens-sfx.spec.js`
- `FrontEnd/static/js/shared/uiSfx.js`
- `FrontEnd/static/js/shared/homeBase.js`
- `FrontEnd/static/js/shared/trophyCase.js`
- `FrontEnd/static/js/shared/seasonPeak.js`
- `FrontEnd/static/js/shared/milestoneModal.js`
- `FrontEnd/static/js/shared/gobSettings.js`
- `FrontEnd/static/js/shared/gobLeaveConfirm.js`
- `FrontEnd/static/js/shared/championshipMoments.js`
- `FrontEnd/static/js/shared/gobShell.js`

## 9. Gates

- `pytest --ignore=tests/e2e`: 4137 passed, 14 skipped, 109 xfailed, 1 xpassed, 0 failed
- Playwright (`workers=1`, `PORT=8197`, `CI` unset): 742 passed, 3 skipped, 0 failed
- `scripts/check_ui_tokens.py --strict --no-write`: exit 0
- `scripts/ci/check_migration_gates.py`: pass (Gate A 0/0, Gate B 138/46). No `--write-allowlist`.

## Unsure

- New-season Proceed using Advance’s confirm file: flagged, not changed.
- Elimination modal close still plays `SFX_SELECT`. If “loss path” means every click on that modal is silent, that is a later call.
- Exit Franchise keeps `x-back.mp3` (doc: “same sound”).
