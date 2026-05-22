/**
 * User-pause gates for UESS playback (`animationPlayback.js`).
 * `gameScene` sets `scene.isPaused` and pauses Phaser tweens + `scene.time`;
 * step orchestration must not advance on wall-clock timers while paused.
 */

const POLL_MS = 50;

export function shouldFastForwardPlayback(scene) {
  return !!scene?.skipToEnd;
}

/** Block until the user resumes (no-op when skip-to-end is active). */
export async function waitWhileUserPaused(scene) {
  if (shouldFastForwardPlayback(scene)) return;
  while (scene?.isPaused) {
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    if (shouldFastForwardPlayback(scene)) return;
  }
}

/**
 * Wall-clock delay that only counts time while not user-paused.
 * Uses short slices so resume feels immediate.
 */
export async function waitMsRespectingPause(scene, ms) {
  if (shouldFastForwardPlayback(scene)) return;
  let remaining = Math.max(0, Math.floor(Number(ms) || 0));
  while (remaining > 0) {
    await waitWhileUserPaused(scene);
    if (shouldFastForwardPlayback(scene)) return;
    const slice = Math.min(POLL_MS, remaining);
    await new Promise((resolve) => setTimeout(resolve, slice));
    if (!scene?.isPaused) {
      remaining -= slice;
    }
  }
  await waitWhileUserPaused(scene);
}

/** Keep Phaser clock timers aligned with tween pause (delayedCall, etc.). */
export function syncSceneTimePaused(scene, isPaused) {
  if (!scene?.time) return;
  if (typeof scene.time.paused === "boolean") {
    scene.time.paused = !!isPaused;
  }
}
