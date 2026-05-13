const DEFAULT_VOLUME = 0.7;

function soundBasePath() {
  if (typeof window !== "undefined" && window.API_CONFIG?.buildStaticPath) {
    return window.API_CONFIG.buildStaticPath("/sounds/");
  }
  return "/sounds/";
}

export function playGameSfx(scene, filename, volume = DEFAULT_VOLUME) {
  if (!filename) return;
  try {
    const audio = new Audio(`${soundBasePath()}${encodeURIComponent(filename)}`);
    audio.volume = volume;
    if (scene) {
      if (!scene._activeSfx) scene._activeSfx = new Set();
      scene._activeSfx.add(audio);
      const release = () => scene._activeSfx?.delete(audio);
      audio.addEventListener("ended", release, { once: true });
      audio.addEventListener("error", release, { once: true });
      audio.play().catch(release);
      return;
    }
    audio.play().catch(() => {});
  } catch (_err) {
    // Audio is non-critical.
  }
}

function toNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function shotTypeForSfx(turnData) {
  return String(turnData?.sfx?.shot_type || turnData?.shot_type || "").toLowerCase();
}

export function playShotLaunchSfx(scene, turnData) {
  const shotType = shotTypeForSfx(turnData);
  if (!["outside", "attack", "inside"].includes(shotType)) return;

  const preDefense = toNumber(turnData?.sfx?.shot_score_pre_defense ?? turnData?.shot_score_pre_defense);
  if (preDefense == null) return;

  const prefix = shotType === "outside" ? "three" : "inside-shot";
  const tier = preDefense < 101 ? "weak" : preDefense > 210 ? "strong" : "medium";
  playGameSfx(scene, `${prefix}-${tier}.wav`);
}

export function playShotResultSfx(scene, turnData, result) {
  if (result === "MAKE") {
    const filename = Math.random() < 0.5 ? "swish.wav" : "swish-with-rim.wav";
    playGameSfx(scene, filename);
    return;
  }

  if (result !== "MISS") return;
  const preDefense = toNumber(turnData?.sfx?.shot_score_pre_defense ?? turnData?.shot_score_pre_defense);
  const defenseScore = toNumber(turnData?.sfx?.shot_defense_score_for_sfx ?? turnData?.shot_defense_score_for_sfx);
  const filename = preDefense != null && defenseScore != null && preDefense - defenseScore < -150
    ? "clank-bad.wav"
    : "clank.wav";
  playGameSfx(scene, filename);
}

export function buildHcoPassSfxContext(scene, passerId, receiverId) {
  const passerSprite = scene?.playerSprites?.[passerId];
  const receiverSprite = scene?.playerSprites?.[receiverId];
  const passerAttrs = passerSprite?.attributes || scene?.playerInfo?.[passerId]?.attributes || {};
  const receiverAttrs = receiverSprite?.attributes || scene?.playerInfo?.[receiverId]?.attributes || {};
  return {
    hcoPass: true,
    passerPS: toNumber(passerAttrs.PS),
    receiverIQ: toNumber(receiverAttrs.IQ),
    receiverCH: toNumber(receiverAttrs.CH),
  };
}

export function playHcoPassStartSfx(scene, sfxContext) {
  if (!sfxContext?.hcoPass) return;
  const ps = toNumber(sfxContext.passerPS);
  const tier = ps != null && ps > 75 ? "strong" : ps != null && ps < 25 ? "weak" : "medium";
  playGameSfx(scene, `pass-${tier}.wav`);
}

export function playHcoReceiveSfx(scene, sfxContext) {
  if (!sfxContext?.hcoPass) return;
  const iq = toNumber(sfxContext.receiverIQ);
  const ch = toNumber(sfxContext.receiverCH);
  const receiverScore = (iq ?? 0) + (ch ?? 0);
  const tier = receiverScore > 130 ? "strong" : receiverScore < 50 ? "weak" : "medium";
  playGameSfx(scene, `receive-${tier}.wav`);
}
