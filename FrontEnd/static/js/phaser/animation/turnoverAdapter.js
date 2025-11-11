import runFastBreakSequence from "./fastBreak.js";
import { runInboundSetup } from "./turnAnimation.js";
import { States, safeTransition } from "../state/gameStateMachine.js";
import {
  clearCurrentOwner,
  clearPendingOwner,
  cancelBallTween,
  getCurrentOwner,
  getPendingOwner,
} from "../ball/ballController.js";
import { triggerTurnoverEffect } from "./negativeActionEffects.js";

/**
 * Map backend TURNOVER events to appropriate animation sequences.
 * Live-ball turnovers trigger a fast break; dead-ball turnovers reset to inbound.
 */
export async function handleTurnover(scene, { playerSprites, ballSprite, turnData, onUpdate }) {
  if (!scene || scene.skipToEnd) return;

  safeTransition(
    scene.stateMachine,
    States.Turnover,
    {
      stepIndex: 0,
      currentOwnerId: getCurrentOwner(scene),
      pendingOwnerId: getPendingOwner(scene),
    },
    ["stepIndex"]
  );

  cancelBallTween(scene, ballSprite);
  clearCurrentOwner(scene);
  clearPendingOwner(scene);
  scene.passInFlight = false;
  scene.tweens?.killAll?.();
  scene.time?.removeAllEvents?.();

  const liveBall =
    turnData?.live_ball === true ||
    turnData?.turnover_type === "STEAL" ||
    turnData?.result_type === "STEAL";
  
  // Trigger turnover effect on player who lost the ball
  const victimId = turnData?.victim_id || turnData?.ball_handler_id || turnData?.ball_handler?.player_id;
  if (victimId) {
    triggerTurnoverEffect(scene, victimId);
  }

  const offenseId = turnData?.possession_team_id;
  if (offenseId != null) {
    scene.offenseTeamId = offenseId;
    scene.events?.emit?.("possessionChange", { offenseTeamId: offenseId });
  }

  if (liveBall) {
    await runFastBreakSequence(scene, { playerSprites, ballSprite, turnData, onUpdate });
    return;
  }

  let newOffenseSide = "home";
  if (offenseId != null) {
    const sample = Object.values(playerSprites).find(
      (s) => String(s.team_id) === String(offenseId)
    );
    if (sample) newOffenseSide = sample.team === "away" ? "away" : "home";
  }

  await runInboundSetup({ scene, ballSprite, playerSprites, newOffenseSide });
}
