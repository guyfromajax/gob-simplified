import { gridToPixels } from "../utils/gridToPixels.js";

export function createPhaserPlayer({ scene, player, teamInfo, position, Phaser }) {
  const { x, y } = player.startingCoords || { x: 50, y: 25 };
  const { x: px, y: py } = gridToPixels(x, y, scene.game.config.width, scene.game.config.height);

  const isHome = player.team === "home"; // ✅ Determine team side
  
  // console.log(`createPhaserPlayer for ${player.playerId ?? player.player_id}:`, {
  //   name: player.name,
  //   team: player.team,
  //   position: position,
  //   startingCoords: { x, y },
  //   pixelCoords: { px, py },
  //   isHome
  // });

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

  // ✅ Create player circle (20% larger than original: 20 → 24)
  const circle = scene.add.circle(0, 0, 24, fillColor);
  circle.setStrokeStyle(3, borderColor);
  circle.setDepth(1);

  // ✅ Position abbreviation — centered inside
  const label = scene.add.text(0, 0, position, {
    font: "bold 18px Arial",
    color: textColor,
    align: "center"
  });
  label.setOrigin(0.5);
  label.setDepth(2);

  // ✅ Jersey number — above if home, below if away
  // ✅ FIX: Handle jersey number 0 - use explicit check to preserve 0
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

  // ✅ Container to group all elements
  const container = scene.add.container(px, py, [circle, label, jersey]);
  container.setDepth(1);
  // const team_identifier = teamInfo.team_id;
  // container.team = team_identifier; // attach team to sprite container


  return container;
}
  