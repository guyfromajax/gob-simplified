# Recruit Image System

> **Status: BUILT (backend) — verifying in staging.** The backend is implemented and merged/in
> review; `set_0001` (300 recruits) + kits are live in R2 and loaded in staging. Remaining:
> wire R2 creds on Railway, frontend *rendering* (owner + C+C), and the offline port.
> **The [As-built architecture](#as-built-architecture-current) section below is authoritative;**
> the deeper design sections that follow it (build projection, classifier, monetization, Conf1)
> remain the design rationale and are still accurate.

Every season a franchise generates **300 recruits**. This system gives each a **white-shirt
portrait** during the recruiting season, then **paints their new team's uniform onto that white
shirt when they sign** (week 35). The same design runs **online today** and in the future
**downloadable/offline build** — identical recolor logic, different place it executes.

It is the recruit-facing extension of the [Player Image System](./Player_Image_System.md)
(the "layered pipeline: base portrait + per-team uniform overlay"). It reuses the same R2 bucket,
`assets.geekedoutgames.com` domain, UUID-keyed object layout, and the frontend resolver.

---

## As-built architecture (current)

Two ideas the original design didn't have, both now implemented:

### 1. `image_id` — the indirection that makes images reusable

Every recruit carries an **`image_id`**: *the portrait it wears*. Image resolution always keys
off `image_id`, never the recruit's own id. This is the single field that lets the same 300 base
images back both purchased sets and dynamically generated classes:

- **Set recruit** → `image_id = recruit_id` (its own pre-built portrait).
- **Dynamic recruit** (a season where no fresh pack was bought) → **borrows** a portrait from the
  **base image library `set_0001`** at random — a shuffled 1:1 mapping so no two recruits in a
  class share a face (wraps only if a class exceeds the library; no library → generic headshot).

`image_id` is stamped by `assign_image_ids()` in `BackEnd/models/recruit_sets.py` and flows
**FRD → `signed_players` → FPD.meta**. The base library is independent of `used_recruit_set_ids`,
so the borrow pool survives after `set_0001` is consumed as a class.

This serves all three monetization profiles with one mechanism:

| Profile | Each season |
|---|---|
| **Never buys packs** | dynamic class + borrowed `set_0001` faces — always has images; the same 300 recur (the intended staleness that drives pack sales) |
| **Buys a fresh pack every season** | loads a purchased set — unique art, `image_id = recruit_id` |
| **Mix** | each season independently loads a set *or* generates + borrows |

Reuse assignment is **purely random** (shuffled) by decision — recruits have no in-game race, so
the image simply *defines* appearance; only body plausibility could matter and it was judged not
worth the complexity.

### 2. Lazy paint (generate-on-miss) — nothing pre-rendered but the kit

The only baked artifact is the **kit** (pre-finish white bust + tank mask + geometry). Both the
white display master *and* the uniformed master are **painted on first view and cached in R2
forever after** — no pre-generation, no batch job, no queue:

```
<img src = CDN/players/master/<player_id>.png>
   200 → show it (painted already; backend never touched again)
   404 → onerror → POST /player-image/ensure {franchise_id, player_id}
             backend: resolve image_id+team → read kit from R2 → recolor → upload master
          → retry <img> → 200 → show   (still fails → generic_headshot)
```

- **White master** (`recruits/white/<image_id>.png`, pre-signing) → `POST /recruit-image/ensure
  {image_id}` finishes the kit bust. No recolor.
- **Uniformed master** (`players/master/<player_id>.png`, post-signing) → `POST
  /player-image/ensure` recolors the kit into the signed team's colors.

> **`player_id` is a fresh unique uuid at signing — NOT the recruit_id.** Set recruits share one
> recruit_id across every franchise (all draw set_0001), so keying the uniformed master by
> recruit_id would collide across franchises that sign the same recruit to different teams
> (first-writer-wins → wrong jersey). The portrait link is `image_id`, not `player_id`, so a
> unique player_id is free — each signed player gets its own uniformed master.

Both endpoints (`BackEnd/api/player_image_routes.py`) are idempotent, auth'd, and degrade to a
status the frontend reads as "use generic" — **never a 500**. The paint core
(`BackEnd/services/recruit_image.py`) is a **verbatim port** of the league recolor + finish, so
recruits render pixel-identical to live players. R2 I/O is a thin `boto3` client
(`BackEnd/services/r2_images.py`); creds come from env vars on Railway.

**Team colors + wordmark come from the Mongo `team` doc** (`primary_color`, `secondary_color`,
`mascot`) — `teams_uniforms.json` is a **build-time artifact only**, not read server-side.

### Costs
No runtime AI cost (reuse + deterministic recolor). Only R2 storage (cheap, egress-free) + the
Cloudflare image transforms already used for league players + modest paint CPU on the existing
service. The NB generation cost is one-time, upfront, per sellable set.

### Portability
Online, `ensure` is a backend endpoint. In the download build the same "if missing, paint
locally, then show" runs on the user's machine (paint core reimplemented in the download
runtime). The `onerror → ensure` pattern maps directly to a local ensure call.

### As-built code map

| Piece | Location |
|---|---|
| `image_id` assignment + set loading | `BackEnd/models/recruit_sets.py` (`assign_image_ids`, `load_unused_set_or_generate`) |
| FRD/signed/FPD `image_id` plumbing | `franchise_manager.py`, `franchise_routes.py` |
| Paint core (recolor + finish, in-memory) | `BackEnd/services/recruit_image.py` |
| R2 client | `BackEnd/services/r2_images.py` |
| Lazy paint endpoints | `BackEnd/api/player_image_routes.py` |
| Frontend resolver + on-miss helpers | `getRecruitImageUrl` / `ensureRecruitImage` / `ensurePlayerImage` in `api-config.js` |
| Ops tooling (bake sets, kits, upload, load) | `scripts/recruit_sets/` |

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

## Recruit build projection & body-type assignment (planned)

A recruit's portrait is baked once and persists into his whole playing career, so it must
reflect his **projected mature build**, not his young recruit-day stats. The build is assigned
by the **same classifier as the 127 teams** — but fed a **forward-projected, mature-equivalent
record**, because recruit ratings/size are on a younger scale.

### How the classifier makes a build (unchanged, shared with the league pipeline)

- **DEFINITION** (muscle tone): `Cut` if `rt≥75 or (st≥65 & ag≥45)`; `Soft` if `rt≤45 & ag≤30`;
  else `Toned`. → driven by **RT, ST, AG**.
- **FRAME** (silhouette): height + BMI (`Lean <25.5`, `Broad ≥26.5`, `≤69" → Slight`, `Doughy`
  if soft+heavy+`st<55`). → driven by **height/weight**, with **ST** gating Broad (`st≥65`) vs
  Doughy.

So ST/AG/RT must be on the **player scale** and height/weight must be **projected**, or a young
recruit renders wrong (e.g. a strong JH prospect reads Soft/undefined; a big JH falls to Doughy).

### Projection 1 — attribute maturity scaling (ST, AG, RT)

Young recruits' attributes are generated on lower bands (`YEAR_TIER_RANGES` in
`franchise_manager.py`); the classifier thresholds are player-scale. Scale each recruit's
**ST, AG, RT up** into a mature-equivalent record by dividing by a per-year factor, then run the
unchanged classifier. (Scaling *up* — rather than cutting thresholds — is mathematically
identical but handles the Cut branch, the Soft branch, and the FRAME ST-override in one step,
and leaves the shared classifier untouched.)

| Recruit year | Factor | Basis |
|---|---|---|
| **JH** | **0.55** | `YEAR_TIER_RANGES` JH→Junior midpoint ratio avg = 0.54; matches the "JH ~doubles over career" rule of thumb |
| **Freshman** | **0.65** | band ratio 0.65 |
| **Sophomore** | **0.80** | band ratio 0.79 |
| **Junior** | **1.00** | already ~mature — no scaling |

- Consistent with the **RT color buckets** (`rtBucket.js`): JH RT uses a compressed scale
  (blue 50+, vs player 81+); FR/SO/JR already use the player scale. RT's own JH bucket factor is
  ~0.62 (slightly gentler than ST/AG) — start with the single per-year factor for all three, and
  swap RT to its exact bucket map only if RT-driven builds look off.
- **Not** related to `NG` (Natural Growth) — that's a gameplay-only combat-energy stat governing
  in-game attribute erosion, not evergreen progression; excluded here.

### Projection 2 — height/weight growth

Height/weight are **not** year-scaled at generation, so project them forward using the game's
**own** training-camp growth model (`training_execution_v2.py`), accounting for the year advancing
one step at signing:

| Recruit year | Grows through (post-signing) | Approx. projection |
|---|---|---|
| **JH** | Freshman + Sophomore camps | **~+2.5" / +20 lb** |
| **Freshman** | Sophomore camp | **~+0.5–1" / +8 lb** |
| **Sophomore / Junior** | none | **none** (current ≈ mature) |

Camp deltas (per camp): Freshman avg ≈ +2" height / +5–30 lb; Sophomore ≈ +0.5" / +0–10 lb.
Use **expected/median** deltas (deterministic) — the portrait is shared across franchises, so it
can't match any single franchise's random roll.

### Assembly

```
projected_record = recruit
  .scale(ST, AG, RT  /= year_factor)          # Projection 1  -> DEFINITION
  .add(height, weight += year_growth)          # Projection 2  -> FRAME
classify(projected_record) -> frame (Slight/Lean/Normal/Broad/Doughy) + definition (Cut/Toned/Soft)
```

Then the same downstream pipeline as the 127 teams (reference body → NB face-swap → white master
→ kit). **Library coverage requirement:** each set's 300 must span all five frames so builds
match faces.

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
2. **One set, end-to-end** — build a single set of 300: reuse the existing
   `generate_recruits_list()` for stats → **project to mature build** (attribute maturity
   scaling ST/AG/RT + height/weight growth, see *Recruit build projection*) → classify → records
   + white masters + kits. For the **first proof set, reuse existing generated faces** (zero NB
   cost) to validate the whole path before spending NB on fresh faces.
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
- **`player_id` is a fresh unique uuid at signing** (superseding the earlier `player_id =
  recruit_id`). The image lineage runs through `image_id`, not `player_id`, so a unique player_id
  avoids cross-franchise uniformed-master collisions (see the as-built section).
- **First proof set reuses existing faces** (free); fresh NB for real sets.
- **Portrait = projected mature build.** Attribute maturity scaling (ST/AG/RT) by per-year
  factor **JH 0.55 / FR 0.65 / SO 0.80 / JR 1.00**, plus height/weight growth projection; then
  the unchanged classifier. Tunable after eyeballing the first set.

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
