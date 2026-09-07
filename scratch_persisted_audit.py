"""Audit the PERSISTED skeleton shapes.

My unreachability proof covered BackEnd/playcall_skeletons/ only. That is the
FALLBACK. The primary source is MongoDB: `play_doc.get("skeletons", {})`
(phase_resolution.py:10174) plus the fcp_skeletons / hct_skeletons collections,
all authored through a builder UI. This audits the on-disk exports of those
documents, which is the closest available proxy for production data.

Reports, per file, the position-key vocabulary of every offense pos_action, and
names any entry that would reach the raise.
"""
import json
import pathlib
from collections import Counter

OFFENSE = {"PG", "SG", "SF", "PF", "C"}
KEYS = ("coords", "location", "spot")

FILES = [
    "play_skeletons_export.json",
    "play_skeletons_export_new.json",
    "_documentation_master/reference/Sample_Play_Skeletons.json",
    "docs/To Do/skeletons_for_plays/4_1_motion_skeleton.json",
    "docs/To Do/skeletons_for_plays/3_2_motion_skeleton.json",
    "docs/To Do/skeletons_for_plays/current_plays_structure.json",
]

grand = Counter()
offenders = []


def walk(obj, trail, tally):
    if isinstance(obj, dict):
        pa = obj.get("pos_actions")
        if isinstance(pa, dict):
            for pos, action in pa.items():
                if not isinstance(action, dict):
                    continue
                scope = "offense" if pos in OFFENSE else "other"
                tally[(scope, "total")] += 1
                which = [k for k in KEYS if k in action]
                tally[(scope, "+".join(which) if which else "NONE")] += 1
                if not which and scope == "offense":
                    offenders.append((trail, pos, sorted(action.keys())))
        for k, v in obj.items():
            walk(v, f"{trail}.{k}", tally)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, f"{trail}[{i}]", tally)


for rel in FILES:
    p = pathlib.Path(rel)
    if not p.exists():
        print(f"  (missing) {rel}")
        continue
    try:
        doc = json.loads(p.read_text())
    except Exception as e:
        print(f"  (unreadable) {rel}: {e}")
        continue
    tally = Counter()
    walk(doc, p.stem, tally)
    grand.update(tally)
    tot = tally[("offense", "total")]
    print(f"\n{rel}")
    print(f"  offense pos_actions: {tot}")
    for (scope, key), n in sorted(tally.items(), key=lambda kv: -kv[1]):
        if scope != "offense" or key == "total":
            continue
        print(f"    {key:24s} {n:6d}  {100.0*n/max(tot,1):5.1f}%")

print("\n" + "=" * 70)
tot = grand[("offense", "total")]
print(f"ALL PERSISTED EXPORTS — {tot} offense pos_actions")
for (scope, key), n in sorted(grand.items(), key=lambda kv: -kv[1]):
    if scope != "offense" or key == "total":
        continue
    print(f"  {key:24s} {n:6d}  {100.0*n/max(tot,1):5.1f}%")

print("\n=== WOULD REACH THE RAISE (no coords/location/spot) ===")
if not offenders:
    print("  none")
else:
    for trail, pos, keys in offenders[:30]:
        print(f"  {trail} [{pos}] keys={keys}")
    print(f"  ({len(offenders)} total)")
