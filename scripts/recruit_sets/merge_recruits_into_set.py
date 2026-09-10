"""Merge an add-on (from build_recruit_set.py --append-to) into the base set.

Run this LAST — after the add-on's kits are built (build_recruit_images.py) and
uploaded to R2 — so the newly-merged recruits have portraits ready.

Two independent merges, both idempotent by recruit_id (a recruit already present
is skipped, so re-running never double-adds and never re-bumps version):

  * DB    : appends the new recruits to the recruit_sets doc in the connected
            database (dry-run unless --commit; prints which DB it hits).
  * REPO  : with --update-repo-file, folds them into scripts/recruit_sets/
            set_<id>.json AND its .manifest.json so the tracked artifact stays in
            sync (a plain local file write — no DB, no --commit needed).

Both set recruit_count to the new length and bump version by 1 (only when there
is actually something new to add).

Usage:
    # DB dry-run (staging via .env.local) — see the plan, write nothing
    python scripts/recruit_sets/merge_recruits_into_set.py --addon scripts/recruit_sets/set_0001_add100.json
    # commit to the connected DB
    MONGO_URI="<uri>" python scripts/recruit_sets/merge_recruits_into_set.py --addon .../set_0001_add100.json --commit
    # update the tracked repo files (local, safe)
    python scripts/recruit_sets/merge_recruits_into_set.py --addon .../set_0001_add100.json --update-repo-file
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)


def _load(path):
    with open(path) as f:
        return json.load(f)


def _new_recruits(addon_recruits, existing_ids):
    """Add-on recruits whose recruit_id is not already present (idempotent merge)."""
    seen = set(existing_ids)
    out = []
    for r in addon_recruits:
        rid = r.get("recruit_id")
        if rid and rid not in seen:
            seen.add(rid)
            out.append(r)
    return out


def merge_db(addon, commit):
    from BackEnd.db import db, client
    is_mock = "mongomock" in type(client).__module__
    banner = f"DB: {db.name} | conn: {'MOCK (no MONGO_URI)' if is_mock else 'REAL'}"
    print("=" * len(banner)); print(banner); print("=" * len(banner))

    set_id = addon["set_id"]
    doc = db.recruit_sets.find_one({"set_id": set_id})
    if not doc:
        print(f"  ⚠️  set_id={set_id} not found in {db.name}.recruit_sets — nothing to merge into.")
        return
    existing = doc.get("recruits") or []
    existing_ids = {r.get("recruit_id") for r in existing}
    new = _new_recruits(addon["recruits"], existing_ids)
    after = len(existing) + len(new)
    cur_v = int(doc.get("version", 1) or 1)

    print(f"  {set_id}: {len(existing)} existing (v{cur_v}) | add-on {len(addon['recruits'])} "
          f"| NEW to add {len(new)} | already-present {len(addon['recruits']) - len(new)}")
    if not new:
        print("  nothing new to add — already merged. No write.")
        return
    print(f"  -> would become recruit_count={after}, version={cur_v + 1}")

    if commit:
        db.recruit_sets.update_one(
            {"set_id": set_id},
            {"$push": {"recruits": {"$each": new}},
             "$set": {"recruit_count": after, "version": cur_v + 1}},
        )
        print(f"  ✔ committed: appended {len(new)} recruits -> {after}, version -> {cur_v + 1}")
    else:
        print("  DRY-RUN — nothing written. Re-run with --commit to persist.")


def merge_repo_file(addon, set_file):
    """Fold the add-on into the tracked set_<id>.json and its .manifest.json."""
    man_file = set_file.replace(".json", ".manifest.json")
    addon_man_file = None
    # add-on manifest sits beside the add-on set file
    cand = None
    for a in (addon.get("_path"),):
        if a:
            cand = a.replace(".json", ".manifest.json")
    addon_man_file = cand

    base = _load(set_file)
    existing_ids = {r.get("recruit_id") for r in base.get("recruits", [])}
    new = _new_recruits(addon["recruits"], existing_ids)
    cur_v = int(base.get("version", 1) or 1)
    print(f"  repo {os.path.basename(set_file)}: {len(base['recruits'])} existing (v{cur_v}) "
          f"| NEW to add {len(new)}")
    if not new:
        print("  repo file already contains these recruits — no change.")
        return

    base["recruits"].extend(new)
    base["recruit_count"] = len(base["recruits"])
    base["version"] = cur_v + 1
    json.dump(base, open(set_file, "w"), indent=2)
    print(f"  ✔ wrote {set_file}: recruit_count={base['recruit_count']}, version={base['version']}")

    # manifest merge (best-effort; needs the add-on manifest beside the add-on set)
    if addon_man_file and os.path.exists(addon_man_file) and os.path.exists(man_file):
        base_man = _load(man_file)
        man_ids = {e.get("recruit_id") for e in base_man.get("entries", [])}
        addon_man = _load(addon_man_file)
        new_entries = [e for e in addon_man.get("entries", []) if e.get("recruit_id") not in man_ids]
        base_man["entries"].extend(new_entries)
        json.dump(base_man, open(man_file, "w"), indent=2)
        print(f"  ✔ wrote {man_file}: +{len(new_entries)} manifest entries")
    else:
        print(f"  ⚠️  manifest not merged (missing {addon_man_file} or {man_file}) — merge it manually if needed.")


def main():
    ap = argparse.ArgumentParser(description="Merge a recruit add-on into the base set (DB + repo).")
    ap.add_argument("--addon", required=True, help="path to the add-on set_<id>_add<N>.json")
    ap.add_argument("--commit", action="store_true", help="perform the DB write (default: dry-run)")
    ap.add_argument("--update-repo-file", metavar="SET.json", nargs="?",
                    const=os.path.join(HERE, "set_0001.json"),
                    help="also merge into the tracked set file (default scripts/recruit_sets/set_0001.json)")
    ap.add_argument("--skip-db", action="store_true", help="only touch the repo file, skip the DB entirely")
    args = ap.parse_args()

    addon = _load(args.addon)
    addon["_path"] = os.path.abspath(args.addon)
    if not addon.get("recruits"):
        sys.exit("add-on has no recruits")

    if args.update_repo_file:
        print("── repo file merge ──")
        merge_repo_file(addon, args.update_repo_file)
        print()

    if not args.skip_db:
        print("── database merge ──")
        merge_db(addon, args.commit)


if __name__ == "__main__":
    main()
