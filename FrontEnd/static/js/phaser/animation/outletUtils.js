import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from "./courtConstants.js";
import { CLAMP_BOUNDS } from "./courtClamp.js";

const COURT_BOUNDS = {
  minX: CLAMP_BOUNDS.minX,
  maxX: CLAMP_BOUNDS.maxX,
  minY: CLAMP_BOUNDS.minY,
  maxY: CLAMP_BOUNDS.maxY,
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

  const rimX = newOffenseBasket.x;
  let minX = COURT_BOUNDS.minX;
  let maxX = COURT_BOUNDS.maxX;

  if (newOffenseTeam === "home") {
    minX = Math.max(
      minX,
      rimX - separationBuffer,
      Math.min(rimX, rebounderGridX)
    );
    maxX = Math.min(maxX, rimX + separationBuffer);
  } else {
    minX = Math.max(minX, rimX - separationBuffer);
    maxX = Math.min(
      maxX,
      rimX + separationBuffer,
      Math.max(rimX, rebounderGridX)
    );
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

