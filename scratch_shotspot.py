"""Driver for the shot_spot probe: one process per (arm, seed), n seeds, aggregated."""
import os, json, subprocess, tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.abspath(__file__))
PY_ = os.path.join(ROOT, "venv", "bin", "python")
W = os.path.join(ROOT, "scratch_shotspot_run.py")
N = int(os.environ.get("GAMES", "20"))

def one(arm, seed):
    fd, out = tempfile.mkstemp(suffix=".json"); os.close(fd)
    env = dict(os.environ, PYTHONHASHSEED="0", ARM=arm, SEED=str(seed), OUT=out,
               GOB_DB_MODE="mongomock", ENVIRONMENT="test", MONGO_DB_NAME="gob-test")
    p = subprocess.run([PY_, W], env=env, capture_output=True, text=True)
    try:
        d = json.load(open(out))
    except Exception:
        d = {"arm": arm, "seed": seed, "error": f"rc={p.returncode} {p.stderr[-300:]}"}
    finally:
        try: os.unlink(out)
        except OSError: pass
    return d

jobs = [(a, 8000+i) for a in ("sim","played") for i in range(N)]
with ThreadPoolExecutor(max_workers=8) as ex:
    res = list(ex.map(lambda j: one(*j), jobs))
json.dump(res, open(os.path.join(ROOT,"scratch_shotspot_results.json"),"w"), indent=1)

for arm in ("sim","played"):
    rows=[r for r in res if r["arm"]==arm and not r.get("error")]
    n=len(rows) or 1
    T=lambda k: sum(r.get(k) or 0 for r in rows)
    C=lambda k: sum((Counter(r.get(k) or {}) for r in rows), Counter())
    cls=C("cls"); syn=C("sync")
    a3=cls["MAKE|3PT"]+cls["MISS|3PT"]+cls["BLOCK|3PT"]; a2=cls["MAKE|2PT"]+cls["MISS|2PT"]+cls["BLOCK|2PT"]
    print(f"\n===== {arm}  (n={len(rows)} games) =====")
    print(f"  shot_spot provenance:        {dict(syn)}")
    print(f"  3PT attempts/game {a3/n:6.2f}   2PT attempts/game {a2/n:6.2f}   "
          f"3PA share {a3/max(a3+a2,1)*100:5.1f}%")
    print(f"  3PT makes/game    {cls['MAKE|3PT']/n:6.2f}   3PT make% {cls['MAKE|3PT']/max(a3,1)*100:5.1f}%")
    print(f"  2PT makes/game    {cls['MAKE|2PT']/n:6.2f}   2PT make% {cls['MAKE|2PT']/max(a2,1)*100:5.1f}%")
    print(f"  classification source:       {dict(C('cls_src'))}")
    print(f"  (b) candidates: n={T('cand_n')}  coords differ={T('cand_coord_differ')}  "
          f"ARC FLIPS={T('cand_flips')}  (skel3->emit2: {T('cand_3to2')}, emit3->skel2: {T('cand_2to3')})")
    print(f"  (d) scored-vs-RENDERED: compared={T('d_total')}  ARC FLIPS={T('d_flips')} "
          f"({T('d_flips')/max(T('d_total'),1)*100:.1f}%)  no-final={T('d_nofinal')}")
    print(f"      flips by outcome: {dict(C('d_by_rt'))}   -> MAKEs misawarded: {T('d_points_err')}"
          f" ({T('d_points_err')/n:.2f}/game)")
    print(f"      all compared by outcome: {dict(C('d_rt_all'))}")
ex_rows=[r for r in res if r["arm"]=="played" and r.get("d_examples")]
print("\nplayed-arm examples (scored vs rendered):")
for r in ex_rows[:3]:
    for e in r["d_examples"][:4]: print("   seed",r["seed"],e)

print("\n" + "="*78)
print("(d) CORRECTED — value ACTUALLY AWARDED vs the arc side of the RENDERED shot coord")
print("="*78)
for arm in ("sim","played"):
    rows=[r for r in res if r["arm"]==arm and not r.get("error")]
    n=len(rows) or 1
    C=lambda k: sum((Counter(r.get(k) or {}) for r in rows), Counter())
    cmp_,fl=C("d_award_cmp"),C("d_award_flip")
    tot,tf=sum(cmp_.values()),sum(fl.values())
    print(f"  {arm}: compared={tot}  DISAGREEMENTS={tf} ({tf/max(tot,1)*100:.2f}%)")
    print(f"      by outcome compared={dict(cmp_)}")
    print(f"      by outcome flipped={dict(fl)}   MAKE flips={fl.get('MAKE',0)} ({fl.get('MAKE',0)/n:.2f}/game)")
for r in [x for x in res if x["arm"]=="played" and x.get("d_award_ex")][:3]:
    for e in r["d_award_ex"][:4]: print("   seed",r["seed"],e)
