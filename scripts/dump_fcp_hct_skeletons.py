#!/usr/bin/env python3
"""Dump FCP and HCT skeleton steps from MongoDB for debugging inbound/step order."""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from BackEnd.db import fcp_skeletons_collection, hct_skeletons_collection

def summarize_step(step, i):
    pos_actions = step.get("pos_actions") or {}
    events = step.get("events") or []
    actions = {pos: (info.get("action"), info.get("spot", "")) for pos, info in pos_actions.items()}
    ev_types = [e.get("type") for e in events if e]
    return {"step": i, "timestamp": step.get("timestamp"), "actions": actions, "events": ev_types}

def dump_collection(name, coll):
    print(f"\n=== {name} ===")
    doc = coll.find_one({})
    if not doc:
        print("  (no document)")
        return
    variants = doc.get("variants", {})
    for vname, vdata in variants.items():
        if not vdata or "versions" not in vdata:
            continue
        versions = vdata["versions"]
        if not versions:
            continue
        # first version only
        steps = versions[0].get("steps", [])
        print(f"  Variant: {vname}, steps: {len(steps)}")
        for i, step in enumerate(steps):
            s = summarize_step(step, i)
            print(f"    Step {i}: ts={s['timestamp']} actions={s['actions']} events={s['events']}")
        break

if __name__ == "__main__":
    dump_collection("FCP", fcp_skeletons_collection)
    dump_collection("HCT", hct_skeletons_collection)
