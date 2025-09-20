import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from "./courtConstants.js";

const COURT_BOUNDS = {
  minX: 4,
  maxX: 97,
  minY: 1,
  maxY: 50,
};

export function deriveOffenseContext(team) {
  const newOffenseTeam = team;
  const newOffenseBasket =
    newOffenseTeam === "home" ? HOME_RIM_COORDS : AWAY_RIM_COORDS;

  return { newOffenseTeam, newOffenseBasket };
}

export function computeFastBreakOutletTarget({
  rebounderGridX,
  rebounderGridY,
  newOffenseTeam,
  newOffenseBasket,
  randomDistance,
  randomYOffset,
  clamp,
  separationBuffer = 45,
}) {
  const distance = randomDistance();
  const direction = newOffenseBasket.x > rebounderGridX ? 1 : -1;

  let minX = COURT_BOUNDS.minX;
  let maxX = COURT_BOUNDS.maxX;

  if (newOffenseTeam === "home") {
    minX = Math.max(minX, newOffenseBasket.x - separationBuffer);
  } else {
    maxX = Math.min(maxX, newOffenseBasket.x + separationBuffer);
  }

  const targetX = clamp(
    rebounderGridX + direction * distance,
    minX,
    maxX
  );
  const targetY = clamp(
    rebounderGridY + randomYOffset(),
    COURT_BOUNDS.minY,
    COURT_BOUNDS.maxY
  );

  return {
    target: { x: targetX, y: targetY },
    direction,
    distance,
    bounds: { minX, maxX },
  };
}

export { COURT_BOUNDS };

