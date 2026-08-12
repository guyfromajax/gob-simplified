#!/usr/bin/env python3
"""
Post-deploy verification. Confirms the deploy ACTUALLY TOOK — code, config and data.

Nothing else on the deploy checklist proves this, and "prod silently diverged from
develop for 158 commits" is exactly the failure it closes. Every check reports what it
saw, not just pass/fail, so a partial deploy is diagnosable rather than just red.

  A. BUILD    /health reports the running commit, PYTHONHASHSEED and GOB_DB_ACCESS.
  B. DATA     the collections the deploy copies match the staging snapshot that was
              shipped (checksums, not counts — counts matched while content differed).
  C. SEEDING  a throwaway franchise's seeded values match what the new code produces.

WHY C NEEDS A FRANCHISE FROM YOU: creating one requires an authenticated session
(POST /franchise/select-team), which this script deliberately does not embed. Create a
throwaway in the UI on prod, pass its id, and use --delete when done.

usage:
  scripts/verify_deploy.py --health-url https://<prod>/health --expect-commit <sha>
  scripts/verify_deploy.py --franchise-id <id> [--delete]
  scripts/verify_deploy.py --data --snapshot ~/gob-measurement-archive/db_backups_predeploy
"""

from __future__ import annotations

# Pin PYTHONHASHSEED before anything else. See BackEnd/utils/repro. Loaded BY PATH so this
# does not import the BackEnd.utils package, whose __init__ pulls in stat_updater -> db.
import os as _os, sys as _sys, importlib.util as _ilu
_GOB_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _GOB_ROOT)
_spec = _ilu.spec_from_file_location(
    "_gob_repro", _os.path.join(_GOB_ROOT, "BackEnd", "utils", "repro.py"))
_repro = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_repro)
_repro.pin_hash_seed()

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
import urllib.request

# Collections the deploy copies staging -> prod. Skeletons are DELIBERATELY ABSENT:
# their content is identical across databases and only the _id differs, so copying
# them would churn prod for no benefit. See projects/bugs.md.
COPIED_COLLECTIONS = ("players", "recruit_sets")

# shot_threshold is DERIVED from the constants so it cannot go stale — it already did
# once: this file hardcoded (80, 90) while the leveling pass moved init to 95-105, which
# would have failed check C on a perfectly good deploy.
from BackEnd.constants.shot_threshold_scale import (  # noqa: E402
    FRANCHISE_INIT_LO as _ST_LO, FRANCHISE_INIT_HI as _ST_HI,
)

# The other two are literals in TeamManager.init_team_attributes rather than named
# constants, so they cannot be derived and MUST be updated here by hand if that changes.
EXPECTED_SEED = {
    "rebound_modifier": (0.5, 0.5),      # team_manager.py, franchise branch
    "team_chemistry": (8, 11),           # team_manager.py, randint(8, 11)
    "shot_threshold": (_ST_LO, _ST_HI),  # derived
}
EXPECTED_CLAMPS = {
    "discipline": (-20, 20), "fight": (-20, 20),
    "offensive_efficiency": (-20, 20), "defensive_efficiency": (-20, 20),
    "fb_efficiency": (-20, 20), "pt_efficiency": (-20, 20),
    "fb_opp_modifier": (-20, 20), "pt_opp_modifier": (-20, 20),
}

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, msg: str) -> bool:
    RESULTS.append((ok, msg))
    print(f"  {'PASS' if ok else 'FAIL'}  {msg}")
    return ok


def section(t: str) -> None:
    print("\n" + "=" * 74 + f"\n{t}\n" + "=" * 74)


# ── A. build ─────────────────────────────────────────────────────────────────────────
def verify_build(url: str, expect_commit: str | None) -> None:
    section("A. BUILD — is the running code what we shipped?")
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            body = json.loads(r.read().decode())
    except Exception as e:
        check(False, f"{url} unreachable: {type(e).__name__}: {e}")
        return
    print(f"       /health -> {body}")
    commit = str(body.get("commit", "unknown"))
    check(commit not in ("", "unknown"),
          f"reports a commit ({commit}) — 'unknown' means the build has no SHA injected")
    if expect_commit:
        check(commit.startswith(expect_commit[:9]) or expect_commit.startswith(commit[:9]),
              f"running commit {commit} matches expected {expect_commit}")
    check(str(body.get("hash_seed")) == "0",
          f"PYTHONHASHSEED=0 in the running process (got {body.get('hash_seed')!r}) "
          f"— set by start.sh; games are not replayable without it")
    check(str(body.get("db_access")) == "write",
          f"GOB_DB_ACCESS=write set in Railway (got {body.get('db_access')!r}) "
          f"— the redundant signal for the prod guard; RAILWAY_* alone also works")


# ── B. data ──────────────────────────────────────────────────────────────────────────
def verify_data(db, snapshot_dir: str) -> None:
    section("B. DATA — did the collection copy land, byte for byte?")
    from bson import json_util
    print(f"       connected to {db.name!r}")
    if db.name != "gob":
        check(False, f"expected to be pointed at prod ('gob'), got {db.name!r} — "
                     f"re-run with GOB_DB_ACCESS=read and the prod MONGO_URI")
        return
    for c in COPIED_COLLECTIONS:
        snap = os.path.join(snapshot_dir, f"staging_20260811__{c}.json.gz")
        if not os.path.exists(snap):
            check(False, f"{c}: snapshot missing at {snap}")
            continue
        want_docs = json_util.loads(gzip.open(snap, "rt", encoding="utf-8").read())
        # Compare CONTENT ignoring _id: prod and staging assign different ObjectIds to
        # the same logical document. Counts alone are not enough — recruit_sets matched
        # on count while differing by 150 recruits.
        def canon(docs):
            out = sorted(json_util.dumps({k: v for k, v in d.items() if k != "_id"},
                                         sort_keys=True) for d in docs)
            return hashlib.sha256("".join(out).encode()).hexdigest()[:16], len(out)
        wh, wn = canon(want_docs)
        gh, gn = canon(list(db[c].find({})))
        check(gh == wh, f"{c}: prod content matches the shipped staging snapshot "
                        f"(prod {gn} docs {gh} vs snapshot {wn} docs {wh})")


# ── C. seeding ───────────────────────────────────────────────────────────────────────
def verify_seeding(db, franchise_id: str, delete: bool) -> None:
    section("C. SEEDING — does a NEW franchise get the new init values?")
    from bson import ObjectId
    FTD = db["franchise_team_data"]
    franchises_collection = db["franchises"]
    print(f"       connected to {db.name!r}")
    oid = ObjectId(franchise_id)
    fdoc = franchises_collection.find_one({"_id": oid})
    if not fdoc:
        check(False, f"franchise {franchise_id} not found in {db.name!r}")
        return
    if int(fdoc.get("week") or 1) != 1:
        check(False, f"franchise is at week {fdoc.get('week')} — seeding checks need an "
                     f"UNPLAYED franchise (training moves these values immediately)")
        return
    docs = list(FTD.find({"franchise_id": {"$in": [oid, str(oid)]}},
                         {"team_attributes": 1, "identity": 1, "strategy_settings": 1}))
    check(len(docs) > 0, f"franchise has FTD documents ({len(docs)})")
    if not docs:
        return

    for attr, (lo, hi) in EXPECTED_SEED.items():
        vals = [float((d.get("team_attributes") or {}).get(attr))
                for d in docs if (d.get("team_attributes") or {}).get(attr) is not None]
        if not vals:
            check(False, f"{attr}: not seeded on any FTD")
            continue
        check(min(vals) >= lo - 1e-9 and max(vals) <= hi + 1e-9,
              f"{attr} seeded in [{lo}, {hi}] (observed {min(vals):g}..{max(vals):g}, "
              f"mean {sum(vals)/len(vals):.2f})")

    with_id = sum(1 for d in docs
                  if isinstance(d.get("identity"), dict) and d["identity"].get("offensive_vision"))
    check(with_id == len(docs),
          f"identity persisted on every team ({with_id}/{len(docs)}) — "
          f"0 means franchise-mode identity never ran")

    flat = []
    for k in ("aggression", "hc_trap", "fc_press"):
        vals = [(d.get("strategy_settings") or {}).get(k) for d in docs]
        vals = [v for v in vals if isinstance(v, (int, float))]
        if len(set(vals)) <= 1:
            flat.append(k)
    check(not flat,
          f"identity sliders VARY across teams (flat: {flat or 'none'}) — "
          f"all-equal means FTD is seeding neutral defaults and identity is inert")

    from BackEnd.models.training_execution_v2 import TEAM_ATTR_CLAMPS
    bad = {k: TEAM_ATTR_CLAMPS.get(k) for k, want in EXPECTED_CLAMPS.items()
           if tuple(TEAM_ATTR_CLAMPS.get(k, ())) != want}
    check(not bad, f"core-8 clamps are ±20 (wrong: {bad or 'none'})")
    print("       NOTE: the clamp check reads LOCAL code, not the deployed build — "
          "the running clamps are whatever commit /health reports.")

    if delete:
        n1 = FTD.delete_many({"franchise_id": {"$in": [oid, str(oid)]}}).deleted_count
        n2 = db["franchise_players_data"].delete_many(
            {"franchise_id": {"$in": [oid, str(oid)]}}).deleted_count
        n3 = db["franchise_recruits_data"].delete_many(
            {"franchise_id": {"$in": [oid, str(oid)]}}).deleted_count
        n4 = franchises_collection.delete_one({"_id": oid}).deleted_count
        print(f"\n       deleted throwaway: {n4} franchise, {n1} FTD, {n2} FPD, {n3} FRD")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--health-url")
    ap.add_argument("--db", choices=["gob"], help="Required for --data or --franchise-id")
    ap.add_argument("--expect-commit", default=None,
                    help="short SHA the deploy should be running (default: local HEAD)")
    ap.add_argument("--data", action="store_true", help="run the collection-content checks")
    ap.add_argument("--snapshot",
                    default=os.path.expanduser("~/gob-measurement-archive/db_backups_predeploy"))
    ap.add_argument("--franchise-id", help="throwaway franchise on prod, week 1, unplayed")
    ap.add_argument("--delete", action="store_true", help="delete the throwaway when done")
    args = ap.parse_args()

    if not (args.health_url or args.data or args.franchise_id):
        ap.error("nothing to do — pass --health-url, --data and/or --franchise-id")
    if (args.data or args.franchise_id) and args.db != "gob":
        ap.error("--data and --franchise-id require the explicit target --db gob")
    if args.delete and not args.franchise_id:
        ap.error("--delete requires --franchise-id")

    connection = None
    if args.data or args.franchise_id:
        from scripts.db_migration_cli import connect_migration_target
        connection = connect_migration_target("gob", write=args.delete)

    expect = args.expect_commit
    if args.health_url and not expect:
        try:
            expect = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], cwd=_GOB_ROOT,
                stderr=subprocess.DEVNULL).decode().strip()
            print(f"(no --expect-commit given; using local HEAD {expect})")
        except Exception:
            expect = None

    if args.health_url:
        verify_build(args.health_url, expect)
    if args.data:
        verify_data(connection.database, args.snapshot)
    if args.franchise_id:
        verify_seeding(connection.database, args.franchise_id, args.delete)
    if connection is not None:
        connection.close()

    section("SUMMARY")
    failed = [m for ok, m in RESULTS if not ok]
    print(f"  {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    for m in failed:
        print(f"    FAILED: {m}")
    print("\n" + ("✅ DEPLOY VERIFIED" if not failed else "❌ DEPLOY NOT VERIFIED"))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
