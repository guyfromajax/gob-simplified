# Recruit Set Schema

The frozen data contract for pre-built recruit sets. See the design doc
[`_documentation_master/00_Operations/Recruit_Image_System.md`](../../_documentation_master/00_Operations/Recruit_Image_System.md)
for the full architecture; this file is the exact field-level spec the **baker** writes and the
**loader** reads.

A "set" is 300 pre-built recruits shipped as a unit. Each recruit carries a **stable
`recruit_id`** that keys its pre-generated uniform kit in R2 (`recruits/kit/<recruit_id>.png`) and
survives all the way to the rostered player (`player_id = recruit_id` at signing).

There are **two artifacts**:

| Artifact | Consumed by | Contains |
|---|---|---|
| **A. Set document** | the game (loaded into FRD) | identity + stats only — lean |
| **B. Baking manifest** | the baker / QC only (sidecar) | projected build + portrait genes |

---

## A. Set document — game-facing

One document per set. In online play this is a doc in the `recruit_sets` collection; in the
downloadable build it ships as a pack file. Self-contained (~1 MB), well under Mongo's 16 MB.

```jsonc
{
  "set_id": "set_0001",           // human-readable, stable, globally unique
  "version": 1,                   // schema/content version; bump if regenerated
  "recruit_count": 300,
  "recruits": [
    {
      "recruit_id": "550e8400-e29b-41d4-a716-446655440000",  // stable UUID
      "name": "Marcus Ellison",
      "year": "JH",               // enum: "JH" | "Freshman" | "Sophomore" | "Junior"
      "archetype": "Athlete",     // any RecruitManager archetype label
      "height": 74,               // integer inches, AS GENERATED (not projected)
      "weight": 190,              // integer lbs,   AS GENERATED (not projected)
      "attributes": { /* exactly the dict generate_recruits_list() emits — see below */ },
      "position_ratings": { "PG": 41, "SG": 44, "SF": 47, "PF": 39, "C": 30 }
    }
    // ... 299 more
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
- **`year`** — one of the four recruit years. A 300-pool skews heavily **JH** (Freshman 10–30,
  Sophomore 5–15, Junior 5–15, JH = remainder).

### Deliberately excluded (layered on per-franchise at load time — never in the set)

`franchise_id`, `Home Region`, `Lean`, `created_at`. These are franchise-specific and assigned
when the set is loaded into FRD, keeping the set portable and identical across every franchise
that draws it.

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

## ID & file conventions

| Thing | Convention |
|---|---|
| `set_id` | `set_NNNN` zero-padded, human-readable, unique (`set_0001`, `set_0002`, …) |
| `recruit_id` | UUIDv4 string |
| White display master (R2) | `recruits/white/<recruit_id>.png` (finished, shown weeks 1-34) |
| Uniform kit (R2) | `recruits/kit/<recruit_id>.png` (+ `.mask.png`, `.json` sidecars) |
| Uniformed master (post-sign, R2) | `players/master/<recruit_id>.png` |
| Set file (offline pack) | `set_NNNN.json` (Artifact A) |
| Baking manifest (repo/build) | `set_NNNN.manifest.json` (Artifact B) |

---

## Validation rules (baker must enforce)

1. `recruits` length == `recruit_count` == 300.
2. All `recruit_id`s unique **within the set** (and, for online, globally across `recruit_sets`).
3. Every recruit has a kit (bust + mask + geometry) **and** a finished white display master at its R2 keys before the set is published.
4. Frames span all five (`Slight, Lean, Normal, Broad, Doughy`) so builds match faces.
5. `year` ∈ the four-value enum; `attributes` contains the core 13 codes.
