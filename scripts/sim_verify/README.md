# Sim verification toolkit

Runnable instruments behind the standing verification rules in
`_documentation_master/projects/Sim_Perf_Capstone.md` → **Verification toolkit**. Promoted from
session scratchpad so future work can *re-run* the checks, not just read about them.

All seeded runs pin `PYTHONHASHSEED=0` (determinism contract). The reference anchor is
`reports/perf/refstats_postB_20260720_20260720_153720.csv` (seed 20260720). Re-cut the anchor only
after an intentional RNG-stream change (see standing rule 2).

| Script / flag | Capstone toolkit row | Use when | Reads |
|---|---|---|---|
| **`--seed` + exact diff** (harness) then `diffstats.py` | Seeded exact-diff | change does NOT alter draw count (pure geometry, dead-code) | two refstats CSVs → per-column diff |
| **`perf_sim_baseline.py --poison-stash`** | Poison-stash test | change removes/alters sim-stream draws | keeps the defender-grid rebuild running, poisons only its stashed output; byte-identical seeded week ⇒ nothing reads it. **Blind spot:** catches arithmetic consumers, not key-presence checks |
| **`distcompare.py`** | Balanced multi-seed distributional arms | change alters the stream by construction (e.g. RNG isolation) | N seeds before vs N after; Welch t + F-ratio, flags \|t\|>3 |
| **`kill_worker_test.py`** | Worker-kill recovery | pool failure semantics | SIGKILLs a live worker mid-game; asserts week completes, byte-identical to seeded ref, 0 RNG leaks |
| **`p2_rng_audit.py`** | (RNG isolation audit) | verifying no engine module draws from the global `random` stream | counts global-module draws during a sim, by module; writes `p2_modules.txt` |

`bench_pool.py` — pool scaling benchmark (wall incl. cold pool creation, per-worker RSS). Not a
correctness check; run on a **quiet box**, medians of 3+ (standing rule 5).

## Copy-paste invocations

```bash
# --- seeded reference / exact-diff arm (draw-preserving changes) ---
PYTHONHASHSEED=0 python3 scripts/perf_sim_baseline.py \
  --franchise 6a28436c98dbd04e902eee09 --week 7 --games 63 --mode both \
  --ps-franchise 6a5e1f0e517ebcc58d981675 --ps-week 3 \
  --seed 20260720 --no-profile --workers 1 --tag mychange
python3 scripts/sim_verify/diffstats.py \
  reports/perf/refstats_postB_20260720_20260720_153720.csv \
  reports/perf/refstats_mychange_*.csv

# --- poison-stash (draw-count changes to StepState.defense) ---
PYTHONHASHSEED=0 python3 scripts/perf_sim_baseline.py \
  --franchise 6a28436c98dbd04e902eee09 --week 7 --games 63 --mode both \
  --ps-franchise 6a5e1f0e517ebcc58d981675 --ps-week 3 \
  --seed 20260720 --no-profile --poison-stash --tag poison
python3 scripts/sim_verify/diffstats.py \
  reports/perf/refstats_postB_20260720_20260720_153720.csv \
  reports/perf/refstats_poison_*.csv          # must be EXACT MATCH

# --- distributional arms (stream-altering changes): 5 seeds before vs after ---
for s in 20260720 20260721 20260722 20260723 20260724; do
  PYTHONHASHSEED=0 python3 scripts/perf_sim_baseline.py \
    --franchise 6a28436c98dbd04e902eee09 --week 7 --games 63 --mode both \
    --ps-franchise 6a5e1f0e517ebcc58d981675 --ps-week 3 \
    --seed $s --no-profile --tag after_$s
done
python3 scripts/sim_verify/distcompare.py \
  "reports/perf/refstats_before_*.csv" "reports/perf/refstats_after_*.csv" before after

# --- pool determinism: pooled == sequential, and pooled twice ---
PYTHONHASHSEED=0 python3 scripts/perf_sim_baseline.py --franchise 6a28436c98dbd04e902eee09 \
  --week 7 --games 63 --mode cpu --seed 20260720 --no-profile --pool 8 --tag pooled
PYTHONHASHSEED=0 python3 scripts/perf_sim_baseline.py --franchise 6a28436c98dbd04e902eee09 \
  --week 7 --games 63 --mode cpu --seed 20260720 --no-profile --workers 1 --tag seq
# diffstats pooled vs seq -> byte-identical

# --- worker-kill recovery ---
PYTHONHASHSEED=0 python3 scripts/sim_verify/kill_worker_test.py    # prints PASS/FAIL

# --- RNG isolation audit (expect 0 BackEnd global draws) ---
python3 scripts/sim_verify/p2_rng_audit.py

# --- pool scaling benchmark (QUIET box only) ---
PYTHONHASHSEED=0 python3 scripts/sim_verify/bench_pool.py "1,4,8,12" 3
```

Fixtures (franchise/PS ids, week 7 / PS week 3) are the staging `gob-staging` docs this initiative
used; swap for any franchise with a populated week-7 schedule + initialized practice squad.
