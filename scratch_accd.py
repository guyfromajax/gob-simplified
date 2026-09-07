"""ACCEPTANCE D driver: make rate on the previously-misplaced shot population,
measured BEFORE and AFTER the spot-key fix with the identical probe.

The population is defined by a SKELETON property (the shoot pos_action carries the
spot name under "spot" only), which is invariant to the fix, so the same class is
identifiable in both runs. Self-validation: for that class the built shot coordinate
must read `logo` before the fix and `real` after. If that flip does not appear, the
probe is not looking at the population it claims to.
"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent
PY = str(ROOT / "venv" / "bin" / "python")
CONV = ROOT / "BackEnd/engine/defender_placement.py"
ORIGINAL = CONV.read_bytes()
SHA0 = hashlib.sha256(ORIGINAL).hexdigest()[:12]

SEEDS = list(range(8000, 8020))
ARMS = ("played", "sim")

FIXED_DISPATCH = 'elif "location" in pos_action or "spot" in pos_action:'
PREFIX_DISPATCH = 'elif "location" in pos_action:'
FIXED_READ = 'location = pos_action.get("location") or pos_action.get("spot") or "key"'
PREFIX_READ = 'location = pos_action.get("location", "key")'
FIXED_ELSE = '''raise ValueError(
                    f"pos_action for {position} at step {step_idx} carries no position key "
                    f"(want one of coords/location/spot, got {sorted(pos_action.keys())})"
                )'''
PREFIX_ELSE = '''coords = {"x": 50, "y": 25}
                coords_already_flipped = False'''


def run(job):
    arm, seed = job
    out = tempfile.mktemp(suffix=f".{arm}.{seed}.json")
    env = dict(os.environ, PYTHONHASHSEED="0", ARM=arm, SEED=str(seed), OUT=out,
               MONGO_DB_NAME=f"gob-accd-{arm}-{seed}")
    p = subprocess.run([PY, "scratch_accd_run.py"], env=env, capture_output=True, text=True,
                       cwd=str(ROOT))
    if not os.path.exists(out):
        return {"arm": arm, "seed": seed, "error": (p.stderr or "")[-300:]}
    d = json.load(open(out))
    os.unlink(out)
    return d


def measure(label):
    with ThreadPoolExecutor(max_workers=6) as ex:
        rows = list(ex.map(run, [(a, s) for a in ARMS for s in SEEDS]))
    bad = [r for r in rows if r.get("error")]
    for r in bad:
        print(f"  !! {r['arm']}/{r['seed']}: {str(r['error'])[:160]}")
    print(f"\n{'='*78}\n{label}\n{'='*78}")
    print(f"{'arm':7s} {'class':11s} {'shots':>6s} {'MAKE':>6s} {'MISS':>6s} {'BLOCK':>6s} "
          f"{'make%':>7s} {'miss+blk%':>10s} {'pts/shot':>9s} {'pts/MAKE':>9s} {'on logo':>9s}")
    summary = {}
    for arm in ARMS:
        rs = [r for r in rows if r.get("arm") == arm and not r.get("error")]
        n = len(rs) or 1
        for cls in ("SPOT_ONLY", "COORDS", "LOCATION"):
            agg, logo, pts = Counter(), Counter(), 0
            for r in rs:
                agg.update((r.get("by_class") or {}).get(cls) or {})
                logo.update((r.get("on_logo") or {}).get(cls) or {})
                pts += (r.get("points") or {}).get(cls, 0)
            shots = agg.get("shots", 0)
            if not shots:
                continue
            mk, ms, bl = agg.get("MAKE", 0), agg.get("MISS", 0), agg.get("BLOCK", 0)
            t3 = agg.get("is3:True", 0)
            lo, re = logo.get("logo", 0), logo.get("real", 0)
            print(f"{arm:7s} {cls:11s} {shots:6d} {mk:6d} {ms:6d} {bl:6d} "
                  f"{100.0*mk/shots:6.1f}% {100.0*(ms+bl)/shots:9.1f}% "
                  f"{pts/shots:9.2f} {(pts/mk if mk else 0):9.2f} "
                  f"{lo:4d}/{lo+re:4d}")
            summary[(arm, cls)] = {"shots": shots, "make%": round(100.0*mk/shots, 1),
                                   "missblk%": round(100.0*(ms+bl)/shots, 1),
                                   "pts/shot": round(pts/shots, 2),
                                   "3pt%": round(100.0*t3/max(shots, 1), 1),
                                   "pts/make": round(pts/mk, 2) if mk else 0,
                                   "logo": lo, "real": re,
                                   "shots/game": round(shots/n, 1)}
    return summary


CONV.write_text(
    CONV.read_text().replace(FIXED_DISPATCH, PREFIX_DISPATCH, 1)
    .replace(FIXED_READ, PREFIX_READ, 1)
    .replace(FIXED_ELSE, PREFIX_ELSE, 1)
)
before = measure("BEFORE — location-only dispatch, centre-court fallthrough")
CONV.write_bytes(ORIGINAL)
assert hashlib.sha256(CONV.read_bytes()).hexdigest()[:12] == SHA0, "restore failed"
after = measure("AFTER — location-or-spot dispatch")

print(f"\n{'='*78}\nHEADLINE — the previously-misplaced population (SPOT_ONLY)\n{'='*78}")
print(f"{'arm':8s} {'metric':12s} {'before':>9s} {'after':>9s}")
for arm in ARMS:
    b, a = before.get((arm, "SPOT_ONLY")), after.get((arm, "SPOT_ONLY"))
    if not b or not a:
        continue
    for k in ("shots/game", "make%", "missblk%", "pts/shot", "pts/make"):
        print(f"{arm:8s} {k:12s} {b[k]:9} {a[k]:9}")
    print(f"{arm:8s} {'on logo':12s} {b['logo']:4d}/{b['logo']+b['real']:<4d} "
          f"{a['logo']:9d}/{a['logo']+a['real']:<4d}")
print(f"\nTREE RESTORED: sha {hashlib.sha256(CONV.read_bytes()).hexdigest()[:12]} == {SHA0}")
