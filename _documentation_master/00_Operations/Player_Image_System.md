# Player Image System

Player headshots are stored in **Cloudflare R2** and served, resized, and format-optimized on the fly through **Cloudflare Image Transformations** at `assets.geekedoutgames.com`. The frontend resolves every headshot through one helper (`API_CONFIG.getPlayerImageUrl`) — no view builds image paths inline. Images are **not** stored in the app repo (a small curated set + the generic fallback may remain locally for dev).

This is the operational reference. The original design rationale lives in [projects/image_migration.md](../projects/image_migration.md).

---

## Key facts

| Thing | Value |
|---|---|
| R2 bucket | `gob-player-images` (location ENAM) |
| Cloudflare account zone | `geekedoutgames.com` (hosts the asset subdomain) |
| Public asset domain | `assets.geekedoutgames.com` (CNAME `assets` → bucket) |
| S3 API endpoint | `https://21a46b928c6e8b378d9cd96097346e7d.r2.cloudflarestorage.com` |
| Object layout | `players/master/<player_id>.png` + `players/master/generic_headshot.png` |
| `<player_id>` | the player document `_id` (UUID). Filenames are exactly `<_id>.png` |
| Master format | full-res transparent PNG (~3–7 MB, 3530×3412) — source of truth |
| Images plan | "Images & Stream" **$0/mo**, "Use my own storage" — free tier, **5,000 unique transforms/month** |

> The game domain `geekedoutbasketball.com` (Netlify/Railway, on Namecheap) is **not** involved — assets are served cross-origin from `geekedoutgames.com`. This was deliberate: no live-domain DNS migration.

---

## URL patterns

| Use | URL |
|---|---|
| Original master | `https://assets.geekedoutgames.com/players/master/<id>.png` |
| Transformed (resized + AVIF/WebP) | `https://assets.geekedoutgames.com/cdn-cgi/image/width=<W>,format=auto/players/master/<id>.png` |

`format=auto` serves AVIF → WebP → PNG by browser support. A 4.6 MB master returns ~3–16 KB at width 128–512. **Always serve transformed URLs at runtime; never the raw master.**

---

## Frontend resolver — [FrontEnd/static/js/config/api-config.js](../../FrontEnd/static/js/config/api-config.js)

All surfaces call these. Do not build `/images/players/...` paths inline.

| Function | Returns |
|---|---|
| `API_CONFIG.getPlayerImageUrl(playerId, {size})` | transformed remote URL (or local static path in dev) |
| `API_CONFIG.getGenericHeadshotUrl({size})` | generic fallback URL |
| `API_CONFIG.usePlayerImageRemote()` | `true` on staging/prod, `false` on localhost (override below) |

**Named sizes** (`size` arg): `thumb`=128px, `card`=256px (default), `modal`=512px, `full`=untransformed master.

**Environment behavior:**
- `localhost` / `127.0.0.1` → **local** images (`/static/images/players/...`). Dev never requires Cloudflare.
- staging / prod → **remote** R2 + transforms.
- Override / kill-switch: set `window.PLAYER_IMAGE_REMOTE = true | false` (e.g. in the browser console) before image render. `true` forces remote even on localhost; `false` forces local.

**Fallback chain (per surface):** resolver URL → on `onerror`, the local **`generic_headshot.png`** (kept deployed) → placeholder/initials. Every `<img>` surface keeps an `onerror` handler.

**Surfaces wired (14):** `roster.js`, `player-detail.js`, `box-score.js` (POTG), `training-report.js`, `set-lineup.js` (×2), `js/shared/potg.js`, `js/phaser/gameScene.js` (tooltip), `js/phaser/bootGame.js` (made-shot), `js/phaser/utils/announcements.js`, `foulOutPopup.js`, `defenseMatchupsPopup.js`, `gameCompletionPopup.js`, and the WebGL texture preload `js/phaser/setup/preloadPlayerHeadshots.js`.

**Phaser/WebGL:** on-court headshot markers are WebGL textures (`preloadPlayerHeadshots.js` → `scene.load.image`). These require cross-origin loading (`scene.load.crossOrigin='anonymous'`, already set) **and** the CORS response header (below). If CORS is missing, markers gracefully fall back to initials.

---

## Cloudflare config (already deployed — reference only)

| Setting | Where | Value |
|---|---|---|
| Custom domain | R2 bucket → Settings → Custom Domains | `assets.geekedoutgames.com`, Access **Enabled** |
| Transformations | Media → Images → Transformations | zone `geekedoutgames.com` = **Enabled** (free plan, "Use my own storage") |
| CORS | `geekedoutgames.com` → Rules → Transform Rules → Response Header | Rule "CORS for player image assets": all requests → **Set static** `Access-Control-Allow-Origin: *` |

Verify CORS + delivery any time:
```bash
curl -sI -H "Origin: https://x" "https://assets.geekedoutgames.com/cdn-cgi/image/width=128,format=auto/players/master/generic_headshot.png" | grep -iE "http/|access-control|content-type"
# expect: 200, image/avif (or webp), access-control-allow-origin: *
```

---

## Runbook — add / update player images

New images never go in the repo. The upload script is **idempotent** (skips objects whose stored `sha256` matches), so re-running only uploads new/changed files.

1. Ensure credentials exist: `scripts/.r2.env` (gitignored) with `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET`. (See "Rotate token" if absent.)
2. Stage the files (filename **must** be `<player_id>.png`, i.e. the player `_id`):
   ```bash
   mkdir -p assets_staging/players        # gitignored
   # copy new <id>.png files into assets_staging/players/
   ```
3. Preview, then upload:
   ```bash
   ./venv/bin/python3 scripts/upload_player_images_to_r2.py --dry-run
   ./venv/bin/python3 scripts/upload_player_images_to_r2.py
   ```
   - Uploads `<source>/*.png` → `players/master/<filename>` with `Content-Type image/png` + `sha256` metadata.
   - Writes audit manifest [scripts/r2_upload_manifest.csv](../../scripts/r2_upload_manifest.csv).
   - `--source <dir>` overrides the default `assets_staging/players`.
4. **No code or DB change needed** — the frontend resolves by `player_id` automatically. Verify the new image in a browser (e.g. roster) or via the `curl` above.
5. Optional: empty `assets_staging/players/` afterward.

Boot dependency: `boto3` (`./venv/bin/python3 -m pip install boto3` if missing).

---

## Runbook — rotate the R2 upload token

The credentials are **never** committed and **must not** be pasted into chat, PRs, or this file. The current token (`gob-image-upload`) should be rotated periodically and was last issued during initial setup.

1. Cloudflare → **R2** → **Manage R2 API Tokens** → **Create Account API token**.
2. Permissions: **Object Read & Write**; Specify bucket: **`gob-player-images`** only; TTL as desired.
3. On the result screen, copy **Access Key ID** + **Secret Access Key** (shown once).
4. Update `scripts/.r2.env` locally with the new values (do not commit — it is gitignored).
5. Verify: `./venv/bin/python3 scripts/upload_player_images_to_r2.py --dry-run` (connects + lists).
6. Delete the **old** token in the dashboard.

---

## Runbook — disable / roll back remote images

| Scope | Action | Effect |
|---|---|---|
| One browser session | console: `window.PLAYER_IMAGE_REMOTE = false` then reload | uses local static images if deployed, else generic |
| App-wide | revert the resolver call sites / set the global in a loaded config script + deploy | falls back to local images |
| Asset outage | none required | each surface's `onerror` already degrades to local `generic_headshot.png` |

Note: if the local bulk images have been removed from the repo, a `false` kill-switch shows generic headshots (local files no longer exist) — it is a safety toggle, not a full restore. Keep `generic_headshot.png` deployed so fallbacks always resolve.

---

## Troubleshooting

| Symptom | Likely cause → fix |
|---|---|
| One player shows generic | master not uploaded → stage `<id>.png` + run upload script |
| On-court markers show initials | WebGL texture failed → confirm CORS header (curl above) + Transformations enabled |
| All headshots broken (staging/prod) | Transformations plan inactive, custom domain down, or CORS rule removed → check Cloudflare config table |
| Images huge / slow | a surface is serving `full`/raw master → use a sized `getPlayerImageUrl(id,{size})` |
| No images on localhost | expected — localhost uses local static; add the file to `FrontEnd/static/images/players/` or set `window.PLAYER_IMAGE_REMOTE = true` |
| `429`/transform errors | exceeded 5,000 free unique transforms/month → reduce distinct sizes or upgrade Images plan |

---

## Tunable Constants

| Constant | Location | Effect |
|---|---|---|
| `PLAYER_IMAGE_REMOTE_BASE` | api-config.js | asset domain base (`https://assets.geekedoutgames.com`) |
| `PLAYER_IMAGE_MASTER_PREFIX` | api-config.js | object key prefix (`players/master`) |
| `PLAYER_IMAGE_SIZES` | api-config.js | named width map: thumb 128 / card 256 / modal 512 / full null |
| `window.PLAYER_IMAGE_REMOTE` | runtime global | force remote (`true`) / local (`false`); unset = env default |
| `KEY_PREFIX` | upload script | R2 key prefix uploads write to (`players/master/`) |
| `DEFAULT_SOURCE` | upload script | default upload source dir (`assets_staging/players`) |
| `CACHE_CONTROL` | upload script | `Cache-Control` set on uploaded masters (`public, max-age=86400`) |

---

## Not in scope here

- DB has **no** `photo_asset_key` / image columns and **no** related env vars — keys are derived from `player_id`, so no backfill was needed.
- Future layered pipeline (base portrait + per-team uniform overlay compositing) is a **planned** design, documented in [projects/image_migration.md](../projects/image_migration.md), not yet built.
