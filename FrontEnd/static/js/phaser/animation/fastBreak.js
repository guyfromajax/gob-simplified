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
export default runFastBreakSequenceWrapper;

