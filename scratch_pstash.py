"""POISON-STASH TEST (SPC principle 8) for the offense converter's coordinate output.

The committed flag `perf_sim_baseline.py --poison-stash` poisons `_step_state["defense"]` --
the DEFENDER grid. The spot-key fix changed the OFFENSE converter's output, so that flag
tests a different value. This is the same method aimed at the right one.

Method, per Sim_Perf_Capstone.md: keep the work running so the draw count at the poison site
is unchanged, replace only its output with an absurd sentinel, run seeded, compare.
  fingerprint identical  => nothing downstream reads this producer's coordinates
  fingerprint diverges   => it is read, and the sentinel reached outcomes

Run as: PYTHONHASHSEED=0 venv/bin/python scratch_pstash.py
"""
import json
import os
import subprocess
import sys
import tempfile

SEEDS = [8000, 8001, 8002, 8003, 8004, 8005]
ARMS = ["played", "sim"]


def run(arm, seed, poison):
    out = tempfile.mktemp(suffix=".json")
    env = dict(os.environ, ARM=arm, SEED=str(seed), OUT=out, PYTHONHASHSEED="0")
    if poison:
        env["POISON_STASH"] = "1"
    else:
        env.pop("POISON_STASH", None)
    p = subprocess.run([sys.executable, "scratch_harness_run.py"],
                       env=env, capture_output=True, text=True, timeout=1800)
    if not os.path.exists(out):
        return {"error": f"worker died rc={p.returncode}: {p.stderr[-400:]}"}
    d = json.load(open(out))
    os.unlink(out)
    return d


print(f"POISON-STASH TEST — offense converter coordinate output")
print(f"sentinel {{x:-9999,y:-9999}}, {len(SEEDS)} seeds x {len(ARMS)} arms x 2 conditions\n")

results = {}
for arm in ARMS:
    for poison in (False, True):
        for seed in SEEDS:
            r = run(arm, seed, poison)
            results[(arm, poison, seed)] = r
            tag = "POISONED" if poison else "clean   "
            if r.get("error"):
                print(f"  {arm:7s} {tag} seed {seed}  ERROR {r['error'][:90]}")
            else:
                pz = r.get("poison", {})
                print(f"  {arm:7s} {tag} seed {seed}  fp={r['fingerprint']}  "
                      f"draws={r['draws']:>7,}  turns={r['turns']:>4}  "
                      f"builds={pz.get('calls', 0):>5}  poisoned_coords={pz.get('coords', 0):>7,}")

print("\n" + "=" * 78)
print("RESULT")
print("=" * 78)

for arm in ARMS:
    same_fp = diff_fp = 0
    dr_clean = dr_pois = 0
    n_builds = n_coords = 0
    errs = 0
    for seed in SEEDS:
        c = results[(arm, False, seed)]
        p = results[(arm, True, seed)]
        if c.get("error") or p.get("error"):
            errs += 1
            continue
        if c["fingerprint"] == p["fingerprint"]:
            same_fp += 1
        else:
            diff_fp += 1
        dr_clean += c["draws"]
        dr_pois += p["draws"]
        n_builds += p.get("poison", {}).get("calls", 0)
        n_coords += p.get("poison", {}).get("coords", 0)

    print(f"\n{arm.upper()} ARM")
    print(f"  builds intercepted        {n_builds:,}")
    print(f"  coordinates poisoned      {n_coords:,}")
    if n_coords == 0:
        print("  ⚠️  VACUOUS — the probe poisoned nothing, so this arm proves nothing.")
    print(f"  fingerprint identical     {same_fp}/{len(SEEDS) - errs}")
    print(f"  fingerprint diverged      {diff_fp}/{len(SEEDS) - errs}")
    if errs:
        print(f"  errored                   {errs}")
    if dr_clean:
        print(f"  draws clean               {dr_clean:,}")
        print(f"  draws poisoned            {dr_pois:,}  "
              f"({100.0 * (dr_pois - dr_clean) / dr_clean:+.1f}%)")
    if n_coords and same_fp and not diff_fp:
        print("  => NOTHING downstream reads this producer's coordinates in this arm.")
    elif diff_fp:
        print("  => the coordinates ARE read; the sentinel reached game outcomes.")

json.dump({f"{a}|{int(p)}|{s}": v for (a, p, s), v in results.items()},
          open("scratch_pstash_results.json", "w"), indent=1)
print("\nwrote scratch_pstash_results.json")
