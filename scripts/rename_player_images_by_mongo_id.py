# scripts/rename_player_images_by_mongo_id.py
import os
import re
import sys
from pathlib import Path

from pymongo import MongoClient
from dotenv import load_dotenv

# ---------- config ----------
IMAGES_DIR = Path("FrontEnd/static/images/players")   # folder with your images
DB_NAME = "gob"
COLL_NAME = "players"
# ----------------------------

def tokenize(name: str):
    base = Path(name).stem
    # split on anything non-letter, lowercase
    return [t for t in re.split(r"[^A-Za-z]+", base.lower()) if t]

def main():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
    if not mongo_uri:
        print("ERROR: Missing MONGO_URI in .env")
        sys.exit(1)

    apply = "--apply" in sys.argv

    if not IMAGES_DIR.exists():
        print(f"ERROR: Images directory not found: {IMAGES_DIR.resolve()}")
        sys.exit(1)

    client = MongoClient(mongo_uri)
    coll = client[DB_NAME][COLL_NAME]

    # pull only what we need
    players = list(coll.find({}, {"_id": 1, "first_name": 1, "last_name": 1}))
    # index by last name
    by_last = {}
    for p in players:
        ln = (p.get("last_name") or "").lower()
        by_last.setdefault(ln, []).append(p)

    total, matched, renamed, ambiguous, missing = 0, 0, 0, 0, 0

    print(f"\nScanning: {IMAGES_DIR.resolve()}\n(DRY RUN)\n" if not apply else
          f"\nScanning: {IMAGES_DIR.resolve()}\n(APPLY MODE)\n")

    for f in sorted(IMAGES_DIR.iterdir()):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue

        total += 1
        tokens = tokenize(f.name)
        # find any last-name token present in filename
        last_hits = [t for t in tokens if t in by_last]

        if not last_hits:
            print(f"  [skip] no last-name match -> {f.name}")
            missing += 1
            continue

        # If multiple last-name tokens appear, pick the first; very rare
        last = last_hits[0]
        candidates = by_last[last]

        if len(candidates) == 1:
            target = candidates[0]
        else:
            # disambiguate by first name if present
            first_hits = { (p.get('first_name') or '').lower(): p for p in candidates }
            found = None
            for t in tokens:
                if t in first_hits:
                    found = first_hits[t]
                    break
            if not found:
                print(f"  [ambiguous] {f.name} -> candidates: " +
                      ", ".join(f"{p['first_name']} {p['last_name']}" for p in candidates))
                ambiguous += 1
                continue
            target = found

        matched += 1
        new_name = f"{target['_id']}{ext}"
        new_path = f.with_name(new_name)

        if f.name == new_name:
            print(f"  [ok] already named -> {f.name}")
            continue

        if new_path.exists():
            # extremely unlikely, but guard against overwriting
            print(f"  [warn] target exists, skipping -> {new_name}")
            ambiguous += 1
            continue

        action = "RENAME" if apply else "DRYRUN"
        print(f"  [{action}] {f.name}  -->  {new_name}")
        if apply:
            f.rename(new_path)
            renamed += 1

    print("\nSummary:")
    print(f"  files seen:   {total}")
    print(f"  matched:      {matched}")
    print(f"  renamed:      {renamed}")
    print(f"  ambiguous:    {ambiguous}  (needs first-name in filename or manual map)")
    print(f"  no last name: {missing}")

if __name__ == "__main__":
    main()
