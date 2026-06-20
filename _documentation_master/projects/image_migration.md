# Player Image Migration Work Plan

## Objective

Move player image storage out of the Git repository and into a scalable long-term asset store before expanding from the current player image set to 1,500+ player portraits.

The target architecture is Cloudflare R2 object storage served through a Cloudflare-backed custom asset domain. The migration must be additive and fallback-safe: existing local `/static/images/players/...` paths should continue to work until remote delivery has been verified across every player-image surface.

## Current State

- Existing player images live in `FrontEnd/static/images/players/`.
- Images are PNG files named by player UUID, for example `{player_uuid}.png`.
- Existing DB/photo convention uses `/static/images/players/{player_uuid}.png`.
- Production frontend paths may normalize Flask-style `/static/...` paths to `/images/...`.
- The folder includes `generic_headshot.png` as a fallback image.
- High-quality reference images are large transparent PNGs, roughly 4-6 MB each at `3530 x 3412`.

This does not scale to 1,500+ full-resolution images because it would add multiple GB to the repository and Git history.

## Target Architecture

### Storage

Use Cloudflare R2 as canonical storage for shared player image assets.

Recommended bucket:

```text
gob-player-images
```

Recommended public custom domain:

```text
assets.geekedoutbasketball.com
```

Recommended object path pattern:

```text
players/{player_uuid}.png
players/generic_headshot.png
```

Future layered asset paths may include:

```text
players/base/{player_uuid}.png
players/final/{player_uuid}.png
uniforms/{team_id}/{frame_type}.png
```

### Data Model

Add remote-compatible image fields without removing the current `photo` field immediately.

Candidate fields:

```text
photo_asset_key: "players/{player_uuid}.png"
photo_url: "https://assets.geekedoutbasketball.com/players/{player_uuid}.png"
```

Preferred long-term model:

- Store `photo_asset_key` as the stable canonical reference.
- Derive full URLs from configured asset base URL.
- Keep direct `photo_url` only if the app needs explicit external URLs in API payloads.

### Runtime Resolution

Image consumers should resolve player images in this order:

1. Remote asset URL or asset key, if available.
2. Existing `player.photo`, if available.
3. Local/static fallback path using player ID.
4. `generic_headshot.png`.

This keeps the rollout safe and avoids breaking local development.

## Migration Phases

### Phase 1: Cloudflare Setup

1. Create the R2 bucket.
2. Connect a custom Cloudflare domain or subdomain.
3. Confirm public read access through the custom domain.
4. Disable or avoid production use of the `r2.dev` development URL.
5. Set cache behavior appropriate for versioned image assets.

Recommended cache posture:

- Long-lived cache for immutable/versioned image URLs.
- Conservative cache or versioned filenames for assets that may be replaced.
- Avoid relying on root bucket listing; object URLs should be explicit.

### Phase 2: Upload Existing Assets

1. Upload all files from:

```text
FrontEnd/static/images/players/
```

2. Preserve UUID filenames.
3. Upload `generic_headshot.png`.
4. Generate an upload manifest with:

```text
player_uuid
local_path
asset_key
remote_url
file_size
checksum
upload_status
```

5. Verify uploaded object count matches local source count.
6. Spot-check representative images in browser:

- Xenon Fletcher: `8487cb3b-887b-472a-90d9-f46caa572d46.png`
- Emery Landraneau: `1ac0782e-e1b3-4cb6-9462-b1ff032ed9ed.png`
- `generic_headshot.png`

### Phase 3: Database Backfill

1. Add `photo_asset_key` for every player with a matching image.
2. Do not remove or overwrite the existing `photo` field during the first pass.
3. Preserve existing player IDs and filenames exactly.
4. Log all missing image/player mismatches.
5. Produce a backfill summary:

```text
players_scanned
players_with_matching_remote_image
players_missing_remote_image
orphaned_remote_images
updated_count
skipped_count
```

### Phase 4: Fallback-Aware URL Resolution

Update shared image URL helper logic so all player-image surfaces can use remote assets without each view implementing its own path rules.

Resolution should be centralized where possible.

Known surfaces to audit:

- Roster views
- Set lineup screen
- Player modal/account views
- Phaser player headshot preloading
- Announcements
- Secondary announcements
- Foul-out popup
- Player of the Game popup
- Community Highlights
- Any stat/player cards that render a headshot

Rules:

- Prefer remote asset key/URL.
- Preserve local static fallback.
- Preserve `generic_headshot.png` fallback.
- Avoid duplicating URL normalization logic across unrelated frontend files.

### Phase 5: Environment Configuration

Add environment-level asset base configuration.

Recommended config:

```text
PLAYER_IMAGE_ASSET_BASE_URL=https://assets.geekedoutbasketball.com
```

Local development options:

- Continue using local `/static/images/players/...`.
- Allow remote assets in local dev through explicit env config.

Do not make local development require Cloudflare access.

### Phase 6: Verification

Run manual and automated checks across all known player-image surfaces.

Minimum verification checklist:

- Player image loads from R2 when `photo_asset_key` exists.
- Existing local image still loads when remote field is absent.
- Missing player image falls back to `generic_headshot.png`.
- Phaser preload does not break on remote URLs.
- Foul-out popup shows correct player image and name.
- POTG popup shows correct image.
- Set lineup screen displays active and fouled-out players correctly.
- Roster/player modal images do not regress.
- Production URL format works through the custom domain.
- Browser cache behavior is acceptable after reload.

### Phase 7: Repo Cleanup

Only after production verification:

1. Keep a small curated reference set in the repo.
2. Keep `generic_headshot.png` locally if needed for fallback/dev.
3. Remove bulk player portraits from the repo.
4. Update documentation to point to R2 as canonical storage.
5. Add scripts/docs for adding new generated player images.

Do not delete the local image set until all production image surfaces are verified against remote delivery.

## Future Layered Image Pipeline

The long-term recruit/team workflow should use layered assets:

1. Generate base recruit portraits with generic white shirts.
2. Store canonical base images once per player.
3. Store reusable uniform overlays once per team and frame type.
4. Backend sends the player image asset and assigned team/uniform asset.
5. Frontend renders the correct visual composition, or a backend/offline pipeline pre-renders high-traffic composites.

This avoids creating duplicate final image files for every possible player/team assignment.

## Open Decisions

- Exact R2 bucket name.
- Exact custom asset domain.
- Whether to store only `photo_asset_key`, only `photo_url`, or both.
- Whether first rollout serves original PNGs only or also pre-generated WebP variants.
- Whether final player/team uniform composites are rendered in frontend or pre-rendered/cached by an asset pipeline.
- Which image sizes should be generated for runtime performance.

## Implementation Safety Notes

- Do not remove existing `photo` fields during the initial migration.
- Do not delete local repo images until remote delivery is proven.
- Keep all URL resolution fallback-aware.
- Keep player image filenames stable and UUID-based.
- Treat generated images and final uniform composites as production assets, not source-code files.
