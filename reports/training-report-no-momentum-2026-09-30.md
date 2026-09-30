# Training Report no Momentum + Class Signed hairline + playbooks fixture + reward-gold allow-list

Branch `fix/training-report-no-momentum` in `~/gob-audit`, from `origin/develop` after `git merge origin/develop` (`6f0bbcf18`). Display-only and checker work. Sim, stored `momentum_score`, and the Training Report API payload are unchanged.

## 1. Training Report Team Report — drop Momentum

`renderTeamAttributes` in `FrontEnd/static/training-report.js` listed twelve measures. Jamie: same eleven as Team Attributes. Removed `momentum_score` from `attrOrder` only. The label map still has `Momentum`; the payload can still carry `momentum_score`.

The unused `renderScoutingTeamReport` in `FrontEnd/static/js/shared/scoutingReport.js` used the same list. Dropped there too so a later call site does not put Momentum back. Nothing calls it today.

### Other Momentum mentions (left unchanged)

| Surface | What | Why left |
|---|---|---|
| Team Attributes `GRID_ROWS` | Already the same 11; no Momentum | Already matches |
| `gridOrder` leftover append | Would show extra server keys | API `measures[]` omits `momentum_score` (`test_team_attribute_measures.py`) |
| Office `MEASURE_LABELS.momentum_score` | Label for payload-driven `moved_most` | Not a display list |
| Game Plan / `gamePlanView.js` | No team-measure list | Nothing to drop |
| FCC `TEAM_MEASURES_RADAR_AXES` | Eight axes, no Momentum | Already excluded |
| Training Report player MO pill / playbook-card “Momentum” bar | In-game player / playbook metric | Not the team-measure list |
| Court / Phaser / `gobPlayerAttributes` MO | Live-game momentum | Not a team-measure list |
| Box score `momentum_score` label | Box-score team attrs | Not Training Report / Team Attributes |
| Tutorials / `attributeTooltips` | Docs and MO tooltip | Not a display list |

## 2. Season review Class Signed — hairline only

Root cause: `big-news-modals.css` `.rc` (`border: 1px solid` + gradient) leaked onto season-review Class Signed rows. `.rv .rc` only set `border-bottom`, so the shorthand left a box. Double header rule was `.sec-h` `border-bottom` plus `.rc-l` `border-top` (the frame inlines `border-top:0` on `.rc-l`).

`FrontEnd/static/css/season-peak.css`:

- `.rv-cols .rc,.rv-cols .aw{min-height:var(--dsz-50)}`
- `.rv .rc-l{border-top:0}`
- `.rv .rc` `border:none;border-bottom:1px solid var(--line);background:transparent;` (plus `border-radius:0;box-shadow:none`)

Guard is computed style on `.rv .rc` first row: `border-left-width` 0, background transparent / `rgba(0,0,0,0)`. Not a class-name check.

## 3. Playbooks before-metrics fixture

`tests/e2e/prep-modules-playbooks.spec.js` no longer depends on untracked `reports/prep-modules-playbooks/before-metrics.json`.

Committed fixture: `tests/e2e/fixtures/playbooks-before-metrics.json` (copy of the playbooks before-metrics: `inApp1280` / `inApp1920` tracks, toggle, save paint, `lockVisible`, `liveCount`, `toastHost`).

`loadBeforeMetrics()` reads the fixture first, then the untracked reports file.

`app/prep-modules-training` on develop added `if (!BEFORE) return;`. After merge that sat next to the fixture read. The fixture restores the full comparison, so the early return (and the skip-if-absent) are gone. One path only.

## 4. Reward-gold allow-list in `check_ui_tokens.py`

`--strict` on develop failed on 11 new reward-gold hits from the office weekly exceptional-gain marker. Fix is the checker, not `office-home.css`.

- `LAW_ANNOTATION_RE` accepts `/* colour-law: reward */`
- `REWARD_SELECTOR_RE` matches the colour-law places: `.med.gold`, season-peak `.pk` / `.pk-` / `.cf`, milestone `.mm.is-gold` / `.mm .med`, `.xg` / `.xg-key` / `xgSweep`, Trophy Case `.gold-t` / `.pk-f` / `.rv-f`, plus `trophy-case`
- `_iter_blocks_inclusive` so `@keyframes xgSweep` wraps the `to` block
- `_scan_reward_gold` skips allowed selectors and the annotation

Ch7 CSS is new-design: `office-home`, `home-base`, `milestone-modal`, `season-peak`, `trophy-case`. `office-home` was already new; the other four were legacy and that is why their legal gold counted against `--strict`.

`tests/test_check_ui_tokens.py`: `test_reward_gold_xg_allowed_and_random_selector_fails` — allowed `.xg` / `.xg-key` / `@keyframes xgSweep` → 0 new reward-gold; `.random-card { color: var(--reward-gold); }` on `css/gob-components.css` → `--strict` exit 1.

Did not commit the rewritten `reports/ui-token-audit-*.md`.

### Reward-gold in the five Ch7 files

Every `--reward-gold` use in those five files is an allowed place (`.pk` / `.cf` / `.med.gold` / `.pk-f` / `.rv-f` / `.mm.is-gold` / `.mm .med` / `.med.gold` / `.gold-t` / `.xg` / `.xg-key` / `xgSweep`). Nothing leftover to list as unallowed.

### Counts

| | New green / orange / reward-gold | Legacy green / orange / reward-gold | Legacy total |
|---|---|---|---|
| Before (develop, `--strict` failing) | 0 / 0 / 11 (office `.xg`) plus the Ch7 files were still legacy | 263 / 789 / 27 | 1079 |
| After (this branch, post-merge) | 0 / 0 / 0 | 263 / 789 / 0 | 1052 |

`--strict` exit 0.

## Screenshots

Open each:

- `reports/training-report-no-momentum/team-report-before-1280.png` — develop-era Training Report; Momentum sits between Discipline and Team Chemistry
- `reports/training-report-no-momentum/team-report-after-1280.png` — Team Report only; 11 rows, no Momentum
- `reports/training-report-no-momentum/review-1280.png` — season review after; Class Signed hairline bottom, no box, no fill
- `reports/training-report-no-momentum/compare-review-1280.png` — frame `season-peak.html?v=review` at 1280, same hairline

## Files

- `FrontEnd/static/training-report.js`
- `FrontEnd/static/js/shared/scoutingReport.js`
- `FrontEnd/static/css/season-peak.css`
- `scripts/check_ui_tokens.py`
- `tests/test_check_ui_tokens.py`
- `tests/e2e/fixtures/playbooks-before-metrics.json`
- `tests/e2e/prep-modules-playbooks.spec.js`
- `tests/e2e/prep-modules-report.spec.js`
- `tests/e2e/season-peak-trophy-case.spec.js`

## Gates

- `pytest --ignore=tests/e2e`: 4136 passed, 14 skipped, 109 xfailed, 1 xpassed, 0 failed
- `tests/test_check_ui_tokens.py`: 8 passed
- `scripts/check_ui_tokens.py --strict`: exit 0
- `scripts/ci/check_migration_gates.py`: pass (Gate A 0/0, Gate B 138/46). No new Gate B. Did not run `--write-allowlist`.
- Playwright (post-merge, `workers=1`, `PORT=8193`, `CI` unset): 741 passed, 3 skipped, 0 failed

## Unsure

- Office `MEASURE_LABELS.momentum_score` still labels a payload-driven “moved most” line. If Jamie wants Momentum gone from that card too, that is a separate display change.
- A pre-merge Playwright run on port 8189 was 707 passed / 9 failed (`player-stats`, `store-client` office/wire, `t2-roster`). Those failures are gone on the merged tree; the post-merge run is the gate.
