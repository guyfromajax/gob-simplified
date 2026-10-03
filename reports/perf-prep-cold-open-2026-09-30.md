# Prep cold-open: Playbooks / Scouting ~3× — 2026-09-30

Branch `perf/prep-cold-open` off `origin/develop` (`6fffd325e`). Worked in `~/gob-stats`. Temporary worktrees: `/tmp/gob-perf-a` (A), `/tmp/gob-perf-bisect` (removed after).

## What was compared

| | SHA | What |
|---|---|---|
| **A** | `8906dab0f` | Playbooks module conversion — the commit that wrote the 113/194 numbers in `reports/prep-modules-2026-09-29.md` (PORT 8175, `--only=playbooks-view`) |
| **B** | `6fffd325e` (`origin/develop`) | Current develop (includes retire-prep-embed + auth-hardening) |

`scripts/measure_nav_timing.js` is **byte-identical** at A and B. Same machine, back to back, `PYTHONHASHSEED=0`, `--only=playbooks-view,scouting-view --pass=timing --runs=5`, desktop + online. Each run creates a Lancaster franchise through the same `select-team` door (`seed_and_serve_desktop.py`).

## A/B table (same seed, same harness)

| screen | profile | A `8906dab0f` cold | A warm | B develop cold | B warm |
|---|---|---|---|---|---|
| playbooks-view | desktop | **155/215** (116–215) | 7/8 | **121/213** (114–213) | 8/8 |
| playbooks-view | online | **118/158** | 7/7 | **128/156** | 7/8 |
| scouting-view | desktop | **164/168** (156–168) | 13/14 | **427/443** (400–443) | 8/9 |
| scouting-view | online | **162/286** | 12/14 | **404/436** | 7/8 |

Raw: `reports/perf-prep-cold-open/a-8906dab0f.json`, `b-develop.json`.

### Playbooks — no product regression

B is the same as A (desktop median 121 vs 155; online 128 vs 118). The 9/29 **113/194** is the same band as today's A 155/215. Yesterday's retire-prep-embed **393/419** was `--only=` five Prep views while pytest was also running on the machine. That is load + a longer click sequence, not a 3× product change. **No fix.**

### Scouting — measure says 2.6×; wall-clock paint does not

The measure script's `vis('#scouting-view .opp-n')` on the playbooks-then-scouting path is 164 ms on A and 427 ms on B (tight clusters, not one outlier).

A same-click **request waterfall** (office → Training rail → Scouting sub-tab, no Playbooks first) is **not** 3× apart:

| | A `8906dab0f` | B develop |
|---|---|---|
| click → `.opp-n` (wall clock) | 875 ms | 801 ms |
| `FranchiseContext.get('franchise_id')` | set, matches URL | set, matches URL |
| `viewLoader.js` / `prepEmbed.js` | 3 ms | 3 ms |
| `scoutingView.js` | 20 ms | 34 ms |
| `POST /franchise/play-next-game` | 193 ms | 174 ms |
| `GET /franchise/team-data` (opponent) | 104 ms | 153 ms |
| `GET /franchise/scouting-report` | 284 ms | 279 ms |

Raw: `reports/perf-prep-cold-open/a-waterfall.json`, `b-waterfall.json`. Same three fetches, same order (scripts → play-next-game → team-data + scouting-report). No extra blocking request on B. Loader rename is 3 ms.

A's measure 164 ms is **below the fetch floor** on that SHA (play-next-game 193 + scouting-report 284 if they run after the module). The harness is calling done early on A after the Playbooks hop; it is not a faster scouting-report. B's 427 ms sits on the play-next-game + report sum (~450 ms).

## Bisect (Scouting measure, desktop cold, 3 runs, threshold 295 ms)

Parents of the merge were both **good** under that threshold:

| SHA | median | verdict |
|---|---|---|
| `e7a83e7d8` ch8-cleanup merge | 159 | good |
| `6f0bbcf18` training module merge | 187 | good |
| `02fe1ea70` training-report-no-momentum | 163 | good |
| `7c619be50` **auth-hardening merge** | 179 | good |
| `8bfa87ff4` **retire-prep-embed commit** | 163 | good |
| `6fffd325e` **Merge chore/retire-prep-embed** | first bad (B = 427) | bad |

First bad: **`6fffd325e` Merge chore/retire-prep-embed** (`7c619be50` + `8bfa87ff4`). Neither parent is slow alone. That is the combination in the measure script, not a single view-line change.

## Time breakdown (B, office → Training → Scouting)

1. CSS (`prep-v2-scouting.css`, `rt-buckets.css`): 9–11 ms. Not serial vs A.
2. `viewLoader.js`: 3 ms (A's `prepEmbed.js` was 3 ms).
3. `scoutingView.js` import: 34 ms (A 20 ms).
4. `GOBFccPrep.resolveUpcomingOpponent` → `POST /franchise/play-next-game`: **174 ms**.
5. Parallel `GET /franchise/team-data` (153 ms) + `GET /franchise/scouting-report` (279 ms).
6. Paint `.opp-n`.

No new CSS/script that used to be parallel. FranchiseContext has `franchise_id` at paint (not an empty-id retry). The slow pieces are the existing play-next-game POST and scouting-report GET — **present and the same duration on A**.

## Fix

**None.** Playbooks is not slower on the same seed. Scouting's wall-clock first paint and its fetch waterfall match A. The 9/29 **154/180** coverage-map number and yesterday's **474/554** are the same kind of harness/path difference as Playbooks 113 vs 393 (yesterday's five-view pass under load). Auth-hardening is one parent of the merge; the task says do not change that path.

Did not edit product files. Did not touch office-home, gob_nav, `check_ui_tokens.py`, or SFX.

## Gates

- `scripts/ci/check_migration_gates.py`: **passed**. Gate A 0/0. Gate B 136 lines / 44 files.
- No product change: pytest / Playwright / `--strict` not re-run.
