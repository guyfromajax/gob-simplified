#!/usr/bin/env python3
"""
Bake builder_set_0001 — Team Builder portrait extension (§6.5a).

Teen age language only. Restored original reference bodies. 150 kits per
scripts/recruit_sets/builder_set_0001.allocation.json.

    # plan + collision check (no API):
    python3 scripts/recruit_sets/bake_builder_set_0001.py --plan-only

    # bake up to 50 finished kits, then stop for QC sheet:
    python3 scripts/recruit_sets/bake_builder_set_0001.py --until 50

    # finish remaining:
    python3 scripts/recruit_sets/bake_builder_set_0001.py --until 150

    # write published + full manifests from finished kits:
    python3 scripts/recruit_sets/bake_builder_set_0001.py --write-manifests

    # unlabelled contact sheet of whatever exists:
    python3 scripts/recruit_sets/bake_builder_set_0001.py --contact-sheet
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
import uuid
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, HERE)
sys.path.insert(0, SCRIPTS)

import generate_player_portraits as gen  # noqa: E402
import apply_team_uniforms as uni        # noqa: E402
import finish_portraits as fin           # noqa: E402

ALLOC_PATH = os.path.join(HERE, "builder_set_0001.allocation.json")
RECRUIT_SET_PATH = os.path.join(HERE, "set_0001.json")  # legacy filename = recruit_set_0001
PILOT_META = "tmp/portrait-pilot/builder_set_0001_pilot/pilot_meta.json"
PILOT_KIT = "tmp/portrait-pilot/builder_set_0001_pilot/kit"
OUT_DIR = "tmp/portrait-pilot/builder_set_0001"
KIT_DIR = os.path.join(OUT_DIR, "kit")
STAGING_KIT = "assets_staging/portrait-kits/builder_set_0001"
R2_PREFIX = "portrait-kits/builder_set_0001/"
PLAN_PATH = os.path.join(OUT_DIR, "bake_plan.json")
RECRUIT_KIT_LEGACY = "/Users/jamesdavies/gob-portraits/assets_staging/recruits/kit"  # legacy R2: recruits/kit/


def load_recruit_set_ids():
    return {r["recruit_id"] for r in json.load(open(RECRUIT_SET_PATH))["recruits"]}


def existing_kit_ids():
    """Any UUID already used as a kit filename on disk (collision = overwrite)."""
    ids = set()
    for d in (STAGING_KIT, RECRUIT_KIT_LEGACY, PILOT_KIT, KIT_DIR):
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if fn.endswith(".png") and not fn.endswith(".mask.png") and ".raw." not in fn:
                ids.add(fn[:-4])
            elif fn.endswith(".json"):
                ids.add(fn[:-5])
    return ids


def stable_uuid(*parts):
    h = hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest()
    return str(uuid.UUID(h))


def load_league_genes():
    by = defaultdict(list)
    for p in csv.DictReader(open(os.path.join(ROOT, "scripts/players_archetypes.csv"))):
        by[(p["frame"], p["definition"], p["skin"])].append(p)
    return by


def pick_gene(pool_map, frame, definition, skin, salt):
    pool = pool_map.get((frame, definition, skin)) or []
    if not pool:
        pool = [p for (fr, de, _), ps in pool_map.items()
                if fr == frame and de == definition for p in ps]
    if not pool:
        pool = [p for (fr, _, _), ps in pool_map.items() if fr == frame for p in ps]
    i = int(hashlib.md5(salt.encode()).hexdigest(), 16) % len(pool)
    return pool[i]


def race_of_skin(skin):
    if skin.startswith("black"):
        return "black"
    if skin.startswith("white"):
        return "white"
    return "other"


def build_plan():
    """Expand allocation into 150 slots; reuse teen pilots; mark developed for rebake."""
    alloc = json.load(open(ALLOC_PATH))
    set0001 = load_recruit_set_ids()
    genes = load_league_genes()

    pilot_by_cell = defaultdict(list)
    if os.path.exists(PILOT_META):
        for s in json.load(open(PILOT_META))["slots"]:
            cell = (s["frame"], s["definition"], s["skin"])
            pilot_by_cell[cell].append(s)

    reserved = set(set0001)
    # Reserve all pilot ids so new mints never collide with them (rebakes keep id)
    for slots in pilot_by_cell.values():
        for s in slots:
            reserved.add(s["image_id"])

    plan = []
    for t in alloc["targets"]:
        frame, definition, skin = t["frame"], t["definition"], t["skin"]
        cell = (frame, definition, skin)
        need = t["extension_count"]
        pilots = list(pilot_by_cell.get(cell, []))
        # Prefer assigning teen pilots first, then developed (to rebake), then new
        teens = [p for p in pilots if p["age_mode"] == "teen"]
        devs = [p for p in pilots if p["age_mode"] == "developed"]
        assigned = 0

        for p in teens:
            if assigned >= need:
                break
            plan.append(_slot_from_pilot(p, action="keep_teen", genes=genes))
            assigned += 1

        for p in devs:
            if assigned >= need:
                break
            # Same id, force teen rebake — developed art superseded
            plan.append(_slot_from_pilot(p, action="rebake_teen", genes=genes))
            assigned += 1

        n = 0
        while assigned < need:
            n += 1
            rid = stable_uuid("builder_set_0001", frame, definition, skin, n)
            # If collision with reserved (pilot used different salt), bump
            bump = 0
            while rid in reserved:
                bump += 1
                rid = stable_uuid("builder_set_0001", frame, definition, skin, n, f"bump{bump}")
            reserved.add(rid)
            src = pick_gene(genes, frame, definition, skin, rid)
            plan.append({
                "image_id": rid,
                "frame": frame,
                "definition": definition,
                "skin": skin,
                "race": race_of_skin(skin),
                "action": "bake_new",
                "source_player": src["name"],
                "source_hw": f"{src['height_in']}in/{src['weight_lb']}lb",
                "row": {
                    "skin_prompt": src["skin_prompt"],
                    "face_prompt": src["face_prompt"],
                    "hair": src["hair"],
                    "expression": src["expression"],
                    "accessories": src.get("accessories", ""),
                    "definition": definition,
                },
            })
            assigned += 1

    assert len(plan) == 150, len(plan)
    ids = [s["image_id"] for s in plan]
    assert len(ids) == len(set(ids)), "duplicate ids inside plan"

    collisions = set(ids) & set0001
    if collisions:
        raise SystemExit(f"FATAL: {len(collisions)} plan ids collide with set_0001")

    # Disk collision against set_0001 kits that aren't in the JSON (paranoia)
    disk = existing_kit_ids()
    # Pilot kits for our own ids are fine; foreign ids that match plan would overwrite
    foreign = (disk - set(ids)) & set0001
    bad = set(ids) & (disk & set0001)
    if bad:
        raise SystemExit(f"FATAL: plan ids collide with set_0001 kits on disk: {bad}")

    return plan


def _slot_from_pilot(p, action, genes):
    # Refresh genes from league if row missing; keep pilot genes when present
    row = p.get("row")
    if not row:
        src = pick_gene(genes, p["frame"], p["definition"], p["skin"], p["image_id"])
        row = {
            "skin_prompt": src["skin_prompt"],
            "face_prompt": src["face_prompt"],
            "hair": src["hair"],
            "expression": src["expression"],
            "accessories": src.get("accessories", ""),
            "definition": p["definition"],
        }
        source_player, source_hw = src["name"], f"{src['height_in']}in/{src['weight_lb']}lb"
    else:
        source_player, source_hw = p.get("source_player", ""), p.get("source_hw", "")
    return {
        "image_id": p["image_id"],
        "frame": p["frame"],
        "definition": p["definition"],
        "skin": p["skin"],
        "race": race_of_skin(p["skin"]),
        "action": action,
        "source_player": source_player,
        "source_hw": source_hw,
        "row": row,
    }


def teen_prompt(row):
    """Always teen — matches set_0001 / league register."""
    return gen.build_prompt(row)


def kit_paths(rid, root=KIT_DIR):
    return {
        "png": os.path.join(root, f"{rid}.png"),
        "mask": os.path.join(root, f"{rid}.mask.png"),
        "json": os.path.join(root, f"{rid}.json"),
    }


def kit_complete(rid, root=KIT_DIR):
    p = kit_paths(rid, root)
    return all(os.path.exists(p[k]) for k in ("png", "mask", "json"))


def ensure_sidecars_from_png(rid, frame, root=KIT_DIR):
    """Rebuild mask/json from an existing RGBA kit png (kept teen pilots).

    Never writes a blank mask. Two bugs produced the eight identical all-black
    builder_set_0001 masks:

    1. ``_tank`` was called on RGBA. Channel min/max then included alpha=255,
       so shaded white fabric failed the neutrality gate and tank came back empty.
    2. When tank was empty, bbox fell back to the person silhouette — but the
       empty tank array was still written to ``.mask.png``.
    """
    from PIL import Image
    import numpy as np
    from scipy import ndimage
    from mask_validation import assert_tank_mask_usable

    p = kit_paths(rid, root)
    src = Image.open(p["png"]).convert("RGBA")
    a = np.asarray(src).astype(np.float32)
    alpha = a[..., 3]
    person = alpha > 128
    # RGB only — alpha must not participate in bright/neutral/warm stats.
    tank = uni._tank(a[..., :3], person, np, ndimage)
    assert_tank_mask_usable(tank, source=p["png"])
    ys, xs = np.where(tank)
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    center = int((xs.min() + xs.max()) / 2)
    Image.fromarray((tank * 255).astype("uint8"), "L").save(p["mask"])
    json.dump({"bbox": bbox, "center_x": center, "frame": frame,
               "canvas": [fin.CANVAS_W, fin.CANVAS_H]},
              open(p["json"], "w"))


def import_teen_pilot(slot):
    """Copy kept teen pilot png into KIT_DIR and ensure sidecars."""
    rid = slot["image_id"]
    src = os.path.join(PILOT_KIT, f"{rid}.png")
    dst = kit_paths(rid)["png"]
    os.makedirs(KIT_DIR, exist_ok=True)
    if not os.path.exists(src):
        raise FileNotFoundError(src)
    if not os.path.exists(dst):
        import shutil
        shutil.copy2(src, dst)
    if not kit_complete(rid):
        ensure_sidecars_from_png(rid, slot["frame"])


def bake_one(slot, client, ref_cache, force=False):
    from PIL import Image
    import numpy as np
    from scipy import ndimage
    from mask_validation import assert_tank_mask_usable

    rid = slot["image_id"]
    paths = kit_paths(rid)
    if kit_complete(rid) and not force and slot["action"] != "rebake_teen":
        return "skip"

    def ref_body(frame):
        key = frame.lower()
        if key not in ref_cache:
            path = os.path.join(ROOT, gen.REF_DIR, f"{key}.png")
            if not os.path.exists(path):
                raise FileNotFoundError(path)
            ref_cache[key] = Image.open(path)
        return ref_cache[key]

    prompt = teen_prompt(slot["row"])
    last_err = None
    for attempt in range(6):
        try:
            resp = client.models.generate_content(
                model=gen.MODEL, contents=[prompt, ref_body(slot["frame"])])
            raw = None
            for part in resp.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    raw = part.inline_data.data
                    break
            if not raw:
                last_err = "no image"
                time.sleep(min(60, 2 ** attempt))
                continue
            raw_tmp = os.path.join(KIT_DIR, f"{rid}.raw.png")
            with open(raw_tmp, "wb") as fh:
                fh.write(raw)
            src = Image.open(raw_tmp).convert("RGB")
            a = np.asarray(src).astype(np.float32)
            alpha = uni.person_alpha(src, np, ndimage)
            person = alpha > 128
            tank = uni._tank(a, person, np, ndimage)
            try:
                assert_tank_mask_usable(tank, source=rid)
            except RuntimeError as exc:
                last_err = str(exc)
                os.remove(raw_tmp)
                time.sleep(min(60, 2 ** attempt))
                continue
            ys, xs = np.where(tank)
            bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
            center = int((xs.min() + xs.max()) / 2)
            rgba = np.dstack([a, alpha]).astype("uint8")
            Image.fromarray(rgba, "RGBA").save(paths["png"])
            Image.fromarray((tank * 255).astype("uint8"), "L").save(paths["mask"])
            json.dump({"bbox": bbox, "center_x": center, "frame": slot["frame"],
                       "canvas": [fin.CANVAS_W, fin.CANVAS_H]},
                      open(paths["json"], "w"))
            os.remove(raw_tmp)
            return "ok"
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:160]}"
            time.sleep(min(60, 2 ** attempt))
    raise RuntimeError(last_err or "unknown")


def count_complete(plan):
    return sum(1 for s in plan if kit_complete(s["image_id"]))


def stage_to_assets(plan):
    """Copy finished kits into assets_staging/portrait-kits/builder_set_0001/ AFTER collision check.
    R2 keys: portrait-kits/builder_set_0001/<uuid>.png (+ .mask.png, .json)."""
    import shutil
    from PIL import Image
    import numpy as np
    from mask_validation import assert_tank_mask_usable

    set0001 = load_recruit_set_ids()
    os.makedirs(STAGING_KIT, exist_ok=True)
    n = 0
    for s in plan:
        rid = s["image_id"]
        if rid in set0001:
            raise RuntimeError(f"collision with recruit_set_0001 id {rid}")
        src = kit_paths(rid)
        if not kit_complete(rid):
            continue
        mask_arr = np.asarray(Image.open(src["mask"]).convert("L"))
        assert_tank_mask_usable(mask_arr, source=src["mask"])
        for key in ("png", "mask", "json"):
            shutil.copy2(src[key], os.path.join(STAGING_KIT, os.path.basename(src[key])))
        n += 1
    return n


def rebuild_bad_masks(plan, image_ids=None):
    """Regenerate masks from existing kit PNGs for the given ids (or all incomplete/bad)."""
    from PIL import Image
    import numpy as np
    from mask_validation import tank_pixel_count, MIN_TANK_PIXELS

    wanted = set(image_ids) if image_ids else None
    rebuilt = failed = skipped = 0
    for s in plan:
        rid = s["image_id"]
        if wanted is not None and rid not in wanted:
            continue
        png = kit_paths(rid, STAGING_KIT)["png"]
        root = STAGING_KIT if os.path.exists(png) else KIT_DIR
        paths = kit_paths(rid, root)
        if not os.path.exists(paths["png"]):
            print(f"[skip] {rid}: no kit png")
            skipped += 1
            continue
        # Always rebuild when explicitly listed; otherwise only if mask is bad/missing.
        if wanted is None and os.path.exists(paths["mask"]):
            count = tank_pixel_count(
                np.asarray(Image.open(paths["mask"]).convert("L"))
            )
            if count >= MIN_TANK_PIXELS:
                skipped += 1
                continue
        try:
            ensure_sidecars_from_png(rid, s["frame"], root=root)
            # Keep pilot kit tree in sync when staging was the source.
            kit_png = kit_paths(rid, KIT_DIR)["png"]
            if root == STAGING_KIT and os.path.exists(kit_png):
                ensure_sidecars_from_png(rid, s["frame"], root=KIT_DIR)
            count = tank_pixel_count(
                np.asarray(Image.open(paths["mask"]).convert("L"))
            )
            print(f"[rebuilt] {rid}  tank_px={count}  ({s['frame']}-{s['definition']}/{s['skin']})")
            rebuilt += 1
        except Exception as exc:
            print(f"[fail] {rid}: {exc}")
            failed += 1
    print(f"[rebuild-masks] rebuilt={rebuilt} failed={failed} skipped={skipped}")
    return rebuilt, failed


def validate_masks(plan, roots=None):
    """Fail loudly if any planned kit mask is below the tank-pixel floor."""
    from PIL import Image
    import numpy as np
    from mask_validation import tank_pixel_count, MIN_TANK_PIXELS

    roots = roots or (STAGING_KIT, KIT_DIR)
    bad = []
    checked = 0
    for s in plan:
        rid = s["image_id"]
        for root in roots:
            mask = kit_paths(rid, root)["mask"]
            if not os.path.exists(mask):
                continue
            checked += 1
            count = tank_pixel_count(np.asarray(Image.open(mask).convert("L")))
            if count < MIN_TANK_PIXELS:
                bad.append((rid, root, count, f"{s['frame']}-{s['definition']}/{s['skin']}"))
            break
    print(f"[validate-masks] checked={checked} bad={len(bad)} floor={MIN_TANK_PIXELS}")
    for rid, root, count, cell in bad:
        print(f"  BAD {rid}  tank_px={count}  {cell}  ({root})")
    if bad:
        raise SystemExit(1)
    return checked


def write_manifests(plan):
    """Full baking manifest + filtered published subset."""
    entries_full = []
    entries_pub = []
    for s in plan:
        if not kit_complete(s["image_id"]):
            continue
        entries_full.append({
            "image_id": s["image_id"],
            "build": {"frame": s["frame"], "definition": s["definition"]},
            "portrait": {
                "race": s["race"],
                "skin": s["skin"],
                "skin_prompt": s["row"]["skin_prompt"],
                "hair": s["row"]["hair"],
                "face_prompt": s["row"]["face_prompt"],
                "expression": s["row"]["expression"],
                "accessories": s["row"].get("accessories", ""),
            },
            "source_player": s.get("source_player"),
            "age_language": "teen",
        })
        entries_pub.append({
            "image_id": s["image_id"],
            "build": {"frame": s["frame"], "definition": s["definition"]},
            "portrait": {"skin": s["skin"]},
        })
    full = {
        "set_id": "builder_set_0001",
        "version": 1,
        "purpose": "Team Builder portrait extension (builder_set_0001) — NOT in recruit assignment pool",
        "age_language": "teen",
        "count": len(entries_full),
        "entries": entries_full,
    }
    pub = {
        "set_id": "builder_set_0001",
        "version": 1,
        "purpose": "Game-facing filtered subset for Team Builder picker/assignment",
        "pool": "recruit_set_0001 ∪ builder_set_0001 (TB only); recruits use recruit_set_0001 alone",
        "published_fields": ["build.frame", "build.definition", "portrait.skin"],
        "count": len(entries_pub),
        "entries": entries_pub,
    }
    full_path = os.path.join(HERE, "builder_set_0001.manifest.json")
    pub_path = os.path.join(HERE, "builder_set_0001.published.json")
    json.dump(full, open(full_path, "w"), indent=2)
    open(full_path, "a").write("\n")
    json.dump(pub, open(pub_path, "w"), indent=2)
    open(pub_path, "a").write("\n")
    print(f"wrote {full_path} ({len(entries_full)} entries)")
    print(f"wrote {pub_path} ({len(entries_pub)} entries)")


def contact_sheet(plan, tag="progress"):
    from PIL import Image
    import random

    tiles = []
    for s in plan:
        p = kit_paths(s["image_id"])["png"]
        if os.path.exists(p):
            tiles.append({"path": p, "origin": "builder_set_0001", "frame": s["frame"],
                          "definition": s["definition"], "skin": s["skin"],
                          "id": s["image_id"]})
    # Mix with set_0001 kits for style drift check
    man = {e["recruit_id"]: e for e in
           json.load(open(os.path.join(HERE, "set_0001.manifest.json")))["entries"]}
    s1 = []
    if os.path.isdir(RECRUIT_KIT_LEGACY):
        for fn in os.listdir(RECRUIT_KIT_LEGACY):
            if not fn.endswith(".png") or fn.endswith(".mask.png"):
                continue
            rid = fn[:-4]
            e = man.get(rid)
            if not e:
                continue
            s1.append({"path": os.path.join(RECRUIT_KIT_LEGACY, fn),
                       "origin": "set_0001", "frame": e["build"]["frame"],
                       "definition": e["build"]["definition"],
                       "skin": e["portrait"]["skin"], "id": rid})
    rng = random.Random(50 if tag == "ckpt50" else 150)
    rng.shuffle(s1)
    n_mix = min(len(tiles), 20 if tag == "ckpt50" else 30)
    tiles = tiles[:60]  # cap sheet size
    mixed = tiles + s1[:n_mix]
    rng.shuffle(mixed)

    C, cols = 240, 10
    rows = (len(mixed) + cols - 1) // cols
    sheet = Image.new("RGB", (C * cols, C * rows), (236, 236, 238))
    key = []
    for i, t in enumerate(mixed):
        x, y = (i % cols) * C, (i // cols) * C
        im = Image.open(t["path"]).convert("RGBA")
        im.thumbnail((C - 6, C - 6))
        bg = Image.new("RGBA", (C, C), (236, 236, 238, 255))
        bg.alpha_composite(im, ((C - im.width) // 2, (C - im.height) // 2))
        sheet.paste(bg.convert("RGB"), (x, y))
        key.append({"index": i, "row": i // cols, "col": i % cols,
                    **{k: t[k] for k in t if k != "path"}})
    out = os.path.join(OUT_DIR, f"contact_sheet_{tag}_unlabelled.png")
    sheet.save(out)
    json.dump({"sheet": out, "tiles": key}, open(os.path.join(OUT_DIR, f"contact_sheet_{tag}_key.json"), "w"), indent=2)
    print(f"[sheet] {out}  ({len(mixed)} tiles)")
    return out


def load_or_build_plan():
    """Prefer the persisted bake_plan (keeps variety-rebake genes) when present."""
    if os.path.exists(PLAN_PATH):
        doc = json.load(open(PLAN_PATH))
        slots = doc.get("slots") or []
        if len(slots) == 150:
            return slots
    return build_plan()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--until", type=int, help="stop once this many kits are complete")
    ap.add_argument("--write-manifests", action="store_true")
    ap.add_argument("--contact-sheet", action="store_true")
    ap.add_argument("--stage", action="store_true", help="copy finished kits to assets_staging")
    ap.add_argument("--rebuild-masks", action="store_true",
                    help="regenerate mask/json from existing kit PNGs (bad/missing by default)")
    ap.add_argument("--validate-masks", action="store_true",
                    help="exit 1 if any staged/kit mask is below the tank-pixel floor")
    ap.add_argument("--image-id", action="append", default=[],
                    help="limit --rebuild-masks to these image_ids (repeatable)")
    ap.add_argument("--sheet-tag", default="progress")
    ap.add_argument("--rebuild-plan", action="store_true",
                    help="ignore persisted bake_plan.json and rebuild from allocation")
    args = ap.parse_args()

    os.makedirs(KIT_DIR, exist_ok=True)
    plan = build_plan() if (args.plan_only or args.rebuild_plan) else load_or_build_plan()
    # Only rewrite bake_plan when explicitly planning/rebuilding — not on stage/manifest/sheet/bake resume
    if args.plan_only or args.rebuild_plan:
        with open(PLAN_PATH, "w") as fh:
            json.dump({"count": len(plan), "actions": dict(Counter(s["action"] for s in plan)),
                       "slots": plan}, fh, indent=2)
            fh.write("\n")
        print(f"plan: {len(plan)} slots -> {PLAN_PATH}")
        print(f"  actions: {dict(Counter(s['action'] for s in plan))}")
    else:
        print(f"plan: {len(plan)} slots (from {PLAN_PATH if os.path.exists(PLAN_PATH) else 'rebuild'})")
        print(f"  actions: {dict(Counter(s['action'] for s in plan))}")
    print(f"  collision check vs recruit_set_0001: PASS ({len(load_recruit_set_ids())} reserved)")

    if args.plan_only:
        return

    if args.validate_masks:
        validate_masks(plan)
        return

    if args.rebuild_masks:
        _rebuilt, failed = rebuild_bad_masks(plan, image_ids=args.image_id or None)
        if failed:
            raise SystemExit(1)
        validate_masks(plan)
        return

    if args.write_manifests:
        write_manifests(plan)
        return

    if args.contact_sheet:
        contact_sheet(plan, tag=args.sheet_tag)
        return

    if args.stage:
        n = stage_to_assets(plan)
        print(f"staged {n} kits -> {STAGING_KIT}")
        return

    # Import kept teen pilots first (counts toward the until target)
    for s in plan:
        if s["action"] == "keep_teen":
            import_teen_pilot(s)
            print(f"[keep] {s['frame']}-{s['definition']}/{s['skin']}  {s['image_id'][:8]}…")

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY not set in the invoking process")
    from google import genai
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    ref_cache = {}

    target = args.until or 150
    ok = skip = fail = 0

    def work_queue():
        # 1) Always finish rebakes (developed → teen) first — they supersede pilot art
        for s in plan:
            if s["action"] == "rebake_teen" and not kit_complete(s["image_id"]):
                yield s, True
        # 2) New bakes until we hit the checkpoint / finish line
        for s in plan:
            if s["action"] != "bake_new":
                continue
            if kit_complete(s["image_id"]):
                continue
            if count_complete(plan) >= target:
                return
            yield s, False

    for s, force in work_queue():
        if not force and count_complete(plan) >= target:
            break
        try:
            if force:
                for p in kit_paths(s["image_id"]).values():
                    if os.path.exists(p):
                        os.remove(p)
            result = bake_one(s, client, ref_cache, force=force)
            if result == "skip":
                skip += 1
            else:
                ok += 1
                print(f"[ok {count_complete(plan)}/{target}] {s['frame']}-{s['definition']}/{s['skin']} "
                      f"({s['action']}) {s['image_id'][:8]}…")
        except Exception as e:
            fail += 1
            print(f"[fail] {s['image_id']}: {e}")

    done = count_complete(plan)
    print(f"\n[done] complete={done}/150  this_run ok={ok} skip={skip} fail={fail}")
    if done >= min(target, 50):
        tag = "ckpt50" if (args.until and args.until <= 50) or done < 150 else "final"
        contact_sheet(plan, tag=tag)


if __name__ == "__main__":
    main()
