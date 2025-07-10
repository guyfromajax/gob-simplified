import { gridToPixels } from "../utils/gridToPixels.js";

export function createPhaserPlayer({ scene, player, teamInfo, position, Phaser }) {
  const { x, y } = player.startingCoords || { x: 50, y: 25 };
  const { x: px, y: py } = gridToPixels(x, y, scene.game.config.width, scene.game.config.height);

  const fill = teamInfo.primary_color || "#ffffff";
  const stroke = teamInfo.secondary_color || "#000000";
  const jerseyText = player.jersey || "";

  // Create circle
  const circle = scene.add.circle(0, 0, 20, Phaser.Display.Color.HexStringToColor(fill).color);
  circle.setStrokeStyle(3, Phaser.Display.Color.HexStringToColor(stroke).color);
  circle.setDepth(1);

  // Position abbreviation (e.g. "PG") — centered inside circle
  const label = scene.add.text(0, 0, position, {
    font: "bold 16px Arial",
    color: stroke,
    align: "center"
  });
  label.setOrigin(0.5);
  label.setDepth(2);

  // Jersey number — above or below depending on team
  const isHome = player.team === "home";
  const jerseyOffset = isHome ? -30 : 28;
  const jersey = scene.add.text(0, jerseyOffset, jerseyText, {
    font: "bold 16px Arial",
    color: fill,
    align: "center"
  });
  jersey.setOrigin(0.5);
  jersey.setDepth(2);

  // Group all into a container
  const container = scene.add.container(px, py, [circle, label, jersey]);
  container.setDepth(1);

  return container;
}

  