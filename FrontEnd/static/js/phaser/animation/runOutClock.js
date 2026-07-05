/**
 * Run Out The Clock — Q4/OT terminal possession animation (EOQ_Perfection_Brief).
 * Step 1: all players drift to assigned spots at drift archetype rate (8 grid/game-sec).
 * Step 2: scoreboard runs to 0:00, airhorn, brief hold before quarter-end modal.
 */

import animationConfig from './animation_config.js';
import { gridToPixels } from '../utils/gridToPixels.js';
import { resolveOffenseTeamId } from '../utils/offenseTeamIdResolver.js';
import { signalQuarterEnded } from '../utils/quarterEndAirhorn.js';

const DRIFT_GRID_PER_GAME_SEC = 8;

function driftDurationMs(sprite, destXPx, destYPx, tickMs) {
  const width = sprite?.scene?.game?.config?.width || 1000;
  const height = sprite?.scene?.game?.config?.height || 1000;
  const sx = sprite.x;
  const sy = sprite.y;
  const gx0 = (sx / width) * 100;
  const gy0 = (sy / height) * 50;
  const gx1 = (destXPx / width) * 100;
  const gy1 = (destYPx / height) * 50;
  const dist = Math.hypot(gx1 - gx0, gy1 - gy0);
  const gameSec = dist / DRIFT_GRID_PER_GAME_SEC;
  return Math.max(400, Math.round(gameSec * tickMs));
}

export async function runOutClockSequence({ scene, playerSprites, turnData, onUpdate }) {
  if (scene?.skipToEnd || !turnData) return;

  const oDestinations = turnData.oDestinations || turnData.o_destinations || {};
  const dDestinations = turnData.dDestinations || turnData.d_destinations || {};
  const offenseTeamId = resolveOffenseTeamId({ scene, turnData, playerSprites });
  const width = scene.game.config.width;
  const height = scene.game.config.height;
  const tickMs = scene?.gameClock?.getState?.().tickMs || 350;
  const ease = animationConfig?.finalTurn?.alignment?.ease ?? 'Linear';

  const offenseByPos = {};
  const defenseByPos = {};
  for (const [id, sprite] of Object.entries(playerSprites || {})) {
    const info = scene.playerInfo?.[id];
    if (!info?.pos || !sprite) continue;
    if (String(sprite.team_id) === String(offenseTeamId)) {
      offenseByPos[info.pos] = sprite;
    } else {
      defenseByPos[info.pos] = sprite;
    }
  }

  const tweenTo = (sprite, coords) => {
    if (!sprite || !coords) return Promise.resolve();
    const { x, y } = gridToPixels(coords.x, coords.y, width, height);
    const duration = driftDurationMs(sprite, x, y, tickMs);
    if (scene.tweens) scene.tweens.killTweensOf(sprite);
    return new Promise((resolve) => {
      scene.tweens.add({
        targets: sprite,
        x,
        y,
        duration,
        ease,
        onComplete: resolve,
        onStop: resolve,
      });
    });
  };

  const step1 = [];
  for (const [pos, coords] of Object.entries(oDestinations)) {
    step1.push(tweenTo(offenseByPos[pos], coords));
  }
  for (const [pos, coords] of Object.entries(dDestinations)) {
    step1.push(tweenTo(defenseByPos[pos], coords));
  }
  await Promise.all(step1);

  const clockDrainMs = animationConfig?.finalTurn?.holdClockOutMs ?? 1800;
  const startSec = Number(turnData.time_elapsed ?? turnData.clock_start ?? 0);
  if (onUpdate && startSec > 0) {
    const steps = Math.max(1, Math.min(startSec, Math.floor(clockDrainMs / 80)));
    for (let i = 1; i <= steps; i += 1) {
      const remaining = Math.max(0, Math.round(startSec * (1 - i / steps)));
      const mins = Math.floor(remaining / 60);
      const secs = remaining % 60;
      onUpdate({
        clock: `${mins}:${String(secs).padStart(2, '0')}`,
        time_remaining: remaining,
      });
      await new Promise((r) => setTimeout(r, Math.round(clockDrainMs / steps)));
    }
  } else {
    await new Promise((r) => setTimeout(r, clockDrainMs));
  }

  if (onUpdate) {
    onUpdate({ clock: '0:00', time_remaining: 0, shot_clock_remaining: 0 });
  }

  signalQuarterEnded(
    scene,
    {
      ...turnData,
      clock_start: startSec || 1,
      clock_end: 0,
    },
    { phase: 'playbackComplete' },
  );

  const holdMs = animationConfig?.finalTurn?.holdFinalShotMs ?? 2000;
  await new Promise((r) => setTimeout(r, holdMs));
}
