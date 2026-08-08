# Recruit Set Schema

The frozen data contract for pre-built recruit sets **and** Team Builder portrait
extension sets. See the design doc
[`_documentation_master/00_Operations/Recruit_Image_System.md`](../../_documentation_master/00_Operations/Recruit_Image_System.md)
for the full architecture; this file is the exact field-level spec the **baker** writes and the
**loader** reads.

## Two sequences (by purpose)

| Sequence | Purpose | Who draws from it | Current |
|---|---|---|---|
| **`recruit_set_NNNN`** | Pre-built recruit classes (stats + kits) | Recruit assignment **only** | `recruit_set_0001` (450) |
| **`builder_set_NNNN`** | Portrait kits for Team Builder body/skin coverage | Team Builder picker + fitted assignment | `builder_set_0001` (150) |

**Team Builder pool** = `recruit_set_0001` ∪ `builder_set_0001`.  
**Recruit assignment** = `recruit_set_0001` alone — never add a builder set to the recruit pool.

### Legacy aliases (do not migrate)

| Logical name | On-disk / Mongo `set_id` | Kit R2 prefix |
|---|---|---|
| `recruit_set_0001` | `set_0001` (file `set_0001.json`, collection `recruit_sets`) | **`recruits/kit/<uuid>.png`** — leave the existing 300 objects here; do not move them |
| `builder_set_0001` | `builder_set_0001` | **`portrait-kits/builder_set_0001/<uuid>.png`** (+ `.mask.png`, `.json`) |

Future recruit classes continue `recruit_set_0002`, `0003`, … (new prefix optional at cutover).  
Future builder extensions continue `builder_set_0002`, `0003`, ….

A recruit set is a batch of pre-built recruits shipped as a unit (`recruit_set_0001` is **450**
after the regen; was 300). Each recruit carries a **stable
`recruit_id`** that keys its pre-generated uniform kit. At signing the player gets a fresh
unique `player_id` (not the recruit_id — set recruits share one recruit_id across franchises,
which would collide); the portrait follows via `image_id`.

There are **two artifacts** for recruit sets:

| Artifact | Consumed by | Contains |
|---|---|---|
| **A. Set document** | the game (loaded into FRD) | identity + stats only — lean |
| **B. Baking manifest** | the baker / QC only (sidecar) | projected build + portrait genes |

Builder sets ship a **baking manifest** plus a **published filtered subset** (below) — no
recruit stats document.

---

## A. Set document — game-facing

One document per set. In online play this is a doc in the `recruit_sets` collection; in the
downloadable build it ships as a pack file. Self-contained (~1 MB), well under Mongo's 16 MB.

```jsonc
{
  "set_id": "set_0001",           // human-readable, stable, globally unique
  "version": 2,                   // schema/content version; bump if regenerated
  "recruit_count": 450,
  "recruits": [
    {
      "recruit_id": "550e8400-e29b-41d4-a716-446655440000",  // stable UUID
      "name": "Marcus Ellison",
      "year": "JH",               // enum: "JH" | "Freshman" | "Sophomore" | "Junior"
      "archetype": "Athlete",     // any RecruitManager archetype label
      "height": 74,               // integer inches, AS GENERATED (not projected)
      "weight": 190,              // integer lbs,   AS GENERATED (not projected)
      "attributes": { /* exactly the dict generate_recruits_list() emits — see below */ },
      "position_ratings": { "PG": 41, "SG": 44, "SF": 47, "PF": 39, "C": 30 },
      "Home Region": "C"          // stable identity — region A–H, baked once, same in every franchise
    }
    // ... 449 more
  ]
}
```

### Field notes

- **`recruit_id`** — UUIDv4 string, minted once at bake time and never changed. The join key
  across the whole image lineage (`recruits/kit/…` → `players/master/…`).
- **`height` / `weight`** — the **as-generated** values, unchanged from `generate_recruits_list()`.
  The mature-build **projection is baking-time only** (Artifact B) and does **not** overwrite
  these — gameplay still starts the recruit at his real generated size and grows him via the
  normal training-camp path.
- **`attributes`** — store the **full dict exactly as `generate_recruits_list()` produces it**,
  so the loader can insert it into FRD verbatim. Core 13 codes:
  `SC SH ID OD PS BH RB AG ST ND IQ FT` + `CH` (and `anchor_CH`). The dict may also include
  gameplay-only fields (`NG`, `MO`, `EM`) from `randomize_game_attributes()` — keep whatever is
  present; do not cherry-pick.
- **`position_ratings`** — as produced by `compute_position_ratings(recruit, profile="recruit")`;
  keys are `PG SG SF PF C`.
- **`year`** — one of the four recruit years. The pool skews heavily **JH** (per draw: Freshman
  10–30, Sophomore 5–15, Junior 5–15, JH = remainder — so a larger pool is proportionally more JH).
- **`Home Region`** — one of `A`–`H`. **Stable identity**: baked once (by the baker, or by
  `bake_home_region.py` for the original set) and read verbatim by the loader, so the recruit
  lands in the same region in every franchise. Note: `Lean` is **not** stored — it still derives
  per-franchise from this region with its own randomness (75% "open", etc.), and jersey is still
  rolled at signing. A recruit with no `Home Region` (dynamic, or a legacy un-baked set) falls
  back to the loader's per-franchise random draw.

### Deliberately excluded (layered on per-franchise at load time — never in the set)

`franchise_id`, `Lean`, `created_at`. These are genuinely franchise-specific and assigned
when the set is loaded into FRD, keeping the set portable across every franchise that draws it.
(`Home Region` used to be here too, but is now baked as stable identity — see above.)

---

## B. Baking manifest — sidecar (build-time only)

One entry per `recruit_id`. The recruit analog of `players_archetypes.csv`: it records the
projected mature build and the portrait genes used to generate the kit. **Never loaded
into the game** — it exists for the baker and for QC/reproducibility.

```jsonc
{
  "set_id": "set_0001",
  "entries": [
    {
      "recruit_id": "550e8400-e29b-41d4-a716-446655440000",
      "projected": {                 // post-projection values fed to the classifier
        "height": 77, "weight": 212, // Projection 2 (growth model)
        "ST": 105, "AG": 109, "RT": 68  // Projection 1 (attr maturity scaling, /factor)
      },
      "build": { "frame": "Broad", "definition": "Cut" },   // classifier output
      "portrait": {                  // classifier-assigned portrait genes
        "race": "black", "skin": "black-normal",
        "hair": "a short crop", "face_prompt": "He has ...",
        "accessories": ""
      }
    }
    // ... one per recruit
  ]
}
```

`projected.*` are the mature-equivalent inputs (see *Recruit build projection* in the design
doc: attr factors JH 0.55 / FR 0.65 / SO 0.80 / JR 1.00, plus height/weight growth). `build`
and `portrait` drive the reference-body pick + NB face-swap, exactly like the 127-team pipeline.

---

## C. Published filtered subset (game-facing — deliberate exception)

`SCHEMA` historically said Artifact B is never loaded into the game. **Exception:** Team Builder
needs portrait metadata for filtering and fitted assignment. Both `recruit_set_0001` and
`builder_set_0001` publish a **filtered** view:

| Published | Not published |
|---|---|
| `image_id` (or `recruit_id` for recruit kits) | `portrait.race` |
| `build.frame` | hair / face / expression genes |
| `build.definition` | projected ST/AG/RT, accessories |
| `portrait.skin` | |

Files:
- Recruit legacy: baking manifest `set_0001.manifest.json` (full genes); filtered publish is the
  same field subset when wired into TB (do not rewrite the baking sidecar).
- Builder: `builder_set_0001.manifest.json` (full genes, baker/QC) and
  `builder_set_0001.published.json` (filtered subset above).

---

## ID & file conventions

| Thing | Convention |
|---|---|
| Recruit sequence | `recruit_set_NNNN` (logical). Legacy on-disk/Mongo id for the first class: `set_0001` |
| Builder sequence | `builder_set_NNNN` |
| `recruit_id` / `image_id` | UUIDv4 string — globally unique across **both** sequences (collision at kit path overwrites art) |
| Recruit kit (R2) — **legacy** | `recruits/kit/<uuid>.png` (+ `.mask.png`, `.json`) — `recruit_set_0001` stays here |
| Builder kit (R2) | `portrait-kits/builder_set_0001/<uuid>.png` (+ `.mask.png`, `.json`) |
| Uniformed master (post-sign, R2) | `players/master/<uuid>.png` |
| Recruit set file | `set_0001.json` (legacy name) / future `recruit_set_NNNN.json` |
| Builder allocation / manifests | `builder_set_NNNN.allocation.json`, `.manifest.json`, `.published.json` |

---

## Validation rules (baker must enforce)

1. Recruit sets: `recruits` length == `recruit_count`. (`recruit_set_0001` is **450** after the
   300→450 regen — 300 reuse + 150 new; it was 300 pre-regen. The invariant is the length/count
   match, not a fixed number.)
2. All ids unique **within the set** and disjoint from every other published kit UUID
   (recruit + builder). Before writing any kit to a flat or prefixed path, verify no collision.
3. Every kit has bust + mask + geometry at its R2 keys before the set is published.
4. Frames span all five (`Slight, Lean, Normal, Broad, Doughy`) so builds match faces
   (recruit sets). Builder sets follow their allocation — coverage-driven, not uniform.
5. Recruit `year` ∈ the four-value enum; `attributes` contains the core 13 codes.
6. Builder published subset must not include `portrait.race`.
7. Recruit assignment loaders must not read `builder_set_*`.
