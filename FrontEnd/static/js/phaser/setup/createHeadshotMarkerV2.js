import { gridToPixels } from "../utils/gridToPixels.js";
import { headshotTextureKey, HEADSHOT_FALLBACK_KEY } from "./preloadPlayerHeadshots.js";
import { drawStaminaArc } from "./staminaRing.js";

// Height in inches → headshot radius. Linear 0.75 px/inch around the 6'4" v1
// baseline (r=33), clamped 25.5 (≤ 5'6") to 39 (≥ 7'0"). Default 28.5 (≈ 5'10")
// when height is unknown — small enough to fit HS rosters without making the
// shipped v1 visual jump on day one of v2.
function headRadiusForHeight(heightInches) {
  if (heightInches == null) return 28.5;
  return Math.max(25.5, Math.min(39, 30 + (heightInches - 72) * 0.75));
}

// Rating → border thickness/alpha. Falls back to the default 3px primary band
// when rating is missing or in the normal range, so missing-data players stay
// visually identical to v1 until the backend supplies the field.
function ratingBorderTreatment(rating, primaryHex, Phaser) {
  const primary = Phaser.Display.Color.HexStringToColor(primaryHex).color;
  if (rating == null) return { width: 3, color: primary, alpha: 1 };
  if (rating < 20) return { width: 3, color: 0x6b7280, alpha: 0.85 }; // desaturated
  if (rating >= 80) return { width: 5, color: primary, alpha: 1 };
  if (rating >= 65) return { width: 4, color: primary, alpha: 1 };
  if (rating >= 40) return { width: 3, color: primary, alpha: 1 };
  return { width: 3, color: primary, alpha: 0.6 };
}

function getLastNameFromFullName(fullName) {
  if (!fullName) return null;
  const tokens = String(fullName).trim().split(/\s+/);
  return tokens.length ? tokens[tokens.length - 1].toUpperCase() : null;
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
  const rating = player.rating;          // may be undefined — degrades to default tier
  const heightIn = player.heightInches;   // may be undefined — degrades to default radius
  const lastName = getLastNameFromFullName(player.name);

  const headR = headRadiusForHeight(heightIn);
  const tier = ratingBorderTreatment(rating, teamInfo.primary_color, Phaser);
  const primary = Phaser.Display.Color.HexStringToColor(teamInfo.primary_color).color;
  const secondary = teamInfo.secondary_color;
  const chipY = -(headR + 24);
  const nameY = +(headR + 24);

  // 1. Vignette (3 stacked dark discs)
  const vig3 = scene.add.circle(0, 0, headR + 15, 0x000000, 0.18);
  const vig2 = scene.add.circle(0, 0, headR + 9, 0x000000, 0.30);
  const vig1 = scene.add.circle(0, 0, headR + 5, 0x000000, 0.42);

  // 2. Floor shadow (proportional to headR — bigger heads cast bigger shadows)
  const shadow = scene.add.ellipse(0, headR + 6, Math.round(headR * 1.36), 12, 0x000000, 0.45);

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

  // 4. Headshot — three-tier fallback (photo → generic → initials tile).
  //    The initials path uses a colored circle which is already circular,
  //    so it does not need a mask.
  const photoKey = playerId ? headshotTextureKey(playerId) : null;
  const hasPhotoTexture = !!photoKey && scene.textures && scene.textures.exists(photoKey);
  const hasFallbackTexture = scene.textures && scene.textures.exists(HEADSHOT_FALLBACK_KEY);

  let photoChild;
  if (hasPhotoTexture || hasFallbackTexture) {
    const textureKey = hasPhotoTexture ? photoKey : HEADSHOT_FALLBACK_KEY;
    const photo = scene.add.image(0, 0, textureKey);
    photo.setDisplaySize(headR * 2, headR * 2);
    photo.setOrigin(0.5, 0.55);
    photo.setMask(mask);
    photoChild = photo;
  } else {
    const tile = scene.add.circle(0, 0, headR, primary);
    const tileTx = scene.add.text(0, 0, getInitialsFromFullName(player.name), {
      font: '20px "Bebas Neue"',
      color: secondary,
      align: "center",
    });
    tileTx.setOrigin(0.5);
    photoChild = scene.add.container(0, 0, [tile, tileTx]);
  }

  // 5. Stamina ring — Graphics object, keep reference for live redraw
  const staminaGfx = scene.add.graphics();
  drawStaminaArc(staminaGfx, headR, stamina);

  // 6. Border ring (rating-tiered)
  const border = scene.add.circle(0, 0, headR);
  border.setStrokeStyle(tier.width, tier.color, tier.alpha);

  // 7. Inner separator
  const inner = scene.add.circle(0, 0, headR - 3);
  inner.setStrokeStyle(1, 0x000000, 0.6);

  // 8. Position chip — rounded rect via Graphics; chip is ALWAYS above the head
  //    in v2 (the v1 home/away above/below rule is retired — team identity is
  //    carried by the chip + name strip colors).
  const chipGfx = scene.add.graphics();
  chipGfx.fillStyle(primary, 1);
  chipGfx.fillRoundedRect(-21, chipY - 13, 42, 27, 5);
  const chipTx = scene.add.text(0, chipY, position, {
    font: '20px "Bebas Neue"',
    color: secondary,
    align: "center",
  });
  chipTx.setOrigin(0.5);

  // 9. Name strip — only if a last name can be resolved
  let nameGfx = null;
  let nameTx = null;
  if (lastName) {
    let display = lastName;
    if (display.length > 8) display = display.substring(0, 7) + ".";
    nameGfx = scene.add.graphics();
    nameGfx.fillStyle(primary, 1);
    nameGfx.fillRoundedRect(-36, nameY - 10, 72, 21, 4);
    nameTx = scene.add.text(0, nameY, display, {
      font: '15px "Bebas Neue"',
      color: secondary,
      align: "center",
    });
    nameTx.setOrigin(0.5);
  }

  const children = [vig3, vig2, vig1, shadow, photoChild, staminaGfx, border, inner, chipGfx, chipTx];
  if (nameGfx) children.push(nameGfx, nameTx);

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
