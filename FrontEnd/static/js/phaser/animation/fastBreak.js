import { runFastBreakSequence } from "./turnAnimation.js";

export function runFastBreakSequenceWrapper(
  scene,
  { playerSprites, ballSprite, turnData }
) {
  return runFastBreakSequence({
    scene,
    playerSprites,
    ballSprite,
    turnData
  });
}

export { runFastBreakSequence } from "./turnAnimation.js";
export { HOME_RIM_COORDS, AWAY_RIM_COORDS, HOME_TOP_KEY, AWAY_TOP_KEY } from "./courtConstants.js";
export default runFastBreakSequenceWrapper;

