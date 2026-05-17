import { gridToPixels } from "../utils/gridToPixels.js";
import { USE_HEADSHOT_MARKER, USE_MARKER_V2_FEATURES } from "./markerConfig.js";
import { headshotTextureKey, HEADSHOT_FALLBACK_KEY } from "./preloadPlayerHeadshots.js";
import { createHeadshotMarkerV2 } from "./createHeadshotMarkerV2.js";

export function createPhaserPlayer(args) {
  if (!USE_HEADSHOT_MARKER) return createLegacyMarker(args);
  return USE_MARKER_V2_FEATURES
    ? createHeadshotMarkerV2(args)
    : createHeadshotMarker(args);
}

function createLegacyMarker({ scene, player, teamInfo, position, Phaser }) {
  const { x, y } = player.startingCoords || { x: 50, y: 25 };
  const { x: px, y: py } = gridToPixels(x, y, scene.game.config.width, scene.game.config.height);

  const isHome = player.team === "home";

  const fillColor = isHome
    ? Phaser.Display.Color.HexStringToColor(teamInfo.primary_color).color
    : 0xffffff;

  const borderColor = isHome
    ? Phaser.Display.Color.HexStringToColor(teamInfo.secondary_color).color
    : Phaser.Display.Color.HexStringToColor(teamInfo.primary_color).color;

  const textColor = isHome
    ? teamInfo.secondary_color
    : teamInfo.primary_color;

  const circle = scene.add.circle(0, 0, 24, fillColor);
  circle.setStrokeStyle(3, borderColor);
  circle.setDepth(1);

  const label = scene.add.text(0, 0, position, {
    font: "bold 18px Arial",
    color: textColor,
    align: "center"
  });
  label.setOrigin(0.5);
  label.setDepth(2);

  const jerseyOffset = isHome ? -32 : 32;
  const jerseyValue = (typeof player.jersey === 'number')
    ? String(player.jersey)
    : (player.jersey !== undefined && player.jersey !== null && player.jersey !== '')
      ? String(player.jersey)
      : '';
  const jersey = scene.add.text(0, jerseyOffset, jerseyValue, {
    font: "bold 15px Arial",
    color: textColor,
    align: "center"
  });
  jersey.setOrigin(0.5);
  jersey.setDepth(2);

  const container = scene.add.container(px, py, [circle, label, jersey]);
  container.setDepth(1);

  return container;
}

function getPlayerInitials(name) {
  if (!name || typeof name !== "string") return "?";
  const tokens = name.trim().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return "?";
  if (tokens.length === 1) return tokens[0][0].toUpperCase();
  const first = tokens[0][0] || "";
  const last = tokens[tokens.length - 1][0] || "";
  const initials = `${first}${last}`.toUpperCase();
  return initials || "?";
}

function createHeadshotMarker({ scene, player, teamInfo, position, Phaser }) {
  const debug = (typeof window !== "undefined") && !!window.DEBUG_HEADSHOT_MARKER;
  const { x, y } = player.startingCoords || { x: 50, y: 25 };
  const { x: px, y: py } = gridToPixels(x, y, scene.game.config.width, scene.game.config.height);

  const isHome = player.team === "home";
  const primary = Phaser.Display.Color.HexStringToColor(teamInfo.primary_color).color;

  const playerId = player.playerId ?? player.player_id ?? player._id;
  const photoKey = playerId ? headshotTextureKey(playerId) : null;
  const hasPhotoTexture = !!photoKey && scene.textures && scene.textures.exists(photoKey);
  const hasFallbackTexture = scene.textures && scene.textures.exists(HEADSHOT_FALLBACK_KEY);

  if (debug) {
    console.log("[headshot]", playerId, {
      photoKey,
      hasPhotoTexture,
      hasFallbackTexture,
      containerOrigin: { px, py },
      playerName: player.name,
    });
  }

  const children = [];

  const shadow = scene.add.ellipse(0, 39, 45, 12, 0x000000, 0.45);
  children.push(shadow);

  // Phaser 3.60 quirk: a GeometryMask source added as a Container child does
  // not reliably inherit the container's world transform during stencil
  // rendering — the stencil ends up at scene (0,0) so the clipped image
  // becomes invisible at the player's actual position. Workaround: keep the
  // mask Graphics at scene level and sync its position to the container each
  // frame via scene 'update' event. Cleanup on container destroy.
  const maskGraphics = scene.add.graphics();
  maskGraphics.fillStyle(0xffffff, 1);
  maskGraphics.fillCircle(0, 0, 33);
  maskGraphics.x = px;
  maskGraphics.y = py;
  // alpha=0 (not setVisible(false)) so the stencil write still fires.
  maskGraphics.setAlpha(0);
  const mask = maskGraphics.createGeometryMask();

  let photoChild;
  let usedPath;
  if (hasPhotoTexture || hasFallbackTexture) {
    const textureKey = hasPhotoTexture ? photoKey : HEADSHOT_FALLBACK_KEY;
    usedPath = hasPhotoTexture ? "photo" : "fallback_texture";
    const photo = scene.add.image(0, 0, textureKey);
    photo.setDisplaySize(66, 66);
    photo.setOrigin(0.5, 0.55);
    photo.setMask(mask);
    photoChild = photo;
  } else {
    usedPath = "initials_tile";
    const tile = scene.add.rectangle(0, 0, 66, 66, primary);
    tile.setOrigin(0.5, 0.5);
    tile.setMask(mask);
    const initials = scene.add.text(0, 0, getPlayerInitials(player.name), {
      font: '700 20px "Bebas Neue"',
      color: teamInfo.secondary_color,
      align: "center"
    });
    initials.setOrigin(0.5, 0.5);
    initials.setMask(mask);
    children.push(tile, initials);
  }
  if (photoChild) children.push(photoChild);

  const borderRing = scene.add.circle(0, 0, 33);
  borderRing.setStrokeStyle(3, primary);
  children.push(borderRing);

  const innerSeparator = scene.add.circle(0, 0, 30);
  innerSeparator.setStrokeStyle(1, 0x000000, 0.6);
  children.push(innerSeparator);

  const posY = isHome ? -57 : 57;
  const chipBg = scene.add.rectangle(0, posY, 42, 27, primary);
  chipBg.setOrigin(0.5);
  children.push(chipBg);

  const chipText = scene.add.text(0, posY, position, {
    font: '700 20px "Bebas Neue"',
    color: teamInfo.secondary_color,
    align: "center"
  });
  chipText.setOrigin(0.5);
  children.push(chipText);

  const container = scene.add.container(px, py, children);
  container.setSize(84, 150);
  container.setDepth(1);

  // Keep the scene-level mask aligned with the container each frame.
  const syncMask = () => {
    maskGraphics.x = container.x;
    maskGraphics.y = container.y;
  };
  scene.events.on("update", syncMask);
  container.once("destroy", () => {
    scene.events.off("update", syncMask);
    if (maskGraphics.scene) maskGraphics.destroy();
  });

  if (debug) {
    const wt = maskGraphics.getWorldTransformMatrix();
    console.log("[headshot]", playerId, "post-container", {
      usedPath,
      containerPos: { x: container.x, y: container.y },
      maskPos: { x: maskGraphics.x, y: maskGraphics.y },
      maskWorld: { tx: wt.tx, ty: wt.ty },
      photoLocal: photoChild ? { x: photoChild.x, y: photoChild.y } : null,
      childCount: container.list.length,
    });
  }

  return container;
}
