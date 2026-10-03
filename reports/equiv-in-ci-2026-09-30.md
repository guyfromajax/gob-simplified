# equiv-v3 in the repo and CI: 2026-09-30

Branch `chore/equiv-in-ci` (worktree `../gob-equiv`), tooling only. No `BackEnd/` or `FrontEnd/` changes. Python 3.11.16 venv from `requirements-dev.txt`.

## What's where

| Path | What |
|---|---|
| `scripts/sim_verify/worker.py` | The equiv-v3 worker, **moved** from `scratch_equiv3_fbdedupe.py`. Only the `sys.path` line (now the repo root) and the docstring changed; the diff is those lines. It still imports `scratch_posture_census` / `scratch_screen_census` from the root. |
| `scratch_equiv3_fbdedupe.py` | Now a thin wrapper that runs the worker (`runpy`) with the same env contract, kept per CLAUDE.md. Proven: seed 8001, `SEED_DEFENSES=0`, played arm run through the wrapper reproduces the reference row exactly. |
| `scripts/sim_verify/aggregate.py` | **Reconstructed aggregator** (details below). |
| `scripts/sim_verify/equiv.py` | The entry point: `python -m scripts.sim_verify.equiv --check [--smoke]` / `--recut`. |
| `scripts/sim_verify/CURRENT_REFERENCE` | The pointer: `_documentation_master/projects/references/equiv_v3_reference_f600628a4_agspread.json`. |
| `tests/test_sim_verify_aggregate.py` | 15 fast tests, no sims: byte-for-byte rebuild of 10 references, old references readable, pointer valid and marked CURRENT in the README, smoke plan, posture, diff wording. |
| `.github/workflows/test.yml` | New job `engine-equiv`. |
| `CLAUDE.md` | New "Engine regression check" section; the engine-rule line repointed. |
| references `README.md` | Pointer and command notes added. |

## Reconstructed aggregator: assumptions, and the proof

The original `/tmp/refcut_equivv3.py` was never committed, so I rebuilt it from the reference files and the README:

- **Cells:** ordered `SEED_DEFENSES=1` then `=0`; arms `sim` then `played`.
- **`per_seed`:** keys are string seeds, ascending. Each row is `{fp, draws, points_per_team, turns, possessions}`, as emitted by the worker.
- **`arm_gap_sim_minus_played`:** paired per-seed `sim − played` points_per_team, mean and 1.96 × SEM (sample SD), both rounded to 3 places, plus `n` and the fixed note.
- **Header and format:** the header is `sha, note, footing, flags`; output is `json.dumps(indent=1)` with no trailing newline.

**Proof:** feeding each committed reference's own rows and header back through the aggregator reproduces **10 of 20 files byte for byte**. That's every file from `5cc98ee3e` onward, including the current reference and all three loose baselines. The other 10 are older files: 8 also carried per-arm summary stats from an earlier aggregator, and 2 (`equiv_v3_sim_reference_*`) have a different shape. Their per-seed rows are still readable, so `--check --reference <old file>` works for kill-switch verification on all 18 `SEED_DEFENSES` files. The two sim-only files aren't supported.

## Current reference, and proof develop matches it

**Current:** `equiv_v3_reference_f600628a4_agspread.json`. It's the one the references README marks CURRENT, and the one the memory notes name as the live reference.

- **Full run on develop** (`b3b7944ec` + tooling only): `python -m scripts.sim_verify.equiv --check`, 160 games (2 footings × 2 arms × seeds 8000–8039), 14 jobs:
  ```
  MATCH: 160/160 games identical on fp, draws, points, turns, possessions and both arm gaps (156.1s)
  ```
  **~2.6 min on 14 cores.** Written out with the reference's header (`--save-run`), the run is **byte-identical** to the committed reference (same SHA-256, `362e4485…18dfe1`).
- **Loose baseline** too: `--reference equiv_v3_loose_baseline_f600628a4_agspread.json`, 80 games at `EQUIV_MAN_POSTURE=loose`: MATCH 80/80, byte-identical, 53 s.
  - A first attempt reported false drift: that file's footing text doesn't name the posture, so I now derive it from the `equiv_v3_loose_baseline_` file name (as the README defines it), with `--posture` as an override.

## CI smoke

- **Seeds:** 8000–8003 on all four cells = **16 games**, one process each, `PYTHONHASHSEED=0`, mongomock. Jobs = runner CPU count.
- **Runtime:** GitHub runner (4 cores) smoke step **54.4 s**; whole job **1 min 46 s** (checkout 26 s, pip install 21 s). Locally at `--jobs 2`: ~47 s.
- **On drift:** exit 1 with per-seed field diffs, per-cell mean deltas and a moved-seed count. A worker crash, emitter failure or game error exits 2 with the log tail.
- **Determinism:** 3 local smoke runs gave identical saved JSON (SHA-256 `96d7f9ce…049bbb` ×3) and identical reports once the timing text is removed (`d20ff70b…1174e8` ×3).

## Drift-catch proof (throwaway, reverted, never committed)

- **The edit:** `BackEnd/models/shot_manager.py:1726`, `made = shot_score > _make_bar` changed to `… > _make_bar + 1` (an undefended outside shot gets one point harder).
- **Smoke result:** exit 1, with:
  ```
  FINGERPRINT DRIFT against equiv_v3_reference_f600628a4_agspread.json (47.9s):
    SEED_DEFENSES=0 played seed 8003: fp 84a9dd0bdd5e0aae -> cf21ce5d1798d2c7; draws 63004 -> 61907 (-1097); points_per_team 75.0 -> 82.5 (+7.5); turns 444 -> 470 (+26); possessions 33 -> 28 (-5)
      SEED_DEFENSES=0 played mean points_per_team over 4 seeds: 82.125 -> 84.000 (+1.875)
      ...
      SEED_DEFENSES=0 played: 1/4 seeds moved
  ```
- **Reverted** with `git checkout`, and `BackEnd/` was confirmed clean.
- **Sensitivity caveat:** this nudge only bites on a rare branch, so it moved 1 of 16 smoke games. A smoke catches rare-branch changes only when a seed happens to hit them. Engine work should still run the full 160-game check locally before finishing (it's in CLAUDE.md).

## Re-cut procedure

```
python -m scripts.sim_verify.equiv --recut --reason "<why the engine moved>" --slug <name>
```

- **Guards:** refuses in CI (`CI` set), without a reason, or with uncommitted changes under `BackEnd/`, `scripts/sim_verify/` or `tests/roster_fixtures.py`, so the new file always describes a commit.
- **Double re-baseline:** runs all 160 games twice and refuses if the passes differ.
- **Output:** writes `equiv_v3_reference_<sha9>_<slug>.json`, with `note` = the reason and footing/flags copied from the old file, and moves the pointer.
- **Then, by hand:** edit `flags` if a flag flipped; in the references README move the old file to Superseded with the switch that reproduces it; commit as `equiv re-cut: <reason>`.
- **Dry run of the whole thing** (references dir and pointer redirected to a temp copy, real files untouched): both guards returned 64, two 160-game passes ran, the written file's cells were **identical** to the current reference (0/160 rows differ), and the pointer moved.

**CLAUDE.md rule added:** never re-cut to make CI green without Jamie's approval (same as `--write-allowlist`).

## Follow-ups (not done)

- The loose baseline isn't in the CI smoke (one pointer, per the brief). A loose-only change would pass CI; check it locally with `--reference …loose_baseline…`. Adding 2 loose seeds × 2 arms would cost about 15 s in CI if you want it.
- The full 160-game run stays local-only by design; CI runs only the smoke.

Migration gates: passed (Gate A 0, Gate B 136 lines / 44 files).
Full suite: 4286 passed, 20 skipped, 109 xfailed, 1 xpassed, 0 failed (the xpass is the known `test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference`, as on develop).
CI: run 36772360535 on `chore/equiv-in-ci` (head `869e459a9`) all green: engine-equiv, test, migration-gates, ui-tokens. The first run, 36771348043 on `f3acd7c0c`, was also all green; its engine-equiv smoke ran in 54.4 s.

## Follow-up (same day): wider smoke + loose baseline

### Seeds

- **Main smoke: 14 seeds** `8000, 8005, 8006, 8007, 8008, 8019, 8020, 8021, 8022, 8028, 8029, 8031, 8032, 8038`, on all four cells = 56 games.
  - **How they were chosen:** a scratch driver ran the unmodified worker on every reference game (80 main sim-arm + 40 loose). Each fingerprint matched the reference, so these are the reference games. It collected path features per game: fast breaks, FT awards, steals, blocks, timeouts, charges, OREB, putback misses, run-out-clock, SIP, HCT, FCP, per-shell zone calls, zone calls without placement, untagged placements, final-turn announces, points, close finish (margin ≤ 3).
  - **What they cover:** a greedy set cover picked seeds so that every top- or bottom-fifth extreme of every feature on both footings is hit **at least twice** (76/76). The old 8000–8003 hit 48/76 once.
  - **Late game:** 8 of the 14 are close finishes, and run-out-clock games appear on both footings.
  - **No overtime:** none of the 40 reference seeds reaches overtime, so the smoke can't cover it. Every event type except run-out-clock, charge, putback-miss and SIP appears in every game.
- **Loose baseline: seeds `8005, 8036`**, both arms = 4 games. They're the two seeds covering the most loose-footing extremes (31/44). There's a new pointer, `scripts/sim_verify/CURRENT_LOOSE_BASELINE`. `--smoke` runs both suites in one worker pool, and `--recut` moves whichever pointer names the re-cut file.

### Runtime and determinism

- **CI run 36776066551** (`d844d8993`): **all green**.
  - The smoke step took **3 min 28 s** (`MATCH: 60/60 games (207.9s)`, 4 jobs).
  - The whole `engine-equiv` job took 4 min 14 s, finishing before `test` (7 min 15 s).
- **Local, `--jobs 4`, 3 runs:** 60/60 each time. Identical saved JSON (`812cefaf…bd81732` ×3) and identical reports minus timing (`2aa0b807…935e5b5e` ×3).

### Drift-catch proof, re-run on the wider smoke (same `shot_manager.py:1726` +1 nudge, reverted, not committed)

- **Wider smoke:** exit 1. **1 of 60 games moved**: `SEED_DEFENSES=0 sim seed 8020: fp fb8638f89ace698b -> 6f0fb596c2c13ef9; draws 61464 -> 59585 (-1879); points_per_team 80.0 -> 78.0 (-2.0); turns 450 -> 444 (-6); possessions 40 -> 38 (-2)`. Loose 4/4 unchanged.
- **For scale, the full 160-game run** with the same nudge moves **5 of 160 games** (3%: d1 sim 8025, d1 played 8010 and 8025, d0 sim 8020, d0 played 8003). The nudge itself only fires on a rare branch, so the smoke's hit rate (1/60) is about proportional. The old 16-game smoke caught it through seed 8003, which the coverage selection doesn't include. A change that shifts more common paths moves many more smoke games. A rare-branch change can still slip past the smoke, which is why CLAUDE.md keeps the full local run for engine work.

Migration gates: passed (Gate A 0, Gate B 136 lines / 44 files), unchanged by this follow-up.
CI: run 36776066551 all green: engine-equiv (smoke 3 min 28 s), test, migration-gates, ui-tokens.
