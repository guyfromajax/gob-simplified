#!/usr/bin/env python3
"""
edit_pool_attributes.py — targeted attribute / position-intent edits for the universal pool.

Hand-edit specific gob-staging.players docs and keep everything derived-from-attributes in sync.
Per edited player it:
  • sets each named attribute AND its `anchor_<ATTR>` mirror to the new value — the mirror is
    load-bearing: in-season training / the offseason attractor reset `live = anchor` at week 1, so
    editing the live value alone is silently wiped at the next tick. Both must move together.
  • recomputes `position_ratings` from the new attributes + the doc's height (never hand-written —
    it is derived via the one canonical `compute_position_ratings`).
  • optionally sets `position_intent` (the training/display position). NOT auto-derived from RT:
    the real assignment is a whole-pool capacity optimization, and argmax≠intent is normal
    (grow-into-frame). Only changes when you name a new intent for that player.

Fields written: attributes, position_ratings, and position_intent (only when specified). Nothing
else — entry_tier / potential_factor / height / weight / archetype are left untouched.

SCOPE: gob-staging.players ONLY. Double DB-name assertion; backs up before writing; dry-run default.

Usage:
    # 1. Fill in EDITS below (or pass --edits path/to/edits.json with the same shape).
    .venv/bin/python scripts/edit_pool_attributes.py            # dry-run + manifest
    .venv/bin/python scripts/edit_pool_attributes.py --commit   # back up then write

EDITS shape — keyed by player_id (UUID string); every field optional except at least one of
attributes / position_intent:
    {
      "eaae738e-6170-4191-b6bf-f6cf4a291b30": {"attributes": {"SC": 62, "SH": 55}, "position_intent": "C"},
      "abc-...": {"attributes": {"ID": 70}},          # attrs only
      "def-...": {"position_intent": "SF"}            # intent only
    }
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pymongo.operations import UpdateOne

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.utils.player_generation import POSITIONS  # noqa: E402
from BackEnd.utils.position_ratings import compute_position_ratings  # noqa: E402
from BackEnd.script_db import STAGING_DB, connect_script_database  # noqa: E402

DB_NAME = STAGING_DB
COLLECTION = "players"
ATTR_MIN, ATTR_MAX = 0, 100  # raw attribute scale (display divides by 10)

# ── EDIT ME (or pass --edits <json> with the same shape) ──────────────────────
EDITS: dict[str, dict] = {
    "8487cb3b-887b-472a-90d9-f46caa572d46": {"attributes": {"BH": 68, "IQ": 61, "PS": 42}, "position_intent": "PG"},
    "8487cb3b-887b-472a-90d9-f46caa572d46": {"attributes": {"BH": 25, "PS": 24}},
}


def _validate(edits: dict, docs_by_id: dict) -> list[str]:
    """Fail loudly on anything malformed BEFORE any write is prepared."""
    errs: list[str] = []
    if not edits:
        errs.append("EDITS is empty — nothing to do (fill in EDITS or pass --edits).")
    for pid, spec in edits.items():
        doc = docs_by_id.get(pid)
        if doc is None:
            errs.append(f"{pid}: no such player in {DB_NAME}.{COLLECTION}")
            continue
        attrs = doc.get("attributes") or {}
        live_keys = {k for k in attrs if not k.startswith("anchor_")}
        overrides = spec.get("attributes") or {}
        intent = spec.get("position_intent")
        if not overrides and intent is None:
            errs.append(f"{pid}: entry has neither 'attributes' nor 'position_intent'")
        for a, val in overrides.items():
            if a not in live_keys:
                errs.append(f"{pid}: unknown attribute {a!r} (not on this player's doc)")
            elif not isinstance(val, (int, float)) or not (ATTR_MIN <= val <= ATTR_MAX):
                errs.append(f"{pid}: attribute {a} value {val!r} out of range [{ATTR_MIN},{ATTR_MAX}]")
        if intent is not None and intent not in POSITIONS:
            errs.append(f"{pid}: position_intent {intent!r} not one of {POSITIONS}")
    return errs


def _apply(doc: dict, spec: dict) -> dict:
    """Return the $set doc for one player and stash before/after on `doc` for the report."""
    attrs = dict(doc.get("attributes") or {})
    overrides = spec.get("attributes") or {}
    changes = []
    for a, val in overrides.items():
        old = attrs.get(a)
        attrs[a] = val
        anchor = f"anchor_{a}"
        if anchor in attrs:               # mirror only if the anchor field exists
            attrs[anchor] = val
        changes.append((a, old, val))
    new_ratings = compute_position_ratings({"attributes": attrs, "height": doc.get("height")})
    set_doc = {"attributes": attrs, "position_ratings": new_ratings}
    intent = spec.get("position_intent")
    if intent is not None:
        set_doc["position_intent"] = intent
    # stash for the manifest
    doc["_changes"] = changes
    doc["_old_ratings"] = doc.get("position_ratings")
    doc["_new_ratings"] = new_ratings
    doc["_old_intent"] = doc.get("position_intent")
    doc["_new_intent"] = intent
    assert set(set_doc) <= {"attributes", "position_ratings", "position_intent"}, \
        "RED FLAG: write set exceeded attributes/position_ratings/position_intent"
    return set_doc


def _report(edits: dict, docs_by_id: dict, ops_by_id: dict, all_docs: list) -> None:
    print("=" * 78)
    print("POOL ATTRIBUTE / INTENT EDIT — DRY-RUN MANIFEST")
    print("=" * 78)
    print(f"TARGET   database={DB_NAME!r}  collection={COLLECTION!r}")
    print(f"WRITES   attributes (+ anchor_ mirrors), position_ratings, position_intent (when set)")
    print(f"PLAYERS  {len(edits)} edited\n")

    intent_changed = False
    for pid in edits:
        d = docs_by_id[pid]
        nm = f"{d.get('first_name','?')} {d.get('last_name','?')}"
        print(f"● {nm}  [{pid}]  {d.get('height')}in {d.get('year')}")
        for a, old, new in d.get("_changes", []):
            print(f"    {a}: {old} → {new}   (anchor_{a} mirrored)")
        if d["_new_intent"] is not None and d["_new_intent"] != d["_old_intent"]:
            intent_changed = True
            print(f"    position_intent: {d['_old_intent']} → {d['_new_intent']}")
            if (d.get("archetype") or "").strip():
                print(f"      note: archetype {d.get('archetype')!r} left as-is — review if it implies a position")
        elif d["_new_intent"] is not None:
            print(f"    position_intent: {d['_old_intent']} (unchanged — same value supplied)")
        print(f"    position_ratings: {d['_old_ratings']} → {d['_new_ratings']}")

    if intent_changed:
        # Pool-wide intent supply shift (only meaningful when intents move).
        before = Counter(str(p.get("position_intent")) for p in all_docs)
        after = Counter(before)
        for pid in edits:
            ni = docs_by_id[pid]["_new_intent"]
            if ni is not None and ni != docs_by_id[pid]["_old_intent"]:
                after[str(docs_by_id[pid]["_old_intent"])] -= 1
                after[ni] += 1
        n = len(all_docs)
        print("\nPOOL INTENT SUPPLY  before → after (manual reassignments skew the ~20% balance)")
        for pos in POSITIONS:
            print(f"  {pos:3}  {before.get(pos,0):4d} ({100*before.get(pos,0)/n:4.1f}%) → "
                  f"{after.get(pos,0):4d} ({100*after.get(pos,0)/n:4.1f}%)")
    print("=" * 78)


def _backup(db) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    name = f"players_backup_attr_edit_{ts}"
    src = db[COLLECTION].count_documents({})
    db[COLLECTION].aggregate([{"$match": {}}, {"$out": name}])
    dst = db[name].count_documents({})
    if dst != src:
        raise SystemExit(f"backup count mismatch: src={src} dst={dst}")
    print(f"BACKUP   {DB_NAME}.{COLLECTION} ({src}) → {DB_NAME}.{name}")
    return name


def main() -> int:
    ap = argparse.ArgumentParser(description="Targeted attribute/intent edits for gob-staging.players")
    ap.add_argument("--db", choices=[DB_NAME], default=DB_NAME)
    ap.add_argument("--edits", help="path to a JSON file with the EDITS shape (overrides the inline EDITS)")
    ap.add_argument("--commit", action="store_true", help="back up then persist (default dry-run)")
    args = ap.parse_args()

    edits = EDITS
    if args.edits:
        edits = json.loads(Path(args.edits).read_text(encoding="utf-8"))

    connection = connect_script_database(
        target=args.db,
        access="write" if args.commit else "read",
        pristine_env=dict(os.environ),
        repo_root=ROOT,
    )
    db = connection.database
    if db.name != DB_NAME:                      # HARD GUARD #1
        raise SystemExit(f"Refusing: target DB is {db.name!r}, expected {DB_NAME!r}. No writes.")

    all_docs = list(db[COLLECTION].find({}))
    docs_by_id = {str(p.get("player_id")): p for p in all_docs}

    errs = _validate(edits, docs_by_id)
    if errs:
        print("VALIDATION FAILED — no writes performed:")
        for e in errs:
            print(f"  ✗ {e}")
        return 1

    ops_by_id = {pid: _apply(docs_by_id[pid], spec) for pid, spec in edits.items()}
    _report(edits, docs_by_id, ops_by_id, all_docs)

    print(f"\nMODE: {'COMMIT' if args.commit else 'DRY-RUN (no writes)'}")
    if args.commit:
        assert db.name == DB_NAME, "guard bypassed"   # HARD GUARD #2
        _backup(db)
        ops = [UpdateOne({"player_id": pid}, {"$set": set_doc}) for pid, set_doc in ops_by_id.items()]
        db[COLLECTION].bulk_write(ops, ordered=False)
        print(f"  {db.name}.{COLLECTION}: updated {len(ops)} docs")
    else:
        print("  (no writes — re-run with --commit to back up and persist)")

    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
