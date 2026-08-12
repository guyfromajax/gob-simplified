#!/usr/bin/env python3
"""
age_up_pool_class_years.py — age the universal pool toward SR40 / JR30 / SO20 / FR10.

WHY: franchise init draws 12/15 from the pool, then adds ~60%-freshman walk-ons. A flat
384-per-year pool opens a franchise ~32% freshman. Real varsity skews upperclassman; the
10/20/30/40 target is exactly the steady state of uniform entry across four class years.

METHOD (development, not regeneration):
  • Promote 230 freshmen → senior via develop_one_offseason ×3 (SO, JR, SR targets).
  • Promote 77 sophomores → junior via develop_one_offseason ×1 (JR target).
  • Pure random selection across the whole pool (not balanced per team).
  • Roll a real growth profile at CURRENT year (peaks on remaining future rungs) BEFORE
    developing; f = 1.0; potential_factor read from the doc (not rewritten).

SCOPE (hard): gob-staging.players ONLY.
  Fields written: year, attributes (incl. anchor_ mirrors), height, weight,
                  position_ratings, development.
  Never touches: entry_tier, position_intent, potential_factor, names, portraits, ids,
                 franchise_*, recruit_sets, teams, or gob.

NOT IDEMPOTENT — re-running would promote another batch. Refuses if the pool already
reads approximately 40/30/20/10.

Usage:
    .venv/bin/python scripts/age_up_pool_class_years.py              # dry-run + manifest
    .venv/bin/python scripts/age_up_pool_class_years.py --commit \\
        --from-manifest tmp/pool_age_up_<ts>/manifest.json           # backup + write
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pymongo.operations import UpdateOne

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.utils.player_development import (  # noqa: E402
    GROWTH_ATTRS,
    JH_ANCHOR_BY_TIER,
    OFFSEASON_ATTRACTOR_ALPHA,
    RUNG_TRANSITIONS,
    develop_one_offseason,
    roll_growth_profile,
)
from BackEnd.utils.player_generation import normalize_year  # noqa: E402
from BackEnd.script_db import STAGING_DB, connect_script_database  # noqa: E402

DB_NAME = STAGING_DB
COLLECTION = "players"
WRITE_FIELDS = frozenset({
    "year", "attributes", "height", "weight", "position_ratings", "development",
})

PROMOTE_FR = 230  # freshman → senior
PROMOTE_SO = 77   # sophomore → junior
TARGET_SHARES = {
    "freshman": 0.10,
    "sophomore": 0.20,
    "junior": 0.30,
    "senior": 0.40,
}
# Refuse if every class year is within this absolute share of target (already aged).
ALREADY_AGED_TOL = 0.025

YEAR_FULL = {"FR": "freshman", "SO": "sophomore", "JR": "junior", "SR": "senior"}
YEAR_ORDER = ("freshman", "sophomore", "junior", "senior")

# Shape-preservation abort — level-only rescale must keep attribute ratios.
SHAPE_COSINE_MIN = 0.990
SHAPE_COSINE_MEDIAN_MIN = 0.999


def _quantile(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    idx = p * (len(s) - 1)
    lo = int(idx)
    frac = idx - lo
    hi = min(lo + 1, len(s) - 1)
    return s[lo] * (1 - frac) + s[hi] * frac


def _pct_line(label: str, before: list[float], after: list[float]) -> str:
    def fmt(xs):
        if not xs:
            return "n/a"
        return (f"p10={_quantile(xs, 0.10):5.1f}  p50={_quantile(xs, 0.50):5.1f}  "
                f"p90={_quantile(xs, 0.90):5.1f}  (n={len(xs)})")
    return f"  {label:10} before {fmt(before)}\n  {label:10} after  {fmt(after)}"


def _top_rt(ratings: dict | None) -> float:
    if not ratings:
        return 0.0
    vals = [float(v) for v in ratings.values() if isinstance(v, (int, float))]
    return max(vals) if vals else 0.0


def _growth_vec(attrs: dict) -> list[float]:
    return [float(attrs.get(a) or attrs.get(f"anchor_{a}") or 0) for a in GROWTH_ATTRS]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def _year_counts(docs: list[dict]) -> Counter:
    return Counter(str(d.get("year") or "").strip().lower() for d in docs)


def _already_aged(counts: Counter, total: int) -> bool:
    if total <= 0:
        return False
    for y, share in TARGET_SHARES.items():
        actual = counts.get(y, 0) / total
        if abs(actual - share) > ALREADY_AGED_TOL:
            return False
    return True


def _assert_db(db) -> None:
    if db.name != DB_NAME:
        raise SystemExit(
            f"Refusing: target DB is {db.name!r}, expected {DB_NAME!r}. No writes."
        )


def _remaining_peak_rungs(current_code: str) -> list[str]:
    """Peaks on destination rungs still ahead of the player (not the arrived year)."""
    idx = RUNG_TRANSITIONS.index(current_code)
    return list(RUNG_TRANSITIONS[idx + 1 :])


def _player_for_develop(doc: dict) -> dict:
    tier = doc.get("entry_tier") or "Average"
    if tier not in JH_ANCHOR_BY_TIER:
        raise SystemExit(f"unknown entry_tier {tier!r} on {doc.get('player_id')}")
    pos = doc.get("position_intent") or doc.get("training_position") or "SF"
    attrs = dict(doc.get("attributes") or {})
    return {
        "attributes": attrs,
        "height": int(doc.get("height") or 0),
        "weight": int(doc.get("weight") or 0),
        "position": pos,
        "training_position": pos,
        "jh_anchor": float(JH_ANCHOR_BY_TIER[tier]),
        "position_ratings": dict(doc.get("position_ratings") or {}),
    }


def _promote_one(doc: dict, targets: list[str], rng: random.Random) -> dict:
    """Roll profile + run develop targets. Returns $set payload (WRITE_FIELDS only)."""
    if doc.get("development"):
        raise SystemExit(
            f"player {doc.get('player_id')} already has development — unexpected; aborting"
        )
    current = normalize_year(doc.get("year"))
    remaining = _remaining_peak_rungs(current)
    if not remaining:
        raise SystemExit(f"no remaining rungs for {doc.get('player_id')} year={doc.get('year')}")

    attrs = doc.get("attributes") or {}
    ch_seed = int(attrs.get("anchor_CH", attrs.get("CH", rng.randint(1, 100))) or rng.randint(1, 100))
    ch_seed = max(1, min(100, ch_seed))
    profile = roll_growth_profile(ch_seed, rng, eligible_peak_rungs=remaining)

    pf = doc.get("potential_factor")
    if pf is None:
        pf = 1.0
    else:
        pf = float(pf)

    player = _player_for_develop(doc)
    before_vec = _growth_vec(player["attributes"])

    for rung in targets:
        develop_one_offseason(
            player,
            rung,
            profile,
            rng,
            accumulator=None,
            coaching_f_value=1.0,
            potential_factor=pf,
        )

    after_vec = _growth_vec(player["attributes"])
    cos = _cosine(before_vec, after_vec)
    final_year = YEAR_FULL[targets[-1]]
    set_doc = {
        "year": final_year,
        "attributes": player["attributes"],
        "height": int(player["height"]),
        "weight": int(player["weight"]),
        "position_ratings": player["position_ratings"],
        "development": profile,
    }
    extra = set(set_doc) - WRITE_FIELDS
    if extra:
        raise SystemExit(f"RED FLAG: $set has unexpected fields {extra}")
    return {
        "set_doc": set_doc,
        "cosine": cos,
        "before_vec": before_vec,
        "after_vec": after_vec,
        "before_rt": _top_rt(doc.get("position_ratings")),
        "after_rt": _top_rt(player["position_ratings"]),
        "before_height": int(doc.get("height") or 0),
        "after_height": int(player["height"]),
        "peak_count": int(profile.get("peak_count") or 0),
        "peak_rungs": list(profile.get("peak_rungs") or []),
        "entry_tier": doc.get("entry_tier"),
        "potential_factor": pf,
        "jh_anchor": float(JH_ANCHOR_BY_TIER[doc.get("entry_tier") or "Average"]),
        "from_year": str(doc.get("year")),
        "to_year": final_year,
        "name": f"{doc.get('first_name', '?')} {doc.get('last_name', '?')}",
        "team": doc.get("team"),
        "position_intent": doc.get("position_intent"),
        "player_id": str(doc.get("player_id") or doc.get("_id")),
        "_id": str(doc["_id"]),
    }


def _select_and_promote(docs: list[dict], rng: random.Random) -> list[dict]:
    by_year = defaultdict(list)
    for d in docs:
        by_year[str(d.get("year") or "").strip().lower()].append(d)

    fr = list(by_year.get("freshman") or [])
    so = list(by_year.get("sophomore") or [])
    if len(fr) < PROMOTE_FR:
        raise SystemExit(f"need {PROMOTE_FR} freshmen, have {len(fr)}")
    if len(so) < PROMOTE_SO:
        raise SystemExit(f"need {PROMOTE_SO} sophomores, have {len(so)}")

    fr_pick = rng.sample(fr, PROMOTE_FR)
    so_pick = rng.sample(so, PROMOTE_SO)

    results = []
    for d in fr_pick:
        results.append(_promote_one(d, ["SO", "JR", "SR"], rng))
    for d in so_pick:
        results.append(_promote_one(d, ["JR"], rng))
    return results


def _shape_ok(results: list[dict]) -> tuple[bool, str]:
    cosines = [r["cosine"] for r in results]
    med = statistics.median(cosines)
    mn = min(cosines)
    ok = mn >= SHAPE_COSINE_MIN and med >= SHAPE_COSINE_MEDIAN_MIN
    msg = (f"shape cosine over promoted cohort: min={mn:.6f} median={med:.6f} "
           f"(abort if min<{SHAPE_COSINE_MIN} or median<{SHAPE_COSINE_MEDIAN_MIN})")
    return ok, msg


def _report(
    db_name: str,
    docs: list[dict],
    results: list[dict],
    seed: int,
    out_dir: Path,
) -> None:
    before_counts = _year_counts(docs)
    total = len(docs)
    after_counts = Counter(before_counts)
    for r in results:
        after_counts[r["from_year"]] -= 1
        after_counts[r["to_year"]] += 1

    print("=" * 78)
    print("POOL CLASS-YEAR AGE-UP — DRY-RUN MANIFEST")
    print("=" * 78)
    print(f"TARGET   database={db_name!r}  collection={COLLECTION!r}")
    print(f"SCOPE    {COLLECTION} only; $set fields={sorted(WRITE_FIELDS)}")
    print(f"SEED     {seed}")
    print(f"ATTRACTOR OFFSEASON_ATTRACTOR_ALPHA={OFFSEASON_ATTRACTOR_ALPHA} "
          f"(must be 0.0 for level-only)")
    print()
    print("COUNTS PROMOTED")
    print(f"  freshmen → senior : {sum(1 for r in results if r['from_year']=='freshman')}")
    print(f"  sophomores → junior: {sum(1 for r in results if r['from_year']=='sophomore')}")
    print(f"  total movers       : {len(results)}")
    print()
    print("CLASS-YEAR DISTRIBUTION  before → after")
    for y in YEAR_ORDER:
        b, a = before_counts.get(y, 0), after_counts.get(y, 0)
        print(f"  {y:10}  {b:4d} ({100*b/total:5.1f}%) → {a:4d} ({100*a/total:5.1f}%)  "
              f"target {100*TARGET_SHARES[y]:.0f}%")
    print()

    # Per-team freshmen promoted
    fr_by_team: dict[str, int] = defaultdict(int)
    teams_with_fr = set()
    for d in docs:
        if str(d.get("year") or "").lower() == "freshman":
            teams_with_fr.add(str(d.get("team") or "?"))
    for r in results:
        if r["from_year"] == "freshman":
            fr_by_team[str(r.get("team") or "?")] += 1
    # include teams that had freshmen but promoted zero
    for t in teams_with_fr:
        fr_by_team.setdefault(t, 0)
    promo_counts = sorted(fr_by_team.values())
    unchanged = sum(1 for c in promo_counts if c == 0)
    print("PER-TEAM FRESHMEN PROMOTED (among teams that had ≥1 freshman)")
    if promo_counts:
        print(f"  teams={len(promo_counts)}  min={min(promo_counts)}  "
              f"median={statistics.median(promo_counts):.1f}  max={max(promo_counts)}  "
              f"unchanged={unchanged}")
        hist = Counter(promo_counts)
        print("  histogram:", dict(sorted(hist.items())))
    print()

    # RT by class year before/after (after = simulated full pool)
    after_rt_by_year: dict[str, list[float]] = defaultdict(list)
    before_rt_by_year: dict[str, list[float]] = defaultdict(list)
    moved_ids = {r["player_id"] for r in results}
    result_by_id = {r["player_id"]: r for r in results}
    for d in docs:
        y = str(d.get("year") or "").lower()
        before_rt_by_year[y].append(_top_rt(d.get("position_ratings")))
        pid = str(d.get("player_id") or d.get("_id"))
        if pid in moved_ids:
            r = result_by_id[pid]
            after_rt_by_year[r["to_year"]].append(r["after_rt"])
        else:
            after_rt_by_year[y].append(_top_rt(d.get("position_ratings")))

    print("RT (top position_rating) p10/p50/p90 by class year")
    for y in YEAR_ORDER:
        print(_pct_line(y, before_rt_by_year.get(y, []), after_rt_by_year.get(y, [])))
    print()

    # Promoted cohort vs tier anchors
    print("PROMOTED COHORT — RT vs flat ladder anchor (jh_anchor × rung multiple @ f=1, pf=1)")
    from BackEnd.utils.player_generation import RUNG_MULTIPLIERS
    fr_prom = [r for r in results if r["from_year"] == "freshman"]
    so_prom = [r for r in results if r["from_year"] == "sophomore"]
    for label, cohort, dest in (
        ("FR→SR", fr_prom, "SR"),
        ("SO→JR", so_prom, "JR"),
    ):
        if not cohort:
            continue
        deltas = []
        by_peaks: dict[int, list[float]] = defaultdict(list)
        for r in cohort:
            flat = r["jh_anchor"] * RUNG_MULTIPLIERS[dest]
            deltas.append(r["after_rt"] - flat)
            by_peaks[r["peak_count"]].append(r["after_rt"])
        print(f"  {label} n={len(cohort)}  after RT p10/p50/p90="
              f"{_quantile([r['after_rt'] for r in cohort], 0.10):.1f}/"
              f"{_quantile([r['after_rt'] for r in cohort], 0.50):.1f}/"
              f"{_quantile([r['after_rt'] for r in cohort], 0.90):.1f}")
        print(f"    vs flat ladder: ΔRT p10/p50/p90="
              f"{_quantile(deltas, 0.10):+.1f}/{_quantile(deltas, 0.50):+.1f}/"
              f"{_quantile(deltas, 0.90):+.1f}")
        peak_hist = Counter(r["peak_count"] for r in cohort)
        print(f"    peak_count hist: {dict(sorted(peak_hist.items()))}")
        for k in sorted(by_peaks):
            xs = by_peaks[k]
            print(f"      peaks={k}: mean RT={statistics.mean(xs):.1f} n={len(xs)}")
    print()

    ok, shape_msg = _shape_ok(results)
    print("SHAPE CHECK (level-only must preserve attribute ratios)")
    print(f"  {shape_msg}")
    print(f"  → {'PASS ✓' if ok else 'FAIL ✗ — STOP; branch may predate attractor retirement'}")
    # Sample: prefer high-SH relative shooters among FR→SR
    scored = []
    for r in fr_prom:
        before = {a: v for a, v in zip(GROWTH_ATTRS, r["before_vec"])}
        sh = before.get("SH", 0)
        mean = statistics.mean(before.values()) or 1.0
        scored.append((sh / mean, r["player_id"], r))
    scored.sort(key=lambda t: (-t[0], t[1]))
    sample = [r for _, _, r in scored[:4]] + so_prom[:2]
    print("  sample before → after (GROWTH_ATTRS; ratios should hold):")
    for r in sample:
        b = {a: int(v) for a, v in zip(GROWTH_ATTRS, r["before_vec"])}
        a = {a: int(v) for a, v in zip(GROWTH_ATTRS, r["after_vec"])}
        print(f"    {r['name']}  {r['from_year']}→{r['to_year']}  "
              f"pos={r['position_intent']}  cos={r['cosine']:.6f}  "
              f"peaks={r['peak_count']}{r['peak_rungs']}")
        print(f"      before {b}")
        print(f"      after  {a}")
        print(f"      RT {r['before_rt']:.0f}→{r['after_rt']:.0f}  "
              f"HT {r['before_height']}→{r['after_height']}")
    print()

    # Height gradient after (full pool simulated)
    after_ht: dict[str, list[float]] = defaultdict(list)
    for d in docs:
        pid = str(d.get("player_id") or d.get("_id"))
        if pid in moved_ids:
            r = result_by_id[pid]
            after_ht[r["to_year"]].append(float(r["after_height"]))
        else:
            after_ht[str(d.get("year") or "").lower()].append(float(d.get("height") or 0))
    print("HEIGHT by class year AFTER (mean; grow-into-frame should be monotone FR≤SO≤JR≤SR)")
    prev = None
    mono = True
    for y in YEAR_ORDER:
        xs = after_ht.get(y, [])
        if not xs:
            continue
        m = statistics.mean(xs)
        if prev is not None and m + 1e-9 < prev:
            mono = False
        print(f"  {y:10} mean={m:.2f}  p50={_quantile(xs, 0.50):.1f}  n={len(xs)}")
        prev = m
    print(f"  → monotone: {'YES ✓' if mono else 'NO ✗'}")
    print()
    print(f"MANIFEST DIR  {out_dir}")
    print("=" * 78)
    if not ok:
        raise SystemExit("SHAPE CHECK FAILED — no manifest write, no commit path.")
    if OFFSEASON_ATTRACTOR_ALPHA != 0.0:
        raise SystemExit(
            f"OFFSEASON_ATTRACTOR_ALPHA={OFFSEASON_ATTRACTOR_ALPHA} — refusing; need 0.0"
        )


def _write_manifest(out_dir: Path, seed: int, results: list[dict], counts_before: dict,
                    counts_after: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "manifest.json"
    payload = {
        "database": DB_NAME,
        "collection": COLLECTION,
        "seed": seed,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "promote_fr": PROMOTE_FR,
        "promote_so": PROMOTE_SO,
        "counts_before": counts_before,
        "counts_after": counts_after,
        "write_fields": sorted(WRITE_FIELDS),
        "movers": [
            {
                "_id": r["_id"],
                "player_id": r["player_id"],
                "from_year": r["from_year"],
                "to_year": r["to_year"],
                "set_doc": r["set_doc"],
                "cosine": r["cosine"],
                "peak_count": r["peak_count"],
                "peak_rungs": r["peak_rungs"],
                "before_rt": r["before_rt"],
                "after_rt": r["after_rt"],
                "team": r["team"],
                "name": r["name"],
            }
            for r in results
        ],
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    # also a short human summary
    (out_dir / "SUMMARY.txt").write_text(
        f"db={DB_NAME}.{COLLECTION}\nseed={seed}\nmovers={len(results)}\n"
        f"before={counts_before}\nafter={counts_after}\n"
        f"manifest={path}\n",
        encoding="utf-8",
    )
    return path


def _backup(db) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    name = f"players_backup_age_up_{ts}"
    src = db[COLLECTION].count_documents({})
    db[COLLECTION].aggregate([{"$match": {}}, {"$out": name}])
    dst = db[name].count_documents({})
    if dst != src:
        raise SystemExit(f"backup count mismatch: src={src} dst={dst}")
    print(f"BACKUP   {DB_NAME}.{COLLECTION} ({src}) → {DB_NAME}.{name}")
    return name


def _commit_from_manifest(db, manifest_path: Path) -> None:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("database") != DB_NAME or data.get("collection") != COLLECTION:
        raise SystemExit(
            f"manifest target {data.get('database')}.{data.get('collection')} "
            f"≠ {DB_NAME}.{COLLECTION}"
        )
    movers = data["movers"]
    ops = []
    for m in movers:
        set_doc = m["set_doc"]
        if set(set_doc) != WRITE_FIELDS:
            raise SystemExit(
                f"manifest $set fields {set(set_doc)} ≠ required {WRITE_FIELDS}"
            )
        # Pool docs use UUID strings for _id (and player_id) — not ObjectId.
        ops.append(UpdateOne({"_id": m["_id"]}, {"$set": set_doc}))

    _assert_db(db)
    _backup(db)
    _assert_db(db)  # again immediately before bulk write
    assert db.name == DB_NAME, "guard bypassed"
    for i in range(0, len(ops), 200):
        db[COLLECTION].bulk_write(ops[i:i + 200], ordered=False)
    print(f"COMMITTED {len(ops)} updates to {db.name}.{COLLECTION}")

    # verify year counts
    counts = _year_counts(list(db[COLLECTION].find({}, {"year": 1})))
    print("POST-WRITE class-year counts:", dict(counts))
    expected = data.get("counts_after") or {}
    for y, n in expected.items():
        if counts.get(y, 0) != n:
            print(f"  WARNING: {y} expected {n} got {counts.get(y, 0)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", choices=[DB_NAME], default=DB_NAME)
    ap.add_argument("--seed", type=int, default=20260808, help="RNG seed (selection + develop)")
    ap.add_argument("--commit", action="store_true",
                    help="backup + write (requires --from-manifest from an approved dry-run)")
    ap.add_argument("--from-manifest", type=Path,
                    help="manifest.json produced by a prior dry-run (required with --commit)")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="directory for dry-run manifest (default tmp/pool_age_up_<ts>)")
    args = ap.parse_args()

    connection = connect_script_database(
        target=args.db,
        access="write" if args.commit else "read",
        pristine_env=dict(os.environ),
        repo_root=ROOT,
    )
    db = connection.database
    _assert_db(db)

    if args.commit:
        if not args.from_manifest:
            raise SystemExit("--commit requires --from-manifest <dry-run manifest.json>")
        print(f"MODE: COMMIT from {args.from_manifest}")
        _commit_from_manifest(db, args.from_manifest)
        connection.close()
        return 0

    # ── dry-run ──────────────────────────────────────────────────────────────
    if OFFSEASON_ATTRACTOR_ALPHA != 0.0:
        raise SystemExit(
            f"ABORT: OFFSEASON_ATTRACTOR_ALPHA={OFFSEASON_ATTRACTOR_ALPHA} (need 0.0). "
            "This branch predates level-only offseason — do not age the pool here."
        )

    docs = list(db[COLLECTION].find({}))
    print(f"loaded {len(docs)} players from {db.name}.{COLLECTION}")
    counts = _year_counts(docs)
    print("current class-year counts:", {y: counts.get(y, 0) for y in YEAR_ORDER})

    if _already_aged(counts, len(docs)):
        raise SystemExit(
            "ABORT: pool class-year distribution already reads approximately "
            "SR40/JR30/SO20/FR10. This script is NOT IDEMPOTENT — refusing to "
            "promote another batch. No writes."
        )

    # Expected flat starting point (warn, don't hard-fail if close)
    for y in YEAR_ORDER:
        if counts.get(y, 0) != 384:
            print(f"  note: expected 384 {y}, have {counts.get(y, 0)}")

    rng = random.Random(args.seed)
    results = _select_and_promote(docs, rng)

    before_counts = {y: counts.get(y, 0) for y in YEAR_ORDER}
    after_counts = dict(before_counts)
    for r in results:
        after_counts[r["from_year"]] -= 1
        after_counts[r["to_year"]] += 1

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = args.out_dir or (ROOT / "tmp" / f"pool_age_up_{ts}")
    _report(db.name, docs, results, args.seed, out_dir)
    path = _write_manifest(out_dir, args.seed, results, before_counts, after_counts)
    print(f"\nMODE: DRY-RUN (no writes)")
    print(f"  Manifest written: {path}")
    print("  Stopped. Approve, then re-run with:")
    print(f"    .venv/bin/python scripts/age_up_pool_class_years.py --commit "
          f"--from-manifest {path}")

    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
