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
| Recruit faces | **Pre-generated white library / sellable pack** | ~$0 marginal per season, instant, and *is* the monetizable 300-pack. (Alt: fresh NB per franchise ≈ $18/season — rejected.) |
| Offline uniforming | **Online-first; keep apply portable, defer offline port** | Ship server path now; the recolor is dependency-light so it drops into the download later with no rework. |
| Uniform storage | **Tiny `teams_uniforms.json` recipe manifest** | No rendered uniforms on R2 — a jersey is data, not an image. |
| Manifest shape | **Variant-based** (`base`, `zones`, `variants[]`) | Future jersey DLC (black / white / color-rush) slots in with no schema change. |
| All 128 teams | **Same templated recolor — Conf1 included, no special-casing** | Simplicity + scale. One code path. |
| Conf1 bespoke art | **Leave existing veterans as-is; recruits get templated** | Don't destroy the hand-painted originals; teams converge to templated as veterans graduate. |
| Body types | **Handled for free** (per-body mask + auto-fit wordmark) | No per-frame work; library just needs coverage across all five frames. |

---

## Asset lifecycle

```
GENERATION (season start / pack build — server-side, full pipeline)
  recruit gets a UUID (_id)         <-- critical: recruits have no _id today
  -> assign a white portrait from the pre-generated library (by frame/geometry, UUID-seeded)
  -> finished white master     ->  recruits/white/<uuid>.png     (shown weeks 1-34)
  -> baked uniform "kit"       ->  recruits/kit/<uuid>.*         (mask + tank bbox; recolor input)

SEASON (weeks 1-34)
  game shows recruits/white/<uuid>.png  — no compute

SIGNED (week 35)
  look up new team's recipe in teams_uniforms.json
  apply_uniform(kit, primary, trim, wordmark) -> finish
  -> uniformed master          ->  players/master/<uuid>.png     (same path the game already resolves)
  online: backend writes to R2   |   offline: same fn writes to local asset store

FOREVER AFTER
  game shows players/master/<uuid>.png
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

1. **Manifest** — generate `teams_uniforms.json` from `128_teams.txt` (variant-shaped,
   `base: primary` for all 128).
2. **Recruit identity** — mint a UUID (`_id`) for each recruit in
   [`generate_recruits_list()`](../../BackEnd/models/franchise_manager.py) (they have none today).
3. **White library + kit baker** — pre-generate the white-portrait pool (all five frames) and
   bake each one's uniform kit (mask + bbox). Upload `recruits/white/` + `recruits/kit/`.
4. **Recolor refactor** — factor `apply_uniform()` out of `apply_team_uniforms.py`,
   u2net-free.
5. **Signing hook** — on week-35 recruit signing, run apply_uniform → finish → write
   `players/master/<uuid>.png`.
6. **Frontend wiring** — resolve `recruits/white/<uuid>.png` pre-signing (a `getRecruitImageUrl`
   or a fallback in `getPlayerImageUrl`); post-signing the existing player resolver just works.
7. **Offline (later)** — port `apply_uniform()` into the downloadable build; ship white
   masters + kits + manifest in the pack.

---

## Open items / decisions still needed

- **Downloadable stack** (Electron/JS, Unity/C#, Godot, native) — determines whether the
  offline recolor is a client reimplementation or a bundled helper. Needed before Phase 7.
- **Kit format** — sidecar mask PNG vs baked alpha channel vs geometry-only. Lean: sidecar
  mask PNG (lossless, simplest).
- **Library size / uniqueness policy** — how many white portraits in the shared online pool,
  and whether packs are exactly-300 unique or drawn from a larger library.
- **Zone catalog** — which jersey zones (sleeves / side-panel / yoke / collar) to bake now, to
  future-proof patterned-jersey DLC without re-baking the library.

---

## Not in scope here

- The one-time generation of the league's **existing** 1,536 player masters — see
  [Player Image System](./Player_Image_System.md) for the built pipeline and R2 runbooks.
- Recruit **gameplay** (attributes, recruiting activities, signing rules) — this doc covers
  images only.
- Pixel-exact reproduction of Conf1 bespoke jerseys — deliberately out of scope (see above).
