# Recruit Image System

> **Status: DESIGN / not yet built.** This is the agreed architecture and build plan for
> recruit portraits + on-signing uniform application. No code, assets, or R2 objects exist
> yet. Sections describing runtime behavior are the *intended* design, not current state.

Every season a franchise generates **300 recruits**. They currently have **no images**. This
system gives each recruit a **generic white-shirt portrait** for the recruiting season
(weeks 1–34), then **paints their new team's uniform onto that white shirt when they sign**
(week 35). The same design runs **online today** and in the future **downloadable/offline
build** — identical recolor logic, different place it executes.

It is the recruit-facing extension of the [Player Image System](./Player_Image_System.md)
(and the realization of the "layered pipeline: base portrait + per-team uniform overlay"
flagged as planned there). It reuses the same R2 bucket, `assets.geekedoutgames.com` domain,
UUID-keyed object layout, and the frontend resolver.

---

## Core principle — a "uniform" is a recipe, not an image

The single most important idea. A team uniform is **not** a stored graphic. It is:

- **a recipe** — `{ body_hex, trim_hex, wordmark, base }` — a few bytes per team, and
- **an algorithm** — recolor the player's *own* white tank to those colors (preserving the
  fabric fold-shadows), paint the collar/armhole trim, stamp the wordmark.

Consequences that shape the whole system:

- **We never store rendered uniforms.** There is nothing image-shaped to cache — a jersey
  only exists once painted onto a specific body. All 128 teams' recipes already live in
  [`teams/128_teams.txt`](../../teams/128_teams.txt).
- **Uniforming adapts to every body type for free.** The recolor mask and wordmark fit are
  computed per-player, so a Broad center and a Slight guard both get a correctly-scaled
  uniform with no per-frame logic. (Proven: the 1,536 shipped league players span all five
  frames through this exact recolor.)
- **The recolor is 100% deterministic.** Same white master + same recipe → identical output,
  every run, online or offline. No per-player or per-team randomness. Jersey body = **primary**
  for **all 128 teams** (the `INVERT_PCT` variety roll exists only in a retired NB script that
  never touched production).

---

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Recruit faces | **Fixed pre-built sets of 300** (loaded whole, never reused within a franchise) | ~$0 marginal per season, instant, and *is* the monetizable 300-pack. (Alt: fresh NB per franchise ≈ $18/season — rejected.) See *Recruit sets & season-init integration*. |
| Offline uniforming | **Online-first; keep apply portable, defer offline port** | Ship server path now; the recolor is dependency-light so it drops into the download later with no rework. |
| Uniform storage | **Tiny `teams_uniforms.json` recipe manifest** | No rendered uniforms on R2 — a jersey is data, not an image. |
| Manifest shape | **Variant-based** (`base`, `zones`, `variants[]`) | Future jersey DLC (black / white / color-rush) slots in with no schema change. |
| All 128 teams | **Same templated recolor — Conf1 included, no special-casing** | Simplicity + scale. One code path. |
| Conf1 bespoke art | **Leave existing veterans as-is; recruits get templated** | Don't destroy the hand-painted originals; teams converge to templated as veterans graduate. |
| Body types | **Handled for free** (per-body mask + auto-fit wordmark) | No per-frame work; library just needs coverage across all five frames. |

---

## Asset lifecycle

```
SET BUILD (offline, one-time — server-side, full pipeline)
  bake a fixed set of 300 recruits, each with a STABLE recruit_id (uuid)
  -> per recruit: white master  ->  recruits/white/<recruit_id>.png   (shown weeks 1-34)
  -> per recruit: uniform "kit"  ->  recruits/kit/<recruit_id>.*       (mask + bbox; recolor input)
  -> store the 300 records in the recruit_sets collection (see below)

SEASON START / ROLLOVER (per franchise, per season)
  pick a random UNUSED set -> load its 300 recruits into FRD with their stable ids
  (no unused set left -> fall back to dynamic generate_recruits_list, no images)

SEASON (weeks 1-34)
  game shows recruits/white/<recruit_id>.png  — no compute

SIGNED (week 35)
  player_id = recruit_id  (identity carries through — see integration below)
  look up new team's recipe in teams_uniforms.json
  apply_uniform(kit, primary, trim, wordmark) -> finish
  -> uniformed master          ->  players/master/<recruit_id>.png    (same path the game already resolves)
  online: backend writes to R2   |   offline: same fn writes to local asset store

FOREVER AFTER
  game shows players/master/<recruit_id>.png   (one UUID, one image lineage)
```

The **kit** is the one genuinely new artifact: a precomputed shirt-mask + tank geometry baked
at generation time. It lets the recolor skip **u2net segmentation** entirely, which is what
makes the apply step portable (server *or* the customer's machine).

---

## Object layout (R2 — planned)

| Asset | Object key | Written when |
|---|---|---|
| Recruit white master (weeks 1–34) | `recruits/white/<uuid>.png` | at recruit generation |
| Uniform kit (mask + bbox; recolor input) | `recruits/kit/<uuid>.png` (+ sidecar meta) | at recruit generation |
| Uniformed master (week 35+) | `players/master/<uuid>.png` | at signing |

Same bucket (`gob-player-images`), same domain, same `<uuid>.png` convention as the
[Player Image System](./Player_Image_System.md). In the **downloadable** build the white
masters + kits + `teams_uniforms.json` ship **inside the pack** instead of living on R2.

---

## Recruit sets & season-init integration (planned)

Today recruits are **generated dynamically** every season and given an **ephemeral** UUID at
DB-insert time — nothing an image can be pre-attached to. The new model loads **fixed,
pre-built sets of 300** whose recruits carry **stable** ids that match pre-baked images.

### How recruits work today (verified against code)

- Generated at **two** sites: season-1 init (`franchise_manager.py:437`) and every
  finish-season rollover (`franchise_routes.py:14079`), both `generate_recruits_list(count=300)`.
- `generate_recruits_list()` returns **id-less** profile dicts.
- Stored in the **`franchise_recruits_data` (FRD)** collection; a `recruit_id` = `str(uuid.uuid4())`
  is minted **at insert** (`franchise_manager.py:522`, `franchise_routes.py:14086`) and
  `delete_many`'d + regenerated fresh each season — not image-stable.
- At week-35 signing, `_week_35_result_entry_from_recruit` (`franchise_routes.py:10344`) mints a
  **third, unrelated** `player_id`; `recruit_id` is kept only as a back-reference (`:10345`).
- FPD player uniqueness is per-franchise: compound unique index `(franchise_id, player_id)`
  (`db.py:170`).

### `recruit_sets` collection (shared, read-only pool)

Each doc is one **self-contained** set (≈1 MB, well under Mongo's 16 MB limit); embedding the
full 300 records makes a set a portable unit == one downloadable pack file:

```jsonc
{
  "set_id": "set_0007",             // stable identifier
  "version": 1,
  "recruits": [                     // 300 frozen records
    { "recruit_id": "<uuid>", "name": "...", "attributes": {...},
      "position_ratings": {...}, "height": ..., "weight": ...,
      "archetype": "...", "year": "..." }
    // image lives in R2 at recruits/white/<recruit_id>.png ; kit at recruits/kit/<recruit_id>.*
  ]
}
```

### Per-franchise usage (never reuse a set within a franchise)

"Used" is a property of **(franchise × set)**, not of the set — sets are shared across
franchises. Track consumed sets on the franchise season-state (small, grows by one per season):

```
used_recruit_set_ids: ["set_0007", "set_0002", ...]
```

### Selection + graceful fallback (identical online & offline)

At each recruit-generation site:

```python
available = all_set_ids - franchise.used_recruit_set_ids
if available:
    set = random.choice(available)          # random unused set, per season
    recruits = load_set(set).recruits        # stable ids + pre-baked images
    franchise.used_recruit_set_ids.append(set)
else:
    recruits = generate_recruits_list(300)   # EXISTING path — no images, generic headshots
```

The current dynamic generator is **kept as the fallback**: a franchise that outlives the set
inventory just gets imageless recruits (today's behavior) — never a repeat, never a crash.

### Downloadable parity

Mechanically identical; only storage differs:

| | Online | Downloadable |
|---|---|---|
| Sets | `recruit_sets` collection (Mongo) | pack files shipped in the download |
| Used-list | `used_recruit_set_ids` on franchise doc | same array in the local save file |
| Exhausted | fall back to dynamic generation | fall back to dynamic generation |

### Code touch points (small, contained)

1. **Season-1 init** — `franchise_manager.py:437` (+ FRD insert `:522`): load an unused set;
   use its stable ids.
2. **Finish-season rollover** — `franchise_routes.py:14079` (+ FRD insert `:14086`): same swap.
3. **Signing** — `franchise_routes.py:10344`: `player_id = recruit_doc.get("recruit_id") or str(uuid.uuid4())`
   (real recruits keep their id → image lineage survives; walk-ons — `recruit_id: None`,
   `franchise_manager.py:224` — still get a fresh id and fall back to the generic headshot).

Two properties this buys for free:

- **No within-franchise identity collision** — a set is consumed once and signed recruits keep
  their id, so no later season can introduce a recruit whose id/face collides with a player
  already on the roster.
- **Cross-franchise face reuse is fine** — two different franchises may use the same set;
  images are shared/global by `recruit_id` (normal for a sports sim).

> **Inventory note:** the number of sets = seasons of *imaged* recruits per franchise (10 sets →
> 10 seasons, then the imageless fallback kicks in). Grow the online `recruit_sets` pool over
> time; the design supports it with no migration.

---

## The uniform recipe manifest — `teams_uniforms.json` (planned)

Single source of truth for all 128 teams. Version it in the repo **and** ship it in the game
bundle. Derived from `teams/128_teams.txt`. Variant-shaped from day one:

```jsonc
{
  "MORRISTOWN": {
    "base": "primary",                 // which hex is the shirt body (primary for all 128 today)
    "zones": [],                       // extra recolor regions (sleeves, side-panel, yoke) — empty = solid
    "variants": [
      { "id": "home",  "body": "#9AA0A6", "trim": "#C8102E", "wordmark": "M" }
      // future DLC: { "id": "blackout", "body": "#111111", "trim": "#C8102E", "wordmark": "M" }
    ]
  }
}
```

- **`variants[0]`** = the team's home look (what all 128 ship with today).
- **Special jerseys are data.** A black/white/color-rush *solid* jersey is just another
  `variants[]` row — no code, no re-render, near-zero marginal cost. Ideal DLC.
- **Patterned jerseys** (stripes, panels, sleeves) need extra **`zones`** — baked mask
  regions. Still no per-user cost, but more upfront work per design; decide desired zones
  *before* baking the white library so they don't need re-baking.

---

## The recolor engine (planned refactor)

Extract the recolor core out of [`scripts/apply_team_uniforms.py`](../../scripts/apply_team_uniforms.py)
into one **dependency-light** function, with the u2net/scipy dependency removed (the mask is
now precomputed in the kit):

```
apply_uniform(white_rgba, tank_mask, tank_bbox, primary, trim, wordmark) -> uniformed_rgba
```

One core, callers by environment:

| Environment | Caller | Notes |
|---|---|---|
| **Online (now)** | Flask backend job/endpoint at week-35 signing | writes `players/master/<uuid>.png` to R2; game auto-resolves it |
| **Offline (later)** | same logic ported to the download's runtime | reimplement in the game engine's language (Decision 2C) or bundle a tiny helper |

Because the mask is baked and it's just masked arithmetic + a text/decal draw, the port is
small and self-contained — the only real work the offline version adds.

---

## Body-type & library coverage requirement

The recolor handles all frames for free, **but** the pre-generated white library must be
**stocked across all five frames** (`Slight, Lean, Normal, Broad, Doughy`) so a recruit is
assigned a face matching his generated build (a 7-ft Broad center must not draw a Slight
body). Frame is derived from the recruit's height/weight/archetype via the same classifier
logic as the league players. **Requirement:** bake the library with good per-frame coverage.

---

## Conf1 teams (8) — same system, converge over time

The 8 Conf1 teams (`Bentley-Truman, Ocean City, Lancaster, Four Corners, Morristown, Xavien,
Little York, South Lancaster`) have **bespoke, human-painted jerseys** (multi-zone bodies,
multi-layer piping, custom crest logos) that the templated recolor **cannot** reproduce
exactly. Decision: **use the templated system for their recruits anyway.**

- Existing bespoke veterans are **left untouched** (already shipped, keyed by UUID).
- New recruits on those teams get the **templated** jersey (that team's primary/secondary +
  generic wordmark).
- Result: a temporary **mixed** look; as veterans graduate the team **fully converges** to
  templated. The bespoke originals read as legacy "throwbacks" on their way out.
- Optional future upgrade (not planned): a **crest-stamp hybrid** — templated recolor + the
  team's real crest art stamped as a decal + 2–3 zone masks — gets ~85–95% fidelity and
  preserves team identity as rosters turn over. Deferred by choice for simplicity/scale.

---

## Monetization fit

- A **pack of 300** = 300 white masters + their kits + `teams_uniforms.json`. Uniforms apply
  on-device after recruiting. Nothing per-team is pre-baked (a recruit joins exactly one team,
  so no 300×128 explosion).
- **Jersey DLC** = a tiny data drop of new `variants[]` rows recolored onto white masters the
  customer already owns. Near-zero marginal cost, infinite reuse.
- Hard-copy sim gamers get an offline-owned product; the recolor runs on their machine.

---

## Build phases (online-first)

1. **Set schema** — lock the frozen `recruit_sets` record shape + stable-id scheme (the contract
   the baker and the loader share).
2. **One set, end-to-end** — build a single set of 300: records + white masters + kits. For the
   **first proof set, reuse existing generated faces** (zero NB cost) to validate the whole
   path before spending NB on fresh faces.
3. **Recolor refactor** — factor `apply_uniform()` out of `apply_team_uniforms.py`, u2net-free.
4. **Manifest** — generate `teams_uniforms.json` from `128_teams.txt` (variant-shaped,
   `base: primary` for all 128).
5. **Loader + 3 touch points** — swap season-1 init (`:437`) and rollover (`:14079`) to load an
   unused set; unify `player_id = recruit_id` at signing (`:10344`); add `used_recruit_set_ids`.
6. **Signing hook** — on week-35 signing, run apply_uniform → finish → write
   `players/master/<recruit_id>.png`.
7. **Frontend wiring** — resolve `recruits/white/<recruit_id>.png` pre-signing (a
   `getRecruitImageUrl` or a fallback in `getPlayerImageUrl`); post-signing the existing player
   resolver just works.
8. **Prove online** — start a franchise, sign a few, confirm white → uniformed images follow the
   id through signing. **Then batch the remaining 9 sets.**
9. **Offline (later)** — port `apply_uniform()` into the downloadable build; ship sets + white
   masters + kits + manifest in the pack.

---

## Decisions locked (this section — resolved during design)

- **Fixed sets** of 300 (not a face library); a franchise loads a whole set per season.
- **Never reuse a set within a franchise**; random pick from unused; graceful fallback to
  dynamic generation when exhausted.
- **`player_id = recruit_id`** through signing — one image lineage; walk-ons excepted.
- **First proof set reuses existing faces** (free); fresh NB for real sets.

## Open items / decisions still needed

- **Downloadable stack** (Electron/JS, Unity/C#, Godot, native) — determines whether the
  offline recolor is a client reimplementation or a bundled helper. Needed before Phase 9.
- **Kit format** — sidecar mask PNG vs baked alpha channel vs geometry-only. Lean: sidecar
  mask PNG (lossless, simplest).
- **Online set inventory target** — how many `recruit_sets` to maintain (= seasons of imaged
  recruits per franchise); start at 10, grow over time.
- **Frame coverage per set** — each set's 300 must span all five frames so recruit builds match
  their assigned face.
- **Zone catalog** — which jersey zones (sleeves / side-panel / yoke / collar) to bake now, to
  future-proof patterned-jersey DLC without re-baking sets.

---

## Not in scope here

- The one-time generation of the league's **existing** 1,536 player masters — see
  [Player Image System](./Player_Image_System.md) for the built pipeline and R2 runbooks.
- Recruit **gameplay** (attributes, recruiting activities, signing rules) — this doc covers
  images only.
- Pixel-exact reproduction of Conf1 bespoke jerseys — deliberately out of scope (see above).
