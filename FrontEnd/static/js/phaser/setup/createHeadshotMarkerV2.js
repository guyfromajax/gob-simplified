import { gridToPixels } from "../utils/gridToPixels.js";
import { headshotTextureKey } from "./preloadPlayerHeadshots.js";
import { drawStaminaArc } from "./staminaRing.js";

// Height in inches → headshot radius. Linear 0.75 px/inch around the 6'4" v1
// baseline (r=33), clamped 25.5 (≤ 5'6") to 39 (≥ 7'0"). Default 28.5 (≈ 5'10")
// when height is unknown — small enough to fit HS rosters without making the
// shipped v1 visual jump on day one of v2.
function headRadiusForHeight(heightInches) {
  if (heightInches == null) return 28.5;
  return Math.max(25.5, Math.min(39, 30 + (heightInches - 72) * 0.75));
}

function getInitialsFromFullName(fullName) {
  if (!fullName || typeof fullName !== "string") return "?";
  const tokens = fullName.trim().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return "?";
  if (tokens.length === 1) return tokens[0][0].toUpperCase();
  return (tokens[0][0] + tokens[tokens.length - 1][0]).toUpperCase();
}

export function createHeadshotMarkerV2({ scene, player, teamInfo, position, Phaser }) {
  const { x, y } = player.startingCoords || { x: 50, y: 25 };
  const { x: px, y: py } = gridToPixels(x, y, scene.game.config.width, scene.game.config.height);

  const playerId = player.playerId ?? player.player_id ?? player._id;
  const stamina = player.NG ?? player.attributes?.NG;
  const heightIn = player.height; // integer inches; undefined → default in headRadiusForHeight
  const isHome = player.team === "home";

  const headR = headRadiusForHeight(heightIn);
  const primary = Phaser.Display.Color.HexStringToColor(teamInfo.primary_color).color;
  const secondary = teamInfo.secondary_color;
  // Home chip above, away chip below (preserves the v1 placement rule).
  const chipY = isHome ? -(headR + 24) : +(headR + 24);
  // Chip styling per team: home = primary fill + secondary text;
  // away = white fill + primary text (inverse scheme).
  const chipFillColor = isHome ? primary : 0xffffff;
  const chipTextColor = isHome ? secondary : teamInfo.primary_color;
  // Backdrop fill (inside-mask disc + outer vignette) per team:
  // home = team primary, away = soft white. Tints the area behind transparent
  // photo pixels and the vignette halo so home/away read at a glance.
  const bgColor = isHome ? primary : 0xf5f5f5;

  // 1. Vignette (3 stacked discs in team-backdrop color — softens edge into court)
  const vig3 = scene.add.circle(0, 0, headR + 15, bgColor, 0.18);
  const vig2 = scene.add.circle(0, 0, headR + 9, bgColor, 0.30);
  const vig1 = scene.add.circle(0, 0, headR + 5, bgColor, 0.42);

  // 2. Floor shadow (proportional to headR — bigger heads cast bigger shadows).
  //    Kept black for the grounding-to-court effect regardless of team.
  const shadow = scene.add.ellipse(0, headR + 6, Math.round(headR * 1.36), 12, 0x000000, 0.45);

  // 2a. Inside-mask backdrop disc — sits behind the photo at the same radius.
  //     Shows through transparent photo pixels (above head, around shoulders),
  //     giving the marker a strong team-color tint. Alpha 0.90 lets a small
  //     amount of court bleed through so it doesn't look pasted on.
  const insideFill = scene.add.circle(0, 0, headR, bgColor, 0.90);

  // 3. Scene-level mask Graphics. Mirrors v1 exactly:
  //    - fillStyle BEFORE fillCircle (else the stencil writes empty and the photo vanishes)
  //    - circle at LOCAL (0, 0); Graphics translated to (px, py) via .x/.y
  //    - setAlpha(0), NOT setVisible(false), so the stencil write still fires
  //    - synced to container.x/y each frame; destroyed on container destroy
  const maskGraphics = scene.add.graphics();
  maskGraphics.fillStyle(0xffffff, 1);
  maskGraphics.fillCircle(0, 0, headR);
  maskGraphics.x = px;
  maskGraphics.y = py;
  maskGraphics.setAlpha(0);
  const mask = maskGraphics.createGeometryMask();

  // 4. Headshot — two-tier fallback (per-player photo → initials tile).
  //    v2 skips the generic-headshot fallback that other UIs (announcements,
  //    playcall center, etc.) and the v1 marker still use; missing photos
  //    surface as the team-aware initials tile so each marker stays uniquely
  //    identifiable on the court.
  //    The initials path uses a colored circle which is already circular,
  //    so it does not need a mask.
  const photoKey = playerId ? headshotTextureKey(playerId) : null;
  const hasPhotoTexture = !!photoKey && scene.textures && scene.textures.exists(photoKey);

  let photoChild;
  if (hasPhotoTexture) {
    const photo = scene.add.image(0, 0, photoKey);
    photo.setDisplaySize(headR * 2, headR * 2);
    photo.setOrigin(0.5, 0.55);
    photo.setMask(mask);
    photoChild = photo;
  } else {
    // Initials tile — shared color rule across sprites, announcements, and
    // playcall center:
    //   Home → tile = team primary, text = team secondary
    //   Away → tile = white,        text = team primary
    // Note: on the v2 sprite, the tile sits in front of the team-color backdrop
    // disc (home backdrop = primary, away = soft white). Home's tile and
    // backdrop are both primary — they blend by design; the secondary text
    // remains visible. Away's white tile sits over the soft-white backdrop
    // for a clean white field that the primary-color initials read against.
    const tileColor = isHome ? primary : 0xffffff;
    const tileTextColor = isHome ? secondary : teamInfo.primary_color;
    const tile = scene.add.circle(0, 0, headR, tileColor);
    const tileTx = scene.add.text(0, 0, getInitialsFromFullName(player.name), {
      font: '20px "Bebas Neue"',
      color: tileTextColor,
      align: "center",
    });
    tileTx.setOrigin(0.5);
    photoChild = scene.add.container(0, 0, [tile, tileTx]);
  }

  // 5. Stamina ring — Graphics object, keep reference for live redraw
  const staminaGfx = scene.add.graphics();
  drawStaminaArc(staminaGfx, headR, stamina);

  // 6. Inner separator (thin dark hairline around the photo edge for legibility
  //    against the light court; the team-color border has been removed in v2).
  const inner = scene.add.circle(0, 0, headR - 1);
  inner.setStrokeStyle(1, 0x000000, 0.6);

  // 8. Position chip — rounded rect via Graphics. Home above / away below;
  //    home uses primary fill + secondary text, away inverts to white fill + primary text.
  const chipGfx = scene.add.graphics();
  chipGfx.fillStyle(chipFillColor, 1);
  chipGfx.fillRoundedRect(-21, chipY - 13, 42, 27, 5);
  const chipTx = scene.add.text(0, chipY, position, {
    font: '20px "Bebas Neue"',
    color: chipTextColor,
    align: "center",
  });
  chipTx.setOrigin(0.5);

  // Z-order: outer vignette → shadow → inside backdrop fill → photo (masked) →
  // stamina ring → inner hairline → position chip.
  const children = [vig3, vig2, vig1, shadow, insideFill, photoChild, staminaGfx, inner, chipGfx, chipTx];

  const container = scene.add.container(px, py, children);
  container.setSize(96, 168);
  container.setDepth(1);

  // Stash refs for live stamina updates + cleanup
  container.staminaGfx = staminaGfx;
  container.headR = headR;

  // Sync the scene-level mask to the container each frame; cleanup on destroy.
  const syncMask = () => {
    maskGraphics.x = container.x;
    maskGraphics.y = container.y;
  };
  scene.events.on("update", syncMask);
  container.once("destroy", () => {
    scene.events.off("update", syncMask);
    if (maskGraphics.scene) maskGraphics.destroy();
  });

  return container;
}
