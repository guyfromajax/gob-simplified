import pathlib
"""
PHASE 2 AUDIT — which modules actually draw from the global `random` module
DURING a sim, and how often?

Wraps every public function on the global random module, attributes each call to
its immediate caller (file:function), and runs 2 CPU games + 1 PS game.

Output drives the scope of the dedicated-RNG conversion: only modules that
actually draw during a sim need converting.
"""
import inspect
import random
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

CALLS = Counter()
FUNCS = Counter()
_depth = {"n": 0}

_WRAPPED = [
    "random", "randint", "choice", "choices", "shuffle", "uniform", "sample",
    "gauss", "normalvariate", "betavariate", "triangular", "randrange",
    "getrandbits", "expovariate", "lognormvariate", "vonmisesvariate",
    "paretovariate", "weibullvariate", "randbytes",
]


def install():
    for name in _WRAPPED:
        fn = getattr(random, name, None)
        if fn is None:
            continue

        def make(fn=fn, name=name):
            def wrapper(*a, **k):
                # guard against re-entrancy (e.g. shuffle -> randrange)
                if _depth["n"] == 0:
                    _depth["n"] = 1
                    try:
                        f = inspect.currentframe().f_back
                        mod = f.f_globals.get("__name__", "?")
                        CALLS[f"{mod}:{f.f_code.co_name}"] += 1
                        FUNCS[name] += 1
                    except Exception:
                        pass
                    finally:
                        _depth["n"] = 0
                return fn(*a, **k)
            return wrapper

        setattr(random, name, make())


def main():
    install()
    from bson import ObjectId
    from BackEnd.db import franchises_collection, db
    from BackEnd.api.franchise_routes import _run_franchise_cpu_full_simulation_core

    fid = ObjectId("6a28436c98dbd04e902eee09")
    f = franchises_collection.find_one({"_id": fid})
    for gi, g in enumerate(f["schedule"][6][:2]):
        aid, hid = (g["away"], g["home"]) if isinstance(g, dict) else (g[0], g[1])
        an = (db.teams.find_one({"_id": aid}, {"name": 1}) or {}).get("name", "")
        hn = (db.teams.find_one({"_id": hid}, {"name": 1}) or {}).get("name", "")
        _run_franchise_cpu_full_simulation_core(fid, hid, aid, hn, an, seed=500 + gi)

    # PS game too — catches PS-only draw sites (and pymongo via bulk_write)
    try:
        from BackEnd.practice_squad.manager import (
            _games_for_week, _resolve_team_roster, _update_scrubs_rosters)
        from BackEnd.practice_squad.sim import run_ps_full_simulation
        from BackEnd.db import (franchise_players_data_collection,
                                franchise_recruits_data_collection)
        pf = ObjectId("6a5e1f0e517ebcc58d981675")
        pdoc = franchises_collection.find_one({"_id": pf}) or {}
        ps_state = dict(pdoc.get("practice_squad") or {})
        _update_scrubs_rosters(ps_state, 3)
        sfid = str(pf)
        fpd = {str(d["player_id"]): d for d in
               franchise_players_data_collection.find({"franchise_id": sfid})}
        frd = {str(d["recruit_id"]): d for d in
               franchise_recruits_data_collection.find({"franchise_id": sfid})}
        teams = ps_state.get("teams") or {}
        for g in _games_for_week(ps_state, 3)[:1]:
            hid, aid = str(g["home_team_id"]), str(g["away_team_id"])
            hr = _resolve_team_roster(ps_state, hid, 3)
            ar = _resolve_team_roster(ps_state, aid, 3)
            if len(hr) < 5 or len(ar) < 5:
                continue
            run_ps_full_simulation(
                home_display_name=(teams.get(hid) or {}).get("display_name") or hid,
                away_display_name=(teams.get(aid) or {}).get("display_name") or aid,
                home_team_id=hid, away_team_id=aid,
                home_roster=hr, away_roster=ar,
                fpd_by_id=fpd, frd_by_id=frd, game_id=None, seed=900)
    except Exception as e:
        print(f"(PS leg skipped: {type(e).__name__}: {e})", file=sys.stderr)

    cpu_calls = sum(CALLS.values())
    cpu_by_mod = Counter()
    for k, n in CALLS.items():
        cpu_by_mod[k.split(":")[0]] += n

    out = sys.stderr
    print("\n" + "=" * 80, file=out)
    print("PHASE 2 RNG AUDIT — global-module draws during 2 CPU games", file=out)
    print("=" * 80, file=out)
    print(f"\ntotal draws: {cpu_calls:,}\n", file=out)

    print(f"{'module':<52}{'draws':>12}{'% ':>8}", file=out)
    print("-" * 72, file=out)
    for mod, n in cpu_by_mod.most_common(40):
        print(f"{mod:<52}{n:>12,}{100*n/cpu_calls:>7.1f}%", file=out)

    print(f"\n{'top call sites':<52}{'draws':>12}", file=out)
    print("-" * 64, file=out)
    for site, n in CALLS.most_common(25):
        print(f"{site:<52}{n:>12,}", file=out)

    print(f"\n{'random fn':<24}{'calls':>12}", file=out)
    print("-" * 36, file=out)
    for fn, n in FUNCS.most_common():
        print(f"{fn:<24}{n:>12,}", file=out)

    # non-BackEnd draws = third-party (pymongo etc.) that must KEEP the global module
    # machine-readable module list for the conversion sweep (written next to this script)
    out_path = pathlib.Path(__file__).resolve().parent / "p2_modules.txt"
    with open(out_path, "w") as fh:
        for mod, n in cpu_by_mod.most_common():
            if mod.startswith("BackEnd"):
                fh.write(f"{mod}\t{n}\n")
    print(f"\nwrote module list ({len([m for m in cpu_by_mod if m.startswith('BackEnd')])} BackEnd modules)",
          file=out)

    print(f"\nNON-BackEnd (third-party) draw sources — these keep the global module:", file=out)
    ext = {m: n for m, n in cpu_by_mod.items() if not m.startswith("BackEnd")}
    if ext:
        for m, n in sorted(ext.items(), key=lambda kv: -kv[1]):
            print(f"  {m:<50}{n:>12,}", file=out)
    else:
        print("  (none observed in-sim)", file=out)


if __name__ == "__main__":
    main()
