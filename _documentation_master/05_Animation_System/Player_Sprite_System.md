# Player Sprite System

**Status:** ✅ **PRODUCTION** — v1 headshot marker shipped May 2026. v2 enhancements (team-color backdrop + vignette, stamina ring, height-linked radius, chip-color inversion per team, team-color border dropped) shipped behind `USE_MARKER_V2_FEATURES`.

The player sprite system renders the 10 on-court players as headshot-centered markers and keeps the ball anchored to whichever marker currently has possession. The system is reversible via two feature flags: `USE_HEADSHOT_MARKER` (v1 vs legacy) and `USE_MARKER_V2_FEATURES` (v2 vs v1).

## Quick Facts

| Property | Value |
| --- | --- |
| Marker container origin | `gridToPixels(player.startingCoords)` — i.e., the center of the player's head |
| Visual diameter (headshot circle) | 66px (radius 33) |
| Border ring | Retired in v2 — only a thin black hairline (1px, radius `headR - 1`) sits inside the headshot edge for legibility. v1 still uses a 3px team-primary stroke. |
| Container bounding box | v1: 84×150 · v2: 96×168 (wider/taller for the vignette + stamina ring extents) |
| Position chip offset | y = ±57 from head center (home above, away below) |
| Ball attach point | `(sprite.x, sprite.y)` — center of the headshot (offset infrastructure preserved but currently `{0, 0}`) |
| Feature flags | `USE_HEADSHOT_MARKER` (legacy ↔ v1+) and `USE_MARKER_V2_FEATURES` (v1 ↔ v2) in `markerConfig.js` |

## Architecture

```
gameScene.preload()
    ↓ (court bg + ball texture)
gameScene.create()
    ↓
preloadPlayerHeadshots(scene, allPlayers)   ← loads 10 player + 1 fallback texture
    ↓
loadPhaserPlayers(scene, allPlayers, Phaser)
    ↓ (per player)
createPhaserPlayer({ scene, player, teamInfo, position, Phaser })
    ↓
   !USE_HEADSHOT_MARKER → createLegacyMarker(...)
   USE_MARKER_V2_FEATURES → createHeadshotMarkerV2(...)
   else                   → createHeadshotMarker(...)   ← v1
```

**Phaser dependency injection convention:** the `Phaser` namespace is passed *through the args* to `createPhaserPlayer` (and forwarded to v1/v2 builders). It is NOT in scope at module level in any of the setup/ files, so module-private helpers that need `Phaser.Display.Color.HexStringToColor` or similar must take `Phaser` as a parameter. Don't reference `Phaser` from a free function — it'll be `undefined`. Pure-math helpers should avoid Phaser entirely (inline `Math.PI / 180` for `Phaser.Math.DegToRad`, etc.).

## Files

| File | Purpose |
| --- | --- |
| `FrontEnd/static/js/phaser/setup/markerConfig.js` | Feature flags (`USE_HEADSHOT_MARKER`, `USE_MARKER_V2_FEATURES`), ball-attach offset constant, `playerBallPos(sprite, extra)` helper |
| `FrontEnd/static/js/phaser/setup/preloadPlayerHeadshots.js` | Phaser texture preload + URL normalization (strips `/static/` on netlify) |
| `FrontEnd/static/js/phaser/setup/createPhaserPlayer.js` | Dispatcher → v2 / v1 / legacy. Holds `createHeadshotMarker` (v1) and `createLegacyMarker` as module-private functions |
| `FrontEnd/static/js/phaser/setup/createHeadshotMarkerV2.js` | v2 builder: team-color backdrop fill + vignette + stamina ring + height-linked radius + chip-color inversion per team (team-color border ring dropped vs v1) |
| `FrontEnd/static/js/phaser/setup/staminaRing.js` | `drawStaminaArc(gfx, headR, stamina)` helper. Extracted from the marker builder so `syncPlayerSpriteAttributes.js` can import without a circular dependency. Pure JS, no Phaser dependency. |
| `FrontEnd/static/js/phaser/setup/loadPhaserPlayers.js` | Iterates roster, calls `createPhaserPlayer`, attaches metadata (`team_id`, `team`, `playerId`, `jersey`, `name`) to each container |
| `FrontEnd/static/js/phaser/utils/syncPlayerSpriteAttributes.js` | Per-turn NG sync; v2 stamina ring redraws here when `container.staminaGfx` is present |

## Marker Composition (Headshot Mode)

Children of the v1 container, in z-order (back → front):

1. **Shadow** — `ellipse(0, 39, 45, 12, 0x000000, 0.45)` — soft drop shadow below the head
2. **Headshot photo** — `image(0, 0, headshot_${playerId})` displayed at 66×66, origin `(0.5, 0.55)` (face anchored slightly above center), clipped to a 33-radius circle via geometry mask
3. **Border ring** — `circle(0, 0, 33)` with 3px stroke in team primary color (v1 only — v2 retires this)
4. **Inner separator** — `circle(0, 0, 30)` with 1px black 60%-alpha stroke (keeps light photos legible against light court)
5. **Position chip bg** — `rectangle(0, ±57, 42, 27)` in team primary
6. **Position chip text** — Bebas Neue 700 20px in team secondary color (`PG`, `SG`, `SF`, `PF`, `C`)

Home team chip sits above the head (y = -57); away team chip sits below (y = +57).

### v2 children (z-order, back → front)

When `USE_MARKER_V2_FEATURES = true`, the container holds these children instead of the v1 list above:

1. **Vignette (outer halo)** — 3 stacked `circle` discs at `r = headR + 15 / 9 / 5`, in `bgColor` (team primary for home, soft white `0xf5f5f5` for away), alphas `0.18 / 0.30 / 0.42`
2. **Floor shadow** — `ellipse(0, headR + 6, headR × 1.36, 12, 0x000000, 0.45)` — always black regardless of team
3. **Inside-mask backdrop disc** — `circle(0, 0, headR, bgColor, 0.90)` — shows through transparent pixels of the photo (above head, around shoulders) to tint the marker in the team color
4. **Headshot photo** — `image(0, 0, headshot_${playerId})` at `headR × 2`, masked to a `headR`-radius circle via the scene-level mask Graphics
5. **Stamina ring** — `Graphics` arc just outside the headshot edge (see "Stamina ring" section below)
6. **Inner separator** — `circle(0, 0, headR - 1)` with 1px black 60%-alpha stroke (legibility hairline)
7. **Position chip bg** — `Graphics.fillRoundedRect(-21, chipY - 13, 42, 27, 5)`, fill per team rule (see "Chip placement and styling" below)
8. **Position chip text** — Bebas Neue 20px, text color per team rule

For v2's design rationale (why the backdrop, why team-color vignette, etc.), see "v2 Additions" below.

### Symmetric team colors (v1)

Unlike the legacy marker (which inverted fill/border by home/away), the v1 headshot marker uses **the team's own primary color** for both home AND away border rings. The headshot itself carries team identity, so the symmetric border reads more clearly. In v2 the team border is dropped entirely — the home/away inverted color scheme on the position chip now carries the team distinction (see "Chip placement and styling" below).

## v2 Additions

v2 layers four enhancements on top of the v1 marker and **drops the team-primary border ring** (replaced by a thin black hairline). All v2 changes gate on `USE_MARKER_V2_FEATURES`; flipping to `false` returns to v1 exactly (border ring restored, no backdrop tint, no vignette, no stamina ring, fixed radius).

| Feature | Source field | If missing |
| --- | --- | --- |
| Team-color backdrop fill | `player.team` (home/away) + `teamInfo.primary_color` | Always rendered (per-team color) |
| Vignette (team-color halo) | `player.team` + `teamInfo.primary_color` | Always rendered |
| Stamina ring | `player.NG ?? player.attributes?.NG` | Ring omitted (no track, no fill) |
| Height-linked radius | `player.height` (integer inches) | Default `r = 28.5` (≈ 5'10") |
| **Removed:** team-color border ring | — | v2 replaces it with a 1px black hairline inside the headshot edge |

### Team-color backdrop + vignette

| Team | `bgColor` | Inside-mask disc alpha | Outer vignette alphas (3 stacked) |
| --- | --- | --- | --- |
| Home | `teamInfo.primary_color` (parsed via `Phaser.Display.Color.HexStringToColor`) | 0.90 | 0.42 / 0.30 / 0.18 (inner → outer) |
| Away | `0xf5f5f5` (soft white, not pure) | 0.90 | 0.42 / 0.30 / 0.18 |

The inside-mask disc (`r = headR`, alpha 0.90) sits between the shadow and the photo. It shows through transparent pixels of the headshot photo (above the head, around shoulders) so the marker reads as the team color at a glance. The 3-disc vignette outside the headshot uses the same color at lower alphas to soften the marker's edge into the court.

The floor shadow ellipse stays black regardless of team — its job is to ground the marker to the court, not to carry team identity.

### Height → radius

Linear 0.75 px/inch around the 6'4" v1 baseline (r=33), clamped 25.5 (≤ 5'6") to 39 (≥ 7'0"). Default 28.5 (≈ 5'10") when height is unknown — close to HS roster average so missing-data players don't visually jump when the backend supplies the field later.

Field source: `player.height` (integer inches). See `Game_Init_System.md` → "Player-level data ingestion" for the load path (DB → `Player.__init__` → `summarize_game_state` → simData).

### Stamina ring

- 2px stroke at `r = headR + 9` (just outside the border)
- 340° arc with a 20° gap at 12 o'clock
- Color tiers: green (>0.89) → yellow (≥0.80) → orange (≥0.70) → red (<0.70)
- Nonlinear fill curve: each color band occupies 25% of the visual arc regardless of underlying NG distribution
- Live redraw: `syncSpriteAttributesFromPlayerEnergy` calls `drawStaminaArc` on every animated turn, but only for containers that have `staminaGfx` (i.e., v2 markers). v1/legacy markers skip cleanly.
- **Low-stamina pulse is intentionally NOT wired.** A future "low-stamina pulse" setting toggle will add `ensureStaminaPulse` to `staminaRing.js`.

### Chip placement and styling

v2 preserves v1's home-above / away-below chip placement rule but inverts the chip color scheme per team:

| Team | Placement | Chip fill | Chip text |
| --- | --- | --- | --- |
| Home | above head (`y = -(headR + 24)`) | team primary color | team secondary color |
| Away | below head (`y = +(headR + 24)`) | white (`0xffffff`) | team primary color |

There is no team-color border ring in v2 — only a 1px black hairline inside the headshot edge for legibility. The chip's inverted fill is the sole home/away color cue.

## Headshot Loading

### URL resolution

`preloadPlayerHeadshots` calls `getPlayerImageUrl(player.photo, playerId)` from `utils/announcements.js` to construct the URL (reuses the same helper that DOM-based UIs like Playcall Center and Announcements use, so the browser cache dedupes requests).

The returned URL is then normalized for the current environment:

- **Localhost (Flask):** ensures `/static/` prefix → `/static/images/players/{id}.png`
- **Netlify (prod):** strips `/static/` → `/images/players/{id}.png`

This normalization is critical — without it, prod players 404 because `/static/` is a Flask-only convention. Browser-based UIs hide the failure via `<img>.onerror → generic_headshot.png`; Phaser textures don't have that fallback.

### Texture keys

- Per-player: `headshot_${playerId}` (e.g., `headshot_26e15606-2eca-4616-840a-d14b87174395`)
- Fallback: `headshot_fallback` (loads `generic_headshot.png` once)

### Fallback chain

1. If `headshot_${playerId}` exists in the texture manager → use it
2. Else if `headshot_fallback` exists → render the generic headshot (clipped to the same circle)
3. Else (rare — both URLs failed) → render an initials tile with the player's first + last initials (e.g. `JD`) in Bebas Neue 20px

**Initials tile contrast (v2):** the tile's fill must contrast with the new team-color backdrop disc that sits behind it:

| Team | Backdrop disc | Initials tile fill | Initials text color |
| --- | --- | --- | --- |
| Home | team primary | team **secondary** | team primary |
| Away | white `0xf5f5f5` | team primary | team secondary |

The fallback decision happens per player at marker creation time, so individual photo failures don't break the whole court.

### Diagnostic logging

`preloadPlayerHeadshots` always logs a one-line summary on completion:

```
[headshots] preload complete — loaded 11/11, failed 0
```

For deeper diagnostics during development, set `window.DEBUG_HEADSHOT_MARKER = true` and hard-reload. This enables per-player logs showing texture existence, container position, mask world position, and the render path chosen (`photo`, `fallback_texture`, or `initials_tile`).

## The Mask: Why It's Scene-Level

The headshot is clipped to a circle via Phaser's `GeometryMask`. **The mask Graphics is added at scene level, not as a Container child** — and there's a specific reason:

Phaser 3.60 has a quirk where a GeometryMask source added as a Container child doesn't reliably inherit the container's world transform during stencil rendering. The stencil writes at scene (0, 0) instead of the container's position, so the masked image becomes invisible at the player's actual on-court location.

### Workaround — the literal pattern

Copy this exactly. Two non-obvious gotchas to preserve:

```js
// 1. scene.add.graphics() — NOT scene.make.graphics({ add: false }).
//    The mask Graphics must be on the scene's display list so its transform
//    matrix gets updated each frame.
const maskGraphics = scene.add.graphics();

// 2. fillStyle() BEFORE fillCircle(). Without fillStyle, the Graphics has zero
//    filled pixels, the stencil writes empty, and the masked content vanishes.
maskGraphics.fillStyle(0xffffff, 1);

// 3. fillCircle at LOCAL (0, 0), then translate the Graphics via .x/.y to (px, py).
//    Drawing the circle at (px, py) AND translating to (px, py) produces world
//    coords of (2*px, 2*py) — mask ends up in the wrong place.
maskGraphics.fillCircle(0, 0, headR);
maskGraphics.x = px;
maskGraphics.y = py;

// 4. setAlpha(0), NOT setVisible(false). Some Phaser render paths short-circuit
//    on visible:false and skip the stencil write.
maskGraphics.setAlpha(0);

const mask = maskGraphics.createGeometryMask();
photo.setMask(mask);

// 5. Sync the Graphics to the container each frame, clean up on destroy.
const syncMask = () => { maskGraphics.x = container.x; maskGraphics.y = container.y; };
scene.events.on('update', syncMask);
container.once('destroy', () => {
  scene.events.off('update', syncMask);
  if (maskGraphics.scene) maskGraphics.destroy();
});
```

This is reliable but adds ~10 per-frame property assignments (one per on-court marker). Negligible perf impact.

### Why not `setVisible(false)`?

Some Phaser code paths short-circuit on `visible === false`. The mask system's stencil write went through these paths and ended up writing an empty stencil, which clipped the masked content to nothing. `setAlpha(0)` keeps the Graphics on the render path (stencil writes still fire) but renders nothing visible.

## Ball Anchoring

The ball anchors to the player's **headshot center** (= sprite center = container origin = `gridToPixels(player.coords)`). This matches pre-headshot behavior and keeps dribbles, passes, and shot releases visually centered on the marker.

### `BALL_ATTACH_OFFSET`

```js
export const BALL_ATTACH_OFFSET = { x: 0, y: 0 };
```

Currently zero in both modes. The composition wiring (the `playerBallPos` helper and all call sites) is preserved so a future setting can re-introduce a hip anchor (or any other offset) by editing this single constant — no need to revisit every animation file.

When a non-zero offset is introduced later, every animation system that anchors the ball to a player will already compose this offset on top of any per-call offset (like the `y - 10` pass lift), so behavior remains consistent across dribbles, passes, shots, rebounds, etc.

### `playerBallPos(sprite, extra)`

Helper in `markerConfig.js`:

```js
export function playerBallPos(sprite, extra) {
  return {
    x: sprite.x + BALL_ATTACH_OFFSET.x + (extra?.x ?? 0),
    y: sprite.y + BALL_ATTACH_OFFSET.y + (extra?.y ?? 0),
  };
}
```

Used wherever a ball position is anchored to a player sprite — `ballSprite.setPosition`, tween targets `{ x, y }`, `runPass` start/end coords, `BallController.attachToPlayer` default offset, etc.

### Files touched by the offset

Anywhere the ball is anchored to a player sprite — direct `setPosition` calls and tween targets:

- `BallController.js`, `BallControllerAdapter.js`
- `ballManager.js`, `ballTween.js`, `ballAnimationSimple.js`
- `animateStep.js`, `animateGameTurns.js`, `turnAnimation.js`
- `PassAnimationSystem.js`, `ShotAnimationSystem.js`, `FreeThrowAnimationSystem.js`, `HCOAnimationSystem.js`
- `countdownAnimation.js`, `passDetection.js`, `animationPlayback.js`
- `possession/PossessionRunner.js`

Court-spot positions (rebound bounce spots, inbound spots, opening tip ball coords, the rim endpoint of a shot arc) deliberately do **not** receive the offset — they're anchored to court geometry, not a player.

## Reversibility

Flip `USE_HEADSHOT_MARKER` to `false` in `markerConfig.js` and:

- `createPhaserPlayer` dispatches to `createLegacyMarker` (the verbatim pre-headshot code — circle + position text + jersey above/below)
- Ball behavior is unchanged in either mode because `BALL_ATTACH_OFFSET` is currently `{0, 0}` in both modes

No other code path needs to change. The flag is the single point of control.

## Player Data Available to the Marker

These are the fields confirmed on the `player` object passed to `createPhaserPlayer({ scene, player, teamInfo, position, Phaser })`. Use this list before assuming a field exists — backend simData does NOT carry the same schema as the roster API.

| Field | Type | Notes |
| --- | --- | --- |
| `playerId` / `player_id` / `_id` | string | UUID. Use `player.playerId ?? player.player_id ?? player._id` |
| `name` | string | Full name (e.g., `"James Davies"`). Last name is **not** a separate field — parse from `name` if needed |
| `jersey` / `jerseyNumber` / `jersey_number` | number/string | Jersey number. Zero is valid; check with explicit `=== 0` |
| `team` | `"home"` \| `"away"` | Team side |
| `team_id` | string | Team identifier (e.g., `"XAVIEN"`) |
| `pos` | string | Position abbreviation (`"PG"`, `"SG"`, `"SF"`, `"PF"`, `"C"`) |
| `photo` | string \| null | Image URL (often `/static/images/players/{id}.png`). May need normalization via `preloadPlayerHeadshots`'s helper |
| `height` | number \| null | **Integer inches.** Wired through `summarize_game_state` and the `/api/game` projection (May 2026). Used by v2 height-linked radius. See `Game_Init_System.md` → "Player-level data ingestion" for the full DB → simData load path. |
| `startingCoords` | `{ x, y }` | Grid coords (0–100 × 0–50) |
| `attributes.NG` | number 0–1 | **Stamina / energy.** Lives at `player.NG` or `player.attributes.NG`. Updated per-turn via `syncSpriteAttributesFromPlayerEnergy`. |
| `attributes.AG` | number | Athleticism (used for movement speed) |
| `attributes.anchor_AG` | number | Pre-fatigue AG anchor (engine: `AG ≈ anchor_AG * NG`) |

Fields that do **NOT** exist on simData players (despite living elsewhere in the backend):

- `rating` / `overall` — player rating. Backend has per-position ratings (`player.position_ratings`) but no composite rating on the simData projection.
- `heightInches` — **wrong field name.** Use `player.height` (integer inches; see row above).
- `lastName` — only `name` (full) is provided. Parse the last whitespace-split token if needed.
- `photoKey` — texture keys are derived via `headshotTextureKey(playerId)` from `setup/preloadPlayerHeadshots.js`, not stored on the player object.

If a marker feature requires a field not on this list, propagate it through `summarize_game_state` and the `/api/game` `players_with_energy` projections — see the recipe in `Game_Init_System.md`.

## Live Updates

### Stamina / energy (per-turn)

Backend ships `turn.player_energy` as part of each animated turn. Frontend applies it via:

```js
import { syncSpriteAttributesFromPlayerEnergy } from './utils/syncPlayerSpriteAttributes.js';
// playerSprites: { [playerId]: container }
// playerEnergy:  { [playerId]: { NG: number } }
syncSpriteAttributesFromPlayerEnergy(playerSprites, turn.player_energy);
```

This currently lives in two places:

- `animation/turnPreparation.js:~123` (preferred — called via `prepareTurnForAnimation`)
- `gameScene.js:~1981`

Any future "live stamina visualization" on the marker should hook into the same `syncSpriteAttributesFromPlayerEnergy` call site rather than introducing a separate subscriber.

### Coordinate updates (per animation step)

Player containers' `x`/`y` are tweened by the animation systems (turnAnimation, animateStep, PassAnimationSystem, ShotAnimationSystem, etc.). The scene-level mask sync runs in `scene.events.on('update', ...)` and tracks these tweens automatically — no per-system hook needed.

## Tests

Two test files import `BALL_ATTACH_OFFSET` and assert positions relative to it (so both modes pass):

- `animation/tests/BallController.test.js` — ball attach to player at default offset
- `animation/tests/PassAnimationSystem.test.js` — uses `expect.objectContaining` for tween targets, so it's mode-agnostic

If you add new tests that assert exact ball coordinates, import `BALL_ATTACH_OFFSET` and compose: `expect(...).toHaveBeenCalledWith(sprite.x + BALL_ATTACH_OFFSET.x, sprite.y + BALL_ATTACH_OFFSET.y)`.

## Future Work

A future iteration will expose user-facing sprite display settings, allowing players to opt between:

- Headshot circle (current default)
- Legacy circle with position text + jersey number above/below

When the user picks the no-headshot option, the legacy inverted color scheme (home: primary fill + secondary border; away: white fill + primary border) returns. The symmetric team-primary border described above is specific to the headshot mode.
