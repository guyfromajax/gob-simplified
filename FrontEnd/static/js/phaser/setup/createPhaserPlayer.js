import { gridToPixels } from "../utils/gridToPixels.js";

export function createPhaserPlayer({ scene, player, teamInfo, position, Phaser }) {
  const { x, y } = player.startingCoords || { x: 50, y: 25 };
  const { x: px, y: py } = gridToPixels(x, y, scene.game.config.width, scene.game.config.height);

  const isHome = player.team === "home"; // ✅ Determine team side

  // ✅ Style logic per GDD
  const fillColor = isHome
    ? Phaser.Display.Color.HexStringToColor(teamInfo.primary_color).color
    : 0xffffff;

  const borderColor = isHome
    ? Phaser.Display.Color.HexStringToColor(teamInfo.secondary_color).color
    : Phaser.Display.Color.HexStringToColor(teamInfo.primary_color).color;

  const textColor = isHome
    ? teamInfo.secondary_color
    : teamInfo.primary_color;

  // ✅ Create player circle
  const circle = scene.add.circle(0, 0, 20, fillColor);
  circle.setStrokeStyle(3, borderColor);
  circle.setDepth(1);

  // ✅ Position abbreviation — centered inside
  const label = scene.add.text(0, 0, position, {
    font: "bold 16px Arial",
    color: textColor,
    align: "center"
  });
  label.setOrigin(0.5);
  label.setDepth(2);

  // ✅ Jersey number — above if home, below if away
  const jerseyOffset = isHome ? -28 : 28;
  const jersey = scene.add.text(0, jerseyOffset, player.jersey || "", {
    font: "bold 14px Arial",
    color: textColor,
    align: "center"
  });
  jersey.setOrigin(0.5);
  jersey.setDepth(2);

  // ✅ Container to group all elements
  const container = scene.add.container(px, py, [circle, label, jersey]);
  container.setDepth(1);
  // const team_identifier = teamInfo.team_id;
  // container.team = team_identifier; // attach team to sprite container


  return container;
}
  