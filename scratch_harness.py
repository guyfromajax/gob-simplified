"""equiv-v3 DRIVER — process-isolated arms, with independence proven before anything is measured.

Two standing gates, both hard. A run that fails either prints no comparison at all.

  GATE 1 INDEPENDENCE. Run the identical arm three times in three separate processes and
  require byte-identical games AND identical sim_rng draw counts. This exists because arms
  run back-to-back in ONE process are provably not independent -- player state persists in
  the mongomock DB across games, so an arm's result tracked its POSITION in the process
  (three identical passes gave draw counts 137,106 / 136,832 / 134,387). Re-seeding the RNGs
  does not reset the DB; only a fresh process does.

  GATE 2 FT-HONOUR PARITY. Free-throw awards honoured must be high and approximately equal
  across arms. If the arms disagree, the harness is misrepresenting one of them and no figure
  from that run is reportable. This caught the equiv-v1 game_state aliasing artifact.

Every equiv-v1 and equiv-v2 figure is treated as VOID here, not as a prior. Nothing is
carried forward as an expectation.
"""
import os, sys, json, math, subprocess, tempfile, statistics as st
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(ROOT, "venv", "bin", "python")
WORKER = os.path.join(ROOT, "scratch_harness_run.py")
WORKERS = int(os.environ.get("WORKERS", "6"))


def run_one(arm, seed, tag=""):
    fd, out = tempfile.mkstemp(suffix=".json", prefix=f"eq3_{arm}_{seed}{tag}_")
    os.close(fd)
    env = dict(os.environ, PYTHONHASHSEED="0", ARM=arm, SEED=str(seed), OUT=out,
               GOB_DB_MODE="mongomock", ENVIRONMENT="test", MONGO_DB_NAME="gob-test")
    p = subprocess.run([PY, WORKER], env=env, capture_output=True, text=True)
    try:
        with open(out) as f:
            data = json.load(f)
    except Exception:
        data = {"arm": arm, "seed": seed, "error": f"worker failed rc={p.returncode}: "
                                                   f"{p.stderr[-400:]}"}
    finally:
        try:
            os.unlink(out)
        except OSError:
            pass
    return data


def run_many(jobs):
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        return list(ex.map(lambda j: run_one(*j), jobs))


def gate_independence():
    print("=" * 78)
    print("GATE 1 — INDEPENDENCE. Identical arm, three separate processes, same seed.")
    print("=" * 78)
    ok = True
    for arm in ("sim", "played"):
        reps = run_many([(arm, 8000, f"_r{i}") for i in range(3)])
        fps = [r.get("fingerprint") for r in reps]
        dws = [r.get("draws") for r in reps]
        trs = [r.get("turns") for r in reps]
        same = len(set(fps)) == 1 and len(set(dws)) == 1
        ok &= same
        print(f"  {arm}:")
        for i, r in enumerate(reps):
            print(f"      pass-{i+1}  fingerprint={r.get('fingerprint')}  "
                  f"turns={r.get('turns')}  draws={(r.get('draws') or 0):,}"
                  + (f"  ERROR {r['error']}" if r.get("error") else ""))
        print(f"      -> {'✅ identical' if same else '❌ NOT identical'}"
              f"  (fingerprints {len(set(fps))} distinct, draw counts {len(set(dws))} distinct)")
    print()
    return ok


def agg(rows):
    n = len(rows)
    g = lambda k: [r[k] for r in rows if r.get(k) is not None]
    tot = lambda k: sum(r.get(k) or 0 for r in rows)
    rt = Counter()
    for r in rows:
        rt.update(r.get("result_types") or {})
    ent = tot("entries")
    return {
        "n": n,
        "turns": tot("turns") / n,
        "points": (sum(v for r in rows for v in (r.get("score") or {}).values())
                   / (2 * n)) if any(isinstance(r.get("score"), dict) for r in rows) else float("nan"),
        "draws": tot("draws") / n,
        "rt": {k: v / n for k, v in rt.items()},
        "ft_awards": tot("ft_awards") / n,
        "ft_windowed": tot("ft_windowed") / n,
        "honour_pct": (tot("ft_windowed") / tot("ft_awards") * 100) if tot("ft_awards") else 0,
        "shots": tot("shots") / n,
        "entries": ent / n,
        "fouls": tot("fouls") / n,
        "contest_share": (ent / tot("shots") * 100) if tot("shots") else 0,
        "foul_rate": (tot("fouls") / ent * 100) if ent else 0,
        "score_mean": st.mean(g("score_mean")) if g("score_mean") else float("nan"),
        "dist_mean": st.mean(g("dist_mean")) if g("dist_mean") else float("nan"),
        "dist_median": st.mean(g("dist_median")) if g("dist_median") else float("nan"),
        "factor_mean": st.mean(g("factor_mean")) if g("factor_mean") else float("nan"),
        "tight_pct": (tot("tight") / tot("n_graded") * 100) if tot("n_graded") else float("nan"),
        # NB: must SUM across games. A dict comprehension here silently kept only the last
        # game's counts (reported 77 for 20 games when one game alone logs 90).
        "src": dict(sum((Counter(r.get("src") or {}) for r in rows), Counter())),
        "src_pure": sum(1 for r in rows if len(r.get("src") or {}) == 1),
    }


def pct(a, b):
    return f"{(b - a) / a * 100:+.1f}%" if a else "n/a"


def row(label, a, b, fmt="{:>9.2f}"):
    return f"  {label:<32} {fmt.format(a)} {fmt.format(b)}   {pct(a, b)}"


if __name__ == "__main__":
    games = int(os.environ.get("GAMES", "20"))
    if not gate_independence():
        print("GATE 1 FAILED — arms are still not independent. No figure from this run is")
        print("reportable. Fix the harness before measuring anything.")
        raise SystemExit(1)

    print("=" * 78)
    print(f"MEASURING — seeds 8000-{8000+games-1}, one process per (arm, seed)")
    print("=" * 78)
    jobs = [("sim", 8000 + i) for i in range(games)] + \
           [("played", 8000 + i) for i in range(games)]
    res = run_many(jobs)
    sim = [r for r in res if r["arm"] == "sim" and not r.get("error")]
    pl = [r for r in res if r["arm"] == "played" and not r.get("error")]
    errs = [r for r in res if r.get("error")]
    for e in errs:
        print(f"  ⚠️  {e['arm']} seed {e['seed']}: {e['error'][:160]}")
    print(f"  completed: sim {len(sim)}/{games}, played {len(pl)}/{games}")
    if not sim or not pl:
        raise SystemExit("no usable games")
    S, P = agg(sim), agg(pl)
    with open(os.path.join(ROOT, "scratch_equiv_v3_results.json"), "w") as f:
        json.dump({"sim": sim, "played": pl}, f, indent=1)
    print("  per-game results written to scratch_equiv_v3_results.json (auditable)")

    print("\n" + "=" * 78)
    print("GATE 2 — FT-HONOUR PARITY")
    print("=" * 78)
    print(f"  awards honoured   sim {S['honour_pct']:5.1f}%   played {P['honour_pct']:5.1f}%"
          f"   gap {abs(S['honour_pct']-P['honour_pct']):.1f}pp")
    if abs(S["honour_pct"] - P["honour_pct"]) > 3.0:
        print("  ❌ ARMS DISAGREE — harness is lying. Nothing below is reportable.")
        raise SystemExit(1)
    print("  ✅ arms agree")

    print("\n" + "=" * 78)
    print("DIVERGENCE (equiv-v3). Every equiv-v1/v2 figure is void; these are not compared")
    print("against them, and no prior expectation is carried in.")
    print("=" * 78)
    print(f"  {'':<32} {'sim':>9} {'played':>9}")
    print(row("turns/game", S["turns"], P["turns"]))
    print(row("points/team/game", S["points"], P["points"]))
    print(row("sim_rng draws/game", S["draws"], P["draws"], "{:>9,.0f}"))
    for k in ("MAKE", "MISS", "FREE_THROW", "STEAL", "FOUL", "BLOCK"):
        a, b = S["rt"].get(k, 0), P["rt"].get(k, 0)
        if a or b:
            print(row(k, a, b))

    print("\n" + "=" * 78)
    print("FT DECOMPOSITION — shooting fouls = shots x contested share x foul-rate")
    print("=" * 78)
    print(row("FT awards/game", S["ft_awards"], P["ft_awards"]))
    print(row("shots (shot-score calls)", S["shots"], P["shots"]))
    print(row("x contested share (%)", S["contest_share"], P["contest_share"]))
    print(row("x foul-rate per contest (%)", S["foul_rate"], P["foul_rate"]))
    print(row("= shooting fouls/game", S["fouls"], P["fouls"]))
    prod = ((P["shots"] / S["shots"]) * (P["contest_share"] / S["contest_share"])
            * (P["foul_rate"] / S["foul_rate"])) if S["shots"] and S["contest_share"] and S["foul_rate"] else float("nan")
    obs = P["fouls"] / S["fouls"] if S["fouls"] else float("nan")
    print(f"\n  three terms multiply to {prod:.4f} vs {obs:.4f} observed "
          f"({'exact' if abs(prod-obs) < 0.01 else 'MISMATCH — a term is missing'})")
    if not math.isnan(prod) and prod > 1e-9:
        tl = [math.log(P["shots"]/S["shots"]), math.log(P["contest_share"]/S["contest_share"]),
              math.log(P["foul_rate"]/S["foul_rate"])]
        tot = sum(tl)
        if abs(tot) > 1e-9:
            print(f"  share of effect:  shots {tl[0]/tot*100:.0f}%   "
                  f"contested share {tl[1]/tot*100:.0f}%   foul-rate {tl[2]/tot*100:.0f}%")

    print("\n" + "=" * 78)
    print("PLACEMENT CHANNEL — proximity, and which source the shot contest read")
    print("=" * 78)
    print(row("defender dist mean (grid)", S["dist_mean"], P["dist_mean"]))
    print(row("defender dist median", S["dist_median"], P["dist_median"]))
    print(row("proximity factor mean", S["factor_mean"], P["factor_mean"], "{:>9.3f}"))
    print(row("tight (<=3 grid) %", S["tight_pct"], P["tight_pct"]))
    print(row("defense_score mean", S["score_mean"], P["score_mean"]))
    print("\n  ShotAttemptGeometry.source:")
    for arm, d in (("sim", S), ("played", P)):
        t = sum(d["src"].values()) or 1
        print(f"      {arm:<8} " + "  ".join(f"{k}={v:,} ({v/t*100:.0f}%)"
                                             for k, v in d["src"].items())
              + f"   [games logging exactly one label: {d['src_pure']}/{d['n']}]")
