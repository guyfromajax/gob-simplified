/**
 * End-of-quarter airhorn — fires once per turn when the game clock contract
 * reaches 0:00 (clock_end === 0). Wired from AnimationRouter clock tween.
 */

export function playEndOfQuarterAirhorn(scene, turnData = {}) {
  if (typeof window === 'undefined' || scene?.skipToEnd) {
    return false;
  }

  const clockEnd = Number(turnData?.clock_end ?? turnData?.clockEnd);
  const clockStart = Number(turnData?.clock_start ?? turnData?.clockStart);
  if (!Number.isFinite(clockEnd) || clockEnd !== 0) {
    return false;
  }
  if (!Number.isFinite(clockStart) || clockStart <= 0) {
    return false;
  }

  const turnKey = String(
    turnData?.index ?? turnData?.turnIndex ?? scene?.currentTurn ?? ''
  );
  if (!turnKey) {
    return false;
  }

  if (!scene._endOfQuarterAirhornTurnKeys) {
    scene._endOfQuarterAirhornTurnKeys = new Set();
  }
  if (scene._endOfQuarterAirhornTurnKeys.has(turnKey)) {
    return false;
  }
  scene._endOfQuarterAirhornTurnKeys.add(turnKey);

  try {
    const staticPath = (window.API_CONFIG && typeof window.API_CONFIG.getStaticPath === 'function')
      ? window.API_CONFIG.getStaticPath()
      : '/static';
    const airhorn = new Audio(`${staticPath}/sounds/airhorn-lowervol.wav`);
    airhorn.volume = 0.7;
    airhorn.currentTime = 0;
    airhorn.play().catch(() => {});
  } catch (e) {
    return false;
  }

  return true;
}
