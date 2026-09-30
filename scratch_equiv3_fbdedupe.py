"""equiv-v3 worker: kept at this path for the reports and runbooks that name it.

The worker now lives in scripts/sim_verify/worker.py (moved 2026-09-30, logic unchanged).
This file runs it with the same env contract as before, e.g.

  PYTHONHASHSEED=0 SEED_DEFENSES=1 ARM=sim SEED_BASE=8000 OUT=/tmp/x.json \\
      python scratch_equiv3_fbdedupe.py

For a whole reference check use: python -m scripts.sim_verify.equiv --check
"""
import os
import runpy
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    runpy.run_module("scripts.sim_verify.worker", run_name="__main__")
