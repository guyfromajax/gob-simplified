#!/usr/bin/env python3
"""§11 league-wide convergence measurement — one master-seeded run.

Full season_advance_harness path (reg → EOS → week-35 recruiting → finish_season),
on scratch DB ``gob-s11-league-convergence``. Measure only; change nothing.

Usage:
    MONGO_DB_NAME=gob-s11-league-convergence FRANCHISE_CPU_SIM_USE_POOL=0 \\
      .venv/bin/python scripts/s11_league_convergence_audit.py --seed 202608061 --seasons 3

Exports under ``tmp/s11_league_convergence/seed_<N>/`` BEFORE any franchise delete.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
import uuid
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

SCRATCH_DB = "gob-s11-league-convergence"
CORE_12 = ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "FT", "ST", "AG", "IQ", "ND")
POSITIONS = ("PG", "SG", "SF", "PF", "C")
YEAR_BUCKETS = ("FR", "SO", "JR", "SR")

os.environ.setdefault("FRANCHISE_CPU_SIM_USE_POOL", "0")


def _configure_validated_scratch_environment(target: str, confirm_db: str | None) -> None:
    """Validate production credentials, then retarget only their URI path to scratch."""
    from BackEnd.script_db import connect_production_cluster_scratch_database

    pristine = dict(os.environ)
    preflight = connect_production_cluster_scratch_database(
        target=target,
        access="write",
        destructive=True,
        confirm_db=confirm_db,
        pristine_env=pristine,
    )
    preflight.close()
    source_uri = pristine.get("MONGO_URI", "")
    parsed = urlsplit(source_uri)
    os.environ["MONGO_URI"] = urlunsplit(
        (parsed.scheme, parsed.netloc, f"/{target}", parsed.query, parsed.fragment)
    )
    os.environ["MONGO_DB_NAME"] = target
    os.environ["ENVIRONMENT"] = "test"


def _norm_year(raw: Any) -> str | None:
    y = str(raw or "").strip().lower()
    if y in {"jh", "junior high", "junior-high"}:
        return None  # exclude JH from FR/SO/JR/SR cuts
    if y.startswith("fr"):
        return "FR"
    if y.startswith("so"):
        return "SO"
    if y.startswith("ju") or y == "jr":
        return "JR"
    if y.startswith("se") or y == "sr":
        return "SR"
    return None


def _core_vals(attrs: dict[str, Any] | None) -> dict[str, float]:
    attrs = attrs or {}
    out = {}
    for a in CORE_12:
        v = attrs.get(f"anchor_{a}", attrs.get(a))
        try:
            out[a] = float(v)
        except (TypeError, ValueError):
            out[a] = float("nan")
    return out


def _best_rt(ratings: dict[str, Any] | None) -> tuple[str, float]:
    ratings = ratings or {}
    if not ratings:
        return "SF", 0.0
    pos = max(ratings, key=lambda k: float(ratings.get(k) or 0))
    return pos, float(ratings.get(pos) or 0)


def _training_pos(doc: dict[str, Any]) -> str:
    tp = doc.get("training_position") or doc.get("position_intent")
    if tp in POSITIONS:
        return str(tp)
    # Attractor default: max RT
    return _best_rt(doc.get("position_ratings"))[0]


def _intent_pos(doc: dict[str, Any]) -> str:
    pi = doc.get("position_intent")
    if pi in POSITIONS:
        return str(pi)
    return _best_rt(doc.get("position_ratings"))[0]


def _stddev(vals: list[float]) -> float | None:
    clean = [v for v in vals if v == v]  # drop nan
    n = len(clean)
    if n < 2:
        return None
    mean = sum(clean) / n
    var = sum((v - mean) ** 2 for v in clean) / (n - 1)  # sample σ
    return math.sqrt(var)


def _player_rows(fpd_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for d in fpd_docs:
        meta = d.get("meta") or {}
        year = _norm_year(meta.get("year"))
        attrs = _core_vals(d.get("attributes"))
        best_pos, best_rt = _best_rt(d.get("position_ratings"))
        rows.append(
            {
                "player_id": d.get("player_id"),
                "team_id": str(meta.get("team_id") or ""),
                "year": year,
                "training_position": _training_pos(d),
                "position_intent": _intent_pos(d),
                "attrs": attrs,
                "best_rt": best_rt,
                "best_pos": best_pos,
            }
        )
    return rows


def _sigma_by_class(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-attribute σ split by class; plus σ(SR)/σ(FR)."""
    by_year: dict[str, list[dict[str, float]]] = {y: [] for y in YEAR_BUCKETS}
    for r in rows:
        if r["year"] in by_year:
            by_year[r["year"]].append(r["attrs"])
    per_attr = {}
    ratios = {}
    for a in CORE_12:
        sig = {}
        for y in YEAR_BUCKETS:
            sig[y] = _stddev([p[a] for p in by_year[y]])
            sig[f"n_{y}"] = len(by_year[y])
        per_attr[a] = sig
        fr, sr = sig.get("FR"), sig.get("SR")
        ratios[a] = (sr / fr) if (fr and sr and fr > 0) else None
    # mean ratio across attrs with defined ratios
    defined = [v for v in ratios.values() if v is not None]
    return {
        "per_attr": per_attr,
        "ratio_sr_fr": ratios,
        "mean_ratio_sr_fr": (sum(defined) / len(defined)) if defined else None,
        "n_by_year": {y: len(by_year[y]) for y in YEAR_BUCKETS},
    }


def _sigma_league_and_within_pos(
    rows: list[dict[str, Any]], *, pos_key: str
) -> dict[str, Any]:
    """League-wide attr σ, within-position attr σ, and RT σ (best RT)."""
    league_attr = {a: _stddev([r["attrs"][a] for r in rows]) for a in CORE_12}
    league_rt = _stddev([r["best_rt"] for r in rows])
    within: dict[str, Any] = {}
    for pos in POSITIONS:
        group = [r for r in rows if r[pos_key] == pos]
        within[pos] = {
            "n": len(group),
            "attr": {a: _stddev([r["attrs"][a] for r in group]) for a in CORE_12},
            "rt": _stddev([r["best_rt"] for r in group]),
            "mean_attr_sigma": None,
        }
        attr_sigs = [v for v in within[pos]["attr"].values() if v is not None]
        within[pos]["mean_attr_sigma"] = (
            sum(attr_sigs) / len(attr_sigs) if attr_sigs else None
        )
    mean_within = [
        within[p]["mean_attr_sigma"]
        for p in POSITIONS
        if within[p]["mean_attr_sigma"] is not None
    ]
    return {
        "pos_key": pos_key,
        "league_attr_sigma": league_attr,
        "league_mean_attr_sigma": (
            sum(v for v in league_attr.values() if v is not None)
            / max(1, sum(1 for v in league_attr.values() if v is not None))
        ),
        "league_rt_sigma": league_rt,
        "within_position": within,
        "mean_within_position_attr_sigma": (
            sum(mean_within) / len(mean_within) if mean_within else None
        ),
    }


def _team_shape_vectors(
    rows: list[dict[str, Any]], *, pos_key: str
) -> dict[str, list[float]]:
    """Per team: concat of per-position mean core-12 (60-d).

    Missing position slot filled with the league-mean vector for that position
    (among teams that have it). Documented fill — avoids zero-padding artifacts.
    """
    # team → pos → list of attr dicts
    nest: dict[str, dict[str, list[dict[str, float]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in rows:
        if not r["team_id"]:
            continue
        nest[r["team_id"]][r[pos_key]].append(r["attrs"])

    # league mean per position
    pos_means: dict[str, dict[str, float]] = {}
    for pos in POSITIONS:
        bucket = []
        for team_pos in nest.values():
            if pos in team_pos and team_pos[pos]:
                # team mean for this pos
                tm = {a: sum(p[a] for p in team_pos[pos]) / len(team_pos[pos]) for a in CORE_12}
                bucket.append(tm)
        if bucket:
            pos_means[pos] = {
                a: sum(b[a] for b in bucket) / len(bucket) for a in CORE_12
            }
        else:
            pos_means[pos] = {a: 0.0 for a in CORE_12}

    vectors = {}
    for tid, team_pos in nest.items():
        vec = []
        for pos in POSITIONS:
            if pos in team_pos and team_pos[pos]:
                mean = {
                    a: sum(p[a] for p in team_pos[pos]) / len(team_pos[pos])
                    for a in CORE_12
                }
            else:
                mean = pos_means[pos]
            vec.extend(mean[a] for a in CORE_12)
        vectors[tid] = vec
    return vectors


def _zscore_rows(vectors: dict[str, list[float]]) -> dict[str, list[float]]:
    if not vectors:
        return {}
    dim = len(next(iter(vectors.values())))
    means = []
    stds = []
    for i in range(dim):
        col = [v[i] for v in vectors.values()]
        m = sum(col) / len(col)
        s = _stddev(col) or 1.0
        means.append(m)
        stds.append(s if s > 1e-9 else 1.0)
    return {
        tid: [(v[i] - means[i]) / stds[i] for i in range(dim)]
        for tid, v in vectors.items()
    }


def _euclid(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _team_distances(rows: list[dict[str, Any]], *, pos_key: str) -> dict[str, Any]:
    raw = _team_shape_vectors(rows, pos_key=pos_key)
    z = _zscore_rows(raw)
    tids = sorted(z.keys())
    if len(tids) < 2:
        return {"n_teams": len(tids), "max_distance": None, "mean_pairwise": None}

    # Overall max / mean pairwise on full shape vector
    dists = []
    max_d = -1.0
    max_pair = None
    for i, a in enumerate(tids):
        for b in tids[i + 1 :]:
            d = _euclid(z[a], z[b])
            dists.append(d)
            if d > max_d:
                max_d = d
                max_pair = (a, b)

    # Per-position: strongest–weakest = max Euclidean between teams' z-scored
    # 12-d mean vectors for that position only.
    per_pos = {}
    for pi, pos in enumerate(POSITIONS):
        sl = slice(pi * 12, (pi + 1) * 12)
        pos_vecs = {tid: z[tid][sl] for tid in tids}
        pd = []
        max_pd = -1.0
        for i, a in enumerate(tids):
            for b in tids[i + 1 :]:
                d = _euclid(list(pos_vecs[a]), list(pos_vecs[b]))
                pd.append(d)
                if d > max_pd:
                    max_pd = d
        per_pos[pos] = {
            "max_distance": max_pd if pd else None,
            "mean_pairwise": (sum(pd) / len(pd)) if pd else None,
        }

    return {
        "n_teams": len(tids),
        "pos_key": pos_key,
        "fill": "missing_position_slot=league_mean_of_teams_with_that_position",
        "max_distance": max_d,
        "max_pair_team_ids": list(max_pair) if max_pair else None,
        "mean_pairwise": sum(dists) / len(dists),
        "per_position": per_pos,
    }


def _ceiling_from_attr_dicts(attr_list: list[dict[str, float]]) -> dict[str, Any]:
    return {
        "n": len(attr_list),
        "per_attr_sigma": {a: _stddev([d[a] for d in attr_list]) for a in CORE_12},
        "mean_attr_sigma": (
            (lambda xs: sum(xs) / len(xs) if xs else None)(
                [
                    _stddev([d[a] for d in attr_list])
                    for a in CORE_12
                    if _stddev([d[a] for d in attr_list]) is not None
                ]
            )
        ),
    }


def measure_snapshot(fpd_docs: list[dict[str, Any]], label: str) -> dict[str, Any]:
    rows = _player_rows(fpd_docs)
    return {
        "label": label,
        "n_players": len(rows),
        "by_class_training_pos_primary": _sigma_by_class(rows),
        # class cut doesn't use position; same numbers either way
        "attr_vs_rt": {
            "training_position": _sigma_league_and_within_pos(
                rows, pos_key="training_position"
            ),
            "position_intent_secondary": _sigma_league_and_within_pos(
                rows, pos_key="position_intent"
            ),
        },
        "team_distance": {
            "training_position": _team_distances(rows, pos_key="training_position"),
            "position_intent_secondary": _team_distances(
                rows, pos_key="position_intent"
            ),
        },
    }


def _jwrite(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str))
    print(f"  [export] {path}")


def _clear_franchise_collections(db) -> None:
    for col in (
        "franchises",
        "franchise_team_data",
        "franchise_players_data",
        "franchise_recruits_data",
        "games",
        "tournaments",
    ):
        n = db[col].delete_many({}).deleted_count
        print(f"  cleared {col}: {n}")


def _snapshot_frd_ceiling(FRD, fid: Any, label: str) -> dict[str, Any]:
    docs = list(FRD.find({"franchise_id": str(fid)}))
    attrs = [_core_vals(d.get("attributes")) for d in docs]
    out = {"label": label, **_ceiling_from_attr_dicts(attrs)}
    return out


def _snapshot_signed_ceiling(signed_players: list[dict[str, Any]], label: str) -> dict[str, Any]:
    attrs = [_core_vals(s.get("attributes")) for s in signed_players]
    return {"label": label, **_ceiling_from_attr_dicts(attrs)}


def run_one_seed(master_seed: int, seasons: int, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Seed EVERYTHING before any BackEnd work that draws RNG.
    random.seed(master_seed)
    # uuid is used for walk-ons / game ids — pin via uuid seed if available (3.13 has uuid.uuid4
    # from os.urandom). Record that uuids are NOT seeded from master; player_ids from pool are
    # stable. Walk-on uuids differ across runs even with same master seed — noted in meta.
    meta = {
        "master_seed": master_seed,
        "scratch_db": SCRATCH_DB,
        "seasons": seasons,
        "cpu_pool": os.environ.get("FRANCHISE_CPU_SIM_USE_POOL"),
        "uuid_note": "uuid4 not seeded from master (os.urandom); pool player_ids stable; walk-on ids vary",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _jwrite(out_dir / "meta.json", meta)

    from bson import ObjectId
    from BackEnd.db import (
        db,
        franchise_players_data_collection as FPD,
        franchise_recruits_data_collection as FRD,
        franchise_team_data_collection as FTD,
    )
    from BackEnd.models.franchise_manager import FranchiseManager
    from BackEnd.utils import stat_updater
    from BackEnd.api import franchise_routes as fr
    from scripts.season_advance_harness import (
        _instrument_finalize,
        run_week_35,
        rollover,
        REGULAR_SEASON_LAST_WEEK,
        EOS_LAST_WEEK,
        advance_regular_week,
        advance_postseason_week,
    )

    if db.name != SCRATCH_DB:
        sys.exit(f"Active DB is {db.name!r}, expected {SCRATCH_DB!r}")
    if db.players.count_documents({}) < 1500:
        sys.exit("Scratch DB missing players — run s11_provision_convergence_scratch.py")

    print(f"Clearing franchise collections on {db.name}…")
    _clear_franchise_collections(db)

    random.seed(master_seed)  # re-seed after any import-time draws
    _instrument_finalize(stat_updater)

    # Pick Couer d'Alene as user team (median; irrelevant to league-wide metrics).
    team = db.teams.find_one({"name": "Couer d'Alene"}) or db.teams.find_one({})
    if not team:
        sys.exit("No teams in scratch DB")
    user_team_oid = team["_id"]
    print(f"Init franchise user_team={team.get('name')!r} seed={master_seed}")

    t_init = time.time()
    mgr = FranchiseManager(db)
    mgr.initialize_season(
        user_team_id=str(team.get("name") or "S11Audit"),
        user_team_object_id=str(user_team_oid),
        user_id=f"s11-convergence-{master_seed}",
    )
    fid = mgr.franchise_id
    print(f"  franchise_id={fid} init={(time.time()-t_init)/60:.1f} min")
    _jwrite(out_dir / "franchise_id.json", {"franchise_id": str(fid), "user_team": team.get("name")})

    # ── t0 ─────────────────────────────────────────────────────────────
    fpd_t0 = list(FPD.find({"franchise_id": str(fid)}))
    t0 = measure_snapshot(fpd_t0, "t0_post_initialize_season")
    _jwrite(out_dir / "t0_metrics.json", t0)
    # Raw FPD export for regression baseline (attrs + keys only — still large).
    raw_t0 = []
    for d in fpd_t0:
        meta_d = d.get("meta") or {}
        raw_t0.append(
            {
                "player_id": d.get("player_id"),
                "team_id": str(meta_d.get("team_id") or ""),
                "year": meta_d.get("year"),
                "height": meta_d.get("height"),
                "training_position": d.get("training_position"),
                "position_intent": d.get("position_intent"),
                "entry_tier": d.get("entry_tier"),
                "potential_factor": d.get("potential_factor"),
                "attributes": {a: (d.get("attributes") or {}).get(a) for a in CORE_12},
                "anchors": {
                    a: (d.get("attributes") or {}).get(f"anchor_{a}") for a in CORE_12
                },
                "position_ratings": d.get("position_ratings"),
            }
        )
    _jwrite(out_dir / "t0_fpd_raw.json", raw_t0)

    ceiling = {
        "generation_pre_sign": [
            _snapshot_frd_ceiling(FRD, fid, "t0_frd_after_init")
        ],
        "signed_pre_rollover": [],
    }
    _jwrite(out_dir / "ceiling_partial.json", ceiling)

    # Headline print for t0
    print("\n=== t0 headline ===")
    _print_headline(t0, ceiling["generation_pre_sign"][-1])

    # ── advance seasons ────────────────────────────────────────────────
    # Custom loop so we can capture signed-pre-rollover between week 35 and finish_season.
    for season_no in range(1, seasons + 1):
        fdoc = db.franchises.find_one({"_id": fid})
        cur = int(fdoc.get("current_season", 1))
        print(f"\n=== season {cur} → {cur+1} (master_seed={master_seed}) ===")
        t0s = time.time()
        week = int(fdoc.get("week", 1))

        while week <= REGULAR_SEASON_LAST_WEEK:
            tw = time.time()
            fdoc = db.franchises.find_one({"_id": fid})
            new_week, _phases = advance_regular_week(
                fr, db, stat_updater, fid, week, user_team_oid, fdoc,
                FPD=FPD, measure_dir=None, season_no=season_no,
            )
            print(f"  reg wk {week:>2} → {new_week:<2}  ({time.time()-tw:.0f}s)")
            if new_week <= week:
                sys.exit(f"regular week {week} did not advance")
            week = new_week

        while REGULAR_SEASON_LAST_WEEK < week <= EOS_LAST_WEEK:
            tw = time.time()
            new_week = advance_postseason_week(fr, db, fid)
            print(f"  eos wk {week:>2} → {new_week:<2}  ({time.time()-tw:.0f}s)")
            if new_week <= week:
                sys.exit(f"postseason week {week} did not advance")
            week = new_week

        fdoc = db.franchises.find_one({"_id": fid})
        if int(fdoc.get("week", 0)) == 35:
            n_signed = run_week_35(fr, db, fid, fdoc, user_team_oid)
            print(f"  wk 35 recruiting: {n_signed} signed → week 36")
            # Signed pre-rollover ceiling (before finish_season develop)
            fdoc = db.franchises.find_one({"_id": fid})
            signed = list(
                ((fdoc.get("week_35_recruiting_results") or {}).get("signed_players"))
                or []
            )
            ceil_s = _snapshot_signed_ceiling(
                signed, f"s{season_no}_signed_pre_rollover"
            )
            ceiling["signed_pre_rollover"].append(ceil_s)
            _jwrite(
                out_dir / f"s{season_no}_signed_pre_rollover.json",
                {"n": len(signed), "ceiling": ceil_s, "sample_ids": [s.get("player_id") for s in signed[:20]]},
            )
            print(
                f"  signed ceiling mean_attr_σ={ceil_s.get('mean_attr_sigma')} n={ceil_s.get('n')}"
            )

        resp = rollover(fr, fid)
        print(f"  rollover done ({(time.time()-t0s)/60:.1f} min this season)")

        # New FRD after finish_season = generation pre-sign ceiling for next season
        ceil_g = _snapshot_frd_ceiling(FRD, fid, f"s{season_no}_frd_post_rollover")
        ceiling["generation_pre_sign"].append(ceil_g)
        _jwrite(out_dir / "ceiling_partial.json", ceiling)
        print(
            f"  generation ceiling mean_attr_σ={ceil_g.get('mean_attr_sigma')} n={ceil_g.get('n')}"
        )

    # ── t+3 ────────────────────────────────────────────────────────────
    fpd_t3 = list(FPD.find({"franchise_id": str(fid)}))
    t3 = measure_snapshot(fpd_t3, f"t_plus_{seasons}_post_rollover")
    _jwrite(out_dir / "t3_metrics.json", t3)
    raw_t3 = []
    for d in fpd_t3:
        meta_d = d.get("meta") or {}
        raw_t3.append(
            {
                "player_id": d.get("player_id"),
                "team_id": str(meta_d.get("team_id") or ""),
                "year": meta_d.get("year"),
                "height": meta_d.get("height"),
                "training_position": d.get("training_position"),
                "position_intent": d.get("position_intent"),
                "entry_tier": d.get("entry_tier"),
                "potential_factor": d.get("potential_factor"),
                "attributes": {a: (d.get("attributes") or {}).get(a) for a in CORE_12},
                "anchors": {
                    a: (d.get("attributes") or {}).get(f"anchor_{a}") for a in CORE_12
                },
                "position_ratings": d.get("position_ratings"),
            }
        )
    _jwrite(out_dir / "t3_fpd_raw.json", raw_t3)
    _jwrite(out_dir / "ceiling.json", ceiling)

    summary = {
        "meta": meta,
        "franchise_id": str(fid),
        "t0": t0,
        "t3": t3,
        "ceiling": ceiling,
        "headline": _headline_block(t0, t3, ceiling),
    }
    _jwrite(out_dir / "summary.json", summary)

    print("\n=== t+3 headline ===")
    _print_headline(t3, ceiling["generation_pre_sign"][-1])
    print("\n=== σ(SR)/σ(FR) at t+3 (primary decision metric) ===")
    ratios = t3["by_class_training_pos_primary"]["ratio_sr_fr"]
    for a, r in ratios.items():
        print(f"  {a}: {r}")
    print(f"  MEAN: {t3['by_class_training_pos_primary']['mean_ratio_sr_fr']}")

    # Delete disposable franchise data but KEEP exports and reference collections.
    print("\nDeleting disposable franchise rows (keeping scratch ref data + exports)…")
    FPD.delete_many({"franchise_id": str(fid)})
    FRD.delete_many({"franchise_id": str(fid)})
    FTD.delete_many({"franchise_id": fid})
    db.franchises.delete_one({"_id": fid})
    db.games.delete_many({"franchise_id": str(fid)})
    print("Done.")
    return summary


def _headline_block(t0, t3, ceiling) -> dict[str, Any]:
    return {
        "mean_ratio_sr_fr_t3": t3["by_class_training_pos_primary"]["mean_ratio_sr_fr"],
        "ratio_sr_fr_t3": t3["by_class_training_pos_primary"]["ratio_sr_fr"],
        "league_mean_attr_sigma": {
            "t0": t0["attr_vs_rt"]["training_position"]["league_mean_attr_sigma"],
            "t3": t3["attr_vs_rt"]["training_position"]["league_mean_attr_sigma"],
        },
        "league_rt_sigma": {
            "t0": t0["attr_vs_rt"]["training_position"]["league_rt_sigma"],
            "t3": t3["attr_vs_rt"]["training_position"]["league_rt_sigma"],
        },
        "mean_within_pos_attr_sigma": {
            "t0": t0["attr_vs_rt"]["training_position"]["mean_within_position_attr_sigma"],
            "t3": t3["attr_vs_rt"]["training_position"]["mean_within_position_attr_sigma"],
        },
        "team_mean_pairwise": {
            "t0": t0["team_distance"]["training_position"]["mean_pairwise"],
            "t3": t3["team_distance"]["training_position"]["mean_pairwise"],
        },
        "team_max_distance": {
            "t0": t0["team_distance"]["training_position"]["max_distance"],
            "t3": t3["team_distance"]["training_position"]["max_distance"],
        },
        "ceiling_generation_mean_attr_sigma": [
            c.get("mean_attr_sigma") for c in ceiling["generation_pre_sign"]
        ],
        "ceiling_signed_mean_attr_sigma": [
            c.get("mean_attr_sigma") for c in ceiling["signed_pre_rollover"]
        ],
    }


def _print_headline(snap, ceil_gen) -> None:
    bc = snap["by_class_training_pos_primary"]
    av = snap["attr_vs_rt"]["training_position"]
    td = snap["team_distance"]["training_position"]
    print(f"  n_players={snap['n_players']} n_by_year={bc['n_by_year']}")
    print(f"  mean σ(SR)/σ(FR)={bc['mean_ratio_sr_fr']}")
    print(
        f"  league mean attr σ={av['league_mean_attr_sigma']:.3f}  "
        f"league RT σ={av['league_rt_sigma']:.3f}  "
        f"mean within-pos attr σ={av['mean_within_position_attr_sigma']}"
    )
    print(
        f"  team mean pairwise={td['mean_pairwise']}  max={td['max_distance']}"
    )
    print(
        f"  ceiling generation mean attr σ={ceil_gen.get('mean_attr_sigma')} n={ceil_gen.get('n')}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, choices=[SCRATCH_DB])
    ap.add_argument("--confirm-db", required=True)
    ap.add_argument("--apply", action="store_true", help="Required: provisions and mutates scratch data")
    ap.add_argument("--seed", type=int, required=True, help="Master seed for this run")
    ap.add_argument("--seasons", type=int, default=3)
    ap.add_argument(
        "--out-root",
        default=str(_REPO / "tmp" / "s11_league_convergence"),
    )
    args = ap.parse_args()
    if not args.apply:
        ap.error("this measurement mutates its scratch database; re-run with --apply")
    _configure_validated_scratch_environment(args.db, args.confirm_db)
    out_dir = Path(args.out_root) / f"seed_{args.seed}"
    print(f"OUT={out_dir}")
    run_one_seed(args.seed, args.seasons, out_dir)


if __name__ == "__main__":
    main()
