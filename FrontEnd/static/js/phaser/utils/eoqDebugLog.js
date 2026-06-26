/**
 * Frontend step tracing for Final Shot and FLSS.
 * Filter browser console with: EOQ-TRACE
 *
 * On by default. Disable with: window.GOB_EOQ_TRACE = false
 */

import { pixelsToGrid } from './gridToPixels.js';

export function isEoqTraceEnabled(_scene) {
  if (typeof window !== 'undefined' && window.GOB_EOQ_TRACE === false) {
    return false;
  }
  return true;
}

function roundCoord(n) {
  return Math.round(Number(n) * 100) / 100;
}

export function snapshotClockFromTurn(turnData, scene) {
  const gs = scene?.gameClock?.getState?.() || {};
  return {
    quarter: turnData?.quarter ?? scene?.simData?.quarter ?? null,
    time_remaining:
      turnData?.time_remaining
      ?? turnData?.clock_end
      ?? gs.remainingSec
      ?? null,
    shot_clock_remaining: turnData?.shot_clock_remaining ?? null,
    clock_start: turnData?.clock_start ?? turnData?.clockStart ?? null,
    clock_end: turnData?.clock_end ?? turnData?.clockEnd ?? null,
    clock_display: turnData?.clock ?? gs.display ?? null,
  };
}

export function snapshotPlayersFromSprites(scene, playerSprites) {
  const width = scene?.game?.config?.width;
  const height = scene?.game?.config?.height;
  const offense = {};
  const defense = {};
  const offenseTeamId = scene?.offenseTeamId ?? scene?.simData?.offense_team_id;

  for (const [playerId, sprite] of Object.entries(playerSprites || {})) {
    if (!sprite) continue;
    const info = scene?.playerInfo?.[playerId];
    const pos = info?.pos ?? '?';
    let coords = null;
    if (Number.isFinite(width) && Number.isFinite(height) && width > 0 && height > 0) {
      coords = pixelsToGrid(sprite.x, sprite.y, width, height);
      coords = { x: roundCoord(coords.x), y: roundCoord(coords.y) };
    } else if (sprite.gridX != null && sprite.gridY != null) {
      coords = { x: roundCoord(sprite.gridX), y: roundCoord(sprite.gridY) };
    }
    const row = {
      player_id: playerId,
      pos,
      coords,
      team_id: sprite.team_id ?? info?.team_id ?? null,
    };
    const isOffense = offenseTeamId != null && String(sprite.team_id) === String(offenseTeamId);
    if (isOffense) {
      offense[pos] = row;
    } else {
      defense[pos] = row;
    }
  }
  return { offense, defense };
}

export function snapshotShooterFromTurn(turnData, scene, playerSprites, label = 'shooter') {
  const shooterId =
    turnData?.shooter_id
    ?? turnData?.shooterId
    ?? turnData?.roles?.shooter_id
    ?? turnData?.ball_handler_id;
  const sprite = shooterId ? playerSprites?.[shooterId] : null;
  const info = shooterId ? scene?.playerInfo?.[shooterId] : null;
  const width = scene?.game?.config?.width;
  const height = scene?.game?.config?.height;
  let coords = turnData?.shooter_coords ?? null;
  if (!coords && sprite && width && height) {
    coords = pixelsToGrid(sprite.x, sprite.y, width, height);
    coords = { x: roundCoord(coords.x), y: roundCoord(coords.y) };
  }
  return {
    label,
    player_id: shooterId ?? null,
    pos: info?.pos ?? turnData?.shooter_pos ?? null,
    name: info?.name ?? null,
    coords,
    flss_zone: turnData?.flss_zone ?? null,
    flss: turnData?.flss ?? false,
    final_turn: turnData?.final_turn ?? false,
  };
}

export function logEoqStep(scene, flow, step, phase, turnData, context = {}, extra = {}) {
  if (!isEoqTraceEnabled(scene)) return;
  const playerSprites = context.playerSprites || scene?.playerSprites || {};
  const payload = {
    flow,
    step,
    phase,
    turn_index: turnData?.index ?? scene?.currentTurn ?? null,
    result_type: turnData?.result_type ?? null,
    flss: turnData?.flss ?? false,
    final_turn: turnData?.final_turn ?? false,
    clock: snapshotClockFromTurn(turnData, scene),
    players: snapshotPlayersFromSprites(scene, playerSprites),
    shooter: snapshotShooterFromTurn(turnData, scene, playerSprites),
    ...extra,
  };
  console.warn('[EOQ-TRACE]', payload);
}
