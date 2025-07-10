import { gridToPixels } from "../utils/gridToPixels.js";

export function createPhaserPlayer({ scene, player, teamInfo, position, Phaser }) {
  const { x, y } = player.startingCoords || { x: 50, y: 25 };
  const { x: px, y: py } = gridToPixels(x, y, scene.game.config.width, scene.game.config.height);

  const fill = teamInfo.primary_color || "#ffffff";
  const stroke = teamInfo.secondary_color || "#000000";
  const jerseyText = player.jersey || "";

  // Position children relative to container origin (0, 0)
  const circle = scene.add.circle(0, 0, 20, Phaser.Display.Color.HexStringToColor(fill).color);
  circle.setStrokeStyle(3, Phaser.Display.Color.HexStringToColor(stroke).color);
  circle.setDepth(1);

  const label = scene.add.text(px, py, position, {
    font: "bold 14px Arial",
    color: stroke,
    align: "center"
  });
  label.setOrigin(0.5);
  label.setDepth(2);
  

  const jerseyOffset = teamInfo.isHome ? -28 : 28;

  const jersey = scene.add.text(px, py + (player.team === "home" ? -30 : 28), jerseyText, {
    font: "bold 16px Arial",
    color: fill,
    align: "center"
  });
  jersey.setOrigin(0.5);
  jersey.setDepth(2);
  

  // Add to container with origin (0,0) at center of circle
  const container = scene.add.container(px, py, [circle, label, jersey]);
  container.setDepth(1);

  return container;
}

  