import { gridToPixels } from "../utils/gridToPixels.js";

export function createPhaserPlayer({ scene, player, teamInfo, position, Phaser }) {
  const { x, y } = player.startingCoords || { x: 50, y: 25 };
  const { x: px, y: py } = gridToPixels(x, y, scene.game.config.width, scene.game.config.height);
  
  const fill = teamInfo.primary_color || "#ffffff";
  const stroke = teamInfo.secondary_color || "#000000";
  const jerseyText = player.jersey || "";

  const circle = scene.add.circle(px, py, 20, Phaser.Display.Color.HexStringToColor(fill).color);
  circle.setStrokeStyle(3, Phaser.Display.Color.HexStringToColor(stroke).color);
  circle.setDepth(1);

  const label = scene.add.text(px, py, position, {
    font: "16px Arial",
    color: stroke,
    align: "center"
  });
  label.setOrigin(0.5);
  label.setDepth(2);

  const jersey = scene.add.text(px, py + 28, jerseyText, {
    font: "16px Arial",
    color: fill,
    align: "center"
  });
  jersey.setOrigin(0.5);
  jersey.setDepth(2);

  // Optionally group into a container
  const container = scene.add.container(0, 0, [circle, label, jersey]);
  container.setPosition(px, py);
  container.setDepth(1);

  return container;
}
  