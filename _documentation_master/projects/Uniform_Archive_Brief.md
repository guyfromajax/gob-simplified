# Uniform Archive Brief — share painted portraits across franchises

**Status: BUILT, unverified against R2.** Written and implemented 2026-09-08 after tracing the
"CPU sprites show initials" bug. Every paint path is unexercised locally (no R2 credentials);
staging is the first place the archive write, the mirror copy, and the self-heal are proven.

## The problem in one line

Painted masters are keyed by `player_id` — a fresh UUID per signing, per franchise — so the same
recruit in the same team's colours is repainted from scratch for every user, forever.

## Why this is the wrong key

`make_signed_master(kit_png, mask_png, primary_hex, secondary_hex, wordmark)` is a pure function.
Its output is determined by exactly four things:

| Input | Comes from |
|---|---|
| kit + tank mask | `image_id` via `resolve_kit_keys()` |
| primary_color, secondary_color, mascot | `resolve_team_display(franchise, team_object_id)` |

`player_id` is **not** an input. Keying the output by it guarantees duplicates.

### Measured cost of the duplication

| | |
|---|---|
| Master size | **10.5 MB** (3530x3412 RGBA PNG) |
| Paint cost | **~1.0 s CPU**, 1-3 s wall with R2 I/O |
| Signed recruits per franchise per season | ~300 |
| Storage per franchise per season | **~3.1 GB** |
| Distinct images actually needed | one per (image_id x team colours) — bounded by the library, not by users |

At a few hundred franchises this is terabytes of byte-identical objects and hours of repeated CPU.

## The design

```
uniforms/<image_id>__<color_key>.png        # the archive — painted once, reused forever
players/master/<player_id>.png              # legacy — keep resolving, never write new ones
```

`color_key` = short stable hash of `(primary_color, secondary_color, mascot)`, normalised
lower-case hex without `#`. Mascot is included because it is stamped into the pixels.

### Write path

1. Resolve `image_id` + team display -> compute `uniform_key`.
2. `r2_images.exists(uniform_key)` -> done, no paint. **This is the whole point.**
3. Miss -> `make_signed_master(...)` -> `put(uniform_key)`.
4. Stamp `meta.uniform_key` on the FPD doc.

Idempotent, and the hit rate rises monotonically as franchises accumulate.

### Read path

`API_CONFIG.getPlayerImageUrl` is already the single resolver ("no view builds image paths
inline" — Player_Image_System.md). It gains one branch:

```
uniform_key present on the payload -> uniforms/<uniform_key>.png
otherwise                          -> players/master/<player_id>.png   (legacy, unchanged)
```

No big-bang migration: existing painted masters keep resolving until their player is re-stamped.

### Rebrands fall out for free

A Team Builder rebrand changes the colours, therefore the key, therefore the object. The current
scheme silently keeps the stale master forever, because both paint paths skip on
`exists(players/master/<player_id>.png)` and the key has no colour component. That defect
disappears rather than needing a fix.

## Sequencing — why this lands BEFORE the paint jobs

The bug fix (below) is about to paint ~300 masters per franchise. Under `player_id` keying every
one of those is a duplicate that the archive makes redundant, and would need repainting later.
Changing the key first means the backfill **populates the archive** instead of filling R2 with
garbage.

Order: **archive key -> backfill -> Signing Day / camp-cut queue -> per-game warm -> preloader
self-heal.**

## What shipped

| Piece | File |
|---|---|
| Key + paint-or-reuse | `BackEnd/utils/uniform_archive.py` |
| Key contract (11 tests, value pinned) | `tests/test_uniform_archive_key.py` |
| Server-side mirror copy | `BackEnd/services/r2_images.py` -> `copy()` |
| ensure -> archive, stamps `meta.uniform_key` | `BackEnd/api/player_image_routes.py` |
| Archive-preferring resolver | `FrontEnd/static/js/config/api-config.js` |
| `uniform_key` on game payloads | `BackEnd/models/player.py`, `BackEnd/utils/shared.py` |
| Sprite preloader: uses key + bounded self-heal | `js/phaser/setup/preloadPlayerHeadshots.js` |
| Backfill (dry-run default) | `scripts/backfill_uniform_archive.py` |
| Pre-game warm (non-blocking) | `POST /player-image/warm-teams`, fired from `set-lineup.js` |
| User/CPU camp cuts unified on lazy | `franchise_routes.py` `warm=True` -> `False` |

### The background queue was NOT built, deliberately

The original plan had a Signing Day / camp-cut job painting every new portrait ahead of time.
It is not needed and would have been a fifth orphaned mechanism:

- The **archive makes paints shared**, so the Nth franchise to sign a recruit to a team pays
  nothing. Load falls as adoption rises rather than scaling with users.
- The **pre-game warm** already paints exactly the players about to be seen, at the one moment
  the user is guaranteed to be idle (Set Lineup), and skips anything already stamped.
- The work therefore spreads itself naturally across games instead of spiking at week 35.

Revisit only if measurement shows a first-play-after-Signing-Day stall. The per-game warm logs a
summary (`[WARM] franchise=... {...}`) precisely so that is answerable from production logs.

## Out of scope (recorded, not solved)

- **10.5 MB masters.** Cloudflare pulls the full original on first request per size. Worth
  revisiting independently of this brief; it is the likely cause of the pre-game lineup delay on
  images that ARE painted.
- **Walk-on / recruit portrait assignment.** Unchanged: `image_id` is stamped only when a player
  survives camp cuts onto the active 12, for user and CPU alike.

## Tunable Constants

| Constant | Value | Effect |
|---|---|---|
| `CANVAS_W, CANVAS_H` (`recruit_image.py:23`) | `3530, 3412` | Master resolution. Drives the 10.5 MB size and ~1 s paint. |
| `UNIFORM_KEY_LEN` (new) | `12` | Hex chars of the colour hash. Shorter = prettier keys, higher collision risk. |
| `WARM_CONCURRENCY` (new) | `2` | Parallel paints. Each holds ~48 MB arrays; Railway runs `MALLOC_ARENA_MAX=2` after an RSS incident, so raise only with measurement. |
| `REVEAL_PREPAINT` (`recruiting-hub.js`) | `15` | Reveal cards force-painted behind the "Prepping Signing Day" screen. |
