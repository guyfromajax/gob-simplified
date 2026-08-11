# Player Image Migration Work Plan

## Objective

Move player image storage out of the Git repo into scalable object storage before scaling from ~98 portraits to 1,500+ (and years of ongoing additions).

**Decisions locked:**
- Storage: **Cloudflare R2** (S3-compatible, $0 egress, custom domain + CDN).
- Delivery: **Cloudflare Image Transformations** — resize/convert to WebP/AVIF **on-the-fly** from masters. No pre-baked variants.
- DB: store **`photo_asset_key` only**; derive URLs from env base.
- Migration is additive + fallback-safe. Local `/static/images/players/...` keeps working until remote is verified everywhere.

## Current State (measured)

| Fact | Value |
|---|---|
| Player images | 98 files, **442 MB** |
| Per-image | 4–6 MB PNG, 3530×3412 (oversized for headshots) |
| Tracked in git | All 98; `.git` already **1.6 GB** |
| 10x projection | ~1,000 images ≈ **4.4 GB** — unworkable in git |
| Resolution logic | Fragmented across ~10 files, inconsistent patterns |
| Naming | `{player_uuid}.png`; `generic_headshot.png` fallback |
| Prod path quirk | `/static/...` normalizes to `/images/...` |

Scattered call sites today: `roster.js:158` (hardcoded `/static/`), `potg.js:73` (`player.photo` + prefix), `set-lineup.js:1600` (`API_CONFIG.buildStaticPath`), `gameScene.js:1600` (own variant). Centralizing is core to this work.

## Why this approach

- **The real win is optimization, not storage.** Serving a 4–6 MB PNG as a headshot is wasteful anywhere. Thumbnails need ~256px, modals ~512px. Image Transformations delivers WebP/AVIF at the right size from one master → ~95% fewer bytes, much faster game.
- R2 $0 egress matters when serving images repeatedly.

## Target Architecture

### Storage layout (R2 bucket `gob-player-images`)
```text
players/master/{player_uuid}.png      # canonical 4-6MB source of truth
players/master/generic_headshot.png
# future layered pipeline:
players/base/{player_uuid}.png
uniforms/{team_id}/{frame_type}.png
```
Only **masters** are stored. Variants are generated at request time.

### Delivery (custom domain `assets.geekedoutgames.com`)
- Cloudflare Image Transformations resizes/reformats per request, e.g.
  `https://assets.geekedoutgames.com/cdn-cgi/image/width=256,format=auto/players/master/{uuid}.png`
- `format=auto` → WebP/AVIF where supported, PNG fallback.
- App requests a **named size** (thumb/card/modal), not arbitrary dimensions, so the CDN cache stays hot on a small set of variants.

### Cache & invalidation
- **UUID filenames are NOT immutable** — the layered pipeline will regenerate images. Long cache + bare UUID = stale images.
- Bust cache with a version token from DB on the asset key: `?v={photo_version|hash}`. Long-lived cache is then safe.

### Data model
```text
photo_asset_key: "players/master/{player_uuid}.png"   # canonical, stored
photo_version:   <int or short hash>                  # cache-bust on regen
```
- Store key + version only. **Do not persist full URLs** (couples DB to domain).
- Keep existing `photo` field untouched during initial migration.

### Runtime resolution (centralized in `api-config.js`)
Add one helper `API_CONFIG.getPlayerImageUrl(player, size)`; replace all ~10 call sites. Order:
1. `photo_asset_key` → built transformation URL (+ version).
2. Existing `player.photo`.
3. Local static `/images/players/{id}.png`.
4. `generic_headshot.png`.

## Migration Phases

### Phase 0: Decide git history
- Removing files later does **not** shrink the 1.6 GB history.
- Options: (a) live with current bloat, stop adding new images to git [recommended]; (b) `git filter-repo`/BFG rewrite — coordinated force-push.

### Phase 0.5: Account & domain setup — DONE / simplified

**Resolved 2026-06-30:** Cloudflare account active; `geekedoutgames.com` already hosted on Cloudflare (NS `lex/ruth.ns.cloudflare.com`); R2 bucket `gob-player-images` already created.

**Key decision:** serve images from **`assets.geekedoutgames.com`**, NOT a subdomain of the game domain. This avoids migrating `geekedoutbasketball.com` (still on Namecheap → Netlify/Railway) — **the live game's DNS is never touched.** Image URLs aren't player-visible, so a different asset domain is fine (cross-origin images work with CORS, set in Phase 1).

The previously-planned nameserver migration is **not needed** and has been dropped.

### Phase 1: Cloudflare setup
1. ✅ DONE — R2 bucket `gob-player-images` created.
2. ✅ DONE — custom domain `assets.geekedoutgames.com` connected; public read verified (200 + checksum match, 2026-06-30).
3. ✅ DONE (2026-06-30) — **Image Transformations** enabled on `geekedoutgames.com` zone (required subscribing to the free "Images & Stream — $0/mo" plan with **"Use my own storage"** = $0; images stay in R2). Verified live: a 4.6 MB master serves as AVIF at **3.4 KB / 7.3 KB / 16 KB** for width 128/256/512 (`format=auto` → AVIF/WebP/PNG fallback). URL pattern: `https://assets.geekedoutgames.com/cdn-cgi/image/width=<W>,format=auto,fit=cover/players/master/<uuid>.png`. Free tier = 5,000 unique transforms/mo.
4. ✅ N/A — not using `r2.dev`; custom domain only.
5. ✅ DONE (2026-06-30) — **CORS** via Response Header Transform Rule "CORS for player image assets" on geekedoutgames.com (all requests → `Set static: Access-Control-Allow-Origin: *`). Verified `access-control-allow-origin: *` on both transformed + direct image responses.

### Phase 2: Upload masters — ✅ DONE (2026-06-30)
- Script: `scripts/upload_player_images_to_r2.py` (boto3 → R2 S3 API; reads process
  credentials or external mode-`0600` `~/.config/gob/r2.env`).
- Idempotent: skips objects whose stored `sha256` metadata matches local → re-run = only new/changed images upload. **This is the runbook for adding new players.**
- Result: **98/98 uploaded** to `players/master/<uuid>.png`, 0 failed. Remote count == local count; 8 checksum spot-checks all matched.
- Manifest: `scripts/r2_upload_manifest.csv` (filename, asset_key, remote_url, file_size, sha256, status).
- Credentials: R2 Account API token "R2 Account Token", Object Read & Write, scoped to bucket only. (Optional: rotate token at project end — secret transited IDE sync.)

### Phase 3: DB backfill
1. Add `photo_asset_key` (+ `photo_version=1`) for every player with a matching image.
2. Don't remove/overwrite `photo`. Preserve IDs/filenames exactly.
3. Log mismatches. Summary: `players_scanned, with_remote, missing_remote, orphaned_remote, updated, skipped`.

### Phase 4: Centralized fallback-aware resolution — ✅ CODE DONE (2026-06-30)
- Added `API_CONFIG.getPlayerImageUrl(playerId, {size})` + `getGenericHeadshotUrl({size})` + `usePlayerImageRemote()` kill-switch in `FrontEnd/static/js/config/api-config.js`. Sizes: thumb 128 / card 256 / modal 512 / full. localhost → local static; staging/prod → remote; `window.PLAYER_IMAGE_REMOTE=true|false` overrides (rollback switch).
- Migrated surfaces (14 files, all parse clean): roster.js, player-detail.js, box-score.js, training-report.js, set-lineup.js (×2), shared/potg.js, phaser/gameScene.js (tooltip), phaser/bootGame.js (made-shot), utils/announcements.js (its `getPlayerImageUrl`), utils/foulOutPopup.js, utils/defenseMatchupsPopup.js, utils/gameCompletionPopup.js. Each keeps an onerror→generic fallback (generic stays deployed locally).
- **Phaser WebGL textures:** `setup/preloadPlayerHeadshots.js` now loads via resolver + `scene.load.crossOrigin='anonymous'`. **REQUIRES** a CORS response header on the asset zone (see ⬜ below) or on-court markers fall back to initials (graceful).
- ✅ DONE (2026-06-30) — CORS Transform Rule deployed; `access-control-allow-origin: *` confirmed on transformed + direct responses. WebGL headshot textures will load cross-origin.

### Phase 5: Env config
```text
PLAYER_IMAGE_ASSET_BASE_URL=https://assets.geekedoutgames.com
```
- Local dev defaults to local static; remote allowed via explicit env. Dev must never require Cloudflare access.

### Phase 6: Verification
- R2 variant loads when `photo_asset_key` exists (correct size/format).
- Local image loads when remote absent; missing → `generic_headshot.png`.
- Phaser preload works on remote URLs (no WebGL taint).
- Foul-out / POTG / set-lineup (active + fouled-out) correct image+name.
- Roster/modal no regression. Custom-domain prod URL works. Cache behavior OK after reload + after a simulated image regen (version bump busts cache).

### Phase 7: Repo cleanup (only after prod verified)
1. Keep `generic_headshot.png` + a tiny curated set locally for dev.
2. Remove bulk portraits from repo going forward.
3. Update docs → R2 canonical. Add "add new player image" script/runbook.

## Future Layered Image Pipeline
1. Generate base recruit portraits (generic white shirt).
2. Store canonical base once per player.
3. Store reusable uniform overlays once per team/frame type.
4. Backend sends player asset + assigned uniform asset.
5. Compose via Image Transformations / pre-rendered composites for high-traffic cases — avoids duplicate final files per player/team combo.

## Open Decisions
- Git history: keep vs rewrite (Phase 0).
- Named variant sizes to expose (proposed: thumb 128, card 256, modal 512).
- Whether high-traffic composites are pre-rendered vs transformed live.
- Exact `photo_version` scheme (incrementing int vs content hash).

## Safety Notes
- Keep `photo` field during initial migration.
- Don't delete local images until remote proven across all surfaces.
- All resolution stays fallback-aware and centralized.
- Filenames stay stable + UUID-based; treat generated/composite images as production assets, not source.
