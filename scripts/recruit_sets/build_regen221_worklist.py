"""Build the art worklist (Artifact B) for the 221 recruits needing portraits:
150 brand-new + 71 rebuilt "movers" (crossed==1). Reads the 450 export + the two
regen CSVs, runs build_one on each of the 221 KEEPING its recruit_id, and writes a
--set-ready pair that build_recruit_images.py consumes:

    set_0001_regen221.json           (221 recruit records)
    set_0001_regen221.manifest.json  (221 baking entries: genes + build frame)

Frames are recomputed from each recruit's CURRENT physicals (the projection), so
movers get a body matching their new build. Genes are seeded by recruit_id, so a
mover reproduces the same *person*; a brand-new recruit gets fresh genes. Read-only
w.r.t. the DB and the canonical set — writes only the two worklist files.
"""
import csv
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import build_recruit_set as B  # noqa: E402

RD = os.path.join(ROOT, "_documentation_master/projects/recruit_set_0001_regen")


def main():
    export = json.load(open(os.path.join(RD, "set_0001.export.json")))
    by_id = {r["recruit_id"]: r for r in export["recruits"]}

    new_ids = [row["recruit_id"] for row in
               csv.DictReader(open(os.path.join(RD, "set0001_new150_portraits.csv")))]
    mover_ids = [row["recruit_id"] for row in
                 csv.DictReader(open(os.path.join(RD, "set0001_reused_movers.csv")))
                 if str(row.get("crossed", "")).strip() == "1"]
    role = {rid: "new" for rid in new_ids}
    role.update({rid: "mover" for rid in mover_ids})
    wl_ids = new_ids + mover_ids
    print(f"worklist: {len(new_ids)} new + {len(mover_ids)} movers = {len(wl_ids)} (expected 221)")

    missing = [i for i in wl_ids if i not in by_id]
    if missing:
        sys.exit(f"{len(missing)} worklist ids not in the 450 export (first few: {missing[:3]})")
    dupes = [k for k, v in Counter(wl_ids).items() if v > 1]
    if dupes:
        sys.exit(f"duplicate ids across new+movers: {dupes[:3]}")

    recs_in = [by_id[i] for i in wl_ids]

    # The export uses abbreviated year enums (JH/FR/SO/JR) but build_one's growth
    # projection keys on full names (JH/Freshman/Sophomore/Junior) — an abbreviated
    # year silently no-ops the projection, giving a frame from RAW (unprojected)
    # size. Normalize to full names for the projection so every frame is correct,
    # regardless of how the year-enum inconsistency (flagged separately) is resolved.
    YEAR_FULL = {"JH": "JH", "FR": "Freshman", "SO": "Sophomore", "JR": "Junior",
                 "Freshman": "Freshman", "Sophomore": "Sophomore", "Junior": "Junior"}
    normalized = 0
    fixed_recs = []
    for rc in recs_in:
        full = YEAR_FULL.get(rc.get("year"))
        if full and full != rc.get("year"):
            rc = {**rc, "year": full}
            normalized += 1
        fixed_recs.append(rc)
    recs_in = fixed_recs
    print(f"normalized {normalized} abbreviated years -> full names for correct projection")

    rw, eth = B.bounded_race_weights(recs_in, seed="set_0001_regen221", cap_pp=8)

    records, manifests = [], []
    for rc in recs_in:
        rec, man = B.build_one(rc, random_weights=rw)   # build_one now keeps existing recruit_id
        assert rec["recruit_id"] == rc["recruit_id"], "recruit_id changed — must never happen"
        records.append(rec)
        manifests.append(man)

    out_set = {"set_id": "set_0001", "version": 2, "recruit_count": len(records),
               "add_on_for": "set_0001", "subset": "regen221 (150 new + 71 movers)",
               "recruits": records}
    out_man = {"set_id": "set_0001", "entries": manifests}
    json.dump(out_set, open(os.path.join(HERE, "set_0001_regen221.json"), "w"), indent=2)
    json.dump(out_man, open(os.path.join(HERE, "set_0001_regen221.manifest.json"), "w"), indent=2)

    # --- report ---
    frames = Counter(m["build"]["frame"] for m in manifests)
    fr_new = Counter(m["build"]["frame"] for m, r in zip(manifests, records) if role[r["recruit_id"]] == "new")
    fr_mov = Counter(m["build"]["frame"] for m, r in zip(manifests, records) if role[r["recruit_id"]] == "mover")
    order = ["Slight", "Lean", "Normal", "Broad", "Doughy"]
    print(f"\nwrote set_0001_regen221.json + .manifest.json ({len(records)} entries)")
    print("frame (all):   " + " | ".join(f"{k} {frames.get(k,0)}" for k in order))
    print("frame (new):   " + " | ".join(f"{k} {fr_new.get(k,0)}" for k in order))
    print("frame (movers):" + " | ".join(f"{k} {fr_mov.get(k,0)}" for k in order))
    print("race target rolled: " + " | ".join(f"{k} {eth[k]:.0f}%" for k in ("black", "white", "other")))
    print("years:         " + " | ".join(f"{k} {Counter(r['year'] for r in records).get(k,0)}"
                                         for k in ("JH", "Freshman", "Sophomore", "Junior")))


if __name__ == "__main__":
    main()
