#!/usr/bin/env python3
"""Snapshot + restore staging's two shared feeds around a load test (STAGING ONLY).

Every completed user game pushes onto community_highlights "global_feed" (entries,
newest first, capped at 20) and upserts a slot on around_the_league "global_board"
(slots, capped at 8). Load-test games push real staging entries out; cleanup can only
pull the tagged rows. So:

  snapshot   (read-only)  save both docs BEFORE the run
  restore    (dry run by default) after cleanup, rebuild each doc as
             real entries/slots present now  +  pre-run ones that were pushed out,
             tagged rows removed, newest first, capped like the app caps them.

Restore writes only with --yes and GOB_DB_ACCESS=write, and only if the doc has not
changed since it was read (compare-and-set on the whole array), so a real user's
concurrent update is never clobbered — it retries instead.

    ../gob-simplified/.venv/bin/python scripts/loadtest/feeds.py snapshot
    ../gob-simplified/.venv/bin/python scripts/loadtest/feeds.py restore            # diff only
    GOB_DB_ACCESS=write ../gob-simplified/.venv/bin/python scripts/loadtest/feeds.py restore --yes
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone

from bson import json_util

from common import STATE_DIR, connect_staging

FEED = ("community_highlights", "global_feed", "entries", 20)   # FEED_DOC_ID, $slice 20
BOARD = ("around_the_league", "global_board", "slots", 8)       # BOARD_DOC_ID, MAX_SLOTS
USERNAME_RE = re.compile(r"^loadtest_\d+$")
SNAPSHOT_GLOB = "feeds-snapshot-*.json"


def _key(row: dict) -> str:
    return json_util.dumps(row, sort_keys=True)


def _stamp(row: dict, field: str) -> str:
    return str(row.get(field) or "")


def _tagged_user_ids(db) -> set[str]:
    return {str(u["_id"]) for u in db["users"].find({"loadtest": True, "email": {"$regex": r"^loadtest\+\d+@example\.com$"}}, {"_id": 1})}


def snapshot() -> int:
    conn = connect_staging("read")
    try:
        db = conn.database
        data = {
            "taken_at": datetime.now(timezone.utc).isoformat(),
            FEED[0]: db[FEED[0]].find_one({"_id": FEED[1]}),
            BOARD[0]: db[BOARD[0]].find_one({"_id": BOARD[1]}),
        }
    finally:
        conn.close()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"feeds-snapshot-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json_util.dumps(data, indent=2))
    feed_n = len((data[FEED[0]] or {}).get(FEED[2]) or [])
    board_n = len((data[BOARD[0]] or {}).get(BOARD[2]) or [])
    print(f"snapshot saved: {path} (feed entries={feed_n}, board slots={board_n})")
    return 0


def _latest_snapshot() -> dict:
    paths = sorted(STATE_DIR.glob(SNAPSHOT_GLOB))
    if not paths:
        raise SystemExit("no snapshot found — run `feeds.py snapshot` before the load test")
    print(f"using snapshot {paths[0].name} (the EARLIEST one, taken before any run)")
    return json_util.loads(paths[0].read_text())


def rebuild(current: list, snap: list, *, is_tagged, stamp_field: str, cap: int, identity) -> list:
    real_now = [r for r in current if not is_tagged(r)]
    have = {identity(r) for r in real_now}
    restored = [r for r in snap if not is_tagged(r) and identity(r) not in have]
    merged = real_now + restored
    merged.sort(key=lambda r: _stamp(r, stamp_field), reverse=True)
    return merged[:cap]


def restore(yes: bool) -> int:
    snap = _latest_snapshot()
    conn = connect_staging("write" if yes else "read")
    try:
        db = conn.database
        tagged_ids = _tagged_user_ids(db)
        plans = [
            # feed rows: identity = whole row; tagged by loadtest username
            (FEED, "at", lambda r: USERNAME_RE.match(str(r.get("username") or "")) is not None, _key),
            # board slots: one per user; tagged by user_id (or loadtest username)
            (BOARD, "completed_at",
             lambda r: str(r.get("user_id")) in tagged_ids or USERNAME_RE.match(str(r.get("username") or "")) is not None,
             lambda r: str(r.get("user_id"))),
        ]
        rc = 0
        for (coll_name, doc_id, field, cap), stamp_field, is_tagged, identity in plans:
            snap_rows = list(((snap.get(coll_name) or {}).get(field)) or [])
            for attempt in range(3):
                doc = db[coll_name].find_one({"_id": doc_id}) or {}
                current = list(doc.get(field) or [])
                target = rebuild(current, snap_rows, is_tagged=is_tagged, stamp_field=stamp_field,
                                 cap=cap, identity=identity)
                added = [r for r in target if _key(r) not in {_key(c) for c in current}]
                removed = [c for c in current if _key(c) not in {_key(r) for r in target}]
                print(f"\n{coll_name}.{field}: now={len(current)} -> target={len(target)} "
                      f"(+{len(added)} restored, -{len(removed)} tagged/overflow)")
                for r in removed:
                    print(f"   - {r.get('username') or r.get('user_id')} @ {_stamp(r, stamp_field)}")
                for r in added:
                    print(f"   + {r.get('username') or r.get('user_id')} @ {_stamp(r, stamp_field)}")
                if not yes or (not added and not removed):
                    break
                res = db[coll_name].update_one({"_id": doc_id, field: current}, {"$set": {field: target}})
                if res.modified_count == 1:
                    print("   written")
                    break
                print("   doc changed underneath (a real user wrote); retrying")
            else:
                print(f"   GAVE UP on {coll_name} after 3 attempts", file=sys.stderr)
                rc = 1
        if not yes:
            print("\ndry run — nothing written. Re-run with GOB_DB_ACCESS=write ... restore --yes")
        return rc
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("snapshot")
    r = sub.add_parser("restore")
    r.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    return snapshot() if args.cmd == "snapshot" else restore(args.yes)


if __name__ == "__main__":
    raise SystemExit(main())
