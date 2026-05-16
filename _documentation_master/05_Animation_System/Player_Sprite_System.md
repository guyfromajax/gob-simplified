# Player Sprite System

**Status:** ✅ **PRODUCTION** — headshot marker shipped May 2026.

The player sprite system renders the 10 on-court players as headshot-centered markers and keeps the ball anchored to whichever marker currently has possession. The system is reversible via a single feature flag.

## Quick Facts

| Property | Value |
| --- | --- |
| Marker container origin | `gridToPixels(player.startingCoords)` — i.e., the center of the player's head |
| Visual diameter (headshot circle) | 66px (radius 33) |
| Border ring outer diameter | ~70px (radius 33 + 3px team-primary stroke) |
| Container bounding box | 84×150 (width × height, includes chip + shadow) |
| Position chip offset | y = ±57 from head center (home above, away below) |
| Ball attach point | `(sprite.x, sprite.y)` — center of the headshot (offset infrastructure preserved but currently `{0, 0}`) |
| Feature flag | `USE_HEADSHOT_MARKER` in `markerConfig.js` |

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
USE_HEADSHOT_MARKER ? createHeadshotMarker(...) : createLegacyMarker(...)
```

## Files

| File | Purpose |
| --- | --- |
| `FrontEnd/static/js/phaser/setup/markerConfig.js` | Feature flag, ball-attach offset constant, `playerBallPos(sprite, extra)` helper |
| `FrontEnd/static/js/phaser/setup/preloadPlayerHeadshots.js` | Phaser texture preload + URL normalization (strips `/static/` on netlify) |
| `FrontEnd/static/js/phaser/setup/createPhaserPlayer.js` | Dispatcher → `createHeadshotMarker` (new) or `createLegacyMarker` (old, preserved verbatim) |
| `FrontEnd/static/js/phaser/setup/loadPhaserPlayers.js` | Iterates roster, calls `createPhaserPlayer`, attaches metadata (`team_id`, `team`, `playerId`, `jersey`, `name`) to each container |

## Marker Composition (Headshot Mode)

Children of the container, in z-order (back → front):

1. **Shadow** — `ellipse(0, 39, 45, 12, 0x000000, 0.45)` — soft drop shadow below the head
2. **Headshot photo** — `image(0, 0, headshot_${playerId})` displayed at 66×66, origin `(0.5, 0.55)` (face anchored slightly above center), clipped to a 33-radius circle via geometry mask
3. **Border ring** — `circle(0, 0, 33)` with 3px stroke in team primary color
4. **Inner separator** — `circle(0, 0, 30)` with 1px black 60%-alpha stroke (keeps light photos legible against light court)
5. **Position chip bg** — `rectangle(0, ±57, 42, 27)` in team primary
6. **Position chip text** — Bebas Neue 700 20px in team secondary color (`PG`, `SG`, `SF`, `PF`, `C`)

Home team chip sits above the head (y = -57); away team chip sits below (y = +57).

### Symmetric team colors

Unlike the legacy marker (which inverted fill/border by home/away), the headshot marker uses **the team's own primary color** for both home AND away. The headshot itself carries team identity, so the symmetric border reads more clearly.

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
3. Else (rare — both URLs failed) → render a solid team-primary tile with the player's initials (`firstInitial + lastInitial`, e.g. `JD`) in Bebas Neue 20px

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

### Workaround

1. Create the mask `Graphics` at scene level via `scene.add.graphics()` (not `scene.make.graphics({ add: false })`)
2. Position it initially at `(px, py)`
3. Hide visually with `setAlpha(0)` — **not** `setVisible(false)`, which short-circuits the stencil write
4. Register a `scene.events.on('update', syncMask)` handler that updates the mask's `x/y` to match the container every frame
5. On `container.once('destroy', ...)`, remove the listener and destroy the mask Graphics to prevent leaks

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
- `BALL_ATTACH_OFFSET` becomes `{0, 0}`, so every ball animation behaves byte-identically to develop pre-May-2026

No other code path needs to change. The flag is the single point of control.

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
