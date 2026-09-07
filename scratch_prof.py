"""SPC principle 7 driver — before/after profile of the HCO build path."""
import hashlib
import json
import os
import pathlib
import subprocess
import statistics as st
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent
PY = str(ROOT / "venv" / "bin" / "python")
CONV = ROOT / "BackEnd/engine/defender_placement.py"
ORIGINAL = CONV.read_bytes()
SHA0 = hashlib.sha256(ORIGINAL).hexdigest()[:12]
SEEDS = list(range(8000, 8012))
ARMS = ("played", "sim")

F_DISPATCH = 'elif "location" in pos_action or "spot" in pos_action:'
F_READ = 'location = pos_action.get("location") or pos_action.get("spot") or "key"'
F_ELSE = '''raise ValueError(
                    f"pos_action for {position} at step {step_idx} carries no position key "
                    f"(want one of coords/location/spot, got {sorted(pos_action.keys())})"
                )'''

METRICS = ("builds", "steps", "step_pos_actions", "build_mean_ms", "build_p50_ms",
           "build_p95_ms", "build_total_s", "build_share_of_game_pct", "game_wall_s", "turns")


def run(job):
    arm, seed = job
    out = tempfile.mktemp(suffix=f".{arm}.{seed}.json")
    env = dict(os.environ, PYTHONHASHSEED="0", ARM=arm, SEED=str(seed), OUT=out,
               MONGO_DB_NAME=f"gob-prof-{arm}-{seed}")
    p = subprocess.run([PY, "scratch_prof_run.py"], env=env, capture_output=True,
                       text=True, cwd=str(ROOT))
    if not os.path.exists(out):
        return {"arm": arm, "seed": seed, "error": (p.stderr or "")[-300:]}
    d = json.load(open(out))
    os.unlink(out)
    return d


def measure():
    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(run, [(a, s) for a in ARMS for s in SEEDS]))
    for r in rows:
        if r.get("error"):
            print(f"  !! {r['arm']}/{r['seed']}: {str(r['error'])[:140]}")
    out = {}
    for arm in ARMS:
        rs = [r for r in rows if r.get("arm") == arm and not r.get("error")]
        out[arm] = {m: round(st.mean([r[m] for r in rs if r.get(m) is not None]), 4)
                    for m in METRICS}
    return out


CONV.write_text(CONV.read_text()
                .replace(F_DISPATCH, 'elif "location" in pos_action:', 1)
                .replace(F_READ, 'location = pos_action.get("location", "key")', 1)
                .replace(F_ELSE, 'coords = {"x": 50, "y": 25}\n'
                                 '                coords_already_flipped = False', 1))
print("profiling BEFORE ...", flush=True)
before = measure()
CONV.write_bytes(ORIGINAL)
assert hashlib.sha256(CONV.read_bytes()).hexdigest()[:12] == SHA0
print("profiling AFTER ...", flush=True)
after = measure()

print(f"\n{'='*84}\nSPC PRINCIPLE 7 — before/after profile, HCO build path (mean over "
      f"{len(SEEDS)} games/arm)\n{'='*84}")
for arm in ARMS:
    print(f"\n  {arm.upper()}")
    print(f"    {'metric':26s} {'before':>12s} {'after':>12s} {'change':>10s}")
    for m in METRICS:
        b, a = before[arm][m], after[arm][m]
        ch = f"{100.0*(a-b)/b:+.1f}%" if b else "n/a"
        print(f"    {m:26s} {b:12.4f} {a:12.4f} {ch:>10s}")
print(f"\nTREE RESTORED: sha {hashlib.sha256(CONV.read_bytes()).hexdigest()[:12]} == {SHA0}")
